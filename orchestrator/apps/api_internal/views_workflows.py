import hashlib
import json
import uuid
from collections.abc import Mapping

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Max
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import IsInternalService
from .serializers import PoolRuntimeStepExecutionSerializer, WorkflowExecutionStatusUpdateSerializer
from .views_common import _model_dump, exclude_schema, logger

APPROVAL_STATE_NOT_REQUIRED = "not_required"
APPROVAL_STATE_PREPARING = "preparing"
APPROVAL_STATE_AWAITING_APPROVAL = "awaiting_approval"
APPROVAL_STATE_APPROVED = "approved"

PUBLICATION_STEP_STATE_NOT_ENQUEUED = "not_enqueued"
PUBLICATION_STEP_STATE_QUEUED = "queued"
PUBLICATION_STEP_STATE_STARTED = "started"
PUBLICATION_STEP_STATE_COMPLETED = "completed"
POOL_RUNTIME_CONTEXT_MISMATCH = "POOL_RUNTIME_CONTEXT_MISMATCH"
IDEMPOTENCY_KEY_CONFLICT = "IDEMPOTENCY_KEY_CONFLICT"
POOL_RUNTIME_PUBLICATION_PATH_DISABLED = "POOL_RUNTIME_PUBLICATION_PATH_DISABLED"
ERROR_DETAILS_MAX_SIZE_BYTES = 8 * 1024
ERROR_DETAILS_REDACTED_VALUE = "***REDACTED***"
ERROR_DETAILS_MAX_DEPTH = 4
ERROR_DETAILS_MAX_LIST_ITEMS = 32
ERROR_DETAILS_MAX_STRING_LENGTH = 2048
ERROR_DETAILS_ALLOWED_TOP_LEVEL_KEYS = {
    "http_status",
    "attempts",
    "deadline_reached",
    "retry_after_seconds",
    "retry_after_ms",
    "retry_budget_seconds",
    "step_attempt",
    "transport_attempt",
    "node_id",
    "operation_type",
    "pool_run_id",
    "workflow_execution_id",
    "tenant_id",
    "error_class",
    "error_kind",
    "reason",
    "message",
    "context",
}


def _build_status_update_response(*, execution) -> dict[str, object]:
    payload: dict[str, object] = {
        "success": True,
        "execution_id": str(execution.id),
        "status": execution.status,
    }
    error_code = str(getattr(execution, "error_code", "") or "").strip()
    if error_code:
        payload["error_code"] = error_code
    return payload


def _sync_workflow_root_projection_from_execution(*, execution) -> None:
    try:
        from apps.operations.services import OperationsService

        OperationsService.sync_workflow_root_operation_status(
            execution_id=str(execution.id),
            workflow_status=execution.status,
            node_id=execution.current_node_id,
            trace_id=execution.trace_id,
            error_message=execution.error_message,
            error_code=execution.error_code,
            error_details=execution.error_details,
        )
    except Exception:
        logger.exception(
            "Failed to sync workflow root projection status",
            extra={"execution_id": str(getattr(execution, "id", "")), "status": getattr(execution, "status", "")},
        )


def _build_error_response_payload(*, error: str, code: str, details: str | None = None) -> dict[str, str]:
    payload = {"error": error, "code": code}
    if details:
        payload["details"] = details
    return payload


def _extract_error_code(error_message: str) -> str:
    token = str(error_message or "").split(":", 1)[0].strip()
    if token and all(ch.isalnum() or ch == "_" for ch in token):
        return token
    return ""


def _build_pool_runtime_request_fingerprint(
    *,
    tenant_id: str,
    pool_run_id: str,
    workflow_execution_id: str,
    node_id: str,
    operation_type: str,
    operation_ref: dict[str, object],
    step_attempt: int,
    payload: dict[str, object],
) -> str:
    canonical_payload = {
        "tenant_id": tenant_id,
        "pool_run_id": pool_run_id,
        "workflow_execution_id": workflow_execution_id,
        "node_id": node_id,
        "operation_type": operation_type,
        "operation_ref": operation_ref,
        "step_attempt": step_attempt,
        "payload": payload,
    }
    encoded = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _build_idempotency_replay_payload(
    *,
    snapshot: dict[str, object],
    idempotency_key: str,
    step_attempt: int | None = None,
    transport_attempt: int | None = None,
) -> dict[str, object]:
    replay_payload = dict(snapshot)
    replay_payload["idempotency_key"] = str(replay_payload.get("idempotency_key") or idempotency_key)
    if step_attempt is not None:
        replay_payload["step_attempt"] = int(step_attempt)
    if transport_attempt is not None:
        replay_payload["transport_attempt"] = int(transport_attempt)
    replay_payload["idempotency_replayed"] = True
    replay_payload["side_effect_applied"] = False
    return replay_payload


def _is_sensitive_error_details_key(key: str) -> bool:
    token = str(key or "").strip().lower()
    if not token:
        return False
    sensitive_markers = (
        "password",
        "passwd",
        "secret",
        "token",
        "authorization",
        "api_key",
        "apikey",
        "cookie",
        "credential",
    )
    return any(marker in token for marker in sensitive_markers)


