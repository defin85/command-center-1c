"""
RBAC management endpoints (API v2).

These endpoints are intended for SPA-primary administration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from apps.databases.models import (
    Cluster,
    ClusterPermission,
    Database,
    DatabasePermission,
    PermissionLevel,
)
from apps.operations.services.admin_action_audit import log_admin_action


class PermissionLevelCodeField(serializers.Field):
    def to_representation(self, value):
        try:
            return PermissionLevel(int(value)).name
        except Exception:
            return None

    def to_internal_value(self, data):
        if isinstance(data, int):
            return int(data)
        if not isinstance(data, str):
            raise serializers.ValidationError("Invalid permission level")
        key = data.strip().upper()
        try:
            return getattr(PermissionLevel, key)
        except Exception:
            raise serializers.ValidationError("Invalid permission level")


class ErrorDetailSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()


class ErrorResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=False)
    error = ErrorDetailSerializer()


class UserRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()


class ClusterRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class DatabaseRefSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    cluster_id = serializers.UUIDField(allow_null=True)


class ClusterPermissionSerializer(serializers.Serializer):
    user = UserRefSerializer()
    cluster = ClusterRefSerializer()
    level = PermissionLevelCodeField()
    granted_by = UserRefSerializer(allow_null=True)
    granted_at = serializers.DateTimeField()
    notes = serializers.CharField(allow_blank=True, required=False)


class DatabasePermissionSerializer(serializers.Serializer):
    user = UserRefSerializer()
    database = DatabaseRefSerializer()
    level = PermissionLevelCodeField()
    granted_by = UserRefSerializer(allow_null=True)
    granted_at = serializers.DateTimeField()
    notes = serializers.CharField(allow_blank=True, required=False)


class ClusterPermissionListResponseSerializer(serializers.Serializer):
    permissions = ClusterPermissionSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class DatabasePermissionListResponseSerializer(serializers.Serializer):
    permissions = DatabasePermissionSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class UserListResponseSerializer(serializers.Serializer):
    users = UserRefSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class GrantClusterPermissionRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    cluster_id = serializers.UUIDField()
    level = PermissionLevelCodeField()
    notes = serializers.CharField(required=False, allow_blank=True)


class RevokeClusterPermissionRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    cluster_id = serializers.UUIDField()


class GrantDatabasePermissionRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    database_id = serializers.CharField()
    level = PermissionLevelCodeField()
    notes = serializers.CharField(required=False, allow_blank=True)


class RevokeDatabasePermissionRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    database_id = serializers.CharField()


class RevokePermissionResponseSerializer(serializers.Serializer):
    deleted = serializers.BooleanField()


class ClusterPermissionUpsertResponseSerializer(serializers.Serializer):
    created = serializers.BooleanField()
    permission = ClusterPermissionSerializer()


class DatabasePermissionUpsertResponseSerializer(serializers.Serializer):
    created = serializers.BooleanField()
    permission = DatabasePermissionSerializer()


class EffectiveAccessClusterItemSerializer(serializers.Serializer):
    cluster = ClusterRefSerializer()
    level = PermissionLevelCodeField()


class EffectiveAccessDatabaseItemSerializer(serializers.Serializer):
    database = DatabaseRefSerializer()
    level = PermissionLevelCodeField()
    source = serializers.ChoiceField(choices=["direct", "cluster"])


class EffectiveAccessResponseSerializer(serializers.Serializer):
    user = UserRefSerializer()
    clusters = EffectiveAccessClusterItemSerializer(many=True)
    databases = EffectiveAccessDatabaseItemSerializer(many=True)


def _user_ref(user: Optional[User]) -> Optional[dict]:
    if user is None:
        return None
    return {"id": user.id, "username": user.username}


def _cluster_ref(cluster: Cluster) -> dict:
    return {"id": cluster.id, "name": cluster.name}


def _database_ref(database: Database) -> dict:
    return {"id": str(database.id), "name": database.name, "cluster_id": database.cluster_id}

def _level_code(level: Optional[int]) -> Optional[str]:
    if level is None:
        return None
    try:
        return PermissionLevel(int(level)).name
    except Exception:
        return None


@dataclass(frozen=True)
class _Pagination:
    limit: int
    offset: int


def _parse_pagination(request, default_limit: int = 50, max_limit: int = 200) -> _Pagination:
    try:
        limit = int(request.query_params.get("limit", default_limit))
    except Exception:
        limit = default_limit
    try:
        offset = int(request.query_params.get("offset", 0))
    except Exception:
        offset = 0
    limit = max(1, min(limit, max_limit))
    offset = max(0, offset)
    return _Pagination(limit=limit, offset=offset)


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
@permission_classes([IsAdminUser])
def list_cluster_permissions(request):
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
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: ErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def grant_cluster_permission(request):
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

    with transaction.atomic():
        obj, created = ClusterPermission.objects.select_for_update().get_or_create(
            user=user,
            cluster=cluster,
            defaults={"level": level, "notes": notes, "granted_by": request.user},
        )
        if not created:
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
            "user_id": user_id,
            "level": _level_code(level),
            "created": created,
            "notes": notes,
        },
    )
    return Response(payload)


@extend_schema(
    tags=["v2"],
    summary="Revoke cluster permission",
    request=RevokeClusterPermissionRequestSerializer,
    responses={
        200: RevokePermissionResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def revoke_cluster_permission(request):
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

    deleted, _ = ClusterPermission.objects.filter(user_id=user_id, cluster_id=cluster_id).delete()

    log_admin_action(
        request,
        action="rbac.revoke_cluster_permission",
        outcome="success",
        target_type="cluster",
        target_id=str(cluster_id),
        metadata={"user_id": user_id, "deleted": deleted > 0},
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
@permission_classes([IsAdminUser])
def list_database_permissions(request):
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
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: ErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def grant_database_permission(request):
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

    with transaction.atomic():
        obj, created = DatabasePermission.objects.select_for_update().get_or_create(
            user=user,
            database=database,
            defaults={"level": level, "notes": notes, "granted_by": request.user},
        )
        if not created:
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
            "user_id": user_id,
            "level": _level_code(level),
            "created": created,
            "notes": notes,
        },
    )
    return Response(payload)


@extend_schema(
    tags=["v2"],
    summary="Revoke database permission",
    request=RevokeDatabasePermissionRequestSerializer,
    responses={
        200: RevokePermissionResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def revoke_database_permission(request):
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

    deleted, _ = DatabasePermission.objects.filter(user_id=user_id, database_id=database_id).delete()

    log_admin_action(
        request,
        action="rbac.revoke_database_permission",
        outcome="success",
        target_type="database",
        target_id=str(database_id),
        metadata={"user_id": user_id, "deleted": deleted > 0},
    )
    return Response({"deleted": deleted > 0})


@extend_schema(
    tags=["v2"],
    summary="List users",
    description="List users for RBAC selection (staff only).",
    parameters=[
        OpenApiParameter(name="search", type=str, required=False, description="Search by username or name"),
        OpenApiParameter(name="limit", type=int, required=False, description="Maximum results (default: 100, max: 1000)"),
        OpenApiParameter(name="offset", type=int, required=False, description="Pagination offset (default: 0)"),
    ],
    responses={
        200: UserListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
def list_users(request):
    search = (request.query_params.get("search") or "").strip()
    try:
        limit = int(request.query_params.get("limit", 100))
        limit = max(1, min(limit, 1000))
    except (TypeError, ValueError):
        limit = 100
    try:
        offset = int(request.query_params.get("offset", 0))
        offset = max(0, offset)
    except (TypeError, ValueError):
        offset = 0

    qs = User.objects.all()
    if search:
        qs = qs.filter(
            Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
        )

    total = qs.count()
    qs = qs.order_by("username")[offset:offset + limit]
    data = UserRefSerializer(qs, many=True).data

    return Response({
        "users": data,
        "count": len(data),
        "total": total,
    })


@extend_schema(
    tags=["v2"],
    summary="Get effective access",
    parameters=[
        OpenApiParameter(
            name="user_id",
            type=int,
            required=False,
            description="Optional (default: current user). Staff-only.",
        ),
        OpenApiParameter(name="include_databases", type=bool, required=False, default=True),
        OpenApiParameter(name="include_clusters", type=bool, required=False, default=True),
    ],
    responses={
        200: EffectiveAccessResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_effective_access(request):
    requested_user_id = request.query_params.get("user_id")
    if requested_user_id and not (request.user.is_staff or request.user.is_superuser):
        return Response({"detail": "Forbidden"}, status=403)

    target_user = request.user
    if requested_user_id:
        try:
            target_user = User.objects.get(id=requested_user_id)
        except User.DoesNotExist:
            return Response(
                {"success": False, "error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
                status=404,
            )

    include_clusters = str(request.query_params.get("include_clusters", "true")).lower() != "false"
    include_databases = str(request.query_params.get("include_databases", "true")).lower() != "false"

    clusters_out = []
    cluster_level_map = {}
    if include_clusters or include_databases:
        cluster_perms = ClusterPermission.objects.select_related("cluster").filter(user=target_user)
        for perm in cluster_perms:
            cluster_level_map[str(perm.cluster_id)] = perm.level
            if include_clusters:
                clusters_out.append({"cluster": _cluster_ref(perm.cluster), "level": _level_code(perm.level)})

    databases_out = []
    if include_databases:
        direct_db_perms = DatabasePermission.objects.select_related("database", "database__cluster").filter(user=target_user)
        direct_db_level_map = {str(p.database_id): p.level for p in direct_db_perms}

        # Add all databases from clusters where user has cluster permission.
        cluster_db_rows = []
        if cluster_level_map:
            cluster_db_rows = list(
                Database.objects.select_related("cluster")
                .filter(cluster_id__in=list(cluster_level_map.keys()))
            )

        # Build final list: union(direct, cluster-derived).
        seen_db_ids = set()

        for perm in direct_db_perms:
            db = perm.database
            seen_db_ids.add(str(db.id))
            cluster_level = cluster_level_map.get(str(db.cluster_id)) if db.cluster_id else None
            effective_level = perm.level
            source = "direct"
            if cluster_level is not None and cluster_level > effective_level:
                effective_level = cluster_level
                source = "cluster"
            databases_out.append(
                {"database": _database_ref(db), "level": _level_code(effective_level), "source": source}
            )

        for db in cluster_db_rows:
            db_id = str(db.id)
            if db_id in seen_db_ids:
                continue
            cluster_level = cluster_level_map.get(str(db.cluster_id))
            if cluster_level is None:
                continue
            direct_level = direct_db_level_map.get(db_id)
            effective_level = cluster_level
            source = "cluster"
            if direct_level is not None and direct_level >= cluster_level:
                effective_level = direct_level
                source = "direct"
            databases_out.append(
                {"database": _database_ref(db), "level": _level_code(effective_level), "source": source}
            )

    return Response(
        {
            "user": _user_ref(target_user),
            "clusters": clusters_out,
            "databases": databases_out,
        }
    )
