# ruff: noqa: F405
from __future__ import annotations

from uuid import UUID

from .common import *  # noqa: F403
from .common import _ensure_permission, _get_active_artifact, _purge_ttl_days

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
        OpenApiParameter(name="artifact_id", type=str, required=False),
        OpenApiParameter(name="kind", type=str, required=False),
        OpenApiParameter(name="name", type=str, required=False),
        OpenApiParameter(name="tag", type=str, required=False),
        OpenApiParameter(name="include_deleted", type=bool, required=False),
        OpenApiParameter(name="only_deleted", type=bool, required=False),
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
    artifact_id = (request.query_params.get("artifact_id") or "").strip()

    if artifact_id:
        try:
            queryset = queryset.filter(id=UUID(artifact_id))
        except (TypeError, ValueError):
            queryset = queryset.none()
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