def _sanitize_error_details_value(value: object, *, key: str, depth: int) -> object:
    if _is_sensitive_error_details_key(key):
        return ERROR_DETAILS_REDACTED_VALUE

    if depth >= ERROR_DETAILS_MAX_DEPTH:
        return "<max_depth_reached>"

    if isinstance(value, Mapping):
        sanitized_map: dict[str, object] = {}
        for raw_child_key, raw_child_value in value.items():
            child_key = str(raw_child_key or "").strip()[:128]
            if not child_key:
                continue
            sanitized_map[child_key] = _sanitize_error_details_value(
                raw_child_value,
                key=child_key,
                depth=depth + 1,
            )
        return sanitized_map

    if isinstance(value, list):
        return [
            _sanitize_error_details_value(item, key=key, depth=depth + 1)
            for item in value[:ERROR_DETAILS_MAX_LIST_ITEMS]
        ]

    if isinstance(value, tuple):
        return [
            _sanitize_error_details_value(item, key=key, depth=depth + 1)
            for item in value[:ERROR_DETAILS_MAX_LIST_ITEMS]
        ]

    if isinstance(value, str):
        text = value
        if len(text) > ERROR_DETAILS_MAX_STRING_LENGTH:
            text = f"{text[:ERROR_DETAILS_MAX_STRING_LENGTH]}...<truncated>"
        return text

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    return str(value)


def _json_size_bytes(value: object) -> int:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return len(encoded)


def _apply_error_details_size_cap(details: dict[str, object]) -> dict[str, object]:
    if _json_size_bytes(details) <= ERROR_DETAILS_MAX_SIZE_BYTES:
        return details

    trimmed = dict(details)
    dropped_fields: list[str] = []

    while _json_size_bytes(trimmed) > ERROR_DETAILS_MAX_SIZE_BYTES:
        removable = [key for key in trimmed.keys() if not key.startswith("_")]
        if not removable:
            break
        key_to_drop = max(removable, key=lambda key: _json_size_bytes(trimmed.get(key)))
        dropped_fields.append(key_to_drop)
        trimmed.pop(key_to_drop, None)

    trimmed["_truncated"] = True
    if dropped_fields:
        trimmed["_dropped_fields"] = dropped_fields[:16]

    while _json_size_bytes(trimmed) > ERROR_DETAILS_MAX_SIZE_BYTES and trimmed.get("_dropped_fields"):
        trimmed["_dropped_fields"] = trimmed["_dropped_fields"][:-1]

    if _json_size_bytes(trimmed) > ERROR_DETAILS_MAX_SIZE_BYTES:
        return {"_truncated": True}

    return trimmed


def _sanitize_error_details(details: object) -> dict[str, object] | None:
    if details is None:
        return None

    normalized: dict[str, object] = {}
    if isinstance(details, Mapping):
        for raw_key, raw_value in details.items():
            key = str(raw_key or "").strip()[:128]
            if not key:
                continue
            key_lc = key.lower()
            if key_lc not in ERROR_DETAILS_ALLOWED_TOP_LEVEL_KEYS and not _is_sensitive_error_details_key(key):
                continue
            normalized[key] = _sanitize_error_details_value(raw_value, key=key, depth=0)
    else:
        normalized["message"] = _sanitize_error_details_value(details, key="message", depth=0)

    if not normalized:
        normalized["context"] = {}

    return _apply_error_details_size_cap(normalized)


def _parse_positive_int(value: object, *, default: int, minimum: int = 1) -> int:
    if isinstance(value, bool):
        return default
    parsed: int | None = None
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float):
        if value.is_integer():
            parsed = int(value)
    elif isinstance(value, str):
        token = value.strip()
        if token:
            try:
                parsed = int(token)
            except ValueError:
                parsed = None
    if parsed is None or parsed < minimum:
        return default
    return parsed


def _extract_publication_result_payload(result_payload: object) -> dict[str, object] | None:
    def _normalize_candidate(candidate: object) -> dict[str, object] | None:
        if not isinstance(candidate, Mapping):
            return None
        if str(candidate.get("step") or "").strip().lower() == "publication_odata":
            return dict(candidate)
        nested_output = candidate.get("output")
        if isinstance(nested_output, Mapping):
            if str(nested_output.get("step") or "").strip().lower() == "publication_odata":
                return dict(nested_output)
        return None

    if not isinstance(result_payload, Mapping):
        return None

    direct = _normalize_candidate(result_payload)
    if direct is not None:
        return direct

    for container_key in ("node_results", "nodes"):
        container = result_payload.get(container_key)
        if not isinstance(container, Mapping):
            continue
        direct_candidate = _normalize_candidate(container.get("publication_odata"))
        if direct_candidate is not None:
            return direct_candidate
        for candidate in container.values():
            normalized = _normalize_candidate(candidate)
            if normalized is not None:
                return normalized
    return None


