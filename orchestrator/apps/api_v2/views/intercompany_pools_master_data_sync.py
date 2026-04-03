from __future__ import annotations

from typing import Any
from uuid import UUID

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.api_v2.serializers.common import ProblemDetailsErrorSerializer
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
)
from apps.tenancy.models import TenantMember

from .intercompany_pools import _problem, _resolve_tenant_id

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


def _require_conflict_action_tenant_access(request) -> tuple[str | None, Response | None]:
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
    tenant_id, access_error = _require_conflict_action_tenant_access(request)
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
    tenant_id, access_error = _require_conflict_action_tenant_access(request)
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
    tenant_id, access_error = _require_conflict_action_tenant_access(request)
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
