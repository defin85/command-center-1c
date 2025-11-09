"""Celery tasks for operations."""
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_operation(self, operation_id: str):
    """
    Process an operation asynchronously.

    Args:
        operation_id: ID of the operation to process
    """
    logger.info(f"Processing operation {operation_id}")

    # TODO: Implement actual operation processing
    # 1. Get operation from database
    # 2. Validate operation data
    # 3. Push to Redis queue for Go workers
    # 4. Monitor execution
    # 5. Update operation status

    try:
        # Placeholder implementation
        pass
    except Exception as exc:
        logger.error(f"Error processing operation {operation_id}: {exc}")
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
