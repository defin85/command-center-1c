import json
import uuid
from typing import Any, Dict

from django.db import transaction
from django.db.utils import OperationalError
from django.utils import timezone

from .flow import get_workflow_metadata, publish_completion_flow, release_idempotency_lock_for_operation
from .metrics import record_batch_metric
from . import runtime


_RESULT_CONTRACT_EXTENSIONS_INVENTORY_V1 = "extensions.inventory.v1"


def _resolve_pinned_extensions_mapping_spec(
    *,
    tenant_id: str,
    mapping_spec_ref: Any,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    from apps.mappings.models import TenantMappingSpec

    if not isinstance(mapping_spec_ref, dict):
        return None, {
            "code": "PINNED_MAPPING_REF_MISSING",
            "message": "mapping_spec_ref is required for contract-aware completion",
            "details": {},
        }

    mapping_spec_id = str(mapping_spec_ref.get("mapping_spec_id") or "").strip()
    entity_kind = str(mapping_spec_ref.get("entity_kind") or "").strip()
    expected_version = str(mapping_spec_ref.get("mapping_spec_version") or "").strip()

    if not mapping_spec_id:
        return None, {
            "code": "PINNED_MAPPING_REF_INVALID",
            "message": "mapping_spec_ref.mapping_spec_id is required",
            "details": {"mapping_spec_ref": mapping_spec_ref},
        }
    try:
        mapping_spec_pk = int(mapping_spec_id)
    except (TypeError, ValueError):
        return None, {
            "code": "PINNED_MAPPING_REF_INVALID",
            "message": "mapping_spec_ref.mapping_spec_id must be numeric",
            "details": {"mapping_spec_ref": mapping_spec_ref},
        }

    if entity_kind != TenantMappingSpec.ENTITY_EXTENSIONS_INVENTORY:
        return None, {
            "code": "PINNED_MAPPING_REF_INVALID",
            "message": "mapping_spec_ref.entity_kind is invalid",
            "details": {
                "mapping_spec_ref": mapping_spec_ref,
                "expected_entity_kind": TenantMappingSpec.ENTITY_EXTENSIONS_INVENTORY,
            },
        }

    row = (
        TenantMappingSpec.objects.filter(
            id=mapping_spec_pk,
            tenant_id=tenant_id,
            entity_kind=TenantMappingSpec.ENTITY_EXTENSIONS_INVENTORY,
            status=TenantMappingSpec.STATUS_PUBLISHED,
        )
        .only("id", "updated_at", "spec")
        .first()
    )

    if row is None:
        return None, {
            "code": "PINNED_MAPPING_NOT_FOUND",
            "message": "pinned mapping is not available",
            "details": {"mapping_spec_ref": mapping_spec_ref},
        }

    actual_version = row.updated_at.isoformat() if getattr(row, "updated_at", None) else ""
    if expected_version and actual_version != expected_version:
        return None, {
            "code": "PINNED_MAPPING_VERSION_MISMATCH",
            "message": "pinned mapping version mismatch",
            "details": {
                "mapping_spec_ref": mapping_spec_ref,
                "resolved_mapping_spec_id": str(row.id),
                "resolved_mapping_spec_version": actual_version or None,
            },
        }

    spec = row.spec if isinstance(row.spec, dict) else {}
    return spec, None


def _validate_extensions_result_contract(
    *,
    canonical_payload: Any,
    result_contract: str,
) -> list[dict[str, Any]]:
    contract = str(result_contract or "").strip()
    if contract != _RESULT_CONTRACT_EXTENSIONS_INVENTORY_V1:
        return []

    from apps.mappings.extensions_inventory import validate_extensions_inventory

    errors = validate_extensions_inventory(canonical_payload)
    if not errors:
        return []
    return [
        {
            "code": "RESULT_CONTRACT_VALIDATION_FAILED",
            "message": "canonical payload does not satisfy result_contract",
            "details": {
                "result_contract": contract,
                "errors": errors[:20],
            },
        }
    ]


def _append_extensions_snapshot_diagnostics(
    *,
    snapshot_errors: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    operation_id: str,
    database_id: str,
    command_id: str,
) -> None:
    for item in diagnostics:
        if not isinstance(item, dict):
            continue
        snapshot_errors.append(
            {
                "kind": "extensions",
                "operation_id": operation_id,
                "database_id": database_id,
                "command_id": command_id,
                "error_code": str(item.get("code") or "SNAPSHOT_DIAGNOSTIC"),
                "error": str(item.get("message") or "snapshot diagnostic"),
                "details": item.get("details") if isinstance(item.get("details"), dict) else {},
            }
        )


def _append_business_configuration_snapshot_error(
    *,
    snapshot_errors: list[dict[str, Any]],
    operation_id: str,
    database_id: str,
    command_id: str,
    error: str,
) -> None:
    snapshot_errors.append(
        {
            "kind": "business_configuration_profile",
            "operation_id": operation_id,
            "database_id": database_id,
            "command_id": command_id,
            "error": error,
        }
    )


def _persist_business_configuration_worker_result(
    *,
    operation_id: str,
    database_id: str,
    command_id: str,
    result_data: Any,
    captured_at,
) -> dict[str, Any] | None:
    from apps.databases.models import Database as DatabaseModel
    from apps.intercompany_pools.business_configuration_operations import (
        enqueue_business_configuration_verification,
    )
    from apps.intercompany_pools.business_configuration_profile import (
        get_business_configuration_profile,
        load_configuration_xml_from_worker_result,
        parse_business_configuration_profile_xml,
        parse_config_generation_id_worker_result,
        persist_business_configuration_profile,
    )
    from apps.operations.models import CommandResultSnapshot
    from apps.operations.snapshot_hash import canonical_json_hash

    db = DatabaseModel.objects.filter(id=database_id).only("id", "tenant_id", "metadata").first()
    if db is None:
        return None

    normalized: dict[str, Any] | None
    if command_id == "infobase.config.generation-id":
        generation_id = parse_config_generation_id_worker_result(
            result_data if isinstance(result_data, dict) else None
        )
        if not generation_id:
            raise ValueError("config generation id is missing in worker result")
        existing_profile = get_business_configuration_profile(database=db)
        if existing_profile is None:
            normalized = {
                "config_generation_id": generation_id,
                "generation_probe_checked_at": captured_at.isoformat(),
            }
            enqueue_business_configuration_verification(
                database=db,
                reason="profile_missing_after_generation_probe",
                triggered_by_operation_id=str(operation_id),
            )
        else:
            updated_profile = dict(existing_profile)
            previous_generation_id = str(updated_profile.get("config_generation_id") or "").strip()
            updated_profile["config_generation_id"] = generation_id
            updated_profile["generation_probe_checked_at"] = captured_at.isoformat()
            updated_profile.pop("generation_probe_operation_id", None)
            updated_profile.pop("generation_probe_requested_at", None)
            normalized = persist_business_configuration_profile(
                database=db,
                profile=updated_profile,
            )
            if previous_generation_id and previous_generation_id != generation_id:
                normalized = persist_business_configuration_profile(
                    database=db,
                    profile={
                        **normalized,
                        "verification_status": "reverify_required",
                    },
                )
                enqueue_business_configuration_verification(
                    database=db,
                    reason="generation_changed",
                    triggered_by_operation_id=str(operation_id),
                )
    elif command_id == "infobase.config.export.objects":
        xml_payload = load_configuration_xml_from_worker_result(
            result_data if isinstance(result_data, dict) else None
        )
        if not xml_payload:
            raise ValueError("Configuration.xml is missing in worker result")
        normalized = parse_business_configuration_profile_xml(xml_payload)
        existing_profile = get_business_configuration_profile(database=db)
        if existing_profile is not None:
            generation_id = str(existing_profile.get("config_generation_id") or "").strip()
            if generation_id:
                normalized["config_generation_id"] = generation_id
        if isinstance(result_data, dict):
            artifact_path = str(result_data.get("artifact_path") or "").strip()
            if artifact_path:
                normalized["verification_artifact_path"] = artifact_path
        normalized["verification_operation_id"] = str(operation_id)
        normalized.pop("generation_probe_operation_id", None)
        normalized.pop("generation_probe_requested_at", None)
        normalized = persist_business_configuration_profile(database=db, profile=normalized)
    else:
        return None

    if getattr(db, "tenant_id", None):
        raw_payload = result_data if isinstance(result_data, dict) else {"raw": result_data}
        canonical = normalized if isinstance(normalized, dict) else {}
        CommandResultSnapshot.objects.create(
            tenant_id=db.tenant_id,
            operation_id=str(operation_id),
            database_id=str(database_id),
            driver="ibcmd",
            command_id=command_id,
            raw_payload=raw_payload,
            normalized_payload=normalized or {},
            canonical_payload=canonical,
            canonical_hash=canonical_json_hash(canonical),
            captured_at=captured_at,
        )

    return normalized


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
            snapshot_kinds = (batch_op.metadata or {}).get("snapshot_kinds")
            snapshot_kinds_list = snapshot_kinds if isinstance(snapshot_kinds, list) else []
            has_extensions_snapshot_marker = "extensions" in snapshot_kinds_list
            has_business_configuration_snapshot_marker = "business_configuration_profile" in snapshot_kinds_list
            snapshot_errors: list[dict[str, Any]] = []

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

                        should_update_extensions_snapshot = (
                            bool(database_id)
                            and bool(op_command_id)
                            and batch_op.operation_type == BatchOperation.TYPE_IBCMD_CLI
                            and has_extensions_snapshot_marker
                        )
                        if should_update_extensions_snapshot and database_id:
                            try:
                                from apps.databases.extensions_snapshot import (
                                    build_extensions_snapshot_from_worker_result,
                                )
                                from apps.mappings.extensions_inventory import build_canonical_extensions_inventory
                                from apps.operations.models import CommandResultSnapshot
                                from apps.operations.snapshot_hash import canonical_json_hash
                                from apps.databases.models import DatabaseExtensionsSnapshot

                                snapshot_data = result.get("data")
                                normalized = build_extensions_snapshot_from_worker_result(snapshot_data)
                                canonical = normalized
                                diagnostics: list[dict[str, Any]] = []

                                metadata = batch_op.metadata if isinstance(batch_op.metadata, dict) else {}
                                result_contract = str(metadata.get("result_contract") or "").strip()
                                mapping_spec_ref = metadata.get("mapping_spec_ref")

                                from apps.databases.models import Database as DatabaseModel

                                db = DatabaseModel.objects.filter(id=database_id).only("id", "tenant_id").first()

                                db_tenant_id = str(getattr(db, "tenant_id", "") or "")
                                requires_contract_mapping = isinstance(mapping_spec_ref, dict) or bool(result_contract)
                                if db_tenant_id and requires_contract_mapping:
                                    pinned_spec, mapping_diagnostic = _resolve_pinned_extensions_mapping_spec(
                                        tenant_id=db_tenant_id,
                                        mapping_spec_ref=mapping_spec_ref,
                                    )
                                    if mapping_diagnostic is None:
                                        canonical = build_canonical_extensions_inventory(normalized, pinned_spec or {})
                                    else:
                                        diagnostics.append(mapping_diagnostic)
                                        # Fail-closed: keep normalized snapshot, do not use runtime fallback mapping.
                                        canonical = normalized

                                diagnostics.extend(
                                    _validate_extensions_result_contract(
                                        canonical_payload=canonical,
                                        result_contract=result_contract,
                                    )
                                )
                                if diagnostics and isinstance(snapshot_data, dict):
                                    existing_diagnostics = snapshot_data.get("diagnostics")
                                    if isinstance(existing_diagnostics, list):
                                        snapshot_data["diagnostics"] = existing_diagnostics + diagnostics[:20]
                                    else:
                                        snapshot_data["diagnostics"] = diagnostics[:20]

                                canonical_hash = canonical_json_hash(canonical)

                                DatabaseExtensionsSnapshot.objects.update_or_create(
                                    database_id=database_id,
                                    defaults={
                                        "snapshot": normalized,
                                        "source_operation_id": str(operation_id),
                                    },
                                )

                                # Enrich task result for UI/clients: keep raw payload but replace/attach
                                # parsed `extensions[]` with the normalized (best-effort) content.
                                try:
                                    if isinstance(snapshot_data, dict):
                                        raw_wrapper = snapshot_data.get("raw") if "raw" in snapshot_data else dict(snapshot_data)

                                        snapshot_data["extensions"] = normalized.get("extensions") or []
                                        snapshot_data["parse_error"] = normalized.get("parse_error")
                                        if isinstance(raw_wrapper, dict):
                                            snapshot_data["raw"] = raw_wrapper
                                        update_fields["result"] = snapshot_data
                                    else:
                                        update_fields["result"] = normalized
                                except Exception:
                                    pass

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
                                    if diagnostics:
                                        _append_extensions_snapshot_diagnostics(
                                            snapshot_errors=snapshot_errors,
                                            diagnostics=diagnostics,
                                            operation_id=str(operation_id),
                                            database_id=str(database_id),
                                            command_id=op_command_id,
                                        )
                            except Exception as exc:
                                runtime.logger.warning(
                                    "Extensions snapshot persistence failed",
                                    extra={
                                        "operation_id": str(operation_id),
                                        "database_id": str(database_id),
                                        "command_id": op_command_id,
                                    },
                                    exc_info=True,
                                )
                                snapshot_errors.append(
                                    {
                                        "kind": "extensions",
                                        "operation_id": str(operation_id),
                                        "database_id": str(database_id),
                                        "command_id": op_command_id,
                                        "error": str(exc),
                                    }
                                )
                        should_update_business_configuration_snapshot = (
                            bool(database_id)
                            and bool(op_command_id)
                            and batch_op.operation_type == BatchOperation.TYPE_IBCMD_CLI
                            and has_business_configuration_snapshot_marker
                        )
                        if should_update_business_configuration_snapshot and database_id:
                            try:
                                snapshot_data = result.get("data")
                                normalized_profile = _persist_business_configuration_worker_result(
                                    operation_id=str(operation_id),
                                    database_id=str(database_id),
                                    command_id=op_command_id,
                                    result_data=snapshot_data,
                                    captured_at=now,
                                )
                                if normalized_profile:
                                    if isinstance(snapshot_data, dict):
                                        enriched = dict(snapshot_data)
                                        enriched["business_configuration_profile"] = normalized_profile
                                        update_fields["result"] = enriched
                                    else:
                                        update_fields["result"] = {
                                            "raw": snapshot_data,
                                            "business_configuration_profile": normalized_profile,
                                        }
                            except Exception as exc:
                                runtime.logger.warning(
                                    "Business configuration profile persistence failed",
                                    extra={
                                        "operation_id": str(operation_id),
                                        "database_id": str(database_id),
                                        "command_id": op_command_id,
                                    },
                                    exc_info=True,
                                )
                                _append_business_configuration_snapshot_error(
                                    snapshot_errors=snapshot_errors,
                                    operation_id=str(operation_id),
                                    database_id=str(database_id),
                                    command_id=op_command_id,
                                    error=str(exc),
                                )
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
            next_status = BatchOperation.STATUS_COMPLETED
            if payload_status in {"failed", "timeout"}:
                next_status = BatchOperation.STATUS_FAILED
            elif summary and failed_tasks > 0 and completed_tasks == 0:
                next_status = BatchOperation.STATUS_FAILED

            terminal_statuses = {
                BatchOperation.STATUS_COMPLETED,
                BatchOperation.STATUS_FAILED,
                BatchOperation.STATUS_CANCELLED,
            }
            is_workflow_root = str(batch_op.operation_type or "").strip() == "execute_workflow"
            if is_workflow_root and batch_op.status in terminal_statuses:
                if batch_op.status == next_status:
                    runtime.logger.info(
                        "Skipping duplicate terminal worker:completed update for workflow root",
                        extra={"operation_id": operation_id, "status": batch_op.status},
                    )
                    return
                runtime.logger.warning(
                    "Skipping conflicting terminal worker:completed update for workflow root",
                    extra={
                        "operation_id": operation_id,
                        "current_status": batch_op.status,
                        "requested_status": next_status,
                    },
                )
                return

            batch_op.status = next_status
            batch_op.progress = 100
            if not batch_op.completed_at:
                batch_op.completed_at = now

            if not isinstance(batch_op.metadata, dict):
                batch_op.metadata = {}
            if snapshot_errors:
                existing = batch_op.metadata.get("snapshot_errors")
                if isinstance(existing, list):
                    batch_op.metadata["snapshot_errors"] = existing + snapshot_errors[:10]
                else:
                    batch_op.metadata["snapshot_errors"] = snapshot_errors[:10]
                batch_op.metadata["snapshot_errors_count"] = int(batch_op.metadata.get("snapshot_errors_count") or 0) + len(
                    snapshot_errors
                )

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
            self._enqueue_post_completion_extensions_sync(batch_op, results)

        except BatchOperation.DoesNotExist:
            runtime.logger.warning("BatchOperation not found: %s", operation_id)
        except OperationalError as e:
            # Transient DB issues MUST bubble up so EventSubscriber does not ACK the message.
            runtime.logger.error("Error handling worker:completed: %s", e, exc_info=True)
            raise
        except Exception as e:
            runtime.logger.error("Error handling worker:completed: %s", e, exc_info=True)

    def _enqueue_post_completion_extensions_sync(self, batch_op, results: list[dict[str, Any]]) -> None:
        """
        Best-effort follow-up extensions.sync after operations that mutate extensions state.

        Triggered by BatchOperation.metadata.post_completion_extensions_sync=true.
        """
        metadata = batch_op.metadata or {}
        if not isinstance(metadata, dict):
            return
        if metadata.get("post_completion_extensions_sync") is not True:
            return

        succeeded: list[str] = []
        for item in results or []:
            if not isinstance(item, dict):
                continue
            if not item.get("success"):
                continue
            db_id = item.get("database_id")
            if db_id:
                succeeded.append(str(db_id))

        if not succeeded:
            fallback = metadata.get("post_completion_extensions_sync_database_ids")
            if isinstance(fallback, list):
                succeeded = [str(x) for x in fallback if x]

        succeeded = [x for x in succeeded if x]
        if not succeeded:
            return

        # Resolve tenant for loading effective runtime settings.
        try:
            from apps.databases.models import Database

            tenant_id = (
                Database.objects.filter(id=succeeded[0]).values_list("tenant_id", flat=True).first()
            )
            tenant_id_str = str(tenant_id) if tenant_id else ""
        except Exception:
            tenant_id_str = ""

        if not tenant_id_str:
            runtime.logger.warning(
                "post_completion_extensions_sync: cannot resolve tenant_id (op=%s)",
                str(getattr(batch_op, "id", "")),
            )
            return

        try:
            from apps.operations.driver_catalog_effective import get_effective_driver_catalog, resolve_driver_catalog_versions
            from apps.operations.ibcmd_cli_builder import (
                build_ibcmd_cli_argv,
                build_ibcmd_cli_argv_manual,
                build_ibcmd_connection_args,
            )
            from apps.operations.models import BatchOperation
            from apps.operations.services.operations_service import OperationsService

            triggered_by = str(getattr(batch_op, "id", "") or "").strip()
            if triggered_by and BatchOperation.objects.filter(metadata__triggered_by_operation_id=triggered_by).exists():
                runtime.logger.info(
                    "post_completion_extensions_sync: follow-up already exists (triggered_by=%s)",
                    triggered_by,
                )
                return

            exec_cfg = metadata.get("post_completion_extensions_sync_executor")
            if not isinstance(exec_cfg, dict):
                runtime.logger.warning(
                    "post_completion_extensions_sync: missing explicit executor in metadata (tenant=%s)",
                    tenant_id_str,
                )
                return

            if not isinstance(exec_cfg, dict) or exec_cfg.get("kind") != "ibcmd_cli":
                runtime.logger.warning(
                    "post_completion_extensions_sync: extensions.sync executor is not ibcmd_cli (tenant=%s)",
                    tenant_id_str,
                )
                return

            driver = str(exec_cfg.get("driver") or "ibcmd").strip().lower() or "ibcmd"
            if driver != "ibcmd":
                runtime.logger.warning(
                    "post_completion_extensions_sync: extensions.sync driver must be ibcmd (got=%s tenant=%s)",
                    driver,
                    tenant_id_str,
                )
                return

            command_id = str(exec_cfg.get("command_id") or "").strip()
            if not command_id:
                return

            mode = str(exec_cfg.get("mode") or "guided").strip().lower()
            params = exec_cfg.get("params") if isinstance(exec_cfg.get("params"), dict) else {}
            additional_args = exec_cfg.get("additional_args") if isinstance(exec_cfg.get("additional_args"), list) else []
            stdin = exec_cfg.get("stdin") if isinstance(exec_cfg.get("stdin"), str) else ""

            versions = resolve_driver_catalog_versions("ibcmd")
            if versions.base_version is None:
                runtime.logger.warning(
                    "post_completion_extensions_sync: ibcmd catalog is not available (tenant=%s)",
                    tenant_id_str,
                )
                return

            effective = get_effective_driver_catalog(
                driver="ibcmd",
                base_version=versions.base_version,
                overrides_version=versions.overrides_version,
            )
            commands_by_id = effective.catalog.get("commands_by_id") if isinstance(effective.catalog, dict) else None
            if not isinstance(commands_by_id, dict):
                return
            command = commands_by_id.get(command_id)
            if not isinstance(command, dict):
                runtime.logger.warning(
                    "post_completion_extensions_sync: unknown ibcmd command_id=%s (tenant=%s)",
                    command_id,
                    tenant_id_str,
                )
                return

            connection: dict[str, Any] = {}
            pre_args = build_ibcmd_connection_args(
                driver_schema=effective.catalog.get("driver_schema") if isinstance(effective.catalog, dict) else None,
                connection=connection,
            )
            builder = build_ibcmd_cli_argv_manual if mode == "manual" else build_ibcmd_cli_argv
            argv, argv_masked = builder(
                command=command,
                params=params if isinstance(params, dict) else {},
                additional_args=[str(x) for x in additional_args if x is not None],
                pre_args=pre_args,
            )

            operation_id = str(uuid.uuid4())
            operation_name = f"extensions.sync (post_completion) - {len(succeeded)} databases"

            payload_data = {
                "command_id": command_id,
                "mode": mode,
                "argv": argv,
                "argv_masked": argv_masked,
                "stdin": stdin,
                "connection": connection,
                "connection_source": "database_profile",
                "ib_auth": {"strategy": "service"},
                "dbms_auth": {"strategy": "service"},
            }
            payload = {"data": payload_data, "filters": {}, "options": {}}

            sync_op = BatchOperation.objects.create(
                id=operation_id,
                name=operation_name,
                operation_type=BatchOperation.TYPE_IBCMD_CLI,
                target_entity="Infobase",
                status=BatchOperation.STATUS_PENDING,
                payload=payload,
                config={
                    "batch_size": 1,
                    "timeout_seconds": int((exec_cfg.get("fixed") or {}).get("timeout_seconds") or 900),
                    "retry_count": 1,
                    "priority": "normal",
                },
                total_tasks=len(succeeded),
                created_by="system",
                metadata={
                    "tags": ["ibcmd", "ibcmd_cli", command_id],
                    "command_id": command_id,
                    "mode": mode,
                    "snapshot_kinds": ["extensions"],
                    "snapshot_source": "extensions_plan_apply.post_completion",
                    "manual_operation": "extensions.sync",
                    "triggered_by_operation_id": str(getattr(batch_op, "id", "")),
                },
            )

            dbs = list(Database.objects.filter(id__in=succeeded))
            sync_op.target_databases.set(dbs)

            tasks = []
            for db in dbs:
                tasks.append(
                    runtime.Task(
                        id=f"{operation_id}-{str(getattr(db, 'id', ''))[:8]}",
                        batch_operation=sync_op,
                        database=db,
                        status=runtime.Task.STATUS_PENDING,
                    )
                )
            runtime.Task.objects.bulk_create(tasks)

            enqueue_res = OperationsService.enqueue_operation(operation_id)
            if not enqueue_res.success:
                runtime.logger.warning(
                    "post_completion_extensions_sync: enqueue failed (op=%s error=%s)",
                    operation_id,
                    getattr(enqueue_res, "error", None),
                )
                return

            runtime.logger.info(
                "post_completion_extensions_sync: enqueued extensions.sync (op=%s, triggered_by=%s, databases=%d)",
                operation_id,
                str(getattr(batch_op, "id", "")),
                len(dbs),
            )
        except Exception as exc:
            runtime.logger.warning(
                "post_completion_extensions_sync failed (tenant=%s op=%s): %s",
                tenant_id_str,
                str(getattr(batch_op, "id", "")),
                str(exc),
                exc_info=True,
            )

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

            terminal_statuses = {
                BatchOperation.STATUS_COMPLETED,
                BatchOperation.STATUS_FAILED,
                BatchOperation.STATUS_CANCELLED,
            }
            is_workflow_root = str(batch_op.operation_type or "").strip() == "execute_workflow"
            if is_workflow_root and batch_op.status in terminal_statuses and batch_op.status != BatchOperation.STATUS_FAILED:
                runtime.logger.warning(
                    "Skipping worker:failed status regression for workflow root",
                    extra={"operation_id": operation_id, "current_status": batch_op.status},
                )
                return

            batch_op.status = BatchOperation.STATUS_FAILED
            batch_op.progress = 100
            if not batch_op.completed_at:
                batch_op.completed_at = timezone.now()

            if not isinstance(batch_op.metadata, dict):
                batch_op.metadata = {}
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
