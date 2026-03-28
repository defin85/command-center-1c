import hashlib
import json
import uuid
from collections.abc import Mapping
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.intercompany_pools.document_plan_artifact_contract import (
    POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY,
)
from apps.intercompany_pools.publication_verification import (
    POOL_RUNTIME_VERIFICATION_CONTEXT_KEY,
    verify_published_documents,
)

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
PUBLICATION_STEP_STATE_RANK = {
    PUBLICATION_STEP_STATE_NOT_ENQUEUED: 0,
    PUBLICATION_STEP_STATE_QUEUED: 1,
    PUBLICATION_STEP_STATE_STARTED: 2,
    PUBLICATION_STEP_STATE_COMPLETED: 3,
}
POOL_RUNTIME_CONTEXT_MISMATCH = "POOL_RUNTIME_CONTEXT_MISMATCH"
IDEMPOTENCY_KEY_CONFLICT = "IDEMPOTENCY_KEY_CONFLICT"
POOL_RUNTIME_PUBLICATION_PATH_DISABLED = "POOL_RUNTIME_PUBLICATION_PATH_DISABLED"
ERROR_DETAILS_MAX_SIZE_BYTES = 8 * 1024
ERROR_DETAILS_REDACTED_VALUE = "***REDACTED***"
ERROR_DETAILS_MAX_DEPTH = 4
ERROR_DETAILS_MAX_LIST_ITEMS = 32
ERROR_DETAILS_MAX_STRING_LENGTH = 2048
WORKFLOW_PROJECTION_IDENTITY_STRATEGY = "workflow_projection"
WORKFLOW_PROJECTION_IDENTITY_PREFIX = "wfproj"
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


def _parse_non_negative_int(value: object, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value if value >= 0 else default
    if isinstance(value, float) and value.is_integer():
        cast_value = int(value)
        return cast_value if cast_value >= 0 else default
    if isinstance(value, str):
        token = value.strip()
        if token:
            try:
                cast_value = int(token)
            except ValueError:
                return default
            return cast_value if cast_value >= 0 else default
    return default


def _preserve_pool_publication_state_on_legacy_input_merge(
    *,
    existing_input_context: Mapping[str, object],
    incoming_input_context: Mapping[str, object],
) -> dict[str, object]:
    normalized_input = dict(incoming_input_context)
    existing_state = str(existing_input_context.get("publication_step_state") or "").strip().lower()
    incoming_state = str(normalized_input.get("publication_step_state") or "").strip().lower()
    existing_rank = PUBLICATION_STEP_STATE_RANK.get(existing_state)
    incoming_rank = PUBLICATION_STEP_STATE_RANK.get(incoming_state)

    if existing_rank is None:
        return normalized_input
    if incoming_rank is None or incoming_rank < existing_rank:
        normalized_input["publication_step_state"] = existing_state
    return normalized_input


def _parse_legacy_datetime(raw_value: object):
    if not isinstance(raw_value, str):
        return None
    token = raw_value.strip()
    if not token:
        return None
    parsed = parse_datetime(token)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _normalize_legacy_workflow_status(raw_status: object) -> str:
    token = str(raw_status or "").strip().lower()
    if token in {"", "none"}:
        return ""
    aliases = {
        "queued": "pending",
        "canceled": "cancelled",
        "paused": "running",
    }
    normalized = aliases.get(token, token)
    if normalized in {"pending", "running", "completed", "failed", "cancelled"}:
        return normalized
    return ""


def _extract_node_results_container(payload: object) -> Mapping[str, object] | None:
    if not isinstance(payload, Mapping):
        return None
    node_results = payload.get("node_results")
    if isinstance(node_results, Mapping) and node_results:
        return node_results
    return None


def _should_preserve_final_result_on_legacy_update(
    *,
    existing_final_result: object,
    incoming_output_data: Mapping[str, object] | None,
) -> bool:
    existing_node_results = _extract_node_results_container(existing_final_result)
    if existing_node_results is None:
        return False
    incoming_node_results = _extract_node_results_container(incoming_output_data)
    return incoming_node_results is None


def _serialize_legacy_workflow_execution_record(*, execution) -> dict[str, object]:
    template = execution.workflow_template
    payload: dict[str, object] = {
        "id": str(execution.id),
        "workflow_id": str(template.id),
        "dag_id": str(template.id),
        "dag_version": int(getattr(template, "version_number", 1) or 1),
        "status": str(execution.status),
        "error_message": str(execution.error_message or ""),
        "input_data": execution.input_context if isinstance(execution.input_context, dict) else {},
        "output_data": execution.final_result if isinstance(execution.final_result, dict) else {},
    }

    if execution.started_at is not None:
        payload["started_at"] = execution.started_at.isoformat()
    if execution.completed_at is not None:
        payload["completed_at"] = execution.completed_at.isoformat()

    created_at = getattr(execution, "created_at", None)
    if created_at is not None:
        payload["created_at"] = created_at.isoformat()
    updated_at = getattr(execution, "updated_at", None)
    if updated_at is not None:
        payload["updated_at"] = updated_at.isoformat()

    return payload


def _apply_legacy_status_transition(
    *,
    execution,
    target_status: str,
    error_message: str,
    output_data: dict[str, object] | None,
) -> tuple[set[str], bool]:
    from apps.templates.workflow.models import WorkflowExecution

    if not target_status:
        return set(), False

    update_fields: set[str] = set()
    status_changed = False
    normalized_output = dict(output_data or {})

    if target_status == execution.status:
        if target_status == WorkflowExecution.STATUS_FAILED and error_message and error_message != execution.error_message:
            execution.error_message = error_message
            update_fields.add("error_message")
        if target_status == WorkflowExecution.STATUS_COMPLETED and output_data is not None:
            if (
                not _should_preserve_final_result_on_legacy_update(
                    existing_final_result=execution.final_result,
                    incoming_output_data=normalized_output,
                )
                and execution.final_result != normalized_output
            ):
                execution.final_result = normalized_output
                update_fields.add("final_result")
        return update_fields, status_changed

    try:
        if target_status == WorkflowExecution.STATUS_RUNNING:
            if execution.status == WorkflowExecution.STATUS_PENDING:
                execution.start()
                update_fields.update({"status", "started_at"})
                status_changed = True

        elif target_status == WorkflowExecution.STATUS_COMPLETED:
            if execution.status == WorkflowExecution.STATUS_PENDING:
                execution.start()
                update_fields.update({"status", "started_at"})
                status_changed = True
            if execution.status == WorkflowExecution.STATUS_RUNNING:
                execution.complete(normalized_output)
                update_fields.update({"status", "final_result", "completed_at"})
                status_changed = True

        elif target_status == WorkflowExecution.STATUS_FAILED:
            if execution.status == WorkflowExecution.STATUS_PENDING:
                execution.start()
                update_fields.update({"status", "started_at"})
                status_changed = True
            if execution.status == WorkflowExecution.STATUS_RUNNING:
                execution.fail(error_message or "Workflow failed")
                update_fields.update({"status", "error_message", "error_node_id", "completed_at"})
                status_changed = True
            elif error_message and error_message != execution.error_message:
                execution.error_message = error_message
                update_fields.add("error_message")

        elif target_status == WorkflowExecution.STATUS_CANCELLED:
            if execution.status in {WorkflowExecution.STATUS_PENDING, WorkflowExecution.STATUS_RUNNING}:
                execution.cancel()
                update_fields.update({"status", "completed_at"})
                status_changed = True

    except Exception:
        logger.exception(
            "Failed to apply legacy workflow transition",
            extra={
                "execution_id": str(getattr(execution, "id", "")),
                "current_status": str(getattr(execution, "status", "")),
                "target_status": target_status,
            },
        )
        return update_fields, status_changed

    return update_fields, status_changed


def _apply_legacy_execution_payload(
    *,
    execution,
    payload: Mapping[str, object],
) -> tuple[set[str], bool]:
    update_fields: set[str] = set()
    status_changed = False

    existing_input_context = execution.input_context if isinstance(execution.input_context, dict) else {}
    input_data = payload.get("input_data")
    if isinstance(input_data, Mapping):
        normalized_input = dict(input_data)
        if str(execution.execution_consumer or "") == "pools":
            normalized_input = _preserve_pool_publication_state_on_legacy_input_merge(
                existing_input_context=existing_input_context,
                incoming_input_context=normalized_input,
            )
        if existing_input_context != normalized_input:
            execution.input_context = normalized_input
            update_fields.add("input_context")

    output_data_raw = payload.get("output_data")
    output_data = dict(output_data_raw) if isinstance(output_data_raw, Mapping) else None
    if output_data is not None and "status" not in payload:
        if (
            not _should_preserve_final_result_on_legacy_update(
                existing_final_result=execution.final_result,
                incoming_output_data=output_data,
            )
            and execution.final_result != output_data
        ):
            execution.final_result = output_data
            update_fields.add("final_result")

    error_message = str(payload.get("error_message") or "").strip()
    if error_message and error_message != execution.error_message:
        execution.error_message = error_message
        update_fields.add("error_message")

    target_status = _normalize_legacy_workflow_status(payload.get("status"))
    transition_update_fields, transition_status_changed = _apply_legacy_status_transition(
        execution=execution,
        target_status=target_status,
        error_message=error_message,
        output_data=output_data,
    )
    update_fields.update(transition_update_fields)
    status_changed = status_changed or transition_status_changed

    # Apply explicit timestamps after FSM transitions so payload can override defaults.
    started_at = _parse_legacy_datetime(payload.get("started_at"))
    if started_at is not None and execution.started_at != started_at:
        execution.started_at = started_at
        update_fields.add("started_at")

    completed_at = _parse_legacy_datetime(payload.get("completed_at"))
    if completed_at is not None and execution.completed_at != completed_at:
        execution.completed_at = completed_at
        update_fields.add("completed_at")

    return update_fields, status_changed


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
    publication_results = _extract_publication_result_payloads(result_payload)
    if not publication_results:
        return None
    return publication_results[0]


def _extract_publication_result_payloads(result_payload: object) -> list[dict[str, object]]:
    def _normalize_candidate(
        candidate: object,
        *,
        projection_key: str = "",
    ) -> dict[str, object] | None:
        if not isinstance(candidate, Mapping):
            return None
        if str(candidate.get("step") or "").strip().lower() == "publication_odata":
            normalized = dict(candidate)
            normalized["_projection_key"] = projection_key
            return normalized
        nested_output = candidate.get("output")
        if isinstance(nested_output, Mapping):
            if str(nested_output.get("step") or "").strip().lower() == "publication_odata":
                normalized = dict(nested_output)
                normalized["_projection_key"] = projection_key
                return normalized
        return None

    if not isinstance(result_payload, Mapping):
        return []

    normalized_results: list[dict[str, object]] = []
    direct = _normalize_candidate(
        result_payload,
        projection_key=str(result_payload.get("node_id") or "").strip(),
    )
    if direct is not None:
        normalized_results.append(direct)

    for container_key in ("node_results", "nodes"):
        container = result_payload.get(container_key)
        if not isinstance(container, Mapping):
            continue
        for node_key, candidate in container.items():
            normalized = _normalize_candidate(
                candidate,
                projection_key=str(node_key or "").strip(),
            )
            if normalized is not None:
                normalized_results.append(normalized)
    return normalized_results


def _normalize_publication_attempt_rows(
    *,
    raw_attempts: object,
    entity_name: str,
    documents_count_by_database: dict[str, int],
    projection_key: str,
    document_entities_by_database: Mapping[str, Mapping[str, str]] | None = None,
) -> list[dict[str, object]]:
    if not isinstance(raw_attempts, list):
        return []

    normalized: list[dict[str, object]] = []
    for raw_index, raw_attempt in enumerate(raw_attempts):
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
        local_attempt_number = _parse_positive_int(raw_attempt.get("attempt_number"), default=1)
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

        resolved_entity_name = _resolve_publication_attempt_entity_name(
            raw_attempt=raw_attempt,
            request_summary=request_summary,
            response_summary=response_summary,
            target_database=target_database,
            fallback_entity_name=entity_name,
            document_entities_by_database=document_entities_by_database,
        )
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
                "attempt_number": local_attempt_number,
                "status": status_value,
                "entity_name": resolved_entity_name,
                "documents_count": documents_count,
                "posted": posted,
                "error_code": error_code,
                "error_message": error_message,
                "http_status": http_status,
                "request_summary": dict(request_summary),
                "response_summary": dict(response_summary),
                "_projection_key": projection_key,
                "_projection_attempt_key": f"{projection_key}:{local_attempt_number}:{raw_index}",
            }
        )
    return normalized


