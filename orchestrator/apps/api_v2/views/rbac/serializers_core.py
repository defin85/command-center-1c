"""RBAC serializers (core types, refs, roles, audit)."""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission, User
from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from rest_framework import serializers

from apps.core import permission_codes as perms
from apps.databases.models import Cluster, Database, PermissionLevel
from apps.templates.models import OperationTemplate
from apps.templates.workflow.models import WorkflowTemplate
from apps.artifacts.models import Artifact

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



