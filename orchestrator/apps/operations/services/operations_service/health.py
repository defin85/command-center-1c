from __future__ import annotations

import uuid

from ...models import BatchOperation
from ...events import event_publisher, flow_publisher
from ...redis_client import redis_client
from .types import EnqueueResult, _record_batch_metric, classify_enqueue_error_code, logger


class OperationsServiceHealthMixin:
    @classmethod
    def enqueue_health_check(
        cls,
        database_ids: list[str],
        created_by: str = "system",
    ) -> EnqueueResult:
        """
        Enqueue health check operation for multiple databases.

        Args:
            database_ids: List of database UUIDs to check
            created_by: User who initiated the operation

        Returns:
            EnqueueResult with generated operation_id
        """
        from apps.databases.models import Database
        from apps.operations.models import Task

        databases = list(Database.objects.filter(id__in=database_ids))
        if not databases:
            return EnqueueResult(
                success=False,
                operation_id="",
                status="error",
                error="No valid databases found for the provided IDs",
                error_code="VALIDATION_ERROR",
            )

        operation_id = str(uuid.uuid4())

        batch_operation = BatchOperation.objects.create(
            id=operation_id,
            name=f"health_check - {len(databases)} databases",
            operation_type="health_check",
            target_entity="Database",
            status=BatchOperation.STATUS_PENDING,
            payload={"data": {}, "filters": {}, "options": {"check_odata": True}},
            config={
                "batch_size": 50,
                "timeout_seconds": 30,
                "retry_count": 1,
                "priority": "low",
            },
            total_tasks=len(databases),
            created_by=created_by,
        )
        batch_operation.target_databases.set(databases)
        workflow_metadata = cls._get_workflow_metadata(batch_operation)

        tasks = [
            Task(
                id=str(uuid.uuid4()),
                batch_operation=batch_operation,
                database=db,
                status=Task.STATUS_PENDING,
            )
            for db in databases
        ]
        Task.objects.bulk_create(tasks)

        try:
            redis_client.add_timeline_event(
                operation_id,
                event="operation.created",
                service="orchestrator",
                metadata={
                    "operation_type": "health_check",
                    "target_databases_count": len(databases),
                    "created_by": created_by,
                    **workflow_metadata,
                },
            )
        except Exception:
            pass

        message = cls._build_execution_envelope(
            operation_id=operation_id,
            operation_type="health_check",
            entity="Database",
            target_databases=[cls._build_target_database_data(db) for db in databases],
            payload_data={},
            payload_options={"check_odata": True},
            execution_config={
                "batch_size": 50,  # Check 50 at a time
                "timeout_seconds": 30,  # 30 seconds per database
                "retry_count": 1,
                "priority": "low",
                "idempotency_key": operation_id,
            },
            metadata={
                "created_by": created_by,
                "template_id": None,
                "tags": ["health_check", "monitoring"],
            },
        )

        try:
            redis_client.acquire_enqueue_lock(task_id=operation_id, ttl_seconds=3600)
            msg_id = redis_client.enqueue_operation_stream(message)

            try:
                redis_client.add_timeline_event(
                    operation_id,
                    event="operation.queued",
                    service="orchestrator",
                    metadata={"queue": cls.QUEUE_KEY, **workflow_metadata},
                )
            except Exception:
                pass

            database_count = len(databases)

            event_publisher.publish(
                operation_id=operation_id,
                state="QUEUED",
                microservice="orchestrator",
                queue=cls.QUEUE_KEY,
                target_databases_count=database_count,
                **workflow_metadata,
            )

            flow_publisher.publish_flow(
                operation_id=operation_id,
                current_service="orchestrator",
                status="processing",
                message="Health check queued",
                operation_type="health_check",
                operation_name=batch_operation.name,
                path=["frontend", "api-gateway", "orchestrator", "worker"],
                metadata={
                    "target_databases_count": database_count,
                    "queue": cls.QUEUE_KEY,
                    **workflow_metadata,
                },
            )

            batch_operation.status = BatchOperation.STATUS_QUEUED
            batch_operation.save(update_fields=["status", "updated_at"])

            logger.info(
                f"Health check operation {operation_id} enqueued",
                extra={
                    "operation_id": operation_id,
                    "database_count": database_count,
                },
            )

            _record_batch_metric("health_check", "queued")

            return EnqueueResult(
                success=True,
                operation_id=operation_id,
                status="queued",
                metadata={"database_count": database_count, "stream_message_id": msg_id},
            )

        except Exception as exc:
            logger.error(f"Error enqueueing health check: {exc}", exc_info=True)
            try:
                redis_client.release_enqueue_lock(task_id=operation_id)
            except Exception:
                pass
            batch_operation.status = BatchOperation.STATUS_FAILED
            batch_operation.save(update_fields=["status", "updated_at"])
            _record_batch_metric("health_check", "error")
            return EnqueueResult(
                success=False,
                operation_id=operation_id,
                status="error",
                error=str(exc),
                error_code=classify_enqueue_error_code(exc),
            )
