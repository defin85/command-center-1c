from datetime import timedelta

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import IsInternalService
from .serializers import ArtifactPurgeJobClaimSerializer, ArtifactPurgeJobCompleteSerializer, ArtifactPurgeJobProgressUpdateSerializer
from .views_common import exclude_schema


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def claim_artifact_purge_job(request):
    serializer = ArtifactPurgeJobClaimSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    from apps.artifacts.models import Artifact, ArtifactPurgeJob, ArtifactPurgeJobMode, ArtifactPurgeJobStatus, ArtifactPurgeState, ArtifactVersion
    from apps.artifacts.purge_blockers import find_purge_blockers
    from apps.operations.prometheus_metrics import record_artifact_purge_job_created

    now = timezone.now()

    with transaction.atomic():
        job = (
            ArtifactPurgeJob.objects.select_for_update(skip_locked=True)
            .filter(status=ArtifactPurgeJobStatus.QUEUED)
            .order_by("created_at")
            .first()
        )

        storage_keys: list[str] = []

        if job is None:
            candidate = None
            for _ in range(20):
                candidate = (
                    Artifact.objects.select_for_update(skip_locked=True)
                    .filter(
                        is_deleted=True,
                        purge_after__lte=now,
                        purge_state__in=[
                            ArtifactPurgeState.SCHEDULED,
                            ArtifactPurgeState.FAILED,
                            ArtifactPurgeState.BLOCKED,
                        ],
                    )
                    .order_by("purge_after", "created_at")
                    .first()
                )
                if candidate is None:
                    break

                if candidate.purge_blocked_until and candidate.purge_blocked_until > now:
                    candidate = None
                    continue

                blockers = find_purge_blockers(candidate.id, limit=20)
                if blockers:
                    candidate.purge_state = ArtifactPurgeState.BLOCKED
                    candidate.purge_blocked_until = now + timedelta(days=1)
                    candidate.purge_blockers = blockers
                    candidate.save(update_fields=["purge_state", "purge_blocked_until", "purge_blockers"])
                    candidate = None
                    continue

                break

            if candidate is None:
                return Response({"success": True, "job": None}, status=status.HTTP_200_OK)

            try:
                job = ArtifactPurgeJob.objects.create(
                    artifact_id=candidate.id,
                    mode=ArtifactPurgeJobMode.TTL,
                    status=ArtifactPurgeJobStatus.QUEUED,
                    reason="ttl_auto_purge",
                )
            except IntegrityError:
                return Response({"success": True, "job": None}, status=status.HTTP_200_OK)

            record_artifact_purge_job_created(ArtifactPurgeJobMode.TTL)

            candidate.purge_state = ArtifactPurgeState.RUNNING
            candidate.purge_blocked_until = None
            candidate.purge_blockers = []
            candidate.save(update_fields=["purge_state", "purge_blocked_until", "purge_blockers"])

        job.status = ArtifactPurgeJobStatus.RUNNING
        if job.started_at is None:
            job.started_at = now

        versions = list(ArtifactVersion.objects.filter(artifact_id=job.artifact_id).values_list("storage_key", "size"))
        storage_keys = [key for key, _ in versions]
        total_bytes = sum(int(size) for _, size in versions)

        job.total_objects = len(storage_keys)
        job.total_bytes = total_bytes
        job.save(update_fields=["status", "started_at", "total_objects", "total_bytes"])

        Artifact.objects.filter(id=job.artifact_id).update(purge_state=ArtifactPurgeState.RUNNING)

    return Response(
        {
            "success": True,
            "job": {
                "job_id": str(job.id),
                "artifact_id": str(job.artifact_id),
                "mode": job.mode,
                "status": job.status,
                "prefix": f"artifacts/{job.artifact_id}/",
                "storage_keys": storage_keys,
                "total_objects": job.total_objects,
                "total_bytes": job.total_bytes,
            },
        },
        status=status.HTTP_200_OK,
    )


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def update_artifact_purge_job(request):
    job_id = request.query_params.get("job_id")
    if not job_id:
        return Response({"success": False, "error": {"job_id": "job_id is required"}}, status=status.HTTP_400_BAD_REQUEST)

    serializer = ArtifactPurgeJobProgressUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    from apps.artifacts.models import ArtifactPurgeJob

    job = get_object_or_404(ArtifactPurgeJob, id=job_id)
    data = serializer.validated_data

    job.deleted_objects = data.get("deleted_objects", job.deleted_objects)
    job.deleted_bytes = data.get("deleted_bytes", job.deleted_bytes)
    job.save(update_fields=["deleted_objects", "deleted_bytes"])

    return Response({"success": True}, status=status.HTTP_200_OK)


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def complete_artifact_purge_job(request):
    job_id = request.query_params.get("job_id")
    if not job_id:
        return Response({"success": False, "error": {"job_id": "job_id is required"}}, status=status.HTTP_400_BAD_REQUEST)

    serializer = ArtifactPurgeJobCompleteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    from apps.artifacts.models import Artifact, ArtifactPurgeJob, ArtifactPurgeJobStatus, ArtifactPurgeState
    from apps.operations.prometheus_metrics import record_artifact_purge_job_completed
    from apps.operations.services.admin_action_audit import log_admin_action

    now = timezone.now()
    data = serializer.validated_data

    with transaction.atomic():
        job = ArtifactPurgeJob.objects.select_for_update().filter(id=job_id).first()
        if job is None:
            return Response({"success": False, "error": "job not found"}, status=status.HTTP_404_NOT_FOUND)

        if job.status not in [ArtifactPurgeJobStatus.QUEUED, ArtifactPurgeJobStatus.RUNNING]:
            return Response({"success": False, "error": "job already completed"}, status=status.HTTP_409_CONFLICT)

        job.completed_at = now
        job.deleted_objects = data.get("deleted_objects", job.deleted_objects)
        job.deleted_bytes = data.get("deleted_bytes", job.deleted_bytes)

        if data["status"] == "success":
            job.status = ArtifactPurgeJobStatus.SUCCESS
            job.error_code = ""
            job.error_message = ""
            job.save(update_fields=["status", "completed_at", "deleted_objects", "deleted_bytes", "error_code", "error_message"])

            started_at = job.started_at or job.created_at
            duration_seconds = (now - started_at).total_seconds() if started_at else 0.0
            record_artifact_purge_job_completed(
                job.mode,
                "success",
                deleted_objects=job.deleted_objects,
                deleted_bytes=int(job.deleted_bytes),
                duration_seconds=duration_seconds,
            )
            log_admin_action(
                None,
                action=f"artifact.purge.{job.mode}",
                outcome="success",
                target_type="artifact",
                target_id=str(job.artifact_id),
                metadata={
                    "job_id": str(job.id),
                    "mode": job.mode,
                    "reason": job.reason,
                    "deleted_objects": job.deleted_objects,
                    "deleted_bytes": int(job.deleted_bytes),
                    "duration_seconds": duration_seconds,
                },
                actor=job.requested_by,
            )

            Artifact.objects.filter(id=job.artifact_id).delete()
            return Response({"success": True}, status=status.HTTP_200_OK)

        job.status = ArtifactPurgeJobStatus.FAILED
        job.error_code = (data.get("error_code") or "").strip()
        job.error_message = (data.get("error_message") or "").strip()
        job.save(update_fields=["status", "completed_at", "deleted_objects", "deleted_bytes", "error_code", "error_message"])

        started_at = job.started_at or job.created_at
        duration_seconds = (now - started_at).total_seconds() if started_at else 0.0
        record_artifact_purge_job_completed(
            job.mode,
            "failed",
            deleted_objects=job.deleted_objects,
            deleted_bytes=int(job.deleted_bytes),
            duration_seconds=duration_seconds,
        )
        log_admin_action(
            None,
            action=f"artifact.purge.{job.mode}",
            outcome="error",
            target_type="artifact",
            target_id=str(job.artifact_id),
            metadata={
                "job_id": str(job.id),
                "mode": job.mode,
                "reason": job.reason,
                "deleted_objects": job.deleted_objects,
                "deleted_bytes": int(job.deleted_bytes),
                "duration_seconds": duration_seconds,
                "error_code": job.error_code,
            },
            error_message=job.error_code or job.error_message or "PURGE_FAILED",
            actor=job.requested_by,
        )

        Artifact.objects.filter(id=job.artifact_id).update(purge_state=ArtifactPurgeState.FAILED)

    return Response({"success": True}, status=status.HTTP_200_OK)