def _normalize_publication_attempt_rows(
    *,
    raw_attempts: object,
    entity_name: str,
    documents_count_by_database: dict[str, int],
) -> list[dict[str, object]]:
    if not isinstance(raw_attempts, list):
        return []

    normalized: list[dict[str, object]] = []
    for raw_attempt in raw_attempts:
        if not isinstance(raw_attempt, Mapping):
            continue
        target_database = str(
            raw_attempt.get("target_database")
            or raw_attempt.get("target_database_id")
            or raw_attempt.get("database_id")
            or ""
        ).strip()
        if not target_database:
            continue

        raw_status = str(raw_attempt.get("status") or "").strip().lower()
        status_value = "success" if raw_status == "success" else "failed"
        default_documents_count = max(int(documents_count_by_database.get(target_database) or 0), 1)
        documents_count = _parse_positive_int(
            raw_attempt.get("documents_count"),
            default=default_documents_count,
        )
        request_summary = raw_attempt.get("request_summary")
        if not isinstance(request_summary, Mapping):
            request_summary = {"documents_count": documents_count}
        response_summary = raw_attempt.get("response_summary")
        if not isinstance(response_summary, Mapping):
            response_summary = {"posted": status_value == "success"}

        posted = bool(
            raw_attempt.get("posted")
            if "posted" in raw_attempt
            else status_value == "success"
        )
        error_code = str(raw_attempt.get("error_code") or "").strip()
        error_message = str(raw_attempt.get("error_message") or "").strip()
        http_status_value = raw_attempt.get("http_status")
        http_status = None
        if isinstance(http_status_value, int):
            http_status = http_status_value
        elif isinstance(http_status_value, float) and http_status_value.is_integer():
            http_status = int(http_status_value)

        normalized.append(
            {
                "target_database": target_database,
                "attempt_number": _parse_positive_int(raw_attempt.get("attempt_number"), default=1),
                "status": status_value,
                "entity_name": str(raw_attempt.get("entity_name") or "").strip() or entity_name,
                "documents_count": documents_count,
                "posted": posted,
                "error_code": error_code,
                "error_message": error_message,
                "http_status": http_status,
                "request_summary": dict(request_summary),
                "response_summary": dict(response_summary),
            }
        )
    return normalized


def _synthesize_publication_attempt_rows(
    *,
    target_databases: list[str],
    entity_name: str,
    documents_count_by_database: dict[str, int],
    failed_databases: dict[str, str],
    failed_databases_diagnostics: dict[str, dict[str, object]],
    max_attempts: int,
) -> list[dict[str, object]]:
    synthesized: list[dict[str, object]] = []
    for database_id in target_databases:
        is_failed = database_id in failed_databases or database_id in failed_databases_diagnostics
        diagnostics = failed_databases_diagnostics.get(database_id) or {}
        attempts_count = 1
        if is_failed:
            attempts_count = _parse_positive_int(
                diagnostics.get("attempts"),
                default=max(max_attempts, 1),
            )

        documents_count = _parse_positive_int(
            documents_count_by_database.get(database_id),
            default=1,
        )
        status_value = "failed" if is_failed else "success"
        error_message = ""
        error_code = ""
        http_status = None
        if is_failed:
            error_message = str(
                failed_databases.get(database_id)
                or diagnostics.get("error")
                or ""
            ).strip()
            error_code = str(diagnostics.get("error_code") or "").strip()
            raw_http_status = diagnostics.get("http_status")
            if isinstance(raw_http_status, int):
                http_status = raw_http_status
            elif isinstance(raw_http_status, float) and raw_http_status.is_integer():
                http_status = int(raw_http_status)

        for attempt_number in range(1, attempts_count + 1):
            synthesized.append(
                {
                    "target_database": database_id,
                    "attempt_number": attempt_number,
                    "status": status_value,
                    "entity_name": entity_name,
                    "documents_count": documents_count,
                    "posted": not is_failed,
                    "error_code": error_code,
                    "error_message": error_message,
                    "http_status": http_status,
                    "request_summary": {"documents_count": documents_count},
                    "response_summary": {"posted": not is_failed},
                }
            )
    return synthesized


