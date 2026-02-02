import json
from typing import Any, Dict

from django.db import transaction
from django.db.utils import OperationalError
from django.utils import timezone

from .flow import get_workflow_metadata, publish_completion_flow, release_idempotency_lock_for_operation
from .metrics import record_batch_metric
from . import runtime


class WorkerEventHandlersMixin:
    def handle_worker_completed(self, data: Dict[str, Any], correlation_id: str) -> None:
        from apps.operations.models import BatchOperation

        envelope_str = data.get("data", "")
        envelope = {}
        if envelope_str:
            try:
                envelope = json.loads(envelope_str)
                payload_str = envelope.get("payload", "{}")
                payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
            except json.JSONDecodeError as e:
                runtime.logger.error("Invalid envelope JSON: %s", e)
                return
        else:
            payload = data

        operation_id = payload.get("operation_id")
        if not operation_id:
            metadata = envelope.get("metadata", {}) if envelope_str else {}
            operation_id = metadata.get("operation_id")
        if not operation_id:
            runtime.logger.warning("No operation_id in worker:completed event: %s", data)
            return

        runtime.logger.info("Worker completed event: operation_id=%s", operation_id)

        try:
            runtime.close_old_connections()
            batch_op = BatchOperation.objects.get(id=operation_id)

            op_command_id = str((batch_op.metadata or {}).get("command_id") or "").strip()
            snapshot_command_ids_by_tenant: dict[str, set[str]] = {}

            def _get_snapshot_command_ids_for_tenant(tenant_id: str) -> set[str]:
                tenant_id = str(tenant_id or "").strip()
                if not tenant_id:
                    return set()
                cached = snapshot_command_ids_by_tenant.get(tenant_id)
                if cached is not None:
                    return cached

                try:
                    from apps.runtime_settings.action_catalog import (
                        UI_ACTION_CATALOG_KEY,
                        ensure_valid_action_catalog,
                    )
                    from apps.runtime_settings.effective import get_effective_runtime_setting

                    raw_catalog = get_effective_runtime_setting(UI_ACTION_CATALOG_KEY, tenant_id).value
                    catalog, _errors = ensure_valid_action_catalog(raw_catalog)

                    extensions = catalog.get("extensions") if isinstance(catalog, dict) else None
                    actions = extensions.get("actions") if isinstance(extensions, dict) else None

                    snapshot_command_ids: set[str] = set()
                    if isinstance(actions, list):
                        for action in actions:
                            if not isinstance(action, dict):
                                continue
                            action_id = str(action.get("id") or "").strip()
                            if action_id not in {"extensions.list", "extensions.sync"}:
                                continue
                            executor = action.get("executor")
                            if not isinstance(executor, dict):
                                continue
                            if executor.get("kind") != "ibcmd_cli":
                                continue
                            command_id = executor.get("command_id")
                            if isinstance(command_id, str) and command_id.strip():
                                snapshot_command_ids.add(command_id.strip())

                    snapshot_command_ids_by_tenant[tenant_id] = snapshot_command_ids
                    return snapshot_command_ids
                except Exception:
                    snapshot_command_ids_by_tenant[tenant_id] = set()
                    return set()

            summary = payload.get("summary", {})
            results = payload.get("results", [])
            workflow_metadata = get_workflow_metadata(batch_op)
            now = timezone.now()

            completed_tasks = summary.get("succeeded", 0)
            failed_tasks = summary.get("failed", 0)
            if results:
                for result in results:
                    database_id = result.get("database_id")
                    task_qs = runtime.Task.objects.filter(batch_operation=batch_op)
                    if database_id:
                        task_qs = task_qs.filter(database_id=database_id)
                    else:
                        task_qs = task_qs.filter(database__isnull=True)

                    task_status = (
                        runtime.Task.STATUS_COMPLETED
                        if result.get("success")
                        else runtime.Task.STATUS_FAILED
                    )
                    duration_seconds = result.get("duration_seconds")
                    update_fields = {
                        "status": task_status,
                        "completed_at": now,
                        "updated_at": now,
                        "duration_seconds": duration_seconds,
                    }
                    if task_status == runtime.Task.STATUS_COMPLETED:
                        update_fields["result"] = result.get("data")
                        update_fields["error_message"] = ""
                        update_fields["error_code"] = ""

                        should_update_extensions_snapshot = False
                        db_for_snapshot = None
                        if (
                            database_id
                            and op_command_id
                            and batch_op.operation_type == BatchOperation.TYPE_IBCMD_CLI
                        ):
                            try:
                                from apps.databases.models import Database

                                db_for_snapshot = (
                                    Database.objects.filter(id=database_id)
                                    .only("id", "tenant_id")
                                    .first()
                                )
                                tenant_id = str(getattr(db_for_snapshot, "tenant_id", "") or "").strip()
                                if tenant_id:
                                    snapshot_command_ids = _get_snapshot_command_ids_for_tenant(tenant_id)
                                    should_update_extensions_snapshot = op_command_id in snapshot_command_ids
                            except Exception:
                                should_update_extensions_snapshot = False

                        if should_update_extensions_snapshot and database_id:
                            try:
                                from apps.databases.extensions_snapshot import (
                                    build_extensions_snapshot_from_worker_result,
                                )
                                from apps.operations.models import CommandResultSnapshot
                                from apps.operations.snapshot_hash import canonical_json_hash
                                from apps.databases.models import DatabaseExtensionsSnapshot

                                snapshot_data = result.get("data")
                                normalized = build_extensions_snapshot_from_worker_result(snapshot_data)
                                canonical = normalized
                                canonical_hash = canonical_json_hash(canonical)

                                DatabaseExtensionsSnapshot.objects.update_or_create(
                                    database_id=database_id,
                                    defaults={
                                        "snapshot": normalized,
                                        "source_operation_id": str(operation_id),
                                    },
                                )

                                db = db_for_snapshot
                                if db is None:
                                    from apps.databases.models import Database as DatabaseModel

                                    db = DatabaseModel.objects.filter(id=database_id).only("id", "tenant_id").first()

                                if db and getattr(db, "tenant_id", None):
                                    CommandResultSnapshot.objects.create(
                                        tenant_id=db.tenant_id,
                                        operation_id=str(operation_id),
                                        database_id=str(database_id),
                                        driver="ibcmd",
                                        command_id=op_command_id,
                                        raw_payload=snapshot_data or {},
                                        normalized_payload=normalized,
                                        canonical_payload=canonical,
                                        canonical_hash=canonical_hash,
                                        captured_at=now,
                                    )
                            except Exception:
                                pass
                    else:
                        update_fields["error_message"] = result.get("error") or "Unknown error"
                        update_fields["error_code"] = (
                            result.get("error_code") or "UNKNOWN_ERROR"
                        )
                        update_fields["result"] = result.get("data")

                    task_qs.update(**update_fields)

                successful = sum(1 for result in results if result.get("success"))
                failed = len(results) - successful
                total = summary.get("total") or batch_op.total_tasks or len(results)
                completed_tasks = summary.get("succeeded", successful)
                failed_tasks = summary.get("failed", failed)
                batch_op.total_tasks = total
                batch_op.completed_tasks = completed_tasks
                batch_op.failed_tasks = failed_tasks

            payload_status = str(payload.get("status") or "").lower()
            if payload_status in {"failed", "timeout"}:
                batch_op.status = BatchOperation.STATUS_FAILED
            elif summary:
                if failed_tasks > 0 and completed_tasks == 0:
                    batch_op.status = BatchOperation.STATUS_FAILED
                else:
                    batch_op.status = BatchOperation.STATUS_COMPLETED
            else:
                batch_op.status = BatchOperation.STATUS_COMPLETED
            batch_op.progress = 100
            if not batch_op.completed_at:
                batch_op.completed_at = now

            batch_op.metadata["worker_result"] = {
                "summary": summary,
                "results_count": len(results),
            }
            batch_op.save(
                update_fields=[
                    "status",
                    "progress",
                    "completed_at",
                    "metadata",
                    "total_tasks",
                    "completed_tasks",
                    "failed_tasks",
                    "updated_at",
                ]
            )

            release_idempotency_lock_for_operation(batch_op)
            try:
                runtime.operations_redis_client.add_timeline_event(
                    operation_id,
                    event="operation.completed",
                    service="event-subscriber",
                    metadata={
                        "status": batch_op.status,
                        "results_count": len(results),
                        **workflow_metadata,
                    },
                )
            except Exception:
                pass

            runtime.logger.info(
                "Updated BatchOperation %s to COMPLETED via Stream", operation_id
            )

            record_batch_metric(batch_op.operation_type, "completed")

            metadata = batch_op.metadata or {}
            target_scope = str(metadata.get("target_scope") or "").strip().lower()
            target_ref = str(metadata.get("target_ref") or "").strip()
            if target_scope == "global" and target_ref:
                try:
                    runtime.operations_redis_client.release_global_target_lock(target_ref)
                except Exception:
                    pass
            else:
                global_lock_key = metadata.get("global_lock_key")
                if global_lock_key:
                    try:
                        runtime.operations_redis_client.release_lock(global_lock_key)
                    except Exception:
                        pass

            publish_completion_flow(
                operation_id=operation_id,
                operation_type=batch_op.operation_type,
                operation_name=batch_op.name,
                status="completed",
                message="Worker completed",
                metadata={"summary": summary, "results_count": len(results), **workflow_metadata},
            )

            self._update_database_restrictions(batch_op, results)
            self._update_database_health(batch_op, results)

        except BatchOperation.DoesNotExist:
            runtime.logger.warning("BatchOperation not found: %s", operation_id)
        except OperationalError as e:
            # Transient DB issues MUST bubble up so EventSubscriber does not ACK the message.
            runtime.logger.error("Error handling worker:completed: %s", e, exc_info=True)
            raise
        except Exception as e:
            runtime.logger.error("Error handling worker:completed: %s", e, exc_info=True)

    def handle_worker_failed(self, data: Dict[str, Any], correlation_id: str) -> None:
        from apps.operations.models import BatchOperation

        envelope_str = data.get("data", "")
        envelope = {}
        if envelope_str:
            try:
                envelope = json.loads(envelope_str)
                payload_str = envelope.get("payload", "{}")
                payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
            except json.JSONDecodeError as e:
                runtime.logger.error("Invalid envelope JSON: %s", e)
                return
        else:
            payload = data

        operation_id = payload.get("operation_id")
        error_msg = payload.get("error", "Unknown error")
        if not operation_id:
            metadata = envelope.get("metadata", {}) if envelope_str else {}
            operation_id = metadata.get("operation_id")
        if not operation_id:
            runtime.logger.warning("No operation_id in worker:failed event: %s", data)
            return

        runtime.logger.info(
            "Worker failed event: operation_id=%s, error=%s",
            operation_id,
            error_msg,
        )

        try:
            runtime.close_old_connections()
            batch_op = BatchOperation.objects.get(id=operation_id)

            batch_op.status = BatchOperation.STATUS_FAILED
            batch_op.progress = 100
            if not batch_op.completed_at:
                batch_op.completed_at = timezone.now()

            batch_op.metadata["error"] = error_msg
            batch_op.save(
                update_fields=["status", "progress", "completed_at", "metadata", "updated_at"]
            )

            release_idempotency_lock_for_operation(batch_op)
            workflow_metadata = get_workflow_metadata(batch_op)
            now = timezone.now()
            runtime.Task.objects.filter(batch_operation=batch_op, database__isnull=True).update(
                status=runtime.Task.STATUS_FAILED,
                completed_at=now,
                updated_at=now,
                duration_seconds=None,
                error_message=error_msg or "Unknown error",
                error_code="WORKER_FAILED",
                result=None,
            )
            try:
                runtime.operations_redis_client.add_timeline_event(
                    operation_id,
                    event="operation.failed",
                    service="event-subscriber",
                    metadata={
                        "status": batch_op.status,
                        "error": error_msg,
                        **workflow_metadata,
                    },
                )
            except Exception:
                pass

            runtime.logger.info("Updated BatchOperation %s to FAILED via Stream", operation_id)

            record_batch_metric(batch_op.operation_type, "failed")

            metadata = batch_op.metadata or {}
            target_scope = str(metadata.get("target_scope") or "").strip().lower()
            target_ref = str(metadata.get("target_ref") or "").strip()
            if target_scope == "global" and target_ref:
                try:
                    runtime.operations_redis_client.release_global_target_lock(target_ref)
                except Exception:
                    pass
            else:
                global_lock_key = metadata.get("global_lock_key")
                if global_lock_key:
                    try:
                        runtime.operations_redis_client.release_lock(global_lock_key)
                    except Exception:
                        pass

            publish_completion_flow(
                operation_id=operation_id,
                operation_type=batch_op.operation_type,
                operation_name=batch_op.name,
                status="failed",
                message=error_msg or "Worker failed",
                metadata={"error": error_msg, **workflow_metadata},
            )

        except BatchOperation.DoesNotExist:
            runtime.logger.warning("BatchOperation not found: %s", operation_id)
        except OperationalError as e:
            # Transient DB issues MUST bubble up so EventSubscriber does not ACK the message.
            runtime.logger.error("Error handling worker:failed: %s", e, exc_info=True)
            raise
        except Exception as e:
            runtime.logger.error("Error handling worker:failed: %s", e, exc_info=True)

    def handle_dlq_message(self, data: Dict[str, Any], correlation_id: str) -> None:
        from apps.operations.models import BatchOperation

        original_message_id = data.get("original_message_id", "unknown")
        operation_id = data.get("operation_id", "")
        error_code = data.get("error_code", "UNKNOWN")
        error_message = data.get("error_message", "Unknown error")
        worker_id = data.get("worker_id", "")
        failed_at = data.get("failed_at", "")

        runtime.logger.error(
            "DLQ message received: operation_id=%s, error_code=%s, error=%s, worker_id=%s, "
            "original_msg_id=%s, failed_at=%s, correlation_id=%s",
            operation_id,
            error_code,
            error_message,
            worker_id,
            original_message_id,
            failed_at,
            correlation_id,
        )

        if operation_id:
            try:
                runtime.close_old_connections()

                terminal_states = [
                    BatchOperation.STATUS_COMPLETED,
                    BatchOperation.STATUS_FAILED,
                    BatchOperation.STATUS_CANCELLED,
                ]
                dlq_dedup_key = f"dlq:processed:{operation_id}"

                with transaction.atomic():
                    if self.redis_client.sismember(dlq_dedup_key, original_message_id):
                        runtime.logger.debug(
                            "DLQ message already processed: operation_id=%s, original_msg_id=%s",
                            operation_id,
                            original_message_id,
                        )
                        return

                    batch_op = BatchOperation.objects.select_for_update().get(id=operation_id)

                    if batch_op.status not in terminal_states:
                        batch_op.status = BatchOperation.STATUS_FAILED
                        batch_op.progress = 100
                        batch_op.completed_at = timezone.now()
                        batch_op.metadata["dlq_error"] = {
                            "error_code": error_code,
                            "error_message": error_message,
                            "worker_id": worker_id,
                            "original_message_id": original_message_id,
                            "failed_at": failed_at,
                        }
                        batch_op.save(
                            update_fields=[
                                "status",
                                "progress",
                                "completed_at",
                                "metadata",
                                "updated_at",
                            ]
                        )
                        runtime.logger.info(
                            "Updated BatchOperation %s to FAILED from DLQ",
                            operation_id,
                        )
                    else:
                        runtime.logger.debug(
                            "BatchOperation %s already in terminal state: %s, skipping DLQ update",
                            operation_id,
                            batch_op.status,
                        )

                    self.redis_client.sadd(dlq_dedup_key, original_message_id)
                    self.redis_client.expire(dlq_dedup_key, 86400)

            except BatchOperation.DoesNotExist:
                runtime.logger.warning(
                    "BatchOperation not found for DLQ message: %s",
                    operation_id,
                )
            except Exception as e:
                runtime.logger.error(
                    "Error updating BatchOperation from DLQ: %s", e, exc_info=True
                )
        else:
            runtime.logger.warning(
                "DLQ message without operation_id, cannot update BatchOperation: "
                "original_msg_id=%s, error_code=%s",
                original_message_id,
                error_code,
            )
