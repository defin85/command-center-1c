"""RBAC endpoints: database group permissions."""

from __future__ import annotations

from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.databases.models import Database, DatabaseGroupPermission, PermissionLevel
from apps.operations.services.admin_action_audit import log_admin_action

from .common import (
    _bulk_delete_group_permissions,
    _bulk_upsert_group_permissions,
    _database_ref,
    _dedupe_keep_order,
    _ensure_manage_rbac,
    _group_ref,
    _level_code,
    _parse_pagination,
    _user_ref,
)
from .serializers_core import (
    DatabaseGroupPermissionListResponseSerializer,
    GrantDatabaseGroupPermissionRequestSerializer,
    RevokeDatabaseGroupPermissionRequestSerializer,
)
from .serializers_permissions import (
    BulkDeleteResponseSerializer,
    BulkUpsertResponseSerializer,
    BulkGrantDatabaseGroupPermissionRequestSerializer,
    BulkRevokeDatabaseGroupPermissionRequestSerializer,
    DatabaseGroupPermissionUpsertResponseSerializer,
    RevokePermissionResponseSerializer,
)

@extend_schema(
    tags=["v2"],
    summary="List database group permissions",
    parameters=[
        OpenApiParameter(name="group_id", type=int, required=False),
        OpenApiParameter(name="database_id", type=str, required=False),
        OpenApiParameter(name="cluster_id", type=str, required=False),
        OpenApiParameter(name="level", type=str, required=False),
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: DatabaseGroupPermissionListResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_database_group_permissions(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    pagination = _parse_pagination(request)
    qs = DatabaseGroupPermission.objects.select_related("group", "database", "database__cluster", "granted_by").all()

    group_id = request.query_params.get("group_id")
    if group_id:
        qs = qs.filter(group_id=group_id)

    database_id = request.query_params.get("database_id")
    if database_id:
        qs = qs.filter(database_id=database_id)

    cluster_id = request.query_params.get("cluster_id")
    if cluster_id:
        qs = qs.filter(database__cluster_id=cluster_id)

    level = request.query_params.get("level")
    if level:
        try:
            level_value = getattr(PermissionLevel, str(level).strip().upper())
            qs = qs.filter(level=level_value)
        except Exception:
            pass

    search = request.query_params.get("search")
    if search:
        qs = qs.filter(
            Q(group__name__icontains=search)
            | Q(database__name__icontains=search)
        )

    total = qs.count()
    rows = list(qs.order_by("-granted_at")[pagination.offset: pagination.offset + pagination.limit])

    data = [
        {
            "group": _group_ref(row.group),
            "database": _database_ref(row.database),
            "level": _level_code(row.level),
            "granted_by": _user_ref(row.granted_by),
            "granted_at": row.granted_at,
            "notes": row.notes,
        }
        for row in rows
    ]
    return Response({"permissions": data, "count": len(data), "total": total})


@extend_schema(
    tags=["v2"],
    summary="Grant database group permission",
    request=GrantDatabaseGroupPermissionRequestSerializer,
    responses={200: DatabaseGroupPermissionUpsertResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grant_database_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = GrantDatabaseGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.grant_database_group_permission",
            outcome="error",
            target_type="database",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    database_id = serializer.validated_data["database_id"]
    level = serializer.validated_data["level"]
    notes = serializer.validated_data.get("notes", "")
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "GROUP_NOT_FOUND", "message": "Role not found"}},
            status=404,
        )

    try:
        database = Database.objects.get(id=database_id)
    except Database.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "DATABASE_NOT_FOUND", "message": "Database not found"}},
            status=404,
        )

    old_level = None
    old_notes = None
    with transaction.atomic():
        obj, created = DatabaseGroupPermission.objects.select_for_update().get_or_create(
            group=group,
            database=database,
            defaults={"level": level, "notes": notes, "granted_by": request.user},
        )
        if not created:
            old_level = _level_code(obj.level)
            old_notes = obj.notes or ""
            obj.level = level
            obj.notes = notes
            obj.granted_by = request.user
            obj.save(update_fields=["level", "notes", "granted_by"])

    payload = {
        "created": created,
        "permission": {
            "group": _group_ref(obj.group),
            "database": _database_ref(obj.database),
            "level": _level_code(obj.level),
            "granted_by": _user_ref(obj.granted_by),
            "granted_at": obj.granted_at,
            "notes": obj.notes,
        },
    }
    log_admin_action(
        request,
        action="rbac.grant_database_group_permission",
        outcome="success",
        target_type="database",
        target_id=str(database_id),
        metadata={
            "reason": reason,
            "group_id": group_id,
            "level": _level_code(level),
            "created": created,
            "notes": notes,
            **({"old_level": old_level, "old_notes": old_notes} if not created else {}),
        },
    )
    return Response(payload)


