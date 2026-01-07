"""
RBAC management endpoints (API v2).

These endpoints are intended for SPA-primary administration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from django.contrib.auth.models import Group, Permission, User
from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, OpenApiTypes, extend_schema, extend_schema_field
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core import permission_codes as perms
from apps.databases.models import (
    Cluster,
    ClusterGroupPermission,
    ClusterPermission,
    Database,
    DatabaseGroupPermission,
    DatabasePermission,
    PermissionLevel,
)
from apps.templates.models import (
    OperationTemplate,
    OperationTemplateGroupPermission,
    OperationTemplatePermission,
    WorkflowTemplateGroupPermission,
    WorkflowTemplatePermission,
)
from apps.templates.workflow.models import WorkflowTemplate
from apps.artifacts.models import Artifact, ArtifactGroupPermission, ArtifactPermission
from apps.operations.models import AdminActionAuditLog
from apps.operations.services.admin_action_audit import log_admin_action


def _ensure_manage_rbac(request):
    if request.user.has_perm(perms.PERM_DATABASES_MANAGE_RBAC):
        return None
    return Response(
        {"success": False, "error": {"code": "PERMISSION_DENIED", "message": "Forbidden"}},
        status=403,
    )


@extend_schema_field(OpenApiTypes.STR)
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


class RbacErrorDetailSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()


class RbacErrorResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=False)
    error = RbacErrorDetailSerializer()


class RbacUserRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()


class ClusterRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class DatabaseRefSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    cluster_id = serializers.UUIDField(allow_null=True)


class RbacGroupRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class RoleSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    users_count = serializers.IntegerField()
    permissions_count = serializers.IntegerField()
    permission_codes = serializers.ListField(child=serializers.CharField())


class RoleListResponseSerializer(serializers.Serializer):
    roles = RoleSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class RoleCreateRequestSerializer(serializers.Serializer):
    name = serializers.CharField()
    reason = serializers.CharField()


class RoleUpdateRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    name = serializers.CharField()
    reason = serializers.CharField()


class RoleDeleteRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    reason = serializers.CharField()


class CapabilitySerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField(allow_blank=True)
    app_label = serializers.CharField()
    codename = serializers.CharField()
    exists = serializers.BooleanField()


class CapabilityListResponseSerializer(serializers.Serializer):
    capabilities = CapabilitySerializer(many=True)
    count = serializers.IntegerField()


class RoleCapabilitiesUpdateRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    permission_codes = serializers.ListField(child=serializers.CharField())
    mode = serializers.ChoiceField(choices=["replace", "add", "remove"], required=False, default="replace")
    reason = serializers.CharField()


class RoleCapabilitiesUpdateResponseSerializer(serializers.Serializer):
    group = RbacGroupRefSerializer()
    permission_codes = serializers.ListField(child=serializers.CharField())


class UserRolesUpdateRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    group_ids = serializers.ListField(child=serializers.IntegerField())
    mode = serializers.ChoiceField(choices=["replace", "add", "remove"], required=False, default="replace")
    reason = serializers.CharField()


class UserRolesGetResponseSerializer(serializers.Serializer):
    user = RbacUserRefSerializer()
    roles = RbacGroupRefSerializer(many=True)


class ClusterGroupPermissionSerializer(serializers.Serializer):
    group = RbacGroupRefSerializer()
    cluster = ClusterRefSerializer()
    level = PermissionLevelCodeField()
    granted_by = RbacUserRefSerializer(allow_null=True)
    granted_at = serializers.DateTimeField()
    notes = serializers.CharField(allow_blank=True, required=False)


class DatabaseGroupPermissionSerializer(serializers.Serializer):
    group = RbacGroupRefSerializer()
    database = DatabaseRefSerializer()
    level = PermissionLevelCodeField()
    granted_by = RbacUserRefSerializer(allow_null=True)
    granted_at = serializers.DateTimeField()
    notes = serializers.CharField(allow_blank=True, required=False)


class ClusterGroupPermissionListResponseSerializer(serializers.Serializer):
    permissions = ClusterGroupPermissionSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class DatabaseGroupPermissionListResponseSerializer(serializers.Serializer):
    permissions = DatabaseGroupPermissionSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class GrantClusterGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    cluster_id = serializers.UUIDField()
    level = PermissionLevelCodeField()
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField()


class RevokeClusterGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    cluster_id = serializers.UUIDField()
    reason = serializers.CharField()


class GrantDatabaseGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    database_id = serializers.CharField()
    level = PermissionLevelCodeField()
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField()


class RevokeDatabaseGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    database_id = serializers.CharField()
    reason = serializers.CharField()


class AdminAuditLogItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    action = serializers.CharField()
    outcome = serializers.CharField()
    actor_username = serializers.CharField()
    actor_id = serializers.IntegerField(allow_null=True)
    target_type = serializers.CharField()
    target_id = serializers.CharField()
    metadata = serializers.DictField()
    error_message = serializers.CharField()


class AdminAuditLogListResponseSerializer(serializers.Serializer):
    items = AdminAuditLogItemSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class RefClustersResponseSerializer(serializers.Serializer):
    clusters = ClusterRefSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class RefDatabasesResponseSerializer(serializers.Serializer):
    databases = DatabaseRefSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class OperationTemplateRefSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()


class WorkflowTemplateRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class ArtifactRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class RefOperationTemplatesResponseSerializer(serializers.Serializer):
    templates = OperationTemplateRefSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class RefWorkflowTemplatesResponseSerializer(serializers.Serializer):
    templates = WorkflowTemplateRefSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class RefArtifactsResponseSerializer(serializers.Serializer):
    artifacts = ArtifactRefSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class ClusterPermissionSerializer(serializers.Serializer):
    user = RbacUserRefSerializer()
    cluster = ClusterRefSerializer()
    level = PermissionLevelCodeField()
    granted_by = RbacUserRefSerializer(allow_null=True)
    granted_at = serializers.DateTimeField()
    notes = serializers.CharField(allow_blank=True, required=False)


class DatabasePermissionSerializer(serializers.Serializer):
    user = RbacUserRefSerializer()
    database = DatabaseRefSerializer()
    level = PermissionLevelCodeField()
    granted_by = RbacUserRefSerializer(allow_null=True)
    granted_at = serializers.DateTimeField()
    notes = serializers.CharField(allow_blank=True, required=False)


class OperationTemplatePermissionSerializer(serializers.Serializer):
    user = RbacUserRefSerializer()
    template = OperationTemplateRefSerializer()
    level = PermissionLevelCodeField()
    granted_by = RbacUserRefSerializer(allow_null=True)
    granted_at = serializers.DateTimeField()
    notes = serializers.CharField(allow_blank=True, required=False)


class OperationTemplateGroupPermissionSerializer(serializers.Serializer):
    group = RbacGroupRefSerializer()
    template = OperationTemplateRefSerializer()
    level = PermissionLevelCodeField()
    granted_by = RbacUserRefSerializer(allow_null=True)
    granted_at = serializers.DateTimeField()
    notes = serializers.CharField(allow_blank=True, required=False)


class WorkflowTemplatePermissionSerializer(serializers.Serializer):
    user = RbacUserRefSerializer()
    template = WorkflowTemplateRefSerializer()
    level = PermissionLevelCodeField()
    granted_by = RbacUserRefSerializer(allow_null=True)
    granted_at = serializers.DateTimeField()
    notes = serializers.CharField(allow_blank=True, required=False)


class WorkflowTemplateGroupPermissionSerializer(serializers.Serializer):
    group = RbacGroupRefSerializer()
    template = WorkflowTemplateRefSerializer()
    level = PermissionLevelCodeField()
    granted_by = RbacUserRefSerializer(allow_null=True)
    granted_at = serializers.DateTimeField()
    notes = serializers.CharField(allow_blank=True, required=False)


class ArtifactPermissionSerializer(serializers.Serializer):
    user = RbacUserRefSerializer()
    artifact = ArtifactRefSerializer()
    level = PermissionLevelCodeField()
    granted_by = RbacUserRefSerializer(allow_null=True)
    granted_at = serializers.DateTimeField()
    notes = serializers.CharField(allow_blank=True, required=False)


class ArtifactGroupPermissionSerializer(serializers.Serializer):
    group = RbacGroupRefSerializer()
    artifact = ArtifactRefSerializer()
    level = PermissionLevelCodeField()
    granted_by = RbacUserRefSerializer(allow_null=True)
    granted_at = serializers.DateTimeField()
    notes = serializers.CharField(allow_blank=True, required=False)


class OperationTemplatePermissionListResponseSerializer(serializers.Serializer):
    permissions = OperationTemplatePermissionSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class OperationTemplateGroupPermissionListResponseSerializer(serializers.Serializer):
    permissions = OperationTemplateGroupPermissionSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class WorkflowTemplatePermissionListResponseSerializer(serializers.Serializer):
    permissions = WorkflowTemplatePermissionSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class WorkflowTemplateGroupPermissionListResponseSerializer(serializers.Serializer):
    permissions = WorkflowTemplateGroupPermissionSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class ArtifactPermissionListResponseSerializer(serializers.Serializer):
    permissions = ArtifactPermissionSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class ArtifactGroupPermissionListResponseSerializer(serializers.Serializer):
    permissions = ArtifactGroupPermissionSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class GrantOperationTemplatePermissionRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    template_id = serializers.CharField()
    level = PermissionLevelCodeField()
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField()


class RevokeOperationTemplatePermissionRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    template_id = serializers.CharField()
    reason = serializers.CharField()


class GrantOperationTemplateGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    template_id = serializers.CharField()
    level = PermissionLevelCodeField()
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField()


class RevokeOperationTemplateGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    template_id = serializers.CharField()
    reason = serializers.CharField()


class GrantWorkflowTemplatePermissionRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    template_id = serializers.UUIDField()
    level = PermissionLevelCodeField()
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField()


class RevokeWorkflowTemplatePermissionRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    template_id = serializers.UUIDField()
    reason = serializers.CharField()


class GrantWorkflowTemplateGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    template_id = serializers.UUIDField()
    level = PermissionLevelCodeField()
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField()


class RevokeWorkflowTemplateGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    template_id = serializers.UUIDField()
    reason = serializers.CharField()


class GrantArtifactPermissionRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    artifact_id = serializers.UUIDField()
    level = PermissionLevelCodeField()
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField()


class RevokeArtifactPermissionRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    artifact_id = serializers.UUIDField()
    reason = serializers.CharField()


class GrantArtifactGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    artifact_id = serializers.UUIDField()
    level = PermissionLevelCodeField()
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField()


class RevokeArtifactGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    artifact_id = serializers.UUIDField()
    reason = serializers.CharField()


class ClusterPermissionListResponseSerializer(serializers.Serializer):
    permissions = ClusterPermissionSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class DatabasePermissionListResponseSerializer(serializers.Serializer):
    permissions = DatabasePermissionSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class RbacUserListResponseSerializer(serializers.Serializer):
    users = RbacUserRefSerializer(many=True)
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


class ClusterGroupPermissionUpsertResponseSerializer(serializers.Serializer):
    created = serializers.BooleanField()
    permission = ClusterGroupPermissionSerializer()


class DatabaseGroupPermissionUpsertResponseSerializer(serializers.Serializer):
    created = serializers.BooleanField()
    permission = DatabaseGroupPermissionSerializer()


class OperationTemplatePermissionUpsertResponseSerializer(serializers.Serializer):
    created = serializers.BooleanField()
    permission = OperationTemplatePermissionSerializer()


class OperationTemplateGroupPermissionUpsertResponseSerializer(serializers.Serializer):
    created = serializers.BooleanField()
    permission = OperationTemplateGroupPermissionSerializer()


class WorkflowTemplatePermissionUpsertResponseSerializer(serializers.Serializer):
    created = serializers.BooleanField()
    permission = WorkflowTemplatePermissionSerializer()


class WorkflowTemplateGroupPermissionUpsertResponseSerializer(serializers.Serializer):
    created = serializers.BooleanField()
    permission = WorkflowTemplateGroupPermissionSerializer()


class ArtifactPermissionUpsertResponseSerializer(serializers.Serializer):
    created = serializers.BooleanField()
    permission = ArtifactPermissionSerializer()


class ArtifactGroupPermissionUpsertResponseSerializer(serializers.Serializer):
    created = serializers.BooleanField()
    permission = ArtifactGroupPermissionSerializer()


class EffectiveAccessClusterItemSerializer(serializers.Serializer):
    cluster = ClusterRefSerializer()
    level = PermissionLevelCodeField()


class EffectiveAccessDatabaseItemSerializer(serializers.Serializer):
    database = DatabaseRefSerializer()
    level = PermissionLevelCodeField()
    source = serializers.ChoiceField(choices=["direct", "cluster"])


class EffectiveAccessOperationTemplateItemSerializer(serializers.Serializer):
    template = OperationTemplateRefSerializer()
    level = PermissionLevelCodeField()
    source = serializers.ChoiceField(choices=["direct", "group"])


class EffectiveAccessWorkflowTemplateItemSerializer(serializers.Serializer):
    template = WorkflowTemplateRefSerializer()
    level = PermissionLevelCodeField()
    source = serializers.ChoiceField(choices=["direct", "group"])


class EffectiveAccessArtifactItemSerializer(serializers.Serializer):
    artifact = ArtifactRefSerializer()
    level = PermissionLevelCodeField()
    source = serializers.ChoiceField(choices=["direct", "group"])


class EffectiveAccessResponseSerializer(serializers.Serializer):
    user = RbacUserRefSerializer()
    clusters = EffectiveAccessClusterItemSerializer(many=True)
    databases = EffectiveAccessDatabaseItemSerializer(many=True)
    operation_templates = EffectiveAccessOperationTemplateItemSerializer(many=True, required=False)
    workflow_templates = EffectiveAccessWorkflowTemplateItemSerializer(many=True, required=False)
    artifacts = EffectiveAccessArtifactItemSerializer(many=True, required=False)


def _user_ref(user: Optional[User]) -> Optional[dict]:
    if user is None:
        return None
    return {"id": user.id, "username": user.username}


def _group_ref(group: Optional[Group]) -> Optional[dict]:
    if group is None:
        return None
    return {"id": group.id, "name": group.name}


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
        200: RbacUserListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_users(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

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
    data = RbacUserRefSerializer(qs, many=True).data

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
            description="Optional (default: current user). Requires databases.manage_rbac for other users.",
        ),
        OpenApiParameter(name="include_databases", type=bool, required=False, default=True),
        OpenApiParameter(name="include_clusters", type=bool, required=False, default=True),
        OpenApiParameter(name="include_templates", type=bool, required=False, default=False),
        OpenApiParameter(name="include_workflows", type=bool, required=False, default=False),
        OpenApiParameter(name="include_artifacts", type=bool, required=False, default=False),
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
    if requested_user_id and int(requested_user_id) != request.user.id:
        denied = _ensure_manage_rbac(request)
        if denied:
            return denied

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
    include_templates = str(request.query_params.get("include_templates", "false")).lower() == "true"
    include_workflows = str(request.query_params.get("include_workflows", "false")).lower() == "true"
    include_artifacts = str(request.query_params.get("include_artifacts", "false")).lower() == "true"

    direct_cluster_perms = []
    direct_cluster_level_map: dict[str, int] = {}
    direct_cluster_obj_map: dict[str, Cluster] = {}

    if include_clusters or include_databases:
        direct_cluster_perms = list(
            ClusterPermission.objects.select_related("cluster").filter(user=target_user)
        )
        direct_cluster_level_map = {str(p.cluster_id): int(p.level) for p in direct_cluster_perms if p.level is not None}
        direct_cluster_obj_map = {str(p.cluster_id): p.cluster for p in direct_cluster_perms}

    group_cluster_level_map: dict[str, int] = {}
    if include_clusters or include_databases:
        rows = (
            ClusterGroupPermission.objects.filter(group__user=target_user)
            .values("cluster_id")
            .annotate(level=Max("level"))
            .values_list("cluster_id", "level")
        )
        group_cluster_level_map = {str(cluster_id): int(level) for cluster_id, level in rows if level is not None}

    cluster_explicit_level_map: dict[str, int] = {}
    for cluster_id in set(direct_cluster_level_map.keys()).union(group_cluster_level_map.keys()):
        levels = [lvl for lvl in [direct_cluster_level_map.get(cluster_id), group_cluster_level_map.get(cluster_id)] if lvl is not None]
        if levels:
            cluster_explicit_level_map[cluster_id] = max(levels)

    clusters_out = []
    if include_clusters:
        derived_cluster_ids: set[str] = set()
        rows = DatabasePermission.objects.filter(
            user=target_user,
            database__cluster_id__isnull=False,
        ).values_list("database__cluster_id", flat=True)
        derived_cluster_ids.update(str(cid) for cid in rows)

        rows = DatabaseGroupPermission.objects.filter(
            group__user=target_user,
            database__cluster_id__isnull=False,
        ).values_list("database__cluster_id", flat=True)
        derived_cluster_ids.update(str(cid) for cid in rows)

        cluster_ids_to_include = set(cluster_explicit_level_map.keys()).union(derived_cluster_ids)
        cluster_obj_map = dict(direct_cluster_obj_map)
        missing_cluster_ids = [cid for cid in cluster_ids_to_include if cid not in cluster_obj_map]
        if missing_cluster_ids:
            for cluster in Cluster.objects.filter(id__in=missing_cluster_ids).only("id", "name"):
                cluster_obj_map[str(cluster.id)] = cluster

        for cluster_id in sorted(cluster_ids_to_include, key=str):
            cluster = cluster_obj_map.get(cluster_id)
            if cluster is None:
                continue
            level = cluster_explicit_level_map.get(cluster_id)
            if level is None:
                level = PermissionLevel.VIEW
            clusters_out.append({"cluster": _cluster_ref(cluster), "level": _level_code(level)})
        clusters_out.sort(key=lambda x: x["cluster"]["name"])

    databases_out = []
    if include_databases:
        direct_db_perms = list(
            DatabasePermission.objects.select_related("database", "database__cluster").filter(user=target_user)
        )
        direct_db_level_map: dict[str, int] = {str(p.database_id): int(p.level) for p in direct_db_perms if p.level is not None}

        rows = (
            DatabaseGroupPermission.objects.filter(group__user=target_user)
            .values("database_id")
            .annotate(level=Max("level"))
            .values_list("database_id", "level")
        )
        group_db_level_map: dict[str, int] = {str(db_id): int(level) for db_id, level in rows if level is not None}

        database_ids_direct = set(direct_db_level_map.keys()).union(group_db_level_map.keys())
        cluster_ids_explicit = list(cluster_explicit_level_map.keys())

        qs = Database.objects.select_related("cluster")
        if database_ids_direct or cluster_ids_explicit:
            qs = qs.filter(
                Q(id__in=list(database_ids_direct))
                | Q(cluster_id__in=cluster_ids_explicit)
            )
        else:
            qs = qs.none()

        databases = list(qs.order_by("name").only("id", "name", "cluster_id"))

        for db in databases:
            db_id = str(db.id)
            direct_level = None
            if db_id in direct_db_level_map:
                direct_level = direct_db_level_map[db_id]
            if db_id in group_db_level_map:
                direct_level = max(direct_level, group_db_level_map[db_id]) if direct_level is not None else group_db_level_map[db_id]

            cluster_level = None
            if db.cluster_id:
                cluster_level = cluster_explicit_level_map.get(str(db.cluster_id))

            levels = [lvl for lvl in [direct_level, cluster_level] if lvl is not None]
            if not levels:
                continue
            effective_level = max(levels)
            source = "direct"
            if cluster_level is not None and (direct_level is None or cluster_level > direct_level):
                source = "cluster"

            databases_out.append(
                {"database": _database_ref(db), "level": _level_code(effective_level), "source": source}
            )

    operation_templates_out = []
    if include_templates:
        direct_rows = list(
            OperationTemplatePermission.objects.select_related("template").filter(user=target_user)
        )
        direct_level_map: dict[str, int] = {str(p.template_id): int(p.level) for p in direct_rows if p.level is not None}

        group_rows = (
            OperationTemplateGroupPermission.objects.filter(group__user=target_user)
            .values("template_id")
            .annotate(level=Max("level"))
            .values_list("template_id", "level")
        )
        group_level_map: dict[str, int] = {str(tpl_id): int(level) for tpl_id, level in group_rows if level is not None}

        template_ids = set(direct_level_map.keys()).union(group_level_map.keys())
        templates = list(
            OperationTemplate.objects.filter(id__in=list(template_ids)).only("id", "name").order_by("name")
        )
        for tpl in templates:
            tpl_id = str(tpl.id)
            user_level = direct_level_map.get(tpl_id)
            group_level = group_level_map.get(tpl_id)
            levels = [lvl for lvl in [user_level, group_level] if lvl is not None]
            if not levels:
                continue
            effective_level = max(levels)
            source = "direct"
            if group_level is not None and (user_level is None or group_level > user_level):
                source = "group"
            operation_templates_out.append(
                {"template": {"id": tpl.id, "name": tpl.name}, "level": _level_code(effective_level), "source": source}
            )

    workflow_templates_out = []
    if include_workflows:
        direct_rows = list(
            WorkflowTemplatePermission.objects.select_related("workflow_template").filter(user=target_user)
        )
        direct_level_map: dict[str, int] = {
            str(p.workflow_template_id): int(p.level) for p in direct_rows if p.level is not None
        }

        group_rows = (
            WorkflowTemplateGroupPermission.objects.filter(group__user=target_user)
            .values("workflow_template_id")
            .annotate(level=Max("level"))
            .values_list("workflow_template_id", "level")
        )
        group_level_map: dict[str, int] = {
            str(tpl_id): int(level) for tpl_id, level in group_rows if level is not None
        }

        template_ids = set(direct_level_map.keys()).union(group_level_map.keys())
        templates = list(
            WorkflowTemplate.objects.filter(id__in=list(template_ids)).only("id", "name").order_by("name")
        )
        for tpl in templates:
            tpl_id = str(tpl.id)
            user_level = direct_level_map.get(tpl_id)
            group_level = group_level_map.get(tpl_id)
            levels = [lvl for lvl in [user_level, group_level] if lvl is not None]
            if not levels:
                continue
            effective_level = max(levels)
            source = "direct"
            if group_level is not None and (user_level is None or group_level > user_level):
                source = "group"
            workflow_templates_out.append(
                {"template": {"id": tpl.id, "name": tpl.name}, "level": _level_code(effective_level), "source": source}
            )

    artifacts_out = []
    if include_artifacts:
        direct_rows = list(
            ArtifactPermission.objects.select_related("artifact").filter(user=target_user)
        )
        direct_level_map: dict[str, int] = {str(p.artifact_id): int(p.level) for p in direct_rows if p.level is not None}

        group_rows = (
            ArtifactGroupPermission.objects.filter(group__user=target_user)
            .values("artifact_id")
            .annotate(level=Max("level"))
            .values_list("artifact_id", "level")
        )
        group_level_map: dict[str, int] = {str(art_id): int(level) for art_id, level in group_rows if level is not None}

        artifact_ids = set(direct_level_map.keys()).union(group_level_map.keys())
        artifacts = list(
            Artifact.objects.filter(id__in=list(artifact_ids), is_deleted=False).only("id", "name").order_by("name")
        )
        for art in artifacts:
            art_id = str(art.id)
            user_level = direct_level_map.get(art_id)
            group_level = group_level_map.get(art_id)
            levels = [lvl for lvl in [user_level, group_level] if lvl is not None]
            if not levels:
                continue
            effective_level = max(levels)
            source = "direct"
            if group_level is not None and (user_level is None or group_level > user_level):
                source = "group"
            artifacts_out.append(
                {"artifact": {"id": art.id, "name": art.name}, "level": _level_code(effective_level), "source": source}
            )

    return Response(
        {
            "user": _user_ref(target_user),
            "clusters": clusters_out,
            "databases": databases_out,
            "operation_templates": operation_templates_out,
            "workflow_templates": workflow_templates_out,
            "artifacts": artifacts_out,
        }
    )


# =============================================================================
# Roles / Capabilities (Django Groups + Django permissions)
# =============================================================================


def _get_curated_permission_codes() -> list[str]:
    codes: set[str] = set()
    for name in dir(perms):
        if not name.startswith("PERM_"):
            continue
        value = getattr(perms, name)
        if isinstance(value, str) and "." in value:
            codes.add(value)
    return sorted(codes)


def _split_permission_code(code: str) -> tuple[str, str] | None:
    value = str(code or "").strip()
    if not value or "." not in value:
        return None
    app_label, codename = value.split(".", 1)
    app_label = app_label.strip()
    codename = codename.strip()
    if not app_label or not codename:
        return None
    return app_label, codename


@extend_schema(
    tags=["v2"],
    summary="List roles (Django groups)",
    parameters=[
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={
        200: RoleListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_roles(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    search = (request.query_params.get("search") or "").strip()
    pagination = _parse_pagination(request, default_limit=100, max_limit=500)

    qs = Group.objects.all()
    if search:
        qs = qs.filter(name__icontains=search)

    total = qs.count()
    rows = list(
        qs.annotate(
            users_count=Count("user", distinct=True),
            permissions_count=Count("permissions", distinct=True),
        )
        .prefetch_related("permissions__content_type")
        .order_by("name")[pagination.offset: pagination.offset + pagination.limit]
    )

    data = []
    for group in rows:
        permission_codes = sorted({
            f"{p.content_type.app_label}.{p.codename}"
            for p in group.permissions.all()
        })
        data.append(
            {
                "id": group.id,
                "name": group.name,
                "users_count": int(getattr(group, "users_count", 0) or 0),
                "permissions_count": int(getattr(group, "permissions_count", 0) or 0),
                "permission_codes": permission_codes,
            }
        )

    return Response({"roles": data, "count": len(data), "total": total})


@extend_schema(
    tags=["v2"],
    summary="Create role (Django group)",
    request=RoleCreateRequestSerializer,
    responses={
        200: RbacGroupRefSerializer,
        400: RbacErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        409: RbacErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_role(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RoleCreateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.create_role",
            outcome="error",
            target_type="group",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    name = str(serializer.validated_data.get("name") or "").strip()
    reason = str(serializer.validated_data.get("reason") or "").strip()
    if not name:
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "name is required"}},
            status=400,
        )

    if Group.objects.filter(name=name).exists():
        return Response(
            {"success": False, "error": {"code": "DUPLICATE", "message": "Role already exists"}},
            status=409,
        )

    group = Group.objects.create(name=name)
    log_admin_action(
        request,
        action="rbac.create_role",
        outcome="success",
        target_type="group",
        target_id=str(group.id),
        metadata={"reason": reason, "name": name},
    )
    return Response({"id": group.id, "name": group.name})


@extend_schema(
    tags=["v2"],
    summary="Update role (rename Django group)",
    request=RoleUpdateRequestSerializer,
    responses={
        200: RbacGroupRefSerializer,
        400: RbacErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: RbacErrorResponseSerializer,
        409: RbacErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_role(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RoleUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.update_role",
            outcome="error",
            target_type="group",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    name = str(serializer.validated_data.get("name") or "").strip()
    reason = str(serializer.validated_data.get("reason") or "").strip()
    if not name:
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "name is required"}},
            status=400,
        )

    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Role not found"}},
            status=404,
        )

    if Group.objects.exclude(id=group_id).filter(name=name).exists():
        return Response(
            {"success": False, "error": {"code": "DUPLICATE", "message": "Role name already exists"}},
            status=409,
        )

    old_name = group.name
    group.name = name
    group.save(update_fields=["name"])
    log_admin_action(
        request,
        action="rbac.update_role",
        outcome="success",
        target_type="group",
        target_id=str(group.id),
        metadata={"reason": reason, "old_name": old_name, "name": name},
    )
    return Response({"id": group.id, "name": group.name})


@extend_schema(
    tags=["v2"],
    summary="Delete role (safe delete)",
    request=RoleDeleteRequestSerializer,
    responses={
        200: RevokePermissionResponseSerializer,
        400: RbacErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: RbacErrorResponseSerializer,
        409: RbacErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def delete_role(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RoleDeleteRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.delete_role",
            outcome="error",
            target_type="group",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Role not found"}},
            status=404,
        )

    has_members = group.user_set.exists()
    has_capabilities = group.permissions.exists()
    has_bindings = (
        ClusterGroupPermission.objects.filter(group=group).exists()
        or DatabaseGroupPermission.objects.filter(group=group).exists()
        or OperationTemplateGroupPermission.objects.filter(group=group).exists()
        or WorkflowTemplateGroupPermission.objects.filter(group=group).exists()
        or ArtifactGroupPermission.objects.filter(group=group).exists()
    )

    if has_members or has_capabilities or has_bindings:
        return Response(
            {
                "success": False,
                "error": {
                    "code": "ROLE_NOT_EMPTY",
                    "message": "Role has members/capabilities/bindings and cannot be deleted",
                },
            },
            status=409,
        )

    group.delete()
    log_admin_action(
        request,
        action="rbac.delete_role",
        outcome="success",
        target_type="group",
        target_id=str(group_id),
        metadata={"reason": reason},
    )
    return Response({"deleted": True})


@extend_schema(
    tags=["v2"],
    summary="List supported capability permissions (curated)",
    responses={
        200: CapabilityListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_capabilities(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    codes = _get_curated_permission_codes()
    pairs = [_split_permission_code(code) for code in codes]
    pairs = [p for p in pairs if p is not None]
    app_labels = sorted({p[0] for p in pairs})
    codenames = sorted({p[1] for p in pairs})

    perm_map: dict[tuple[str, str], Permission] = {}
    if pairs:
        qs = Permission.objects.select_related("content_type").filter(
            content_type__app_label__in=app_labels,
            codename__in=codenames,
        )
        perm_map = {(p.content_type.app_label, p.codename): p for p in qs}

    items = []
    for code in codes:
        split = _split_permission_code(code)
        if split is None:
            continue
        app_label, codename = split
        perm = perm_map.get((app_label, codename))
        items.append(
            {
                "code": code,
                "name": perm.name if perm else "",
                "app_label": app_label,
                "codename": codename,
                "exists": bool(perm),
            }
        )

    return Response({"capabilities": items, "count": len(items)})


@extend_schema(
    tags=["v2"],
    summary="Update role capabilities (group permissions)",
    request=RoleCapabilitiesUpdateRequestSerializer,
    responses={
        200: RoleCapabilitiesUpdateResponseSerializer,
        400: RbacErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: RbacErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_role_capabilities(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RoleCapabilitiesUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.set_role_capabilities",
            outcome="error",
            target_type="group",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    permission_codes = serializer.validated_data["permission_codes"]
    mode = serializer.validated_data.get("mode") or "replace"
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Role not found"}},
            status=404,
        )

    parsed: list[tuple[str, str, str]] = []
    for code in permission_codes:
        split = _split_permission_code(code)
        if split is None:
            return Response(
                {"success": False, "error": {"code": "INVALID_PERMISSION", "message": f"Invalid code: {code}"}},
                status=400,
            )
        app_label, codename = split
        parsed.append((code, app_label, codename))

    app_labels = sorted({app_label for _, app_label, _ in parsed})
    codenames = sorted({codename for _, _, codename in parsed})
    perm_map: dict[tuple[str, str], Permission] = {}
    if parsed:
        qs = Permission.objects.select_related("content_type").filter(
            content_type__app_label__in=app_labels,
            codename__in=codenames,
        )
        perm_map = {(p.content_type.app_label, p.codename): p for p in qs}

    missing = [code for code, app_label, codename in parsed if (app_label, codename) not in perm_map]
    if missing:
        return Response(
            {
                "success": False,
                "error": {"code": "UNKNOWN_PERMISSION", "message": f"Unknown permission codes: {missing}"},
            },
            status=400,
        )

    resolved = [perm_map[(app_label, codename)] for _, app_label, codename in parsed]

    if mode == "replace":
        group.permissions.set(resolved)
    elif mode == "add":
        group.permissions.add(*resolved)
    elif mode == "remove":
        group.permissions.remove(*resolved)
    else:
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Invalid mode"}},
            status=400,
        )

    updated_codes = sorted({f"{p.content_type.app_label}.{p.codename}" for p in group.permissions.select_related("content_type").all()})
    log_admin_action(
        request,
        action="rbac.set_role_capabilities",
        outcome="success",
        target_type="group",
        target_id=str(group.id),
        metadata={
            "reason": reason,
            "mode": mode,
            "permission_codes": permission_codes,
        },
    )
    return Response({"group": _group_ref(group), "permission_codes": updated_codes})


@extend_schema(
    tags=["v2"],
    summary="Get user roles (groups)",
    parameters=[OpenApiParameter(name="user_id", type=int, required=False)],
    responses={
        200: UserRolesGetResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: RbacErrorResponseSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_roles(request):
    requested_user_id = request.query_params.get("user_id")
    if requested_user_id and int(requested_user_id) != request.user.id:
        denied = _ensure_manage_rbac(request)
        if denied:
            return denied

    target_user = request.user
    if requested_user_id:
        try:
            target_user = User.objects.get(id=requested_user_id)
        except User.DoesNotExist:
            return Response(
                {"success": False, "error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
                status=404,
            )

    roles = list(target_user.groups.all().order_by("name"))
    return Response({"user": _user_ref(target_user), "roles": [_group_ref(g) for g in roles]})


@extend_schema(
    tags=["v2"],
    summary="Update user roles (group membership)",
    request=UserRolesUpdateRequestSerializer,
    responses={
        200: UserRolesGetResponseSerializer,
        400: RbacErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: RbacErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_user_roles(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = UserRolesUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.set_user_roles",
            outcome="error",
            target_type="user",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    user_id = serializer.validated_data["user_id"]
    group_ids = serializer.validated_data["group_ids"]
    mode = serializer.validated_data.get("mode") or "replace"
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
            status=404,
        )

    groups = list(Group.objects.filter(id__in=group_ids))
    if len(groups) != len(set(group_ids)):
        return Response(
            {"success": False, "error": {"code": "GROUP_NOT_FOUND", "message": "One or more roles not found"}},
            status=404,
        )

    if mode == "replace":
        target_user.groups.set(groups)
    elif mode == "add":
        target_user.groups.add(*groups)
    elif mode == "remove":
        target_user.groups.remove(*groups)
    else:
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Invalid mode"}},
            status=400,
        )

    roles = list(target_user.groups.all().order_by("name"))
    log_admin_action(
        request,
        action="rbac.set_user_roles",
        outcome="success",
        target_type="user",
        target_id=str(target_user.id),
        metadata={"reason": reason, "mode": mode, "group_ids": group_ids},
    )
    return Response({"user": _user_ref(target_user), "roles": [_group_ref(g) for g in roles]})


# =============================================================================
# RBAC Object Refs (for SPA pickers; requires manage_rbac)
# =============================================================================


@extend_schema(
    tags=["v2"],
    summary="List clusters (RBAC ref)",
    parameters=[
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: RefClustersResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ref_clusters(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    search = (request.query_params.get("search") or "").strip()
    pagination = _parse_pagination(request, default_limit=200, max_limit=1000)

    qs = Cluster.objects.all()
    if search:
        qs = qs.filter(name__icontains=search)

    total = qs.count()
    rows = list(qs.order_by("name")[pagination.offset: pagination.offset + pagination.limit])
    data = [{"id": row.id, "name": row.name} for row in rows]
    return Response({"clusters": data, "count": len(data), "total": total})


@extend_schema(
    tags=["v2"],
    summary="List databases (RBAC ref)",
    parameters=[
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="cluster_id", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: RefDatabasesResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ref_databases(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    search = (request.query_params.get("search") or "").strip()
    cluster_id = (request.query_params.get("cluster_id") or "").strip()
    pagination = _parse_pagination(request, default_limit=200, max_limit=2000)

    qs = Database.objects.all()
    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(id__icontains=search))

    total = qs.count()
    rows = list(qs.order_by("name")[pagination.offset: pagination.offset + pagination.limit])
    data = [{"id": str(row.id), "name": row.name, "cluster_id": row.cluster_id} for row in rows]
    return Response({"databases": data, "count": len(data), "total": total})


@extend_schema(
    tags=["v2"],
    summary="List operation templates (RBAC ref)",
    parameters=[
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: RefOperationTemplatesResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ref_operation_templates(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    search = (request.query_params.get("search") or "").strip()
    pagination = _parse_pagination(request, default_limit=200, max_limit=2000)

    qs = OperationTemplate.objects.all()
    if search:
        qs = qs.filter(Q(id__icontains=search) | Q(name__icontains=search))

    total = qs.count()
    rows = list(qs.order_by("name")[pagination.offset: pagination.offset + pagination.limit])
    data = [{"id": row.id, "name": row.name} for row in rows]
    return Response({"templates": data, "count": len(data), "total": total})


@extend_schema(
    tags=["v2"],
    summary="List workflow templates (RBAC ref)",
    parameters=[
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: RefWorkflowTemplatesResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ref_workflow_templates(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    search = (request.query_params.get("search") or "").strip()
    pagination = _parse_pagination(request, default_limit=200, max_limit=2000)

    qs = WorkflowTemplate.objects.all()
    if search:
        qs = qs.filter(name__icontains=search)

    total = qs.count()
    rows = list(qs.order_by("name")[pagination.offset: pagination.offset + pagination.limit])
    data = [{"id": row.id, "name": row.name} for row in rows]
    return Response({"templates": data, "count": len(data), "total": total})


@extend_schema(
    tags=["v2"],
    summary="List artifacts (RBAC ref)",
    parameters=[
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: RefArtifactsResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ref_artifacts(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    search = (request.query_params.get("search") or "").strip()
    pagination = _parse_pagination(request, default_limit=200, max_limit=2000)

    qs = Artifact.objects.filter(is_deleted=False)
    if search:
        qs = qs.filter(name__icontains=search)

    total = qs.count()
    rows = list(qs.order_by("name")[pagination.offset: pagination.offset + pagination.limit])
    data = [{"id": row.id, "name": row.name} for row in rows]
    return Response({"artifacts": data, "count": len(data), "total": total})


# =============================================================================
# Group bindings (clusters/databases/templates/workflows/artifacts)
# =============================================================================


@extend_schema(
    tags=["v2"],
    summary="List cluster group permissions",
    parameters=[
        OpenApiParameter(name="group_id", type=int, required=False),
        OpenApiParameter(name="cluster_id", type=str, required=False),
        OpenApiParameter(name="level", type=str, required=False),
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: ClusterGroupPermissionListResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_cluster_group_permissions(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    pagination = _parse_pagination(request)
    qs = ClusterGroupPermission.objects.select_related("group", "cluster", "granted_by").all()

    group_id = request.query_params.get("group_id")
    if group_id:
        qs = qs.filter(group_id=group_id)

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
            Q(group__name__icontains=search)
            | Q(cluster__name__icontains=search)
        )

    total = qs.count()
    rows = list(qs.order_by("-granted_at")[pagination.offset: pagination.offset + pagination.limit])

    data = [
        {
            "group": _group_ref(row.group),
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
    summary="Grant cluster group permission",
    request=GrantClusterGroupPermissionRequestSerializer,
    responses={200: ClusterGroupPermissionUpsertResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grant_cluster_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = GrantClusterGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.grant_cluster_group_permission",
            outcome="error",
            target_type="cluster",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    cluster_id = serializer.validated_data["cluster_id"]
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
        cluster = Cluster.objects.get(id=cluster_id)
    except Cluster.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "CLUSTER_NOT_FOUND", "message": "Cluster not found"}},
            status=404,
        )

    with transaction.atomic():
        obj, created = ClusterGroupPermission.objects.select_for_update().get_or_create(
            group=group,
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
            "group": _group_ref(obj.group),
            "cluster": _cluster_ref(obj.cluster),
            "level": _level_code(obj.level),
            "granted_by": _user_ref(obj.granted_by),
            "granted_at": obj.granted_at,
            "notes": obj.notes,
        },
    }
    log_admin_action(
        request,
        action="rbac.grant_cluster_group_permission",
        outcome="success",
        target_type="cluster",
        target_id=str(cluster_id),
        metadata={"reason": reason, "group_id": group_id, "level": _level_code(level), "created": created, "notes": notes},
    )
    return Response(payload)


@extend_schema(
    tags=["v2"],
    summary="Revoke cluster group permission",
    request=RevokeClusterGroupPermissionRequestSerializer,
    responses={200: RevokePermissionResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_cluster_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RevokeClusterGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.revoke_cluster_group_permission",
            outcome="error",
            target_type="cluster",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    cluster_id = serializer.validated_data["cluster_id"]
    reason = str(serializer.validated_data.get("reason") or "").strip()

    deleted, _ = ClusterGroupPermission.objects.filter(group_id=group_id, cluster_id=cluster_id).delete()
    log_admin_action(
        request,
        action="rbac.revoke_cluster_group_permission",
        outcome="success",
        target_type="cluster",
        target_id=str(cluster_id),
        metadata={"reason": reason, "group_id": group_id, "deleted": deleted > 0},
    )
    return Response({"deleted": deleted > 0})


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

    with transaction.atomic():
        obj, created = DatabaseGroupPermission.objects.select_for_update().get_or_create(
            group=group,
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
        metadata={"reason": reason, "group_id": group_id, "level": _level_code(level), "created": created, "notes": notes},
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

    deleted, _ = DatabaseGroupPermission.objects.filter(group_id=group_id, database_id=database_id).delete()
    log_admin_action(
        request,
        action="rbac.revoke_database_group_permission",
        outcome="success",
        target_type="database",
        target_id=str(database_id),
        metadata={"reason": reason, "group_id": group_id, "deleted": deleted > 0},
    )
    return Response({"deleted": deleted > 0})


# =============================================================================
# User bindings for Templates/Workflows/Artifacts (SPA-primary RBAC)
# =============================================================================


@extend_schema(
    tags=["v2"],
    summary="List operation template permissions (user)",
    parameters=[
        OpenApiParameter(name="user_id", type=int, required=False),
        OpenApiParameter(name="template_id", type=str, required=False),
        OpenApiParameter(name="level", type=str, required=False),
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: OperationTemplatePermissionListResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_operation_template_permissions(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    pagination = _parse_pagination(request)
    qs = OperationTemplatePermission.objects.select_related("user", "template", "granted_by").all()

    user_id = request.query_params.get("user_id")
    if user_id:
        qs = qs.filter(user_id=user_id)

    template_id = request.query_params.get("template_id")
    if template_id:
        qs = qs.filter(template_id=template_id)

    level = request.query_params.get("level")
    if level:
        try:
            level_value = getattr(PermissionLevel, str(level).strip().upper())
            qs = qs.filter(level=level_value)
        except Exception:
            pass

    search = request.query_params.get("search")
    if search:
        qs = qs.filter(Q(user__username__icontains=search) | Q(template__name__icontains=search))

    total = qs.count()
    rows = list(qs.order_by("-granted_at")[pagination.offset: pagination.offset + pagination.limit])
    data = [
        {
            "user": _user_ref(row.user),
            "template": {"id": row.template.id, "name": row.template.name},
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
    summary="Grant operation template permission (user)",
    request=GrantOperationTemplatePermissionRequestSerializer,
    responses={200: OperationTemplatePermissionUpsertResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grant_operation_template_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = GrantOperationTemplatePermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.grant_operation_template_permission",
            outcome="error",
            target_type="operation_template",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    user_id = serializer.validated_data["user_id"]
    template_id = serializer.validated_data["template_id"]
    level = serializer.validated_data["level"]
    notes = serializer.validated_data.get("notes", "")
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
            status=404,
        )

    try:
        template = OperationTemplate.objects.get(id=template_id)
    except OperationTemplate.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "TEMPLATE_NOT_FOUND", "message": "Template not found"}},
            status=404,
        )

    with transaction.atomic():
        obj, created = OperationTemplatePermission.objects.select_for_update().get_or_create(
            user=user,
            template=template,
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
            "template": {"id": obj.template.id, "name": obj.template.name},
            "level": _level_code(obj.level),
            "granted_by": _user_ref(obj.granted_by),
            "granted_at": obj.granted_at,
            "notes": obj.notes,
        },
    }
    log_admin_action(
        request,
        action="rbac.grant_operation_template_permission",
        outcome="success",
        target_type="operation_template",
        target_id=str(template_id),
        metadata={"reason": reason, "user_id": user_id, "level": _level_code(level), "created": created, "notes": notes},
    )
    return Response(payload)


@extend_schema(
    tags=["v2"],
    summary="Revoke operation template permission (user)",
    request=RevokeOperationTemplatePermissionRequestSerializer,
    responses={200: RevokePermissionResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_operation_template_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RevokeOperationTemplatePermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.revoke_operation_template_permission",
            outcome="error",
            target_type="operation_template",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    user_id = serializer.validated_data["user_id"]
    template_id = serializer.validated_data["template_id"]
    reason = str(serializer.validated_data.get("reason") or "").strip()

    deleted, _ = OperationTemplatePermission.objects.filter(user_id=user_id, template_id=template_id).delete()
    log_admin_action(
        request,
        action="rbac.revoke_operation_template_permission",
        outcome="success",
        target_type="operation_template",
        target_id=str(template_id),
        metadata={"reason": reason, "user_id": user_id, "deleted": deleted > 0},
    )
    return Response({"deleted": deleted > 0})


@extend_schema(
    tags=["v2"],
    summary="List operation template permissions (group)",
    parameters=[
        OpenApiParameter(name="group_id", type=int, required=False),
        OpenApiParameter(name="template_id", type=str, required=False),
        OpenApiParameter(name="level", type=str, required=False),
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: OperationTemplateGroupPermissionListResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_operation_template_group_permissions(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    pagination = _parse_pagination(request)
    qs = OperationTemplateGroupPermission.objects.select_related("group", "template", "granted_by").all()

    group_id = request.query_params.get("group_id")
    if group_id:
        qs = qs.filter(group_id=group_id)

    template_id = request.query_params.get("template_id")
    if template_id:
        qs = qs.filter(template_id=template_id)

    level = request.query_params.get("level")
    if level:
        try:
            level_value = getattr(PermissionLevel, str(level).strip().upper())
            qs = qs.filter(level=level_value)
        except Exception:
            pass

    search = request.query_params.get("search")
    if search:
        qs = qs.filter(Q(group__name__icontains=search) | Q(template__name__icontains=search))

    total = qs.count()
    rows = list(qs.order_by("-granted_at")[pagination.offset: pagination.offset + pagination.limit])
    data = [
        {
            "group": _group_ref(row.group),
            "template": {"id": row.template.id, "name": row.template.name},
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
    summary="Grant operation template permission (group)",
    request=GrantOperationTemplateGroupPermissionRequestSerializer,
    responses={200: OperationTemplateGroupPermissionUpsertResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grant_operation_template_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = GrantOperationTemplateGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.grant_operation_template_group_permission",
            outcome="error",
            target_type="operation_template",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    template_id = serializer.validated_data["template_id"]
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
        template = OperationTemplate.objects.get(id=template_id)
    except OperationTemplate.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "TEMPLATE_NOT_FOUND", "message": "Template not found"}},
            status=404,
        )

    with transaction.atomic():
        obj, created = OperationTemplateGroupPermission.objects.select_for_update().get_or_create(
            group=group,
            template=template,
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
            "group": _group_ref(obj.group),
            "template": {"id": obj.template.id, "name": obj.template.name},
            "level": _level_code(obj.level),
            "granted_by": _user_ref(obj.granted_by),
            "granted_at": obj.granted_at,
            "notes": obj.notes,
        },
    }
    log_admin_action(
        request,
        action="rbac.grant_operation_template_group_permission",
        outcome="success",
        target_type="operation_template",
        target_id=str(template_id),
        metadata={"reason": reason, "group_id": group_id, "level": _level_code(level), "created": created, "notes": notes},
    )
    return Response(payload)


@extend_schema(
    tags=["v2"],
    summary="Revoke operation template permission (group)",
    request=RevokeOperationTemplateGroupPermissionRequestSerializer,
    responses={200: RevokePermissionResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_operation_template_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RevokeOperationTemplateGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.revoke_operation_template_group_permission",
            outcome="error",
            target_type="operation_template",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    template_id = serializer.validated_data["template_id"]
    reason = str(serializer.validated_data.get("reason") or "").strip()

    deleted, _ = OperationTemplateGroupPermission.objects.filter(group_id=group_id, template_id=template_id).delete()
    log_admin_action(
        request,
        action="rbac.revoke_operation_template_group_permission",
        outcome="success",
        target_type="operation_template",
        target_id=str(template_id),
        metadata={"reason": reason, "group_id": group_id, "deleted": deleted > 0},
    )
    return Response({"deleted": deleted > 0})


@extend_schema(
    tags=["v2"],
    summary="List workflow template permissions (user)",
    parameters=[
        OpenApiParameter(name="user_id", type=int, required=False),
        OpenApiParameter(name="template_id", type=str, required=False),
        OpenApiParameter(name="level", type=str, required=False),
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: WorkflowTemplatePermissionListResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_workflow_template_permissions(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    pagination = _parse_pagination(request)
    qs = WorkflowTemplatePermission.objects.select_related("user", "workflow_template", "granted_by").all()

    user_id = request.query_params.get("user_id")
    if user_id:
        qs = qs.filter(user_id=user_id)

    template_id = request.query_params.get("template_id")
    if template_id:
        qs = qs.filter(workflow_template_id=template_id)

    level = request.query_params.get("level")
    if level:
        try:
            level_value = getattr(PermissionLevel, str(level).strip().upper())
            qs = qs.filter(level=level_value)
        except Exception:
            pass

    search = request.query_params.get("search")
    if search:
        qs = qs.filter(Q(user__username__icontains=search) | Q(workflow_template__name__icontains=search))

    total = qs.count()
    rows = list(qs.order_by("-granted_at")[pagination.offset: pagination.offset + pagination.limit])
    data = [
        {
            "user": _user_ref(row.user),
            "template": {"id": row.workflow_template.id, "name": row.workflow_template.name},
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
    summary="Grant workflow template permission (user)",
    request=GrantWorkflowTemplatePermissionRequestSerializer,
    responses={200: WorkflowTemplatePermissionUpsertResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grant_workflow_template_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = GrantWorkflowTemplatePermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.grant_workflow_template_permission",
            outcome="error",
            target_type="workflow_template",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    user_id = serializer.validated_data["user_id"]
    template_id = serializer.validated_data["template_id"]
    level = serializer.validated_data["level"]
    notes = serializer.validated_data.get("notes", "")
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
            status=404,
        )

    try:
        template = WorkflowTemplate.objects.get(id=template_id)
    except WorkflowTemplate.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "TEMPLATE_NOT_FOUND", "message": "Template not found"}},
            status=404,
        )

    with transaction.atomic():
        obj, created = WorkflowTemplatePermission.objects.select_for_update().get_or_create(
            user=user,
            workflow_template=template,
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
            "template": {"id": obj.workflow_template.id, "name": obj.workflow_template.name},
            "level": _level_code(obj.level),
            "granted_by": _user_ref(obj.granted_by),
            "granted_at": obj.granted_at,
            "notes": obj.notes,
        },
    }
    log_admin_action(
        request,
        action="rbac.grant_workflow_template_permission",
        outcome="success",
        target_type="workflow_template",
        target_id=str(template_id),
        metadata={"reason": reason, "user_id": user_id, "level": _level_code(level), "created": created, "notes": notes},
    )
    return Response(payload)


@extend_schema(
    tags=["v2"],
    summary="Revoke workflow template permission (user)",
    request=RevokeWorkflowTemplatePermissionRequestSerializer,
    responses={200: RevokePermissionResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_workflow_template_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RevokeWorkflowTemplatePermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.revoke_workflow_template_permission",
            outcome="error",
            target_type="workflow_template",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    user_id = serializer.validated_data["user_id"]
    template_id = serializer.validated_data["template_id"]
    reason = str(serializer.validated_data.get("reason") or "").strip()

    deleted, _ = WorkflowTemplatePermission.objects.filter(user_id=user_id, workflow_template_id=template_id).delete()
    log_admin_action(
        request,
        action="rbac.revoke_workflow_template_permission",
        outcome="success",
        target_type="workflow_template",
        target_id=str(template_id),
        metadata={"reason": reason, "user_id": user_id, "deleted": deleted > 0},
    )
    return Response({"deleted": deleted > 0})


@extend_schema(
    tags=["v2"],
    summary="List workflow template permissions (group)",
    parameters=[
        OpenApiParameter(name="group_id", type=int, required=False),
        OpenApiParameter(name="template_id", type=str, required=False),
        OpenApiParameter(name="level", type=str, required=False),
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: WorkflowTemplateGroupPermissionListResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_workflow_template_group_permissions(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    pagination = _parse_pagination(request)
    qs = WorkflowTemplateGroupPermission.objects.select_related("group", "workflow_template", "granted_by").all()

    group_id = request.query_params.get("group_id")
    if group_id:
        qs = qs.filter(group_id=group_id)

    template_id = request.query_params.get("template_id")
    if template_id:
        qs = qs.filter(workflow_template_id=template_id)

    level = request.query_params.get("level")
    if level:
        try:
            level_value = getattr(PermissionLevel, str(level).strip().upper())
            qs = qs.filter(level=level_value)
        except Exception:
            pass

    search = request.query_params.get("search")
    if search:
        qs = qs.filter(Q(group__name__icontains=search) | Q(workflow_template__name__icontains=search))

    total = qs.count()
    rows = list(qs.order_by("-granted_at")[pagination.offset: pagination.offset + pagination.limit])
    data = [
        {
            "group": _group_ref(row.group),
            "template": {"id": row.workflow_template.id, "name": row.workflow_template.name},
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
    summary="Grant workflow template permission (group)",
    request=GrantWorkflowTemplateGroupPermissionRequestSerializer,
    responses={200: WorkflowTemplateGroupPermissionUpsertResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grant_workflow_template_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = GrantWorkflowTemplateGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.grant_workflow_template_group_permission",
            outcome="error",
            target_type="workflow_template",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    template_id = serializer.validated_data["template_id"]
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
        template = WorkflowTemplate.objects.get(id=template_id)
    except WorkflowTemplate.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "TEMPLATE_NOT_FOUND", "message": "Template not found"}},
            status=404,
        )

    with transaction.atomic():
        obj, created = WorkflowTemplateGroupPermission.objects.select_for_update().get_or_create(
            group=group,
            workflow_template=template,
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
            "group": _group_ref(obj.group),
            "template": {"id": obj.workflow_template.id, "name": obj.workflow_template.name},
            "level": _level_code(obj.level),
            "granted_by": _user_ref(obj.granted_by),
            "granted_at": obj.granted_at,
            "notes": obj.notes,
        },
    }
    log_admin_action(
        request,
        action="rbac.grant_workflow_template_group_permission",
        outcome="success",
        target_type="workflow_template",
        target_id=str(template_id),
        metadata={"reason": reason, "group_id": group_id, "level": _level_code(level), "created": created, "notes": notes},
    )
    return Response(payload)


@extend_schema(
    tags=["v2"],
    summary="Revoke workflow template permission (group)",
    request=RevokeWorkflowTemplateGroupPermissionRequestSerializer,
    responses={200: RevokePermissionResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_workflow_template_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RevokeWorkflowTemplateGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.revoke_workflow_template_group_permission",
            outcome="error",
            target_type="workflow_template",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    template_id = serializer.validated_data["template_id"]
    reason = str(serializer.validated_data.get("reason") or "").strip()

    deleted, _ = WorkflowTemplateGroupPermission.objects.filter(group_id=group_id, workflow_template_id=template_id).delete()
    log_admin_action(
        request,
        action="rbac.revoke_workflow_template_group_permission",
        outcome="success",
        target_type="workflow_template",
        target_id=str(template_id),
        metadata={"reason": reason, "group_id": group_id, "deleted": deleted > 0},
    )
    return Response({"deleted": deleted > 0})


@extend_schema(
    tags=["v2"],
    summary="List artifact permissions (user)",
    parameters=[
        OpenApiParameter(name="user_id", type=int, required=False),
        OpenApiParameter(name="artifact_id", type=str, required=False),
        OpenApiParameter(name="level", type=str, required=False),
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: ArtifactPermissionListResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_artifact_permissions(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    pagination = _parse_pagination(request)
    qs = ArtifactPermission.objects.select_related("user", "artifact", "granted_by").all()

    user_id = request.query_params.get("user_id")
    if user_id:
        qs = qs.filter(user_id=user_id)

    artifact_id = request.query_params.get("artifact_id")
    if artifact_id:
        qs = qs.filter(artifact_id=artifact_id)

    level = request.query_params.get("level")
    if level:
        try:
            level_value = getattr(PermissionLevel, str(level).strip().upper())
            qs = qs.filter(level=level_value)
        except Exception:
            pass

    search = request.query_params.get("search")
    if search:
        qs = qs.filter(Q(user__username__icontains=search) | Q(artifact__name__icontains=search))

    total = qs.count()
    rows = list(qs.order_by("-granted_at")[pagination.offset: pagination.offset + pagination.limit])
    data = [
        {
            "user": _user_ref(row.user),
            "artifact": {"id": row.artifact.id, "name": row.artifact.name},
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
    summary="Grant artifact permission (user)",
    request=GrantArtifactPermissionRequestSerializer,
    responses={200: ArtifactPermissionUpsertResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grant_artifact_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = GrantArtifactPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.grant_artifact_permission",
            outcome="error",
            target_type="artifact",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    user_id = serializer.validated_data["user_id"]
    artifact_id = serializer.validated_data["artifact_id"]
    level = serializer.validated_data["level"]
    notes = serializer.validated_data.get("notes", "")
    reason = str(serializer.validated_data.get("reason") or "").strip()

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
            status=404,
        )

    try:
        artifact = Artifact.objects.get(id=artifact_id, is_deleted=False)
    except Artifact.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "ARTIFACT_NOT_FOUND", "message": "Artifact not found"}},
            status=404,
        )

    with transaction.atomic():
        obj, created = ArtifactPermission.objects.select_for_update().get_or_create(
            user=user,
            artifact=artifact,
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
            "artifact": {"id": obj.artifact.id, "name": obj.artifact.name},
            "level": _level_code(obj.level),
            "granted_by": _user_ref(obj.granted_by),
            "granted_at": obj.granted_at,
            "notes": obj.notes,
        },
    }
    log_admin_action(
        request,
        action="rbac.grant_artifact_permission",
        outcome="success",
        target_type="artifact",
        target_id=str(artifact_id),
        metadata={"reason": reason, "user_id": user_id, "level": _level_code(level), "created": created, "notes": notes},
    )
    return Response(payload)


@extend_schema(
    tags=["v2"],
    summary="Revoke artifact permission (user)",
    request=RevokeArtifactPermissionRequestSerializer,
    responses={200: RevokePermissionResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_artifact_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RevokeArtifactPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.revoke_artifact_permission",
            outcome="error",
            target_type="artifact",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    user_id = serializer.validated_data["user_id"]
    artifact_id = serializer.validated_data["artifact_id"]
    reason = str(serializer.validated_data.get("reason") or "").strip()

    deleted, _ = ArtifactPermission.objects.filter(user_id=user_id, artifact_id=artifact_id).delete()
    log_admin_action(
        request,
        action="rbac.revoke_artifact_permission",
        outcome="success",
        target_type="artifact",
        target_id=str(artifact_id),
        metadata={"reason": reason, "user_id": user_id, "deleted": deleted > 0},
    )
    return Response({"deleted": deleted > 0})


@extend_schema(
    tags=["v2"],
    summary="List artifact permissions (group)",
    parameters=[
        OpenApiParameter(name="group_id", type=int, required=False),
        OpenApiParameter(name="artifact_id", type=str, required=False),
        OpenApiParameter(name="level", type=str, required=False),
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: ArtifactGroupPermissionListResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_artifact_group_permissions(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    pagination = _parse_pagination(request)
    qs = ArtifactGroupPermission.objects.select_related("group", "artifact", "granted_by").all()

    group_id = request.query_params.get("group_id")
    if group_id:
        qs = qs.filter(group_id=group_id)

    artifact_id = request.query_params.get("artifact_id")
    if artifact_id:
        qs = qs.filter(artifact_id=artifact_id)

    level = request.query_params.get("level")
    if level:
        try:
            level_value = getattr(PermissionLevel, str(level).strip().upper())
            qs = qs.filter(level=level_value)
        except Exception:
            pass

    search = request.query_params.get("search")
    if search:
        qs = qs.filter(Q(group__name__icontains=search) | Q(artifact__name__icontains=search))

    total = qs.count()
    rows = list(qs.order_by("-granted_at")[pagination.offset: pagination.offset + pagination.limit])
    data = [
        {
            "group": _group_ref(row.group),
            "artifact": {"id": row.artifact.id, "name": row.artifact.name},
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
    summary="Grant artifact permission (group)",
    request=GrantArtifactGroupPermissionRequestSerializer,
    responses={200: ArtifactGroupPermissionUpsertResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grant_artifact_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = GrantArtifactGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.grant_artifact_group_permission",
            outcome="error",
            target_type="artifact",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    artifact_id = serializer.validated_data["artifact_id"]
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
        artifact = Artifact.objects.get(id=artifact_id, is_deleted=False)
    except Artifact.DoesNotExist:
        return Response(
            {"success": False, "error": {"code": "ARTIFACT_NOT_FOUND", "message": "Artifact not found"}},
            status=404,
        )

    with transaction.atomic():
        obj, created = ArtifactGroupPermission.objects.select_for_update().get_or_create(
            group=group,
            artifact=artifact,
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
            "group": _group_ref(obj.group),
            "artifact": {"id": obj.artifact.id, "name": obj.artifact.name},
            "level": _level_code(obj.level),
            "granted_by": _user_ref(obj.granted_by),
            "granted_at": obj.granted_at,
            "notes": obj.notes,
        },
    }
    log_admin_action(
        request,
        action="rbac.grant_artifact_group_permission",
        outcome="success",
        target_type="artifact",
        target_id=str(artifact_id),
        metadata={"reason": reason, "group_id": group_id, "level": _level_code(level), "created": created, "notes": notes},
    )
    return Response(payload)


@extend_schema(
    tags=["v2"],
    summary="Revoke artifact permission (group)",
    request=RevokeArtifactGroupPermissionRequestSerializer,
    responses={200: RevokePermissionResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_artifact_group_permission(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    serializer = RevokeArtifactGroupPermissionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        log_admin_action(
            request,
            action="rbac.revoke_artifact_group_permission",
            outcome="error",
            target_type="artifact",
            metadata={"error": "VALIDATION_ERROR"},
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(serializer.errors)}},
            status=400,
        )

    group_id = serializer.validated_data["group_id"]
    artifact_id = serializer.validated_data["artifact_id"]
    reason = str(serializer.validated_data.get("reason") or "").strip()

    deleted, _ = ArtifactGroupPermission.objects.filter(group_id=group_id, artifact_id=artifact_id).delete()
    log_admin_action(
        request,
        action="rbac.revoke_artifact_group_permission",
        outcome="success",
        target_type="artifact",
        target_id=str(artifact_id),
        metadata={"reason": reason, "group_id": group_id, "deleted": deleted > 0},
    )
    return Response({"deleted": deleted > 0})


# =============================================================================
# Audit (SPA-primary)
# =============================================================================


def _parse_dt(value: str | None):
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


@extend_schema(
    tags=["v2"],
    summary="List admin audit log entries",
    parameters=[
        OpenApiParameter(name="action", type=str, required=False),
        OpenApiParameter(name="outcome", type=str, required=False),
        OpenApiParameter(name="actor", type=str, required=False, description="Filter by actor_username (contains)"),
        OpenApiParameter(name="target_type", type=str, required=False),
        OpenApiParameter(name="target_id", type=str, required=False),
        OpenApiParameter(name="since", type=str, required=False),
        OpenApiParameter(name="until", type=str, required=False),
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: AdminAuditLogListResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_admin_audit(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    pagination = _parse_pagination(request, default_limit=100, max_limit=500)
    qs = AdminActionAuditLog.objects.select_related("actor").all()

    action = (request.query_params.get("action") or "").strip()
    if action:
        qs = qs.filter(action=action)

    outcome = (request.query_params.get("outcome") or "").strip()
    if outcome:
        qs = qs.filter(outcome=outcome)

    actor = (request.query_params.get("actor") or "").strip()
    if actor:
        qs = qs.filter(actor_username__icontains=actor)

    target_type = (request.query_params.get("target_type") or "").strip()
    if target_type:
        qs = qs.filter(target_type=target_type)

    target_id = (request.query_params.get("target_id") or "").strip()
    if target_id:
        qs = qs.filter(target_id=target_id)

    since = _parse_dt(request.query_params.get("since"))
    if since:
        qs = qs.filter(created_at__gte=since)

    until = _parse_dt(request.query_params.get("until"))
    if until:
        qs = qs.filter(created_at__lte=until)

    search = (request.query_params.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(action__icontains=search)
            | Q(actor_username__icontains=search)
            | Q(target_type__icontains=search)
            | Q(target_id__icontains=search)
        )

    total = qs.count()
    rows = list(qs.order_by("-created_at")[pagination.offset: pagination.offset + pagination.limit])

    data = [
        {
            "id": row.id,
            "created_at": row.created_at,
            "action": row.action,
            "outcome": row.outcome,
            "actor_username": row.actor_username,
            "actor_id": row.actor_id,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "metadata": row.metadata or {},
            "error_message": row.error_message or "",
        }
        for row in rows
    ]
    return Response({"items": data, "count": len(data), "total": total})
