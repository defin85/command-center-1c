from __future__ import annotations

from uuid import UUID

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.api_v2.serializers.common import ProblemDetailsErrorSerializer
from apps.databases.models import Database
from apps.intercompany_pools.master_data_bootstrap_import_feature_flags import (
    MasterDataBootstrapImportConfigInvalidError,
    is_pool_master_data_bootstrap_import_enabled,
)
from apps.intercompany_pools.master_data_bootstrap_import_service import (
    BOOTSTRAP_IMPORT_MODE_DRY_RUN,
    BOOTSTRAP_IMPORT_MODE_EXECUTE,
    cancel_pool_master_data_bootstrap_import_job,
    create_pool_master_data_bootstrap_import_job,
    get_pool_master_data_bootstrap_import_job,
    list_pool_master_data_bootstrap_import_jobs,
    retry_failed_pool_master_data_bootstrap_import_chunks,
    run_pool_master_data_bootstrap_preflight_preview,
    serialize_pool_master_data_bootstrap_import_job,
)
from apps.intercompany_pools.models import PoolMasterDataBootstrapImportEntityType
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


def _require_bootstrap_mutation_tenant_access(request) -> tuple[str | None, Response | None]:
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


def _require_bootstrap_feature_enabled(*, tenant_id: str | None) -> Response | None:
    try:
        enabled = is_pool_master_data_bootstrap_import_enabled(
            tenant_id=str(tenant_id or "").strip() or None,
            fail_closed_on_invalid=True,
        )
    except MasterDataBootstrapImportConfigInvalidError as exc:
        return _problem(
            code=str(exc.code),
            title="Bootstrap Import Flag Invalid",
            detail=str(exc.detail),
            status_code=http_status.HTTP_409_CONFLICT,
            errors={
                "runtime_key": str(exc.runtime_key),
                "source": str(exc.source),
                "raw_value": repr(exc.raw_value),
            },
        )
    if not enabled:
        return _problem(
            code="BOOTSTRAP_IMPORT_DISABLED",
            title="Bootstrap Import Disabled",
            detail="Bootstrap import feature flag is disabled.",
            status_code=http_status.HTTP_403_FORBIDDEN,
        )
    return None


class BootstrapImportScopeRequestSerializer(serializers.Serializer):
    database_id = serializers.CharField(max_length=64)
    entity_scope = serializers.ListField(
        child=serializers.ChoiceField(choices=PoolMasterDataBootstrapImportEntityType.values),
        allow_empty=False,
    )


class BootstrapImportCreateJobRequestSerializer(BootstrapImportScopeRequestSerializer):
    mode = serializers.ChoiceField(choices=[BOOTSTRAP_IMPORT_MODE_DRY_RUN, BOOTSTRAP_IMPORT_MODE_EXECUTE])
    chunk_size = serializers.IntegerField(required=False, min_value=1, max_value=1000, default=200)


class BootstrapImportListQuerySerializer(serializers.Serializer):
    database_id = serializers.CharField(required=False, max_length=64)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=200, default=50)
    offset = serializers.IntegerField(required=False, min_value=0, default=0)


class BootstrapImportChunkSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    job_id = serializers.UUIDField()
    entity_type = serializers.ChoiceField(choices=PoolMasterDataBootstrapImportEntityType.values)
    chunk_index = serializers.IntegerField(min_value=0)
    status = serializers.CharField()
    attempt_count = serializers.IntegerField(min_value=0)
    idempotency_key = serializers.CharField(allow_blank=True)
    records_total = serializers.IntegerField(min_value=0)
    records_created = serializers.IntegerField(min_value=0)
    records_updated = serializers.IntegerField(min_value=0)
    records_skipped = serializers.IntegerField(min_value=0)
    records_failed = serializers.IntegerField(min_value=0)
    last_error_code = serializers.CharField(allow_blank=True)
    last_error = serializers.CharField(allow_blank=True)
    diagnostics = serializers.JSONField(required=False)
    metadata = serializers.JSONField(required=False)
    started_at = serializers.DateTimeField(required=False, allow_null=True)
    finished_at = serializers.DateTimeField(required=False, allow_null=True)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class BootstrapImportJobSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    database_id = serializers.CharField()
    entity_scope = serializers.ListField(
        child=serializers.ChoiceField(choices=PoolMasterDataBootstrapImportEntityType.values)
    )
    status = serializers.CharField()
    started_at = serializers.DateTimeField(required=False, allow_null=True)
    finished_at = serializers.DateTimeField(required=False, allow_null=True)
    last_error_code = serializers.CharField(allow_blank=True)
    last_error = serializers.CharField(allow_blank=True)
    preflight_result = serializers.JSONField(required=False)
    dry_run_summary = serializers.JSONField(required=False)
    progress = serializers.JSONField(required=False)
    audit_trail = serializers.JSONField(required=False)
    report = serializers.JSONField(required=False)
    chunks = BootstrapImportChunkSerializer(many=True, required=False)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class BootstrapImportPreflightResponseSerializer(serializers.Serializer):
    preflight = serializers.JSONField()


class BootstrapImportJobResponseSerializer(serializers.Serializer):
    job = BootstrapImportJobSerializer()


class BootstrapImportJobListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    limit = serializers.IntegerField(min_value=1)
    offset = serializers.IntegerField(min_value=0)
    jobs = BootstrapImportJobSerializer(many=True)


