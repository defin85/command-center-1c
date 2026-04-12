from __future__ import annotations

from typing import Any
from uuid import UUID

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.api_v2.serializers.common import ProblemDetailsErrorSerializer
from apps.databases.models import Cluster, Database
from apps.intercompany_pools.master_data_sync_launch_service import (
    SYNC_LAUNCH_CLUSTER_NOT_FOUND,
    SYNC_LAUNCH_DATABASE_NOT_FOUND,
    SYNC_LAUNCH_EMPTY_TARGETS,
    SYNC_LAUNCH_REQUEST_NOT_FOUND,
    create_pool_master_data_sync_launch_request,
    get_pool_master_data_sync_launch_request,
    list_pool_master_data_sync_launch_requests,
    serialize_pool_master_data_sync_launch_request,
)
from apps.intercompany_pools.master_data_sync_conflict_actions import (
    reconcile_master_data_sync_conflict,
    resolve_master_data_sync_conflict,
    retry_master_data_sync_conflict,
)
from apps.intercompany_pools.master_data_registry import (
    POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND,
    POOL_MASTER_DATA_CAPABILITY_SYNC_OUTBOUND,
    POOL_MASTER_DATA_CAPABILITY_SYNC_RECONCILE,
    get_pool_master_data_entity_types_for_capabilities,
)
from apps.intercompany_pools.master_data_sync_read_model import list_master_data_sync_status_rows
from apps.intercompany_pools.models import (
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncConflictStatus,
    PoolMasterDataSyncLaunchMode,
    PoolMasterDataSyncLaunchStatus,
    PoolMasterDataSyncLaunchTargetMode,
)
from apps.tenancy.models import Tenant
from apps.tenancy.models import TenantMember

from .intercompany_pools import _problem, _resolve_tenant_id
from .rbac.serializers_core import RefClustersResponseSerializer, RefDatabasesResponseSerializer

SCHEDULING_PRIORITY_CHOICES = ["p0", "p1", "p2", "p3"]
SCHEDULING_ROLE_CHOICES = ["inbound", "outbound", "reconcile", "manual_remediation"]
_SYNC_ENTITY_TYPE_CHOICES = get_pool_master_data_entity_types_for_capabilities(
    POOL_MASTER_DATA_CAPABILITY_SYNC_OUTBOUND,
    POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND,
    POOL_MASTER_DATA_CAPABILITY_SYNC_RECONCILE,
)


def _validation_problem(*, detail: str, errors: object | None = None) -> Response:
    return _problem(
        code="VALIDATION_ERROR",
        title="Validation Error",
        detail=detail,
        status_code=http_status.HTTP_400_BAD_REQUEST,
        errors=errors,
    )


def _require_sync_mutation_tenant_access(request) -> tuple[str | None, Response | None]:
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


def _serialize_sync_conflict(conflict: PoolMasterDataSyncConflict) -> dict[str, Any]:
    return {
        "id": str(conflict.id),
        "tenant_id": str(conflict.tenant_id),
        "database_id": str(conflict.database_id),
        "entity_type": str(conflict.entity_type),
        "status": str(conflict.status),
        "conflict_code": str(conflict.conflict_code),
        "canonical_id": str(conflict.canonical_id or ""),
        "origin_system": str(conflict.origin_system or ""),
        "origin_event_id": str(conflict.origin_event_id or ""),
        "diagnostics": dict(conflict.diagnostics or {}),
        "metadata": dict(conflict.metadata or {}),
        "resolved_at": conflict.resolved_at,
        "resolved_by_id": str(conflict.resolved_by_id) if conflict.resolved_by_id else None,
        "created_at": conflict.created_at,
        "updated_at": conflict.updated_at,
    }