def _resolve_publication_attempt_entity_name(
    *,
    raw_attempt: Mapping[str, object],
    request_summary: Mapping[str, object],
    response_summary: Mapping[str, object],
    target_database: str,
    fallback_entity_name: str,
    document_entities_by_database: Mapping[str, Mapping[str, str]] | None,
) -> str:
    explicit_entity_name = str(raw_attempt.get("entity_name") or "").strip()
    inferred_entity_name = ""
    if target_database and isinstance(document_entities_by_database, Mapping):
        entities_by_key = document_entities_by_database.get(target_database)
        if isinstance(entities_by_key, Mapping):
            inferred_entity_name = _infer_attempt_entity_name_from_document_keys(
                request_summary=request_summary,
                response_summary=response_summary,
                entities_by_key=entities_by_key,
            )
    if inferred_entity_name:
        return inferred_entity_name
    if explicit_entity_name:
        return explicit_entity_name

    return fallback_entity_name


def _infer_attempt_entity_name_from_document_keys(
    *,
    request_summary: Mapping[str, object],
    response_summary: Mapping[str, object],
    entities_by_key: Mapping[str, str],
) -> str:
    candidate_keys = _collect_attempt_document_idempotency_keys(
        request_summary=request_summary,
        response_summary=response_summary,
    )
    if not candidate_keys:
        return ""

    matched_entity_names = {
        str(entities_by_key.get(document_key) or "").strip()
        for document_key in candidate_keys
        if str(entities_by_key.get(document_key) or "").strip()
    }
    if len(matched_entity_names) == 1:
        return next(iter(matched_entity_names))
    return ""


def _collect_attempt_document_idempotency_keys(
    *,
    request_summary: Mapping[str, object],
    response_summary: Mapping[str, object],
) -> list[str]:
    keys: list[str] = []
    for raw_value in (
        request_summary.get("document_idempotency_keys"),
        response_summary.get("successful_document_idempotency_keys"),
    ):
        if not isinstance(raw_value, list):
            continue
        for raw_key in raw_value:
            normalized_key = str(raw_key or "").strip()
            if normalized_key and normalized_key not in keys:
                keys.append(normalized_key)
    return keys


def _collect_document_entities_by_database(
    *,
    input_context: Mapping[str, object] | None,
) -> dict[str, dict[str, str]]:
    if not isinstance(input_context, Mapping):
        return {}
    artifact = input_context.get(POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY)
    if not isinstance(artifact, Mapping):
        return {}
    raw_targets = artifact.get("targets")
    if not isinstance(raw_targets, list):
        return {}

    entities_by_database: dict[str, dict[str, str]] = {}
    for target_raw in raw_targets:
        if not isinstance(target_raw, Mapping):
            continue
        database_id = str(target_raw.get("database_id") or "").strip()
        if not database_id:
            continue
        raw_chains = target_raw.get("chains")
        if not isinstance(raw_chains, list):
            continue
        entities_by_key = entities_by_database.setdefault(database_id, {})
        for chain_raw in raw_chains:
            if not isinstance(chain_raw, Mapping):
                continue
            raw_documents = chain_raw.get("documents")
            if not isinstance(raw_documents, list):
                continue
            for document_raw in raw_documents:
                if not isinstance(document_raw, Mapping):
                    continue
                document_key = str(document_raw.get("idempotency_key") or "").strip()
                entity_name = str(document_raw.get("entity_name") or "").strip()
                if document_key and entity_name:
                    entities_by_key[document_key] = entity_name
    return {database_id: entities for database_id, entities in entities_by_database.items() if entities}


