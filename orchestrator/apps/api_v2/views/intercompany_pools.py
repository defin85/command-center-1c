from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from datetime import date, datetime, timedelta, timezone as dt_timezone
from typing import Any
from uuid import UUID, uuid4

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core import permission_codes as perms
from apps.api_v2.serializers.common import ErrorResponseSerializer, ProblemDetailsErrorSerializer
from apps.databases.models import Database
from apps.intercompany_pools.models import (
    Organization,
    OrganizationStatus,
    OrganizationPool,
    PoolMasterParty,
    PoolODataMetadataCatalogSnapshot,
    PoolPublicationAttempt,
    PoolPublicationAttemptStatus,
    PoolEdgeVersion,
    PoolNodeVersion,
    PoolRun,
    PoolRunAuditEvent,
    PoolRunCommandLog,
    PoolRunCommandResultClass,
    PoolRunCommandType,
    PoolRunDirection,
    PoolRunMode,
    PoolSchemaTemplate,
    PoolSchemaTemplateFormat,
)
from apps.intercompany_pools.metadata_catalog import (
    ERROR_CODE_POOL_METADATA_REFERENCE_INVALID,
    ERROR_CODE_POOL_METADATA_SNAPSHOT_UNAVAILABLE,
    MetadataCatalogError,
    build_metadata_catalog_api_payload,
    describe_metadata_catalog_snapshot_resolution,
    get_current_snapshot_for_database_scope,
    normalize_catalog_payload,
    read_existing_metadata_catalog_snapshot,
    read_metadata_catalog_snapshot,
    refresh_metadata_catalog_snapshot,
    validate_document_policy_references,
)
from apps.intercompany_pools.runtime_projection_contract import (
    POOL_RUNTIME_PROJECTION_CONTEXT_KEY,
    validate_pool_runtime_projection_v1,
)
from apps.intercompany_pools.command_log import (
    PoolRunCommandIdempotencyConflict,
    record_pool_run_command_outcome,
)
from apps.intercompany_pools.document_plan_artifact_contract import (
    POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED,
    POOL_DOCUMENT_POLICY_SLOT_COVERAGE_AMBIGUOUS,
    POOL_DOCUMENT_POLICY_SLOT_DUPLICATE,
    POOL_DOCUMENT_POLICY_SLOT_NOT_BOUND,
    POOL_DOCUMENT_POLICY_SLOT_OUTPUT_INVALID,
    POOL_DOCUMENT_POLICY_SLOT_SELECTOR_MISSING,
)
from apps.intercompany_pools.document_policy_contract import (
    DOCUMENT_POLICY_METADATA_KEY,
    resolve_document_policy_from_edge_metadata,
)
from apps.intercompany_pools.safe_commands import (
    CONFLICT_REASON_AWAITING_PRE_PUBLISH,
    CONFLICT_REASON_IDEMPOTENCY_KEY_REUSED,
    CONFLICT_REASON_NOT_SAFE_RUN,
    CONFLICT_REASON_PUBLICATION_STARTED,
    CONFLICT_REASON_READINESS_BLOCKED,
    CONFLICT_REASON_TERMINAL_STATE,
    process_pool_run_safe_command,
)
from apps.intercompany_pools.sync import sync_organizations
from apps.intercompany_pools.validators import validate_pool_graph
from apps.intercompany_pools.publication_policy import (
    MAX_PUBLICATION_ATTEMPTS,
    MAX_RETRY_INTERVAL_SECONDS,
)
from apps.intercompany_pools.binding_preview import build_pool_workflow_binding_preview
from apps.intercompany_pools.runs import upsert_pool_run
from apps.intercompany_pools.workflow_runtime import (
    POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY,
    resolve_pool_runtime_schema_template,
    start_pool_run_retry_workflow_execution,
    start_pool_run_workflow_execution,
)
from apps.intercompany_pools.workflow_authoring_contract import (
    POOL_DOCUMENT_POLICY_SLOT_REQUIRED,
    PoolWorkflowBindingContract,
    build_pool_workflow_binding_read_model,
)
from apps.intercompany_pools.workflow_binding_resolution import (
    PoolWorkflowBindingResolutionError,
    resolve_pool_workflow_binding_for_run,
)
from apps.intercompany_pools.workflow_binding_attachments_store import (
    PoolWorkflowBindingAttachmentLifecycleConflictError,
    delete_pool_workflow_binding_attachment as delete_attached_pool_workflow_binding,
    get_pool_workflow_binding_attachment as get_attached_pool_workflow_binding,
    get_pool_workflow_binding_attachments_collection as get_attached_pool_workflow_binding_collection,
    list_pool_workflow_binding_attachments as list_attached_pool_workflow_bindings,
    replace_pool_workflow_binding_attachments_collection as replace_attached_pool_workflow_bindings_collection,
    upsert_pool_workflow_binding_attachment as upsert_attached_pool_workflow_binding,
)
from apps.intercompany_pools.workflow_bindings_store import (
    PoolWorkflowBindingCollectionConflictError,
    PoolWorkflowBindingNotFoundError,
    PoolWorkflowBindingRevisionConflictError,
    PoolWorkflowBindingStoreError,
)
from apps.templates.workflow.models import WorkflowExecution
from apps.runtime_settings.effective import get_effective_runtime_setting
from apps.tenancy.authentication import TENANT_HEADER
from apps.tenancy.models import Tenant

APPROVAL_STATE_NOT_REQUIRED = "not_required"
APPROVAL_STATE_PREPARING = "preparing"
APPROVAL_STATE_AWAITING_APPROVAL = "awaiting_approval"
APPROVAL_STATE_APPROVED = "approved"

PUBLICATION_STEP_STATE_NOT_ENQUEUED = "not_enqueued"
PUBLICATION_STEP_STATE_QUEUED = "queued"
PUBLICATION_STEP_STATE_STARTED = "started"
PUBLICATION_STEP_STATE_COMPLETED = "completed"

_VALID_APPROVAL_STATES = {
    APPROVAL_STATE_NOT_REQUIRED,
    APPROVAL_STATE_PREPARING,
    APPROVAL_STATE_AWAITING_APPROVAL,
    APPROVAL_STATE_APPROVED,
}

_VALID_PUBLICATION_STEP_STATES = {
    PUBLICATION_STEP_STATE_NOT_ENQUEUED,
    PUBLICATION_STEP_STATE_QUEUED,
    PUBLICATION_STEP_STATE_STARTED,
    PUBLICATION_STEP_STATE_COMPLETED,
}

ATTEMPT_KIND_INITIAL = "initial"
ATTEMPT_KIND_RETRY = "retry"
_VALID_ATTEMPT_KINDS = {ATTEMPT_KIND_INITIAL, ATTEMPT_KIND_RETRY}

_SENSITIVE_TOKEN_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|token|authorization|secret)\b\s*[:=]\s*([^\s,;]+)"
)
_UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)

RUN_INPUT_CONTRACT_VERSION_V1 = "run_input_v1"
RUN_INPUT_CONTRACT_VERSION_LEGACY = "legacy_pre_run_input"
TOPOLOGY_VERSION_TOKEN_PREFIX = "v1"
_POOL_RUNTIME_START_FAIL_CLOSED_CODES = {
    "POOL_RUNTIME_TEMPLATE_NOT_CONFIGURED",
    "POOL_RUNTIME_TEMPLATE_INACTIVE",
    "TEMPLATE_DRIFT",
    "POOL_RUNTIME_TEMPLATE_UNSUPPORTED_EXECUTOR",
    "POOL_DOCUMENT_POLICY_SLOT_SELECTOR_MISSING",
    "POOL_DOCUMENT_POLICY_SLOT_NOT_BOUND",
    "POOL_DOCUMENT_POLICY_SLOT_DUPLICATE",
    "POOL_DOCUMENT_POLICY_SLOT_REQUIRED",
    "POOL_DOCUMENT_POLICY_SLOT_OUTPUT_INVALID",
    "POOL_DOCUMENT_POLICY_SLOT_COVERAGE_AMBIGUOUS",
    "POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED",
    "POOL_WORKFLOW_BINDING_REQUIRED",
    "ODATA_MAPPING_NOT_CONFIGURED",
    "ODATA_MAPPING_AMBIGUOUS",
    "ODATA_PUBLICATION_AUTH_CONTEXT_INVALID",
}
_POOL_WORKFLOW_BINDING_VALIDATION_CODES = {
    "POOL_DOCUMENT_POLICY_SLOT_DUPLICATE",
    "POOL_DOCUMENT_POLICY_SLOT_REQUIRED",
    "POOL_WORKFLOW_BINDING_PROFILE_REVISION_NOT_FOUND",
}
POOL_PROJECTION_HARDENING_CUTOFF_KEY = "pools.projection.publication_hardening_cutoff_utc"
POOL_PUBLICATION_STEP_INCOMPLETE_CODE = "POOL_PUBLICATION_STEP_INCOMPLETE"
MASTER_DATA_GATE_STATUS_COMPLETED = "completed"
MASTER_DATA_GATE_STATUS_FAILED = "failed"
MASTER_DATA_GATE_STATUS_SKIPPED = "skipped"
MASTER_DATA_GATE_READ_MODEL_MODE = "resolve_upsert"
POOL_RUNTIME_READINESS_BLOCKERS_CONTEXT_KEY = "pool_runtime_readiness_blockers"
POOL_RUNTIME_VERIFICATION_CONTEXT_KEY = "pool_runtime_verification"
READINESS_STATUS_READY = "ready"
READINESS_STATUS_NOT_READY = "not_ready"
READINESS_CHECK_CODE_MASTER_DATA_COVERAGE = "master_data_coverage"
READINESS_CHECK_CODE_ORGANIZATION_PARTY_BINDINGS = "organization_party_bindings"
READINESS_CHECK_CODE_POLICY_COMPLETENESS = "policy_completeness"
READINESS_CHECK_CODE_ODATA_VERIFY_READINESS = "odata_verify_readiness"
READINESS_CHECK_CODES = (
    READINESS_CHECK_CODE_MASTER_DATA_COVERAGE,
    READINESS_CHECK_CODE_ORGANIZATION_PARTY_BINDINGS,
    READINESS_CHECK_CODE_POLICY_COMPLETENESS,
    READINESS_CHECK_CODE_ODATA_VERIFY_READINESS,
)
READINESS_BLOCKER_CODE_ORGANIZATION_PARTY_BINDING_MISSING = "MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING"
READINESS_BLOCKER_CODE_POLICY_MAPPING_INVALID = "POOL_DOCUMENT_POLICY_MAPPING_INVALID"
READINESS_ODATA_BLOCKER_CODES = {
    "ODATA_MAPPING_NOT_CONFIGURED",
    "ODATA_MAPPING_AMBIGUOUS",
    "ODATA_PUBLICATION_AUTH_CONTEXT_INVALID",
}
POOL_RUN_READINESS_BLOCKED_CODE = "POOL_RUN_READINESS_BLOCKED"
VERIFICATION_STATUS_NOT_VERIFIED = "not_verified"
VERIFICATION_STATUS_PASSED = "passed"
VERIFICATION_STATUS_FAILED = "failed"
_VALID_MASTER_DATA_GATE_STATUSES = {
    MASTER_DATA_GATE_STATUS_COMPLETED,
    MASTER_DATA_GATE_STATUS_FAILED,
    MASTER_DATA_GATE_STATUS_SKIPPED,
}
_VALID_VERIFICATION_STATUSES = {
    VERIFICATION_STATUS_NOT_VERIFIED,
    VERIFICATION_STATUS_PASSED,
    VERIFICATION_STATUS_FAILED,
}


def _error(*, code: str, message: str, status_code: int) -> Response:
    return Response(
        {
            "success": False,
            "error": {
                "code": code,
                "message": message,
            },
        },
        status=status_code,
    )


def _problem(
    *,
    code: str,
    title: str,
    detail: str,
    status_code: int,
    type_uri: str = "about:blank",
    errors: Any | None = None,
) -> Response:
    payload: dict[str, Any] = {
        "type": type_uri,
        "title": title,
        "status": int(status_code),
        "detail": detail,
        "code": code,
    }
    if errors is not None:
        payload["errors"] = errors
    return Response(
        payload,
        status=status_code,
        content_type="application/problem+json",
    )


def _database_permission_problem(*, detail: str) -> Response:
    return _problem(
        code="PERMISSION_DENIED",
        title="Permission Denied",
        detail=detail,
        status_code=http_status.HTTP_403_FORBIDDEN,
    )


def _safe_command_conflict_payload(*, run_id: UUID, conflict_reason: str | None) -> dict[str, Any]:
    reason = str(conflict_reason or "").strip().lower()
    code_map = {
        CONFLICT_REASON_NOT_SAFE_RUN: ("NOT_SAFE_RUN", "Safe command is not allowed for this run."),
        CONFLICT_REASON_AWAITING_PRE_PUBLISH: (
            "AWAITING_PRE_PUBLISH",
            "Pre-publish этап ещё выполняется, команда пока недоступна.",
        ),
        CONFLICT_REASON_READINESS_BLOCKED: (
            POOL_RUN_READINESS_BLOCKED_CODE,
            "Resolve readiness blockers before confirm-publication.",
        ),
        CONFLICT_REASON_PUBLICATION_STARTED: (
            "PUBLICATION_STARTED",
            "Publication уже началась, команда больше недоступна.",
        ),
        CONFLICT_REASON_TERMINAL_STATE: ("TERMINAL_STATE", "Run уже находится в terminal state."),
        CONFLICT_REASON_IDEMPOTENCY_KEY_REUSED: (
            "IDEMPOTENCY_KEY_REUSED",
            "Idempotency-Key уже использован для другой семантики команды.",
        ),
    }
    error_code, error_message = code_map.get(reason, ("COMMAND_CONFLICT", "Команда недоступна в текущем состоянии run."))
    retryable = reason in {CONFLICT_REASON_AWAITING_PRE_PUBLISH}
    return {
        "success": False,
        "error_code": error_code,
        "error_message": error_message,
        "conflict_reason": reason or CONFLICT_REASON_TERMINAL_STATE,
        "retryable": retryable,
        "run_id": str(run_id),
    }


def _binding_revision_conflict_problem(exc: PoolWorkflowBindingRevisionConflictError) -> Response:
    return _problem(
        code="POOL_WORKFLOW_BINDING_REVISION_CONFLICT",
        title="Pool Workflow Binding Revision Conflict",
        detail=(
            "Workflow binding was changed by another session. "
            "Reload binding data and retry with the latest revision."
        ),
        status_code=http_status.HTTP_409_CONFLICT,
        errors=[
            {
                "binding_id": exc.binding_id,
                "expected_revision": exc.expected_revision,
                "actual_revision": exc.actual_revision,
                "operation": exc.operation,
            }
        ],
    )


def _binding_collection_conflict_problem(exc: PoolWorkflowBindingCollectionConflictError) -> Response:
    return _problem(
        code="POOL_WORKFLOW_BINDING_COLLECTION_CONFLICT",
        title="Pool Workflow Binding Collection Conflict",
        detail=(
            "Workflow binding collection was changed by another session. "
            "Reload the canonical collection and retry with the latest collection_etag."
        ),
        status_code=http_status.HTTP_409_CONFLICT,
        errors=[
            {
                "expected_collection_etag": exc.expected_collection_etag,
                "actual_collection_etag": exc.actual_collection_etag,
            }
        ],
    )


def _binding_profile_lifecycle_conflict_problem(
    exc: PoolWorkflowBindingAttachmentLifecycleConflictError,
) -> Response:
    return _problem(
        code="POOL_WORKFLOW_BINDING_PROFILE_LIFECYCLE_CONFLICT",
        title="Pool Workflow Binding Profile Lifecycle Conflict",
        detail=(
            "Pinned binding profile revision is deactivated and cannot be attached via the default "
            "workflow binding path."
        ),
        status_code=http_status.HTTP_409_CONFLICT,
        errors=[
            {
                "binding_profile_revision_id": exc.binding_profile_revision_id,
                "profile_status": exc.profile_status,
                "operation": exc.operation,
            }
        ],
    )


def _resolve_tenant_id(request) -> str | None:
    tenant_id = getattr(request, "tenant_id", None)
    if tenant_id:
        return str(tenant_id)

    raw = request.META.get(TENANT_HEADER)
    if raw is None and getattr(request, "_request", None) is not None:
        raw = request._request.META.get(TENANT_HEADER)
    raw_value = str(raw or "").strip()
    if raw_value:
        return raw_value

    underlying = getattr(request, "_request", None)
    forced_user = getattr(request, "_force_auth_user", None)
    if forced_user is None and underlying is not None:
        forced_user = getattr(underlying, "_force_auth_user", None)
    if forced_user is None:
        return None

    default_tenant_id = Tenant.objects.filter(slug="default").values_list("id", flat=True).first()
    return str(default_tenant_id) if default_tenant_id else None


def _validation_message(exc: Exception) -> str:
    if isinstance(exc, DjangoValidationError):
        if exc.messages:
            return "; ".join(str(item) for item in exc.messages)
        if hasattr(exc, "message_dict") and exc.message_dict:
            return str(exc.message_dict)
    return str(exc)


def _resolve_pool_runtime_start_error(exc: Exception) -> tuple[str, str]:
    message = _validation_message(exc).strip()
    if not message:
        return "VALIDATION_ERROR", "Pool runtime workflow execution failed."

    raw_code, has_separator, raw_detail = message.partition(":")
    code = str(raw_code or "").strip().upper()
    detail = str(raw_detail or "").strip()
    if has_separator and code in _POOL_RUNTIME_START_FAIL_CLOSED_CODES:
        return code, detail or message
    return "VALIDATION_ERROR", message


def _resolve_pool_workflow_binding_validation_error(exc: Exception) -> tuple[str, str]:
    message = _validation_message(exc).strip()
    if not message:
        return "VALIDATION_ERROR", "Pool workflow binding validation failed."

    raw_code, has_separator, raw_detail = message.partition(":")
    code = str(raw_code or "").strip().upper()
    detail = re.sub(r"\s+\[type=.*$", "", str(raw_detail or "").strip()).strip()
    if has_separator and code in _POOL_WORKFLOW_BINDING_VALIDATION_CODES:
        return code, detail or message
    for known_code in _POOL_WORKFLOW_BINDING_VALIDATION_CODES:
        if known_code not in message:
            continue
        match = re.search(rf"{re.escape(known_code)}:\s*([^\n]+)", message)
        if match is not None:
            normalized_detail = re.sub(r"\s+\[type=.*$", "", str(match.group(1) or "").strip()).strip()
            return known_code, normalized_detail or message
        return known_code, message
    return "VALIDATION_ERROR", message


def _parse_date_param(raw: str | None, *, field_name: str) -> tuple[date | None, str | None]:
    value = str(raw or "").strip()
    if not value:
        return None, None
    try:
        return date.fromisoformat(value), None
    except ValueError:
        return None, f"{field_name} must be YYYY-MM-DD"


def _parse_limit(raw: str | None, *, default: int = 50, max_value: int = 200) -> int:
    try:
        value = int(raw or default)
    except (TypeError, ValueError):
        return default
    if value < 1:
        return default
    return min(value, max_value)


def _collect_failed_target_ids_for_retry(*, run: PoolRun) -> list[str]:
    latest_status_by_database: dict[str, str] = {}
    attempts = (
        PoolPublicationAttempt.objects.filter(run=run)
        .order_by("target_database_id", "attempt_number", "created_at")
        .only("target_database_id", "status")
    )
    for attempt in attempts:
        latest_status_by_database[str(attempt.target_database_id)] = attempt.status
    return sorted(
        database_id
        for database_id, status in latest_status_by_database.items()
        if status == PoolPublicationAttemptStatus.FAILED
    )


