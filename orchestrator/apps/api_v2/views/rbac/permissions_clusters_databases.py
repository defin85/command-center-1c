"""RBAC endpoints: direct user permissions for clusters/databases."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.databases.models import Cluster, ClusterPermission, Database, DatabasePermission, PermissionLevel
from apps.operations.services.admin_action_audit import log_admin_action

from .common import _cluster_ref, _database_ref, _ensure_manage_rbac, _level_code, _parse_pagination, _user_ref
from .serializers_core import RbacErrorResponseSerializer
from .serializers_permissions import (
    ClusterPermissionListResponseSerializer,
    ClusterPermissionUpsertResponseSerializer,
    DatabasePermissionListResponseSerializer,
    DatabasePermissionUpsertResponseSerializer,
    GrantClusterPermissionRequestSerializer,
    GrantDatabasePermissionRequestSerializer,
    RevokePermissionResponseSerializer,
    RevokeClusterPermissionRequestSerializer,
    RevokeDatabasePermissionRequestSerializer,
)

@extend_schema(
    tags=["v2"],
    summary="List cluster permissions",
    parameters=[
        OpenApiParameter(name="user_id", type=int, required=False),
        OpenApiParameter(name="cluster_id", type=str, required=False),
        OpenApiParameter(name="level", type=str, required=False),
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={
        200: ClusterPermissionListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_cluster_permissions(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    pagination = _parse_pagination(request)
    qs = ClusterPermission.objects.select_related("user", "cluster", "granted_by").all()

    user_id = request.query_params.get("user_id")
    if user_id:
        qs = qs.filter(user_id=user_id)

    cluster_id = request.query_params.get("cluster_id")
    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)

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
            Q(user__username__icontains=search)
            | Q(cluster__name__icontains=search)
        )

    total = qs.count()
    rows = list(qs.order_by("-granted_at")[pagination.offset: pagination.offset + pagination.limit])

    data = [
        {
            "user": _user_ref(row.user),
            "cluster": _cluster_ref(row.cluster),
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
    summary="Grant cluster permission",
    request=GrantClusterPermissionRequestSerializer,
    responses={
        200: ClusterPermissionUpsertResponseSerializer,
        400: RbacErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: RbacErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grant_cluster_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = GrantClusterPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.grant_cluster_permission",
            outcome="error",
            target_type="cluster",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    user_id = serializer.validated_data["user_id"]
    cluster_id = serializer.validated_data["cluster_id"]
    level = serializer.validated_data["level"]
    notes = serializer.validated_data.get("notes", "")
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        log_admin_action(
            request,
            action="rbac.grant_cluster_permission",
            outcome="error",
            target_type="user",
            target_id=str(user_id),
            metadata={"cluster_id": str(cluster_id)},
            error_message="USER_NOT_FOUND",
        )
        return Response(
            {"success": False, "error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
            status=404,
        )

    try:
        cluster = Cluster.objects.get(id=cluster_id)
    except Cluster.DoesNotExist:
        log_admin_action(
            request,
            action="rbac.grant_cluster_permission",
            outcome="error",
            target_type="cluster",
            target_id=str(cluster_id),
            metadata={"user_id": user_id},
            error_message="CLUSTER_NOT_FOUND",
        )
        return Response(
            {"success": False, "error": {"code": "CLUSTER_NOT_FOUND", "message": "Cluster not found"}},
            status=404,
        )

    old_level = None
    old_notes = None
    with transaction.atomic():
        obj, created = ClusterPermission.objects.select_for_update().get_or_create(
            user=user,
            cluster=cluster,
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
            "user": _user_ref(obj.user),
            "cluster": _cluster_ref(obj.cluster),
            "level": _level_code(obj.level),
            "granted_by": _user_ref(obj.granted_by),
            "granted_at": obj.granted_at,
            "notes": obj.notes,
        },
    }

    log_admin_action(
        request,
        action="rbac.grant_cluster_permission",
        outcome="success",
        target_type="cluster",
        target_id=str(cluster_id),
        metadata={
            "reason": reason,
            "user_id": user_id,
            "level": _level_code(level),
            "created": created,
            "notes": notes,
            **({"old_level": old_level, "old_notes": old_notes} if not created else {}),
        },
    )
    return Response(payload)


@extend_schema(
    tags=["v2"],
    summary="Revoke cluster permission",
    request=RevokeClusterPermissionRequestSerializer,
    responses={
        200: RevokePermissionResponseSerializer,
        400: RbacErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_cluster_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RevokeClusterPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.revoke_cluster_permission",
            outcome="error",
            target_type="cluster",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    user_id = serializer.validated_data["user_id"]
    cluster_id = serializer.validated_data["cluster_id"]
    reason = str(serializer.validated_data.get("reason") or "").strip()

    old_level = None
    old_notes = None
    with transaction.atomic():
        existing = ClusterPermission.objects.select_for_update().filter(user_id=user_id, cluster_id=cluster_id).first()
        if existing is not None:
            old_level = _level_code(existing.level)
            old_notes = existing.notes or ""
        deleted, _ = ClusterPermission.objects.filter(user_id=user_id, cluster_id=cluster_id).delete()

    log_admin_action(
        request,
        action="rbac.revoke_cluster_permission",
        outcome="success",
        target_type="cluster",
        target_id=str(cluster_id),
        metadata={
            "reason": reason,
            "user_id": user_id,
            "deleted": deleted > 0,
            **({"old_level": old_level, "old_notes": old_notes} if deleted > 0 and old_level is not None else {}),
        },
    )
    return Response({"deleted": deleted > 0})


@extend_schema(
    tags=["v2"],
    summary="List database permissions",
    parameters=[
        OpenApiParameter(name="user_id", type=int, required=False),
        OpenApiParameter(name="database_id", type=str, required=False),
        OpenApiParameter(name="cluster_id", type=str, required=False),
        OpenApiParameter(name="level", type=str, required=False),
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={
        200: DatabasePermissionListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_database_permissions(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    pagination = _parse_pagination(request)
    qs = DatabasePermission.objects.select_related("user", "database", "database__cluster", "granted_by").all()

    user_id = request.query_params.get("user_id")
    if user_id:
        qs = qs.filter(user_id=user_id)

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
            Q(user__username__icontains=search)
            | Q(database__name__icontains=search)
        )

    total = qs.count()
    rows = list(qs.order_by("-granted_at")[pagination.offset: pagination.offset + pagination.limit])

    data = [
        {
            "user": _user_ref(row.user),
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
    summary="Grant database permission",
    request=GrantDatabasePermissionRequestSerializer,
    responses={
        200: DatabasePermissionUpsertResponseSerializer,
        400: RbacErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: RbacErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grant_database_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = GrantDatabasePermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.grant_database_permission",
            outcome="error",
            target_type="database",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    user_id = serializer.validated_data["user_id"]
    database_id = serializer.validated_data["database_id"]
    level = serializer.validated_data["level"]
    notes = serializer.validated_data.get("notes", "")
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        log_admin_action(
            request,
            action="rbac.grant_database_permission",
            outcome="error",
            target_type="user",
            target_id=str(user_id),
            metadata={"database_id": str(database_id)},
            error_message="USER_NOT_FOUND",
        )
        return Response(
            {"success": False, "error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
            status=404,
        )

    try:
        database = Database.objects.select_related("cluster").get(id=database_id)
    except Database.DoesNotExist:
        log_admin_action(
            request,
            action="rbac.grant_database_permission",
            outcome="error",
            target_type="database",
            target_id=str(database_id),
            metadata={"user_id": user_id},
            error_message="DATABASE_NOT_FOUND",
        )
        return Response(
            {"success": False, "error": {"code": "DATABASE_NOT_FOUND", "message": "Database not found"}},
            status=404,
        )

    old_level = None
    old_notes = None
    with transaction.atomic():
        obj, created = DatabasePermission.objects.select_for_update().get_or_create(
            user=user,
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
            "user": _user_ref(obj.user),
            "database": _database_ref(obj.database),
            "level": _level_code(obj.level),
            "granted_by": _user_ref(obj.granted_by),
            "granted_at": obj.granted_at,
            "notes": obj.notes,
        },
    }

    log_admin_action(
        request,
        action="rbac.grant_database_permission",
        outcome="success",
        target_type="database",
        target_id=str(database_id),
        metadata={
            "reason": reason,
            "user_id": user_id,
            "level": _level_code(level),
            "created": created,
            "notes": notes,
            **({"old_level": old_level, "old_notes": old_notes} if not created else {}),
        },
    )
    return Response(payload)


@extend_schema(
    tags=["v2"],
    summary="Revoke database permission",
    request=RevokeDatabasePermissionRequestSerializer,
    responses={
        200: RevokePermissionResponseSerializer,
        400: RbacErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_database_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RevokeDatabasePermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.revoke_database_permission",
            outcome="error",
            target_type="database",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    user_id = serializer.validated_data["user_id"]
    database_id = serializer.validated_data["database_id"]
    reason = str(serializer.validated_data.get("reason") or "").strip()

    old_level = None
    old_notes = None
    with transaction.atomic():
        existing = DatabasePermission.objects.select_for_update().filter(user_id=user_id, database_id=database_id).first()
        if existing is not None:
            old_level = _level_code(existing.level)
            old_notes = existing.notes or ""
        deleted, _ = DatabasePermission.objects.filter(user_id=user_id, database_id=database_id).delete()

    log_admin_action(
        request,
        action="rbac.revoke_database_permission",
        outcome="success",
        target_type="database",
        target_id=str(database_id),
        metadata={
            "reason": reason,
            "user_id": user_id,
            "deleted": deleted > 0,
            **({"old_level": old_level, "old_notes": old_notes} if deleted > 0 and old_level is not None else {}),
        },
    )
    return Response({"deleted": deleted > 0})