def _synthesize_publication_attempt_rows(
    *,
    target_databases: list[str],
    entity_name: str,
    documents_count_by_database: dict[str, int],
    failed_databases: dict[str, str],
    failed_databases_diagnostics: dict[str, dict[str, object]],
    max_attempts: int,
    projection_key: str,
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
                    "_projection_key": projection_key,
                    "_projection_attempt_key": (
                        f"{projection_key}:synthetic:{database_id}:{attempt_number}"
                    ),
                }
            )
    return synthesized


def _build_publication_projection_identity(
    *,
    execution_id: str,
    database_id: str,
    projection_key: str,
    projection_attempt_key: str,
) -> str:
    raw = "|".join(
        [
            str(execution_id or "").strip(),
            str(database_id or "").strip(),
            str(projection_key or "").strip(),
            str(projection_attempt_key or "").strip(),
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"{WORKFLOW_PROJECTION_IDENTITY_PREFIX}:{execution_id}:{digest}"


def _project_pool_publication_attempts_from_result(*, execution, result_payload: object) -> None:
    from apps.databases.models import Database
    from apps.intercompany_pools.models import (
        PoolPublicationAttempt,
        PoolPublicationAttemptStatus,
        PoolRun,
    )

    if str(execution.execution_consumer or "") != "pools":
        return

    publication_results = _extract_publication_result_payloads(result_payload)
    if not publication_results:
        return

    execution_context = execution.input_context if isinstance(execution.input_context, dict) else {}
    pool_run_id = str(
        publication_results[0].get("pool_run_id")
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
    documents_count_by_database: dict[str, int] = {}
    failed_databases: dict[str, str] = {}
    failed_databases_diagnostics: dict[str, dict[str, object]] = {}
    attempt_rows: list[dict[str, object]] = []
    entity_name = "Document_РеализацияТоваровУслуг"
    max_attempts = 1
    document_entities_by_database = _collect_document_entities_by_database(
        input_context=execution.input_context if isinstance(execution.input_context, Mapping) else None,
    )

    publication_results = sorted(
        publication_results,
        key=lambda item: str(item.get("_projection_key") or ""),
    )

    for publication_result in publication_results:
        raw_targets = publication_result.get("target_databases")
        if isinstance(raw_targets, list):
            for raw_value in raw_targets:
                normalized = str(raw_value or "").strip()
                if normalized and normalized not in target_databases:
                    target_databases.append(normalized)

        raw_documents_count = publication_result.get("documents_count_by_database")
        if isinstance(raw_documents_count, Mapping):
            for raw_database_id, raw_count in raw_documents_count.items():
                database_id = str(raw_database_id or "").strip()
                if not database_id:
                    continue
                documents_count_by_database[database_id] = documents_count_by_database.get(database_id, 0) + _parse_positive_int(
                    raw_count,
                    default=1,
                )
                if database_id not in target_databases:
                    target_databases.append(database_id)

        raw_failed_databases = publication_result.get("failed_databases")
        if isinstance(raw_failed_databases, Mapping):
            for raw_database_id, raw_error in raw_failed_databases.items():
                database_id = str(raw_database_id or "").strip()
                if not database_id:
                    continue
                failed_databases[database_id] = str(raw_error or "").strip()
                if database_id not in target_databases:
                    target_databases.append(database_id)

        raw_failed_diagnostics = publication_result.get("failed_databases_diagnostics")
        if isinstance(raw_failed_diagnostics, Mapping):
            for raw_database_id, raw_diagnostics in raw_failed_diagnostics.items():
                database_id = str(raw_database_id or "").strip()
                if not database_id or not isinstance(raw_diagnostics, Mapping):
                    continue
                failed_databases_diagnostics[database_id] = dict(raw_diagnostics)
                if database_id not in target_databases:
                    target_databases.append(database_id)

        normalized_entity_name = str(publication_result.get("entity_name") or "").strip()
        if normalized_entity_name:
            entity_name = normalized_entity_name
        max_attempts = max(
            max_attempts,
            _parse_positive_int(publication_result.get("max_attempts"), default=1),
        )
        projection_key = str(publication_result.get("_projection_key") or "").strip()

        normalized_attempt_rows = _normalize_publication_attempt_rows(
            raw_attempts=publication_result.get("attempts"),
            entity_name=entity_name,
            documents_count_by_database=documents_count_by_database,
            projection_key=projection_key,
            document_entities_by_database=document_entities_by_database,
        )
        if not normalized_attempt_rows and target_databases:
            normalized_attempt_rows = _synthesize_publication_attempt_rows(
                target_databases=target_databases,
                entity_name=entity_name,
                documents_count_by_database=documents_count_by_database,
                failed_databases=failed_databases,
                failed_databases_diagnostics=failed_databases_diagnostics,
                max_attempts=max_attempts,
                projection_key=projection_key,
            )
        attempt_rows.extend(normalized_attempt_rows)

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
        projected_attempt_rows: list[dict[str, object]] = []
        projection_identities_by_database: dict[str, set[str]] = {}
        for row in attempt_rows:
            database_id = str(row.get("target_database") or "").strip()
            if not database_id:
                continue
            projection_key = str(row.get("_projection_key") or "").strip()
            projection_attempt_key = str(row.get("_projection_attempt_key") or "").strip()
            projection_identity = _build_publication_projection_identity(
                execution_id=str(execution.id),
                database_id=database_id,
                projection_key=projection_key,
                projection_attempt_key=projection_attempt_key,
            )
            projected_row = dict(row)
            projected_row["_projection_identity"] = projection_identity
            projected_attempt_rows.append(projected_row)
            projection_identities_by_database.setdefault(database_id, set()).add(projection_identity)

        projected_database_ids = sorted(
            {
                str(row.get("target_database") or "").strip()
                for row in projected_attempt_rows
                if str(row.get("target_database") or "").strip() in databases
            }
        )
        existing_attempts = list(
            PoolPublicationAttempt.objects.filter(
                run=run,
                target_database_id__in=projected_database_ids,
            )
        )
        stale_attempt_ids: list[str] = []
        existing_attempts_by_identity: dict[tuple[str, str], PoolPublicationAttempt] = {}
        next_attempt_number_by_database: dict[str, int] = {}
        current_execution_identity_prefix = (
            f"{WORKFLOW_PROJECTION_IDENTITY_PREFIX}:{str(execution.id)}:"
        )
        for attempt in existing_attempts:
            database_id = str(attempt.target_database_id)
            next_attempt_number_by_database[database_id] = max(
                next_attempt_number_by_database.get(database_id, 0),
                int(attempt.attempt_number or 0),
            )
            if attempt.identity_strategy != WORKFLOW_PROJECTION_IDENTITY_STRATEGY:
                continue
            identity = str(attempt.external_document_identity or "").strip()
            if not identity.startswith(current_execution_identity_prefix):
                continue
            if identity in projection_identities_by_database.get(database_id, set()):
                existing_attempts_by_identity[(database_id, identity)] = attempt
                next_attempt_number_by_database[database_id] = max(
                    next_attempt_number_by_database.get(database_id, 0),
                    int(attempt.attempt_number or 0),
                )
                continue
            stale_attempt_ids.append(str(attempt.id))

        if stale_attempt_ids:
            PoolPublicationAttempt.objects.filter(id__in=stale_attempt_ids).delete()

        for database_id, identities in projection_identities_by_database.items():
            preserved_attempt_numbers = {
                int(existing_attempts_by_identity[(database_id, identity)].attempt_number or 0)
                for identity in identities
                if (database_id, identity) in existing_attempts_by_identity
            }
            next_attempt_number_by_database[database_id] = max(
                (
                    int(attempt.attempt_number or 0)
                    for attempt in existing_attempts
                    if str(attempt.target_database_id) == database_id
                    and str(attempt.id) not in stale_attempt_ids
                    and int(attempt.attempt_number or 0) not in preserved_attempt_numbers
                ),
                default=0,
            )

        projection_timestamp = timezone.now()
        for row in projected_attempt_rows:
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

            status_value = str(row.get("status") or "").strip().lower()
            if status_value not in {
                PoolPublicationAttemptStatus.SUCCESS,
                PoolPublicationAttemptStatus.FAILED,
            }:
                status_value = PoolPublicationAttemptStatus.FAILED
            projection_identity = str(row.get("_projection_identity") or "").strip()
            existing_attempt = existing_attempts_by_identity.get((database_id, projection_identity))
            if existing_attempt is not None:
                attempt_number = int(existing_attempt.attempt_number or 0)
            else:
                attempt_number = next_attempt_number_by_database.get(database_id, 0) + 1
                next_attempt_number_by_database[database_id] = attempt_number

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
                    "external_document_identity": projection_identity,
                    "identity_strategy": WORKFLOW_PROJECTION_IDENTITY_STRATEGY,
                    "posted": bool(row.get("posted")),
                    "http_status": row.get("http_status"),
                    "error_code": str(row.get("error_code") or "").strip(),
                    "error_message": str(row.get("error_message") or "").strip(),
                    "request_summary": dict(row.get("request_summary") or {}),
                    "response_summary": dict(row.get("response_summary") or {}),
                    "started_at": projection_timestamp,
                    "finished_at": projection_timestamp,
                },
            )

    failed_target_ids = {
        str(database_id or "").strip()
        for database_id in failed_databases.keys()
        if str(database_id or "").strip()
    }
    failed_target_ids.update(
        str(row.get("target_database") or "").strip()
        for row in attempt_rows
        if str(row.get("status") or "").strip().lower() == PoolPublicationAttemptStatus.FAILED
    )
    failed_target_ids.discard("")
    total_targets = len({database_id for database_id in target_databases if database_id})
    failed_targets = len(failed_target_ids)
    succeeded_targets = max(total_targets - failed_targets, 0)
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

    _project_pool_publication_verification_from_result(
        execution=execution,
        publication_results=publication_results,
    )


def _project_pool_batch_publication_attempts_from_result(*, execution, result_payload: object) -> None:
    from apps.databases.models import Database
    from apps.intercompany_pools.models import (
        PoolBatch,
        PoolBatchPublicationAttempt,
        PoolBatchPublicationAttemptStatus,
        PoolBatchSettlementStatus,
    )

    if str(execution.execution_consumer or "") != "pools":
        return

    publication_results = _extract_publication_result_payloads(result_payload)
    if not publication_results:
        return

    execution_context = execution.input_context if isinstance(execution.input_context, dict) else {}
    pool_batch_id = str(
        publication_results[0].get("pool_batch_id")
        or execution_context.get("pool_batch_id")
        or ""
    ).strip()
    if not pool_batch_id:
        return

    try:
        pool_batch_uuid = uuid.UUID(pool_batch_id)
    except ValueError:
        logger.warning(
            "Skipping batch publication projection: invalid pool batch id",
            extra={"execution_id": str(execution.id), "pool_batch_id": pool_batch_id},
        )
        return

    batch = PoolBatch.objects.select_related("settlement").filter(id=pool_batch_uuid).first()
    if batch is None:
        logger.warning(
            "Skipping batch publication projection: pool batch is missing",
            extra={"execution_id": str(execution.id), "pool_batch_id": pool_batch_id},
        )
        return

    execution_tenant_id = str(getattr(execution, "tenant_id", "") or "").strip()
    if execution_tenant_id and str(batch.tenant_id) != execution_tenant_id:
        logger.warning(
            "Skipping batch publication projection due to tenant mismatch",
            extra={
                "execution_id": str(execution.id),
                "pool_batch_id": str(batch.id),
                "batch_tenant_id": str(batch.tenant_id),
                "execution_tenant_id": execution_tenant_id,
            },
        )
        return

    target_databases: list[str] = []
    documents_count_by_database: dict[str, int] = {}
    failed_databases: dict[str, str] = {}
    failed_databases_diagnostics: dict[str, dict[str, object]] = {}
    attempt_rows: list[dict[str, object]] = []
    entity_name = "Document_РеализацияТоваровУслуг"
    max_attempts = 1
    document_entities_by_database = _collect_document_entities_by_database(
        input_context=execution.input_context if isinstance(execution.input_context, Mapping) else None,
    )

    publication_results = sorted(
        publication_results,
        key=lambda item: str(item.get("_projection_key") or ""),
    )

    for publication_result in publication_results:
        raw_targets = publication_result.get("target_databases")
        if isinstance(raw_targets, list):
            for raw_value in raw_targets:
                normalized = str(raw_value or "").strip()
                if normalized and normalized not in target_databases:
                    target_databases.append(normalized)

        raw_documents_count = publication_result.get("documents_count_by_database")
        if isinstance(raw_documents_count, Mapping):
            for raw_database_id, raw_count in raw_documents_count.items():
                database_id = str(raw_database_id or "").strip()
                if not database_id:
                    continue
                documents_count_by_database[database_id] = documents_count_by_database.get(database_id, 0) + _parse_positive_int(
                    raw_count,
                    default=1,
                )
                if database_id not in target_databases:
                    target_databases.append(database_id)

        raw_failed_databases = publication_result.get("failed_databases")
        if isinstance(raw_failed_databases, Mapping):
            for raw_database_id, raw_error in raw_failed_databases.items():
                database_id = str(raw_database_id or "").strip()
                if not database_id:
                    continue
                failed_databases[database_id] = str(raw_error or "").strip()
                if database_id not in target_databases:
                    target_databases.append(database_id)

        raw_failed_diagnostics = publication_result.get("failed_databases_diagnostics")
        if isinstance(raw_failed_diagnostics, Mapping):
            for raw_database_id, raw_diagnostics in raw_failed_diagnostics.items():
                database_id = str(raw_database_id or "").strip()
                if not database_id or not isinstance(raw_diagnostics, Mapping):
                    continue
                failed_databases_diagnostics[database_id] = dict(raw_diagnostics)
                if database_id not in target_databases:
                    target_databases.append(database_id)

        normalized_entity_name = str(publication_result.get("entity_name") or "").strip()
        if normalized_entity_name:
            entity_name = normalized_entity_name
        max_attempts = max(
            max_attempts,
            _parse_positive_int(publication_result.get("max_attempts"), default=1),
        )
        projection_key = str(publication_result.get("_projection_key") or "").strip()

        normalized_attempt_rows = _normalize_publication_attempt_rows(
            raw_attempts=publication_result.get("attempts"),
            entity_name=entity_name,
            documents_count_by_database=documents_count_by_database,
            projection_key=projection_key,
            document_entities_by_database=document_entities_by_database,
        )
        if not normalized_attempt_rows and target_databases:
            normalized_attempt_rows = _synthesize_publication_attempt_rows(
                target_databases=target_databases,
                entity_name=entity_name,
                documents_count_by_database=documents_count_by_database,
                failed_databases=failed_databases,
                failed_databases_diagnostics=failed_databases_diagnostics,
                max_attempts=max_attempts,
                projection_key=projection_key,
            )
        attempt_rows.extend(normalized_attempt_rows)

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
                "Skipping batch publication projection for invalid database id",
                extra={
                    "execution_id": str(execution.id),
                    "pool_batch_id": str(batch.id),
                    "target_database_id": database_id,
                },
            )

    databases = {
        str(db.id): db
        for db in Database.objects.filter(
            id__in=list(valid_database_ids),
            tenant=batch.tenant,
        )
    }

    if attempt_rows:
        projected_attempt_rows: list[dict[str, object]] = []
        projection_identities_by_database: dict[str, set[str]] = {}
        for row in attempt_rows:
            database_id = str(row.get("target_database") or "").strip()
            if not database_id:
                continue
            projection_key = str(row.get("_projection_key") or "").strip()
            projection_attempt_key = str(row.get("_projection_attempt_key") or "").strip()
            projection_identity = _build_publication_projection_identity(
                execution_id=str(execution.id),
                database_id=database_id,
                projection_key=projection_key,
                projection_attempt_key=projection_attempt_key,
            )
            projected_row = dict(row)
            projected_row["_projection_identity"] = projection_identity
            projected_attempt_rows.append(projected_row)
            projection_identities_by_database.setdefault(database_id, set()).add(projection_identity)

        projected_database_ids = sorted(
            {
                str(row.get("target_database") or "").strip()
                for row in projected_attempt_rows
                if str(row.get("target_database") or "").strip() in databases
            }
        )
        existing_attempts = list(
            PoolBatchPublicationAttempt.objects.filter(
                batch=batch,
                target_database_id__in=projected_database_ids,
            )
        )
        stale_attempt_ids: list[str] = []
        existing_attempts_by_identity: dict[tuple[str, str], PoolBatchPublicationAttempt] = {}
        next_attempt_number_by_database: dict[str, int] = {}
        current_execution_identity_prefix = (
            f"{WORKFLOW_PROJECTION_IDENTITY_PREFIX}:{str(execution.id)}:"
        )
        for attempt in existing_attempts:
            database_id = str(attempt.target_database_id)
            next_attempt_number_by_database[database_id] = max(
                next_attempt_number_by_database.get(database_id, 0),
                int(attempt.attempt_number or 0),
            )
            if attempt.identity_strategy != WORKFLOW_PROJECTION_IDENTITY_STRATEGY:
                continue
            identity = str(attempt.external_document_identity or "").strip()
            if not identity.startswith(current_execution_identity_prefix):
                continue
            if identity in projection_identities_by_database.get(database_id, set()):
                existing_attempts_by_identity[(database_id, identity)] = attempt
                continue
            stale_attempt_ids.append(str(attempt.id))

        if stale_attempt_ids:
            PoolBatchPublicationAttempt.objects.filter(id__in=stale_attempt_ids).delete()

        for database_id, identities in projection_identities_by_database.items():
            preserved_attempt_numbers = {
                int(existing_attempts_by_identity[(database_id, identity)].attempt_number or 0)
                for identity in identities
                if (database_id, identity) in existing_attempts_by_identity
            }
            next_attempt_number_by_database[database_id] = max(
                (
                    int(attempt.attempt_number or 0)
                    for attempt in existing_attempts
                    if str(attempt.target_database_id) == database_id
                    and str(attempt.id) not in stale_attempt_ids
                    and int(attempt.attempt_number or 0) not in preserved_attempt_numbers
                ),
                default=0,
            )

        projection_timestamp = timezone.now()
        for row in projected_attempt_rows:
            database_id = str(row.get("target_database") or "").strip()
            target_database = databases.get(database_id)
            if target_database is None:
                logger.warning(
                    "Skipping batch publication attempt projection: database is missing",
                    extra={
                        "execution_id": str(execution.id),
                        "pool_batch_id": str(batch.id),
                        "target_database_id": database_id,
                    },
                )
                continue

            status_value = str(row.get("status") or "").strip().lower()
            if status_value not in {
                PoolBatchPublicationAttemptStatus.SUCCESS,
                PoolBatchPublicationAttemptStatus.FAILED,
            }:
                status_value = PoolBatchPublicationAttemptStatus.FAILED
            projection_identity = str(row.get("_projection_identity") or "").strip()
            existing_attempt = existing_attempts_by_identity.get((database_id, projection_identity))
            if existing_attempt is not None:
                attempt_number = int(existing_attempt.attempt_number or 0)
            else:
                attempt_number = next_attempt_number_by_database.get(database_id, 0) + 1
                next_attempt_number_by_database[database_id] = attempt_number

            PoolBatchPublicationAttempt.objects.update_or_create(
                batch=batch,
                target_database=target_database,
                attempt_number=attempt_number,
                defaults={
                    "tenant": batch.tenant,
                    "status": status_value,
                    "entity_name": str(row.get("entity_name") or entity_name).strip() or entity_name,
                    "documents_count": _parse_positive_int(
                        row.get("documents_count"),
                        default=1,
                    ),
                    "external_document_identity": projection_identity,
                    "identity_strategy": WORKFLOW_PROJECTION_IDENTITY_STRATEGY,
                    "posted": bool(row.get("posted")),
                    "http_status": row.get("http_status"),
                    "error_code": str(row.get("error_code") or "").strip(),
                    "error_message": str(row.get("error_message") or "").strip(),
                    "request_summary": dict(row.get("request_summary") or {}),
                    "response_summary": dict(row.get("response_summary") or {}),
                    "started_at": projection_timestamp,
                    "finished_at": projection_timestamp,
                },
            )
    else:
        projection_timestamp = timezone.now()

    failed_target_ids = {
        str(database_id or "").strip()
        for database_id in failed_databases.keys()
        if str(database_id or "").strip()
    }
    failed_target_ids.update(
        str(row.get("target_database") or "").strip()
        for row in attempt_rows
        if str(row.get("status") or "").strip().lower() == PoolBatchPublicationAttemptStatus.FAILED
    )
    failed_target_ids.discard("")
    total_targets = len({database_id for database_id in target_databases if database_id})
    failed_targets = len(failed_target_ids)
    succeeded_targets = max(total_targets - failed_targets, 0)
    batch.publication_summary = {
        "total_targets": total_targets,
        "succeeded_targets": succeeded_targets,
        "failed_targets": failed_targets,
        "max_attempts": max_attempts,
    }
    batch.workflow_execution_id = execution.id
    batch.workflow_status = str(execution.status or "").strip()
    batch.last_error_code = ""
    batch.last_error = ""
    batch.save(
        update_fields=[
            "workflow_execution_id",
            "workflow_status",
            "publication_summary",
            "last_error_code",
            "last_error",
            "updated_at",
        ]
    )

    settlement = getattr(batch, "settlement", None)
    if settlement is not None:
        settlement_summary = dict(settlement.summary or {})
        settlement_summary["publication_summary"] = dict(batch.publication_summary)
        settlement.summary = settlement_summary
        settlement.freshness_at = projection_timestamp
        settlement_update_fields = ["summary", "freshness_at", "updated_at"]
        if failed_targets > 0:
            settlement.status = PoolBatchSettlementStatus.ATTENTION_REQUIRED
            settlement_update_fields.append("status")
        elif total_targets > 0 and succeeded_targets == total_targets:
            settlement.status = PoolBatchSettlementStatus.CLOSED
            settlement.outgoing_amount = settlement.incoming_amount
            settlement.open_balance = Decimal("0.00")
            settlement_update_fields.extend(["status", "outgoing_amount", "open_balance"])
        settlement.save(update_fields=settlement_update_fields)

    current_publication_state = str(
        execution_context.get("publication_step_state") or ""
    ).strip().lower()
    if current_publication_state != PUBLICATION_STEP_STATE_COMPLETED:
        updated_context = dict(execution_context)
        updated_context["publication_step_state"] = PUBLICATION_STEP_STATE_COMPLETED
        execution.input_context = updated_context


