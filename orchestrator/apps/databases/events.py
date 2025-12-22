"""Database event publishing to Redis Streams."""

import json
import logging
from typing import Any, Optional

import redis
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class DatabaseEventPublisher:
    """Publisher for database update events."""

    STREAM_NAME = "events:databases"
    STREAM_MAXLEN = 10000

    def __init__(self) -> None:
        self.redis_client = redis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
            decode_responses=True,
        )

    def publish(
        self,
        *,
        action: str,
        database_id: str,
        cluster_id: Optional[str],
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        event = {
            "version": "1.0",
            "type": "database_update",
            "action": action,
            "database_id": database_id,
            "cluster_id": cluster_id,
            "timestamp": timezone.now().isoformat(),
            "metadata": metadata or {},
        }

        try:
            self.redis_client.xadd(
                self.STREAM_NAME,
                {
                    "data": json.dumps(event),
                    "database_id": database_id,
                    "cluster_id": cluster_id or "",
                    "event_type": event["type"],
                },
                maxlen=self.STREAM_MAXLEN,
                approximate=True,
            )
        except Exception as exc:
            logger.warning("Failed to publish database stream event: %s", exc)


_database_event_publisher: Optional[DatabaseEventPublisher] = None


def get_database_event_publisher() -> DatabaseEventPublisher:
    global _database_event_publisher
    if _database_event_publisher is None:
        _database_event_publisher = DatabaseEventPublisher()
    return _database_event_publisher


class _DatabaseEventPublisherProxy:
    def __getattr__(self, name):
        return getattr(get_database_event_publisher(), name)


database_event_publisher = _DatabaseEventPublisherProxy()
