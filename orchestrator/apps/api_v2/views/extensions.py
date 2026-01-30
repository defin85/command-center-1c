"""
Extensions overview endpoints for API v2.

Provides aggregated view across databases using stored extensions snapshots.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from django.db.models import QuerySet
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.core import permission_codes as perms
from apps.databases.extensions_snapshot import normalize_extensions_snapshot
from apps.databases.models import Database, DatabaseExtensionsSnapshot, PermissionLevel
from apps.databases.services import PermissionService
from apps.mappings.extensions_inventory import build_canonical_extensions_inventory
from apps.mappings.models import TenantMappingSpec


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


def _accessible_databases_qs(request, *, cluster_id: str | None = None) -> QuerySet:
    qs = Database.objects.select_related("cluster").all()
    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)
    if not _is_staff(request.user):
        qs = PermissionService.filter_accessible_databases(request.user, qs, PermissionLevel.VIEW)
    return qs


@dataclass(frozen=True)
class _SnapshotState:
    ok: bool
    updated_at: Any
    extensions: list[dict[str, Any]]


def _load_snapshot_state(db: Database) -> _SnapshotState:
    try:
        snapshot_obj: DatabaseExtensionsSnapshot = db.extensions_snapshot
    except DatabaseExtensionsSnapshot.DoesNotExist:
        return _SnapshotState(ok=False, updated_at=None, extensions=[])

    raw_snapshot = snapshot_obj.snapshot or {}
    # Legacy snapshots stored raw worker payload (stdout/stderr/...) without reserved keys.
    # Treat them as "unknown" for overview/drill-down, to avoid misclassifying them as "missing".
    if isinstance(raw_snapshot, dict) and not any(k in raw_snapshot for k in ("extensions", "raw", "parse_error")):
        return _SnapshotState(ok=False, updated_at=snapshot_obj.updated_at, extensions=[])

    payload = normalize_extensions_snapshot(raw_snapshot)
    if payload.get("parse_error"):
        return _SnapshotState(ok=False, updated_at=snapshot_obj.updated_at, extensions=[])

    spec = TenantMappingSpec.objects.filter(
        tenant_id=db.tenant_id,
        entity_kind=TenantMappingSpec.ENTITY_EXTENSIONS_INVENTORY,
        status=TenantMappingSpec.STATUS_PUBLISHED,
    ).values_list("spec", flat=True).first()
    spec_dict = spec if isinstance(spec, dict) else {}
    canonical = build_canonical_extensions_inventory(payload, spec_dict)

    extensions = canonical.get("extensions")
    if not isinstance(extensions, list):
        return _SnapshotState(ok=False, updated_at=snapshot_obj.updated_at, extensions=[])

    out: list[dict[str, Any]] = []
    for item in extensions:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        version = item.get("version")
        if version is not None:
            version = str(version).strip() or None
        is_active = item.get("is_active")
        if is_active is not None and not isinstance(is_active, bool):
            is_active = None
        normalized: dict[str, Any] = {"name": name}
        if version is not None:
            normalized["version"] = version
        if is_active is not None:
            normalized["is_active"] = is_active
        out.append(normalized)

    return _SnapshotState(ok=True, updated_at=snapshot_obj.updated_at, extensions=out)


def _compute_extension_status(item: dict[str, Any]) -> str:
    is_active = item.get("is_active")
    if is_active is True:
        return "active"
    if is_active is False:
        return "inactive"
    return "unknown"


class ExtensionsOverviewRowSerializer(serializers.Serializer):
    name = serializers.CharField()
    installed_count = serializers.IntegerField()
    active_count = serializers.IntegerField()
    inactive_count = serializers.IntegerField()
    missing_count = serializers.IntegerField()
    unknown_count = serializers.IntegerField()
    versions = serializers.ListField(child=serializers.DictField())
    latest_snapshot_at = serializers.DateTimeField(allow_null=True, required=False)


class ExtensionsOverviewResponseSerializer(serializers.Serializer):
    extensions = ExtensionsOverviewRowSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()
    total_databases = serializers.IntegerField()


@extend_schema(
    tags=["v2"],
    summary="Extensions overview (aggregated)",
    description="Aggregated extensions overview across accessible databases (snapshot-driven).",
    parameters=[
        OpenApiParameter(name="search", type=str, required=False, description="Search by extension name (substring)"),
        OpenApiParameter(name="status", type=str, required=False, description="Filter by status: active|inactive|missing|unknown"),
        OpenApiParameter(name="version", type=str, required=False, description="Filter rows where this version exists"),
        OpenApiParameter(name="cluster_id", type=str, required=False, description="Restrict to a cluster"),
        OpenApiParameter(name="limit", type=int, required=False, description="Max items (default 100, max 1000)"),
        OpenApiParameter(name="offset", type=int, required=False, description="Offset (default 0)"),
    ],
    responses={
        200: ExtensionsOverviewResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_extensions_overview(request):
    if not request.user.has_perm(perms.PERM_DATABASES_VIEW_DATABASE):
        return _permission_denied("You do not have permission to view databases.")

    search = str(request.query_params.get("search") or "").strip().lower()
    status_filter = str(request.query_params.get("status") or "").strip().lower()
    version_filter = str(request.query_params.get("version") or "").strip()
    cluster_id = str(request.query_params.get("cluster_id") or "").strip() or None

    limit = _parse_int(request.query_params.get("limit"), default=100, min_value=1, max_value=1000)
    offset = _parse_int(request.query_params.get("offset"), default=0, min_value=0, max_value=1_000_000)

    databases = list(_accessible_databases_qs(request, cluster_id=cluster_id))
    total_databases = len(databases)

    unknown_snapshot_count = 0
    ok_snapshots: dict[str, _SnapshotState] = {}
    for db in databases:
        state = _load_snapshot_state(db)
        if not state.ok:
            unknown_snapshot_count += 1
            continue
        ok_snapshots[str(db.id)] = state

    # Aggregate over extension names seen in parsed snapshots.
    counters: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "active": 0,
        "inactive": 0,
        "unknown_active": 0,
        "versions": Counter(),
        "latest_snapshot_at": None,
    })

    for state in ok_snapshots.values():
        for item in state.extensions:
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            bucket = counters[name]

            st = _compute_extension_status(item)
            if st == "active":
                bucket["active"] += 1
            elif st == "inactive":
                bucket["inactive"] += 1
            else:
                bucket["unknown_active"] += 1

            ver = item.get("version")
            bucket["versions"][ver] += 1

            if state.updated_at is not None:
                prev = bucket["latest_snapshot_at"]
                if prev is None or state.updated_at > prev:
                    bucket["latest_snapshot_at"] = state.updated_at

    rows: list[dict[str, Any]] = []
    for name, bucket in counters.items():
        active = int(bucket["active"])
        inactive = int(bucket["inactive"])
        unknown_active = int(bucket["unknown_active"])
        installed = active + inactive + unknown_active
        missing = max(0, total_databases - installed - unknown_snapshot_count)
        unknown = unknown_snapshot_count + unknown_active

        versions_counter: Counter = bucket["versions"]
        versions = [
            {"version": ver, "count": int(cnt)}
            for ver, cnt in versions_counter.items()
            if cnt and (ver is None or isinstance(ver, str))
        ]
        versions.sort(key=lambda item: (item["version"] is None, str(item["version"])))

        row = {
            "name": name,
            "installed_count": installed,
            "active_count": active,
            "inactive_count": inactive,
            "missing_count": missing,
            "unknown_count": unknown,
            "versions": versions,
            "latest_snapshot_at": bucket["latest_snapshot_at"],
        }
        rows.append(row)

    # Apply filters.
    if search:
        rows = [r for r in rows if search in str(r.get("name") or "").lower()]

    if version_filter:
        rows = [
            r
            for r in rows
            if any(str(v.get("version") or "") == version_filter for v in (r.get("versions") or []))
        ]

    if status_filter in {"active", "inactive", "missing", "unknown"}:
        key = f"{status_filter}_count"
        rows = [r for r in rows if int(r.get(key) or 0) > 0]

    rows.sort(key=lambda r: str(r.get("name") or "").lower())

    total = len(rows)
    page = rows[offset:offset + limit]

    return Response({"extensions": page, "count": len(page), "total": total, "total_databases": total_databases})


class ExtensionsOverviewDatabaseRowSerializer(serializers.Serializer):
    database_id = serializers.UUIDField()
    database_name = serializers.CharField()
    cluster_id = serializers.UUIDField(allow_null=True, required=False)
    cluster_name = serializers.CharField(allow_blank=True, required=False)
    status = serializers.CharField()
    version = serializers.CharField(allow_null=True, required=False)
    snapshot_updated_at = serializers.DateTimeField(allow_null=True, required=False)


class ExtensionsOverviewDatabasesResponseSerializer(serializers.Serializer):
    databases = ExtensionsOverviewDatabaseRowSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


@extend_schema(
    tags=["v2"],
    summary="Extensions overview drill-down (databases)",
    description="List databases for a given extension name/version/status (snapshot-driven).",
    parameters=[
        OpenApiParameter(name="name", type=str, required=True, description="Extension name (exact match)"),
        OpenApiParameter(name="version", type=str, required=False, description="Filter by exact version"),
        OpenApiParameter(name="status", type=str, required=False, description="Filter by status: active|inactive|missing|unknown"),
        OpenApiParameter(name="cluster_id", type=str, required=False, description="Restrict to a cluster"),
        OpenApiParameter(name="limit", type=int, required=False, description="Max items (default 100, max 1000)"),
        OpenApiParameter(name="offset", type=int, required=False, description="Offset (default 0)"),
    ],
    responses={
        200: ExtensionsOverviewDatabasesResponseSerializer,
        400: OpenApiResponse(description="Bad request"),
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_extensions_overview_databases(request):
    if not request.user.has_perm(perms.PERM_DATABASES_VIEW_DATABASE):
        return _permission_denied("You do not have permission to view databases.")

    name = str(request.query_params.get("name") or "").strip()
    if not name:
        return Response(
            {"success": False, "error": {"code": "MISSING_PARAMETER", "message": "name is required"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    version_filter = str(request.query_params.get("version") or "").strip() or None
    status_filter = str(request.query_params.get("status") or "").strip().lower() or None
    cluster_id = str(request.query_params.get("cluster_id") or "").strip() or None

    limit = _parse_int(request.query_params.get("limit"), default=100, min_value=1, max_value=1000)
    offset = _parse_int(request.query_params.get("offset"), default=0, min_value=0, max_value=1_000_000)

    databases = list(_accessible_databases_qs(request, cluster_id=cluster_id))

    rows: list[dict[str, Any]] = []
    for db in databases:
        state = _load_snapshot_state(db)
        if not state.ok:
            status = "unknown"
            found_version = None
        else:
            found = None
            for item in state.extensions:
                if str(item.get("name") or "").strip() != name:
                    continue
                if version_filter is not None and str(item.get("version") or "").strip() != version_filter:
                    continue
                found = item
                break

            if found is None:
                status = "missing"
                found_version = None
            else:
                status = _compute_extension_status(found)
                found_version = found.get("version")

        if status_filter in {"active", "inactive", "missing", "unknown"} and status != status_filter:
            continue

        rows.append({
            "database_id": str(db.id),
            "database_name": db.name,
            "cluster_id": str(db.cluster_id) if db.cluster_id else None,
            "cluster_name": (db.cluster.name if db.cluster else ""),
            "status": status,
            "version": found_version,
            "snapshot_updated_at": state.updated_at,
        })

    rows.sort(key=lambda r: str(r.get("database_name") or "").lower())
    total = len(rows)
    page = rows[offset:offset + limit]

    return Response({"databases": page, "count": len(page), "total": total})
