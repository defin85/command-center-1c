"""Centralized Redis client for operations app."""
import redis
import json
import logging
from django.conf import settings
from django.utils import timezone
from typing import Optional, Dict, Any
import uuid

logger = logging.getLogger(__name__)

# Import Prometheus metrics with availability flag
try:
    from .prometheus_metrics import record_redis_event_published
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    record_redis_event_published = None


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
            "payload": message,  # object, not string - Go expects json.RawMessage
            "metadata": {}       # object, not string - Go expects map[string]interface{}
        }

    def enqueue_operation_stream(self, message: Dict[str, Any]) -> Optional[str]:
        """
        Push message to operations stream (Redis Streams).

        Args:
            message: Operation message (v2.0 schema)

        Returns:
            Stream message ID

        Raises:
            Exception: If stream write fails (propagate to rollback transaction)
        """
        # Create envelope and serialize to JSON BEFORE creating stream_fields (FIX #6)
        # This ensures json.dumps failure happens before any partial state
        envelope = self._create_envelope(message)
        envelope_json = json.dumps(envelope)  # May raise - happens before stream_fields

        # XADD with data field containing JSON envelope
        # Fallback fields are duplicated outside envelope for recovery
        # when parsing fails (Error Feedback Phase 1)
        stream_fields = {
            "data": envelope_json,
            "correlation_id": envelope.get("correlation_id", ""),
            "operation_id": message.get("operation_id", ""),
            "event_type": envelope.get("event_type", ""),
        }

        try:
            msg_id = self.client.xadd(
                self.STREAM_COMMANDS,
                stream_fields,
                maxlen=self.STREAM_MAX_LEN
            )

            # Record Prometheus metric for published event
            if METRICS_AVAILABLE:
                try:
                    event_type = envelope.get("event_type")
                    if not event_type:
                        logger.warning(f"Missing event_type in envelope: {envelope.get('correlation_id')}")
                        event_type = "unknown"
                    record_redis_event_published(event_type, self.STREAM_COMMANDS)
                except Exception as metric_err:
                    logger.warning(f"Failed to record redis event metric: {metric_err}")

            return msg_id
        except Exception as e:
            # FIX #3: raise instead of return None to propagate exception
            # This allows transaction rollback in calling code
            logger.error(f"Stream write failed for operation_id={message.get('operation_id')}: {e}")
            raise  # Propagate exception to rollback transaction

    def enqueue_operation(self, message: Dict[str, Any]) -> bool:
        """
        Push message to operations stream (Redis Streams).

        Args:
            message: Operation message (v2.0 schema)

        Returns:
            True if success

        Note:
            This method catches exceptions for backward compatibility.
            Use enqueue_operation_stream() directly if you need exception propagation
            for transaction rollback.
        """
        try:
            msg_id = self.enqueue_operation_stream(message)
            return msg_id is not None
        except Exception:
            return False

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

    # ========== Enqueue Locks (Orchestrator-side duplicate prevention) ==========
    # These locks prevent duplicate enqueue requests from reaching the queue.
    # Key format: cc1c:enqueue:{task_id}:lock
    # Worker uses different key (cc1c:task:{task_id}:lock) for processing idempotency.

    def acquire_enqueue_lock(self, task_id: str, ttl_seconds: int = 3600) -> bool:
        """
        Acquire enqueue lock to prevent duplicate submissions.

        This lock is used by Orchestrator to prevent the same operation
        from being enqueued multiple times (e.g., double-click protection).

        Note: Worker uses separate lock (REDIS_KEY_TASK_LOCK) for processing.

        Args:
            task_id: Operation/Task ID
            ttl_seconds: Lock TTL (default 1 hour)

        Returns:
            True if lock acquired, False if already exists
        """
        key = settings.REDIS_KEY_ENQUEUE_LOCK.format(task_id=task_id)
        return self.client.set(key, "orchestrator", nx=True, ex=ttl_seconds)

    def release_enqueue_lock(self, task_id: str) -> bool:
        """Release enqueue lock (on error before queue)."""
        key = settings.REDIS_KEY_ENQUEUE_LOCK.format(task_id=task_id)
        return self.client.delete(key) > 0

    def check_enqueue_lock(self, task_id: str) -> bool:
        """Check if enqueue lock exists."""
        key = settings.REDIS_KEY_ENQUEUE_LOCK.format(task_id=task_id)
        return self.client.exists(key) > 0

    # ========== Legacy Task Locks (kept for backward compatibility) ==========
    # WARNING: These use cc1c:task:{task_id}:lock which conflicts with Worker!
    # Use acquire_enqueue_lock() for Orchestrator-side locking instead.
    # These methods are kept for special cases (sync_cluster, discover_clusters).

    def acquire_lock(self, task_id: str, ttl_seconds: int = 3600) -> bool:
        """
        Acquire idempotency lock (legacy - use acquire_enqueue_lock for new code).

        WARNING: This uses REDIS_KEY_TASK_LOCK which may conflict with Worker.
        For operation enqueue, use acquire_enqueue_lock() instead.
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

    # ========== Timeline Operations ==========

    TIMELINE_KEY_PREFIX = "operation:timeline:"
    TIMELINE_MAX_LEN = 5000
    TIMELINE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days

    def add_timeline_event(
        self,
        operation_id: str,
        *,
        event: str,
        service: str,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp_ms: Optional[int] = None,
    ) -> None:
        """
        Append a timeline event into Redis ZSET.

        Stored format:
          score: timestamp_ms
          member: JSON with at least {event, service, metadata}
        """
        key = f"{self.TIMELINE_KEY_PREFIX}{operation_id}"
        ts_ms = timestamp_ms if timestamp_ms is not None else int(timezone.now().timestamp() * 1000)
        member = json.dumps(
            {
                "id": str(uuid.uuid4()),
                "event": event,
                "service": service,
                "metadata": metadata or {},
            }
        )

        self.client.zadd(key, {member: ts_ms})

        # Best-effort cap + TTL
        try:
            size = self.client.zcard(key)
            if size > self.TIMELINE_MAX_LEN:
                # Remove oldest (lowest scores)
                self.client.zremrangebyrank(key, 0, size - self.TIMELINE_MAX_LEN - 1)
            self.client.expire(key, self.TIMELINE_TTL_SECONDS)
        except Exception as e:
            logger.debug("Timeline cap/ttl update failed: %s", e)

    def get_timeline(
        self,
        operation_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[list[dict], int]:
        """
        Get operation timeline from Redis ZSET.

        Args:
            operation_id: Operation ID
            limit: Max events to return
            offset: Starting offset

        Returns:
            (events_list, total_count)
        """
        key = f"{self.TIMELINE_KEY_PREFIX}{operation_id}"

        # Get total count
        total = self.client.zcard(key)

        # Get range with scores (sorted by timestamp ascending)
        start = offset
        end = offset + limit - 1
        results = self.client.zrange(key, start, end, withscores=True)

        events = []
        for member, score in results:
            try:
                data = json.loads(member)
                events.append({
                    "timestamp": int(score),
                    "event": data.get("event", ""),
                    "service": data.get("service", ""),
                    "metadata": data.get("metadata", {})
                })
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Invalid JSON in timeline for {operation_id}: {str(member)[:100]}, error: {e}"
                )
                continue

        return events, total

    def get_timeline_duration(self, operation_id: str) -> Optional[int]:
        """
        Get duration from first to last event in timeline.

        Args:
            operation_id: Operation ID

        Returns:
            Duration in milliseconds or None if < 2 events
        """
        key = f"{self.TIMELINE_KEY_PREFIX}{operation_id}"

        # Get first event
        first = self.client.zrange(key, 0, 0, withscores=True)
        if not first:
            return None

        # Get last event
        last = self.client.zrange(key, -1, -1, withscores=True)
        if not last or first[0][1] == last[0][1]:
            return None

        return int(last[0][1] - first[0][1])

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