def _normalize_retry_target_ids(raw_target_ids: object) -> list[str]:
    if not isinstance(raw_target_ids, list):
        return []
    normalized_ids: list[str] = []
    seen: set[str] = set()
    for raw_target_id in raw_target_ids:
        target_id = str(raw_target_id or "").strip()
        if not target_id or target_id in seen:
            continue
        seen.add(target_id)
        normalized_ids.append(target_id)
    return sorted(normalized_ids)


def _build_retry_command_fingerprint(
    *,
    entity_name: str,
    target_ids: list[str],
    max_attempts: int,
    retry_interval_seconds: int,
    external_key_field: str,
    use_retry_subset_payload: bool,
) -> str:
    fingerprint_payload = "|".join(
        [
            "v1",
            f"entity={entity_name}",
            f"targets={','.join(target_ids)}",
            f"max_attempts={max_attempts}",
            f"retry_interval_seconds={retry_interval_seconds}",
            f"external_key_field={external_key_field}",
            f"use_retry_subset_payload={int(bool(use_retry_subset_payload))}",
        ]
    )
    digest = hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest()
    return f"v1:{digest}"


def _resolve_run_input_read_contract(*, run: PoolRun) -> tuple[dict[str, Any] | None, str]:
    raw_run_input = run.run_input
    legacy_source_hash = str(run.source_hash or "").strip()
    if isinstance(raw_run_input, dict):
        if raw_run_input or not legacy_source_hash:
            return raw_run_input, RUN_INPUT_CONTRACT_VERSION_V1
    return None, RUN_INPUT_CONTRACT_VERSION_LEGACY


def _build_topology_version_token(
    *,
    active_nodes: list[PoolNodeVersion],
    active_edges: list[PoolEdgeVersion],
) -> str:
    node_tokens = sorted(
        "|".join(
            [
                str(node.id),
                str(node.organization_id),
                "1" if node.is_root else "0",
                node.effective_from.isoformat(),
                node.effective_to.isoformat() if node.effective_to else "",
                node.updated_at.isoformat(),
            ]
        )
        for node in active_nodes
    )
    edge_tokens = sorted(
        "|".join(
            [
                str(edge.id),
                str(edge.parent_node_id),
                str(edge.child_node_id),
                str(edge.weight),
                str(edge.min_amount) if edge.min_amount is not None else "",
                str(edge.max_amount) if edge.max_amount is not None else "",
                edge.effective_from.isoformat(),
                edge.effective_to.isoformat() if edge.effective_to else "",
                edge.updated_at.isoformat(),
            ]
        )
        for edge in active_edges
    )
    fingerprint_payload = "\n".join(
        [
            "nodes",
            *node_tokens,
            "edges",
            *edge_tokens,
        ]
    )
    digest = hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest()
    return f"{TOPOLOGY_VERSION_TOKEN_PREFIX}:{digest}"


def _load_pool_graph_state(
    *,
    pool: OrganizationPool,
    target_date: date,
) -> tuple[list[PoolNodeVersion], list[PoolEdgeVersion]]:
    active_nodes = list(
        PoolNodeVersion.objects.select_related("organization")
        .filter(pool=pool, effective_from__lte=target_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target_date))
        # Keep snapshot insertion order for UI round-trips.
        .order_by("created_at", "id")
    )
    active_node_ids = {str(node.id) for node in active_nodes}
    active_edges_qs = (
        PoolEdgeVersion.objects.select_related("parent_node__organization", "child_node__organization")
        .filter(pool=pool, effective_from__lte=target_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target_date))
    )
    if active_node_ids:
        active_edges_qs = active_edges_qs.filter(
            parent_node_id__in=active_node_ids,
            child_node_id__in=active_node_ids,
        )
    else:
        active_edges_qs = active_edges_qs.none()
    active_edges = list(
        # Keep snapshot insertion order for UI round-trips.
        active_edges_qs.order_by("created_at", "id")
    )
    return active_nodes, active_edges


