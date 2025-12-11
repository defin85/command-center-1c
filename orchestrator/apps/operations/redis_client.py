"""Centralized Redis client for operations app."""
import redis
import json
from django.conf import settings
from django.utils import timezone
from typing import Optional, Dict, Any


class RedisClient:
    """Wrapper для Redis операций."""

    # Stream constants (Phase 0 migration)
    STREAM_COMMANDS = "commands:worker:operations"
    STREAM_MAX_LEN = 10000  # Limit stream size

    def __init__(self):
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT),
            db=int(settings.REDIS_DB),
            decode_responses=True
        )

    # ========== Queue Operations ==========

    def _create_envelope(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Create envelope for Redis Streams (compatible with Go shared/events)."""
        import uuid
        from datetime import datetime

        return {
            "version": "1.0",
            "message_id": str(uuid.uuid4()),
            "correlation_id": message.get("operation_id", str(uuid.uuid4())),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": "operation.created",
            "service_name": "orchestrator",
            "payload": json.dumps(message),
            "metadata": json.dumps({})
        }

    def enqueue_operation_stream(self, message: Dict[str, Any]) -> Optional[str]:
        """
        Push message to operations stream (Redis Streams).

        Args:
            message: Operation message (v2.0 schema)

        Returns:
            Stream message ID or None on error
        """
        try:
            envelope = self._create_envelope(message)
            # XADD with data field containing JSON envelope
            msg_id = self.client.xadd(
                self.STREAM_COMMANDS,
                {"data": json.dumps(envelope)},
                maxlen=self.STREAM_MAX_LEN
            )
            return msg_id
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Stream write failed: {e}")
            return None

    def enqueue_operation(self, message: Dict[str, Any]) -> bool:
        """
        Push message to operations stream (Redis Streams).

        Args:
            message: Operation message (v2.0 schema)

        Returns:
            True if success
        """
        msg_id = self.enqueue_operation_stream(message)
        return msg_id is not None

    def enqueue_dlq(self, message: Dict[str, Any]) -> bool:
        """Push failed message to DLQ."""
        queue = settings.REDIS_QUEUE_DLQ
        self.client.lpush(queue, json.dumps(message))
        return True

    def get_queue_depth(self, queue_name: str = None) -> int:
        """Get stream length (operations queue)."""
        # Use Stream instead of LIST
        return self.get_stream_depth(self.STREAM_COMMANDS)

    def get_stream_depth(self, stream_name: str) -> int:
        """Get Redis Stream length."""
        try:
            return self.client.xlen(stream_name)
        except Exception:
            return 0

    # ========== Idempotency Locks ==========

    def acquire_lock(self, task_id: str, ttl_seconds: int = 3600) -> bool:
        """
        Acquire idempotency lock.

        Args:
            task_id: Operation/Task ID
            ttl_seconds: Lock TTL (default 1 hour)

        Returns:
            True if lock acquired, False if already exists
        """
        key = settings.REDIS_KEY_TASK_LOCK.format(task_id=task_id)
        return self.client.set(key, "locked", nx=True, ex=ttl_seconds)

    def extend_lock(self, task_id: str, ttl_seconds: int = 86400) -> bool:
        """Extend lock TTL (e.g., on completion to 24 hours)."""
        key = settings.REDIS_KEY_TASK_LOCK.format(task_id=task_id)
        return self.client.expire(key, ttl_seconds)

    def release_lock(self, task_id: str) -> bool:
        """Release lock (delete key)."""
        key = settings.REDIS_KEY_TASK_LOCK.format(task_id=task_id)
        return self.client.delete(key) > 0

    def check_lock(self, task_id: str) -> bool:
        """Check if lock exists."""
        key = settings.REDIS_KEY_TASK_LOCK.format(task_id=task_id)
        return self.client.exists(key) > 0

    # ========== Progress Tracking ==========

    def update_progress(self, task_id: str, progress: int, status: str) -> bool:
        """
        Update task progress.

        Args:
            task_id: Task ID
            progress: Progress percentage (0-100)
            status: Status string (processing, completed, etc.)
        """
        key = settings.REDIS_KEY_TASK_PROGRESS.format(task_id=task_id)
        self.client.hset(key, mapping={
            "progress": progress,
            "status": status,
            "updated_at": str(timezone.now())
        })
        self.client.expire(key, 3600)  # 1 hour TTL
        return True

    def get_progress(self, task_id: str) -> Optional[Dict[str, str]]:
        """Get task progress."""
        key = settings.REDIS_KEY_TASK_PROGRESS.format(task_id=task_id)
        data = self.client.hgetall(key)
        return data if data else None


# Singleton instance
redis_client = RedisClient()