class MasterDataSyncStatusQuerySerializer(serializers.Serializer):
    database_id = serializers.UUIDField(required=False)
    entity_type = serializers.ChoiceField(required=False, choices=_SYNC_ENTITY_TYPE_CHOICES)
    priority = serializers.ChoiceField(required=False, choices=SCHEDULING_PRIORITY_CHOICES)
    role = serializers.ChoiceField(required=False, choices=SCHEDULING_ROLE_CHOICES)
    server_affinity = serializers.CharField(required=False, allow_blank=False, max_length=128)
    deadline_state = serializers.ChoiceField(
        required=False,
        choices=["none", "pending", "met", "missed"],
    )


class MasterDataSyncStatusRowSerializer(serializers.Serializer):
    tenant_id = serializers.UUIDField()
    database_id = serializers.UUIDField()
    entity_type = serializers.ChoiceField(choices=_SYNC_ENTITY_TYPE_CHOICES)
    checkpoint_token = serializers.CharField(allow_blank=True)
    pending_checkpoint_token = serializers.CharField(allow_blank=True)
    checkpoint_status = serializers.CharField(allow_blank=True)
    pending_count = serializers.IntegerField(min_value=0)
    retry_count = serializers.IntegerField(min_value=0)
    conflict_pending_count = serializers.IntegerField(min_value=0)
    conflict_retrying_count = serializers.IntegerField(min_value=0)
    lag_seconds = serializers.IntegerField(min_value=0)
    last_success_at = serializers.DateTimeField(required=False, allow_null=True)
    last_applied_at = serializers.DateTimeField(required=False, allow_null=True)
    last_error_code = serializers.CharField(allow_blank=True)
    last_error_reason = serializers.CharField(allow_blank=True)
    priority = serializers.CharField(allow_blank=True)
    role = serializers.CharField(allow_blank=True)
    server_affinity = serializers.CharField(allow_blank=True)
    deadline_at = serializers.CharField(allow_blank=True)
    deadline_state = serializers.ChoiceField(choices=["none", "pending", "met", "missed"])
    queue_states = serializers.DictField(child=serializers.IntegerField(min_value=0))


class MasterDataSyncStatusListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    statuses = MasterDataSyncStatusRowSerializer(many=True)


class RetryConflictRequestSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=512)
    metadata = serializers.DictField(required=False)


class ReconcileConflictRequestSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=512)
    reconcile_payload = serializers.DictField(required=False, default=dict)


class ResolveConflictRequestSerializer(serializers.Serializer):
    resolution_code = serializers.CharField(required=True, max_length=64)
    note = serializers.CharField(required=False, allow_blank=True, max_length=512)
    metadata = serializers.DictField(required=False, default=dict)


class SyncConflictActionResponseSerializer(serializers.Serializer):
    conflict = serializers.DictField()


class SyncConflictListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    conflicts = serializers.ListField(child=serializers.DictField())


class MasterDataSyncConflictListQuerySerializer(serializers.Serializer):
    database_id = serializers.UUIDField(required=False)
    entity_type = serializers.ChoiceField(required=False, choices=_SYNC_ENTITY_TYPE_CHOICES)
    status = serializers.ChoiceField(required=False, choices=PoolMasterDataSyncConflictStatus.values)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=500, default=100)


_SYNC_LAUNCH_MODE_CHOICES = list(PoolMasterDataSyncLaunchMode.values)
_SYNC_LAUNCH_TARGET_MODE_CHOICES = list(PoolMasterDataSyncLaunchTargetMode.values)
_SYNC_LAUNCH_STATUS_CHOICES = list(PoolMasterDataSyncLaunchStatus.values)


class SyncLaunchCreateRequestSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=_SYNC_LAUNCH_MODE_CHOICES)
    target_mode = serializers.ChoiceField(choices=_SYNC_LAUNCH_TARGET_MODE_CHOICES)
    cluster_id = serializers.UUIDField(required=False, allow_null=True)
    database_ids = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        allow_empty=True,
    )
    entity_scope = serializers.ListField(
        child=serializers.ChoiceField(choices=_SYNC_ENTITY_TYPE_CHOICES),
        allow_empty=False,
    )


class SyncLaunchListQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=200, default=20)
    offset = serializers.IntegerField(required=False, min_value=0, default=0)


class SyncTargetDatabasesQuerySerializer(serializers.Serializer):
    cluster_id = serializers.UUIDField(required=False)


class SyncLaunchItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    database_id = serializers.CharField()
    database_name = serializers.CharField()
    cluster_id = serializers.UUIDField(required=False, allow_null=True)
    entity_type = serializers.ChoiceField(choices=_SYNC_ENTITY_TYPE_CHOICES)
    status = serializers.CharField()
    reason_code = serializers.CharField(allow_blank=True)
    reason_detail = serializers.CharField(allow_blank=True)
    child_job_id = serializers.UUIDField(required=False, allow_null=True)
    child_job_status = serializers.CharField(allow_blank=True)
    child_workflow_execution_id = serializers.UUIDField(required=False, allow_null=True)
    child_operation_id = serializers.UUIDField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class SyncLaunchSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    mode = serializers.ChoiceField(choices=_SYNC_LAUNCH_MODE_CHOICES)
    target_mode = serializers.ChoiceField(choices=_SYNC_LAUNCH_TARGET_MODE_CHOICES)
    cluster_id = serializers.UUIDField(required=False, allow_null=True)
    database_ids = serializers.ListField(child=serializers.CharField())
    entity_scope = serializers.ListField(
        child=serializers.ChoiceField(choices=_SYNC_ENTITY_TYPE_CHOICES)
    )
    status = serializers.ChoiceField(choices=_SYNC_LAUNCH_STATUS_CHOICES)
    workflow_execution_id = serializers.UUIDField(required=False, allow_null=True)
    operation_id = serializers.UUIDField(required=False, allow_null=True)
    requested_by_id = serializers.IntegerField(required=False, allow_null=True)
    requested_by_username = serializers.CharField(allow_blank=True)
    last_error_code = serializers.CharField(allow_blank=True)
    last_error = serializers.CharField(allow_blank=True)
    aggregate_counters = serializers.JSONField(required=False)
    progress = serializers.JSONField(required=False)
    child_job_status_counts = serializers.JSONField(required=False)
    audit_trail = serializers.JSONField(required=False)
    items = SyncLaunchItemSerializer(many=True, required=False)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class SyncLaunchResponseSerializer(serializers.Serializer):
    launch = SyncLaunchSerializer()


class SyncLaunchListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    limit = serializers.IntegerField(min_value=1)
    offset = serializers.IntegerField(min_value=0)
    launches = SyncLaunchSerializer(many=True)


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


def _sync_launch_exception_to_response(exc: Exception) -> Response:
    detail = str(exc) or "Sync launch request failed."
    code = "VALIDATION_ERROR"
    status_code = http_status.HTTP_400_BAD_REQUEST
    if ":" in detail:
        maybe_code, maybe_detail = detail.split(":", 1)
        normalized_code = str(maybe_code or "").strip()
        if normalized_code:
            code = normalized_code
            detail = str(maybe_detail or "").strip() or detail
    if code in {
        SYNC_LAUNCH_CLUSTER_NOT_FOUND,
        SYNC_LAUNCH_DATABASE_NOT_FOUND,
        SYNC_LAUNCH_REQUEST_NOT_FOUND,
    }:
        status_code = http_status.HTTP_404_NOT_FOUND
    if code == SYNC_LAUNCH_EMPTY_TARGETS:
        status_code = http_status.HTTP_409_CONFLICT
    return _problem(
        code=code,
        title="Sync Launch Invalid",
        detail=detail,
        status_code=status_code,
    )


