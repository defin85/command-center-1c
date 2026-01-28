"""RBAC serializers (effective access)."""

from __future__ import annotations

from rest_framework import serializers

from .serializers_core import (
    ArtifactRefSerializer,
    ClusterRefSerializer,
    DatabaseRefSerializer,
    OperationTemplateRefSerializer,
    PermissionLevelCodeField,
    RbacUserRefSerializer,
    WorkflowTemplateRefSerializer,
)

class EffectiveAccessClusterSourceItemSerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=["direct", "group", "database"])
    level = PermissionLevelCodeField()


class EffectiveAccessClusterItemSerializer(serializers.Serializer):
    cluster = ClusterRefSerializer()
    level = PermissionLevelCodeField()
    sources = EffectiveAccessClusterSourceItemSerializer(many=True, required=False)


class EffectiveAccessDatabaseSourceItemSerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=["direct", "group", "cluster"])
    level = PermissionLevelCodeField()
    via_cluster_id = serializers.UUIDField(required=False, allow_null=True)


class EffectiveAccessDatabaseItemSerializer(serializers.Serializer):
    database = DatabaseRefSerializer()
    level = PermissionLevelCodeField()
    source = serializers.ChoiceField(choices=["direct", "group", "cluster"])
    via_cluster_id = serializers.UUIDField(required=False, allow_null=True)
    sources = EffectiveAccessDatabaseSourceItemSerializer(many=True, required=False)


class EffectiveAccessOperationTemplateSourceItemSerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=["direct", "group"])
    level = PermissionLevelCodeField()


class EffectiveAccessOperationTemplateItemSerializer(serializers.Serializer):
    template = OperationTemplateRefSerializer()
    level = PermissionLevelCodeField()
    source = serializers.ChoiceField(choices=["direct", "group"])
    sources = EffectiveAccessOperationTemplateSourceItemSerializer(many=True, required=False)


class EffectiveAccessWorkflowTemplateSourceItemSerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=["direct", "group"])
    level = PermissionLevelCodeField()


class EffectiveAccessWorkflowTemplateItemSerializer(serializers.Serializer):
    template = WorkflowTemplateRefSerializer()
    level = PermissionLevelCodeField()
    source = serializers.ChoiceField(choices=["direct", "group"])
    sources = EffectiveAccessWorkflowTemplateSourceItemSerializer(many=True, required=False)


class EffectiveAccessArtifactSourceItemSerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=["direct", "group"])
    level = PermissionLevelCodeField()


class EffectiveAccessArtifactItemSerializer(serializers.Serializer):
    artifact = ArtifactRefSerializer()
    level = PermissionLevelCodeField()
    source = serializers.ChoiceField(choices=["direct", "group"])
    sources = EffectiveAccessArtifactSourceItemSerializer(many=True, required=False)


class EffectiveAccessResponseSerializer(serializers.Serializer):
    user = RbacUserRefSerializer()
    clusters = EffectiveAccessClusterItemSerializer(many=True)
    databases = EffectiveAccessDatabaseItemSerializer(many=True)
    databases_count = serializers.IntegerField(required=False)
    databases_total = serializers.IntegerField(required=False)
    databases_limit = serializers.IntegerField(required=False)
    databases_offset = serializers.IntegerField(required=False)
    operation_templates = EffectiveAccessOperationTemplateItemSerializer(many=True, required=False)
    workflow_templates = EffectiveAccessWorkflowTemplateItemSerializer(many=True, required=False)
    artifacts = EffectiveAccessArtifactItemSerializer(many=True, required=False)



