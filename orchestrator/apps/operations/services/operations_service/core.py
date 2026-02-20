from __future__ import annotations

import redis as redis_pkg
from typing import Any

from django.conf import settings

from ...models import BatchOperation
from ...events import event_publisher, flow_publisher
from ...redis_client import redis_client
from .types import EnqueueResult, _record_batch_metric, classify_enqueue_error_code, logger


class OperationsServiceCore:
    QUEUE_KEY = "cc1c:operations:v1"
    VERSION = "2.0"
    TARGET_SCOPE_GLOBAL = "global"

    # Conflicting operation types - cannot run concurrently on same databases
    CONFLICTING_OPERATIONS = {
        "lock_scheduled_jobs": ["unlock_scheduled_jobs", "lock_scheduled_jobs"],
        "unlock_scheduled_jobs": ["lock_scheduled_jobs", "unlock_scheduled_jobs"],
        "block_sessions": ["unblock_sessions", "block_sessions"],
        "unblock_sessions": ["block_sessions", "unblock_sessions"],
        "terminate_sessions": ["terminate_sessions"],
    }

    @staticmethod
    def _get_workflow_metadata(operation: BatchOperation) -> dict[str, Any]:
        metadata = operation.metadata or {}
        if not isinstance(metadata, dict):
            metadata = {}
        execution_consumer = str(metadata.get("execution_consumer") or "").strip() or "operations"
        lane = str(metadata.get("lane") or "").strip() or execution_consumer
        result: dict[str, Any] = {}
        for key in ("workflow_execution_id", "node_id", "trace_id"):
            value = metadata.get(key)
            if value:
                result[key] = value
        result["root_operation_id"] = str(metadata.get("root_operation_id") or operation.id)
        result["execution_consumer"] = execution_consumer
        result["lane"] = lane
        return result

    @classmethod
    def check_conflicting_operations(
        cls,
        database_ids: list,
        operation_type: str,
        max_pending_age_minutes: int = 10,
    ) -> tuple[bool, str]:
        """
        Check for active/pending operations on the same databases.

        Args:
            database_ids: List of database UUIDs
            operation_type: Type of operation to execute
            max_pending_age_minutes: Ignore pending ops older than this (stuck operations)

        Returns:
            (has_conflict: bool, error_message: str)
        """
        from datetime import timedelta

        from django.utils import timezone

        conflicting_types = cls.CONFLICTING_OPERATIONS.get(operation_type, [operation_type])

        # Calculate cutoff time for "stuck" operations
        cutoff_time = timezone.now() - timedelta(minutes=max_pending_age_minutes)

        # Find active operations on same databases with conflicting types
        active_ops = (
            BatchOperation.objects.filter(
                status__in=[
                    BatchOperation.STATUS_PENDING,
                    BatchOperation.STATUS_QUEUED,
                    BatchOperation.STATUS_PROCESSING,
                ],
                operation_type__in=conflicting_types,
                target_databases__id__in=database_ids,
                created_at__gte=cutoff_time,  # Ignore old stuck operations
            )
            .distinct()
            .first()
        )

        if active_ops:
            return (
                True,
                f"Conflicting operation '{active_ops.operation_type}' " f"(id: {active_ops.id}) is already in progress",
            )

        return (False, "")

    @classmethod
    def is_celery_enabled(cls) -> bool:
        """Check if Celery fallback is enabled."""
        return getattr(settings, "CELERY_ENABLED", True)

    @classmethod
    def enqueue_operation(cls, operation_id: str) -> EnqueueResult:
        """
        Enqueue operation to Redis queue for Go Worker processing.

        Args:
            operation_id: BatchOperation ID (UUID string)

        Returns:
            EnqueueResult with status and metadata
        """
        logger.info(f"Enqueuing operation {operation_id}")

        try:
            # 1. Get operation from DB
            operation = BatchOperation.objects.get(id=operation_id)

            # 1.1 Optional: global scope lock (per standalone target_ref)
            global_target_ref = None
            target_scope = cls._extract_target_scope(operation.payload)
            if target_scope == cls.TARGET_SCOPE_GLOBAL:
                target_ref = cls._compute_global_target_ref(operation.payload)
                if target_ref:
                    global_target_ref = target_ref
                    lock_acquired = redis_client.acquire_global_target_lock(
                        target_ref,
                        ttl_seconds=3600,  # 1 hour safety TTL; released on completion when possible
                    )
                    if not lock_acquired:
                        logger.warning(
                            "Global target already locked (duplicate submission)",
                            extra={
                                "operation_id": operation_id,
                                "operation_type": operation.operation_type,
                                "target_ref": target_ref,
                            },
                        )
                        return EnqueueResult(
                            success=False,
                            operation_id=operation_id,
                            status="duplicate",
                            error="Global target already in progress",
                            error_code="DUPLICATE",
                        )

                    metadata = operation.metadata or {}
                    metadata["target_scope"] = cls.TARGET_SCOPE_GLOBAL
                    metadata["target_ref"] = target_ref
                    operation.metadata = metadata

                    if isinstance(operation.payload, dict):
                        payload_options = operation.payload.get("options")
                        if not isinstance(payload_options, dict):
                            payload_options = {}
                            operation.payload["options"] = payload_options
                        payload_options["target_scope"] = cls.TARGET_SCOPE_GLOBAL
                        payload_options["target_ref"] = target_ref

                    operation.save(update_fields=["metadata", "payload", "updated_at"])
                else:
                    logger.info(
                        "Global scope operation without target_ref: skipping global lock",
                        extra={"operation_id": operation_id, "operation_type": operation.operation_type},
                    )

            # 2. Idempotency check - acquire enqueue lock (separate from Worker's task lock)
            lock_acquired = redis_client.acquire_enqueue_lock(task_id=operation_id, ttl_seconds=3600)  # 1 hour

            if not lock_acquired:
                logger.warning(f"Operation {operation_id} already locked (duplicate submission)")
                if global_target_ref:
                    try:
                        redis_client.release_global_target_lock(global_target_ref)
                    except Exception:
                        pass
                return EnqueueResult(
                    success=False,
                    operation_id=operation_id,
                    status="duplicate",
                    error="Operation already in progress",
                    error_code="DUPLICATE",
                )

            workflow_metadata = cls._get_workflow_metadata(operation)

            # 3. Build Message Protocol v2.0 message
            message = cls._build_message(operation)

            # 4. Enqueue to Redis
            msg_id = redis_client.enqueue_operation_stream(message)

            # 5. Publish QUEUED event for real-time tracking
            event_publisher.publish(
                operation_id=str(operation_id),
                state="QUEUED",
                microservice="orchestrator",
                queue=cls.QUEUE_KEY,
                target_databases_count=len(message["target_databases"]),
                **workflow_metadata,
            )

            # 6. Update operation status
            operation.status = BatchOperation.STATUS_QUEUED
            operation.save(update_fields=["status", "updated_at"])

            logger.info(
                f"Operation {operation_id} enqueued successfully",
                extra={
                    "operation_id": operation_id,
                    "operation_type": operation.operation_type,
                    "target_databases_count": len(message["target_databases"]),
                },
            )

            # Record Prometheus metric for queued batch operation
            _record_batch_metric(operation.operation_type, "queued")

            # Publish flow event for Service Mesh visualization
            flow_publisher.publish_flow(
                operation_id=str(operation_id),
                current_service="orchestrator",
                status="processing",
                message=f"Operation queued: {operation.operation_type}",
                operation_type=operation.operation_type,
                operation_name=operation.name or operation.operation_type,
                path=["frontend", "api-gateway", "orchestrator", "worker"],
                metadata={
                    "target_databases_count": len(message["target_databases"]),
                    "queue": cls.QUEUE_KEY,
                    **workflow_metadata,
                },
            )

            return EnqueueResult(
                success=True,
                operation_id=operation_id,
                status="queued",
                metadata={
                    "queue": cls.QUEUE_KEY,
                    "target_databases_count": len(message["target_databases"]),
                    "stream_message_id": msg_id,
                },
            )

        except BatchOperation.DoesNotExist:
            logger.error(f"Operation {operation_id} not found in database")
            # Record error metric
            _record_batch_metric("unknown", "error")
            return EnqueueResult(
                success=False,
                operation_id=operation_id,
                status="error",
                error=f"Operation {operation_id} not found",
                error_code="NOT_FOUND",
            )

        except redis_pkg.exceptions.RedisError as exc:
            logger.error(f"Redis error while enqueueing operation {operation_id}: {exc}", exc_info=True)

            # Release enqueue lock on error (best-effort)
            try:
                redis_client.release_enqueue_lock(operation_id)
            except Exception:
                pass

            # Release global lock (if acquired) on error before queue (best-effort)
            try:
                if "global_target_ref" in locals() and global_target_ref:
                    redis_client.release_global_target_lock(global_target_ref)
            except Exception:
                pass

            # Record error metric (use operation type if available from local scope)
            try:
                op_type = operation.operation_type if "operation" in locals() else "unknown"
                _record_batch_metric(op_type, "error")
            except Exception:
                _record_batch_metric("unknown", "error")

            return EnqueueResult(
                success=False,
                operation_id=operation_id,
                status="error",
                error=str(exc),
                error_code="REDIS_ERROR",
            )

        except Exception as exc:
            error_code = classify_enqueue_error_code(exc)
            logger.error(
                f"Error enqueueing operation {operation_id} (error_code={error_code}): {exc}",
                exc_info=True,
            )

            # Release enqueue lock on error
            try:
                redis_client.release_enqueue_lock(operation_id)
            except Exception:
                pass

            # Release global lock (if acquired) on error before queue
            try:
                if "global_target_ref" in locals() and global_target_ref:
                    redis_client.release_global_target_lock(global_target_ref)
            except Exception:
                pass

            # Record error metric (use operation type if available from local scope)
            try:
                op_type = operation.operation_type if "operation" in locals() else "unknown"
                _record_batch_metric(op_type, "error")
            except Exception:
                _record_batch_metric("unknown", "error")

            return EnqueueResult(
                success=False,
                operation_id=operation_id,
                status="error",
                error=str(exc),
                error_code=error_code,
            )
