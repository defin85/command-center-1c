# Tasks package for operations
from apps.operations.tasks.event_replay import replay_failed_events
from celery import shared_task
import logging

from apps.operations.models import BatchOperation, Task
from apps.operations.redis_client import redis_client
from apps.operations.events import event_publisher

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=60,  # 60 seconds graceful
    time_limit=70,       # 70 seconds hard
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=300,  # Max 5 minutes
    retry_jitter=True    # Add randomness
)
def enqueue_operation(self, operation_id: str):
    """
    Enqueue operation to Go worker queue.

    Message Protocol v2.0:
    - Build message according to v2.0 schema
    - Check idempotency lock
    - Push to Redis queue: cc1c:operations:v1
    - Update operation status

    Args:
        operation_id: BatchOperation ID (UUID string)

    Returns:
        dict: {"status": "queued|duplicate", "operation_id": "..."}
    """
    logger.info(f"Enqueuing operation {operation_id}")

    try:
        # 1. Get operation from DB
        operation = BatchOperation.objects.get(id=operation_id)

        # 2. Idempotency check - acquire lock
        lock_acquired = redis_client.acquire_lock(
            task_id=operation_id,
            ttl_seconds=3600  # 1 hour
        )

        if not lock_acquired:
            logger.warning(
                f"Operation {operation_id} already locked (duplicate submission)"
            )
            return {
                "status": "duplicate",
                "operation_id": operation_id
            }

        # 3. Build Message Protocol v2.0 message
        message = {
            "version": "2.0",
            "operation_id": str(operation.id),
            "batch_id": None,  # TODO: Implement batch grouping
            "operation_type": operation.operation_type,
            "entity": operation.target_entity,

            "target_databases": [
                str(db.id) for db in operation.target_databases.all()
            ],

            "payload": {
                "data": operation.payload.get("data", {}),
                "filters": operation.payload.get("filters", {}),
                "options": operation.payload.get("options", {})
            },

            "execution_config": {
                "batch_size": operation.config.get("batch_size", 100),
                "timeout_seconds": 30,
                "retry_count": 3,
                "priority": "normal",
                "idempotency_key": str(operation.id)
            },

            "metadata": {
                "created_by": operation.created_by or "system",
                "created_at": operation.created_at.isoformat(),
                "template_id": str(operation.template.id) if operation.template else None,
                "tags": operation.metadata.get("tags", [])
            }
        }

        # 4. Enqueue to Redis
        redis_client.enqueue_operation(message)

        # 4.1. Publish QUEUED event for real-time tracking
        event_publisher.publish(
            operation_id=str(operation_id),
            state='QUEUED',
            microservice='celery',
            message="Operation enqueued to worker"
        )

        # 5. Update operation status
        operation.status = 'QUEUED'
        operation.save(update_fields=['status'])

        logger.info(f"Operation {operation_id} queued successfully")

        return {
            "status": "queued",
            "operation_id": str(operation_id)
        }

    except BatchOperation.DoesNotExist:
        logger.error(f"Operation {operation_id} not found")
        raise
    except Exception as e:
        logger.exception(f"Error enqueuing operation {operation_id}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


__all__ = ["replay_failed_events", "enqueue_operation"]