@extend_schema(
    tags=["v2"],
    summary="Revoke database group permission",
    request=RevokeDatabaseGroupPermissionRequestSerializer,
    responses={200: RevokePermissionResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_database_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RevokeDatabaseGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.revoke_database_group_permission",
            outcome="error",
            target_type="database",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    database_id = serializer.validated_data["database_id"]
    reason = str(serializer.validated_data.get("reason") or "").strip()

    old_level = None
    old_notes = None
    with transaction.atomic():
        existing = DatabaseGroupPermission.objects.select_for_update().filter(group_id=group_id, database_id=database_id).first()
        if existing is not None:
            old_level = _level_code(existing.level)
            old_notes = existing.notes or ""
        deleted, _ = DatabaseGroupPermission.objects.filter(group_id=group_id, database_id=database_id).delete()
    log_admin_action(
        request,
        action="rbac.revoke_database_group_permission",
        outcome="success",
        target_type="database",
        target_id=str(database_id),
        metadata={
            "reason": reason,
            "group_id": group_id,
            "deleted": deleted > 0,
            **({"old_level": old_level, "old_notes": old_notes} if deleted > 0 and old_level is not None else {}),
        },
    )
    return Response({"deleted": deleted > 0})


@extend_schema(
    tags=["v2"],
    summary="Bulk grant database group permission",
    request=BulkGrantDatabaseGroupPermissionRequestSerializer,
    responses={200: BulkUpsertResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bulk_grant_database_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = BulkGrantDatabaseGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.bulk_grant_database_group_permission",
            outcome="error",
            target_type="database",
            target_id="bulk",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    database_ids = _dedupe_keep_order([str(v) for v in serializer.validated_data["database_ids"]])
    level = serializer.validated_data["level"]
    notes = serializer.validated_data.get("notes", "")
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "GROUP_NOT_FOUND", "message": "Role not found"}},
            status=404,
        )

    found_ids = set(str(v) for v in Database.objects.filter(id__in=database_ids).values_list("id", flat=True))
    missing = [str(dbid) for dbid in database_ids if str(dbid) not in found_ids]
    if missing:
        return Response(
            {"success": False, "error": {"code": "DATABASE_NOT_FOUND", "message": f"Databases not found: {missing}"}},
            status=404,
        )

    with transaction.atomic():
        result = _bulk_upsert_group_permissions(
            model=DatabaseGroupPermission,
            group=group,
            object_ids=database_ids,
            object_id_field="database_id",
            level=level,
            notes=notes,
            granted_by=request.user,
        )

    log_admin_action(
        request,
        action="rbac.bulk_grant_database_group_permission",
        outcome="success",
        target_type="database",
        target_id="bulk",
        metadata={
            "reason": reason,
            "group_id": group_id,
            "level": _level_code(level),
            "notes": notes,
            **result,
            "database_ids_sample": [str(dbid) for dbid in database_ids[:20]],
        },
    )
    return Response(result)


@extend_schema(
    tags=["v2"],
    summary="Bulk revoke database group permission",
    request=BulkRevokeDatabaseGroupPermissionRequestSerializer,
    responses={200: BulkDeleteResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bulk_revoke_database_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = BulkRevokeDatabaseGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.bulk_revoke_database_group_permission",
            outcome="error",
            target_type="database",
            target_id="bulk",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    database_ids = _dedupe_keep_order([str(v) for v in serializer.validated_data["database_ids"]])
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "GROUP_NOT_FOUND", "message": "Role not found"}},
            status=404,
        )

    found_ids = set(str(v) for v in Database.objects.filter(id__in=database_ids).values_list("id", flat=True))
    missing = [str(dbid) for dbid in database_ids if str(dbid) not in found_ids]
    if missing:
        return Response(
            {"success": False, "error": {"code": "DATABASE_NOT_FOUND", "message": f"Databases not found: {missing}"}},
            status=404,
        )

    with transaction.atomic():
        result = _bulk_delete_group_permissions(
            model=DatabaseGroupPermission,
            group=group,
            object_ids=database_ids,
            object_id_field="database_id",
        )

    log_admin_action(
        request,
        action="rbac.bulk_revoke_database_group_permission",
        outcome="success",
        target_type="database",
        target_id="bulk",
        metadata={
            "reason": reason,
            "group_id": group_id,
            **result,
            "database_ids_sample": [str(dbid) for dbid in database_ids[:20]],
        },
    )
    return Response(result)