def _serialize_metadata_catalog_snapshot(
    *,
    database: Database,
    snapshot: PoolODataMetadataCatalogSnapshot,
    source: str,
    resolution,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_metadata_catalog_api_payload(
        database=database,
        snapshot=snapshot,
        source=source,
        resolution=resolution,
        profile=profile,
    )


def _resolve_topology_document_policy_referential_errors(
    *,
    tenant_id: str,
    organizations: dict[str, Organization],
    edges_payload: list[dict[str, Any]],
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    snapshot_cache: dict[str, PoolODataMetadataCatalogSnapshot | None] = {}
    for edge_index, edge in enumerate(edges_payload):
        metadata = edge.get("metadata")
        if not isinstance(metadata, dict):
            continue
        try:
            policy = resolve_document_policy_from_edge_metadata(metadata=metadata)
        except ValueError:
            # Contract-level validation is handled by serializer pre-validation.
            continue
        if policy is None:
            continue

        child_org_id = str(edge.get("child_organization_id") or "").strip()
        child_org = organizations.get(child_org_id)
        if child_org is None:
            continue
        database_id = str(child_org.database_id or "").strip()
        if not database_id:
            errors.append(
                {
                    "code": ERROR_CODE_POOL_METADATA_SNAPSHOT_UNAVAILABLE,
                    "path": f"edges[{edge_index}].metadata.document_policy",
                    "detail": "Child organization must be linked to database for metadata validation.",
                }
            )
            continue

        snapshot = snapshot_cache.get(database_id)
        if database_id not in snapshot_cache:
            database = Database.objects.filter(id=database_id, tenant_id=tenant_id).first()
            snapshot = (
                get_current_snapshot_for_database_scope(tenant_id=tenant_id, database=database)
                if database is not None
                else None
            )
            snapshot_cache[database_id] = snapshot

        policy_errors = validate_document_policy_references(
            policy=policy,
            snapshot=snapshot,
            path_prefix=f"edges[{edge_index}].metadata.document_policy",
        )
        errors.extend(policy_errors)
    return errors


def _collect_legacy_document_policy_write_errors(
    *,
    pool_metadata: Mapping[str, Any] | None = None,
    edges_payload: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if isinstance(pool_metadata, Mapping) and DOCUMENT_POLICY_METADATA_KEY in pool_metadata:
        errors.append(
            {
                "code": POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED,
                "path": f"metadata.{DOCUMENT_POLICY_METADATA_KEY}",
                "detail": (
                    "Legacy pool.metadata.document_policy is not allowed in mutating authoring path. "
                    "Use /decisions, workflow bindings, and edge.metadata.document_policy_key."
                ),
            }
        )
    for edge_index, edge in enumerate(edges_payload or []):
        metadata = edge.get("metadata")
        if not isinstance(metadata, Mapping) or DOCUMENT_POLICY_METADATA_KEY not in metadata:
            continue
        errors.append(
            {
                "code": POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED,
                "path": f"edges[{edge_index}].metadata.{DOCUMENT_POLICY_METADATA_KEY}",
                "detail": (
                    "Legacy edge.metadata.document_policy is not allowed in mutating authoring path. "
                    "Use /decisions, workflow bindings, and edge.metadata.document_policy_key."
                ),
            }
        )
    return errors


def _legacy_document_policy_write_problem(*, errors: list[dict[str, str]]) -> Response:
    first_error = errors[0]
    return _problem(
        code=POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED,
        title="Legacy Document Policy Rejected",
        detail=f"{first_error['detail']} (path: {first_error['path']})",
        status_code=http_status.HTTP_400_BAD_REQUEST,
        errors=errors,
    )


def _serialize_run(
    run: PoolRun,
    *,
    publication_hardening_cutoff_utc: datetime | None = None,
) -> dict[str, Any]:
    run_input, input_contract_version = _resolve_run_input_read_contract(run=run)
    (
        workflow_status,
        workflow_input_context,
        projection_timestamp,
        workflow_failure_context,
        workflow_execution_consumer,
    ) = _resolve_workflow_projection_context(run)
    execution_backend = run.execution_backend or (
        "workflow_core" if run.workflow_execution_id else "legacy_pool_runtime"
    )
    approval_state = _resolve_approval_state(
        run=run,
        workflow_status=workflow_status,
        workflow_input_context=workflow_input_context,
    )
    publication_step_state = _resolve_publication_step_state(
        run=run,
        workflow_status=workflow_status,
        workflow_input_context=workflow_input_context,
        approval_state=approval_state,
        execution_backend=execution_backend,
    )
    master_data_gate = _resolve_master_data_gate_read_model(
        workflow_input_context=workflow_input_context
    )
    readiness_blockers = _resolve_readiness_blockers_read_model(
        workflow_input_context=workflow_input_context,
        master_data_gate=master_data_gate,
    )
    verification_status, verification_summary = _resolve_verification_read_model(
        workflow_input_context=workflow_input_context
    )
    readiness_checklist = _resolve_readiness_checklist_read_model(
        workflow_status=workflow_status,
        approval_state=approval_state,
        publication_step_state=publication_step_state,
        execution_backend=execution_backend,
        master_data_gate=master_data_gate,
        readiness_blockers=readiness_blockers,
        verification_status=verification_status,
    )
    terminal_reason = _resolve_terminal_reason(
        run=run,
        workflow_input_context=workflow_input_context,
    )
    projected_status, status_reason = _project_pool_status(
        run=run,
        workflow_status=workflow_status,
        approval_state=approval_state,
        publication_step_state=publication_step_state,
        execution_backend=execution_backend,
        projection_timestamp=projection_timestamp,
        publication_hardening_cutoff_utc=publication_hardening_cutoff_utc,
    )
    diagnostics = _resolve_run_diagnostics(
        run=run,
        workflow_status=workflow_status,
        approval_state=approval_state,
        publication_step_state=publication_step_state,
        projected_status=projected_status,
        workflow_failure_context=workflow_failure_context,
    )
    observability_fields = _resolve_run_observability_fields(
        run=run,
        workflow_execution_consumer=workflow_execution_consumer,
    )
    provenance = _build_run_provenance(
        run=run,
        workflow_status=workflow_status,
        execution_backend=execution_backend,
        observability_fields=observability_fields,
    )
    workflow_binding = _resolve_workflow_binding_read_model(
        run=run,
        workflow_input_context=workflow_input_context,
    )
    runtime_projection = _resolve_runtime_projection_read_model(
        run=run,
        workflow_input_context=workflow_input_context,
    )
    return {
        "id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "pool_id": str(run.pool_id),
        "schema_template_id": str(run.schema_template_id) if run.schema_template_id else None,
        "mode": run.mode,
        "direction": run.direction,
        "status": projected_status,
        "status_reason": status_reason,
        "period_start": run.period_start,
        "period_end": run.period_end,
        "run_input": run_input,
        "input_contract_version": input_contract_version,
        "idempotency_key": run.idempotency_key,
        "workflow_execution_id": str(run.workflow_execution_id) if run.workflow_execution_id else None,
        "workflow_status": workflow_status,
        "root_operation_id": observability_fields.get("root_operation_id"),
        "execution_consumer": observability_fields.get("execution_consumer"),
        "lane": observability_fields.get("lane"),
        "approval_state": approval_state,
        "publication_step_state": publication_step_state,
        "master_data_gate": master_data_gate,
        "readiness_blockers": readiness_blockers,
        "readiness_checklist": readiness_checklist,
        "verification_status": verification_status,
        "verification_summary": verification_summary,
        "terminal_reason": terminal_reason,
        "execution_backend": execution_backend,
        "provenance": provenance,
        "workflow_binding": workflow_binding,
        "runtime_projection": runtime_projection,
        "workflow_template_name": run.workflow_template_name or None,
        "seed": run.seed,
        "validation_summary": run.validation_summary,
        "publication_summary": run.publication_summary,
        "diagnostics": diagnostics,
        "last_error": run.last_error,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "validated_at": run.validated_at,
        "publication_confirmed_at": run.publication_confirmed_at,
        "publishing_started_at": run.publishing_started_at,
        "completed_at": run.completed_at,
    }


def _resolve_run_diagnostics(
    *,
    run: PoolRun,
    workflow_status: str | None,
    approval_state: str | None,
    publication_step_state: str | None,
    projected_status: str,
    workflow_failure_context: dict[str, Any] | None,
) -> Any:
    workflow_failure_problem = _build_workflow_failure_problem_details(
        workflow_status=workflow_status,
        projected_status=projected_status,
        workflow_failure_context=workflow_failure_context,
    )
    publication_step_problem = _build_publication_step_problem_details(
        workflow_status=workflow_status,
        approval_state=approval_state,
        publication_step_state=publication_step_state,
        projected_status=projected_status,
    )

    generated_problems: list[dict[str, Any]] = []
    if workflow_failure_problem is not None:
        generated_problems.append(workflow_failure_problem)
    if publication_step_problem is not None:
        generated_problems.append(publication_step_problem)

    return _merge_run_diagnostics(
        base_diagnostics=run.diagnostics,
        generated_problems=generated_problems,
    )


def _merge_run_diagnostics(
    *,
    base_diagnostics: object,
    generated_problems: list[dict[str, Any]],
) -> Any:
    if not generated_problems:
        return base_diagnostics

    diagnostics: list[Any]
    if isinstance(base_diagnostics, list):
        diagnostics = list(base_diagnostics)
    elif _has_legacy_run_diagnostics_payload(base_diagnostics):
        diagnostics = [base_diagnostics]
    else:
        diagnostics = []

    existing_codes = {
        str(item.get("code") or "").strip()
        for item in diagnostics
        if isinstance(item, dict) and str(item.get("code") or "").strip()
    }
    for problem in generated_problems:
        code = str(problem.get("code") or "").strip()
        if code and code in existing_codes:
            continue
        diagnostics.append(problem)
        if code:
            existing_codes.add(code)
    return diagnostics


def _has_legacy_run_diagnostics_payload(raw_value: object) -> bool:
    if raw_value is None:
        return False
    if isinstance(raw_value, str):
        return bool(raw_value.strip())
    if isinstance(raw_value, Mapping):
        return bool(raw_value)
    if isinstance(raw_value, (list, tuple, set)):
        return bool(raw_value)
    return True


def _build_workflow_failure_problem_details(
    *,
    workflow_status: str | None,
    projected_status: str,
    workflow_failure_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    workflow_state = str(workflow_status or "").strip().lower()
    if workflow_state != WorkflowExecution.STATUS_FAILED:
        return None
    if projected_status != PoolRun.STATUS_FAILED:
        return None
    if not isinstance(workflow_failure_context, dict):
        return None

    error_code = str(workflow_failure_context.get("error_code") or "").strip()
    if not error_code:
        return None

    error_message = _sanitize_diagnostics_message(workflow_failure_context.get("error_message"))
    payload: dict[str, Any] = {
        "type": "about:blank",
        "title": "Workflow Execution Failed",
        "status": int(http_status.HTTP_409_CONFLICT),
        "detail": error_message or "Workflow execution failed.",
        "code": error_code,
    }
    error_details = workflow_failure_context.get("error_details")
    if isinstance(error_details, dict) and error_details:
        payload["error_details"] = error_details
    return payload


def _build_publication_step_problem_details(
    *,
    workflow_status: str | None,
    approval_state: str | None,
    publication_step_state: str | None,
    projected_status: str,
) -> dict[str, Any] | None:
    workflow_state = str(workflow_status or "").strip().lower()
    if workflow_state != WorkflowExecution.STATUS_COMPLETED:
        return None
    if projected_status != PoolRun.STATUS_FAILED:
        return None
    if approval_state not in {APPROVAL_STATE_APPROVED, APPROVAL_STATE_NOT_REQUIRED}:
        return None
    if publication_step_state == PUBLICATION_STEP_STATE_COMPLETED:
        return None
    return {
        "type": "about:blank",
        "title": "Publication Step Incomplete",
        "status": int(http_status.HTTP_409_CONFLICT),
        "detail": (
            "Workflow execution completed without confirmed publication-step completion."
        ),
        "code": POOL_PUBLICATION_STEP_INCOMPLETE_CODE,
    }


def _resolve_workflow_projection_context(
    run: PoolRun,
) -> tuple[str | None, dict[str, Any], datetime | None, dict[str, Any] | None, str | None]:
    workflow_status = run.workflow_status or None
    workflow_input_context: dict[str, Any] = {}
    projection_timestamp: datetime | None = run.created_at
    workflow_failure_context: dict[str, Any] | None = None
    workflow_execution_consumer: str | None = None
    execution = _resolve_workflow_execution_for_projection(run=run)

    if not execution:
        return (
            workflow_status,
            workflow_input_context,
            projection_timestamp,
            workflow_failure_context,
            workflow_execution_consumer,
        )

    execution_id = execution.get("id")
    if execution_id:
        run.workflow_execution_id = execution_id
        run.execution_backend = "workflow_core"

    started_at = execution.get("started_at")
    created_at = execution.get("created_at")
    if isinstance(started_at, datetime):
        projection_timestamp = started_at
    elif isinstance(created_at, datetime):
        projection_timestamp = created_at

    raw_input_context = execution.get("input_context")
    if isinstance(raw_input_context, dict):
        workflow_input_context = raw_input_context

    template_name = str(execution.get("workflow_template__name") or "").strip()
    if template_name and not run.workflow_template_name:
        run.workflow_template_name = template_name

    resolved_status = execution.get("status") or workflow_status
    if resolved_status:
        run.workflow_status = resolved_status
    execution_error_code = str(execution.get("error_code") or "").strip()
    if execution_error_code:
        workflow_failure_context = {
            "error_code": execution_error_code,
            "error_message": str(execution.get("error_message") or ""),
            "error_details": execution.get("error_details"),
        }

    execution_consumer = str(execution.get("execution_consumer") or "").strip()
    if execution_consumer:
        workflow_execution_consumer = execution_consumer

    return (
        resolved_status,
        workflow_input_context,
        projection_timestamp,
        workflow_failure_context,
        workflow_execution_consumer,
    )


def _parse_positive_int(raw_value: object) -> int | None:
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None
    if value < 1:
        return None
    return value


def _parse_non_negative_int(raw_value: object) -> int:
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return 0
    if value < 0:
        return 0
    return value


def _normalize_optional_text(raw_value: object) -> str | None:
    value = str(raw_value or "").strip()
    return value or None


def _normalize_master_data_gate_status(*, raw_status: object, error_code: str | None) -> str:
    status_token = str(raw_status or "").strip().lower()
    if status_token in _VALID_MASTER_DATA_GATE_STATUSES:
        return status_token
    if error_code:
        return MASTER_DATA_GATE_STATUS_FAILED
    return MASTER_DATA_GATE_STATUS_COMPLETED


def _resolve_master_data_gate_read_model(
    *,
    workflow_input_context: dict[str, Any],
) -> dict[str, Any] | None:
    raw_gate_summary = workflow_input_context.get("pool_runtime_master_data_gate")
    if raw_gate_summary is None:
        return None
    if not isinstance(raw_gate_summary, Mapping):
        return None

    gate_summary = dict(raw_gate_summary)
    error_code = _normalize_optional_text(gate_summary.get("error_code"))
    detail = _normalize_optional_text(gate_summary.get("detail")) or _normalize_optional_text(
        gate_summary.get("reason")
    )
    diagnostic_raw = gate_summary.get("diagnostic")
    diagnostic = dict(diagnostic_raw) if isinstance(diagnostic_raw, Mapping) else None

    return {
        "status": _normalize_master_data_gate_status(
            raw_status=gate_summary.get("status"),
            error_code=error_code,
        ),
        "mode": MASTER_DATA_GATE_READ_MODEL_MODE,
        "targets_count": _parse_non_negative_int(gate_summary.get("targets_count")),
        "bindings_count": _parse_non_negative_int(gate_summary.get("bindings_count")),
        "error_code": error_code,
        "detail": detail,
        "diagnostic": diagnostic,
    }


def _resolve_readiness_blockers_read_model(
    *,
    workflow_input_context: dict[str, Any],
    master_data_gate: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    raw_blockers = workflow_input_context.get(POOL_RUNTIME_READINESS_BLOCKERS_CONTEXT_KEY)
    blockers = _normalize_readiness_blockers(raw_blockers)
    if blockers:
        return blockers
    if not isinstance(master_data_gate, Mapping):
        return []
    if str(master_data_gate.get("status") or "").strip().lower() != MASTER_DATA_GATE_STATUS_FAILED:
        return []
    return [
        _normalize_readiness_blocker(
            {
                "code": _normalize_optional_text(master_data_gate.get("error_code")),
                "detail": _normalize_optional_text(master_data_gate.get("detail")),
                "diagnostic": dict(master_data_gate.get("diagnostic") or {})
                if isinstance(master_data_gate.get("diagnostic"), Mapping)
                else None,
            }
        )
    ]


def _normalize_readiness_blockers(raw_blockers: object) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if not isinstance(raw_blockers, list):
        return blockers
    for raw_blocker in raw_blockers:
        if isinstance(raw_blocker, Mapping):
            blockers.append(_normalize_readiness_blocker(raw_blocker))
    return blockers


def _normalize_readiness_blocker(raw_blocker: Mapping[str, Any]) -> dict[str, Any]:
    blocker: dict[str, Any] = {
        "code": _normalize_optional_text(raw_blocker.get("code")) or _normalize_optional_text(
            raw_blocker.get("error_code")
        ),
        "detail": _normalize_optional_text(raw_blocker.get("detail")),
    }
    for field_name in ("kind", "entity_name", "field_or_table_path", "database_id", "organization_id"):
        blocker[field_name] = _normalize_optional_text(raw_blocker.get(field_name))
    diagnostic_raw = raw_blocker.get("diagnostic")
    blocker["diagnostic"] = dict(diagnostic_raw) if isinstance(diagnostic_raw, Mapping) else None
    return blocker


def _resolve_readiness_checklist_read_model(
    *,
    workflow_status: str | None,
    approval_state: str | None,
    publication_step_state: str | None,
    execution_backend: str | None,
    master_data_gate: dict[str, Any] | None,
    readiness_blockers: list[dict[str, Any]],
    verification_status: str,
) -> dict[str, Any]:
    has_runtime_evidence = _readiness_has_runtime_evidence(
        workflow_status=workflow_status,
        approval_state=approval_state,
        publication_step_state=publication_step_state,
        execution_backend=execution_backend,
        master_data_gate=master_data_gate,
        verification_status=verification_status,
    )
    checks = [
        _build_readiness_check(
            check_code=check_code,
            readiness_blockers=readiness_blockers,
            has_runtime_evidence=has_runtime_evidence,
            execution_backend=execution_backend,
        )
        for check_code in READINESS_CHECK_CODES
    ]
    return {
        "status": (
            READINESS_STATUS_READY
            if checks and all(item["status"] == READINESS_STATUS_READY for item in checks)
            else READINESS_STATUS_NOT_READY
        ),
        "checks": checks,
    }


def _readiness_has_runtime_evidence(
    *,
    workflow_status: str | None,
    approval_state: str | None,
    publication_step_state: str | None,
    execution_backend: str | None,
    master_data_gate: dict[str, Any] | None,
    verification_status: str,
) -> bool:
    if isinstance(master_data_gate, Mapping):
        gate_status = str(master_data_gate.get("status") or "").strip().lower()
        if gate_status in _VALID_MASTER_DATA_GATE_STATUSES:
            return True

    if approval_state in {
        APPROVAL_STATE_AWAITING_APPROVAL,
        APPROVAL_STATE_APPROVED,
        APPROVAL_STATE_NOT_REQUIRED,
    }:
        return True

    if publication_step_state in {
        PUBLICATION_STEP_STATE_QUEUED,
        PUBLICATION_STEP_STATE_STARTED,
        PUBLICATION_STEP_STATE_COMPLETED,
    }:
        return True

    if verification_status in {VERIFICATION_STATUS_PASSED, VERIFICATION_STATUS_FAILED}:
        return True

    workflow_state = str(workflow_status or "").strip().lower()
    return execution_backend == "workflow_core" and workflow_state == WorkflowExecution.STATUS_COMPLETED


def _build_readiness_check(
    *,
    check_code: str,
    readiness_blockers: list[dict[str, Any]],
    has_runtime_evidence: bool,
    execution_backend: str | None,
) -> dict[str, Any]:
    blockers = [
        dict(blocker)
        for blocker in readiness_blockers
        if _readiness_blocker_matches_check(check_code=check_code, blocker=blocker)
    ]
    default_ready = has_runtime_evidence
    if check_code == READINESS_CHECK_CODE_ODATA_VERIFY_READINESS:
        default_ready = has_runtime_evidence and execution_backend == "workflow_core"
    blocker_codes = sorted(
        {
            code
            for code in (_normalize_optional_text(item.get("code")) for item in blockers)
            if code
        }
    )
    return {
        "code": check_code,
        "status": READINESS_STATUS_READY if not blockers and default_ready else READINESS_STATUS_NOT_READY,
        "blocker_codes": blocker_codes,
        "blockers": blockers,
    }


def _readiness_blocker_matches_check(*, check_code: str, blocker: Mapping[str, Any]) -> bool:
    code = str(blocker.get("code") or "").strip().upper()
    if not code:
        return False
    if check_code == READINESS_CHECK_CODE_ORGANIZATION_PARTY_BINDINGS:
        return code == READINESS_BLOCKER_CODE_ORGANIZATION_PARTY_BINDING_MISSING
    if check_code == READINESS_CHECK_CODE_POLICY_COMPLETENESS:
        return code == READINESS_BLOCKER_CODE_POLICY_MAPPING_INVALID
    if check_code == READINESS_CHECK_CODE_ODATA_VERIFY_READINESS:
        return code in READINESS_ODATA_BLOCKER_CODES or code.startswith("ODATA_")
    if check_code == READINESS_CHECK_CODE_MASTER_DATA_COVERAGE:
        if code == READINESS_BLOCKER_CODE_ORGANIZATION_PARTY_BINDING_MISSING:
            return False
        if code == READINESS_BLOCKER_CODE_POLICY_MAPPING_INVALID:
            return False
        if code in READINESS_ODATA_BLOCKER_CODES or code.startswith("ODATA_"):
            return False
        return code.startswith("MASTER_DATA_")
    return False


def _normalize_verification_status(raw_status: object) -> str:
    status_token = str(raw_status or "").strip().lower()
    if status_token in _VALID_VERIFICATION_STATUSES:
        return status_token
    return VERIFICATION_STATUS_NOT_VERIFIED


def _normalize_verification_mismatch(raw_mismatch: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "database_id": _normalize_optional_text(raw_mismatch.get("database_id")),
        "entity_name": _normalize_optional_text(raw_mismatch.get("entity_name")),
        "document_idempotency_key": _normalize_optional_text(raw_mismatch.get("document_idempotency_key")),
        "field_or_table_path": _normalize_optional_text(raw_mismatch.get("field_or_table_path")),
        "kind": _normalize_optional_text(raw_mismatch.get("kind")),
    }


def _resolve_verification_read_model(
    *,
    workflow_input_context: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    raw_verification = workflow_input_context.get(POOL_RUNTIME_VERIFICATION_CONTEXT_KEY)
    if not isinstance(raw_verification, Mapping):
        return VERIFICATION_STATUS_NOT_VERIFIED, None
    status_value = _normalize_verification_status(raw_verification.get("status"))
    summary_raw = raw_verification.get("summary")
    summary = None
    if isinstance(summary_raw, Mapping):
        raw_mismatches = summary_raw.get("mismatches")
        mismatches = (
            [
                _normalize_verification_mismatch(raw_mismatch)
                for raw_mismatch in raw_mismatches
                if isinstance(raw_mismatch, Mapping)
            ]
            if isinstance(raw_mismatches, list)
            else []
        )
        summary = {
            "checked_targets": _parse_non_negative_int(summary_raw.get("checked_targets")),
            "verified_documents": _parse_non_negative_int(summary_raw.get("verified_documents")),
            "mismatches_count": _parse_non_negative_int(summary_raw.get("mismatches_count")),
            "mismatches": mismatches,
        }
    return status_value, summary


def _normalize_attempt_kind(raw_attempt_kind: object) -> str | None:
    attempt_kind = str(raw_attempt_kind or "").strip().lower()
    if attempt_kind in _VALID_ATTEMPT_KINDS:
        return attempt_kind
    return None


def _normalize_workflow_run_id(raw_workflow_run_id: object) -> str | None:
    token = str(raw_workflow_run_id or "").strip()
    if not token:
        return None
    try:
        UUID(token)
    except (TypeError, ValueError, AttributeError):
        return None
    return token


def _workflow_execution_projection_fields() -> tuple[str, ...]:
    fields = [
        "id",
        "status",
        "input_context",
        "error_code",
        "error_message",
        "error_details",
        "tenant_id",
        "execution_consumer",
        "workflow_template__name",
        "started_at",
    ]
    if "created_at" in {field.name for field in WorkflowExecution._meta.concrete_fields}:
        fields.append("created_at")
    return tuple(fields)


def _resolve_run_observability_fields(
    *,
    run: PoolRun,
    workflow_execution_consumer: str | None,
) -> dict[str, str | None]:
    workflow_execution_id = str(run.workflow_execution_id or "").strip()
    if not workflow_execution_id:
        return {
            "root_operation_id": None,
            "execution_consumer": None,
            "lane": None,
        }

    execution_consumer = str(workflow_execution_consumer or "").strip() or "pools"
    lane = "workflows" if execution_consumer == "pools" else execution_consumer
    return {
        "root_operation_id": workflow_execution_id,
        "execution_consumer": execution_consumer,
        "lane": lane,
    }


def _load_transition_workflow_candidates_for_run(run: PoolRun) -> list[dict[str, Any]]:
    execution_fields = _workflow_execution_projection_fields()
    transition_candidates = list(
        WorkflowExecution.objects.filter(
            execution_consumer="pools",
            input_context__pool_run_id=str(run.id),
        )
        .values(*execution_fields)
        .order_by("started_at", "id")
    )
    if run.workflow_execution_id and all(
        candidate.get("id") != run.workflow_execution_id for candidate in transition_candidates
    ):
        linked_execution = (
            WorkflowExecution.objects.filter(id=run.workflow_execution_id)
            .values(*execution_fields)
            .first()
        )
        if linked_execution:
            transition_candidates.append(linked_execution)
    return transition_candidates


def _select_tenant_scoped_workflow_candidates(
    *,
    run: PoolRun,
    transition_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    exact_tenant_candidates = [
        candidate
        for candidate in transition_candidates
        if candidate.get("tenant_id") == run.tenant_id
    ]
    if exact_tenant_candidates:
        return exact_tenant_candidates

    null_tenant_candidates = [
        candidate for candidate in transition_candidates if candidate.get("tenant_id") is None
    ]
    cross_tenant_candidates = [
        candidate
        for candidate in transition_candidates
        if candidate.get("tenant_id") not in {None, run.tenant_id}
    ]
    if null_tenant_candidates and not cross_tenant_candidates:
        return null_tenant_candidates
    return []


def _execution_attempt_number(candidate: dict[str, Any]) -> int | None:
    input_context = candidate.get("input_context")
    if not isinstance(input_context, dict):
        return None
    return _parse_positive_int(input_context.get("attempt_number"))


def _execution_sort_key_for_active(candidate: dict[str, Any]) -> tuple[int, str, str]:
    attempt_number = _execution_attempt_number(candidate) or 0
    started_at = candidate.get("started_at")
    started_at_sort = started_at.isoformat() if started_at else ""
    execution_id = str(candidate.get("id") or "")
    return (attempt_number, started_at_sort, execution_id)


def _select_active_workflow_execution_candidate(
    *,
    run: PoolRun,
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not candidates:
        return None
    if run.workflow_execution_id:
        for candidate in candidates:
            if candidate.get("id") == run.workflow_execution_id:
                return candidate
    return sorted(candidates, key=_execution_sort_key_for_active)[-1]


def _resolve_workflow_execution_for_projection(run: PoolRun) -> dict[str, Any] | None:
    transition_candidates = _load_transition_workflow_candidates_for_run(run=run)
    scoped_candidates = _select_tenant_scoped_workflow_candidates(
        run=run,
        transition_candidates=transition_candidates,
    )
    return _select_active_workflow_execution_candidate(run=run, candidates=scoped_candidates)


def _resolve_approval_state(
    *,
    run: PoolRun,
    workflow_status: str | None,
    workflow_input_context: dict[str, Any],
) -> str | None:
    if not run.workflow_execution_id:
        return None

    if run.mode == PoolRunMode.UNSAFE:
        return APPROVAL_STATE_NOT_REQUIRED

    approved_at_from_context = workflow_input_context.get("approved_at")
    if run.publication_confirmed_at is not None or _has_context_value(approved_at_from_context):
        return APPROVAL_STATE_APPROVED

    workflow_state = str(workflow_status or "").strip().lower()
    raw_state = str(workflow_input_context.get("approval_state") or "").strip().lower()
    if raw_state in _VALID_APPROVAL_STATES:
        if raw_state == APPROVAL_STATE_PREPARING and workflow_state == WorkflowExecution.STATUS_COMPLETED:
            return APPROVAL_STATE_AWAITING_APPROVAL
        if raw_state == APPROVAL_STATE_NOT_REQUIRED:
            return APPROVAL_STATE_PREPARING
        return raw_state

    if workflow_state == WorkflowExecution.STATUS_COMPLETED:
        return APPROVAL_STATE_AWAITING_APPROVAL
    return APPROVAL_STATE_PREPARING


def _resolve_publication_step_state(
    *,
    run: PoolRun,
    workflow_status: str | None,
    workflow_input_context: dict[str, Any],
    approval_state: str | None,
    execution_backend: str,
) -> str | None:
    if not run.workflow_execution_id:
        return None

    workflow_state = str(workflow_status or "").strip().lower()
    raw_state = str(workflow_input_context.get("publication_step_state") or "").strip().lower()

    if raw_state in _VALID_PUBLICATION_STEP_STATES:
        if (
            raw_state == PUBLICATION_STEP_STATE_NOT_ENQUEUED
            and approval_state in {APPROVAL_STATE_APPROVED, APPROVAL_STATE_NOT_REQUIRED}
        ):
            return PUBLICATION_STEP_STATE_QUEUED
        if (
            raw_state in {PUBLICATION_STEP_STATE_NOT_ENQUEUED, PUBLICATION_STEP_STATE_QUEUED}
            and run.publishing_started_at is not None
        ):
            return PUBLICATION_STEP_STATE_STARTED
        return raw_state

    if run.publishing_started_at is not None:
        return PUBLICATION_STEP_STATE_STARTED
    if approval_state in {APPROVAL_STATE_PREPARING, APPROVAL_STATE_AWAITING_APPROVAL}:
        return PUBLICATION_STEP_STATE_NOT_ENQUEUED
    if workflow_state == WorkflowExecution.STATUS_COMPLETED:
        if execution_backend == "workflow_core":
            return None
        return PUBLICATION_STEP_STATE_COMPLETED
    return PUBLICATION_STEP_STATE_QUEUED


def _resolve_terminal_reason(
    *,
    run: PoolRun,
    workflow_input_context: dict[str, Any],
) -> str | None:
    if not run.workflow_execution_id:
        return None
    raw_reason = str(workflow_input_context.get("terminal_reason") or "").strip().lower()
    return raw_reason or None


def _resolve_workflow_binding_read_model(
    *,
    run: PoolRun,
    workflow_input_context: dict[str, Any],
) -> dict[str, Any] | None:
    raw_binding = run.workflow_binding_snapshot
    if isinstance(raw_binding, Mapping) and raw_binding:
        try:
            binding = PoolWorkflowBindingContract(**dict(raw_binding))
            return build_pool_workflow_binding_read_model(
                binding=binding,
            )
        except Exception:
            pass
    raw_binding = workflow_input_context.get(POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY)
    if not isinstance(raw_binding, Mapping):
        return None
    try:
        binding = PoolWorkflowBindingContract(**dict(raw_binding))
        return build_pool_workflow_binding_read_model(
            binding=binding,
        )
    except Exception:
        return None


def _resolve_runtime_projection_read_model(
    *,
    run: PoolRun,
    workflow_input_context: dict[str, Any],
) -> dict[str, Any] | None:
    raw_projection = run.runtime_projection_snapshot
    if isinstance(raw_projection, Mapping) and raw_projection:
        try:
            return validate_pool_runtime_projection_v1(projection=raw_projection)
        except Exception:
            pass
    raw_projection = workflow_input_context.get(POOL_RUNTIME_PROJECTION_CONTEXT_KEY)
    if not isinstance(raw_projection, Mapping):
        return None
    try:
        return validate_pool_runtime_projection_v1(projection=raw_projection)
    except Exception:
        return None


def _execution_sort_key_for_lineage(candidate: dict[str, Any]) -> tuple[int, str, str]:
    attempt_number = _execution_attempt_number(candidate)
    attempt_sort = attempt_number if attempt_number is not None else 10**9
    started_at = candidate.get("started_at")
    started_at_sort = started_at.isoformat() if started_at else ""
    execution_id = str(candidate.get("id") or "")
    return (attempt_sort, started_at_sort, execution_id)


def _build_retry_chain_from_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    retry_chain: list[dict[str, Any]] = []
    ordered_candidates = sorted(candidates, key=_execution_sort_key_for_lineage)
    previous_workflow_run_id: str | None = None
    next_attempt_number = 1
    root_workflow_run_id: str | None = None

    for candidate in ordered_candidates:
        workflow_run_id = _normalize_workflow_run_id(candidate.get("id"))
        if not workflow_run_id:
            continue

        input_context = candidate.get("input_context")
        context = input_context if isinstance(input_context, dict) else {}
        explicit_root_workflow_run_id = _normalize_workflow_run_id(
            context.get("root_workflow_run_id")
        )
        if root_workflow_run_id is None:
            root_workflow_run_id = explicit_root_workflow_run_id or workflow_run_id

        explicit_attempt_number = _parse_positive_int(context.get("attempt_number"))
        attempt_number = explicit_attempt_number if explicit_attempt_number is not None else next_attempt_number
        if attempt_number < next_attempt_number:
            attempt_number = next_attempt_number

        if previous_workflow_run_id is None:
            attempt_number = 1
            attempt_kind = ATTEMPT_KIND_INITIAL
            parent_workflow_run_id = None
        else:
            attempt_kind = _normalize_attempt_kind(context.get("attempt_kind")) or ATTEMPT_KIND_RETRY
            parent_workflow_run_id = (
                _normalize_workflow_run_id(context.get("parent_workflow_run_id"))
                or previous_workflow_run_id
            )

        status_value = str(candidate.get("status") or "").strip() or WorkflowExecution.STATUS_PENDING
        retry_chain.append(
            {
                "workflow_run_id": workflow_run_id,
                "parent_workflow_run_id": parent_workflow_run_id,
                "attempt_number": attempt_number,
                "attempt_kind": attempt_kind,
                "status": status_value,
            }
        )
        previous_workflow_run_id = workflow_run_id
        next_attempt_number = attempt_number + 1

    return retry_chain


def _build_run_provenance(
    *,
    run: PoolRun,
    workflow_status: str | None,
    execution_backend: str,
    observability_fields: Mapping[str, Any],
) -> dict[str, Any]:
    transition_candidates = _load_transition_workflow_candidates_for_run(run=run)
    scoped_candidates = _select_tenant_scoped_workflow_candidates(
        run=run,
        transition_candidates=transition_candidates,
    )
    retry_chain = _build_retry_chain_from_candidates(scoped_candidates)

    workflow_run_id = retry_chain[0]["workflow_run_id"] if retry_chain else None
    active_status = str(workflow_status or run.workflow_status or "").strip()
    if not active_status and retry_chain:
        active_status = str(retry_chain[-1].get("status") or "").strip()
    if workflow_run_id and not active_status:
        active_status = WorkflowExecution.STATUS_PENDING

    return {
        "workflow_run_id": workflow_run_id,
        "workflow_status": active_status or None,
        "execution_backend": execution_backend,
        "retry_chain": retry_chain,
        "root_operation_id": observability_fields.get("root_operation_id"),
        "execution_consumer": observability_fields.get("execution_consumer"),
        "lane": observability_fields.get("lane"),
    }


def _has_context_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _normalize_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if timezone.is_naive(value):
        return value.replace(tzinfo=dt_timezone.utc)
    return value.astimezone(dt_timezone.utc)


def _is_historical_workflow_core_projection(
    *,
    projection_timestamp: datetime | None,
    publication_hardening_cutoff_utc: datetime | None,
) -> bool:
    # Rollback-safe default: until cutoff is configured, keep legacy projection for historical null-state runs.
    normalized_cutoff = _normalize_utc_datetime(publication_hardening_cutoff_utc)
    if normalized_cutoff is None:
        return True

    normalized_projection_ts = _normalize_utc_datetime(projection_timestamp)
    if normalized_projection_ts is None:
        return True

    return normalized_projection_ts < normalized_cutoff


def _resolve_publication_hardening_cutoff_utc(*, tenant_id: str | None) -> datetime | None:
    try:
        effective = get_effective_runtime_setting(POOL_PROJECTION_HARDENING_CUTOFF_KEY, tenant_id)
    except Exception:
        return None
    return _parse_publication_hardening_cutoff_utc(effective.value)


def _parse_publication_hardening_cutoff_utc(raw_value: object) -> datetime | None:
    token = str(raw_value or "").strip()
    if not token:
        return None

    normalized_token = token[:-1] + "+00:00" if token.endswith("Z") else token
    try:
        parsed = datetime.fromisoformat(normalized_token)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return None
    if parsed.utcoffset() != timedelta(0):
        return None

    return parsed.astimezone(dt_timezone.utc)


def _project_pool_status(
    *,
    run: PoolRun,
    workflow_status: str | None,
    approval_state: str | None,
    publication_step_state: str | None,
    execution_backend: str,
    projection_timestamp: datetime | None,
    publication_hardening_cutoff_utc: datetime | None,
) -> tuple[str, str | None]:
    status = run.status
    status_reason: str | None = None
    workflow_state = str(workflow_status or "").strip().lower()
    failed_targets = int((run.publication_summary or {}).get("failed_targets") or 0)
    safe_unapproved = run.mode == PoolRunMode.SAFE and run.publication_confirmed_at is None

    if workflow_state in {WorkflowExecution.STATUS_FAILED, WorkflowExecution.STATUS_CANCELLED}:
        return PoolRun.STATUS_FAILED, None

    if safe_unapproved and approval_state in {
        APPROVAL_STATE_PREPARING,
        APPROVAL_STATE_AWAITING_APPROVAL,
    }:
        status_reason = (
            "preparing"
            if approval_state == APPROVAL_STATE_PREPARING
            else "awaiting_approval"
        )
        if workflow_state in {
            WorkflowExecution.STATUS_PENDING,
            WorkflowExecution.STATUS_RUNNING,
            WorkflowExecution.STATUS_COMPLETED,
            "queued",
        }:
            return PoolRun.STATUS_VALIDATED, status_reason

    if (
        workflow_state in {
            WorkflowExecution.STATUS_PENDING,
            WorkflowExecution.STATUS_RUNNING,
            "queued",
        }
        and
        publication_step_state == PUBLICATION_STEP_STATE_STARTED
        and approval_state in {APPROVAL_STATE_APPROVED, APPROVAL_STATE_NOT_REQUIRED}
    ):
        return PoolRun.STATUS_PUBLISHING, None

    if workflow_state == WorkflowExecution.STATUS_COMPLETED:
        if publication_step_state == PUBLICATION_STEP_STATE_COMPLETED:
            if failed_targets > 0:
                return PoolRun.STATUS_PARTIAL_SUCCESS, None
            return PoolRun.STATUS_PUBLISHED, None

        if publication_step_state is None:
            if execution_backend == "workflow_core":
                if _is_historical_workflow_core_projection(
                    projection_timestamp=projection_timestamp,
                    publication_hardening_cutoff_utc=publication_hardening_cutoff_utc,
                ):
                    if failed_targets > 0:
                        return PoolRun.STATUS_PARTIAL_SUCCESS, None
                    return PoolRun.STATUS_PUBLISHED, None
                return PoolRun.STATUS_FAILED, None
            if failed_targets > 0:
                return PoolRun.STATUS_PARTIAL_SUCCESS, None
            return PoolRun.STATUS_PUBLISHED, None
        return PoolRun.STATUS_FAILED, None

    if workflow_state in {
        WorkflowExecution.STATUS_PENDING,
        WorkflowExecution.STATUS_RUNNING,
        "queued",
    }:
        if publication_step_state == PUBLICATION_STEP_STATE_STARTED:
            return PoolRun.STATUS_PUBLISHING, None
        return PoolRun.STATUS_VALIDATED, "queued"

    if status == PoolRun.STATUS_VALIDATED:
        if run.mode == PoolRunMode.SAFE and run.publication_confirmed_at is None:
            if approval_state == APPROVAL_STATE_AWAITING_APPROVAL:
                status_reason = "awaiting_approval"
            else:
                status_reason = "preparing"
        else:
            status_reason = "queued"
    return status, status_reason


def _sanitize_diagnostics_message(raw_message: object) -> str:
    message = str(raw_message or "").strip()
    if not message:
        return ""

    compact = " ".join(message.split())
    lowered = compact.lower()
    has_stack_trace_hint = (
        "traceback" in lowered
        or "stack trace" in lowered
        or ('file "' in lowered and " line " in lowered)
    )
    if has_stack_trace_hint:
        return "internal_error"

    redacted = _SENSITIVE_TOKEN_PATTERN.sub(r"\1=[REDACTED]", compact)
    redacted = _UUID_PATTERN.sub("[REDACTED_ID]", redacted)
    if len(redacted) > 512:
        return f"{redacted[:509]}..."
    return redacted


def _build_attempt_payload_summary(attempt: PoolPublicationAttempt) -> dict[str, Any]:
    payload_summary: dict[str, Any] = {
        "documents_count": attempt.documents_count,
        "entity_name": attempt.entity_name,
    }
    request_summary = attempt.request_summary if isinstance(attempt.request_summary, dict) else {}
    requested_count = _parse_positive_int(request_summary.get("documents_count"))
    if requested_count is not None:
        payload_summary["requested_documents_count"] = requested_count
    response_summary = attempt.response_summary if isinstance(attempt.response_summary, dict) else {}
    posted = response_summary.get("posted")
    if isinstance(posted, bool):
        payload_summary["posted"] = posted
    return payload_summary


def _build_attempt_http_error(
    *,
    http_status_value: int | None,
    domain_error_code: str,
    domain_error_message: str,
) -> dict[str, Any] | None:
    if http_status_value is None:
        return None
    payload: dict[str, Any] = {"status": int(http_status_value)}
    if domain_error_code:
        payload["code"] = domain_error_code
    if domain_error_message:
        payload["message"] = domain_error_message
    return payload


def _build_attempt_transport_error(
    *,
    http_status_value: int | None,
    domain_error_code: str,
    domain_error_message: str,
) -> dict[str, Any] | None:
    if http_status_value is not None:
        return None
    if not domain_error_code and not domain_error_message:
        return None
    payload: dict[str, Any] = {}
    if domain_error_code:
        payload["code"] = domain_error_code
    if domain_error_message:
        payload["message"] = domain_error_message
    return payload


def _serialize_attempt(attempt: PoolPublicationAttempt) -> dict[str, Any]:
    domain_error_code = str(attempt.error_code or "").strip()
    domain_error_message = _sanitize_diagnostics_message(attempt.error_message)
    http_status_value = attempt.http_status
    return {
        "id": str(attempt.id),
        "run_id": str(attempt.run_id),
        "target_database_id": str(attempt.target_database_id),
        "attempt_number": attempt.attempt_number,
        "attempt_timestamp": attempt.started_at or attempt.created_at,
        "status": attempt.status,
        "entity_name": attempt.entity_name,
        "documents_count": attempt.documents_count,
        "payload_summary": _build_attempt_payload_summary(attempt),
        "http_error": _build_attempt_http_error(
            http_status_value=http_status_value,
            domain_error_code=domain_error_code,
            domain_error_message=domain_error_message,
        ),
        "transport_error": _build_attempt_transport_error(
            http_status_value=http_status_value,
            domain_error_code=domain_error_code,
            domain_error_message=domain_error_message,
        ),
        "domain_error_code": domain_error_code,
        "domain_error_message": domain_error_message,
        "external_document_identity": attempt.external_document_identity,
        "publication_identity_strategy": attempt.identity_strategy,
        "posted": attempt.posted,
        "request_summary": attempt.request_summary,
        "response_summary": attempt.response_summary,
        "started_at": attempt.started_at,
        "finished_at": attempt.finished_at,
        "created_at": attempt.created_at,
    }


def _serialize_audit_event(event: PoolRunAuditEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "status_before": event.status_before,
        "status_after": event.status_after,
        "payload": event.payload,
        "actor_id": str(event.actor_id) if event.actor_id else None,
        "created_at": event.created_at,
    }


def _serialize_schema_template(template: PoolSchemaTemplate) -> dict[str, Any]:
    metadata = template.metadata if isinstance(template.metadata, dict) else {}
    workflow_template_id = metadata.get("workflow_template_id")
    workflow_template_id_str = str(workflow_template_id).strip() if workflow_template_id is not None else None
    if not workflow_template_id_str:
        workflow_template_id_str = None
    return {
        "id": str(template.id),
        "tenant_id": str(template.tenant_id),
        "code": template.code,
        "name": template.name,
        "format": template.format,
        "is_public": template.is_public,
        "is_active": template.is_active,
        "schema": template.schema if isinstance(template.schema, dict) else {},
        "metadata": metadata,
        "workflow_template_id": workflow_template_id_str,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


def _serialize_organization_pool(pool: OrganizationPool) -> dict[str, Any]:
    metadata = dict(pool.metadata) if isinstance(pool.metadata, dict) else {}
    metadata.pop("workflow_bindings", None)
    workflow_bindings: list[dict[str, Any]] = []
    try:
        workflow_bindings = list_attached_pool_workflow_bindings(pool=pool)
    except PoolWorkflowBindingStoreError as exc:
        error_code, detail = _resolve_pool_workflow_binding_validation_error(exc)
        metadata["workflow_bindings_read_error"] = {
            "code": error_code,
            "detail": detail,
        }
    return {
        "id": str(pool.id),
        "code": pool.code,
        "name": pool.name,
        "description": pool.description,
        "is_active": pool.is_active,
        "metadata": metadata,
        "workflow_bindings": workflow_bindings,
        "updated_at": pool.updated_at,
    }


def _serialize_organization(organization: Organization) -> dict[str, Any]:
    return {
        "id": str(organization.id),
        "tenant_id": str(organization.tenant_id),
        "database_id": str(organization.database_id) if organization.database_id else None,
        "master_party_id": str(organization.master_party_id) if organization.master_party_id else None,
        "name": organization.name,
        "full_name": organization.full_name,
        "inn": organization.inn,
        "kpp": organization.kpp,
        "status": organization.status,
        "external_ref": organization.external_ref,
        "metadata": organization.metadata if isinstance(organization.metadata, dict) else {},
        "created_at": organization.created_at,
        "updated_at": organization.updated_at,
    }


class PoolRunRetryChainAttemptSerializer(serializers.Serializer):
    workflow_run_id = serializers.UUIDField()
    parent_workflow_run_id = serializers.UUIDField(required=False, allow_null=True)
    attempt_number = serializers.IntegerField(min_value=1)
    attempt_kind = serializers.ChoiceField(choices=[ATTEMPT_KIND_INITIAL, ATTEMPT_KIND_RETRY])
    status = serializers.CharField()


class PoolRunProvenanceSerializer(serializers.Serializer):
    workflow_run_id = serializers.UUIDField(required=False, allow_null=True)
    workflow_status = serializers.CharField(required=False, allow_null=True)
    execution_backend = serializers.CharField()
    retry_chain = PoolRunRetryChainAttemptSerializer(many=True)
    root_operation_id = serializers.CharField(required=False, allow_null=True)
    execution_consumer = serializers.CharField(required=False, allow_null=True)
    lane = serializers.CharField(required=False, allow_null=True)
    legacy_reference = serializers.CharField(required=False, allow_null=True)


class PoolRunMasterDataGateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            MASTER_DATA_GATE_STATUS_COMPLETED,
            MASTER_DATA_GATE_STATUS_FAILED,
            MASTER_DATA_GATE_STATUS_SKIPPED,
        ]
    )
    mode = serializers.ChoiceField(choices=[MASTER_DATA_GATE_READ_MODEL_MODE])
    targets_count = serializers.IntegerField(min_value=0)
    bindings_count = serializers.IntegerField(min_value=0)
    error_code = serializers.CharField(required=False, allow_null=True)
    detail = serializers.CharField(required=False, allow_null=True)
    diagnostic = serializers.JSONField(required=False, allow_null=True)


class PoolRunReadinessBlockerSerializer(serializers.Serializer):
    code = serializers.CharField(required=False, allow_null=True)
    detail = serializers.CharField(required=False, allow_null=True)
    kind = serializers.CharField(required=False, allow_null=True)
    entity_name = serializers.CharField(required=False, allow_null=True)
    field_or_table_path = serializers.CharField(required=False, allow_null=True)
    database_id = serializers.UUIDField(required=False, allow_null=True)
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    diagnostic = serializers.JSONField(required=False, allow_null=True)


class PoolRunConfirmPublicationReadinessProblemDetailsSerializer(serializers.Serializer):
    type = serializers.CharField(default="about:blank")
    title = serializers.CharField()
    status = serializers.IntegerField()
    detail = serializers.CharField()
    code = serializers.CharField()
    errors = PoolRunReadinessBlockerSerializer(many=True, required=False, default=list)


class PoolRunReadinessCheckSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=list(READINESS_CHECK_CODES))
    status = serializers.ChoiceField(choices=[READINESS_STATUS_READY, READINESS_STATUS_NOT_READY])
    blocker_codes = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    blockers = PoolRunReadinessBlockerSerializer(many=True, required=False, default=list)


class PoolRunReadinessChecklistSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[READINESS_STATUS_READY, READINESS_STATUS_NOT_READY])
    checks = PoolRunReadinessCheckSerializer(many=True, required=False, default=list)


class PoolRunVerificationMismatchSerializer(serializers.Serializer):
    database_id = serializers.UUIDField(required=False, allow_null=True)
    entity_name = serializers.CharField(required=False, allow_null=True)
    document_idempotency_key = serializers.CharField(required=False, allow_null=True)
    field_or_table_path = serializers.CharField(required=False, allow_null=True)
    kind = serializers.CharField(required=False, allow_null=True)


class PoolRunVerificationSummarySerializer(serializers.Serializer):
    checked_targets = serializers.IntegerField(min_value=0)
    verified_documents = serializers.IntegerField(min_value=0)
    mismatches_count = serializers.IntegerField(min_value=0)
    mismatches = PoolRunVerificationMismatchSerializer(many=True)


class WorkflowDefinitionRefInputSerializer(serializers.Serializer):
    contract_version = serializers.CharField(required=False)
    workflow_definition_key = serializers.CharField()
    workflow_revision_id = serializers.CharField()
    workflow_revision = serializers.IntegerField(min_value=1)
    workflow_name = serializers.CharField()


class PoolWorkflowBindingDecisionRefInputSerializer(serializers.Serializer):
    decision_table_id = serializers.CharField()
    decision_key = serializers.CharField()
    slot_key = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    decision_revision = serializers.IntegerField(min_value=1)


class PoolWorkflowBindingSelectorInputSerializer(serializers.Serializer):
    direction = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    mode = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    tags = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class PoolWorkflowBindingProfileLifecycleWarningSerializer(serializers.Serializer):
    code = serializers.CharField()
    title = serializers.CharField()
    detail = serializers.CharField()


class PoolWorkflowBindingResolvedProfileSerializer(serializers.Serializer):
    binding_profile_id = serializers.CharField()
    code = serializers.CharField()
    name = serializers.CharField()
    status = serializers.CharField()
    binding_profile_revision_id = serializers.CharField()
    binding_profile_revision_number = serializers.IntegerField(min_value=1)
    workflow = WorkflowDefinitionRefInputSerializer()
    decisions = PoolWorkflowBindingDecisionRefInputSerializer(many=True, required=False, default=list)
    parameters = serializers.JSONField(required=False, default=dict)
    role_mapping = serializers.DictField(
        child=serializers.CharField(),
        required=False,
        default=dict,
    )


class PoolWorkflowBindingInputSerializer(serializers.Serializer):
    contract_version = serializers.CharField(required=False, allow_blank=False, default="pool_workflow_binding.v2")
    binding_id = serializers.CharField(required=False, allow_blank=False)
    pool_id = serializers.UUIDField(required=False)
    revision = serializers.IntegerField(min_value=1, required=False)
    binding_profile_revision_id = serializers.CharField(required=True, allow_blank=False)
    selector = PoolWorkflowBindingSelectorInputSerializer(required=False, default=dict)
    effective_from = serializers.DateField()
    effective_to = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=["draft", "active", "inactive"],
        required=False,
        default="draft",
    )

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            forbidden_fields = [
                key
                for key in ("workflow", "decisions", "parameters", "role_mapping")
                if key in data
            ]
            if forbidden_fields:
                raise serializers.ValidationError(
                    {
                        key: [
                            "Attachment contract does not support local workflow logic overrides. "
                            "Create or revise a reusable binding profile instead."
                        ]
                        for key in forbidden_fields
                    }
                )
        return super().to_internal_value(data)


class PoolWorkflowBindingReadSerializer(PoolWorkflowBindingInputSerializer):
    contract_version = serializers.CharField(required=True, allow_blank=False)
    binding_id = serializers.CharField(required=True, allow_blank=False)
    pool_id = serializers.UUIDField(required=True)
    binding_profile_id = serializers.CharField(required=True, allow_blank=False)
    binding_profile_revision_id = serializers.CharField(required=True, allow_blank=False)
    binding_profile_revision_number = serializers.IntegerField(min_value=1, required=True)
    revision = serializers.IntegerField(min_value=1, required=True)
    status = serializers.ChoiceField(
        choices=["draft", "active", "inactive"],
        required=True,
    )
    resolved_profile = PoolWorkflowBindingResolvedProfileSerializer(required=True)
    profile_lifecycle_warning = PoolWorkflowBindingProfileLifecycleWarningSerializer(
        required=False,
        allow_null=True,
    )


class PoolRunSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    pool_id = serializers.UUIDField()
    schema_template_id = serializers.UUIDField(required=False, allow_null=True)
    mode = serializers.CharField()
    direction = serializers.CharField()
    status = serializers.CharField()
    status_reason = serializers.CharField(required=False, allow_null=True)
    period_start = serializers.DateField()
    period_end = serializers.DateField(required=False, allow_null=True)
    run_input = serializers.JSONField(required=False, allow_null=True)
    input_contract_version = serializers.ChoiceField(
        choices=[RUN_INPUT_CONTRACT_VERSION_V1, RUN_INPUT_CONTRACT_VERSION_LEGACY],
        required=False,
    )
    idempotency_key = serializers.CharField()
    workflow_execution_id = serializers.UUIDField(required=False, allow_null=True)
    workflow_status = serializers.CharField(required=False, allow_null=True)
    root_operation_id = serializers.CharField(required=False, allow_null=True)
    execution_consumer = serializers.CharField(required=False, allow_null=True)
    lane = serializers.CharField(required=False, allow_null=True)
    approval_state = serializers.CharField(required=False, allow_null=True)
    publication_step_state = serializers.CharField(required=False, allow_null=True)
    master_data_gate = PoolRunMasterDataGateSerializer(required=False, allow_null=True)
    readiness_blockers = PoolRunReadinessBlockerSerializer(many=True, required=False, default=list)
    readiness_checklist = PoolRunReadinessChecklistSerializer(required=False)
    verification_status = serializers.ChoiceField(
        choices=[VERIFICATION_STATUS_NOT_VERIFIED, VERIFICATION_STATUS_PASSED, VERIFICATION_STATUS_FAILED],
        required=False,
        allow_null=True,
    )
    verification_summary = PoolRunVerificationSummarySerializer(required=False, allow_null=True)
    terminal_reason = serializers.CharField(required=False, allow_null=True)
    execution_backend = serializers.CharField(required=False, allow_null=True)
    provenance = PoolRunProvenanceSerializer(required=False)
    workflow_binding = PoolWorkflowBindingReadSerializer(required=False, allow_null=True)
    runtime_projection = serializers.JSONField(required=False, allow_null=True)
    workflow_template_name = serializers.CharField(required=False, allow_null=True)
    seed = serializers.IntegerField(required=False, allow_null=True)
    validation_summary = serializers.JSONField(required=False)
    publication_summary = serializers.JSONField(required=False)
    diagnostics = serializers.JSONField(required=False)
    last_error = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)
    validated_at = serializers.DateTimeField(required=False, allow_null=True)
    publication_confirmed_at = serializers.DateTimeField(required=False, allow_null=True)
    publishing_started_at = serializers.DateTimeField(required=False, allow_null=True)
    completed_at = serializers.DateTimeField(required=False, allow_null=True)


class PoolPublicationAttemptSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    run_id = serializers.UUIDField()
    target_database_id = serializers.CharField()
    attempt_number = serializers.IntegerField()
    attempt_timestamp = serializers.DateTimeField(required=False, allow_null=True)
    status = serializers.CharField()
    entity_name = serializers.CharField()
    documents_count = serializers.IntegerField()
    payload_summary = serializers.JSONField(required=False)
    http_error = serializers.JSONField(required=False, allow_null=True)
    transport_error = serializers.JSONField(required=False, allow_null=True)
    domain_error_code = serializers.CharField(required=False, allow_blank=True)
    domain_error_message = serializers.CharField(required=False, allow_blank=True)
    external_document_identity = serializers.CharField(required=False, allow_blank=True)
    publication_identity_strategy = serializers.CharField(required=False, allow_blank=True)
    posted = serializers.BooleanField()
    request_summary = serializers.JSONField(required=False)
    response_summary = serializers.JSONField(required=False)
    started_at = serializers.DateTimeField(required=False)
    finished_at = serializers.DateTimeField(required=False, allow_null=True)
    created_at = serializers.DateTimeField(required=False)


class PoolRunAuditEventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_type = serializers.CharField()
    status_before = serializers.CharField(required=False, allow_blank=True)
    status_after = serializers.CharField(required=False, allow_blank=True)
    payload = serializers.JSONField(required=False)
    actor_id = serializers.UUIDField(required=False, allow_null=True)
    created_at = serializers.DateTimeField(required=False)


class PoolRunCreateRequestSerializer(serializers.Serializer):
    pool_id = serializers.UUIDField()
    pool_workflow_binding_id = serializers.CharField(required=True, allow_blank=False)
    direction = serializers.ChoiceField(choices=PoolRunDirection.values)
    period_start = serializers.DateField()
    period_end = serializers.DateField(required=False, allow_null=True)
    run_input = serializers.JSONField(required=True)
    mode = serializers.ChoiceField(choices=PoolRunMode.values, required=False, default=PoolRunMode.SAFE)
    schema_template_id = serializers.UUIDField(required=False, allow_null=True)
    seed = serializers.IntegerField(required=False, allow_null=True)
    validation_summary = serializers.JSONField(required=False, default=dict)
    diagnostics = serializers.ListField(child=serializers.JSONField(), required=False, default=list)

    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError("Invalid payload type. Expected object.")
        unknown_fields = sorted({str(field) for field in data.keys() if str(field) not in self.fields})
        if unknown_fields:
            raise serializers.ValidationError({field: "Unknown field." for field in unknown_fields})
        return super().to_internal_value(data)

    def validate(self, attrs):
        direction = attrs.get("direction")
        run_input = attrs.get("run_input")

        if not isinstance(run_input, dict):
            raise serializers.ValidationError({"run_input": "run_input must be an object."})

        if direction == PoolRunDirection.TOP_DOWN:
            raw_starting_amount = run_input.get("starting_amount")
            if raw_starting_amount in {None, ""}:
                raise serializers.ValidationError(
                    {"run_input": "top_down run_input must contain required field 'starting_amount'."}
                )
            try:
                starting_amount = Decimal(str(raw_starting_amount))
            except (InvalidOperation, TypeError, ValueError):
                raise serializers.ValidationError(
                    {"run_input": "top_down starting_amount must be a valid decimal value."}
                ) from None
            if starting_amount <= 0:
                raise serializers.ValidationError(
                    {"run_input": "top_down starting_amount must be greater than 0."}
                )

        if direction == PoolRunDirection.BOTTOM_UP:
            source_payload = run_input.get("source_payload")
            source_artifact_id = str(run_input.get("source_artifact_id") or "").strip()
            has_source_payload = source_payload is not None
            has_source_artifact = bool(source_artifact_id)
            if not has_source_payload and not has_source_artifact:
                raise serializers.ValidationError(
                    {
                        "run_input": (
                            "bottom_up run_input must contain source_payload "
                            "or source_artifact_id."
                        )
                    }
                )
            if has_source_payload and not isinstance(source_payload, (dict, list)):
                raise serializers.ValidationError(
                    {"run_input": "bottom_up source_payload must be object or array."}
                )

        return attrs


class PoolRunCreateResponseSerializer(serializers.Serializer):
    run = PoolRunSerializer()
    created = serializers.BooleanField()


class PoolWorkflowBindingPreviewRequestSerializer(PoolRunCreateRequestSerializer):
    pool_workflow_binding_id = serializers.CharField(required=True, allow_blank=False)


class PoolWorkflowBindingPreviewResponseSerializer(serializers.Serializer):
    workflow_binding = PoolWorkflowBindingReadSerializer()
    compiled_document_policy_slots = serializers.JSONField()
    compiled_document_policy = serializers.JSONField(required=False)
    slot_coverage_summary = serializers.JSONField()
    runtime_projection = serializers.JSONField()


class PoolRunListResponseSerializer(serializers.Serializer):
    runs = PoolRunSerializer(many=True)
    count = serializers.IntegerField()


class PoolRunDetailResponseSerializer(serializers.Serializer):
    run = PoolRunSerializer()
    publication_attempts = PoolPublicationAttemptSerializer(many=True)
    audit_events = PoolRunAuditEventSerializer(many=True)


class PoolRunRetryRequestSerializer(serializers.Serializer):
    entity_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    documents_by_database = serializers.DictField(
        child=serializers.ListField(child=serializers.JSONField()),
        required=False,
        allow_empty=True,
        default=dict,
    )
    target_database_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=False,
    )
    max_attempts = serializers.IntegerField(
        required=False,
        default=MAX_PUBLICATION_ATTEMPTS,
        min_value=1,
        max_value=MAX_PUBLICATION_ATTEMPTS,
    )
    retry_interval_seconds = serializers.IntegerField(
        required=False,
        default=0,
        min_value=0,
        max_value=MAX_RETRY_INTERVAL_SECONDS,
    )
    external_key_field = serializers.CharField(required=False, default="ExternalRunKey")
    use_retry_subset_payload = serializers.BooleanField(required=False, default=False)


class PoolRunRetryTargetSummarySerializer(serializers.Serializer):
    requested_targets = serializers.IntegerField()
    requested_documents = serializers.IntegerField()
    failed_targets = serializers.IntegerField()
    enqueued_targets = serializers.IntegerField()
    skipped_successful_targets = serializers.IntegerField()


class PoolRunRetryAcceptedResponseSerializer(serializers.Serializer):
    accepted = serializers.BooleanField()
    workflow_execution_id = serializers.UUIDField()
    operation_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    retry_target_summary = PoolRunRetryTargetSummarySerializer()


class PoolRunSafeCommandResponseSerializer(serializers.Serializer):
    run = PoolRunSerializer()
    command_type = serializers.CharField()
    result = serializers.CharField()
    replayed = serializers.BooleanField()


class PoolRunSafeCommandConflictSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    error_code = serializers.CharField()
    error_message = serializers.CharField()
    conflict_reason = serializers.CharField()
    retryable = serializers.BooleanField()
    run_id = serializers.UUIDField()


class PoolSchemaTemplateSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    format = serializers.CharField()
    is_public = serializers.BooleanField()
    is_active = serializers.BooleanField()
    schema = serializers.JSONField(required=False)
    metadata = serializers.JSONField(required=False)
    workflow_template_id = serializers.UUIDField(required=False, allow_null=True)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class PoolSchemaTemplateListResponseSerializer(serializers.Serializer):
    templates = PoolSchemaTemplateSerializer(many=True)
    count = serializers.IntegerField()


class PoolSchemaTemplateCreateRequestSerializer(serializers.Serializer):
    code = serializers.SlugField(max_length=64)
    name = serializers.CharField(max_length=255)
    format = serializers.ChoiceField(choices=PoolSchemaTemplateFormat.values)
    is_public = serializers.BooleanField(required=False, default=True)
    is_active = serializers.BooleanField(required=False, default=True)
    schema = serializers.JSONField(required=False, default=dict)
    metadata = serializers.JSONField(required=False, default=dict)
    workflow_template_id = serializers.UUIDField(required=False, allow_null=True)


class PoolSchemaTemplateUpdateRequestSerializer(PoolSchemaTemplateCreateRequestSerializer):
    pass


class PoolSchemaTemplateCreateResponseSerializer(serializers.Serializer):
    template = PoolSchemaTemplateSerializer()


class OrganizationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    database_id = serializers.UUIDField(required=False, allow_null=True)
    master_party_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField()
    full_name = serializers.CharField(required=False, allow_blank=True)
    inn = serializers.CharField()
    kpp = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField()
    external_ref = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class OrganizationListResponseSerializer(serializers.Serializer):
    organizations = OrganizationSerializer(many=True)
    count = serializers.IntegerField()


class OrganizationDetailResponseSerializer(serializers.Serializer):
    organization = OrganizationSerializer()
    pool_bindings = serializers.ListField(child=serializers.JSONField(), required=False)


class OrganizationUpsertRequestSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField(required=False)
    inn = serializers.CharField(max_length=12)
    name = serializers.CharField(max_length=255)
    full_name = serializers.CharField(required=False, allow_blank=True, default="")
    kpp = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(choices=OrganizationStatus.values, required=False)
    database_id = serializers.UUIDField(required=False, allow_null=True)
    master_party_id = serializers.UUIDField(required=False, allow_null=True)
    external_ref = serializers.CharField(required=False, allow_blank=True, default="")
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be an object")
        return value


class OrganizationUpsertResponseSerializer(serializers.Serializer):
    organization = OrganizationSerializer()
    created = serializers.BooleanField()


class OrganizationSyncRequestSerializer(serializers.Serializer):
    rows = serializers.ListField(child=serializers.JSONField(), allow_empty=False)


class OrganizationSyncResponseSerializer(serializers.Serializer):
    stats = serializers.JSONField()
    total_rows = serializers.IntegerField()


class OrganizationPoolSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField()
    metadata = serializers.JSONField(required=False)
    workflow_bindings = serializers.ListField(child=serializers.JSONField(), required=False)
    updated_at = serializers.DateTimeField(required=False)


class OrganizationPoolListResponseSerializer(serializers.Serializer):
    pools = OrganizationPoolSerializer(many=True)
    count = serializers.IntegerField()


class PoolWorkflowBindingScopeQuerySerializer(serializers.Serializer):
    pool_id = serializers.UUIDField()


class PoolWorkflowBindingDeleteQuerySerializer(serializers.Serializer):
    pool_id = serializers.UUIDField()
    revision = serializers.IntegerField(min_value=1)


class PoolWorkflowBindingBlockingRemediationSerializer(serializers.Serializer):
    code = serializers.CharField()
    title = serializers.CharField()
    detail = serializers.CharField()


class PoolWorkflowBindingCollectionResponseSerializer(serializers.Serializer):
    pool_id = serializers.UUIDField()
    workflow_bindings = PoolWorkflowBindingReadSerializer(many=True)
    collection_etag = serializers.CharField()
    blocking_remediation = PoolWorkflowBindingBlockingRemediationSerializer(
        required=False,
        allow_null=True,
    )


class PoolWorkflowBindingCollectionReplaceRequestSerializer(serializers.Serializer):
    pool_id = serializers.UUIDField()
    expected_collection_etag = serializers.CharField(allow_blank=False)
    workflow_bindings = PoolWorkflowBindingInputSerializer(many=True)


class PoolWorkflowBindingDetailResponseSerializer(serializers.Serializer):
    pool_id = serializers.UUIDField()
    workflow_binding = PoolWorkflowBindingReadSerializer()


class PoolWorkflowBindingUpsertRequestSerializer(serializers.Serializer):
    pool_id = serializers.UUIDField()
    workflow_binding = PoolWorkflowBindingInputSerializer()


class PoolWorkflowBindingUpsertResponseSerializer(serializers.Serializer):
    pool_id = serializers.UUIDField()
    workflow_binding = PoolWorkflowBindingReadSerializer()
    created = serializers.BooleanField()


class PoolWorkflowBindingDeleteResponseSerializer(serializers.Serializer):
    pool_id = serializers.UUIDField()
    workflow_binding = PoolWorkflowBindingReadSerializer()
    deleted = serializers.BooleanField()


class OrganizationPoolUpsertRequestSerializer(serializers.Serializer):
    pool_id = serializers.UUIDField(required=False)
    code = serializers.SlugField(max_length=64)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    is_active = serializers.BooleanField(required=False, default=True)
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be an object")
        if "workflow_bindings" in value:
            raise serializers.ValidationError(
                "workflow_bindings must be managed via /api/v2/pools/workflow-bindings/."
            )
        return value

    def validate(self, attrs):
        if isinstance(self.initial_data, Mapping) and "workflow_bindings" in self.initial_data:
            raise serializers.ValidationError(
                {
                    "workflow_bindings": [
                        "workflow_bindings must be managed via /api/v2/pools/workflow-bindings/."
                    ]
                }
            )
        return attrs


class OrganizationPoolUpsertResponseSerializer(serializers.Serializer):
    pool = OrganizationPoolSerializer()
    created = serializers.BooleanField()


class PoolTopologySnapshotNodeInputSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    is_root = serializers.BooleanField(required=False, default=False)
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be an object")
        return value


class PoolTopologySnapshotEdgeInputSerializer(serializers.Serializer):
    parent_organization_id = serializers.UUIDField()
    child_organization_id = serializers.UUIDField()
    weight = serializers.DecimalField(max_digits=12, decimal_places=6, required=False, default=1)
    min_amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, allow_null=True)
    max_amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, allow_null=True)
    metadata = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs):
        if attrs.get("parent_organization_id") == attrs.get("child_organization_id"):
            raise serializers.ValidationError("Edge cannot reference the same organization as parent and child.")
        min_amount = attrs.get("min_amount")
        max_amount = attrs.get("max_amount")
        if min_amount is not None and max_amount is not None and max_amount < min_amount:
            raise serializers.ValidationError("max_amount must be greater than or equal to min_amount.")
        return attrs

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be an object")
        return dict(value)


