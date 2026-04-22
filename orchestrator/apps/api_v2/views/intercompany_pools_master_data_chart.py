from __future__ import annotations

from uuid import UUID

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.api_v2.serializers.common import ProblemDetailsErrorSerializer
from apps.databases.models import Database
from apps.intercompany_pools.master_data_chart_materialization_service import (
    CHART_JOB_MODE_INVALID,
    CHART_JOB_NOT_FOUND,
    CHART_JOB_PREREQUISITE_MISSING,
    CHART_SOURCE_BUSINESS_PROFILE_MISMATCH,
    CHART_SOURCE_BUSINESS_PROFILE_MISSING,
    CHART_SOURCE_CHART_IDENTITY_REQUIRED,
    CHART_SOURCE_DATABASE_NOT_FOUND,
    CHART_SOURCE_FETCH_FAILED,
    CHART_SOURCE_NOT_FOUND,
    CHART_SOURCE_PREFLIGHT_FAILED,
    CHART_SOURCE_ROWS_EMPTY,
    create_pool_master_data_chart_job,
    get_pool_master_data_chart_job,
    list_pool_master_data_chart_jobs,
    list_pool_master_data_chart_sources,
    serialize_pool_master_data_chart_job,
    serialize_pool_master_data_chart_source,
    upsert_pool_master_data_chart_source,
)
from apps.intercompany_pools.models import PoolMasterDataChartMaterializationMode
from apps.tenancy.models import Tenant
from apps.tenancy.models import TenantMember

from .intercompany_pools import _problem, _resolve_tenant_id


def _validation_problem(*, detail: str, errors: object | None = None) -> Response:
    return _problem(
        code="VALIDATION_ERROR",
        title="Validation Error",
        detail=detail,
        status_code=http_status.HTTP_400_BAD_REQUEST,
        errors=errors,
    )


def _require_chart_mutation_tenant_access(request) -> tuple[str | None, Response | None]:
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return None, _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    is_tenant_admin = TenantMember.objects.filter(
        user_id=request.user.id,
        tenant_id=tenant_id,
        role=TenantMember.ROLE_ADMIN,
    ).exists()
    is_staff = bool(getattr(request.user, "is_staff", False) or getattr(request.user, "is_superuser", False))
    if not (is_staff or is_tenant_admin):
        return None, _problem(
            code="FORBIDDEN",
            title="Forbidden",
            detail="Tenant admin only.",
            status_code=http_status.HTTP_403_FORBIDDEN,
        )
    return str(tenant_id), None


