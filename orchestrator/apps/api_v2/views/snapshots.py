"""
Command result snapshots endpoints for API v2.
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core import permission_codes as perms
from apps.databases.models import Database, PermissionLevel
from apps.databases.services import PermissionService
from apps.operations.models import CommandResultSnapshot
from apps.tenancy.permissions import TenantContextPermission


def _permission_denied(message: str):
    return Response(
        {"success": False, "error": {"code": "PERMISSION_DENIED", "message": message}},
        status=http_status.HTTP_403_FORBIDDEN,
    )


def _parse_int(value: Any, *, default: int, min_value: int, max_value: int) -> int:
    try:
        out = int(value)
    except (ValueError, TypeError):
        return default
    return max(min_value, min(max_value, out))


def _is_staff(user) -> bool:
    return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))


def _accessible_databases_qs(request):
    qs = Database.objects.all()
    if not _is_staff(request.user):
        qs = PermissionService.filter_accessible_databases(request.user, qs, PermissionLevel.VIEW)
    return qs


class SnapshotListItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    captured_at = serializers.DateTimeField()
    command_id = serializers.CharField()
    driver = serializers.CharField()
    database_id = serializers.CharField(allow_null=True)
    canonical_hash = serializers.CharField()


class SnapshotListResponseSerializer(serializers.Serializer):
    snapshots = SnapshotListItemSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


@extend_schema(
    tags=["v2"],
    summary="List command result snapshots",
    description="List snapshots for current tenant (RBAC-scoped to accessible databases).",
    parameters=[
        OpenApiParameter(name="command_id", type=str, required=False),
        OpenApiParameter(name="database_id", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False, description="Max items (default 50, max 500)"),
        OpenApiParameter(name="offset", type=int, required=False, description="Offset (default 0)"),
    ],
    responses={
        200: SnapshotListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, TenantContextPermission])
def list_snapshots(request):
    if not request.user.has_perm(perms.PERM_DATABASES_VIEW_DATABASE):
        return _permission_denied("You do not have permission to view databases.")

    tenant_id = str(request.tenant_id)

    command_id = str(request.query_params.get("command_id") or "").strip() or None
    database_id = str(request.query_params.get("database_id") or "").strip() or None
    limit = _parse_int(request.query_params.get("limit"), default=50, min_value=1, max_value=500)
    offset = _parse_int(request.query_params.get("offset"), default=0, min_value=0, max_value=1_000_000)

    snapshots = CommandResultSnapshot.objects.filter(tenant_id=tenant_id)
    if command_id:
        snapshots = snapshots.filter(command_id=command_id)
    if database_id:
        snapshots = snapshots.filter(database_id=database_id)
    else:
        snapshots = snapshots.filter(database__in=_accessible_databases_qs(request))

    total = snapshots.count()
    rows = list(
        snapshots.order_by("-captured_at")[offset:offset + limit].values(
            "id",
            "captured_at",
            "command_id",
            "driver",
            "database_id",
            "canonical_hash",
        )
    )
    return Response({"snapshots": rows, "count": len(rows), "total": total})


class SnapshotGetResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    captured_at = serializers.DateTimeField()
    command_id = serializers.CharField()
    driver = serializers.CharField()
    database_id = serializers.CharField(allow_null=True)
    canonical_hash = serializers.CharField()
    raw_payload = serializers.JSONField()
    normalized_payload = serializers.JSONField()
    canonical_payload = serializers.JSONField()


@extend_schema(
    tags=["v2"],
    summary="Get snapshot details",
    parameters=[OpenApiParameter(name="snapshot_id", type=int, required=True)],
    responses={
        200: SnapshotGetResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: OpenApiResponse(description="Not found"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, TenantContextPermission])
def get_snapshot(request):
    if not request.user.has_perm(perms.PERM_DATABASES_VIEW_DATABASE):
        return _permission_denied("You do not have permission to view databases.")

    tenant_id = str(request.tenant_id)

    snapshot_id_raw = request.query_params.get("snapshot_id")
    try:
        snapshot_id = int(snapshot_id_raw)
    except (TypeError, ValueError):
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "snapshot_id must be int"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    qs = CommandResultSnapshot.objects.filter(tenant_id=tenant_id)
    snap = qs.filter(id=snapshot_id).select_related("database").first()
    if snap is None:
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Snapshot not found"}},
            status=http_status.HTTP_404_NOT_FOUND,
        )

    if snap.database_id:
        allowed = snap.database_id in set(_accessible_databases_qs(request).values_list("id", flat=True))
        if not allowed and not _is_staff(request.user):
            return _permission_denied("You do not have permission to view this database.")

    return Response(
        {
            "id": snap.id,
            "captured_at": snap.captured_at,
            "command_id": snap.command_id,
            "driver": snap.driver,
            "database_id": snap.database_id,
            "canonical_hash": snap.canonical_hash,
            "raw_payload": snap.raw_payload,
            "normalized_payload": snap.normalized_payload,
            "canonical_payload": snap.canonical_payload,
        }
    )
