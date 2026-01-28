"""
Artifact storage endpoints (v2).

Provides artifact registry with versions and aliases backed by MinIO + Postgres.
"""

import logging
import json
from datetime import timedelta

from django.conf import settings
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.api_v2.serializers.common import ErrorResponseSerializer
from apps.core import permission_codes as perms
from apps.artifacts.models import (
    Artifact,
    ArtifactAlias,
    ArtifactKind,
    ArtifactPurgeJob,
    ArtifactPurgeJobMode,
    ArtifactPurgeJobStatus,
    ArtifactPurgeState,
    ArtifactVersion,
)
from apps.artifacts.rbac import ArtifactPermissionService
from apps.artifacts.services import ArtifactService
from apps.artifacts.storage import ArtifactStorageClient, ArtifactStorageError
from apps.artifacts.purge_blockers import find_purge_blockers
from apps.databases.models import PermissionLevel
from apps.files.services import FileStorageService
from apps.operations.prometheus_metrics import record_artifact_purge_job_created


logger = logging.getLogger(__name__)


# =============================================================================
# Serializers
# =============================================================================

class ArtifactPurgeBlockerSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["batch_operation", "workflow_execution"])
    id = serializers.CharField()
    status = serializers.CharField()
    name = serializers.CharField(required=False, allow_blank=True, default="")
    details = serializers.CharField(required=False, allow_blank=True, default="")


class ArtifactSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    kind = serializers.CharField()
    is_versioned = serializers.BooleanField()
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    is_deleted = serializers.BooleanField()
    deleted_at = serializers.DateTimeField(allow_null=True, required=False)
    purge_state = serializers.CharField()
    purge_after = serializers.DateTimeField(allow_null=True, required=False)
    purge_blocked_until = serializers.DateTimeField(allow_null=True, required=False)
    purge_blockers = ArtifactPurgeBlockerSerializer(many=True, required=False)
    created_at = serializers.DateTimeField()


class ArtifactListResponseSerializer(serializers.Serializer):
    artifacts = ArtifactSerializer(many=True)
    count = serializers.IntegerField()


class ArtifactCreateRequestSerializer(serializers.Serializer):
    name = serializers.CharField()
    kind = serializers.ChoiceField(choices=ArtifactKind.choices)
    is_versioned = serializers.BooleanField(required=False, default=True)
    tags = serializers.ListField(child=serializers.CharField(), required=False)


class ArtifactCreateResponseSerializer(serializers.Serializer):
    artifact = ArtifactSerializer()
    message = serializers.CharField()


class ArtifactVersionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    version = serializers.CharField()
    filename = serializers.CharField()
    storage_key = serializers.CharField()
    size = serializers.IntegerField()
    checksum = serializers.CharField()
    content_type = serializers.CharField()
    metadata = serializers.DictField()
    created_at = serializers.DateTimeField()


class ArtifactVersionUploadRequestSerializer(serializers.Serializer):
    file = serializers.FileField()
    version = serializers.CharField(required=False, allow_blank=True)
    filename = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.CharField(required=False, allow_blank=True)


class ArtifactVersionListResponseSerializer(serializers.Serializer):
    versions = ArtifactVersionSerializer(many=True)
    count = serializers.IntegerField()


class ArtifactAliasSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    alias = serializers.CharField()
    version = serializers.CharField()
    version_id = serializers.UUIDField()
    updated_at = serializers.DateTimeField()


class ArtifactAliasListResponseSerializer(serializers.Serializer):
    aliases = ArtifactAliasSerializer(many=True)
    count = serializers.IntegerField()


class ArtifactAliasUpsertRequestSerializer(serializers.Serializer):
    alias = serializers.CharField()
    version = serializers.CharField(required=False)
    version_id = serializers.UUIDField(required=False)

    def validate(self, attrs):
        if not attrs.get("version") and not attrs.get("version_id"):
            raise serializers.ValidationError("version or version_id is required")
        return attrs


class ArtifactPurgeRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    dry_run = serializers.BooleanField(required=False, default=False)

class ArtifactPurgePlanSerializer(serializers.Serializer):
    artifact_id = serializers.UUIDField()
    versions_count = serializers.IntegerField()
    aliases_count = serializers.IntegerField()
    total_bytes = serializers.IntegerField()
    storage_keys = serializers.ListField(child=serializers.CharField())
    storage_keys_total = serializers.IntegerField()
    prefix = serializers.CharField()


class ArtifactPurgeResponseSerializer(serializers.Serializer):
    job_id = serializers.UUIDField(allow_null=True, required=False)
    plan = ArtifactPurgePlanSerializer()
    blockers = ArtifactPurgeBlockerSerializer(many=True)


class ArtifactPurgeJobSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    artifact_id = serializers.UUIDField()
    mode = serializers.CharField()
    status = serializers.CharField()
    reason = serializers.CharField(allow_blank=True, required=False)
    created_at = serializers.DateTimeField()
    started_at = serializers.DateTimeField(allow_null=True, required=False)
    completed_at = serializers.DateTimeField(allow_null=True, required=False)
    total_objects = serializers.IntegerField()
    deleted_objects = serializers.IntegerField()
    total_bytes = serializers.IntegerField()
    deleted_bytes = serializers.IntegerField()
    error_code = serializers.CharField(allow_blank=True, required=False)
    error_message = serializers.CharField(allow_blank=True, required=False)


# =============================================================================
# Permissions
# =============================================================================

def _permission_denied(message: str):
    return Response(
        {"success": False, "error": {"code": "PERMISSION_DENIED", "message": message}},
        status=http_status.HTTP_403_FORBIDDEN,
    )


def _ensure_permission(request, perm: str, obj=None, message: str = "Forbidden"):
    if request.user.has_perm(perm, obj):
        return None
    return _permission_denied(message)


def _get_active_artifact(artifact_id):
    return get_object_or_404(Artifact, id=artifact_id, is_deleted=False)


def _purge_ttl_days() -> int:
    value = getattr(settings, "ARTIFACT_PURGE_TTL_DAYS", 30)
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 30
    return max(1, value)


def _build_purge_plan(artifact: Artifact, keys_limit: int = 200) -> dict:
    versions_qs = ArtifactVersion.objects.filter(artifact=artifact).order_by("created_at")
    storage_keys_total = versions_qs.count()
    storage_keys = list(versions_qs.values_list("storage_key", flat=True)[:keys_limit])
    total_bytes = versions_qs.aggregate(total=Sum("size")).get("total") or 0
    aliases_count = ArtifactAlias.objects.filter(artifact=artifact).count()
    return {
        "artifact_id": artifact.id,
        "versions_count": storage_keys_total,
        "aliases_count": aliases_count,
        "total_bytes": int(total_bytes),
        "storage_keys": storage_keys,
        "storage_keys_total": storage_keys_total,
        "prefix": f"artifacts/{artifact.id}/",
    }


# =============================================================================
# Endpoints
# =============================================================================


