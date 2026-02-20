"""Event publishing для workflow tracking."""
import json
from typing import Any, Optional
from django.utils import timezone
from django.conf import settings
import redis
from apps.templates.tracing import get_current_trace_id


class OperationEventPublisher:
    """Publisher для workflow events в Redis Streams.

    Использует Redis Streams (XADD) вместо Pub/Sub для надёжной доставки
    и возможности replay событий через XREAD/XRANGE.

    Stream name: events:operation:{operation_id}
    """

    STREAM_MAXLEN = 1000  # Auto-trim для предотвращения OOM

    STATES = {
        'PENDING': 'Операция создана',
        'QUEUED': 'Отправлена в очередь',
        'PROCESSING': 'Обработка Worker',
        'UPLOADING': 'Загрузка файла',
        'INSTALLING': 'Установка в базу',
        'VERIFYING': 'Проверка установки',
        'SUCCESS': 'Успешно завершено',
        'FAILED': 'Ошибка выполнения',
        'TIMEOUT': 'Превышено время ожидания',
    }

    def __init__(self):
        """Инициализация Redis клиента."""
        self.redis_client = redis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
            decode_responses=True
        )
        self.logger = __import__('logging').getLogger(__name__)

    def publish(
        self,
        operation_id: str,
        state: str,
        microservice: str,
        message: Optional[str] = None,
        trace_id: Optional[str] = None,
        **metadata: Any
    ) -> None:
        """Публикует событие workflow в Redis Stream.

        Args:
            operation_id: UUID операции
            state: Состояние из STATES
            microservice: Источник события (orchestrator|celery|worker)
            message: Опциональное сообщение (по умолчанию из STATES)
            **metadata: Дополнительные данные
        """
        trace_id_value = trace_id or metadata.get("trace_id") or get_current_trace_id()
        workflow_execution_id = metadata.get("workflow_execution_id")
        node_id = metadata.get("node_id")
        root_operation_id = metadata.get("root_operation_id") or operation_id
        execution_consumer = str(metadata.get("execution_consumer") or "").strip() or "operations"
        lane = str(metadata.get("lane") or "").strip() or execution_consumer
        normalized_metadata = dict(metadata)
        normalized_metadata["root_operation_id"] = root_operation_id
        normalized_metadata["execution_consumer"] = execution_consumer
        normalized_metadata["lane"] = lane
        event = {
            "version": "1.0",
            "operation_id": operation_id,
            "timestamp": timezone.now().isoformat(),
            "trace_id": trace_id_value,
            "workflow_execution_id": workflow_execution_id,
            "node_id": node_id,
            "root_operation_id": root_operation_id,
            "execution_consumer": execution_consumer,
            "lane": lane,
            "state": state,
            "microservice": microservice,
            "message": message or self.STATES.get(state, ""),
            "metadata": normalized_metadata
        }

        stream_name = f"events:operation:{operation_id}"
        try:
            stream_fields = {
                "data": json.dumps(event),
                "operation_id": operation_id,
                "event_type": "workflow_event",
            }
            self.redis_client.xadd(
                stream_name,
                stream_fields,
                maxlen=self.STREAM_MAXLEN,
                approximate=True
            )
            self.logger.debug(
                f"Published workflow event to stream: operation_id={operation_id}, "
                f"state={state}, microservice={microservice}"
            )
        except Exception as e:
            # Log error but don't fail the operation
            self.logger.error(f"Failed to publish workflow event to stream: {e}")


# Lazy singleton instance
_event_publisher = None


def get_event_publisher() -> OperationEventPublisher:
    """Get or create event publisher singleton (lazy initialization)."""
    global _event_publisher
    if _event_publisher is None:
        _event_publisher = OperationEventPublisher()
    return _event_publisher


# Backward compatible alias
class _EventPublisherProxy:
    """Proxy for lazy initialization of event_publisher."""

    def __getattr__(self, name):
        return getattr(get_event_publisher(), name)


event_publisher = _EventPublisherProxy()