@extend_schema(
    methods=["GET"],
    summary="List master-data sync launches",
    request=None,
    parameters=[SyncLaunchListQuerySerializer],
    responses={
        200: SyncLaunchListResponseSerializer,
        400: ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@extend_schema(
    methods=["POST"],
    summary="Create master-data sync launch",
    request=SyncLaunchCreateRequestSerializer,
    responses={
        201: SyncLaunchResponseSerializer,
        400: ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: ProblemDetailsErrorSerializer,
        404: ProblemDetailsErrorSerializer,
        409: ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def sync_launches_collection(request):
    if request.method == "GET":
        tenant_id = _resolve_tenant_id(request)
        if not tenant_id:
            return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

        query_serializer = SyncLaunchListQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            return _validation_problem(detail="Invalid query parameters.", errors=query_serializer.errors)

        limit = int(query_serializer.validated_data.get("limit") or 20)
        offset = int(query_serializer.validated_data.get("offset") or 0)
        launches, total = list_pool_master_data_sync_launch_requests(
            tenant_id=str(tenant_id),
            limit=limit,
            offset=offset,
        )
        return Response(
            {
                "count": total,
                "limit": limit,
                "offset": offset,
                "launches": [
                    serialize_pool_master_data_sync_launch_request(
                        launch_request=launch,
                        include_items=False,
                    )
                    for launch in launches
                ],
            },
            status=http_status.HTTP_200_OK,
        )

    tenant_id, access_error = _require_sync_mutation_tenant_access(request)
    if access_error is not None:
        return access_error

    tenant, tenant_problem = _resolve_tenant_or_problem(tenant_id=str(tenant_id))
    if tenant_problem is not None:
        return tenant_problem

    serializer = SyncLaunchCreateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return _validation_problem(detail="Sync launch payload validation failed.", errors=serializer.errors)

    validated = serializer.validated_data
    try:
        launch = create_pool_master_data_sync_launch_request(
            tenant=tenant,
            mode=str(validated.get("mode") or ""),
            target_mode=str(validated.get("target_mode") or ""),
            cluster_id=str(validated.get("cluster_id")) if validated.get("cluster_id") is not None else None,
            database_ids=validated.get("database_ids") or [],
            entity_scope=validated.get("entity_scope") or [],
            actor_id=str(request.user.id),
            actor_username=str(getattr(request.user, "username", "") or ""),
        )
    except ValueError as exc:
        return _sync_launch_exception_to_response(exc)

    return Response(
        {
            "launch": serialize_pool_master_data_sync_launch_request(
                launch_request=launch,
                include_items=False,
            )
        },
        status=http_status.HTTP_201_CREATED,
    )


@extend_schema(
    summary="Get master-data sync launch detail",
    request=None,
    responses={
        200: SyncLaunchResponseSerializer,
        400: ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_sync_launch(request, id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    try:
        launch = get_pool_master_data_sync_launch_request(
            tenant_id=str(tenant_id),
            launch_request_id=str(id),
        )
    except LookupError as exc:
        return _sync_launch_exception_to_response(exc)

    return Response(
        {
            "launch": serialize_pool_master_data_sync_launch_request(
                launch_request=launch,
                include_items=True,
            )
        },
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    summary="List sync target clusters",
    request=None,
    responses={
        200: RefClustersResponseSerializer,
        400: ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_sync_target_clusters(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    tenant, tenant_problem = _resolve_tenant_or_problem(tenant_id=str(tenant_id))
    if tenant_problem is not None:
        return tenant_problem

    rows = list(Cluster.objects.filter(tenant_id=tenant.id).order_by("name", "id"))
    payload = {
        "clusters": [
            {
                "id": cluster.id,
                "name": cluster.name,
            }
            for cluster in rows
        ],
        "count": len(rows),
        "total": len(rows),
    }
    return Response(payload, status=http_status.HTTP_200_OK)


@extend_schema(
    summary="List sync target databases",
    request=None,
    parameters=[SyncTargetDatabasesQuerySerializer],
    responses={
        200: RefDatabasesResponseSerializer,
        400: ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_sync_target_databases(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    tenant, tenant_problem = _resolve_tenant_or_problem(tenant_id=str(tenant_id))
    if tenant_problem is not None:
        return tenant_problem

    query_serializer = SyncTargetDatabasesQuerySerializer(data=request.query_params)
    if not query_serializer.is_valid():
        return _validation_problem(detail="Invalid query parameters.", errors=query_serializer.errors)

    cluster_id = query_serializer.validated_data.get("cluster_id")
    queryset = Database.objects.filter(tenant_id=tenant.id)
    if cluster_id is not None:
        queryset = queryset.filter(cluster_id=cluster_id)
    rows = list(queryset.order_by("name", "id"))
    payload = {
        "databases": [
            {
                "id": str(database.id),
                "name": database.name,
                "cluster_id": database.cluster_id,
            }
            for database in rows
        ],
        "count": len(rows),
        "total": len(rows),
    }
    return Response(payload, status=http_status.HTTP_200_OK)


@extend_schema(
    summary="List master-data sync status",
    request=None,
    parameters=[MasterDataSyncStatusQuerySerializer],
    responses={
        200: MasterDataSyncStatusListResponseSerializer,
        400: ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_master_data_sync_status(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    query_serializer = MasterDataSyncStatusQuerySerializer(data=request.query_params)
    if not query_serializer.is_valid():
        return _validation_problem(detail="Invalid query parameters.", errors=query_serializer.errors)

    database_id = query_serializer.validated_data.get("database_id")
    entity_type = query_serializer.validated_data.get("entity_type")
    priority = query_serializer.validated_data.get("priority")
    role = query_serializer.validated_data.get("role")
    server_affinity = query_serializer.validated_data.get("server_affinity")
    deadline_state = query_serializer.validated_data.get("deadline_state")
    rows = list_master_data_sync_status_rows(
        tenant_id=str(tenant_id),
        database_id=str(database_id) if database_id is not None else None,
        entity_type=str(entity_type) if entity_type is not None else None,
        priority=str(priority) if priority is not None else None,
        role=str(role) if role is not None else None,
        server_affinity=str(server_affinity) if server_affinity is not None else None,
        deadline_state=str(deadline_state) if deadline_state is not None else None,
    )
    payload = {
        "count": len(rows),
        "statuses": rows,
    }
    return Response(payload, status=http_status.HTTP_200_OK)


@extend_schema(
    summary="List master-data sync conflicts",
    request=None,
    parameters=[MasterDataSyncConflictListQuerySerializer],
    responses={
        200: SyncConflictListResponseSerializer,
        400: ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_master_data_sync_conflicts(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    query_serializer = MasterDataSyncConflictListQuerySerializer(data=request.query_params)
    if not query_serializer.is_valid():
        return _validation_problem(detail="Invalid query parameters.", errors=query_serializer.errors)

    validated = query_serializer.validated_data
    queryset = PoolMasterDataSyncConflict.objects.filter(tenant_id=tenant_id).order_by("-created_at")
    database_id = validated.get("database_id")
    if database_id is not None:
        queryset = queryset.filter(database_id=database_id)
    entity_type = validated.get("entity_type")
    if entity_type is not None:
        queryset = queryset.filter(entity_type=entity_type)
    status = validated.get("status")
    if status is not None:
        queryset = queryset.filter(status=status)
    limit = int(validated.get("limit") or 100)
    rows = list(queryset[:limit])

    return Response(
        {
            "count": queryset.count(),
            "conflicts": [_serialize_sync_conflict(item) for item in rows],
        },
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    summary="Retry sync conflict",
    request=RetryConflictRequestSerializer,
    responses={
        200: SyncConflictActionResponseSerializer,
        400: ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: ProblemDetailsErrorSerializer,
        404: ProblemDetailsErrorSerializer,
        409: ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def retry_master_data_sync_conflict_endpoint(request, id: UUID):
    tenant_id, access_error = _require_sync_mutation_tenant_access(request)
    if access_error is not None:
        return access_error

    serializer = RetryConflictRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return _validation_problem(detail="Retry payload validation failed.", errors=serializer.errors)

    try:
        conflict = retry_master_data_sync_conflict(
            conflict_id=str(id),
            tenant_id=str(tenant_id),
            actor_id=str(request.user.id),
            note=str(serializer.validated_data.get("note") or ""),
            metadata=serializer.validated_data.get("metadata"),
        )
    except PoolMasterDataSyncConflict.DoesNotExist:
        return _problem(
            code="SYNC_CONFLICT_NOT_FOUND",
            title="Sync Conflict Not Found",
            detail=f"Sync conflict '{id}' does not exist.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    except ValueError as exc:
        return _problem(
            code="SYNC_CONFLICT_ACTION_INVALID",
            title="Sync Conflict Action Invalid",
            detail=str(exc),
            status_code=http_status.HTTP_409_CONFLICT,
        )

    return Response({"conflict": _serialize_sync_conflict(conflict)}, status=http_status.HTTP_200_OK)


@extend_schema(
    summary="Reconcile sync conflict",
    request=ReconcileConflictRequestSerializer,
    responses={
        200: SyncConflictActionResponseSerializer,
        400: ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: ProblemDetailsErrorSerializer,
        404: ProblemDetailsErrorSerializer,
        409: ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reconcile_master_data_sync_conflict_endpoint(request, id: UUID):
    tenant_id, access_error = _require_sync_mutation_tenant_access(request)
    if access_error is not None:
        return access_error

    serializer = ReconcileConflictRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return _validation_problem(detail="Reconcile payload validation failed.", errors=serializer.errors)

    try:
        conflict = reconcile_master_data_sync_conflict(
            conflict_id=str(id),
            tenant_id=str(tenant_id),
            actor_id=str(request.user.id),
            reconcile_payload=serializer.validated_data.get("reconcile_payload") or {},
            note=str(serializer.validated_data.get("note") or ""),
        )
    except PoolMasterDataSyncConflict.DoesNotExist:
        return _problem(
            code="SYNC_CONFLICT_NOT_FOUND",
            title="Sync Conflict Not Found",
            detail=f"Sync conflict '{id}' does not exist.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    except ValueError as exc:
        return _problem(
            code="SYNC_CONFLICT_ACTION_INVALID",
            title="Sync Conflict Action Invalid",
            detail=str(exc),
            status_code=http_status.HTTP_409_CONFLICT,
        )

    return Response({"conflict": _serialize_sync_conflict(conflict)}, status=http_status.HTTP_200_OK)


@extend_schema(
    summary="Resolve sync conflict",
    request=ResolveConflictRequestSerializer,
    responses={
        200: SyncConflictActionResponseSerializer,
        400: ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: ProblemDetailsErrorSerializer,
        404: ProblemDetailsErrorSerializer,
        409: ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resolve_master_data_sync_conflict_endpoint(request, id: UUID):
    tenant_id, access_error = _require_sync_mutation_tenant_access(request)
    if access_error is not None:
        return access_error

    serializer = ResolveConflictRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return _validation_problem(detail="Resolve payload validation failed.", errors=serializer.errors)

    try:
        conflict = resolve_master_data_sync_conflict(
            conflict_id=str(id),
            tenant_id=str(tenant_id),
            actor_id=str(request.user.id),
            resolution_code=str(serializer.validated_data.get("resolution_code") or ""),
            note=str(serializer.validated_data.get("note") or ""),
            metadata=serializer.validated_data.get("metadata") or {},
        )
    except PoolMasterDataSyncConflict.DoesNotExist:
        return _problem(
            code="SYNC_CONFLICT_NOT_FOUND",
            title="Sync Conflict Not Found",
            detail=f"Sync conflict '{id}' does not exist.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    except ValueError as exc:
        return _problem(
            code="SYNC_CONFLICT_ACTION_INVALID",
            title="Sync Conflict Action Invalid",
            detail=str(exc),
            status_code=http_status.HTTP_409_CONFLICT,
        )

    return Response({"conflict": _serialize_sync_conflict(conflict)}, status=http_status.HTTP_200_OK)