def _resolve_tenant_or_problem(*, tenant_id: str) -> tuple[Tenant | None, Response | None]:
    tenant = Tenant.objects.filter(id=str(tenant_id or "").strip()).first()
    if tenant is None:
        return None, _problem(
            code="TENANT_NOT_FOUND",
            title="Tenant Not Found",
            detail="Tenant not found in current context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    return tenant, None


def _resolve_database_or_problem(*, tenant_id: str, database_id: str) -> tuple[Database | None, Response | None]:
    database = Database.objects.filter(id=str(database_id or "").strip(), tenant_id=str(tenant_id or "").strip()).first()
    if database is None:
        return None, _problem(
            code=CHART_SOURCE_DATABASE_NOT_FOUND,
            title="Chart Source Database Not Found",
            detail="Database not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    return database, None


def _chart_exception_to_response(exc: Exception) -> Response:
    detail = str(exc) or "Chart import request failed."
    code = "VALIDATION_ERROR"
    status_code = http_status.HTTP_400_BAD_REQUEST
    if ":" in detail:
        maybe_code, maybe_detail = detail.split(":", 1)
        normalized_code = str(maybe_code or "").strip()
        if normalized_code:
            code = normalized_code
            detail = str(maybe_detail or "").strip() or detail

    if code in {CHART_SOURCE_DATABASE_NOT_FOUND, CHART_SOURCE_NOT_FOUND, CHART_JOB_NOT_FOUND}:
        status_code = http_status.HTTP_404_NOT_FOUND
    elif code in {
        CHART_SOURCE_BUSINESS_PROFILE_MISSING,
        CHART_SOURCE_BUSINESS_PROFILE_MISMATCH,
        CHART_SOURCE_PREFLIGHT_FAILED,
        CHART_SOURCE_ROWS_EMPTY,
        CHART_SOURCE_FETCH_FAILED,
        CHART_JOB_PREREQUISITE_MISSING,
    }:
        status_code = http_status.HTTP_409_CONFLICT
    elif code in {CHART_SOURCE_CHART_IDENTITY_REQUIRED, CHART_JOB_MODE_INVALID}:
        status_code = http_status.HTTP_400_BAD_REQUEST

    return _problem(
        code=code,
        title="Chart Import Request Failed",
        detail=detail,
        status_code=status_code,
    )


_CHART_JOB_MODE_CHOICES = [choice for choice, _label in PoolMasterDataChartMaterializationMode.choices]


class ChartSourceUpsertRequestSerializer(serializers.Serializer):
    database_id = serializers.CharField(max_length=64)
    chart_identity = serializers.CharField(max_length=255)


class ChartSourceListQuerySerializer(serializers.Serializer):
    chart_identity = serializers.CharField(required=False, allow_blank=True)
    config_name = serializers.CharField(required=False, allow_blank=True)
    config_version = serializers.CharField(required=False, allow_blank=True)
    database_id = serializers.CharField(required=False, allow_blank=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=200, default=50)
    offset = serializers.IntegerField(required=False, min_value=0, default=0)


class ChartSnapshotSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    chart_source_id = serializers.UUIDField()
    fingerprint = serializers.CharField()
    row_count = serializers.IntegerField(min_value=0)
    materialized_count = serializers.IntegerField(min_value=0)
    updated_count = serializers.IntegerField(min_value=0)
    unchanged_count = serializers.IntegerField(min_value=0)
    retired_count = serializers.IntegerField(min_value=0)
    metadata = serializers.JSONField(required=False)
    created_at = serializers.DateTimeField(required=False)


class ChartJobSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    chart_source_id = serializers.UUIDField()
    snapshot = ChartSnapshotSerializer(required=False, allow_null=True)
    mode = serializers.ChoiceField(choices=_CHART_JOB_MODE_CHOICES)
    status = serializers.CharField()
    database_ids = serializers.ListField(child=serializers.CharField(), required=False)
    requested_by_username = serializers.CharField(allow_blank=True)
    last_error_code = serializers.CharField(allow_blank=True)
    last_error = serializers.CharField(allow_blank=True)
    counters = serializers.JSONField(required=False)
    diagnostics = serializers.JSONField(required=False)
    audit_trail = serializers.JSONField(required=False)
    started_at = serializers.DateTimeField(required=False, allow_null=True)
    finished_at = serializers.DateTimeField(required=False, allow_null=True)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class ChartSourceCandidateDatabaseSerializer(serializers.Serializer):
    database_id = serializers.CharField()
    database_name = serializers.CharField()
    cluster_id = serializers.UUIDField(required=False, allow_null=True)


class ChartSourceSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    database_id = serializers.CharField()
    database_name = serializers.CharField()
    cluster_id = serializers.UUIDField(required=False, allow_null=True)
    chart_identity = serializers.CharField()
    config_name = serializers.CharField()
    config_version = serializers.CharField()
    status = serializers.CharField()
    last_success_at = serializers.DateTimeField(required=False, allow_null=True)
    last_error_code = serializers.CharField(allow_blank=True)
    last_error = serializers.CharField(allow_blank=True)
    metadata = serializers.JSONField(required=False)
    latest_snapshot = ChartSnapshotSerializer(required=False, allow_null=True)
    latest_job = ChartJobSummarySerializer(required=False, allow_null=True)
    candidate_databases = ChartSourceCandidateDatabaseSerializer(many=True, required=False)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class ChartFollowerStatusSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    job_id = serializers.UUIDField()
    snapshot_id = serializers.UUIDField(required=False, allow_null=True)
    database_id = serializers.CharField()
    database_name = serializers.CharField()
    cluster_id = serializers.UUIDField(required=False, allow_null=True)
    verdict = serializers.CharField()
    detail = serializers.CharField(allow_blank=True)
    matched_accounts = serializers.IntegerField(min_value=0)
    missing_accounts = serializers.IntegerField(min_value=0)
    ambiguous_accounts = serializers.IntegerField(min_value=0)
    stale_bindings = serializers.IntegerField(min_value=0)
    backfilled_accounts = serializers.IntegerField(min_value=0)
    diagnostics = serializers.JSONField(required=False)
    bindings_remediation_href = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    last_verified_at = serializers.DateTimeField(required=False, allow_null=True)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class ChartJobSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    chart_source_id = serializers.UUIDField()
    chart_source = ChartSourceSerializer(required=False, allow_null=True)
    snapshot = ChartSnapshotSerializer(required=False, allow_null=True)
    mode = serializers.ChoiceField(choices=_CHART_JOB_MODE_CHOICES)
    status = serializers.CharField()
    database_ids = serializers.ListField(child=serializers.CharField(), required=False)
    requested_by_username = serializers.CharField(allow_blank=True)
    last_error_code = serializers.CharField(allow_blank=True)
    last_error = serializers.CharField(allow_blank=True)
    counters = serializers.JSONField(required=False)
    diagnostics = serializers.JSONField(required=False)
    audit_trail = serializers.JSONField(required=False)
    follower_statuses = ChartFollowerStatusSerializer(many=True, required=False)
    started_at = serializers.DateTimeField(required=False, allow_null=True)
    finished_at = serializers.DateTimeField(required=False, allow_null=True)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class ChartSourceResponseSerializer(serializers.Serializer):
    source = ChartSourceSerializer()


class ChartSourceListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    limit = serializers.IntegerField(min_value=1)
    offset = serializers.IntegerField(min_value=0)
    sources = ChartSourceSerializer(many=True)


class ChartJobCreateRequestSerializer(serializers.Serializer):
    chart_source_id = serializers.UUIDField()
    mode = serializers.ChoiceField(choices=_CHART_JOB_MODE_CHOICES)
    database_ids = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        allow_empty=True,
    )


class ChartJobListQuerySerializer(serializers.Serializer):
    chart_source_id = serializers.CharField(required=False, allow_blank=True)
    mode = serializers.ChoiceField(required=False, choices=_CHART_JOB_MODE_CHOICES)
    status = serializers.CharField(required=False, allow_blank=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=200, default=50)
    offset = serializers.IntegerField(required=False, min_value=0, default=0)


class ChartJobResponseSerializer(serializers.Serializer):
    job = ChartJobSerializer()


class ChartJobListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    limit = serializers.IntegerField(min_value=1)
    offset = serializers.IntegerField(min_value=0)
    jobs = ChartJobSerializer(many=True)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_chart_import_sources_list",
    summary="List chart import authoritative sources",
    parameters=[ChartSourceListQuerySerializer],
    responses={
        200: ChartSourceListResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_pool_master_data_chart_sources_endpoint(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    serializer = ChartSourceListQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return _validation_problem(detail="Invalid query parameters.", errors=serializer.errors)
    params = serializer.validated_data
    rows, count = list_pool_master_data_chart_sources(
        tenant_id=str(tenant_id),
        chart_identity=str(params.get("chart_identity") or "").strip(),
        config_name=str(params.get("config_name") or "").strip(),
        config_version=str(params.get("config_version") or "").strip(),
        database_id=str(params.get("database_id") or "").strip(),
        limit=int(params.get("limit") or 50),
        offset=int(params.get("offset") or 0),
    )
    return Response(
        {
            "count": count,
            "limit": int(params.get("limit") or 50),
            "offset": int(params.get("offset") or 0),
            "sources": [serialize_pool_master_data_chart_source(row) for row in rows],
        },
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_chart_import_sources_upsert",
    summary="Upsert chart import authoritative source",
    request=ChartSourceUpsertRequestSerializer,
    responses={
        200: ChartSourceResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (403, "application/problem+json"): ProblemDetailsErrorSerializer,
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upsert_pool_master_data_chart_source_endpoint(request):
    tenant_id, access_error = _require_chart_mutation_tenant_access(request)
    if access_error is not None:
        return access_error

    serializer = ChartSourceUpsertRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _validation_problem(detail="Chart source payload validation failed.", errors=serializer.errors)
    payload = serializer.validated_data

    tenant, tenant_error = _resolve_tenant_or_problem(tenant_id=str(tenant_id))
    if tenant_error is not None:
        return tenant_error
    database, database_error = _resolve_database_or_problem(
        tenant_id=str(tenant_id),
        database_id=str(payload.get("database_id")),
    )
    if database_error is not None:
        return database_error

    try:
        source, _created = upsert_pool_master_data_chart_source(
            tenant=tenant,
            database=database,
            chart_identity=str(payload.get("chart_identity")),
        )
    except (LookupError, ValueError) as exc:
        return _chart_exception_to_response(exc)

    return Response(
        {"source": serialize_pool_master_data_chart_source(source)},
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    methods=["POST"],
    tags=["v2"],
    operation_id="v2_pools_master_data_chart_import_jobs_create",
    summary="Create chart import job",
    request=ChartJobCreateRequestSerializer,
    responses={
        201: ChartJobResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (403, "application/problem+json"): ProblemDetailsErrorSerializer,
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@extend_schema(
    methods=["GET"],
    tags=["v2"],
    operation_id="v2_pools_master_data_chart_import_jobs_list",
    summary="List chart import jobs",
    parameters=[ChartJobListQuerySerializer],
    responses={
        200: ChartJobListResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def pool_master_data_chart_jobs_endpoint(request):
    if request.method == "POST":
        tenant_id, access_error = _require_chart_mutation_tenant_access(request)
        if access_error is not None:
            return access_error

        serializer = ChartJobCreateRequestSerializer(data=request.data or {})
        if not serializer.is_valid():
            return _validation_problem(detail="Chart job payload validation failed.", errors=serializer.errors)
        payload = serializer.validated_data

        chart_source_id = str(payload.get("chart_source_id"))
        tenant, tenant_error = _resolve_tenant_or_problem(tenant_id=str(tenant_id))
        if tenant_error is not None:
            return tenant_error
        chart_source = tenant.pool_master_data_chart_sources.filter(id=chart_source_id).first()
        if chart_source is None:
            return _problem(
                code=CHART_SOURCE_NOT_FOUND,
                title="Chart Source Not Found",
                detail=f"Chart source '{chart_source_id}' does not exist.",
                status_code=http_status.HTTP_404_NOT_FOUND,
            )

        try:
            job = create_pool_master_data_chart_job(
                tenant=tenant,
                chart_source=chart_source,
                mode=str(payload.get("mode")),
                database_ids=list(payload.get("database_ids") or []),
                requested_by_username=str(getattr(request.user, "username", "") or ""),
            )
        except (LookupError, ValueError) as exc:
            return _chart_exception_to_response(exc)

        return Response({"job": serialize_pool_master_data_chart_job(job)}, status=http_status.HTTP_201_CREATED)

    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    serializer = ChartJobListQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return _validation_problem(detail="Invalid query parameters.", errors=serializer.errors)
    params = serializer.validated_data
    rows, count = list_pool_master_data_chart_jobs(
        tenant_id=str(tenant_id),
        chart_source_id=str(params.get("chart_source_id") or "").strip(),
        mode=str(params.get("mode") or "").strip(),
        status=str(params.get("status") or "").strip(),
        limit=int(params.get("limit") or 50),
        offset=int(params.get("offset") or 0),
    )
    return Response(
        {
            "count": count,
            "limit": int(params.get("limit") or 50),
            "offset": int(params.get("offset") or 0),
            "jobs": [serialize_pool_master_data_chart_job(job) for job in rows],
        },
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_chart_import_jobs_get",
    summary="Get chart import job",
    responses={
        200: ChartJobResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_pool_master_data_chart_job_endpoint(request, id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    try:
        job = get_pool_master_data_chart_job(tenant_id=str(tenant_id), job_id=str(id))
    except (LookupError, ValueError) as exc:
        return _chart_exception_to_response(exc)
    return Response({"job": serialize_pool_master_data_chart_job(job)}, status=http_status.HTTP_200_OK)
