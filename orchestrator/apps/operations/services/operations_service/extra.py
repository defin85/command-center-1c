from __future__ import annotations

import uuid

from django.utils import timezone

from ...models import BatchOperation
from ...events import event_publisher, flow_publisher
from ...redis_client import redis_client
from .types import _record_batch_metric, logger


class OperationsServiceExtraMixin:
    @classmethod
    def get_queue_depth(cls) -> int:
        """Get current operations queue depth."""
        return redis_client.get_queue_depth(cls.QUEUE_KEY)

    @classmethod
    def enqueue_ras_operation(
        cls,
        operation_type: str,
        database_ids: list,
        config: dict,
        user,
    ) -> BatchOperation:
        """
        Create BatchOperation for RAS operation and enqueue to Redis.

        Args:
            operation_type: lock_scheduled_jobs, unlock_scheduled_jobs,
                           block_sessions, unblock_sessions, terminate_sessions
            database_ids: List of database UUIDs
            config: Operation-specific config (message, permission_code for block_sessions)
            user: User who initiated the operation

        Returns:
            BatchOperation instance

        Raises:
            ValueError: If no valid databases found
        """
        from apps.databases.models import Database
        from apps.operations.models import Task

        # Check for conflicting operations
        has_conflict, error_msg = cls.check_conflicting_operations(database_ids, operation_type)
        if has_conflict:
            raise ValueError(error_msg)

        # Get databases with cluster data
        databases = list(Database.objects.filter(id__in=database_ids).select_related("cluster"))

        if not databases:
            raise ValueError("No valid databases found for the provided IDs")

        # Generate operation ID
        operation_id = str(uuid.uuid4())

        # Create BatchOperation
        batch_operation = BatchOperation.objects.create(
            id=operation_id,
            name=f"{operation_type} - {len(databases)} databases",
            operation_type=operation_type,
            target_entity="Infobase",
            status=BatchOperation.STATUS_PENDING,
            payload={"data": config, "filters": {}, "options": {}},
            config={
                "batch_size": 1,
                "timeout_seconds": 60,
                "retry_count": 3,
                "priority": "normal",
            },
            total_tasks=len(databases),
            created_by=user.username if user else "system",
        )
        batch_operation.target_databases.set(databases)
        workflow_metadata = cls._get_workflow_metadata(batch_operation)

        # Timeline: operation created (best-effort)
        try:
            redis_client.add_timeline_event(
                operation_id,
                event="operation.created",
                service="orchestrator",
                metadata={
                    "operation_type": operation_type,
                    "target_databases_count": len(databases),
                    "created_by": user.username if user else "system",
                    **workflow_metadata,
                },
            )
        except Exception:
            pass

        # Create Tasks for each database
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

        # Build Message Protocol v2.0 message
        message = {
            "version": cls.VERSION,
            "operation_id": operation_id,
            "batch_id": None,
            "operation_type": operation_type,
            "entity": "Infobase",
            "target_databases": [cls._build_target_database_data(db) for db in databases],
            "payload": {"data": config, "filters": {}, "options": {}},
            "execution_config": {
                "batch_size": 1,
                "timeout_seconds": 60,
                "retry_count": 3,
                "priority": "normal",
                "idempotency_key": operation_id,
            },
            "metadata": {
                "created_by": user.username if user else "system",
                "created_at": timezone.now().isoformat(),
                "template_id": None,
                "tags": ["ras", operation_type],
            },
        }

        try:
            # Acquire enqueue lock (separate key from Worker's task lock)
            # This prevents duplicate enqueue, Worker handles processing idempotency
            redis_client.acquire_enqueue_lock(task_id=operation_id, ttl_seconds=3600)  # 1 hour

            # Enqueue to Redis
            redis_client.enqueue_operation_stream(message)

            # Timeline: operation queued (best-effort)
            try:
                redis_client.add_timeline_event(
                    operation_id,
                    event="operation.queued",
                    service="orchestrator",
                    metadata={"queue": cls.QUEUE_KEY, **workflow_metadata},
                )
            except Exception:
                pass

            # Publish QUEUED event
            event_publisher.publish(
                operation_id=operation_id,
                state="QUEUED",
                microservice="orchestrator",
                queue=cls.QUEUE_KEY,
                target_databases_count=len(databases),
                **workflow_metadata,
            )

            # Publish flow event for Service Mesh visualization
            flow_publisher.publish_flow(
                operation_id=operation_id,
                current_service="orchestrator",
                status="processing",
                message=f"Operation queued: {operation_type}",
                operation_type=operation_type,
                operation_name=batch_operation.name,
                path=["frontend", "api-gateway", "orchestrator", "worker"],
                metadata={
                    "target_databases_count": len(databases),
                    "queue": cls.QUEUE_KEY,
                    **workflow_metadata,
                },
            )

            # Update status to QUEUED
            batch_operation.status = BatchOperation.STATUS_QUEUED
            batch_operation.save(update_fields=["status", "updated_at"])

            logger.info(
                f"RAS operation {operation_id} enqueued",
                extra={
                    "operation_id": operation_id,
                    "operation_type": operation_type,
                    "database_count": len(databases),
                },
            )

            # Record Prometheus metric for queued batch operation
            _record_batch_metric(operation_type, "queued")

            return batch_operation

        except Exception as exc:
            logger.error(f"Error enqueueing RAS operation: {exc}", exc_info=True)
            try:
                redis_client.release_enqueue_lock(task_id=operation_id)
            except Exception:
                pass
            # Mark operation as failed
            batch_operation.status = BatchOperation.STATUS_FAILED
            batch_operation.save(update_fields=["status", "updated_at"])
            # Record error metric
            _record_batch_metric(operation_type, "error")
            raise

    @classmethod
    def enqueue_odata_operation(
        cls,
        operation_type: str,
        database_ids: list,
        target_entity: str,
        data: dict,
        filters: dict,
        options: dict,
        user,
    ) -> BatchOperation:
        """
        Create BatchOperation for OData operation and enqueue to Redis.
        """
        from apps.databases.models import Database
        from apps.operations.models import Task

        databases = list(Database.objects.filter(id__in=database_ids))
        if not databases:
            raise ValueError("No valid databases found for the provided IDs")

        operation_id = str(uuid.uuid4())
        timeout_seconds = 300

        batch_operation = BatchOperation.objects.create(
            id=operation_id,
            name=f"{operation_type} - {len(databases)} databases",
            operation_type=operation_type,
            target_entity=target_entity,
            status=BatchOperation.STATUS_PENDING,
            payload={"data": data, "filters": filters, "options": options},
            config={
                "batch_size": 1,
                "timeout_seconds": timeout_seconds,
                "retry_count": 2,
                "priority": "normal",
            },
            total_tasks=len(databases),
            created_by=user.username if user else "system",
            metadata={"tags": ["odata", operation_type]},
        )
        batch_operation.target_databases.set(databases)

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

        enqueue_result = cls.enqueue_operation(operation_id)
        if not enqueue_result.success:
            batch_operation.status = BatchOperation.STATUS_FAILED
            batch_operation.save(update_fields=["status", "updated_at"])
            raise ValueError(enqueue_result.error or "Failed to enqueue operation")

        return batch_operation

    @classmethod
    def enqueue_cli_operation(
        cls,
        operation_type: str,
        database_ids: list,
        config: dict,
        user,
    ) -> BatchOperation:
        """
        Create BatchOperation for CLI operation and enqueue to Redis.
        """
        from apps.databases.models import Database
        from apps.operations.models import Task

        databases = list(Database.objects.filter(id__in=database_ids))
        if not databases:
            raise ValueError("No valid databases found for the provided IDs")

        operation_id = str(uuid.uuid4())

        command = str((config or {}).get("command") or "").strip()
        raw_args = (config or {}).get("args") or []
        args_list = [str(x) for x in raw_args if x is not None]
        argv_masked = [command] + ["/P***" if a.startswith("/P") and len(a) > 2 else a for a in args_list]
        bindings = [
            {
                "target_ref": "command",
                "source_ref": "request.config.command",
                "resolve_at": "api",
                "sensitive": False,
                "status": "applied",
            }
        ]
        for idx, token in enumerate(args_list):
            is_sensitive = token.startswith("/P") or "pwd" in token.lower() or "password" in token.lower()
            bindings.append(
                {
                    "target_ref": f"args[{idx}]",
                    "source_ref": f"request.config.args[{idx}]",
                    "resolve_at": "api",
                    "sensitive": bool(is_sensitive),
                    "status": "applied",
                }
            )

        execution_plan = {
            "kind": "designer_cli",
            "plan_version": 1,
            "argv_masked": argv_masked,
            "targets": {"database_ids_count": len(databases)},
        }

        batch_operation = BatchOperation.objects.create(
            id=operation_id,
            name=f"{operation_type} - {len(databases)} databases",
            operation_type=operation_type,
            target_entity="Infobase",
            status=BatchOperation.STATUS_PENDING,
            payload={"data": config, "filters": {}, "options": {}},
            config={
                "batch_size": 1,
                "timeout_seconds": 900,
                "retry_count": 1,
                "priority": "normal",
            },
            total_tasks=len(databases),
            created_by=user.username if user else "system",
            metadata={
                "tags": ["cli", operation_type],
                "execution_plan": execution_plan,
                "bindings": bindings,
            },
        )
        batch_operation.target_databases.set(databases)

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

        enqueue_result = cls.enqueue_operation(operation_id)
        if not enqueue_result.success:
            batch_operation.status = BatchOperation.STATUS_FAILED
            batch_operation.save(update_fields=["status", "updated_at"])
            raise ValueError(enqueue_result.error or "Failed to enqueue operation")

        return batch_operation
