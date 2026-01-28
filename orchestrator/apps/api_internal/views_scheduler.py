from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import IsInternalService
from .serializers import SchedulerRunCompleteSerializer, SchedulerRunStartSerializer
from .views_common import exclude_schema, logger


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def start_scheduler_run(request):
    """
    POST /api/v2/internal/start-scheduler-run

    Start a new scheduler job run.
    Called by Go Worker when a scheduled job begins execution.

    Request body:
    {
        "job_name": "health_check_databases",
        "worker_instance": "worker-1"
    }

    Response:
    {
        "run_id": 123,
        "status": "running"
    }
    """
    serializer = SchedulerRunStartSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    from apps.operations.models import SchedulerJobRun

    run = SchedulerJobRun.objects.create(
        job_name=data["job_name"],
        worker_instance=data["worker_instance"],
        status=SchedulerJobRun.STATUS_RUNNING,
        started_at=timezone.now(),
        job_config=data.get("job_config") or {},
    )

    logger.info(f"Scheduler run started: job={data['job_name']}, " f"worker={data['worker_instance']}")

    return Response(
        {
            "success": True,
            "run_id": run.id,
            "status": "running",
        },
        status=status.HTTP_201_CREATED,
    )


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def complete_scheduler_run(request):
    """
    POST /api/v2/internal/complete-scheduler-run?run_id=X

    Complete a scheduler job run.
    Called by Go Worker when a scheduled job finishes execution.

    Query params:
        run_id: int (required)

    Request body:
    {
        "status": "success",
        "duration_ms": 1234,
        "result_summary": "Processed 10 items",
        "error_message": "",
        "items_processed": 10,
        "items_failed": 0
    }

    Response:
    {
        "success": true,
        "run_id": 123,
        "status": "success"
    }
    """
    run_id = request.query_params.get("run_id")
    if not run_id:
        return Response(
            {"success": False, "error": {"run_id": "This query parameter is required"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        run_id = int(run_id)
    except ValueError:
        return Response(
            {"success": False, "error": {"run_id": "Must be an integer"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = SchedulerRunCompleteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    from apps.operations.models import SchedulerJobRun

    try:
        run = SchedulerJobRun.objects.get(id=run_id)
    except SchedulerJobRun.DoesNotExist:
        return Response(
            {"success": False, "error": f"Scheduler run {run_id} not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    run.status = data["status"]
    run.finished_at = timezone.now()
    run.duration_ms = data.get("duration_ms", 0)
    run.result_summary = data.get("result_summary", "")
    run.error_message = data.get("error_message", "")
    run.items_processed = data.get("items_processed", 0)
    run.items_failed = data.get("items_failed", 0)
    run.save(
        update_fields=[
            "status",
            "finished_at",
            "duration_ms",
            "result_summary",
            "error_message",
            "items_processed",
            "items_failed",
        ],
    )

    logger.info(f"Scheduler run completed: id={run_id}, status={data['status']}, " f"duration={data['duration_ms']}ms")

    return Response(
        {"success": True, "run_id": run_id, "status": data["status"]},
        status=status.HTTP_200_OK,
    )