class PoolTopologySnapshotUpsertRequestSerializer(serializers.Serializer):
    version = serializers.CharField()
    effective_from = serializers.DateField()
    effective_to = serializers.DateField(required=False, allow_null=True)
    nodes = PoolTopologySnapshotNodeInputSerializer(many=True, allow_empty=False)
    edges = PoolTopologySnapshotEdgeInputSerializer(many=True, required=False, default=list)

    def validate(self, attrs):
        effective_from = attrs.get("effective_from")
        effective_to = attrs.get("effective_to")
        if effective_to is not None and effective_to < effective_from:
            raise serializers.ValidationError("effective_to must be greater than or equal to effective_from.")
        return attrs


class PoolTopologySnapshotUpsertResponseSerializer(serializers.Serializer):
    pool_id = serializers.UUIDField()
    version = serializers.CharField()
    effective_from = serializers.DateField()
    effective_to = serializers.DateField(required=False, allow_null=True)
    nodes_count = serializers.IntegerField()
    edges_count = serializers.IntegerField()


class PoolTopologySnapshotListItemSerializer(serializers.Serializer):
    effective_from = serializers.DateField()
    effective_to = serializers.DateField(required=False, allow_null=True)
    nodes_count = serializers.IntegerField()
    edges_count = serializers.IntegerField()


