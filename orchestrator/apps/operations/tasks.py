"""Celery tasks for operations."""
from celery import shared_task
from django.utils import timezone
import logging

from .models import BatchOperation, Task
from .redis_client import redis_client
from .events import event_publisher

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
            "batch_id": None,  # TODO: Implement batch grouping in Phase 2
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
            queue="cc1c:operations:v1",
            target_databases_count=len(message["target_databases"])
        )

        # 5. Update operation status
        operation.status = BatchOperation.STATUS_QUEUED
        operation.celery_task_id = self.request.id
        operation.save(update_fields=["status", "celery_task_id", "updated_at"])

        logger.info(
            f"Operation {operation_id} enqueued successfully",
            extra={
                "operation_id": operation_id,
                "operation_type": operation.operation_type,
                "target_databases_count": len(message["target_databases"])
            }
        )

        return {
            "status": "queued",
            "operation_id": operation_id,
            "celery_task_id": self.request.id
        }

    except BatchOperation.DoesNotExist:
        logger.error(f"Operation {operation_id} not found in database")
        raise

    except Exception as exc:
        logger.error(
            f"Error enqueueing operation {operation_id}: {exc}",
            exc_info=True
        )

        # Release lock on error
        redis_client.release_lock(operation_id)

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def process_operation_with_template(self, operation_id: str):
    """
    Process operation using template engine.

    Flow:
    1. Load operation from DB
    2. If operation has template → render template
    3. Push rendered payload to Redis queue (TODO: Track 2)
    4. Monitor execution

    Args:
        operation_id: BatchOperation UUID

    Returns:
        dict with status and result
    """
    from apps.operations.models import BatchOperation
    from apps.templates.engine import TemplateRenderer, TemplateValidationError, TemplateRenderError

    try:
        # 1. Load operation
        operation = BatchOperation.objects.get(id=operation_id)
        operation.status = 'processing'
        operation.save()

        logger.info(
            f"Processing operation {operation_id}",
            extra={'operation_id': operation_id, 'template_id': str(operation.template_id) if operation.template else None}
        )

        # 2. If operation has template → render it
        if operation.template:
            renderer = TemplateRenderer()

            # Prepare context data
            context_data = {
                'operation_id': str(operation.id),
                **operation.payload  # User-provided variables
            }

            # Add database info if target_databases set
            if operation.target_databases.exists():
                first_db = operation.target_databases.first()
                context_data.update({
                    'database_name': first_db.name,
                    'database_type': getattr(first_db, 'type', 'unknown'),
                    'database_id': str(first_db.id)
                })

            # Render template (with validation + caching!)
            try:
                rendered_payload = renderer.render(
                    template=operation.template,
                    context_data=context_data,
                    validate=True  # Validate before render
                )

                # Update operation payload with rendered data
                operation.payload = rendered_payload
                operation.save()

                logger.info(
                    f"Template rendered successfully for operation {operation_id}",
                    extra={
                        'operation_id': operation_id,
                        'template_id': str(operation.template.id)
                    }
                )

            except (TemplateValidationError, TemplateRenderError) as exc:
                # Template validation or rendering failed
                operation.status = 'failed'
                operation.save()

                logger.error(
                    f"Template error for operation {operation_id}: {exc}",
                    extra={'operation_id': operation_id}
                )

                raise  # Re-raise to mark Celery task as failed

        # 3. TODO (Track 2): Push to Redis queue for Go workers
        # from apps.operations.queue import push_to_worker_queue
        # push_to_worker_queue(operation)

        # For now, mark as completed (no actual execution yet)
        operation.status = 'completed'
        operation.save()

        logger.info(
            f"Operation {operation_id} completed (template rendered)",
            extra={'operation_id': operation_id}
        )

        return {
            'status': 'success',
            'operation_id': operation_id,
            'template_rendered': operation.template is not None
        }

    except (TemplateValidationError, TemplateRenderError):
        raise  # Already logged above

    except Exception as exc:
        logger.error(
            f"Error processing operation {operation_id}: {exc}",
            extra={'operation_id': operation_id},
            exc_info=True
        )

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60)


@shared_task
def process_operation_result(result_data: dict):
    """
    Process operation result from Go worker.

    Called when worker publishes result to Redis results queue.
    Alternative to HTTP callback.

    Args:
        result_data: OperationResult dict from worker
    """
    operation_id = result_data.get("operation_id")
    status_val = result_data.get("status")
    results = result_data.get("results", [])

    logger.info(f"Processing result for operation {operation_id}, status={status_val}")

    try:
        operation = BatchOperation.objects.get(id=operation_id)

        # Update operation status
        if status_val == "completed":
            operation.status = BatchOperation.STATUS_COMPLETED
        elif status_val == "failed":
            operation.status = BatchOperation.STATUS_FAILED
        else:
            operation.status = BatchOperation.STATUS_PROCESSING

        # Update tasks
        for result in results:
            database_id = result.get("database_id")
            success = result.get("success")

            try:
                task = Task.objects.get(
                    batch_operation=operation,
                    database_id=database_id
                )

                if success:
                    task.mark_completed(result=result.get("data"))
                else:
                    task.mark_failed(
                        error_message=result.get("error", "Unknown error"),
                        error_code=result.get("error_code", "UNKNOWN_ERROR")
                    )
            except Task.DoesNotExist:
                logger.warning(
                    f"Task not found for database {database_id} in operation {operation_id}"
                )

        # Update operation progress
        operation.update_progress()

        # Extend lock to 24 hours (prevent re-execution)
        redis_client.extend_lock(operation_id, ttl_seconds=86400)

    except BatchOperation.DoesNotExist:
        logger.error(f"Operation {operation_id} not found")


@shared_task
def process_batch_operation(batch_id: str):
    """
    Process a batch operation.

    Args:
        batch_id: ID of the batch operation
    """
    logger.info(f"Processing batch operation {batch_id}")

    # TODO: Implement batch processing
    # 1. Get all operations in batch
    # 2. Queue each operation
    # 3. Track progress
    # 4. Update batch status

    pass


@shared_task
def cleanup_old_operations():
    """Clean up old completed/failed operations."""
    logger.info("Cleaning up old operations")

    # TODO: Implement cleanup logic
    # Delete operations older than 30 days

    pass
