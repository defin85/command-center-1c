from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.api_v2.serializers.common import ErrorResponseSerializer
from apps.databases.models import Database
from apps.intercompany_pools.models import (
    Organization,
    OrganizationStatus,
    OrganizationPool,
    PoolPublicationAttempt,
    PoolEdgeVersion,
    PoolNodeVersion,
    PoolRun,
    PoolRunAuditEvent,
    PoolRunDirection,
    PoolRunMode,
    PoolSchemaTemplate,
    PoolSchemaTemplateFormat,
)
from apps.intercompany_pools.sync import sync_organizations
from apps.intercompany_pools.publication import (
    MAX_PUBLICATION_ATTEMPTS,
    MAX_RETRY_INTERVAL_SECONDS,
    retry_failed_run_documents,
)
from apps.intercompany_pools.runs import upsert_pool_run
from apps.intercompany_pools.workflow_runtime import start_pool_run_workflow_execution
from apps.templates.workflow.models import WorkflowExecution
from apps.tenancy.authentication import TENANT_HEADER
from apps.tenancy.models import Tenant


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


def _serialize_run(run: PoolRun) -> dict[str, Any]:
    workflow_status = _resolve_workflow_status(run)
    projected_status, status_reason = _project_pool_status(run=run, workflow_status=workflow_status)
    execution_backend = run.execution_backend or (
        "workflow_core" if run.workflow_execution_id else "legacy_pool_runtime"
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
        "source_hash": run.source_hash,
        "idempotency_key": run.idempotency_key,
        "workflow_execution_id": str(run.workflow_execution_id) if run.workflow_execution_id else None,
        "workflow_status": workflow_status,
        "execution_backend": execution_backend,
        "workflow_template_name": run.workflow_template_name or None,
        "seed": run.seed,
        "validation_summary": run.validation_summary,
        "publication_summary": run.publication_summary,
        "diagnostics": run.diagnostics,
        "last_error": run.last_error,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "validated_at": run.validated_at,
        "publication_confirmed_at": run.publication_confirmed_at,
        "publishing_started_at": run.publishing_started_at,
        "completed_at": run.completed_at,
    }


def _resolve_workflow_status(run: PoolRun) -> str | None:
    if not run.workflow_execution_id:
        return run.workflow_status or None

    execution_status = (
        WorkflowExecution.objects.filter(id=run.workflow_execution_id)
        .values_list("status", flat=True)
        .first()
    )
    return execution_status or run.workflow_status or None


def _project_pool_status(*, run: PoolRun, workflow_status: str | None) -> tuple[str, str | None]:
    status = run.status
    status_reason: str | None = None
    workflow_state = str(workflow_status or "").strip().lower()
    failed_targets = int((run.publication_summary or {}).get("failed_targets") or 0)
    safe_unapproved = run.mode == PoolRunMode.SAFE and run.publication_confirmed_at is None

    if workflow_state in {WorkflowExecution.STATUS_FAILED, WorkflowExecution.STATUS_CANCELLED}:
        return PoolRun.STATUS_FAILED, None

    if safe_unapproved:
        if workflow_state in {
            WorkflowExecution.STATUS_PENDING,
            WorkflowExecution.STATUS_RUNNING,
            WorkflowExecution.STATUS_COMPLETED,
            "queued",
        }:
            return PoolRun.STATUS_VALIDATED, "awaiting_approval"

    if workflow_state == WorkflowExecution.STATUS_COMPLETED:
        if failed_targets > 0:
            return PoolRun.STATUS_PARTIAL_SUCCESS, None
        return PoolRun.STATUS_PUBLISHED, None

    if workflow_state in {
        WorkflowExecution.STATUS_PENDING,
        WorkflowExecution.STATUS_RUNNING,
        "queued",
    }:
        if run.publishing_started_at is not None:
            return PoolRun.STATUS_PUBLISHING, None
        return PoolRun.STATUS_VALIDATED, "queued"

    if status == PoolRun.STATUS_VALIDATED:
        if run.mode == PoolRunMode.SAFE and run.publication_confirmed_at is None:
            status_reason = "awaiting_approval"
        else:
            status_reason = "queued"
    return status, status_reason