def _project_pool_publication_verification_from_result(
    *,
    execution,
    publication_results: list[dict[str, object]],
) -> None:
    if str(execution.execution_consumer or "") != "pools":
        return

    execution_context = execution.input_context if isinstance(execution.input_context, dict) else {}
    verification = verify_published_documents(
        tenant_id=str(getattr(execution, "tenant_id", "") or ""),
        document_plan_artifact=(
            execution_context.get("pool_runtime_document_plan_artifact")
            if isinstance(execution_context.get("pool_runtime_document_plan_artifact"), Mapping)
            else None
        ),
        publication_results=publication_results,
    )
    updated_context = dict(execution_context)
    updated_context[POOL_RUNTIME_VERIFICATION_CONTEXT_KEY] = verification
    execution.input_context = updated_context


def _reconcile_pool_publication_step_state_from_persisted_attempts(*, execution) -> bool:
    from apps.intercompany_pools.models import PoolPublicationAttempt, PoolRun

    if str(execution.execution_consumer or "") != "pools":
        return False

    execution_context = execution.input_context if isinstance(execution.input_context, dict) else {}
    if not execution_context:
        return False

    current_publication_state = str(
        execution_context.get("publication_step_state") or ""
    ).strip().lower()
    if current_publication_state == PUBLICATION_STEP_STATE_COMPLETED:
        return False

    approval_state = str(execution_context.get("approval_state") or "").strip().lower()
    if approval_state not in {APPROVAL_STATE_APPROVED, APPROVAL_STATE_NOT_REQUIRED}:
        return False

    pool_run_id = str(execution_context.get("pool_run_id") or "").strip()
    if not pool_run_id:
        return False
    try:
        pool_run_uuid = uuid.UUID(pool_run_id)
    except ValueError:
        return False

    run = PoolRun.objects.filter(id=pool_run_uuid).first()
    if run is None:
        return False

    execution_tenant_id = str(getattr(execution, "tenant_id", "") or "").strip()
    if execution_tenant_id and str(run.tenant_id) != execution_tenant_id:
        return False

    publication_summary = run.publication_summary if isinstance(run.publication_summary, dict) else {}
    has_publication_summary = bool(publication_summary)
    has_publication_attempts = PoolPublicationAttempt.objects.filter(run=run).exists()
    if not has_publication_summary and not has_publication_attempts:
        return False

    updated_context = dict(execution_context)
    updated_context["publication_step_state"] = PUBLICATION_STEP_STATE_COMPLETED
    execution.input_context = updated_context
    return True