class PoolTopologySnapshotListResponseSerializer(serializers.Serializer):
    pool_id = serializers.UUIDField()
    count = serializers.IntegerField()
    snapshots = PoolTopologySnapshotListItemSerializer(many=True)


class PoolODataMetadataCatalogReadQuerySerializer(serializers.Serializer):
    database_id = serializers.CharField()

    def validate_database_id(self, value):
        token = str(value or "").strip()
        if not token:
            raise serializers.ValidationError("database_id is required.")
        return token


class PoolODataMetadataCatalogRefreshRequestSerializer(serializers.Serializer):
    database_id = serializers.CharField()

    def validate_database_id(self, value):
        token = str(value or "").strip()
        if not token:
            raise serializers.ValidationError("database_id is required.")
        return token


class PoolODataMetadataCatalogFieldSerializer(serializers.Serializer):
    name = serializers.CharField()
    type = serializers.CharField()
    nullable = serializers.BooleanField()


class PoolODataMetadataCatalogTablePartSerializer(serializers.Serializer):
    name = serializers.CharField()
    row_fields = PoolODataMetadataCatalogFieldSerializer(many=True)


class PoolODataMetadataCatalogDocumentSerializer(serializers.Serializer):
    entity_name = serializers.CharField()
    display_name = serializers.CharField()
    fields = PoolODataMetadataCatalogFieldSerializer(many=True)
    table_parts = PoolODataMetadataCatalogTablePartSerializer(many=True)


