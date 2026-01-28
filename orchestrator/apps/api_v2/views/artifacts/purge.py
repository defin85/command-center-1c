from __future__ import annotations

from .common import *  # noqa: F403
from .common import _build_purge_plan, _ensure_permission, _permission_denied

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