def _reconcile_pool_batch_publication_step_state_from_persisted_attempts(*, execution) -> bool:
    from apps.intercompany_pools.models import PoolBatch, PoolBatchPublicationAttempt

    if str(execution.execution_consumer or "") != "pools":
        return False

    execution_context = execution.input_context if isinstance(execution.input_context, dict) else {}
    if not execution_context:
        return False

    current_publication_state = str(
        execution_context.get("publication_step_state") or ""
    ).strip().lower()
    if current_publication_state == PUBLICATION_STEP_STATE_COMPLETED:
        return False

    approval_state = str(execution_context.get("approval_state") or "").strip().lower()
    if approval_state not in {APPROVAL_STATE_APPROVED, APPROVAL_STATE_NOT_REQUIRED}:
        return False

    pool_batch_id = str(execution_context.get("pool_batch_id") or "").strip()
    if not pool_batch_id:
        return False
    try:
        pool_batch_uuid = uuid.UUID(pool_batch_id)
    except ValueError:
        return False

    batch = PoolBatch.objects.filter(id=pool_batch_uuid).first()
    if batch is None:
        return False

    execution_tenant_id = str(getattr(execution, "tenant_id", "") or "").strip()
    if execution_tenant_id and str(batch.tenant_id) != execution_tenant_id:
        return False

    publication_summary = batch.publication_summary if isinstance(batch.publication_summary, dict) else {}
    has_publication_summary = bool(publication_summary)
    has_publication_attempts = PoolBatchPublicationAttempt.objects.filter(batch=batch).exists()
    if not has_publication_summary and not has_publication_attempts:
        return False

    updated_context = dict(execution_context)
    updated_context["publication_step_state"] = PUBLICATION_STEP_STATE_COMPLETED
    execution.input_context = updated_context
    return True


