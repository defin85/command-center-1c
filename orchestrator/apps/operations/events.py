"""Event publishing для workflow tracking."""
import json
from typing import Any, Dict, Optional
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
            settings.CELERY_BROKER_URL,
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
