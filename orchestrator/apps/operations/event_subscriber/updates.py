from typing import Any, Dict, Optional

from django.db import transaction

from .runtime import Task, logger


class TaskAndDatabaseUpdatesMixin:
    def _update_database_restrictions(self, batch_op, results: list[Dict[str, Any]]) -> None:
        if batch_op.operation_type not in {
            "lock_scheduled_jobs",
            "unlock_scheduled_jobs",
            "block_sessions",
            "unblock_sessions",
        }:
            return

        config = {}
        if isinstance(batch_op.payload, dict):
            config = batch_op.payload.get("data") or {}
        if not isinstance(config, dict):
            config = {}

        success_ids = [
            result.get("database_id")
            for result in results
            if result.get("success") and result.get("database_id")
        ]
        if not success_ids:
            return

        def set_metadata_value(metadata: dict, key: str, value: Optional[str]) -> None:
            if value:
                metadata[key] = value
            else:
                metadata.pop(key, None)

        from apps.databases.models import Database

        for database in Database.objects.filter(id__in=success_ids):
            metadata = database.metadata or {}
            if not isinstance(metadata, dict):
                metadata = {}

            if batch_op.operation_type == "lock_scheduled_jobs":
                metadata["scheduled_jobs_deny"] = True
            elif batch_op.operation_type == "unlock_scheduled_jobs":
                metadata["scheduled_jobs_deny"] = False
            elif batch_op.operation_type == "block_sessions":
                metadata["sessions_deny"] = True
                set_metadata_value(metadata, "denied_from", config.get("denied_from"))
                set_metadata_value(metadata, "denied_to", config.get("denied_to"))
                set_metadata_value(metadata, "denied_message", config.get("message"))
                set_metadata_value(metadata, "permission_code", config.get("permission_code"))
                set_metadata_value(metadata, "denied_parameter", config.get("parameter"))
            elif batch_op.operation_type == "unblock_sessions":
                metadata["sessions_deny"] = False
                for key in (
                    "denied_from",
                    "denied_to",
                    "denied_message",
                    "permission_code",
                    "denied_parameter",
                ):
                    metadata.pop(key, None)

            database.metadata = metadata
            database.save(update_fields=["metadata", "updated_at"])

    def _update_database_health(self, batch_op, results: list[Dict[str, Any]]) -> None:
        if batch_op.operation_type != "health_check":
            return
        if not results:
            return

        from apps.databases.models import Database

        def parse_response_time(value: Any) -> Optional[float]:
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        for result in results:
            database_id = result.get("database_id")
            if not database_id:
                continue

            try:
                database = Database.objects.get(id=database_id)
            except Database.DoesNotExist:
                continue

            data = result.get("data") or {}
            response_time_ms = parse_response_time(data.get("response_time_ms"))
            success = bool(result.get("success"))

            database.mark_health_check(success=success, response_time=response_time_ms)

            metadata = database.metadata if isinstance(database.metadata, dict) else {}
            metadata_updated = False

            if success:
                for key in ("last_health_error", "last_health_error_code"):
                    if key in metadata:
                        metadata.pop(key, None)
                        metadata_updated = True
            else:
                error_message = result.get("error")
                error_code = result.get("error_code")

                if error_message:
                    metadata["last_health_error"] = error_message
                    metadata_updated = True
                elif "last_health_error" in metadata:
                    metadata.pop("last_health_error", None)
                    metadata_updated = True

                if error_code:
                    metadata["last_health_error_code"] = error_code
                    metadata_updated = True
                elif "last_health_error_code" in metadata:
                    metadata.pop("last_health_error_code", None)
                    metadata_updated = True

            if metadata_updated:
                database.metadata = metadata
                database.save(update_fields=["metadata", "updated_at"])

    def _update_task_status_from_correlation_id(
        self,
        correlation_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> None:
        try:
            if not correlation_id.startswith("batch-"):
                logger.warning(
                    "Invalid correlation_id format (missing batch- prefix): %s",
                    correlation_id,
                )
                return

            remainder = correlation_id[6:]
            task_prefix_index = remainder.rfind("-task-")
            if task_prefix_index == -1:
                logger.warning(
                    "Invalid correlation_id format (no task- found): %s",
                    correlation_id,
                )
                return

            task_id = remainder[task_prefix_index + 1 :]

            with transaction.atomic():
                try:
                    task = Task.objects.select_for_update().get(id=task_id)
                except Task.DoesNotExist:
                    logger.warning(
                        "Task not found: %s (correlation_id=%s)",
                        task_id,
                        correlation_id,
                    )
                    return

                if status == Task.STATUS_COMPLETED:
                    task.mark_completed(result=result)
                    logger.info("Task %s marked as completed", task_id)
                elif status == Task.STATUS_FAILED:
                    task.mark_failed(
                        error_message=error_message or "Unknown error",
                        error_code=error_code,
                        should_retry=True,
                    )
                    logger.info("Task %s marked as failed: %s", task_id, error_message)
                else:
                    task.status = status
                    task.save(update_fields=["status", "updated_at"])
                    logger.info("Task %s status updated to %s", task_id, status)

        except Exception as e:
            logger.error(
                "Error updating task from correlation_id %s: %s",
                correlation_id,
                e,
                exc_info=True,
            )