def _sync_pool_run_terminal_state_from_publication_projection(*, execution) -> None:
    from apps.intercompany_pools.models import PoolRun

    if str(execution.execution_consumer or "") != "pools":
        return

    execution_context = execution.input_context if isinstance(execution.input_context, dict) else {}
    pool_run_id = str(execution_context.get("pool_run_id") or "").strip()
    if not pool_run_id:
        return

    try:
        pool_run_uuid = uuid.UUID(pool_run_id)
    except ValueError:
        return

    run = PoolRun.objects.filter(id=pool_run_uuid).first()
    if run is None:
        return

    execution_tenant_id = str(getattr(execution, "tenant_id", "") or "").strip()
    if execution_tenant_id and str(run.tenant_id) != execution_tenant_id:
        return

    publication_summary = run.publication_summary if isinstance(run.publication_summary, dict) else {}
    if not publication_summary:
        return

    total_targets = _parse_non_negative_int(publication_summary.get("total_targets"), default=0)
    succeeded_targets = _parse_non_negative_int(publication_summary.get("succeeded_targets"), default=0)
    failed_targets = _parse_non_negative_int(publication_summary.get("failed_targets"), default=0)

    update_fields: set[str] = {"updated_at"}
    if run.workflow_execution_id != execution.id:
        run.workflow_execution_id = execution.id
        update_fields.add("workflow_execution_id")
    if run.execution_backend != "workflow_core":
        run.execution_backend = "workflow_core"
        update_fields.add("execution_backend")
    if run.workflow_status != execution.status:
        run.workflow_status = execution.status
        update_fields.add("workflow_status")

    approved_at = _parse_legacy_datetime(execution_context.get("approved_at"))
    if approved_at is not None and run.publication_confirmed_at is None:
        run.publication_confirmed_at = approved_at
        update_fields.add("publication_confirmed_at")

    target_status: str | None = None
    failure_message = ""
    if total_targets > 0:
        if failed_targets > 0 and succeeded_targets <= 0:
            target_status = PoolRun.STATUS_FAILED
            failure_message = "Publication failed for all target databases."
        elif failed_targets > 0:
            target_status = PoolRun.STATUS_PARTIAL_SUCCESS
        elif succeeded_targets > 0:
            target_status = PoolRun.STATUS_PUBLISHED

    if target_status in {
        PoolRun.STATUS_PUBLISHED,
        PoolRun.STATUS_PARTIAL_SUCCESS,
        PoolRun.STATUS_FAILED,
    }:
        if run.status == PoolRun.STATUS_VALIDATED and run._can_start_publishing():
            run.start_publishing()
            update_fields.update({"status", "publishing_started_at"})
        elif (
            run.status in {PoolRun.STATUS_PARTIAL_SUCCESS, PoolRun.STATUS_FAILED}
            and target_status != run.status
            and run._can_start_publishing()
        ):
            run.restart_publishing()
            update_fields.update({"status", "publishing_started_at", "completed_at", "last_error"})

        if target_status == PoolRun.STATUS_PUBLISHED:
            if run.status == PoolRun.STATUS_PUBLISHING:
                run.mark_published(summary=publication_summary)
                update_fields.update({"status", "completed_at", "publication_summary"})
            elif run.status == PoolRun.STATUS_PUBLISHED:
                run.publication_summary = publication_summary
                update_fields.add("publication_summary")
                if run.completed_at is None:
                    run.completed_at = timezone.now()
                    update_fields.add("completed_at")
        elif target_status == PoolRun.STATUS_PARTIAL_SUCCESS:
            if run.status == PoolRun.STATUS_PUBLISHING:
                run.mark_partial_success(summary=publication_summary)
                update_fields.update({"status", "completed_at", "publication_summary"})
            elif run.status == PoolRun.STATUS_PARTIAL_SUCCESS:
                run.publication_summary = publication_summary
                update_fields.add("publication_summary")
                if run.completed_at is None:
                    run.completed_at = timezone.now()
                    update_fields.add("completed_at")
        elif run.status in {
            PoolRun.STATUS_DRAFT,
            PoolRun.STATUS_VALIDATED,
            PoolRun.STATUS_PUBLISHING,
        }:
            run.mark_failed(error=failure_message, summary=publication_summary)
            update_fields.update({"status", "completed_at", "last_error", "publication_summary"})
        elif run.status == PoolRun.STATUS_FAILED:
            run.publication_summary = publication_summary
            run.last_error = failure_message
            update_fields.update({"publication_summary", "last_error"})
            if run.completed_at is None:
                run.completed_at = timezone.now()
                update_fields.add("completed_at")

    if len(update_fields) > 1:
        run.save(update_fields=sorted(update_fields))