def _project_pool_publication_attempts_from_result(*, execution, result_payload: object) -> None:
    from apps.databases.models import Database
    from apps.intercompany_pools.models import (
        PoolPublicationAttempt,
        PoolPublicationAttemptStatus,
        PoolRun,
    )

    if str(execution.execution_consumer or "") != "pools":
        return

    publication_result = _extract_publication_result_payload(result_payload)
    if publication_result is None:
        return

    execution_context = execution.input_context if isinstance(execution.input_context, dict) else {}
    pool_run_id = str(
        publication_result.get("pool_run_id")
        or execution_context.get("pool_run_id")
        or ""
    ).strip()
    if not pool_run_id:
        return

    try:
        pool_run_uuid = uuid.UUID(pool_run_id)
    except ValueError:
        logger.warning(
            "Skipping publication projection: invalid pool run id",
            extra={"execution_id": str(execution.id), "pool_run_id": pool_run_id},
        )
        return

    run = PoolRun.objects.filter(id=pool_run_uuid).first()
    if run is None:
        logger.warning(
            "Skipping publication projection: pool run is missing",
            extra={"execution_id": str(execution.id), "pool_run_id": pool_run_id},
        )
        return

    execution_tenant_id = str(getattr(execution, "tenant_id", "") or "").strip()
    if execution_tenant_id and str(run.tenant_id) != execution_tenant_id:
        logger.warning(
            "Skipping publication projection due to tenant mismatch",
            extra={
                "execution_id": str(execution.id),
                "pool_run_id": str(run.id),
                "run_tenant_id": str(run.tenant_id),
                "execution_tenant_id": execution_tenant_id,
            },
        )
        return

    target_databases: list[str] = []
    raw_targets = publication_result.get("target_databases")
    if isinstance(raw_targets, list):
        for raw_value in raw_targets:
            normalized = str(raw_value or "").strip()
            if normalized and normalized not in target_databases:
                target_databases.append(normalized)

    documents_count_by_database: dict[str, int] = {}
    raw_documents_count = publication_result.get("documents_count_by_database")
    if isinstance(raw_documents_count, Mapping):
        for raw_database_id, raw_count in raw_documents_count.items():
            database_id = str(raw_database_id or "").strip()
            if not database_id:
                continue
            documents_count_by_database[database_id] = _parse_positive_int(
                raw_count,
                default=1,
            )
            if database_id not in target_databases:
                target_databases.append(database_id)

    failed_databases: dict[str, str] = {}
    raw_failed_databases = publication_result.get("failed_databases")
    if isinstance(raw_failed_databases, Mapping):
        for raw_database_id, raw_error in raw_failed_databases.items():
            database_id = str(raw_database_id or "").strip()
            if not database_id:
                continue
            failed_databases[database_id] = str(raw_error or "").strip()
            if database_id not in target_databases:
                target_databases.append(database_id)

    failed_databases_diagnostics: dict[str, dict[str, object]] = {}
    raw_failed_diagnostics = publication_result.get("failed_databases_diagnostics")
    if isinstance(raw_failed_diagnostics, Mapping):
        for raw_database_id, raw_diagnostics in raw_failed_diagnostics.items():
            database_id = str(raw_database_id or "").strip()
            if not database_id or not isinstance(raw_diagnostics, Mapping):
                continue
            failed_databases_diagnostics[database_id] = dict(raw_diagnostics)
            if database_id not in target_databases:
                target_databases.append(database_id)

    entity_name = str(
        publication_result.get("entity_name") or "Document_РеализацияТоваровУслуг"
    ).strip() or "Document_РеализацияТоваровУслуг"
    max_attempts = _parse_positive_int(publication_result.get("max_attempts"), default=1)
    attempt_rows = _normalize_publication_attempt_rows(
        raw_attempts=publication_result.get("attempts"),
        entity_name=entity_name,
        documents_count_by_database=documents_count_by_database,
    )
    if not attempt_rows and target_databases:
        attempt_rows = _synthesize_publication_attempt_rows(
            target_databases=target_databases,
            entity_name=entity_name,
            documents_count_by_database=documents_count_by_database,
            failed_databases=failed_databases,
            failed_databases_diagnostics=failed_databases_diagnostics,
            max_attempts=max_attempts,
        )

    database_ids: set[str] = set(target_databases)
    for row in attempt_rows:
        database_ids.add(str(row.get("target_database") or "").strip())
    database_ids = {value for value in database_ids if value}
    valid_database_ids: set[str] = set()
    for database_id in database_ids:
        try:
            valid_database_ids.add(str(uuid.UUID(database_id)))
        except ValueError:
            logger.warning(
                "Skipping publication projection for invalid database id",
                extra={
                    "execution_id": str(execution.id),
                    "pool_run_id": str(run.id),
                    "target_database_id": database_id,
                },
            )

    databases = {
        str(db.id): db
        for db in Database.objects.filter(
            id__in=list(valid_database_ids),
            tenant=run.tenant,
        )
    }

    if attempt_rows:
        existing_attempts = (
            PoolPublicationAttempt.objects.filter(
                run=run,
                target_database_id__in=list(databases.keys()),
            )
            .values("target_database_id")
            .annotate(max_attempt=Max("attempt_number"))
        )
        attempt_offset_by_database = {
            str(item["target_database_id"]): int(item["max_attempt"] or 0)
            for item in existing_attempts
        }

        for row in attempt_rows:
            database_id = str(row.get("target_database") or "").strip()
            target_database = databases.get(database_id)
            if target_database is None:
                logger.warning(
                    "Skipping publication attempt projection: database is missing",
                    extra={
                        "execution_id": str(execution.id),
                        "pool_run_id": str(run.id),
                        "target_database_id": database_id,
                    },
                )
                continue

            local_attempt_number = _parse_positive_int(row.get("attempt_number"), default=1)
            attempt_number = attempt_offset_by_database.get(database_id, 0) + local_attempt_number
            status_value = str(row.get("status") or "").strip().lower()
            if status_value not in {
                PoolPublicationAttemptStatus.SUCCESS,
                PoolPublicationAttemptStatus.FAILED,
            }:
                status_value = PoolPublicationAttemptStatus.FAILED

            PoolPublicationAttempt.objects.update_or_create(
                run=run,
                target_database=target_database,
                attempt_number=attempt_number,
                defaults={
                    "tenant": run.tenant,
                    "status": status_value,
                    "entity_name": str(row.get("entity_name") or entity_name).strip() or entity_name,
                    "documents_count": _parse_positive_int(
                        row.get("documents_count"),
                        default=1,
                    ),
                    "posted": bool(row.get("posted")),
                    "http_status": row.get("http_status"),
                    "error_code": str(row.get("error_code") or "").strip(),
                    "error_message": str(row.get("error_message") or "").strip(),
                    "request_summary": dict(row.get("request_summary") or {}),
                    "response_summary": dict(row.get("response_summary") or {}),
                    "started_at": timezone.now(),
                    "finished_at": timezone.now(),
                },
            )

    total_targets = _parse_positive_int(
        publication_result.get("documents_targets"),
        default=len(target_databases),
        minimum=0,
    )
    failed_targets = _parse_positive_int(
        publication_result.get("failed_targets"),
        default=len(failed_databases),
        minimum=0,
    )
    succeeded_targets = _parse_positive_int(
        publication_result.get("succeeded_targets"),
        default=max(total_targets - failed_targets, 0),
        minimum=0,
    )
    run.publication_summary = {
        "total_targets": total_targets,
        "succeeded_targets": succeeded_targets,
        "failed_targets": failed_targets,
        "max_attempts": max_attempts,
    }
    run.save(update_fields=["publication_summary", "updated_at"])

    current_publication_state = str(
        execution_context.get("publication_step_state") or ""
    ).strip().lower()
    if current_publication_state != PUBLICATION_STEP_STATE_COMPLETED:
        updated_context = dict(execution_context)
        updated_context["publication_step_state"] = PUBLICATION_STEP_STATE_COMPLETED
        execution.input_context = updated_context