def _resolve_database_or_problem(*, tenant_id: str, database_id: str) -> tuple[Database | None, Response | None]:
    database = Database.objects.filter(id=str(database_id or "").strip(), tenant_id=tenant_id).first()
    if database is None:
        return None, _problem(
            code="MASTER_DATA_DATABASE_NOT_FOUND",
            title="Master Data Database Not Found",
            detail="Database not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    return database, None


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_bootstrap_import_preflight",
    summary="Run bootstrap import preflight",
    request=BootstrapImportScopeRequestSerializer,
    responses={
        200: BootstrapImportPreflightResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (403, "application/problem+json"): ProblemDetailsErrorSerializer,
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def preflight_pool_master_data_bootstrap_import(request):
    tenant_id, access_error = _require_bootstrap_mutation_tenant_access(request)
    if access_error is not None:
        return access_error
    feature_error = _require_bootstrap_feature_enabled(tenant_id=tenant_id)
    if feature_error is not None:
        return feature_error

    serializer = BootstrapImportScopeRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _validation_problem(detail="Bootstrap preflight payload validation failed.", errors=serializer.errors)
    payload = serializer.validated_data

    database, database_error = _resolve_database_or_problem(
        tenant_id=str(tenant_id),
        database_id=str(payload.get("database_id")),
    )
    if database_error is not None:
        return database_error

    preflight = run_pool_master_data_bootstrap_preflight_preview(
        tenant_id=str(tenant_id),
        database=database,
        entity_scope=list(payload.get("entity_scope") or []),
        actor_id=str(request.user.id),
    )
    return Response({"preflight": preflight}, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_bootstrap_import_jobs_create",
    summary="Create bootstrap import job (dry-run or execute)",
    request=BootstrapImportCreateJobRequestSerializer,
    responses={
        201: BootstrapImportJobResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (403, "application/problem+json"): ProblemDetailsErrorSerializer,
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_pool_master_data_bootstrap_import_job_endpoint(request):
    tenant_id, access_error = _require_bootstrap_mutation_tenant_access(request)
    if access_error is not None:
        return access_error
    feature_error = _require_bootstrap_feature_enabled(tenant_id=tenant_id)
    if feature_error is not None:
        return feature_error

    serializer = BootstrapImportCreateJobRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _validation_problem(detail="Bootstrap job payload validation failed.", errors=serializer.errors)
    payload = serializer.validated_data

    database, database_error = _resolve_database_or_problem(
        tenant_id=str(tenant_id),
        database_id=str(payload.get("database_id")),
    )
    if database_error is not None:
        return database_error

    try:
        job = create_pool_master_data_bootstrap_import_job(
            tenant=database.tenant,
            database=database,
            entity_scope=list(payload.get("entity_scope") or []),
            mode=str(payload.get("mode")),
            chunk_size=int(payload.get("chunk_size") or 200),
            actor_id=str(request.user.id),
        )
    except ValueError as exc:
        return _validation_problem(detail=str(exc))

    return Response(
        {"job": serialize_pool_master_data_bootstrap_import_job(job=job, include_chunks=False)},
        status=http_status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_bootstrap_import_jobs_list",
    summary="List bootstrap import jobs",
    parameters=[BootstrapImportListQuerySerializer],
    responses={
        200: BootstrapImportJobListResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (403, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_pool_master_data_bootstrap_import_jobs_endpoint(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")
    feature_error = _require_bootstrap_feature_enabled(tenant_id=str(tenant_id))
    if feature_error is not None:
        return feature_error

    serializer = BootstrapImportListQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return _validation_problem(detail="Invalid query parameters.", errors=serializer.errors)
    params = serializer.validated_data
    rows, count = list_pool_master_data_bootstrap_import_jobs(
        tenant_id=str(tenant_id),
        database_id=str(params.get("database_id") or "").strip() or None,
        limit=int(params.get("limit") or 50),
        offset=int(params.get("offset") or 0),
    )
    jobs = [serialize_pool_master_data_bootstrap_import_job(job=row, include_chunks=False) for row in rows]
    return Response(
        {
            "count": count,
            "limit": int(params.get("limit") or 50),
            "offset": int(params.get("offset") or 0),
            "jobs": jobs,
        },
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    methods=["POST"],
    tags=["v2"],
    operation_id="v2_pools_master_data_bootstrap_import_jobs_create",
    summary="Create bootstrap import job (dry-run or execute)",
    request=BootstrapImportCreateJobRequestSerializer,
    responses={
        201: BootstrapImportJobResponseSerializer,
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
    operation_id="v2_pools_master_data_bootstrap_import_jobs_list",
    summary="List bootstrap import jobs",
    parameters=[BootstrapImportListQuerySerializer],
    responses={
        200: BootstrapImportJobListResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (403, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def pool_master_data_bootstrap_import_jobs_endpoint(request):
    if request.method == "POST":
        tenant_id, access_error = _require_bootstrap_mutation_tenant_access(request)
        if access_error is not None:
            return access_error
        feature_error = _require_bootstrap_feature_enabled(tenant_id=tenant_id)
        if feature_error is not None:
            return feature_error

        serializer = BootstrapImportCreateJobRequestSerializer(data=request.data or {})
        if not serializer.is_valid():
            return _validation_problem(detail="Bootstrap job payload validation failed.", errors=serializer.errors)
        payload = serializer.validated_data

        database, database_error = _resolve_database_or_problem(
            tenant_id=str(tenant_id),
            database_id=str(payload.get("database_id")),
        )
        if database_error is not None:
            return database_error

        try:
            job = create_pool_master_data_bootstrap_import_job(
                tenant=database.tenant,
                database=database,
                entity_scope=list(payload.get("entity_scope") or []),
                mode=str(payload.get("mode")),
                chunk_size=int(payload.get("chunk_size") or 200),
                actor_id=str(request.user.id),
            )
        except ValueError as exc:
            return _validation_problem(detail=str(exc))

        return Response(
            {"job": serialize_pool_master_data_bootstrap_import_job(job=job, include_chunks=False)},
            status=http_status.HTTP_201_CREATED,
        )

    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")
    feature_error = _require_bootstrap_feature_enabled(tenant_id=str(tenant_id))
    if feature_error is not None:
        return feature_error

    serializer = BootstrapImportListQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return _validation_problem(detail="Invalid query parameters.", errors=serializer.errors)
    params = serializer.validated_data
    rows, count = list_pool_master_data_bootstrap_import_jobs(
        tenant_id=str(tenant_id),
        database_id=str(params.get("database_id") or "").strip() or None,
        limit=int(params.get("limit") or 50),
        offset=int(params.get("offset") or 0),
    )
    jobs = [serialize_pool_master_data_bootstrap_import_job(job=row, include_chunks=False) for row in rows]
    return Response(
        {
            "count": count,
            "limit": int(params.get("limit") or 50),
            "offset": int(params.get("offset") or 0),
            "jobs": jobs,
        },
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_bootstrap_import_jobs_get",
    summary="Get bootstrap import job",
    responses={
        200: BootstrapImportJobResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (403, "application/problem+json"): ProblemDetailsErrorSerializer,
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_pool_master_data_bootstrap_import_job_endpoint(request, id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")
    feature_error = _require_bootstrap_feature_enabled(tenant_id=str(tenant_id))
    if feature_error is not None:
        return feature_error

    try:
        job = get_pool_master_data_bootstrap_import_job(
            tenant_id=str(tenant_id),
            job_id=str(id),
        )
    except LookupError:
        return _problem(
            code="BOOTSTRAP_IMPORT_JOB_NOT_FOUND",
            title="Bootstrap Import Job Not Found",
            detail=f"Bootstrap import job '{id}' does not exist.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    return Response(
        {"job": serialize_pool_master_data_bootstrap_import_job(job=job, include_chunks=True)},
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_bootstrap_import_jobs_cancel",
    summary="Cancel bootstrap import job",
    request=None,
    responses={
        200: BootstrapImportJobResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (403, "application/problem+json"): ProblemDetailsErrorSerializer,
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_pool_master_data_bootstrap_import_job_endpoint(request, id: UUID):
    tenant_id, access_error = _require_bootstrap_mutation_tenant_access(request)
    if access_error is not None:
        return access_error
    feature_error = _require_bootstrap_feature_enabled(tenant_id=tenant_id)
    if feature_error is not None:
        return feature_error

    try:
        job = cancel_pool_master_data_bootstrap_import_job(
            tenant_id=str(tenant_id),
            job_id=str(id),
            actor_id=str(request.user.id),
        )
    except LookupError:
        return _problem(
            code="BOOTSTRAP_IMPORT_JOB_NOT_FOUND",
            title="Bootstrap Import Job Not Found",
            detail=f"Bootstrap import job '{id}' does not exist.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    return Response(
        {"job": serialize_pool_master_data_bootstrap_import_job(job=job, include_chunks=True)},
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_bootstrap_import_jobs_retry_failed_chunks",
    summary="Retry failed bootstrap import chunks",
    request=None,
    responses={
        200: BootstrapImportJobResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (403, "application/problem+json"): ProblemDetailsErrorSerializer,
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def retry_failed_pool_master_data_bootstrap_import_chunks_endpoint(request, id: UUID):
    tenant_id, access_error = _require_bootstrap_mutation_tenant_access(request)
    if access_error is not None:
        return access_error
    feature_error = _require_bootstrap_feature_enabled(tenant_id=tenant_id)
    if feature_error is not None:
        return feature_error

    try:
        job = retry_failed_pool_master_data_bootstrap_import_chunks(
            tenant_id=str(tenant_id),
            job_id=str(id),
            actor_id=str(request.user.id),
        )
    except LookupError:
        return _problem(
            code="BOOTSTRAP_IMPORT_JOB_NOT_FOUND",
            title="Bootstrap Import Job Not Found",
            detail=f"Bootstrap import job '{id}' does not exist.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    except ValueError as exc:
        return _validation_problem(detail=str(exc))

    return Response(
        {"job": serialize_pool_master_data_bootstrap_import_job(job=job, include_chunks=True)},
        status=http_status.HTTP_200_OK,
    )


__all__ = [
    "cancel_pool_master_data_bootstrap_import_job_endpoint",
    "get_pool_master_data_bootstrap_import_job_endpoint",
    "pool_master_data_bootstrap_import_jobs_endpoint",
    "preflight_pool_master_data_bootstrap_import",
    "retry_failed_pool_master_data_bootstrap_import_chunks_endpoint",
]