def _sync_pool_batch_workflow_state_from_execution(*, execution) -> None:
    from apps.intercompany_pools.models import PoolBatch, PoolBatchSettlementStatus

    if str(execution.execution_consumer or "") != "pools":
        return

    execution_context = execution.input_context if isinstance(execution.input_context, dict) else {}
    pool_batch_id = str(execution_context.get("pool_batch_id") or "").strip()
    if not pool_batch_id:
        return

    try:
        pool_batch_uuid = uuid.UUID(pool_batch_id)
    except ValueError:
        return

    batch = PoolBatch.objects.select_related("settlement").filter(id=pool_batch_uuid).first()
    if batch is None:
        return

    execution_tenant_id = str(getattr(execution, "tenant_id", "") or "").strip()
    if execution_tenant_id and str(batch.tenant_id) != execution_tenant_id:
        return

    update_fields: set[str] = set()
    if batch.workflow_execution_id != execution.id:
        batch.workflow_execution_id = execution.id
        update_fields.add("workflow_execution_id")

    normalized_workflow_status = str(execution.status or "").strip()
    if batch.workflow_status != normalized_workflow_status:
        batch.workflow_status = normalized_workflow_status
        update_fields.add("workflow_status")

    next_error_code = ""
    next_error_message = ""
    if normalized_workflow_status == "failed":
        next_error_code = str(getattr(execution, "error_code", "") or "").strip()
        next_error_message = str(getattr(execution, "error_message", "") or "").strip()
    if batch.last_error_code != next_error_code:
        batch.last_error_code = next_error_code
        update_fields.add("last_error_code")
    if batch.last_error != next_error_message:
        batch.last_error = next_error_message
        update_fields.add("last_error")

    if update_fields:
        update_fields.add("updated_at")
        batch.save(update_fields=sorted(update_fields))

    if normalized_workflow_status == "failed":
        settlement = getattr(batch, "settlement", None)
        if settlement is not None and settlement.status != PoolBatchSettlementStatus.ATTENTION_REQUIRED:
            settlement.status = PoolBatchSettlementStatus.ATTENTION_REQUIRED
            settlement.save(update_fields=["status", "updated_at"])


def _sync_pool_factual_projection_for_execution_update(*, execution, result_payload=None) -> None:
    from apps.intercompany_pools.factual_result_projection import (
        mark_pool_factual_execution_failed,
        project_pool_factual_result_from_execution,
        sync_pool_factual_checkpoint_state_from_execution,
    )
    from apps.templates.workflow.models import WorkflowExecution

    sync_pool_factual_checkpoint_state_from_execution(execution=execution)

    if execution.status == WorkflowExecution.STATUS_COMPLETED:
        project_pool_factual_result_from_execution(
            execution=execution,
            result_payload=result_payload or execution.final_result or {},
        )
    elif execution.status == WorkflowExecution.STATUS_FAILED:
        mark_pool_factual_execution_failed(execution=execution)