class OperationFlowPublisher:
    """Publisher для operation flow events в Service Mesh.

    Публикует события о прохождении операций через сервисы для
    визуализации Service Mesh в реальном времени.

    Использует Redis Streams (XADD) вместо Pub/Sub для надёжной доставки
    и возможности fan-out через XREAD.
    """

    STREAM_NAME = "events:service-mesh:operation-flow"
    STREAM_MAXLEN = 5000  # Auto-trim для предотвращения OOM

    def __init__(self):
        """Инициализация Redis клиента."""
        self.redis_client = redis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
            decode_responses=True
        )
        self.logger = __import__('logging').getLogger(__name__)

    def publish_flow(
        self,
        operation_id: str,
        current_service: str,
        status: str,  # processing, completed, failed
        message: str,
        operation_type: str = "",
        operation_name: str = "",
        path: list = None,
        metadata: dict = None,
        trace_id: Optional[str] = None
    ) -> None:
        """Публикует событие flow в Redis для Service Mesh визуализации.

        Args:
            operation_id: UUID операции
            current_service: Текущий сервис обрабатывающий операцию
            status: Статус операции (processing, completed, failed)
            message: Человекочитаемое сообщение о текущем действии
            operation_type: Тип операции (sync_cluster, designer_cli, etc.)
            operation_name: Имя операции для отображения
            path: Список сервисов через которые проходит операция
            metadata: Дополнительные данные операции
        """
        if not operation_id:
            self.logger.debug("Skipping flow publish: operation_id is None (fallback mode)")
            return

        path = path or []
        metadata = metadata or {}
        trace_id_value = trace_id or metadata.get("trace_id") or get_current_trace_id()
        workflow_execution_id = metadata.get("workflow_execution_id")
        node_id = metadata.get("node_id")

        # Строим path с статусами для каждого узла
        current_idx = -1
        try:
            current_idx = path.index(current_service)
        except ValueError:
            pass

        timestamp = timezone.now()

        # Формируем path с статусами
        path_with_status = []
        for idx, service in enumerate(path):
            if status == "failed":
                # При ошибке: всё до текущего - completed, текущий - failed
                if idx < current_idx:
                    node_status = "completed"
                elif idx == current_idx:
                    node_status = "failed"
                else:
                    node_status = "pending"
            elif status == "completed":
                # При завершении: все сервисы в path - completed
                node_status = "completed"
            else:
                # processing: до текущего - completed, текущий - active, после - pending
                if idx < current_idx:
                    node_status = "completed"
                elif idx == current_idx:
                    node_status = "active"
                else:
                    node_status = "pending"

            path_with_status.append({
                "service": service,
                "status": node_status,
                "timestamp": timestamp.isoformat() if node_status != "pending" else None
            })

        # Формируем edges
        edges = []
        for i in range(len(path) - 1):
            from_service = path[i]
            to_service = path[i + 1]

            # Определяем статус edge
            to_idx = i + 1

            if status == "failed":
                if to_idx < current_idx:
                    edge_status = "completed"
                elif to_idx == current_idx:
                    edge_status = "failed"
                else:
                    edge_status = "pending"
            elif status == "completed":
                edge_status = "completed"
            else:
                if to_idx < current_idx:
                    edge_status = "completed"
                elif to_idx == current_idx:
                    edge_status = "active"
                else:
                    edge_status = "pending"

            edges.append({
                "from": from_service,
                "to": to_service,
                "status": edge_status
            })

        # Формируем полное событие
        event = {
            "version": "1.0",
            "type": "operation_flow_update",
            "operation_id": operation_id,
            "timestamp": timestamp.isoformat(),
            "trace_id": trace_id_value,
            "workflow_execution_id": workflow_execution_id,
            "node_id": node_id,
            "flow": {
                "current_service": current_service,
                "path": path_with_status,
                "edges": edges
            },
            "operation": {
                "type": operation_type,
                "name": operation_name,
                "status": status,
                "message": message,
                "metadata": metadata
            }
        }

        try:
            # Формируем данные для XADD (формат как в других streams проекта)
            stream_fields = {
                "data": json.dumps(event),
                "operation_id": operation_id,
                "event_type": "operation_flow_update",
            }

            self.redis_client.xadd(
                self.STREAM_NAME,
                stream_fields,
                maxlen=self.STREAM_MAXLEN,
                approximate=True
            )
            self.logger.debug(
                f"Published flow event to stream: operation_id={operation_id}, "
                f"service={current_service}, status={status}"
            )
        except Exception as e:
            # Логируем ошибку, но не прерываем операцию
            self.logger.error(f"Failed to publish flow event to stream: {e}")


# Lazy singleton instance для flow events
_flow_publisher = None


def get_flow_publisher() -> OperationFlowPublisher:
    """Get or create flow publisher singleton (lazy initialization)."""
    global _flow_publisher
    if _flow_publisher is None:
        _flow_publisher = OperationFlowPublisher()
    return _flow_publisher


# Backward compatible alias
class _FlowPublisherProxy:
    """Proxy for lazy initialization of flow_publisher."""

    def __getattr__(self, name):
        return getattr(get_flow_publisher(), name)


flow_publisher = _FlowPublisherProxy()