def _resolve_workflow_node(*, execution, node_id: str) -> dict[str, object] | None:
    dag_structure = _model_dump(execution.workflow_template.dag_structure)
    if not isinstance(dag_structure, dict):
        return None
    nodes = dag_structure.get("nodes")
    if not isinstance(nodes, list):
        return None

    target_node_id = str(node_id or "").strip()
    for node in nodes:
        if isinstance(node, dict) and str(node.get("id") or "").strip() == target_node_id:
            return node
    return None


def _resolve_node_operation_type(node: dict[str, object]) -> str:
    operation_ref = node.get("operation_ref")
    if isinstance(operation_ref, dict):
        alias = str(operation_ref.get("alias") or "").strip()
        if alias:
            return alias
    return str(node.get("template_id") or "").strip()


def _validate_node_operation_ref(
    *,
    node_id: str,
    node_operation_ref: dict[str, object],
    request_operation_ref: dict[str, object],
) -> str | None:
    expected_binding_mode = str(node_operation_ref.get("binding_mode") or "").strip()
    expected_exposure_id = str(node_operation_ref.get("template_exposure_id") or "").strip()
    expected_exposure_revision = str(node_operation_ref.get("template_exposure_revision") or "").strip()

    # Enforce strict operation_ref matching only for pinned references.
    if expected_binding_mode != "pinned_exposure" and not expected_exposure_id and not expected_exposure_revision:
        return None

    for field in ("alias", "binding_mode", "template_exposure_id", "template_exposure_revision"):
        expected_raw = node_operation_ref.get(field)
        expected = str(expected_raw or "").strip()
        if not expected:
            continue
        actual = str(request_operation_ref.get(field) or "").strip()
        if actual != expected:
            return f"workflow node '{node_id}' expects operation_ref.{field}='{expected}', got '{actual}'"
    return None


def _validate_pool_runtime_bridge_context(
    *,
    execution,
    run,
    tenant_id: str,
    node_id: str,
    operation_type: str,
    operation_ref: dict[str, object],
) -> str | None:
    if str(execution.execution_consumer or "") != "pools":
        return f"workflow execution '{execution.id}' is not pool-scoped"

    execution_tenant_id = str(execution.tenant_id or "").strip()
    if execution_tenant_id != tenant_id:
        return f"execution tenant '{execution_tenant_id}' does not match request tenant '{tenant_id}'"

    run_tenant_id = str(run.tenant_id or "").strip()
    if run_tenant_id != tenant_id:
        return f"pool run tenant '{run_tenant_id}' does not match request tenant '{tenant_id}'"

    run_execution_id = str(run.workflow_execution_id or "").strip()
    execution_id = str(execution.id)
    if not run_execution_id or run_execution_id != execution_id:
        return (
            f"pool run '{run.id}' is linked to execution '{run_execution_id or '<none>'}', "
            f"got '{execution_id}'"
        )

    node = _resolve_workflow_node(execution=execution, node_id=node_id)
    if node is None:
        return f"workflow node '{node_id}' does not exist in template '{execution.workflow_template_id}'"

    expected_operation_type = _resolve_node_operation_type(node)
    if expected_operation_type and expected_operation_type != operation_type:
        return (
            f"workflow node '{node_id}' expects operation '{expected_operation_type}', "
            f"got '{operation_type}'"
        )

    current_node_id = str(execution.current_node_id or "").strip()
    if current_node_id and current_node_id != node_id:
        return f"workflow execution '{execution.id}' currently points to node '{current_node_id}', got '{node_id}'"

    node_operation_ref = node.get("operation_ref")
    if isinstance(node_operation_ref, dict):
        operation_ref_mismatch = _validate_node_operation_ref(
            node_id=node_id,
            node_operation_ref=node_operation_ref,
            request_operation_ref=operation_ref,
        )
        if operation_ref_mismatch:
            return operation_ref_mismatch

    return None


