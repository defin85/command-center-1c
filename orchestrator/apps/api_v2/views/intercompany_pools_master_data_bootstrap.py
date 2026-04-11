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
    BootstrapImportPreflightBlockedError,
    cancel_pool_master_data_bootstrap_import_job,
    create_pool_master_data_bootstrap_import_job,
    get_pool_master_data_bootstrap_import_job,
    list_pool_master_data_bootstrap_import_jobs,
    retry_failed_pool_master_data_bootstrap_import_chunks,
    run_pool_master_data_bootstrap_preflight_preview,
    serialize_pool_master_data_bootstrap_import_job,
)
from apps.intercompany_pools.master_data_bootstrap_collection_service import (
    BOOTSTRAP_COLLECTION_CLUSTER_NOT_FOUND,
    BOOTSTRAP_COLLECTION_DATABASE_NOT_FOUND,
    BOOTSTRAP_COLLECTION_REQUEST_NOT_FOUND,
    create_pool_master_data_bootstrap_collection_request,
    get_pool_master_data_bootstrap_collection_request,
    list_pool_master_data_bootstrap_collection_requests,
    run_pool_master_data_bootstrap_collection_preflight_preview,
    serialize_pool_master_data_bootstrap_collection_request,
)
from apps.intercompany_pools.master_data_registry import get_pool_master_data_bootstrap_entity_types
from apps.intercompany_pools.models import (
    PoolMasterDataBootstrapCollectionMode,
    PoolMasterDataBootstrapCollectionTargetMode,
)
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


_BOOTSTRAP_ENTITY_SCOPE_CHOICES = get_pool_master_data_bootstrap_entity_types()
_BOOTSTRAP_COLLECTION_TARGET_MODE_CHOICES = [
    PoolMasterDataBootstrapCollectionTargetMode.CLUSTER_ALL,
    PoolMasterDataBootstrapCollectionTargetMode.DATABASE_SET,
]
_BOOTSTRAP_COLLECTION_MODE_CHOICES = [
    PoolMasterDataBootstrapCollectionMode.DRY_RUN,
    PoolMasterDataBootstrapCollectionMode.EXECUTE,
]


class BootstrapImportScopeRequestSerializer(serializers.Serializer):
    database_id = serializers.CharField(max_length=64)
    entity_scope = serializers.ListField(
        child=serializers.ChoiceField(choices=_BOOTSTRAP_ENTITY_SCOPE_CHOICES),
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
    entity_type = serializers.ChoiceField(choices=_BOOTSTRAP_ENTITY_SCOPE_CHOICES)
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
        child=serializers.ChoiceField(choices=_BOOTSTRAP_ENTITY_SCOPE_CHOICES)
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


class BootstrapCollectionScopeRequestSerializer(serializers.Serializer):
    target_mode = serializers.ChoiceField(choices=_BOOTSTRAP_COLLECTION_TARGET_MODE_CHOICES)
    cluster_id = serializers.UUIDField(required=False, allow_null=True)
    database_ids = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        allow_empty=True,
    )
    entity_scope = serializers.ListField(
        child=serializers.ChoiceField(choices=_BOOTSTRAP_ENTITY_SCOPE_CHOICES),
        allow_empty=False,
    )


class BootstrapCollectionCreateRequestSerializer(BootstrapCollectionScopeRequestSerializer):
    mode = serializers.ChoiceField(choices=_BOOTSTRAP_COLLECTION_MODE_CHOICES)
    chunk_size = serializers.IntegerField(required=False, min_value=1, max_value=1000, default=200)


class BootstrapCollectionListQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=200, default=20)
    offset = serializers.IntegerField(required=False, min_value=0, default=0)


class BootstrapCollectionItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    database_id = serializers.CharField()
    database_name = serializers.CharField()
    cluster_id = serializers.UUIDField(required=False, allow_null=True)
    status = serializers.CharField()
    reason_code = serializers.CharField(allow_blank=True)
    reason_detail = serializers.CharField(allow_blank=True)
    child_job_id = serializers.UUIDField(required=False, allow_null=True)
    child_job_status = serializers.CharField(allow_blank=True)
    preflight_result = serializers.JSONField(required=False)
    dry_run_summary = serializers.JSONField(required=False)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class BootstrapCollectionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    target_mode = serializers.ChoiceField(choices=_BOOTSTRAP_COLLECTION_TARGET_MODE_CHOICES)
    mode = serializers.ChoiceField(choices=_BOOTSTRAP_COLLECTION_MODE_CHOICES)
    cluster_id = serializers.UUIDField(required=False, allow_null=True)
    database_ids = serializers.ListField(child=serializers.CharField())
    entity_scope = serializers.ListField(
        child=serializers.ChoiceField(choices=_BOOTSTRAP_ENTITY_SCOPE_CHOICES)
    )
    status = serializers.CharField()
    requested_by_id = serializers.IntegerField(required=False, allow_null=True)
    requested_by_username = serializers.CharField(allow_blank=True)
    last_error_code = serializers.CharField(allow_blank=True)
    last_error = serializers.CharField(allow_blank=True)
    aggregate_counters = serializers.JSONField(required=False)
    progress = serializers.JSONField(required=False)
    child_job_status_counts = serializers.JSONField(required=False)
    aggregate_dry_run_summary = serializers.JSONField(required=False)
    audit_trail = serializers.JSONField(required=False)
    items = BootstrapCollectionItemSerializer(many=True, required=False)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class BootstrapCollectionPreflightResponseSerializer(serializers.Serializer):
    preflight = serializers.JSONField()


class BootstrapCollectionResponseSerializer(serializers.Serializer):
    collection = BootstrapCollectionSerializer()


class BootstrapCollectionListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    limit = serializers.IntegerField(min_value=1)
    offset = serializers.IntegerField(min_value=0)
    collections = BootstrapCollectionSerializer(many=True)


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
    database = Database.objects.filter(id=str(database_id or "").strip(), tenant_id=tenant_id).first()
    if database is None:
        return None, _problem(
            code="MASTER_DATA_DATABASE_NOT_FOUND",
            title="Master Data Database Not Found",
            detail="Database not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    return database, None


def _collection_exception_to_response(exc: Exception) -> Response:
    detail = str(exc) or "Bootstrap collection request failed."
    code = "VALIDATION_ERROR"
    status_code = http_status.HTTP_400_BAD_REQUEST
    if ":" in detail:
        maybe_code, maybe_detail = detail.split(":", 1)
        normalized_code = str(maybe_code or "").strip()
        if normalized_code:
            code = normalized_code
            detail = str(maybe_detail or "").strip() or detail
    if code in {
        BOOTSTRAP_COLLECTION_CLUSTER_NOT_FOUND,
        BOOTSTRAP_COLLECTION_DATABASE_NOT_FOUND,
        BOOTSTRAP_COLLECTION_REQUEST_NOT_FOUND,
    }:
        status_code = http_status.HTTP_404_NOT_FOUND
    return _problem(
        code=code,
        title="Bootstrap Collection Request Failed",
        detail=detail,
        status_code=status_code,
    )


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
    operation_id="v2_pools_master_data_bootstrap_collections_preflight",
    summary="Run bootstrap collection preflight",
    request=BootstrapCollectionScopeRequestSerializer,
    responses={
        200: BootstrapCollectionPreflightResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (403, "application/problem+json"): ProblemDetailsErrorSerializer,
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def preflight_pool_master_data_bootstrap_collection(request):
    tenant_id, access_error = _require_bootstrap_mutation_tenant_access(request)
    if access_error is not None:
        return access_error
    feature_error = _require_bootstrap_feature_enabled(tenant_id=tenant_id)
    if feature_error is not None:
        return feature_error

    serializer = BootstrapCollectionScopeRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _validation_problem(
            detail="Bootstrap collection preflight payload validation failed.",
            errors=serializer.errors,
        )
    payload = serializer.validated_data
    try:
        preflight = run_pool_master_data_bootstrap_collection_preflight_preview(
            tenant_id=str(tenant_id),
            target_mode=str(payload.get("target_mode")),
            cluster_id=str(payload.get("cluster_id")) if payload.get("cluster_id") else None,
            database_ids=list(payload.get("database_ids") or []),
            entity_scope=list(payload.get("entity_scope") or []),
            actor_id=str(request.user.id),
        )
    except (LookupError, ValueError) as exc:
        return _collection_exception_to_response(exc)
    return Response({"preflight": preflight}, status=http_status.HTTP_200_OK)


@extend_schema(
    methods=["POST"],
    tags=["v2"],
    operation_id="v2_pools_master_data_bootstrap_collections_create",
    summary="Create bootstrap collection request",
    request=BootstrapCollectionCreateRequestSerializer,
    responses={
        201: BootstrapCollectionResponseSerializer,
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
    operation_id="v2_pools_master_data_bootstrap_collections_list",
    summary="List bootstrap collection requests",
    parameters=[BootstrapCollectionListQuerySerializer],
    responses={
        200: BootstrapCollectionListResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (403, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def pool_master_data_bootstrap_collections_endpoint(request):
    if request.method == "POST":
        tenant_id, access_error = _require_bootstrap_mutation_tenant_access(request)
        if access_error is not None:
            return access_error
        feature_error = _require_bootstrap_feature_enabled(tenant_id=tenant_id)
        if feature_error is not None:
            return feature_error

        serializer = BootstrapCollectionCreateRequestSerializer(data=request.data or {})
        if not serializer.is_valid():
            return _validation_problem(
                detail="Bootstrap collection payload validation failed.",
                errors=serializer.errors,
            )
        payload = serializer.validated_data
        tenant, tenant_error = _resolve_tenant_or_problem(tenant_id=str(tenant_id))
        if tenant_error is not None:
            return tenant_error

        try:
            collection = create_pool_master_data_bootstrap_collection_request(
                tenant=tenant,
                target_mode=str(payload.get("target_mode")),
                cluster_id=str(payload.get("cluster_id")) if payload.get("cluster_id") else None,
                database_ids=list(payload.get("database_ids") or []),
                entity_scope=list(payload.get("entity_scope") or []),
                mode=str(payload.get("mode")),
                chunk_size=int(payload.get("chunk_size") or 200),
                actor_id=str(request.user.id),
                actor_username=str(getattr(request.user, "username", "") or ""),
            )
        except (LookupError, ValueError) as exc:
            return _collection_exception_to_response(exc)
        return Response(
            {
                "collection": serialize_pool_master_data_bootstrap_collection_request(
                    collection=collection,
                    include_items=False,
                )
            },
            status=http_status.HTTP_201_CREATED,
        )

    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")
    feature_error = _require_bootstrap_feature_enabled(tenant_id=str(tenant_id))
    if feature_error is not None:
        return feature_error

    serializer = BootstrapCollectionListQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return _validation_problem(detail="Invalid query parameters.", errors=serializer.errors)
    params = serializer.validated_data
    rows, count = list_pool_master_data_bootstrap_collection_requests(
        tenant_id=str(tenant_id),
        limit=int(params.get("limit") or 20),
        offset=int(params.get("offset") or 0),
    )
    return Response(
        {
            "count": count,
            "limit": int(params.get("limit") or 20),
            "offset": int(params.get("offset") or 0),
            "collections": [
                serialize_pool_master_data_bootstrap_collection_request(
                    collection=row,
                    include_items=False,
                )
                for row in rows
            ],
        },
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_bootstrap_collections_get",
    summary="Get bootstrap collection request",
    responses={
        200: BootstrapCollectionResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (403, "application/problem+json"): ProblemDetailsErrorSerializer,
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_pool_master_data_bootstrap_collection_endpoint(request, id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")
    feature_error = _require_bootstrap_feature_enabled(tenant_id=str(tenant_id))
    if feature_error is not None:
        return feature_error

    try:
        collection = get_pool_master_data_bootstrap_collection_request(
            tenant_id=str(tenant_id),
            collection_id=str(id),
        )
    except LookupError as exc:
        return _collection_exception_to_response(exc)
    return Response(
        {
            "collection": serialize_pool_master_data_bootstrap_collection_request(
                collection=collection,
                include_items=True,
            )
        },
        status=http_status.HTTP_200_OK,
    )


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
    except BootstrapImportPreflightBlockedError as exc:
        return _problem(
            code=str(exc.error_code),
            title="Bootstrap Execute Blocked by Preflight",
            detail=str(exc.detail),
            status_code=http_status.HTTP_409_CONFLICT,
            errors={"preflight": dict(exc.preflight_result)},
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
        except BootstrapImportPreflightBlockedError as exc:
            return _problem(
                code=str(exc.error_code),
                title="Bootstrap Execute Blocked by Preflight",
                detail=str(exc.detail),
                status_code=http_status.HTTP_409_CONFLICT,
                errors={"preflight": dict(exc.preflight_result)},
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
    "get_pool_master_data_bootstrap_collection_endpoint",
    "get_pool_master_data_bootstrap_import_job_endpoint",
    "pool_master_data_bootstrap_collections_endpoint",
    "pool_master_data_bootstrap_import_jobs_endpoint",
    "preflight_pool_master_data_bootstrap_collection",
    "preflight_pool_master_data_bootstrap_import",
    "retry_failed_pool_master_data_bootstrap_import_chunks_endpoint",
]
