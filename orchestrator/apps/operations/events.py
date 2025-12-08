"""Event publishing для workflow tracking."""
import json
from typing import Any, Optional
from django.utils import timezone
from django.conf import settings
import redis


class OperationEventPublisher:
    """Publisher для workflow events в Redis PubSub."""

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

    def publish(
        self,
        operation_id: str,
        state: str,
        microservice: str,
        message: Optional[str] = None,
        **metadata: Any
    ) -> None:
        """Публикует событие workflow в Redis PubSub.

        Args:
            operation_id: UUID операции
            state: Состояние из STATES
            microservice: Источник события (orchestrator|celery|worker)
            message: Опциональное сообщение (по умолчанию из STATES)
            **metadata: Дополнительные данные
        """
        event = {
            "version": "1.0",
            "operation_id": operation_id,
            "timestamp": timezone.now().isoformat(),
            "state": state,
            "microservice": microservice,
            "message": message or self.STATES.get(state, ""),
            "metadata": metadata
        }

        channel = f"operation:{operation_id}:events"
        try:
            self.redis_client.publish(channel, json.dumps(event))
        except Exception as e:
            # Log error but don't fail the operation
            print(f"Failed to publish event: {e}")


# Singleton instance
event_publisher = OperationEventPublisher()


class OperationFlowPublisher:
    """Publisher для operation flow events в Service Mesh.

    Публикует события о прохождении операций через сервисы для
    визуализации Service Mesh в реальном времени.
    """

    CHANNEL = "service_mesh:operation_flow"

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
        metadata: dict = None
    ) -> None:
        """Публикует событие flow в Redis для Service Mesh визуализации.

        Args:
            operation_id: UUID операции
            current_service: Текущий сервис обрабатывающий операцию
            status: Статус операции (processing, completed, failed)
            message: Человекочитаемое сообщение о текущем действии
            operation_type: Тип операции (sync_cluster, install_extension, etc.)
            operation_name: Имя операции для отображения
            path: Список сервисов через которые проходит операция
            metadata: Дополнительные данные операции
        """
        if not operation_id:
            self.logger.debug("Skipping flow publish: operation_id is None (fallback mode)")
            return

        path = path or []
        metadata = metadata or {}

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
            from_idx = i
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
            self.redis_client.publish(self.CHANNEL, json.dumps(event))
            self.logger.debug(
                f"Published flow event: operation_id={operation_id}, "
                f"service={current_service}, status={status}"
            )
        except Exception as e:
            # Логируем ошибку, но не прерываем операцию
            self.logger.error(f"Failed to publish flow event: {e}")


# Singleton instance для flow events
flow_publisher = OperationFlowPublisher()