@exclude_schema
@api_view(["GET"])
@permission_classes([IsInternalService])
def get_workflow_execution(request):
    """
    GET /api/v2/internal/workflows/get-execution?execution_id=<uuid>

    Returns workflow execution data for Go Worker.
    """
    from apps.templates.workflow.models import WorkflowExecution

    execution_id = request.query_params.get("execution_id")
    if not execution_id:
        return Response({"success": False, "error": "execution_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        uuid.UUID(str(execution_id))
    except ValueError:
        return Response({"success": False, "error": "execution_id must be a valid UUID"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        execution = WorkflowExecution.objects.select_related("workflow_template").get(id=execution_id)
    except WorkflowExecution.DoesNotExist:
        return Response({"success": False, "error": "Workflow execution not found"}, status=status.HTTP_404_NOT_FOUND)

    template = execution.workflow_template

    response = {
        "id": str(execution.id),
        "workflow_template": {
            "id": str(template.id),
            "name": template.name,
            "description": template.description or "",
            "workflow_type": template.workflow_type,
            "dag_structure": _model_dump(template.dag_structure),
            "config": _model_dump(template.config),
            "is_valid": template.is_valid,
            "is_active": template.is_active,
            "version_number": template.version_number,
        },
        "input_context": execution.input_context or {},
        "status": execution.status,
        "current_node_id": execution.current_node_id,
        "completed_nodes": execution.completed_nodes or [],
        "failed_nodes": execution.failed_nodes or [],
    }

    return Response(response)


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def execute_pool_runtime_step_v2(request):
    """
    POST /api/v2/internal/workflows/execute-pool-runtime-step

    Executes pool runtime step via canonical internal bridge endpoint.
    """
    from apps.intercompany_pools.models import PoolRun, PoolRuntimeStepIdempotencyLog
    from apps.intercompany_pools.pool_domain_steps import execute_pool_runtime_step
    from apps.templates.workflow.models import WorkflowExecution

    serializer = PoolRuntimeStepExecutionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            _build_error_response_payload(
                error="Invalid request body",
                code="BAD_REQUEST",
                details=str(serializer.errors),
            ),
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    workflow_execution_id = data["workflow_execution_id"]
    pool_run_id = data["pool_run_id"]
    tenant_id = str(data["tenant_id"])
    node_id = str(data["node_id"] or "").strip()
    operation_type = str(data["operation_type"] or "").strip()
    step_attempt = int(data["step_attempt"])
    transport_attempt = int(data["transport_attempt"])
    idempotency_key = str(data["idempotency_key"] or "").strip()
    operation_ref = dict(data.get("operation_ref") or {})
    publication_auth = data.get("publication_auth") if isinstance(data.get("publication_auth"), dict) else None
    rendered_payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}

    try:
        execution = WorkflowExecution.objects.select_related("workflow_template").get(id=workflow_execution_id)
    except WorkflowExecution.DoesNotExist:
        return Response(
            _build_error_response_payload(error="Workflow execution not found", code="NOT_FOUND"),
            status=status.HTTP_404_NOT_FOUND,
        )

    run = PoolRun.objects.filter(id=pool_run_id).first()
    if run is None:
        return Response(
            _build_error_response_payload(error="Pool run not found", code="NOT_FOUND"),
            status=status.HTTP_404_NOT_FOUND,
        )

    mismatch_details = _validate_pool_runtime_bridge_context(
        execution=execution,
        run=run,
        tenant_id=tenant_id,
        node_id=node_id,
        operation_type=operation_type,
        operation_ref=operation_ref,
    )
    if mismatch_details:
        return Response(
            _build_error_response_payload(
                error="Bridge context does not match execution scope",
                code=POOL_RUNTIME_CONTEXT_MISMATCH,
                details=mismatch_details,
            ),
            status=status.HTTP_409_CONFLICT,
        )

    if operation_type == "pool.publication_odata":
        return Response(
            _build_error_response_payload(
                error="Publication OData side effects are disabled for bridge path",
                code=POOL_RUNTIME_PUBLICATION_PATH_DISABLED,
            ),
            status=status.HTTP_409_CONFLICT,
        )

    request_fingerprint = _build_pool_runtime_request_fingerprint(
        tenant_id=tenant_id,
        pool_run_id=str(run.id),
        workflow_execution_id=str(execution.id),
        node_id=node_id,
        operation_type=operation_type,
        operation_ref=operation_ref,
        step_attempt=step_attempt,
        payload=rendered_payload,
    )
    response_payload: dict[str, object] = {}

    try:
        with transaction.atomic():
            existing = (
                PoolRuntimeStepIdempotencyLog.objects.select_for_update()
                .filter(tenant_id=run.tenant_id, idempotency_key=idempotency_key)
                .order_by("id")
                .first()
            )
            if existing is not None:
                if existing.request_fingerprint != request_fingerprint:
                    return Response(
                        _build_error_response_payload(
                            error="Idempotency key conflict",
                            code=IDEMPOTENCY_KEY_CONFLICT,
                        ),
                        status=status.HTTP_409_CONFLICT,
                    )
                replay_snapshot = dict(existing.response_snapshot or {})
                PoolRuntimeStepIdempotencyLog.objects.filter(id=existing.id).update(
                    replay_count=F("replay_count") + 1,
                    last_replayed_at=timezone.now(),
                )
                return Response(
                    _build_idempotency_replay_payload(
                        snapshot=replay_snapshot,
                        idempotency_key=idempotency_key,
                        step_attempt=step_attempt,
                        transport_attempt=transport_attempt,
                    ),
                    status=status.HTTP_200_OK,
                )

            runtime_context = {"pool_run_id": str(run.id)}
            if publication_auth:
                runtime_context["publication_auth"] = publication_auth

            step_result = execute_pool_runtime_step(
                operation_type=operation_type,
                rendered_data=rendered_payload,
                context=runtime_context,
                execution=execution,
            )

            response_payload: dict[str, object] = {
                "success": True,
                "workflow_execution_id": str(execution.id),
                "pool_run_id": str(run.id),
                "node_id": node_id,
                "step_attempt": step_attempt,
                "transport_attempt": transport_attempt,
                "idempotency_key": idempotency_key,
                "status": "completed",
                "side_effect_applied": True,
                "idempotency_replayed": False,
                "result": step_result if isinstance(step_result, dict) else {},
            }
            PoolRuntimeStepIdempotencyLog.objects.create(
                run=run,
                tenant_id=run.tenant_id,
                workflow_execution_id=execution.id,
                node_id=node_id,
                operation_type=operation_type,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                response_snapshot=response_payload,
            )
    except IntegrityError:
        existing = (
            PoolRuntimeStepIdempotencyLog.objects.filter(tenant_id=run.tenant_id, idempotency_key=idempotency_key)
            .order_by("id")
            .first()
        )
        if existing is None:
            logger.exception(
                "Pool runtime idempotency persistence failed",
                extra={
                    "workflow_execution_id": str(workflow_execution_id),
                    "pool_run_id": str(pool_run_id),
                    "node_id": node_id,
                },
            )
            return Response(
                _build_error_response_payload(error="Failed to execute pool runtime step", code="INTERNAL_ERROR"),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if existing.request_fingerprint != request_fingerprint:
            return Response(
                _build_error_response_payload(
                    error="Idempotency key conflict",
                    code=IDEMPOTENCY_KEY_CONFLICT,
                ),
                status=status.HTTP_409_CONFLICT,
            )
        replay_snapshot = dict(existing.response_snapshot or {})
        PoolRuntimeStepIdempotencyLog.objects.filter(id=existing.id).update(
            replay_count=F("replay_count") + 1,
            last_replayed_at=timezone.now(),
        )
        return Response(
            _build_idempotency_replay_payload(
                snapshot=replay_snapshot,
                idempotency_key=idempotency_key,
                step_attempt=step_attempt,
                transport_attempt=transport_attempt,
            ),
            status=status.HTTP_200_OK,
        )
    except ValueError as exc:
        message = str(exc)
        parsed_code = _extract_error_code(message) or "BAD_REQUEST"
        if parsed_code in {
            "POOL_RUNTIME_RUN_LINK_MISMATCH",
            "POOL_RUNTIME_TENANT_MISMATCH",
            IDEMPOTENCY_KEY_CONFLICT,
        }:
            return Response(
                _build_error_response_payload(
                    error=message,
                    code=IDEMPOTENCY_KEY_CONFLICT if parsed_code == IDEMPOTENCY_KEY_CONFLICT else POOL_RUNTIME_CONTEXT_MISMATCH,
                ),
                status=status.HTTP_409_CONFLICT,
            )
        if parsed_code == "POOL_RUNTIME_RUN_NOT_FOUND":
            return Response(
                _build_error_response_payload(error=message, code="NOT_FOUND"),
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            _build_error_response_payload(error=message, code=parsed_code),
            status=status.HTTP_400_BAD_REQUEST,
        )
    except ValidationError as exc:
        return Response(
            _build_error_response_payload(error="Pool runtime validation failed", code="BAD_REQUEST", details=str(exc)),
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:
        logger.exception(
            "Failed to execute pool runtime step",
            extra={
                "workflow_execution_id": str(workflow_execution_id),
                "pool_run_id": str(pool_run_id),
                "node_id": node_id,
                "operation_type": operation_type,
            },
        )
        return Response(
            _build_error_response_payload(error="Failed to execute pool runtime step", code="INTERNAL_ERROR"),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(response_payload, status=status.HTTP_200_OK)


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def update_workflow_execution_status(request):
    """
    POST /api/v2/internal/workflows/update-execution-status

    Updates workflow execution status for Go Worker.
    """
    from apps.templates.workflow.models import WorkflowExecution

    serializer = WorkflowExecutionStatusUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    execution_id = data["execution_id"]
    target_status = data["status"]
    error_message = data.get("error_message") or ""
    error_code_provided = "error_code" in data
    error_code = str(data.get("error_code") or "").strip()
    error_details_provided = "error_details" in data
    error_details = _sanitize_error_details(data.get("error_details")) if error_details_provided else None
    result_payload = data.get("result") or {}

    try:
        execution = WorkflowExecution.objects.get(id=execution_id)
    except WorkflowExecution.DoesNotExist:
        return Response({"success": False, "error": "Workflow execution not found"}, status=status.HTTP_404_NOT_FOUND)

    if target_status == execution.status:
        if target_status == WorkflowExecution.STATUS_FAILED:
            update_fields: list[str] = []
            if error_message and error_message != execution.error_message:
                execution.error_message = error_message
                update_fields.append("error_message")
            if error_code_provided and error_code != execution.error_code:
                execution.error_code = error_code
                update_fields.append("error_code")
            if error_details_provided and error_details != execution.error_details:
                execution.error_details = error_details
                update_fields.append("error_details")
            if update_fields:
                execution.save(update_fields=update_fields)
        _sync_workflow_root_projection_from_execution(execution=execution)
        return Response(_build_status_update_response(execution=execution))

    try:
        if target_status == WorkflowExecution.STATUS_RUNNING:
            if execution.status != WorkflowExecution.STATUS_PENDING:
                return Response({"success": False, "error": "Execution is not pending"}, status=status.HTTP_409_CONFLICT)
            execution.start()

        elif target_status == WorkflowExecution.STATUS_COMPLETED:
            if execution.status == WorkflowExecution.STATUS_PENDING:
                execution.start()
            if execution.status != WorkflowExecution.STATUS_RUNNING:
                return Response({"success": False, "error": "Execution is not running"}, status=status.HTTP_409_CONFLICT)
            execution.complete(result_payload)
            _project_pool_publication_attempts_from_result(
                execution=execution,
                result_payload=result_payload,
            )

        elif target_status == WorkflowExecution.STATUS_FAILED:
            if execution.status == WorkflowExecution.STATUS_PENDING:
                execution.start()
            if execution.status != WorkflowExecution.STATUS_RUNNING:
                return Response({"success": False, "error": "Execution is not running"}, status=status.HTTP_409_CONFLICT)
            execution.fail(error_message or "Workflow failed")
            if error_code_provided:
                execution.error_code = error_code
            if error_details_provided:
                execution.error_details = error_details

        elif target_status == WorkflowExecution.STATUS_CANCELLED:
            if execution.status not in [WorkflowExecution.STATUS_PENDING, WorkflowExecution.STATUS_RUNNING]:
                return Response({"success": False, "error": "Execution cannot be cancelled"}, status=status.HTTP_409_CONFLICT)
            execution.cancel()
        else:
            return Response({"success": False, "error": "Unsupported status"}, status=status.HTTP_400_BAD_REQUEST)

        _advance_pools_runtime_metadata_on_status_update(execution=execution, target_status=target_status)
        execution.save()
        _sync_workflow_root_projection_from_execution(execution=execution)

    except Exception:
        logger.exception("Failed to update workflow execution status")
        return Response({"success": False, "error": "Failed to update execution status"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    logger.info("Workflow execution status updated", extra={"execution_id": str(execution.id), "status": execution.status})

    return Response(_build_status_update_response(execution=execution))


def _advance_pools_runtime_metadata_on_status_update(*, execution, target_status: str) -> None:
    if execution.execution_consumer != "pools":
        return

    input_context = execution.input_context if isinstance(execution.input_context, dict) else {}
    if not input_context:
        return

    approval_required = bool(input_context.get("approval_required"))
    approved_at = input_context.get("approved_at")
    raw_state = str(input_context.get("approval_state") or "").strip().lower()

    next_approval_state = raw_state
    if approval_required and not approved_at:
        if target_status == execution.STATUS_COMPLETED and raw_state in {"", APPROVAL_STATE_PREPARING}:
            next_approval_state = APPROVAL_STATE_AWAITING_APPROVAL
    elif approval_required and approved_at:
        next_approval_state = APPROVAL_STATE_APPROVED
    elif not approval_required:
        next_approval_state = APPROVAL_STATE_NOT_REQUIRED

    raw_publication_state = str(input_context.get("publication_step_state") or "").strip().lower()
    next_publication_state = raw_publication_state
    if approval_required and not approved_at:
        if raw_publication_state == "":
            next_publication_state = PUBLICATION_STEP_STATE_NOT_ENQUEUED
    else:
        if raw_publication_state == "":
            next_publication_state = PUBLICATION_STEP_STATE_QUEUED
        elif raw_publication_state == PUBLICATION_STEP_STATE_NOT_ENQUEUED:
            next_publication_state = PUBLICATION_STEP_STATE_QUEUED

    if (
        next_approval_state != raw_state
        or next_publication_state != raw_publication_state
    ):
        updated_context = dict(input_context)
        if next_approval_state:
            updated_context["approval_state"] = next_approval_state
        if next_publication_state:
            updated_context["publication_step_state"] = next_publication_state
        execution.input_context = updated_context
