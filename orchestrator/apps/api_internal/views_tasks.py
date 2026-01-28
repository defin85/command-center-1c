from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import IsInternalService
from .serializers import TaskExecutionCompleteSerializer, TaskExecutionStartSerializer
from .views_common import exclude_schema, logger


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def start_task(request):
    """
    POST /api/v2/internal/start-task

    Log task execution start.
    Called by Go Worker when a task begins processing.

    Request body:
    {
        "task_id": "task-123",
        "task_type": "health_check",
        "queue_name": "default",
        "worker_instance": "worker-1",
        "operation_id": "op-456"  // optional
    }

    Response:
    {
        "task_id": 123,
        "status": "running"
    }
    """
    serializer = TaskExecutionStartSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    from apps.operations.models import BatchOperation, TaskExecutionLog

    try:
        operation = BatchOperation.objects.get(id=data["operation_id"])
    except BatchOperation.DoesNotExist:
        return Response(
            {"success": False, "error": f"Batch operation {data['operation_id']} not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    log = TaskExecutionLog.objects.create(
        operation=operation,
        task_type=data["task_type"],
        queue_name="internal",
        worker_instance=data.get("worker_instance") or "worker",
        status=TaskExecutionLog.STATUS_RUNNING,
        started_at=timezone.now(),
        input_summary={
            "target_id": data["target_id"],
            "target_type": data.get("target_type") or "",
            "parameters": data.get("parameters") or {},
        },
    )

    logger.info(
        "Task started",
        extra={
            "task_id": log.id,
            "task_type": data["task_type"],
            "operation_id": data["operation_id"],
        },
    )

    return Response({"success": True, "task_id": log.id, "status": "running"}, status=status.HTTP_201_CREATED)


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def complete_task(request):
    """
    POST /api/v2/internal/complete-task?task_id=X

    Log task execution completion.
    Called by Go Worker when a task finishes processing.

    Query params:
        task_id: int (required)

    Request body:
    {
        "status": "success",
        "duration_ms": 1234,
        "result_summary": "OK",
        "error_message": "",
        "error_type": "",
        "retry_count": 0
    }

    Response:
    {
        "success": true,
        "task_id": 123,
        "status": "success"
    }
    """
    task_id = request.query_params.get("task_id")
    if not task_id:
        return Response(
            {"success": False, "error": {"task_id": "This query parameter is required"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        task_id = int(task_id)
    except ValueError:
        return Response(
            {"success": False, "error": {"task_id": "Must be an integer"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = TaskExecutionCompleteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    from apps.operations.models import TaskExecutionLog

    try:
        log = TaskExecutionLog.objects.get(id=task_id)
    except TaskExecutionLog.DoesNotExist:
        return Response({"success": False, "error": f"Task {task_id} not found"}, status=status.HTTP_404_NOT_FOUND)

    log.status = data["status"]
    log.finished_at = timezone.now()
    log.duration_ms = data.get("duration_ms", 0)
    log.result_summary = data.get("result") or {}
    log.error_message = data.get("error_message", "")
    log.error_type = data.get("error_code", "")
    log.retry_count = data.get("retry_count", 0)
    log.save(
        update_fields=[
            "status",
            "finished_at",
            "duration_ms",
            "result_summary",
            "error_message",
            "error_type",
            "retry_count",
        ],
    )

    logger.info(f"Task completed: id={task_id}, status={data['status']}, " f"duration={data.get('duration_ms', 0)}ms")

    return Response({"success": True, "task_id": task_id, "status": data["status"]}, status=status.HTTP_200_OK)