def _reconcile_pool_publication_projection_for_execution_update(*, execution) -> bool:
    from apps.templates.workflow.models import WorkflowExecution

    previous_input_context = (
        dict(execution.input_context)
        if isinstance(execution.input_context, dict)
        else {}
    )

    publication_state_reconciled = False
    if execution.status == WorkflowExecution.STATUS_COMPLETED:
        current_publication_step_state = str(
            previous_input_context.get("publication_step_state") or ""
        ).strip().lower()
        should_project_publication = (
            _extract_publication_result_payload(execution.final_result or {}) is not None
            and current_publication_step_state != PUBLICATION_STEP_STATE_COMPLETED
        )
        if should_project_publication:
            _project_pool_publication_attempts_from_result(
                execution=execution,
                result_payload=execution.final_result or {},
            )
            _project_pool_batch_publication_attempts_from_result(
                execution=execution,
                result_payload=execution.final_result or {},
            )
            publication_state_reconciled = True
        else:
            publication_state_reconciled = _reconcile_pool_publication_step_state_from_persisted_attempts(
                execution=execution,
            )
            publication_state_reconciled = (
                _reconcile_pool_batch_publication_step_state_from_persisted_attempts(
                    execution=execution,
                )
                or publication_state_reconciled
            )
        _sync_pool_run_terminal_state_from_publication_projection(
            execution=execution,
        )
        _sync_pool_batch_workflow_state_from_execution(
            execution=execution,
        )
        _sync_pool_factual_projection_for_execution_update(
            execution=execution,
        )
    else:
        publication_state_reconciled = _reconcile_pool_publication_step_state_from_persisted_attempts(
            execution=execution,
        )
        publication_state_reconciled = (
            _reconcile_pool_batch_publication_step_state_from_persisted_attempts(
                execution=execution,
            )
            or publication_state_reconciled
        )
        _sync_pool_batch_workflow_state_from_execution(
            execution=execution,
        )
        _sync_pool_factual_projection_for_execution_update(
            execution=execution,
        )

    next_input_context = (
        dict(execution.input_context)
        if isinstance(execution.input_context, dict)
        else {}
    )
    return publication_state_reconciled and next_input_context != previous_input_context


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
@api_view(["GET", "POST"])
@permission_classes([IsInternalService])
def legacy_workflow_executions_collection(request):
    """
    Legacy compatibility endpoint for worker history client.

    Supports:
      - POST /api/v2/internal/workflow-executions/
      - GET /api/v2/internal/workflow-executions/
    """
    from apps.templates.workflow.models import WorkflowExecution

    if request.method == "GET":
        limit = _parse_non_negative_int(request.query_params.get("limit"), default=50)
        if limit <= 0:
            limit = 50
        limit = min(limit, 200)
        offset = _parse_non_negative_int(request.query_params.get("offset"), default=0)

        queryset = WorkflowExecution.objects.select_related("workflow_template").order_by("-started_at", "-id")

        raw_workflow_id = str(request.query_params.get("workflow_id") or "").strip()
        if raw_workflow_id:
            try:
                workflow_uuid = uuid.UUID(raw_workflow_id)
            except (TypeError, ValueError, AttributeError):
                return Response({"executions": [], "total": 0, "limit": limit, "offset": offset})
            queryset = queryset.filter(workflow_template_id=workflow_uuid)

        status_filter = _normalize_legacy_workflow_status(request.query_params.get("status"))
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        total = queryset.count()
        executions = [
            _serialize_legacy_workflow_execution_record(execution=execution)
            for execution in queryset[offset:offset + limit]
        ]
        return Response(
            {
                "executions": executions,
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )

    payload = request.data if isinstance(request.data, Mapping) else {}
    raw_execution_id = payload.get("id") or payload.get("execution_id")
    try:
        execution_uuid = uuid.UUID(str(raw_execution_id))
    except (TypeError, ValueError, AttributeError):
        return Response(
            {"success": False, "error": "id must be a valid UUID"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    execution = WorkflowExecution.objects.select_related("workflow_template").filter(id=execution_uuid).first()
    if execution is None:
        return Response(
            {
                "success": True,
                "id": str(execution_uuid),
                "persisted": False,
            }
        )

    update_fields, status_changed = _apply_legacy_execution_payload(execution=execution, payload=payload)
    publication_state_reconciled = _reconcile_pool_publication_projection_for_execution_update(
        execution=execution,
    )
    if publication_state_reconciled:
        update_fields.add("input_context")
    if update_fields:
        execution.save(update_fields=sorted(update_fields))
        if status_changed:
            _sync_workflow_root_projection_from_execution(execution=execution)

    return Response(
        {
            "success": True,
            "id": str(execution.id),
            "persisted": True,
            "status": execution.status,
        }
    )


@exclude_schema
@api_view(["GET", "PATCH"])
@permission_classes([IsInternalService])
def legacy_workflow_execution_detail(request, execution_id):
    """
    Legacy compatibility endpoint for worker history client.

    Supports:
      - GET /api/v2/internal/workflow-executions/<execution_id>/
      - PATCH /api/v2/internal/workflow-executions/<execution_id>/
    """
    from apps.templates.workflow.models import WorkflowExecution

    execution = WorkflowExecution.objects.select_related("workflow_template").filter(id=execution_id).first()

    if request.method == "GET":
        if execution is None:
            return Response({"success": False, "error": "Workflow execution not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize_legacy_workflow_execution_record(execution=execution))

    if execution is None:
        return Response(
            {
                "success": True,
                "id": str(execution_id),
                "persisted": False,
            }
        )

    payload = request.data if isinstance(request.data, Mapping) else {}
    update_fields, status_changed = _apply_legacy_execution_payload(execution=execution, payload=payload)
    publication_state_reconciled = _reconcile_pool_publication_projection_for_execution_update(
        execution=execution,
    )
    if publication_state_reconciled:
        update_fields.add("input_context")
    if update_fields:
        execution.save(update_fields=sorted(update_fields))
        if status_changed:
            _sync_workflow_root_projection_from_execution(execution=execution)

    return Response(
        {
            "success": True,
            "id": str(execution.id),
            "persisted": True,
            "status": execution.status,
        }
    )


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def legacy_workflow_transitions_collection(request):
    """
    Legacy compatibility endpoint for worker history client.

    Supports:
      - POST /api/v2/internal/workflow-transitions/
    """
    from apps.templates.workflow.models import WorkflowExecution

    payload = request.data if isinstance(request.data, Mapping) else {}
    raw_execution_id = payload.get("execution_id")
    try:
        execution_uuid = uuid.UUID(str(raw_execution_id))
    except (TypeError, ValueError, AttributeError):
        return Response(
            {"success": False, "error": "execution_id must be a valid UUID"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    execution = WorkflowExecution.objects.select_related("workflow_template").filter(id=execution_uuid).first()
    if execution is None:
        return Response(
            {
                "success": True,
                "execution_id": str(execution_uuid),
                "persisted": False,
            }
        )

    target_status = _normalize_legacy_workflow_status(payload.get("to_status") or payload.get("status"))
    update_fields, status_changed = _apply_legacy_status_transition(
        execution=execution,
        target_status=target_status,
        error_message=str(payload.get("message") or "").strip(),
        output_data=None,
    )
    publication_state_reconciled = _reconcile_pool_publication_projection_for_execution_update(
        execution=execution,
    )
    if publication_state_reconciled:
        update_fields.add("input_context")
    if update_fields:
        execution.save(update_fields=sorted(update_fields))
        if status_changed:
            _sync_workflow_root_projection_from_execution(execution=execution)

    return Response(
        {
            "success": True,
            "execution_id": str(execution.id),
            "persisted": True,
            "status": execution.status,
        }
    )


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
        update_fields: list[str] = []
        if target_status == WorkflowExecution.STATUS_FAILED:
            if error_message and error_message != execution.error_message:
                execution.error_message = error_message
                update_fields.append("error_message")
            if error_code_provided and error_code != execution.error_code:
                execution.error_code = error_code
                update_fields.append("error_code")
            if error_details_provided and error_details != execution.error_details:
                execution.error_details = error_details
                update_fields.append("error_details")
        elif target_status == WorkflowExecution.STATUS_COMPLETED:
            previous_input_context = (
                dict(execution.input_context)
                if isinstance(execution.input_context, dict)
                else {}
            )
            current_publication_step_state = str(
                previous_input_context.get("publication_step_state") or ""
            ).strip().lower()
            should_project_publication = (
                _extract_publication_result_payload(result_payload) is not None
                and current_publication_step_state != PUBLICATION_STEP_STATE_COMPLETED
            )
            publication_state_reconciled = False

            if result_payload and result_payload != (execution.final_result or {}):
                execution.final_result = result_payload
                update_fields.append("final_result")

            if should_project_publication:
                _project_pool_publication_attempts_from_result(
                    execution=execution,
                    result_payload=result_payload,
                )
                _project_pool_batch_publication_attempts_from_result(
                    execution=execution,
                    result_payload=result_payload,
                )
                publication_state_reconciled = True
            else:
                publication_state_reconciled = _reconcile_pool_publication_step_state_from_persisted_attempts(
                    execution=execution,
                )
                publication_state_reconciled = (
                    _reconcile_pool_batch_publication_step_state_from_persisted_attempts(
                        execution=execution,
                    )
                    or publication_state_reconciled
                )

            _sync_pool_run_terminal_state_from_publication_projection(
                execution=execution,
            )
            _sync_pool_batch_workflow_state_from_execution(
                execution=execution,
            )
            _sync_pool_factual_projection_for_execution_update(
                execution=execution,
                result_payload=result_payload,
            )

            if publication_state_reconciled:
                next_input_context = (
                    dict(execution.input_context)
                    if isinstance(execution.input_context, dict)
                    else {}
                )
                if next_input_context != previous_input_context:
                    update_fields.append("input_context")

        if target_status == WorkflowExecution.STATUS_FAILED:
            _sync_pool_batch_workflow_state_from_execution(execution=execution)
            _sync_pool_factual_projection_for_execution_update(execution=execution)
        if update_fields:
            execution.save(update_fields=update_fields)
        _sync_workflow_root_projection_from_execution(execution=execution)
        return Response(_build_status_update_response(execution=execution))

    previous_input_context = (
        dict(execution.input_context)
        if isinstance(execution.input_context, dict)
        else {}
    )

    try:
        update_fields: set[str] = set()
        if target_status == WorkflowExecution.STATUS_RUNNING:
            if execution.status != WorkflowExecution.STATUS_PENDING:
                return Response({"success": False, "error": "Execution is not pending"}, status=status.HTTP_409_CONFLICT)
            execution.start()
            update_fields.update({"status", "started_at"})
            _sync_pool_batch_workflow_state_from_execution(
                execution=execution,
            )

        elif target_status == WorkflowExecution.STATUS_COMPLETED:
            if execution.status == WorkflowExecution.STATUS_PENDING:
                execution.start()
                update_fields.update({"status", "started_at"})
            if execution.status != WorkflowExecution.STATUS_RUNNING:
                return Response({"success": False, "error": "Execution is not running"}, status=status.HTTP_409_CONFLICT)
            execution.complete(result_payload)
            update_fields.update({"status", "final_result", "completed_at"})
            _project_pool_publication_attempts_from_result(
                execution=execution,
                result_payload=result_payload,
            )
            _project_pool_batch_publication_attempts_from_result(
                execution=execution,
                result_payload=result_payload,
            )
            _reconcile_pool_publication_step_state_from_persisted_attempts(
                execution=execution,
            )
            _reconcile_pool_batch_publication_step_state_from_persisted_attempts(
                execution=execution,
            )
            _sync_pool_run_terminal_state_from_publication_projection(
                execution=execution,
            )
            _sync_pool_batch_workflow_state_from_execution(
                execution=execution,
            )
            _sync_pool_factual_projection_for_execution_update(
                execution=execution,
                result_payload=result_payload,
            )

        elif target_status == WorkflowExecution.STATUS_FAILED:
            if execution.status == WorkflowExecution.STATUS_PENDING:
                execution.start()
                update_fields.update({"status", "started_at"})
            if execution.status != WorkflowExecution.STATUS_RUNNING:
                return Response({"success": False, "error": "Execution is not running"}, status=status.HTTP_409_CONFLICT)
            execution.fail(error_message or "Workflow failed")
            update_fields.update({"status", "error_message", "error_node_id", "completed_at"})
            if error_code_provided:
                execution.error_code = error_code
                update_fields.add("error_code")
            if error_details_provided:
                execution.error_details = error_details
                update_fields.add("error_details")
            _sync_pool_batch_workflow_state_from_execution(
                execution=execution,
            )
            _sync_pool_factual_projection_for_execution_update(
                execution=execution,
            )

        elif target_status == WorkflowExecution.STATUS_CANCELLED:
            if execution.status not in [WorkflowExecution.STATUS_PENDING, WorkflowExecution.STATUS_RUNNING]:
                return Response({"success": False, "error": "Execution cannot be cancelled"}, status=status.HTTP_409_CONFLICT)
            execution.cancel()
            update_fields.update({"status", "completed_at"})
            _sync_pool_batch_workflow_state_from_execution(
                execution=execution,
            )
            _sync_pool_factual_projection_for_execution_update(
                execution=execution,
            )
        else:
            return Response({"success": False, "error": "Unsupported status"}, status=status.HTTP_400_BAD_REQUEST)

        _advance_pools_runtime_metadata_on_status_update(execution=execution, target_status=target_status)
        next_input_context = (
            dict(execution.input_context)
            if isinstance(execution.input_context, dict)
            else {}
        )
        if next_input_context != previous_input_context:
            update_fields.add("input_context")
        execution.save(update_fields=sorted(update_fields))
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