def _serialize_attempt(attempt: PoolPublicationAttempt) -> dict[str, Any]:
    return {
        "id": str(attempt.id),
        "run_id": str(attempt.run_id),
        "target_database_id": str(attempt.target_database_id),
        "attempt_number": attempt.attempt_number,
        "status": attempt.status,
        "entity_name": attempt.entity_name,
        "documents_count": attempt.documents_count,
        "external_document_identity": attempt.external_document_identity,
        "identity_strategy": attempt.identity_strategy,
        "posted": attempt.posted,
        "http_status": attempt.http_status,
        "error_code": attempt.error_code,
        "error_message": attempt.error_message,
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


def _serialize_organization(organization: Organization) -> dict[str, Any]:
    return {
        "id": str(organization.id),
        "tenant_id": str(organization.tenant_id),
        "database_id": str(organization.database_id) if organization.database_id else None,
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
    source_hash = serializers.CharField()
    idempotency_key = serializers.CharField()
    workflow_execution_id = serializers.UUIDField(required=False, allow_null=True)
    workflow_status = serializers.CharField(required=False, allow_null=True)
    execution_backend = serializers.CharField(required=False, allow_null=True)
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
    status = serializers.CharField()
    entity_name = serializers.CharField()
    documents_count = serializers.IntegerField()
    external_document_identity = serializers.CharField(required=False, allow_blank=True)
    identity_strategy = serializers.CharField(required=False, allow_blank=True)
    posted = serializers.BooleanField()
    http_status = serializers.IntegerField(required=False, allow_null=True)
    error_code = serializers.CharField(required=False, allow_blank=True)
    error_message = serializers.CharField(required=False, allow_blank=True)
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
    direction = serializers.ChoiceField(choices=PoolRunDirection.values)
    period_start = serializers.DateField()
    period_end = serializers.DateField(required=False, allow_null=True)
    source_hash = serializers.CharField(required=False, allow_blank=True, default="")
    mode = serializers.ChoiceField(choices=PoolRunMode.values, required=False, default=PoolRunMode.SAFE)
    schema_template_id = serializers.UUIDField(required=False, allow_null=True)
    seed = serializers.IntegerField(required=False, allow_null=True)
    validation_summary = serializers.JSONField(required=False, default=dict)
    diagnostics = serializers.ListField(child=serializers.JSONField(), required=False, default=list)


class PoolRunCreateResponseSerializer(serializers.Serializer):
    run = PoolRunSerializer()
    created = serializers.BooleanField()


class PoolRunListResponseSerializer(serializers.Serializer):
    runs = PoolRunSerializer(many=True)
    count = serializers.IntegerField()


class PoolRunDetailResponseSerializer(serializers.Serializer):
    run = PoolRunSerializer()
    publication_attempts = PoolPublicationAttemptSerializer(many=True)
    audit_events = PoolRunAuditEventSerializer(many=True)


class PoolRunRetryRequestSerializer(serializers.Serializer):
    entity_name = serializers.CharField(max_length=255)
    documents_by_database = serializers.DictField(
        child=serializers.ListField(child=serializers.JSONField()),
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


class PublicationSummarySerializer(serializers.Serializer):
    total_targets = serializers.IntegerField()
    succeeded_targets = serializers.IntegerField()
    failed_targets = serializers.IntegerField()
    max_attempts = serializers.IntegerField()


class PoolRunRetryResponseSerializer(serializers.Serializer):
    run = PoolRunSerializer()
    summary = PublicationSummarySerializer()


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


class PoolSchemaTemplateCreateResponseSerializer(serializers.Serializer):
    template = PoolSchemaTemplateSerializer()


class OrganizationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    database_id = serializers.UUIDField(required=False, allow_null=True)
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
    is_active = serializers.BooleanField()
    metadata = serializers.JSONField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class OrganizationPoolListResponseSerializer(serializers.Serializer):
    pools = OrganizationPoolSerializer(many=True)
    count = serializers.IntegerField()


class PoolGraphNodeSerializer(serializers.Serializer):
    node_version_id = serializers.UUIDField()
    organization_id = serializers.UUIDField()
    inn = serializers.CharField()
    name = serializers.CharField()
    is_root = serializers.BooleanField()


class PoolGraphEdgeSerializer(serializers.Serializer):
    edge_version_id = serializers.UUIDField()
    parent_node_version_id = serializers.UUIDField()
    child_node_version_id = serializers.UUIDField()
    weight = serializers.DecimalField(max_digits=12, decimal_places=6)
    min_amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, allow_null=True)
    max_amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, allow_null=True)


class PoolGraphResponseSerializer(serializers.Serializer):
    pool_id = serializers.UUIDField()
    date = serializers.DateField()
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
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: ErrorResponseSerializer,
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
        return _error(
            code="TENANT_CONTEXT_REQUIRED",
            message="X-CC1C-Tenant-ID is required.",
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
        payload = {
            "runs": [_serialize_run(run) for run in runs],
            "count": len(runs),
        }
        return Response(payload, status=http_status.HTTP_200_OK)

    serializer = PoolRunCreateRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": serializer.errors},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    pool = OrganizationPool.objects.filter(id=data["pool_id"], tenant_id=tenant_id).first()
    if pool is None:
        return _error(
            code="POOL_NOT_FOUND",
            message="Organization pool not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    schema_template = None
    schema_template_id = data.get("schema_template_id")
    if schema_template_id:
        schema_template = PoolSchemaTemplate.objects.filter(id=schema_template_id, tenant_id=tenant_id).first()
        if schema_template is None:
            return _error(
                code="SCHEMA_TEMPLATE_NOT_FOUND",
                message="Schema template not found in current tenant context.",
                status_code=http_status.HTTP_404_NOT_FOUND,
            )

    try:
        result = upsert_pool_run(
            tenant=pool.tenant,
            pool=pool,
            direction=data["direction"],
            period_start=data["period_start"],
            period_end=data.get("period_end"),
            source_hash=data.get("source_hash", ""),
            mode=data.get("mode", PoolRunMode.SAFE),
            schema_template=schema_template,
            seed=data.get("seed"),
            created_by=request.user if request.user and request.user.is_authenticated else None,
            validation_summary=data.get("validation_summary"),
            diagnostics=data.get("diagnostics"),
        )
    except ValueError as exc:
        return _error(
            code="VALIDATION_ERROR",
            message=str(exc),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    runtime_result = start_pool_run_workflow_execution(
        run=result.run,
        requested_by=request.user if request.user and request.user.is_authenticated else None,
    )

    payload = {
        "run": _serialize_run(runtime_result.run),
        "created": result.created,
    }
    response_status = http_status.HTTP_201_CREATED if result.created else http_status.HTTP_200_OK
    return Response(payload, status=response_status)


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

    queryset = Organization.objects.filter(tenant_id=tenant_id).select_related("database")
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

    organization = Organization.objects.filter(id=organization_id, tenant_id=tenant_id).select_related("database").first()
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
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: ErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upsert_organization(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _error(
            code="TENANT_CONTEXT_REQUIRED",
            message="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    serializer = OrganizationUpsertRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": serializer.errors},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    organization = None
    organization_id = data.get("organization_id")
    if organization_id:
        organization = Organization.objects.filter(id=organization_id, tenant_id=tenant_id).first()
        if organization is None:
            return _error(
                code="ORGANIZATION_NOT_FOUND",
                message="Organization not found in current tenant context.",
                status_code=http_status.HTTP_404_NOT_FOUND,
            )
    if organization is None:
        organization = Organization.objects.filter(tenant_id=tenant_id, inn=data["inn"]).first()

    if organization is not None and organization.inn != data["inn"]:
        if Organization.objects.filter(tenant_id=tenant_id, inn=data["inn"]).exclude(id=organization.id).exists():
            return _error(
                code="DUPLICATE_ORGANIZATION_INN",
                message="Organization with this INN already exists in current tenant.",
                status_code=http_status.HTTP_400_BAD_REQUEST,
            )

    database = None
    if "database_id" in data:
        database_id = data.get("database_id")
        if database_id is not None:
            database = Database.objects.filter(id=database_id, tenant_id=tenant_id).first()
            if database is None:
                return _error(
                    code="DATABASE_NOT_FOUND",
                    message="Database not found in current tenant context.",
                    status_code=http_status.HTTP_404_NOT_FOUND,
                )
            conflict_qs = Organization.objects.filter(tenant_id=tenant_id, database=database)
            if organization is not None:
                conflict_qs = conflict_qs.exclude(id=organization.id)
            if conflict_qs.exists():
                return _error(
                    code="DATABASE_ALREADY_LINKED",
                    message="Database is already linked to another organization.",
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                )

    created = organization is None
    status_value = data.get("status", organization.status if organization else OrganizationStatus.ACTIVE)
    metadata_value = data.get("metadata", organization.metadata if organization else {})
    full_name = data.get("full_name", organization.full_name if organization else "")
    kpp = data.get("kpp", organization.kpp if organization else "")
    external_ref = data.get("external_ref", organization.external_ref if organization else "")
    database_value = database if "database_id" in data else (organization.database if organization else None)

    try:
        if created:
            organization = Organization.objects.create(
                tenant_id=tenant_id,
                database=database_value,
                name=data["name"],
                full_name=full_name,
                inn=data["inn"],
                kpp=kpp,
                status=status_value,
                external_ref=external_ref,
                metadata=metadata_value,
            )
        else:
            changed_fields: list[str] = []
            updates = {
                "database": database_value,
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
                organization.save(update_fields=[*changed_fields, "updated_at"])
    except IntegrityError:
        return _error(
            code="DUPLICATE_ORGANIZATION_INN",
            message="Organization with this INN already exists in current tenant.",
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
        "pools": [
            {
                "id": str(pool.id),
                "code": pool.code,
                "name": pool.name,
                "is_active": pool.is_active,
                "metadata": pool.metadata if isinstance(pool.metadata, dict) else {},
                "updated_at": pool.updated_at,
            }
            for pool in pools
        ],
        "count": len(pools),
    }
    return Response(payload, status=http_status.HTTP_200_OK)


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

    active_nodes = list(
        PoolNodeVersion.objects.select_related("organization")
        .filter(pool=pool, effective_from__lte=target_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target_date))
        .order_by("-is_root", "organization__name")
    )
    active_node_ids = {str(node.id) for node in active_nodes}
    active_edges = list(
        PoolEdgeVersion.objects.filter(pool=pool, effective_from__lte=target_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target_date))
        .order_by("parent_node_id", "child_node_id")
    )
    filtered_edges = [
        edge
        for edge in active_edges
        if str(edge.parent_node_id) in active_node_ids and str(edge.child_node_id) in active_node_ids
    ]
    payload = {
        "pool_id": str(pool.id),
        "date": target_date,
        "nodes": [
            {
                "node_version_id": str(node.id),
                "organization_id": str(node.organization_id),
                "inn": node.organization.inn,
                "name": node.organization.name,
                "is_root": node.is_root,
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
            }
            for edge in filtered_edges
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
    payload = {
        "run": _serialize_run(run),
        "publication_attempts": [_serialize_attempt(item) for item in attempts],
        "validation_summary": run.validation_summary,
        "publication_summary": run.publication_summary,
        "diagnostics": run.diagnostics,
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
    payload = {
        "run": _serialize_run(run),
        "publication_attempts": [_serialize_attempt(item) for item in attempts],
        "audit_events": [_serialize_audit_event(item) for item in audit_events],
    }
    return Response(payload, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_runs_retry",
    summary="Retry failed publication targets for pool run",
    request=PoolRunRetryRequestSerializer,
    responses={
        200: PoolRunRetryResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: ErrorResponseSerializer,
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

    data = serializer.validated_data
    try:
        summary = retry_failed_run_documents(
            run=run,
            entity_name=data["entity_name"],
            documents_by_database=data["documents_by_database"],
            max_attempts=data.get("max_attempts", MAX_PUBLICATION_ATTEMPTS),
            retry_interval_seconds=data.get("retry_interval_seconds", 0),
            external_key_field=data.get("external_key_field", "ExternalRunKey"),
        )
    except (ValueError, DjangoValidationError) as exc:
        return _error(
            code="VALIDATION_ERROR",
            message=_validation_message(exc),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    run_fresh = PoolRun.objects.get(id=run.id)
    payload = {
        "run": _serialize_run(run_fresh),
        "summary": {
            "total_targets": summary.total_targets,
            "succeeded_targets": summary.succeeded_targets,
            "failed_targets": summary.failed_targets,
            "max_attempts": summary.max_attempts,
        },
    }
    return Response(payload, status=http_status.HTTP_200_OK)