class PoolODataMetadataCatalogResponseSerializer(serializers.Serializer):
    database_id = serializers.CharField()
    snapshot_id = serializers.CharField()
    source = serializers.CharField()
    fetched_at = serializers.DateTimeField()
    catalog_version = serializers.CharField()
    config_name = serializers.CharField()
    config_version = serializers.CharField()
    config_generation_id = serializers.CharField(required=False, allow_blank=True)
    extensions_fingerprint = serializers.CharField()
    metadata_hash = serializers.CharField()
    observed_metadata_hash = serializers.CharField(required=False, allow_blank=True)
    publication_drift = serializers.BooleanField(required=False)
    resolution_mode = serializers.CharField()
    is_shared_snapshot = serializers.BooleanField()
    provenance_database_id = serializers.CharField()
    provenance_confirmed_at = serializers.DateTimeField()
    documents = PoolODataMetadataCatalogDocumentSerializer(many=True)


class PoolGraphNodeSerializer(serializers.Serializer):
    node_version_id = serializers.UUIDField()
    organization_id = serializers.UUIDField()
    inn = serializers.CharField()
    name = serializers.CharField()
    is_root = serializers.BooleanField()
    metadata = serializers.JSONField(required=False)


class PoolGraphEdgeSerializer(serializers.Serializer):
    edge_version_id = serializers.UUIDField()
    parent_node_version_id = serializers.UUIDField()
    child_node_version_id = serializers.UUIDField()
    weight = serializers.DecimalField(max_digits=12, decimal_places=6)
    min_amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, allow_null=True)
    max_amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, allow_null=True)
    metadata = serializers.JSONField(required=False)


class PoolGraphResponseSerializer(serializers.Serializer):
    pool_id = serializers.UUIDField()
    date = serializers.DateField()
    version = serializers.CharField()
    nodes = PoolGraphNodeSerializer(many=True)
    edges = PoolGraphEdgeSerializer(many=True)


