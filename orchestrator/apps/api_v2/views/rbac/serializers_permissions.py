"""RBAC serializers (permissions and bindings)."""

from __future__ import annotations

from django.contrib.auth.models import Group, User
from rest_framework import serializers

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

from .serializers_core import (
    ArtifactRefSerializer,
    ClusterGroupPermissionSerializer,
    ClusterRefSerializer,
    DatabaseGroupPermissionSerializer,
    DatabaseRefSerializer,
    OperationTemplateRefSerializer,
    PermissionLevelCodeField,
    RbacGroupRefSerializer,
    RbacUserRefSerializer,
    WorkflowTemplateRefSerializer,
)

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


class BulkUpsertResponseSerializer(serializers.Serializer):
    created = serializers.IntegerField()
    updated = serializers.IntegerField()
    skipped = serializers.IntegerField()
    total = serializers.IntegerField()


class BulkDeleteResponseSerializer(serializers.Serializer):
    deleted = serializers.IntegerField()
    skipped = serializers.IntegerField()
    total = serializers.IntegerField()


class BulkGrantClusterGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    cluster_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    level = PermissionLevelCodeField()
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField()


class BulkRevokeClusterGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    cluster_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    reason = serializers.CharField()


class BulkGrantDatabaseGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    database_ids = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    level = PermissionLevelCodeField()
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField()


class BulkRevokeDatabaseGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    database_ids = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    reason = serializers.CharField()


class BulkGrantOperationTemplateGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    template_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    level = PermissionLevelCodeField()
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField()


class BulkRevokeOperationTemplateGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    template_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    reason = serializers.CharField()


class BulkGrantWorkflowTemplateGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    template_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    level = PermissionLevelCodeField()
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField()


class BulkRevokeWorkflowTemplateGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    template_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    reason = serializers.CharField()


class BulkGrantArtifactGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    artifact_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    level = PermissionLevelCodeField()
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField()


class BulkRevokeArtifactGroupPermissionRequestSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    artifact_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
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


class RbacUserWithRolesSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    roles = RbacGroupRefSerializer(many=True)


class RbacUserWithRolesListResponseSerializer(serializers.Serializer):
    users = RbacUserWithRolesSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class GrantClusterPermissionRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    cluster_id = serializers.UUIDField()
    level = PermissionLevelCodeField()
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField()


class RevokeClusterPermissionRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    cluster_id = serializers.UUIDField()
    reason = serializers.CharField()


class GrantDatabasePermissionRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    database_id = serializers.CharField()
    level = PermissionLevelCodeField()
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField()


class RevokeDatabasePermissionRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    database_id = serializers.CharField()
    reason = serializers.CharField()


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


