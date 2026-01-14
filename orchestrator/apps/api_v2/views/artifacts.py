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

@extend_schema(
    tags=["v2"],
    summary="Create artifact",
    request=ArtifactCreateRequestSerializer,
    responses={
        201: ArtifactCreateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_artifact(request):
    denied = _ensure_permission(
        request,
        perms.PERM_ARTIFACTS_MANAGE_ARTIFACT,
        message="You do not have permission to manage artifacts.",
    )
    if denied:
        return denied

    serializer = ArtifactCreateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": serializer.errors},
            status=400,
        )

    data = serializer.validated_data
    tags = data.get("tags") or []

    try:
        artifact = Artifact.objects.create(
            name=data["name"],
            kind=data["kind"],
            is_versioned=data.get("is_versioned", True),
            tags=tags,
            created_by=request.user,
        )
    except IntegrityError:
        return Response(
            {"success": False, "error": {"code": "DUPLICATE", "message": "Artifact already exists"}},
            status=400,
        )

    response = ArtifactCreateResponseSerializer(
        {"artifact": artifact, "message": "Artifact created"}
    )
    return Response(response.data, status=201)


@extend_schema(
    tags=["v2"],
    summary="List artifacts",
    parameters=[
        OpenApiParameter(name="kind", type=str, required=False),
        OpenApiParameter(name="name", type=str, required=False),
        OpenApiParameter(name="tag", type=str, required=False),
    ],
    responses={
        200: ArtifactListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_artifacts(request):
    denied = _ensure_permission(
        request,
        perms.PERM_ARTIFACTS_VIEW_ARTIFACT,
        message="You do not have permission to view artifacts.",
    )
    if denied:
        return denied

    include_deleted = request.query_params.get("include_deleted") == "true"
    only_deleted = request.query_params.get("only_deleted") == "true"
    if only_deleted:
        queryset = Artifact.objects.filter(is_deleted=True)
    elif include_deleted:
        queryset = Artifact.objects.all()
    else:
        queryset = Artifact.objects.filter(is_deleted=False)
    kind = request.query_params.get("kind")
    name = request.query_params.get("name")
    tag = request.query_params.get("tag")

    if kind:
        queryset = queryset.filter(kind=kind)
    if name:
        queryset = queryset.filter(name__icontains=name)
    if tag:
        queryset = queryset.filter(tags__contains=[tag])

    if not request.user.is_staff:
        queryset = ArtifactPermissionService.filter_accessible_artifacts(
            request.user,
            queryset,
            min_level=PermissionLevel.VIEW,
        )

    artifacts = list(queryset.order_by("-created_at"))
    response = ArtifactListResponseSerializer({"artifacts": artifacts, "count": len(artifacts)})
    return Response(response.data)


@extend_schema(
    tags=["v2"],
    summary="Delete artifact (soft)",
    responses={
        204: OpenApiResponse(description="Deleted"),
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: ErrorResponseSerializer,
    },
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_artifact(request, artifact_id):
    artifact = _get_active_artifact(artifact_id)
    denied = _ensure_permission(
        request,
        perms.PERM_ARTIFACTS_MANAGE_ARTIFACT,
        obj=artifact,
        message="You do not have permission to manage this artifact.",
    )
    if denied:
        return denied

    artifact.is_deleted = True
    artifact.deleted_at = timezone.now()
    artifact.deleted_by = request.user
    artifact.purge_state = ArtifactPurgeState.SCHEDULED
    artifact.purge_after = artifact.deleted_at + timedelta(days=_purge_ttl_days())
    artifact.purge_blocked_until = None
    artifact.purge_blockers = []
    artifact.save(
        update_fields=[
            "is_deleted",
            "deleted_at",
            "deleted_by",
            "purge_state",
            "purge_after",
            "purge_blocked_until",
            "purge_blockers",
        ]
    )
    return Response(status=http_status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["v2"],
    summary="Restore artifact",
    request=None,
    responses={
        200: ArtifactSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: ErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def restore_artifact(request, artifact_id):
    artifact = get_object_or_404(Artifact, id=artifact_id, is_deleted=True)
    denied = _ensure_permission(
        request,
        perms.PERM_ARTIFACTS_MANAGE_ARTIFACT,
        obj=artifact,
        message="You do not have permission to manage this artifact.",
    )
    if denied:
        return denied

    if ArtifactPurgeJob.objects.filter(
        artifact_id=artifact.id,
        status__in=[ArtifactPurgeJobStatus.QUEUED, ArtifactPurgeJobStatus.RUNNING],
    ).exists():
        return Response(
            {"success": False, "error": {"code": "PURGE_ALREADY_RUNNING", "message": "Artifact purge is running"}},
            status=http_status.HTTP_409_CONFLICT,
        )

    artifact.is_deleted = False
    artifact.deleted_at = None
    artifact.deleted_by = None
    artifact.purge_state = ArtifactPurgeState.NONE
    artifact.purge_after = None
    artifact.purge_blocked_until = None
    artifact.purge_blockers = []
    artifact.save(
        update_fields=[
            "is_deleted",
            "deleted_at",
            "deleted_by",
            "purge_state",
            "purge_after",
            "purge_blocked_until",
            "purge_blockers",
        ]
    )
    response = ArtifactSerializer(artifact)
    return Response(response.data, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    summary="Upload artifact version",
    request=ArtifactVersionUploadRequestSerializer,
    responses={
        201: ArtifactVersionSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        500: ErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def upload_artifact_version(request, artifact_id):
    artifact = _get_active_artifact(artifact_id)
    denied = _ensure_permission(
        request,
        perms.PERM_ARTIFACTS_UPLOAD_ARTIFACT_VERSION,
        obj=artifact,
        message="You do not have permission to upload artifact versions.",
    )
    if denied:
        return denied

    file = request.FILES.get("file")
    if not file:
        return Response(
            {"success": False, "error": {"code": "MISSING_FILE", "message": "No file provided"}},
            status=400,
        )

    if file.size > settings.FILE_UPLOAD_MAX_SIZE:
        return Response(
            {
                "success": False,
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": "File too large",
                },
            },
            status=400,
        )

    filename = request.data.get("filename") or file.name
    filename = FileStorageService.sanitize_filename(filename)
    version = request.data.get("version")
    metadata = ArtifactService.parse_metadata(request.data.get("metadata"))

    if ArtifactVersion.objects.filter(filename=filename).exists():
        return Response(
            {
                "success": False,
                "error": {"code": "FILENAME_EXISTS", "message": "Filename already exists"},
            },
            status=400,
        )

    try:
        version_obj = ArtifactService.create_version(
            artifact=artifact,
            file_obj=file,
            filename=filename,
            version=version,
            metadata=metadata,
            content_type=getattr(file, "content_type", None),
            created_by=request.user,
        )
    except ValueError as exc:
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
            status=400,
        )
    except IntegrityError:
        return Response(
            {"success": False, "error": {"code": "DUPLICATE", "message": "Artifact version already exists"}},
            status=400,
        )
    except ArtifactStorageError as exc:
        return Response(
            {"success": False, "error": {"code": "STORAGE_ERROR", "message": str(exc)}},
            status=500,
        )

    serializer = ArtifactVersionSerializer(version_obj)
    return Response(serializer.data, status=201)


@extend_schema(
    tags=["v2"],
    summary="List artifact versions",
    responses={
        200: ArtifactVersionListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_artifact_versions(request, artifact_id):
    artifact = _get_active_artifact(artifact_id)
    denied = _ensure_permission(
        request,
        perms.PERM_ARTIFACTS_VIEW_ARTIFACT,
        obj=artifact,
        message="You do not have permission to access this artifact.",
    )
    if denied:
        return denied

    versions = list(artifact.versions.order_by("-created_at"))
    response = ArtifactVersionListResponseSerializer({"versions": versions, "count": len(versions)})
    return Response(response.data)


@extend_schema(
    tags=["v2"],
    summary="Upsert artifact alias",
    request=ArtifactAliasUpsertRequestSerializer,
    responses={
        200: ArtifactAliasSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upsert_artifact_alias(request, artifact_id):
    artifact = _get_active_artifact(artifact_id)
    denied = _ensure_permission(
        request,
        perms.PERM_ARTIFACTS_MANAGE_ARTIFACT,
        obj=artifact,
        message="You do not have permission to manage this artifact.",
    )
    if denied:
        return denied

    serializer = ArtifactAliasUpsertRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": serializer.errors},
            status=400,
        )

    data = serializer.validated_data
    version_obj = None
    if data.get("version_id"):
        version_obj = get_object_or_404(ArtifactVersion, id=data["version_id"], artifact=artifact)
    elif data.get("version"):
        version_obj = get_object_or_404(ArtifactVersion, artifact=artifact, version=data["version"])

    alias_obj, _ = ArtifactAlias.objects.update_or_create(
        artifact=artifact,
        alias=data["alias"],
        defaults={"version": version_obj},
    )

    response = ArtifactAliasSerializer(
        {
            "id": alias_obj.id,
            "alias": alias_obj.alias,
            "version": alias_obj.version.version,
            "version_id": alias_obj.version.id,
            "updated_at": alias_obj.updated_at,
        }
    )
    return Response(response.data)


@extend_schema(
    tags=["v2"],
    summary="List artifact aliases",
    responses={
        200: ArtifactAliasListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_artifact_aliases(request, artifact_id):
    artifact = _get_active_artifact(artifact_id)
    denied = _ensure_permission(
        request,
        perms.PERM_ARTIFACTS_VIEW_ARTIFACT,
        obj=artifact,
        message="You do not have permission to access this artifact.",
    )
    if denied:
        return denied

    aliases = list(artifact.aliases.select_related("version").order_by("alias"))
    response = ArtifactAliasListResponseSerializer(
        {
            "aliases": [
                {
                    "id": alias.id,
                    "alias": alias.alias,
                    "version": alias.version.version,
                    "version_id": alias.version.id,
                    "updated_at": alias.updated_at,
                }
                for alias in aliases
            ],
            "count": len(aliases),
        }
    )
    return Response(response.data)


@extend_schema(
    tags=["v2"],
    summary="Download artifact version",
    responses={
        200: OpenApiResponse(description="File download"),
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_artifact_version(request, artifact_id, version):
    artifact = _get_active_artifact(artifact_id)
    version_obj = get_object_or_404(ArtifactVersion, artifact=artifact, version=version)
    denied = _ensure_permission(
        request,
        perms.PERM_ARTIFACTS_DOWNLOAD_ARTIFACT_VERSION,
        obj=version_obj,
        message="You do not have permission to download this artifact version.",
    )
    if denied:
        return denied

    storage = ArtifactStorageClient()
    try:
        data = storage.get_object(version_obj.storage_key)
    except ArtifactStorageError as exc:
        return Response(
            {"success": False, "error": {"code": "STORAGE_ERROR", "message": str(exc)}},
            status=500,
        )

    response = FileResponse(data, as_attachment=True, filename=version_obj.filename)
    response["Content-Type"] = version_obj.content_type or "application/octet-stream"
    return response


@extend_schema(
    tags=["v2"],
    summary="Purge artifact (permanent delete)",
    request=ArtifactPurgeRequestSerializer,
    responses={
        200: ArtifactPurgeResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: ErrorResponseSerializer,
        409: ErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def purge_artifact(request, artifact_id):
    artifact = get_object_or_404(Artifact, id=artifact_id)
    denied = _ensure_permission(
        request,
        perms.PERM_ARTIFACTS_MANAGE_ARTIFACT,
        obj=artifact,
        message="You do not have permission to manage this artifact.",
    )
    if denied:
        return denied

    denied = _ensure_permission(
        request,
        perms.PERM_ARTIFACTS_PURGE_ARTIFACT,
        obj=artifact,
        message="You do not have permission to purge this artifact.",
    )
    if denied:
        return denied

    serializer = ArtifactPurgeRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=400)

    data = serializer.validated_data
    dry_run = bool(data.get("dry_run", False))
    reason = (data.get("reason") or "").strip()

    plan = _build_purge_plan(artifact)
    blockers = find_purge_blockers(artifact.id) if artifact.is_deleted else []

    if dry_run:
        response = ArtifactPurgeResponseSerializer({"job_id": None, "plan": plan, "blockers": blockers})
        return Response(response.data, status=http_status.HTTP_200_OK)

    if not artifact.is_deleted:
        return Response(
            {"success": False, "error": {"code": "PURGE_NOT_ALLOWED", "message": "Artifact must be deleted first"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    if not reason:
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "reason is required"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    if blockers:
        return Response(
            {"success": False, "error": {"code": "ARTIFACT_IN_USE", "message": "Artifact is used by active operations/workflows"}},
            status=http_status.HTTP_409_CONFLICT,
        )

    existing_job = ArtifactPurgeJob.objects.filter(
        artifact_id=artifact.id,
        status__in=[ArtifactPurgeJobStatus.QUEUED, ArtifactPurgeJobStatus.RUNNING],
    ).first()
    if existing_job:
        return Response(
            {"success": False, "error": {"code": "PURGE_ALREADY_RUNNING", "message": "Artifact purge already running"}},
            status=http_status.HTTP_409_CONFLICT,
        )

    with transaction.atomic():
        locked = Artifact.objects.select_for_update().get(id=artifact.id)
        if locked.purge_state == ArtifactPurgeState.RUNNING:
            return Response(
                {"success": False, "error": {"code": "PURGE_ALREADY_RUNNING", "message": "Artifact purge already running"}},
                status=http_status.HTTP_409_CONFLICT,
            )

        job = ArtifactPurgeJob.objects.create(
            artifact_id=locked.id,
            mode=ArtifactPurgeJobMode.MANUAL,
            status=ArtifactPurgeJobStatus.QUEUED,
            reason=reason,
            requested_by=request.user,
        )
        locked.purge_state = ArtifactPurgeState.RUNNING
        locked.purge_blocked_until = None
        locked.purge_blockers = []
        locked.save(update_fields=["purge_state", "purge_blocked_until", "purge_blockers"])

    record_artifact_purge_job_created(job.mode)

    response = ArtifactPurgeResponseSerializer({"job_id": job.id, "plan": plan, "blockers": []})
    return Response(response.data, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    summary="Get artifact purge job",
    responses={
        200: ArtifactPurgeJobSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: ErrorResponseSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_purge_job(request, job_id):
    job = get_object_or_404(ArtifactPurgeJob, id=job_id)

    artifact = Artifact.objects.filter(id=job.artifact_id).first()
    if artifact is not None:
        denied = _ensure_permission(
            request,
            perms.PERM_ARTIFACTS_MANAGE_ARTIFACT,
            obj=artifact,
            message="You do not have permission to manage this artifact.",
        )
        if denied:
            return denied
    else:
        if not request.user.is_staff and job.requested_by_id != request.user.id:
            return _permission_denied("You do not have permission to view this purge job.")

    response = ArtifactPurgeJobSerializer(job)
    return Response(response.data, status=http_status.HTTP_200_OK)