class PoolRunReportResponseSerializer(serializers.Serializer):
    run = PoolRunSerializer()
    publication_attempts = PoolPublicationAttemptSerializer(many=True)
    validation_summary = serializers.JSONField(required=False)
    publication_summary = serializers.JSONField(required=False)
    diagnostics = serializers.JSONField(required=False)
    attempts_by_status = serializers.JSONField(required=False)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_runs_create",
    summary="Create or upsert pool run",
    request=PoolRunCreateRequestSerializer,
    responses={
        200: PoolRunCreateResponseSerializer,
        201: PoolRunCreateResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
    methods=["POST"],
)
@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_runs_list",
    summary="List pool runs",
    responses={
        200: PoolRunListResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
    methods=["GET"],
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def create_pool_run(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    if request.method == "GET":
        queryset = PoolRun.objects.filter(tenant_id=tenant_id).select_related("pool", "schema_template")
        pool_id = str(request.query_params.get("pool_id", "")).strip()
        status_value = str(request.query_params.get("status", "")).strip()
        if pool_id:
            queryset = queryset.filter(pool_id=pool_id)
        if status_value:
            queryset = queryset.filter(status=status_value)
        limit = _parse_limit(request.query_params.get("limit"))
        runs = list(queryset.order_by("-created_at")[:limit])
        publication_hardening_cutoff_utc = _resolve_publication_hardening_cutoff_utc(tenant_id=tenant_id)
        payload = {
            "runs": [
                _serialize_run(
                    run,
                    publication_hardening_cutoff_utc=publication_hardening_cutoff_utc,
                )
                for run in runs
            ],
            "count": len(runs),
        }
        return Response(payload, status=http_status.HTTP_200_OK)

    serializer = PoolRunCreateRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        if "pool_workflow_binding_id" in serializer.errors:
            return _problem(
                code="POOL_WORKFLOW_BINDING_REQUIRED",
                title="Pool Workflow Binding Required",
                detail="pool_workflow_binding_id is required.",
                status_code=http_status.HTTP_400_BAD_REQUEST,
            )
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(serializer.errors),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    pool = OrganizationPool.objects.filter(id=data["pool_id"], tenant_id=tenant_id).first()
    if pool is None:
        return _problem(
            code="POOL_NOT_FOUND",
            title="Pool Not Found",
            detail="Organization pool not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    try:
        resolved_workflow_binding = resolve_pool_workflow_binding_for_run(
            raw_bindings=list_attached_pool_workflow_bindings(pool=pool),
            requested_binding_id=str(data.get("pool_workflow_binding_id") or "").strip() or None,
            direction=data["direction"],
            mode=data.get("mode", PoolRunMode.SAFE),
            period_start=data["period_start"],
        )
    except PoolWorkflowBindingResolutionError as exc:
        return _problem(
            code=exc.code,
            title="Pool Workflow Binding Resolution Failed",
            detail=str(exc),
            status_code=http_status.HTTP_400_BAD_REQUEST,
            errors=exc.errors,
        )

    resolved_workflow_binding_payload = (
        resolved_workflow_binding.model_dump(mode="json", exclude_none=True)
        if resolved_workflow_binding is not None
        else None
    )
    if resolved_workflow_binding is None:
        return _problem(
            code="POOL_WORKFLOW_BINDING_NOT_RESOLVED",
            title="Pool Workflow Binding Resolution Failed",
            detail="No pool workflow bindings are configured for this pool.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
            errors=[],
        )

    schema_template = None
    schema_template_id = data.get("schema_template_id")
    if schema_template_id:
        schema_template = PoolSchemaTemplate.objects.filter(id=schema_template_id, tenant_id=tenant_id).first()
        if schema_template is None:
            return _problem(
                code="SCHEMA_TEMPLATE_NOT_FOUND",
                title="Schema Template Not Found",
                detail="Schema template not found in current tenant context.",
                status_code=http_status.HTTP_404_NOT_FOUND,
            )

    try:
        result = upsert_pool_run(
            tenant=pool.tenant,
            pool=pool,
            direction=data["direction"],
            period_start=data["period_start"],
            period_end=data.get("period_end"),
            workflow_binding_id=(
                resolved_workflow_binding.binding_id if resolved_workflow_binding is not None else None
            ),
            workflow_binding_revision=(
                resolved_workflow_binding.revision if resolved_workflow_binding is not None else None
            ),
            binding_profile_revision_id=(
                resolved_workflow_binding.binding_profile_revision_id
                if resolved_workflow_binding is not None
                else None
            ),
            run_input=data.get("run_input"),
            mode=data.get("mode", PoolRunMode.SAFE),
            schema_template=schema_template,
            seed=data.get("seed"),
            created_by=request.user if request.user and request.user.is_authenticated else None,
            validation_summary=data.get("validation_summary"),
            diagnostics=data.get("diagnostics"),
        )
    except ValueError as exc:
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(exc),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    try:
        runtime_result = start_pool_run_workflow_execution(
            run=result.run,
            requested_by=request.user if request.user and request.user.is_authenticated else None,
            workflow_binding=resolved_workflow_binding_payload,
        )
    except (ValueError, DjangoValidationError) as exc:
        error_code, detail = _resolve_pool_runtime_start_error(exc)
        title = (
            "Pool Runtime Configuration Error"
            if error_code in _POOL_RUNTIME_START_FAIL_CLOSED_CODES
            else "Validation Error"
        )
        return _problem(
            code=error_code,
            title=title,
            detail=detail,
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    payload = {
        "run": _serialize_run(
            runtime_result.run,
            publication_hardening_cutoff_utc=_resolve_publication_hardening_cutoff_utc(tenant_id=tenant_id),
        ),
        "created": result.created,
    }
    response_status = http_status.HTTP_201_CREATED if result.created else http_status.HTTP_200_OK
    return Response(payload, status=response_status)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_workflow_bindings_preview",
    summary="Preview effective pool workflow binding runtime projection",
    request=PoolWorkflowBindingPreviewRequestSerializer,
    responses={
        200: PoolWorkflowBindingPreviewResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def preview_pool_workflow_binding(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    serializer = PoolWorkflowBindingPreviewRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        if "pool_workflow_binding_id" in serializer.errors:
            return _problem(
                code="POOL_WORKFLOW_BINDING_REQUIRED",
                title="Pool Workflow Binding Required",
                detail="pool_workflow_binding_id is required.",
                status_code=http_status.HTTP_400_BAD_REQUEST,
            )
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(serializer.errors),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    pool = OrganizationPool.objects.filter(id=data["pool_id"], tenant_id=tenant_id).first()
    if pool is None:
        return _problem(
            code="POOL_NOT_FOUND",
            title="Pool Not Found",
            detail="Organization pool not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    schema_template_id = data.get("schema_template_id")
    if schema_template_id:
        schema_template = PoolSchemaTemplate.objects.filter(id=schema_template_id, tenant_id=tenant_id).first()
        if schema_template is None:
            return _problem(
                code="SCHEMA_TEMPLATE_NOT_FOUND",
                title="Schema Template Not Found",
                detail="Schema template not found in current tenant context.",
                status_code=http_status.HTTP_404_NOT_FOUND,
            )
    else:
        preview_run = PoolRun(
            tenant=pool.tenant,
            pool=pool,
            direction=data["direction"],
            mode=data.get("mode", PoolRunMode.SAFE),
            period_start=data["period_start"],
            period_end=data.get("period_end"),
        )
        schema_template = resolve_pool_runtime_schema_template(run=preview_run)

    try:
        preview = build_pool_workflow_binding_preview(
            tenant=pool.tenant,
            pool=pool,
            pool_workflow_binding_id=str(data["pool_workflow_binding_id"]),
            direction=data["direction"],
            mode=data.get("mode", PoolRunMode.SAFE),
            period_start=data["period_start"],
            period_end=data.get("period_end"),
            run_input=data.get("run_input"),
            schema_template=schema_template,
        )
    except PoolWorkflowBindingResolutionError as exc:
        return _problem(
            code=exc.code,
            title="Pool Workflow Binding Resolution Failed",
            detail=str(exc),
            status_code=http_status.HTTP_400_BAD_REQUEST,
            errors=exc.errors,
        )
    except ValueError as exc:
        error_code, detail = _resolve_pool_runtime_start_error(exc)
        return _problem(
            code=error_code,
            title="Pool Workflow Binding Preview Failed",
            detail=detail,
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    try:
        preview["workflow_binding"] = get_attached_pool_workflow_binding(
            pool=pool,
            binding_id=str(data["pool_workflow_binding_id"]),
        )
    except (PoolWorkflowBindingNotFoundError, PoolWorkflowBindingStoreError):
        pass

    return Response(preview, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_workflow_bindings_list",
    summary="List workflow bindings for a pool",
    responses={
        200: PoolWorkflowBindingCollectionResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
    methods=["GET"],
)
@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_workflow_bindings_replace",
    summary="Replace workflow bindings collection for a pool",
    request=PoolWorkflowBindingCollectionReplaceRequestSerializer,
    responses={
        200: PoolWorkflowBindingCollectionResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
    methods=["PUT"],
)
@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def list_pool_workflow_bindings(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    if request.method == "GET":
        serializer = PoolWorkflowBindingScopeQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return _problem(
                code="VALIDATION_ERROR",
                title="Validation Error",
                detail=str(serializer.errors),
                status_code=http_status.HTTP_400_BAD_REQUEST,
            )

        pool = OrganizationPool.objects.filter(
            id=serializer.validated_data["pool_id"],
            tenant_id=tenant_id,
        ).first()
        if pool is None:
            return _problem(
                code="POOL_NOT_FOUND",
                title="Pool Not Found",
                detail="Organization pool not found in current tenant context.",
                status_code=http_status.HTTP_404_NOT_FOUND,
            )

        try:
            collection = get_attached_pool_workflow_binding_collection(pool=pool)
        except PoolWorkflowBindingStoreError as exc:
            error_code, detail = _resolve_pool_workflow_binding_validation_error(exc)
            return _problem(
                code=error_code,
                title="Validation Error",
                detail=detail,
                status_code=http_status.HTTP_400_BAD_REQUEST,
            )
        except PoolWorkflowBindingResolutionError as exc:
            return _problem(
                code=exc.code,
                title="Pool Workflow Binding Resolution Failed",
                detail=str(exc),
                status_code=http_status.HTTP_400_BAD_REQUEST,
                errors=exc.errors,
            )
        return Response(collection, status=http_status.HTTP_200_OK)

    serializer = PoolWorkflowBindingCollectionReplaceRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(serializer.errors),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    pool = OrganizationPool.objects.filter(id=data["pool_id"], tenant_id=tenant_id).first()
    if pool is None:
        return _problem(
            code="POOL_NOT_FOUND",
            title="Pool Not Found",
            detail="Organization pool not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    try:
        collection = replace_attached_pool_workflow_bindings_collection(
            pool=pool,
            expected_collection_etag=data["expected_collection_etag"],
            workflow_bindings=[dict(item) for item in data["workflow_bindings"]],
            actor_username=(
                request.user.username
                if request.user and request.user.is_authenticated
                else ""
            ),
        )
    except PoolWorkflowBindingCollectionConflictError as exc:
        return _binding_collection_conflict_problem(exc)
    except PoolWorkflowBindingAttachmentLifecycleConflictError as exc:
        return _binding_profile_lifecycle_conflict_problem(exc)
    except PoolWorkflowBindingStoreError as exc:
        error_code, detail = _resolve_pool_workflow_binding_validation_error(exc)
        return _problem(
            code=error_code,
            title="Validation Error",
            detail=detail,
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )
    except PoolWorkflowBindingResolutionError as exc:
        return _problem(
            code=exc.code,
            title="Pool Workflow Binding Resolution Failed",
            detail=str(exc),
            status_code=http_status.HTTP_400_BAD_REQUEST,
            errors=exc.errors,
        )

    return Response(collection, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_workflow_bindings_upsert",
    summary="Create or update a workflow binding for a pool",
    request=PoolWorkflowBindingUpsertRequestSerializer,
    responses={
        200: PoolWorkflowBindingUpsertResponseSerializer,
        201: PoolWorkflowBindingUpsertResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upsert_pool_workflow_binding(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    serializer = PoolWorkflowBindingUpsertRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(serializer.errors),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    pool = OrganizationPool.objects.filter(id=data["pool_id"], tenant_id=tenant_id).first()
    if pool is None:
        return _problem(
            code="POOL_NOT_FOUND",
            title="Pool Not Found",
            detail="Organization pool not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    try:
        workflow_binding, created = upsert_attached_pool_workflow_binding(
            pool=pool,
            workflow_binding=dict(data["workflow_binding"]),
            actor_username=(
                request.user.username
                if request.user and request.user.is_authenticated
                else ""
            ),
        )
    except PoolWorkflowBindingRevisionConflictError as exc:
        return _binding_revision_conflict_problem(exc)
    except PoolWorkflowBindingAttachmentLifecycleConflictError as exc:
        return _binding_profile_lifecycle_conflict_problem(exc)
    except PoolWorkflowBindingStoreError as exc:
        error_code, detail = _resolve_pool_workflow_binding_validation_error(exc)
        return _problem(
            code=error_code,
            title="Validation Error",
            detail=detail,
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )
    except PoolWorkflowBindingResolutionError as exc:
        return _problem(
            code=exc.code,
            title="Pool Workflow Binding Resolution Failed",
            detail=str(exc),
            status_code=http_status.HTTP_400_BAD_REQUEST,
            errors=exc.errors,
        )

    response_status = http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK
    return Response(
        {
            "pool_id": str(pool.id),
            "workflow_binding": workflow_binding,
            "created": created,
        },
        status=response_status,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_workflow_bindings_detail",
    summary="Get a workflow binding for a pool",
    responses={
        200: PoolWorkflowBindingDetailResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
    methods=["GET"],
)
@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_workflow_bindings_delete",
    summary="Delete a workflow binding for a pool",
    responses={
        200: PoolWorkflowBindingDeleteResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
    methods=["DELETE"],
)
@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def pool_workflow_binding_detail(request, binding_id: str):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    serializer_class = (
        PoolWorkflowBindingDeleteQuerySerializer
        if request.method == "DELETE"
        else PoolWorkflowBindingScopeQuerySerializer
    )
    serializer = serializer_class(data=request.query_params)
    if not serializer.is_valid():
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(serializer.errors),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    pool = OrganizationPool.objects.filter(
        id=serializer.validated_data["pool_id"],
        tenant_id=tenant_id,
    ).first()
    if pool is None:
        return _problem(
            code="POOL_NOT_FOUND",
            title="Pool Not Found",
            detail="Organization pool not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    try:
        binding = get_attached_pool_workflow_binding(pool=pool, binding_id=binding_id)
    except PoolWorkflowBindingNotFoundError:
        return _problem(
            code="POOL_WORKFLOW_BINDING_NOT_FOUND",
            title="Pool Workflow Binding Not Found",
            detail="Workflow binding not found for the specified pool.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    except PoolWorkflowBindingStoreError as exc:
        error_code, detail = _resolve_pool_workflow_binding_validation_error(exc)
        return _problem(
            code=error_code,
            title="Validation Error",
            detail=detail,
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )
    except PoolWorkflowBindingResolutionError as exc:
        return _problem(
            code=exc.code,
            title="Pool Workflow Binding Resolution Failed",
            detail=str(exc),
            status_code=http_status.HTTP_400_BAD_REQUEST,
            errors=exc.errors,
        )

    if request.method == "GET":
        return Response(
            {
                "pool_id": str(pool.id),
                "workflow_binding": binding,
            },
            status=http_status.HTTP_200_OK,
        )

    try:
        deleted_binding = delete_attached_pool_workflow_binding(
            pool=pool,
            binding_id=binding_id,
            revision=serializer.validated_data["revision"],
        )
    except PoolWorkflowBindingRevisionConflictError as exc:
        return _binding_revision_conflict_problem(exc)
    except PoolWorkflowBindingNotFoundError:
        return _problem(
            code="POOL_WORKFLOW_BINDING_NOT_FOUND",
            title="Pool Workflow Binding Not Found",
            detail="Workflow binding not found for the specified pool.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    except PoolWorkflowBindingResolutionError as exc:
        return _problem(
            code=exc.code,
            title="Pool Workflow Binding Resolution Failed",
            detail=str(exc),
            status_code=http_status.HTTP_400_BAD_REQUEST,
            errors=exc.errors,
        )
    return Response(
        {
            "pool_id": str(pool.id),
            "workflow_binding": deleted_binding,
            "deleted": True,
        },
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_organizations_list",
    summary="List organizations in pools catalog",
    responses={
        200: OrganizationListResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_organizations(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _error(
            code="TENANT_CONTEXT_REQUIRED",
            message="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    queryset = Organization.objects.filter(tenant_id=tenant_id).select_related("database", "master_party")
    status_value = str(request.query_params.get("status", "")).strip().lower()
    if status_value:
        if status_value not in OrganizationStatus.values:
            return _error(
                code="VALIDATION_ERROR",
                message=f"Unsupported status '{status_value}'.",
                status_code=http_status.HTTP_400_BAD_REQUEST,
            )
        queryset = queryset.filter(status=status_value)

    query = str(request.query_params.get("query", "")).strip()
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(full_name__icontains=query)
            | Q(inn__icontains=query)
            | Q(kpp__icontains=query)
        )

    linked_raw = request.query_params.get("database_linked")
    if linked_raw is not None:
        is_linked = str(linked_raw).strip().lower() in {"1", "true", "yes"}
        if is_linked:
            queryset = queryset.filter(database_id__isnull=False)
        else:
            queryset = queryset.filter(database_id__isnull=True)

    limit = _parse_limit(request.query_params.get("limit"), default=100, max_value=500)
    organizations = list(queryset.order_by("name", "inn")[:limit])
    payload = {
        "organizations": [_serialize_organization(item) for item in organizations],
        "count": len(organizations),
    }
    return Response(payload, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_organizations_get",
    summary="Get organization details from pools catalog",
    responses={
        200: OrganizationDetailResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: ErrorResponseSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_organization(request, organization_id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _error(
            code="TENANT_CONTEXT_REQUIRED",
            message="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    organization = (
        Organization.objects.filter(id=organization_id, tenant_id=tenant_id)
        .select_related("database", "master_party")
        .first()
    )
    if organization is None:
        return _error(
            code="ORGANIZATION_NOT_FOUND",
            message="Organization not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    pool_bindings = list(
        PoolNodeVersion.objects.select_related("pool")
        .filter(organization=organization)
        .order_by("-effective_from", "pool__code", "pool_id")
    )
    payload = {
        "organization": _serialize_organization(organization),
        "pool_bindings": [
            {
                "pool_id": str(binding.pool_id),
                "pool_code": binding.pool.code,
                "pool_name": binding.pool.name,
                "is_root": binding.is_root,
                "effective_from": binding.effective_from,
                "effective_to": binding.effective_to,
            }
            for binding in pool_bindings
        ],
    }
    return Response(payload, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_organizations_upsert",
    summary="Create or update organization in pools catalog",
    request=OrganizationUpsertRequestSerializer,
    responses={
        200: OrganizationUpsertResponseSerializer,
        201: OrganizationUpsertResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upsert_organization(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    serializer = OrganizationUpsertRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail="Organization payload validation failed.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
            errors=serializer.errors,
        )

    data = serializer.validated_data
    organization = None
    organization_id = data.get("organization_id")
    if organization_id:
        organization = Organization.objects.filter(id=organization_id, tenant_id=tenant_id).first()
        if organization is None:
            return _problem(
                code="ORGANIZATION_NOT_FOUND",
                title="Organization Not Found",
                detail="Organization not found in current tenant context.",
                status_code=http_status.HTTP_404_NOT_FOUND,
            )
    if organization is None:
        organization = Organization.objects.filter(tenant_id=tenant_id, inn=data["inn"]).first()

    if organization is not None and organization.inn != data["inn"]:
        if Organization.objects.filter(tenant_id=tenant_id, inn=data["inn"]).exclude(id=organization.id).exists():
            return _problem(
                code="DUPLICATE_ORGANIZATION_INN",
                title="Duplicate Organization INN",
                detail="Organization with this INN already exists in current tenant.",
                status_code=http_status.HTTP_400_BAD_REQUEST,
            )

    database = None
    if "database_id" in data:
        database_id = data.get("database_id")
        if database_id is not None:
            database = Database.objects.filter(id=database_id, tenant_id=tenant_id).first()
            if database is None:
                return _problem(
                    code="DATABASE_NOT_FOUND",
                    title="Database Not Found",
                    detail="Database not found in current tenant context.",
                    status_code=http_status.HTTP_404_NOT_FOUND,
                )
            conflict_qs = Organization.objects.filter(tenant_id=tenant_id, database=database)
            if organization is not None:
                conflict_qs = conflict_qs.exclude(id=organization.id)
            if conflict_qs.exists():
                return _problem(
                    code="DATABASE_ALREADY_LINKED",
                    title="Database Already Linked",
                    detail="Database is already linked to another organization.",
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                )

    master_party = None
    if "master_party_id" in data:
        master_party_id = data.get("master_party_id")
        if master_party_id is not None:
            master_party = PoolMasterParty.objects.filter(id=master_party_id, tenant_id=tenant_id).first()
            if master_party is None:
                return _problem(
                    code="MASTER_PARTY_NOT_FOUND",
                    title="Master Party Not Found",
                    detail="Master party not found in current tenant context.",
                    status_code=http_status.HTTP_404_NOT_FOUND,
                )
            if not master_party.is_our_organization:
                return _problem(
                    code="MASTER_PARTY_ROLE_INVALID",
                    title="Master Party Role Invalid",
                    detail="Master party must have organization role (is_our_organization=true).",
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                )
            conflict_qs = Organization.objects.filter(master_party=master_party)
            if organization is not None:
                conflict_qs = conflict_qs.exclude(id=organization.id)
            if conflict_qs.exists():
                return _problem(
                    code="MASTER_PARTY_ALREADY_LINKED",
                    title="Master Party Already Linked",
                    detail="Master party is already linked to another organization.",
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                )

    created = organization is None
    status_value = data.get("status", organization.status if organization else OrganizationStatus.ACTIVE)
    metadata_value = data.get("metadata", organization.metadata if organization else {})
    full_name = data.get("full_name", organization.full_name if organization else "")
    kpp = data.get("kpp", organization.kpp if organization else "")
    external_ref = data.get("external_ref", organization.external_ref if organization else "")
    database_value = database if "database_id" in data else (organization.database if organization else None)
    master_party_value = master_party if "master_party_id" in data else (organization.master_party if organization else None)

    try:
        if created:
            organization = Organization(
                tenant_id=tenant_id,
                database=database_value,
                master_party=master_party_value,
                name=data["name"],
                full_name=full_name,
                inn=data["inn"],
                kpp=kpp,
                status=status_value,
                external_ref=external_ref,
                metadata=metadata_value,
            )
            organization.full_clean()
            organization.save()
        else:
            changed_fields: list[str] = []
            updates = {
                "database": database_value,
                "master_party": master_party_value,
                "name": data["name"],
                "full_name": full_name,
                "inn": data["inn"],
                "kpp": kpp,
                "status": status_value,
                "external_ref": external_ref,
                "metadata": metadata_value,
            }
            for field_name, value in updates.items():
                if getattr(organization, field_name) != value:
                    setattr(organization, field_name, value)
                    changed_fields.append(field_name)
            if changed_fields:
                organization.full_clean()
                organization.save(update_fields=[*changed_fields, "updated_at"])
    except DjangoValidationError as exc:
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail="Organization payload validation failed.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
            errors=exc.message_dict if hasattr(exc, "message_dict") else str(exc),
        )
    except IntegrityError:
        if "master_party_id" in data and data.get("master_party_id") is not None:
            return _problem(
                code="MASTER_PARTY_ALREADY_LINKED",
                title="Master Party Already Linked",
                detail="Master party is already linked to another organization.",
                status_code=http_status.HTTP_400_BAD_REQUEST,
            )
        return _problem(
            code="DUPLICATE_ORGANIZATION_INN",
            title="Duplicate Organization INN",
            detail="Organization with this INN already exists in current tenant.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    payload = {
        "organization": _serialize_organization(organization),
        "created": created,
    }
    response_status = http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK
    return Response(payload, status=response_status)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_organizations_sync",
    summary="Sync organizations catalog",
    request=OrganizationSyncRequestSerializer,
    responses={
        200: OrganizationSyncResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sync_organizations_catalog(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _error(
            code="TENANT_CONTEXT_REQUIRED",
            message="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    serializer = OrganizationSyncRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": serializer.errors},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    tenant = Tenant.objects.filter(id=tenant_id).first()
    if tenant is None:
        return _error(
            code="TENANT_NOT_FOUND",
            message="Tenant context is invalid.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    rows = serializer.validated_data["rows"]
    try:
        stats = sync_organizations(tenant=tenant, rows=rows)
    except DjangoValidationError as exc:
        return _error(
            code="VALIDATION_ERROR",
            message=_validation_message(exc),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    payload = {
        "stats": {
            "created": stats.created,
            "updated": stats.updated,
            "skipped": stats.skipped,
        },
        "total_rows": len(rows),
    }
    return Response(payload, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_odata_metadata_catalog_get",
    summary="Get normalized OData metadata catalog for selected database",
    parameters=[PoolODataMetadataCatalogReadQuerySerializer],
    responses={
        200: PoolODataMetadataCatalogResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (403, "application/problem+json"): ProblemDetailsErrorSerializer,
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_pool_odata_metadata_catalog(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    serializer = PoolODataMetadataCatalogReadQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(serializer.errors),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    database_id = serializer.validated_data["database_id"]
    database = Database.objects.filter(id=database_id, tenant_id=tenant_id).first()
    if database is None:
        return _problem(
            code="DATABASE_NOT_FOUND",
            title="Database Not Found",
            detail="Database not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    if not request.user.has_perm(perms.PERM_DATABASES_VIEW_DATABASE, database):
        return _database_permission_problem(
            detail="You do not have permission to access this database metadata catalog.",
        )

    try:
        snapshot, source, resolution, profile = read_existing_metadata_catalog_snapshot(
            tenant_id=tenant_id,
            database=database,
            requested_by_username=str(getattr(request.user, "username", "") or "").strip(),
        )
    except MetadataCatalogError as exc:
        return _problem(
            code=exc.code,
            title=exc.title,
            detail=exc.detail,
            status_code=exc.status_code,
            errors=exc.errors or None,
        )

    return Response(
        _serialize_metadata_catalog_snapshot(
            database=database,
            snapshot=snapshot,
            source=source,
            resolution=resolution,
            profile=profile,
        ),
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_odata_metadata_catalog_refresh",
    summary="Refresh OData metadata catalog snapshot for selected database",
    request=PoolODataMetadataCatalogRefreshRequestSerializer,
    responses={
        200: PoolODataMetadataCatalogResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (403, "application/problem+json"): ProblemDetailsErrorSerializer,
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def refresh_pool_odata_metadata_catalog(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    serializer = PoolODataMetadataCatalogRefreshRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(serializer.errors),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    database_id = serializer.validated_data["database_id"]
    database = Database.objects.filter(id=database_id, tenant_id=tenant_id).first()
    if database is None:
        return _problem(
            code="DATABASE_NOT_FOUND",
            title="Database Not Found",
            detail="Database not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    if not request.user.has_perm(perms.PERM_DATABASES_OPERATE_DATABASE, database):
        return _database_permission_problem(
            detail="You do not have permission to refresh metadata for this database.",
        )

    try:
        snapshot = refresh_metadata_catalog_snapshot(
            tenant_id=tenant_id,
            database=database,
            requested_by_username=str(getattr(request.user, "username", "") or "").strip(),
            source="live_refresh",
        )
    except MetadataCatalogError as exc:
        return _problem(
            code=exc.code,
            title=exc.title,
            detail=exc.detail,
            status_code=exc.status_code,
            errors=exc.errors or None,
        )

    resolution = describe_metadata_catalog_snapshot_resolution(
        tenant_id=tenant_id,
        database=database,
        snapshot=snapshot,
    )
    return Response(
        _serialize_metadata_catalog_snapshot(
            database=database,
            snapshot=snapshot,
            source="live_refresh",
            resolution=resolution,
        ),
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_list",
    summary="List organization pools",
    responses={
        200: OrganizationPoolListResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_organization_pools(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _error(
            code="TENANT_CONTEXT_REQUIRED",
            message="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    queryset = OrganizationPool.objects.filter(tenant_id=tenant_id)
    is_active_value = request.query_params.get("is_active")
    if is_active_value is not None:
        queryset = queryset.filter(is_active=str(is_active_value).strip().lower() in {"1", "true", "yes"})
    pools = list(queryset.order_by("code"))
    payload = {
        "pools": [_serialize_organization_pool(pool) for pool in pools],
        "count": len(pools),
    }
    return Response(payload, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_upsert",
    summary="Create or update organization pool metadata",
    request=OrganizationPoolUpsertRequestSerializer,
    responses={
        200: OrganizationPoolUpsertResponseSerializer,
        201: OrganizationPoolUpsertResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upsert_organization_pool(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    serializer = OrganizationPoolUpsertRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(serializer.errors),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    pool = None
    pool_id = data.get("pool_id")
    if pool_id:
        pool = OrganizationPool.objects.filter(id=pool_id, tenant_id=tenant_id).first()
        if pool is None:
            return _problem(
                code="POOL_NOT_FOUND",
                title="Pool Not Found",
                detail="Organization pool not found in current tenant context.",
                status_code=http_status.HTTP_404_NOT_FOUND,
            )
    else:
        pool = OrganizationPool.objects.filter(tenant_id=tenant_id, code=data["code"]).first()

    existing_metadata = pool.metadata if pool and isinstance(pool.metadata, dict) else {}
    created = pool is None
    description_value = data.get("description", pool.description if pool else "")
    metadata_value = dict(data.get("metadata", existing_metadata) or {})
    metadata_value.pop("workflow_bindings", None)
    metadata_value.pop("workflow_bindings_read_error", None)
    is_active_value = data.get("is_active", pool.is_active if pool else True)
    pool_uuid = pool.id if pool else uuid4()
    legacy_write_errors = _collect_legacy_document_policy_write_errors(pool_metadata=metadata_value)
    if legacy_write_errors:
        return _legacy_document_policy_write_problem(errors=legacy_write_errors)

    try:
        if created:
            pool = OrganizationPool.objects.create(
                id=pool_uuid,
                tenant_id=tenant_id,
                code=data["code"],
                name=data["name"],
                description=description_value,
                is_active=is_active_value,
                metadata=metadata_value,
            )
        else:
            changed_fields: list[str] = []
            updates = {
                "code": data["code"],
                "name": data["name"],
                "description": description_value,
                "is_active": is_active_value,
                "metadata": metadata_value,
            }
            for field_name, value in updates.items():
                if getattr(pool, field_name) != value:
                    setattr(pool, field_name, value)
                    changed_fields.append(field_name)
            if changed_fields:
                pool.save(update_fields=[*changed_fields, "updated_at"])
    except IntegrityError:
        return _problem(
            code="DUPLICATE_POOL_CODE",
            title="Duplicate Pool Code",
            detail="Pool with this code already exists in current tenant.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    payload = {
        "pool": _serialize_organization_pool(pool),
        "created": created,
    }
    response_status = http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK
    return Response(payload, status=response_status)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_topology_snapshot_upsert",
    summary="Create or update topology snapshot for a pool",
    request=PoolTopologySnapshotUpsertRequestSerializer,
    responses={
        200: PoolTopologySnapshotUpsertResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upsert_pool_topology_snapshot(request, pool_id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    pool = OrganizationPool.objects.filter(id=pool_id, tenant_id=tenant_id).first()
    if pool is None:
        return _problem(
            code="POOL_NOT_FOUND",
            title="Pool Not Found",
            detail="Organization pool not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    serializer = PoolTopologySnapshotUpsertRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(serializer.errors),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    version_token = str(data.get("version") or "").strip()
    nodes_payload = list(data.get("nodes") or [])
    edges_payload = list(data.get("edges") or [])
    effective_from = data["effective_from"]
    effective_to = data.get("effective_to")
    legacy_write_errors = _collect_legacy_document_policy_write_errors(
        pool_metadata=pool.metadata if isinstance(pool.metadata, Mapping) else None,
        edges_payload=edges_payload,
    )
    if legacy_write_errors:
        return _legacy_document_policy_write_problem(errors=legacy_write_errors)

    active_nodes, active_edges = _load_pool_graph_state(pool=pool, target_date=effective_from)
    current_version = _build_topology_version_token(
        active_nodes=active_nodes,
        active_edges=active_edges,
    )
    if version_token != current_version:
        return _problem(
            code="TOPOLOGY_VERSION_CONFLICT",
            title="Topology Version Conflict",
            detail=(
                "Topology snapshot was changed by another session. "
                "Reload graph data and retry with the latest version token."
            ),
            status_code=http_status.HTTP_409_CONFLICT,
        )

    organization_ids = [str(item["organization_id"]) for item in nodes_payload]
    if len(set(organization_ids)) != len(organization_ids):
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail="Topology snapshot contains duplicate organization nodes.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    organizations = {
        str(item.id): item
        for item in Organization.objects.filter(id__in=organization_ids, tenant_id=tenant_id)
    }
    missing_org_ids = sorted(set(organization_ids) - set(organizations))
    if missing_org_ids:
        return _problem(
            code="ORGANIZATION_NOT_FOUND",
            title="Organization Not Found",
            detail=f"Organizations not found in tenant context: {', '.join(missing_org_ids)}",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    edge_pairs: list[tuple[str, str]] = []
    for edge in edges_payload:
        parent_org_id = str(edge["parent_organization_id"])
        child_org_id = str(edge["child_organization_id"])
        if parent_org_id not in organizations or child_org_id not in organizations:
            return _problem(
                code="VALIDATION_ERROR",
                title="Validation Error",
                detail="Topology edges must reference organizations from nodes list.",
                status_code=http_status.HTTP_400_BAD_REQUEST,
            )
        edge_pairs.append((parent_org_id, child_org_id))

    try:
        validate_pool_graph(node_ids=list(organization_ids), edge_pairs=edge_pairs)
    except DjangoValidationError as exc:
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=_validation_message(exc),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    period_node_qs = PoolNodeVersion.objects.filter(pool=pool, effective_from=effective_from)
    period_edge_qs = PoolEdgeVersion.objects.filter(pool=pool, effective_from=effective_from)
    replacement_previous_end = effective_from - timedelta(days=1)

    try:
        with transaction.atomic():
            # Close previously active topology versions so the new snapshot becomes the only
            # active graph starting from effective_from.
            PoolEdgeVersion.objects.filter(pool=pool, effective_from__lt=effective_from).filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from)
            ).update(effective_to=replacement_previous_end)
            PoolNodeVersion.objects.filter(pool=pool, effective_from__lt=effective_from).filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from)
            ).update(effective_to=replacement_previous_end)

            period_edge_qs.delete()
            period_node_qs.delete()

            node_versions_by_org: dict[str, PoolNodeVersion] = {}
            for node in nodes_payload:
                org_id = str(node["organization_id"])
                node_versions_by_org[org_id] = PoolNodeVersion.objects.create(
                    pool=pool,
                    organization=organizations[org_id],
                    effective_from=effective_from,
                    effective_to=effective_to,
                    is_root=bool(node.get("is_root", False)),
                    metadata=node.get("metadata") if isinstance(node.get("metadata"), dict) else {},
                )

            for edge in edges_payload:
                parent_org_id = str(edge["parent_organization_id"])
                child_org_id = str(edge["child_organization_id"])
                PoolEdgeVersion.objects.create(
                    pool=pool,
                    parent_node=node_versions_by_org[parent_org_id],
                    child_node=node_versions_by_org[child_org_id],
                    effective_from=effective_from,
                    effective_to=effective_to,
                    weight=edge.get("weight", 1),
                    min_amount=edge.get("min_amount"),
                    max_amount=edge.get("max_amount"),
                    metadata=edge.get("metadata") if isinstance(edge.get("metadata"), dict) else {},
                )

            pool.validate_graph(effective_from)
    except (IntegrityError, DjangoValidationError, ValueError) as exc:
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=_validation_message(exc),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    updated_nodes, updated_edges = _load_pool_graph_state(pool=pool, target_date=effective_from)

    payload = {
        "pool_id": str(pool.id),
        "version": _build_topology_version_token(
            active_nodes=updated_nodes,
            active_edges=updated_edges,
        ),
        "effective_from": effective_from,
        "effective_to": effective_to,
        "nodes_count": len(nodes_payload),
        "edges_count": len(edges_payload),
    }
    return Response(payload, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_topology_snapshots_list",
    summary="List topology snapshots for a pool",
    responses={
        200: PoolTopologySnapshotListResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: ErrorResponseSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_pool_topology_snapshots(request, pool_id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _error(
            code="TENANT_CONTEXT_REQUIRED",
            message="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    pool = OrganizationPool.objects.filter(id=pool_id, tenant_id=tenant_id).first()
    if pool is None:
        return _error(
            code="POOL_NOT_FOUND",
            message="Organization pool not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    node_rows = list(
        PoolNodeVersion.objects.filter(pool=pool)
        .values("effective_from", "effective_to")
        .annotate(nodes_count=Count("id"))
    )
    edge_rows = list(
        PoolEdgeVersion.objects.filter(pool=pool)
        .values("effective_from", "effective_to")
        .annotate(edges_count=Count("id"))
    )

    snapshots_by_period: dict[tuple[date, date | None], dict[str, Any]] = {}
    for row in node_rows:
        period = (row["effective_from"], row["effective_to"])
        snapshots_by_period[period] = {
            "effective_from": row["effective_from"],
            "effective_to": row["effective_to"],
            "nodes_count": int(row.get("nodes_count") or 0),
            "edges_count": 0,
        }

    for row in edge_rows:
        period = (row["effective_from"], row["effective_to"])
        snapshot = snapshots_by_period.get(period)
        if snapshot is None:
            snapshot = {
                "effective_from": row["effective_from"],
                "effective_to": row["effective_to"],
                "nodes_count": 0,
                "edges_count": 0,
            }
            snapshots_by_period[period] = snapshot
        snapshot["edges_count"] = int(row.get("edges_count") or 0)

    snapshots = sorted(
        snapshots_by_period.values(),
        key=lambda item: (
            item["effective_from"],
            item["effective_to"] or date.max,
        ),
        reverse=True,
    )

    return Response(
        {
            "pool_id": str(pool.id),
            "count": len(snapshots),
            "snapshots": snapshots,
        },
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_graph_get",
    summary="Get active pool graph by date",
    responses={
        200: PoolGraphResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: ErrorResponseSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_pool_graph(request, pool_id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _error(
            code="TENANT_CONTEXT_REQUIRED",
            message="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    pool = OrganizationPool.objects.filter(id=pool_id, tenant_id=tenant_id).first()
    if pool is None:
        return _error(
            code="POOL_NOT_FOUND",
            message="Organization pool not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    target_date, parse_error = _parse_date_param(request.query_params.get("date"), field_name="date")
    if parse_error:
        return _error(
            code="VALIDATION_ERROR",
            message=parse_error,
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )
    if target_date is None:
        target_date = timezone.localdate()

    active_nodes, active_edges = _load_pool_graph_state(pool=pool, target_date=target_date)
    payload = {
        "pool_id": str(pool.id),
        "date": target_date,
        "version": _build_topology_version_token(
            active_nodes=active_nodes,
            active_edges=active_edges,
        ),
        "nodes": [
            {
                "node_version_id": str(node.id),
                "organization_id": str(node.organization_id),
                "inn": node.organization.inn,
                "name": node.organization.name,
                "is_root": node.is_root,
                "metadata": node.metadata if isinstance(node.metadata, dict) else {},
            }
            for node in active_nodes
        ],
        "edges": [
            {
                "edge_version_id": str(edge.id),
                "parent_node_version_id": str(edge.parent_node_id),
                "child_node_version_id": str(edge.child_node_id),
                "weight": edge.weight,
                "min_amount": edge.min_amount,
                "max_amount": edge.max_amount,
                "metadata": edge.metadata if isinstance(edge.metadata, dict) else {},
            }
            for edge in active_edges
        ],
    }
    return Response(payload, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_runs_report_get",
    summary="Get pool run dry-run/report payload",
    responses={
        200: PoolRunReportResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: ErrorResponseSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_pool_run_report(request, run_id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _error(
            code="TENANT_CONTEXT_REQUIRED",
            message="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    run = (
        PoolRun.objects.select_related("pool", "schema_template")
        .filter(id=run_id, tenant_id=tenant_id)
        .first()
    )
    if run is None:
        return _error(
            code="RUN_NOT_FOUND",
            message="Pool run not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    attempts = list(
        PoolPublicationAttempt.objects.filter(run=run).order_by(
            "target_database_id",
            "attempt_number",
            "created_at",
        )
    )
    attempts_by_status: dict[str, int] = {}
    for attempt in attempts:
        attempts_by_status[attempt.status] = attempts_by_status.get(attempt.status, 0) + 1
    publication_hardening_cutoff_utc = _resolve_publication_hardening_cutoff_utc(tenant_id=tenant_id)
    serialized_run = _serialize_run(
        run,
        publication_hardening_cutoff_utc=publication_hardening_cutoff_utc,
    )
    payload = {
        "run": serialized_run,
        "publication_attempts": [_serialize_attempt(item) for item in attempts],
        "validation_summary": run.validation_summary,
        "publication_summary": run.publication_summary,
        "diagnostics": serialized_run.get("diagnostics"),
        "attempts_by_status": attempts_by_status,
    }
    return Response(payload, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_schema_templates_list",
    summary="List public pool schema templates",
    responses={
        200: PoolSchemaTemplateListResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
    methods=["GET"],
)
@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_schema_templates_create",
    summary="Create pool schema template",
    request=PoolSchemaTemplateCreateRequestSerializer,
    responses={
        201: PoolSchemaTemplateCreateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
    methods=["POST"],
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def list_or_create_schema_templates(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _error(
            code="TENANT_CONTEXT_REQUIRED",
            message="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    if request.method == "GET":
        queryset = PoolSchemaTemplate.objects.filter(tenant_id=tenant_id)
        format_value = str(request.query_params.get("format", "")).strip().lower()
        if format_value:
            if format_value not in PoolSchemaTemplateFormat.values:
                return _error(
                    code="VALIDATION_ERROR",
                    message=f"Unsupported format '{format_value}'.",
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(format=format_value)

        is_public_value = request.query_params.get("is_public")
        if is_public_value is None:
            queryset = queryset.filter(is_public=True)
        else:
            queryset = queryset.filter(is_public=str(is_public_value).strip().lower() in {"1", "true", "yes"})

        is_active_value = request.query_params.get("is_active")
        if is_active_value is not None:
            queryset = queryset.filter(is_active=str(is_active_value).strip().lower() in {"1", "true", "yes"})

        templates = list(queryset.order_by("code"))
        payload = {
            "templates": [_serialize_schema_template(item) for item in templates],
            "count": len(templates),
        }
        return Response(payload, status=http_status.HTTP_200_OK)

    serializer = PoolSchemaTemplateCreateRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": serializer.errors},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    metadata = dict(data.get("metadata") or {})
    workflow_template_id = data.get("workflow_template_id")
    if workflow_template_id is not None:
        metadata["workflow_template_id"] = str(workflow_template_id)
    else:
        metadata.pop("workflow_template_id", None)

    try:
        template = PoolSchemaTemplate.objects.create(
            tenant_id=tenant_id,
            code=data["code"],
            name=data["name"],
            format=data["format"],
            is_public=data.get("is_public", True),
            is_active=data.get("is_active", True),
            schema=data.get("schema") if isinstance(data.get("schema"), dict) else {},
            metadata=metadata,
        )
    except IntegrityError:
        return _error(
            code="DUPLICATE_TEMPLATE_CODE",
            message="Template with this code already exists in current tenant.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {"template": _serialize_schema_template(template)},
        status=http_status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_schema_templates_update",
    summary="Update pool schema template",
    request=PoolSchemaTemplateUpdateRequestSerializer,
    responses={
        200: PoolSchemaTemplateCreateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: ErrorResponseSerializer,
    },
    methods=["PUT"],
)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_schema_template(request, template_id):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _error(
            code="TENANT_CONTEXT_REQUIRED",
            message="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    template = PoolSchemaTemplate.objects.filter(id=template_id, tenant_id=tenant_id).first()
    if template is None:
        return _error(
            code="TEMPLATE_NOT_FOUND",
            message="Pool schema template not found.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    serializer = PoolSchemaTemplateUpdateRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": serializer.errors},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    metadata = dict(data.get("metadata") or {})
    workflow_template_id = data.get("workflow_template_id")
    if workflow_template_id is not None:
        metadata["workflow_template_id"] = str(workflow_template_id)
    else:
        metadata.pop("workflow_template_id", None)

    template.code = data["code"]
    template.name = data["name"]
    template.format = data["format"]
    template.is_public = data.get("is_public", True)
    template.is_active = data.get("is_active", True)
    template.schema = data.get("schema") if isinstance(data.get("schema"), dict) else {}
    template.metadata = metadata

    try:
        template.save()
    except IntegrityError:
        return _error(
            code="DUPLICATE_TEMPLATE_CODE",
            message="Template with this code already exists in current tenant.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {"template": _serialize_schema_template(template)},
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_runs_get",
    summary="Get pool run status and details",
    responses={
        200: PoolRunDetailResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: ErrorResponseSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_pool_run(request, run_id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _error(
            code="TENANT_CONTEXT_REQUIRED",
            message="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    run = (
        PoolRun.objects.select_related("pool", "schema_template")
        .filter(id=run_id, tenant_id=tenant_id)
        .first()
    )
    if run is None:
        return _error(
            code="RUN_NOT_FOUND",
            message="Pool run not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    attempts = list(
        PoolPublicationAttempt.objects.filter(run=run).order_by(
            "target_database_id",
            "attempt_number",
            "created_at",
        )
    )
    audit_events = list(
        PoolRunAuditEvent.objects.filter(run=run).order_by("created_at", "id")
    )
    publication_hardening_cutoff_utc = _resolve_publication_hardening_cutoff_utc(tenant_id=tenant_id)
    payload = {
        "run": _serialize_run(
            run,
            publication_hardening_cutoff_utc=publication_hardening_cutoff_utc,
        ),
        "publication_attempts": [_serialize_attempt(item) for item in attempts],
        "audit_events": [_serialize_audit_event(item) for item in audit_events],
    }
    return Response(payload, status=http_status.HTTP_200_OK)


def _resolve_safe_command_readiness_blockers(
    *,
    run: PoolRun,
    outcome,
) -> list[dict[str, Any]]:
    snapshot = outcome.response_snapshot if isinstance(outcome.response_snapshot, Mapping) else {}
    blockers = _normalize_readiness_blockers(snapshot.get("readiness_blockers"))
    if blockers:
        return blockers

    if run.workflow_execution_id is None:
        return []

    execution_context = (
        WorkflowExecution.objects.filter(id=run.workflow_execution_id)
        .values_list("input_context", flat=True)
        .first()
    )
    if not isinstance(execution_context, Mapping):
        return []
    return _normalize_readiness_blockers(
        execution_context.get(POOL_RUNTIME_READINESS_BLOCKERS_CONTEXT_KEY)
    )


def _handle_pool_run_safe_command(
    *,
    request,
    run_id: UUID,
    command_type: str,
) -> Response:
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _error(
            code="TENANT_CONTEXT_REQUIRED",
            message="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    run = PoolRun.objects.filter(id=run_id, tenant_id=tenant_id).first()
    if run is None:
        return _error(
            code="RUN_NOT_FOUND",
            message="Pool run not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    idempotency_key = str(
        request.headers.get("Idempotency-Key")
        or request.META.get("HTTP_IDEMPOTENCY_KEY")
        or ""
    ).strip()
    if not idempotency_key:
        return _error(
            code="IDEMPOTENCY_KEY_REQUIRED",
            message="Idempotency-Key header is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    try:
        outcome = process_pool_run_safe_command(
            run_id=run.id,
            command_type=command_type,
            idempotency_key=idempotency_key,
            requested_by=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
        )
    except ValueError as exc:
        return _error(
            code="VALIDATION_ERROR",
            message=str(exc),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    if outcome.result_class == PoolRunCommandResultClass.CONFLICT:
        if outcome.conflict_reason == CONFLICT_REASON_READINESS_BLOCKED:
            return _problem(
                code=POOL_RUN_READINESS_BLOCKED_CODE,
                title="Pool Run Readiness Blocked",
                detail="Resolve readiness blockers before confirm-publication.",
                status_code=http_status.HTTP_409_CONFLICT,
                errors=_resolve_safe_command_readiness_blockers(run=run, outcome=outcome),
            )
        return Response(
            _safe_command_conflict_payload(run_id=run.id, conflict_reason=outcome.conflict_reason),
            status=http_status.HTTP_409_CONFLICT,
        )

    run_refresh = PoolRun.objects.get(id=run.id)
    publication_hardening_cutoff_utc = _resolve_publication_hardening_cutoff_utc(tenant_id=tenant_id)
    payload = {
        "run": _serialize_run(
            run_refresh,
            publication_hardening_cutoff_utc=publication_hardening_cutoff_utc,
        ),
        "command_type": command_type,
        "result": "accepted" if outcome.result_class == PoolRunCommandResultClass.ACCEPTED else "noop",
        "replayed": outcome.replayed,
    }
    return Response(payload, status=outcome.response_status_code)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_runs_confirm_publication",
    summary="Confirm safe-mode publication for pool run",
    responses={
        200: PoolRunSafeCommandResponseSerializer,
        202: PoolRunSafeCommandResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: ErrorResponseSerializer,
        (409, "application/json"): PoolRunSafeCommandConflictSerializer,
        (409, "application/problem+json"): PoolRunConfirmPublicationReadinessProblemDetailsSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def confirm_pool_run_publication(request, run_id: UUID):
    return _handle_pool_run_safe_command(
        request=request,
        run_id=run_id,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_runs_abort_publication",
    summary="Abort safe-mode publication for pool run",
    responses={
        200: PoolRunSafeCommandResponseSerializer,
        202: PoolRunSafeCommandResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: ErrorResponseSerializer,
        409: PoolRunSafeCommandConflictSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def abort_pool_run_publication(request, run_id: UUID):
    return _handle_pool_run_safe_command(
        request=request,
        run_id=run_id,
        command_type=PoolRunCommandType.ABORT_PUBLICATION,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_runs_retry",
    summary="Retry failed publication targets for pool run",
    request=PoolRunRetryRequestSerializer,
    responses={
        202: PoolRunRetryAcceptedResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: ErrorResponseSerializer,
        409: PoolRunSafeCommandConflictSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def retry_pool_run_failed(request, run_id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _error(
            code="TENANT_CONTEXT_REQUIRED",
            message="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    run = PoolRun.objects.filter(id=run_id, tenant_id=tenant_id).first()
    if run is None:
        return _error(
            code="RUN_NOT_FOUND",
            message="Pool run not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    serializer = PoolRunRetryRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": serializer.errors},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    if not run.workflow_execution_id:
        return _error(
            code="RUN_NOT_LINKED",
            message="Pool run is not linked to workflow execution.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    data = dict(serializer.validated_data)
    documents_by_database = data.get("documents_by_database") or {}
    requested_documents = sum(
        len(documents)
        for documents in documents_by_database.values()
        if isinstance(documents, list)
    )

    failed_target_ids = _collect_failed_target_ids_for_retry(run=run)
    if not failed_target_ids:
        return _error(
            code="NO_FAILED_TARGETS",
            message="Pool run has no failed targets to retry.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    failed_target_set = set(failed_target_ids)
    explicit_target_ids = _normalize_retry_target_ids(data.get("target_database_ids"))
    requested_target_ids = explicit_target_ids
    if not requested_target_ids and isinstance(documents_by_database, dict):
        requested_target_ids = sorted(
            {
                str(database_id or "").strip()
                for database_id in documents_by_database.keys()
                if str(database_id or "").strip()
            }
        )
    if not requested_target_ids:
        requested_target_ids = failed_target_ids

    invalid_target_ids = sorted(set(explicit_target_ids) - failed_target_set)
    if explicit_target_ids and invalid_target_ids:
        return _error(
            code="INVALID_RETRY_TARGETS",
            message=(
                "Retry targets must be failed targets only: "
                + ", ".join(invalid_target_ids)
            ),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    selected_target_ids = [
        target_id
        for target_id in requested_target_ids
        if target_id in failed_target_set
    ]
    if not selected_target_ids:
        return _error(
            code="NO_FAILED_TARGETS",
            message="Pool run has no failed targets to retry.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    filtered_documents_by_database = {
        str(database_id): documents
        for database_id, documents in documents_by_database.items()
        if str(database_id) in set(selected_target_ids)
    }
    requested_targets = len(requested_target_ids)

    retry_target_summary = {
        "requested_targets": requested_targets,
        "requested_documents": requested_documents,
        "failed_targets": len(failed_target_ids),
        "enqueued_targets": len(selected_target_ids),
        "skipped_successful_targets": max(0, requested_targets - len(selected_target_ids)),
    }

    retry_command_log: PoolRunCommandLog | None = None
    idempotency_key = str(request.META.get("HTTP_IDEMPOTENCY_KEY") or "").strip()
    if idempotency_key:
        command_fingerprint = _build_retry_command_fingerprint(
            entity_name=str(data.get("entity_name") or ""),
            target_ids=sorted(selected_target_ids),
            max_attempts=int(data.get("max_attempts", MAX_PUBLICATION_ATTEMPTS)),
            retry_interval_seconds=int(data.get("retry_interval_seconds", 0)),
            external_key_field=str(data.get("external_key_field") or "ExternalRunKey"),
            use_retry_subset_payload=bool(data.get("use_retry_subset_payload")),
        )
        pending_snapshot = {
            "accepted": True,
            "workflow_execution_id": str(run.workflow_execution_id),
            "operation_id": None,
            "retry_target_summary": retry_target_summary,
        }
        try:
            write_result = record_pool_run_command_outcome(
                run=run,
                command_type=PoolRunCommandType.RETRY_PUBLICATION,
                idempotency_key=idempotency_key,
                command_fingerprint=command_fingerprint,
                result_class=PoolRunCommandResultClass.ACCEPTED,
                response_status_code=http_status.HTTP_202_ACCEPTED,
                response_snapshot=pending_snapshot,
                created_by=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
            )
        except PoolRunCommandIdempotencyConflict:
            return Response(
                _safe_command_conflict_payload(
                    run_id=run.id,
                    conflict_reason=CONFLICT_REASON_IDEMPOTENCY_KEY_REUSED,
                ),
                status=http_status.HTTP_409_CONFLICT,
            )

        if write_result.replayed:
            snapshot = (
                write_result.entry.response_snapshot
                if isinstance(write_result.entry.response_snapshot, dict)
                else pending_snapshot
            )
            replay_payload = {
                "accepted": bool(snapshot.get("accepted", True)),
                "workflow_execution_id": str(snapshot.get("workflow_execution_id") or run.workflow_execution_id),
                "operation_id": snapshot.get("operation_id"),
                "retry_target_summary": (
                    snapshot.get("retry_target_summary")
                    if isinstance(snapshot.get("retry_target_summary"), dict)
                    else retry_target_summary
                ),
            }
            return Response(
                replay_payload,
                status=int(write_result.entry.response_status_code or http_status.HTTP_202_ACCEPTED),
            )
        retry_command_log = write_result.entry

    data["documents_by_database"] = filtered_documents_by_database
    data["target_database_ids"] = selected_target_ids
    try:
        retry_result = start_pool_run_retry_workflow_execution(
            run=run,
            retry_request=data,
            requested_by=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
        )
    except (ValueError, DjangoValidationError) as exc:
        if retry_command_log is not None:
            retry_command_log.result_class = PoolRunCommandResultClass.BAD_REQUEST
            retry_command_log.response_status_code = http_status.HTTP_400_BAD_REQUEST
            retry_command_log.response_snapshot = {"accepted": False, "error": _validation_message(exc)}
            retry_command_log.save(
                update_fields=[
                    "result_class",
                    "response_status_code",
                    "response_snapshot",
                ]
            )
        return _error(
            code="VALIDATION_ERROR",
            message=_validation_message(exc),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    payload = {
        "accepted": bool(retry_result.enqueue_success),
        "workflow_execution_id": retry_result.execution_id,
        "operation_id": retry_result.operation_id,
        "retry_target_summary": retry_target_summary,
    }
    if retry_command_log is not None:
        retry_command_log.result_class = PoolRunCommandResultClass.ACCEPTED
        retry_command_log.response_status_code = http_status.HTTP_202_ACCEPTED
        retry_command_log.response_snapshot = payload
        retry_command_log.save(
            update_fields=[
                "result_class",
                "response_status_code",
                "response_snapshot",
            ]
        )
    return Response(payload, status=http_status.HTTP_202_ACCEPTED)
