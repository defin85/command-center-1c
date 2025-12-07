"""
Internal API views for Go Worker communication.

These endpoints are for service-to-service calls only.
All endpoints require X-Internal-Token authentication.
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

from .permissions import IsInternalService
from .serializers import (
    SchedulerRunStartSerializer,
    SchedulerRunCompleteSerializer,
    TaskStartSerializer,
    TaskCompleteSerializer,
    DatabaseCredentialsSerializer,
    HealthUpdateSerializer,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Scheduler Job History Endpoints
# =============================================================================

@api_view(['POST'])
@permission_classes([IsInternalService])
def scheduler_run_start(request):
    """
    POST /api/internal/scheduler/runs/start

    Start a new scheduler job run.
    Called by Go Worker when a scheduled job begins execution.

    Request body:
    {
        "job_name": "health_check_databases",
        "worker_instance": "worker-1"
    }

    Response:
    {
        "id": 123
    }
    """
    serializer = SchedulerRunStartSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    # TODO: Implement when SchedulerJobRun model is created
    # from apps.scheduler.models import SchedulerJobRun
    #
    # run = SchedulerJobRun.objects.create(
    #     job_name=data['job_name'],
    #     worker_instance=data['worker_instance'],
    #     started_at=timezone.now(),
    #     status='running',
    # )

    logger.info(
        f"Scheduler run started: job={data['job_name']}, "
        f"worker={data['worker_instance']}"
    )

    # Return stub ID until model is implemented
    # TODO: Return actual run.id
    return Response({'id': 0}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsInternalService])
def scheduler_run_complete(request, run_id):
    """
    POST /api/internal/scheduler/runs/{id}/complete

    Complete a scheduler job run.
    Called by Go Worker when a scheduled job finishes execution.

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
        "status": "ok"
    }
    """
    serializer = SchedulerRunCompleteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    # TODO: Implement when SchedulerJobRun model is created
    # from apps.scheduler.models import SchedulerJobRun
    #
    # try:
    #     run = SchedulerJobRun.objects.get(id=run_id)
    # except SchedulerJobRun.DoesNotExist:
    #     return Response(
    #         {'error': f'SchedulerJobRun {run_id} not found'},
    #         status=status.HTTP_404_NOT_FOUND
    #     )
    #
    # run.status = data['status']
    # run.duration_ms = data['duration_ms']
    # run.result_summary = data.get('result_summary', '')
    # run.error_message = data.get('error_message', '')
    # run.items_processed = data.get('items_processed', 0)
    # run.items_failed = data.get('items_failed', 0)
    # run.completed_at = timezone.now()
    # run.save()

    logger.info(
        f"Scheduler run completed: id={run_id}, status={data['status']}, "
        f"duration={data['duration_ms']}ms"
    )

    return Response({'status': 'ok'}, status=status.HTTP_200_OK)


# =============================================================================
# Task Execution Log Endpoints
# =============================================================================

@api_view(['POST'])
@permission_classes([IsInternalService])
def task_start(request):
    """
    POST /api/internal/tasks/start

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
        "id": 123
    }
    """
    serializer = TaskStartSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    # TODO: Implement when TaskExecutionLog model is created
    # from apps.scheduler.models import TaskExecutionLog
    #
    # log = TaskExecutionLog.objects.create(
    #     task_id=data['task_id'],
    #     task_type=data['task_type'],
    #     queue_name=data['queue_name'],
    #     worker_instance=data['worker_instance'],
    #     operation_id=data.get('operation_id'),
    #     started_at=timezone.now(),
    #     status='running',
    # )

    logger.info(
        f"Task started: task_id={data['task_id']}, type={data['task_type']}, "
        f"worker={data['worker_instance']}"
    )

    # Return stub ID until model is implemented
    # TODO: Return actual log.id
    return Response({'id': 0}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsInternalService])
def task_complete(request, log_id):
    """
    POST /api/internal/tasks/{id}/complete

    Log task execution completion.
    Called by Go Worker when a task finishes processing.

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
        "status": "ok"
    }
    """
    serializer = TaskCompleteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    # TODO: Implement when TaskExecutionLog model is created
    # from apps.scheduler.models import TaskExecutionLog
    #
    # try:
    #     log = TaskExecutionLog.objects.get(id=log_id)
    # except TaskExecutionLog.DoesNotExist:
    #     return Response(
    #         {'error': f'TaskExecutionLog {log_id} not found'},
    #         status=status.HTTP_404_NOT_FOUND
    #     )
    #
    # log.status = data['status']
    # log.duration_ms = data['duration_ms']
    # log.result_summary = data.get('result_summary', '')
    # log.error_message = data.get('error_message', '')
    # log.error_type = data.get('error_type', '')
    # log.retry_count = data.get('retry_count', 0)
    # log.completed_at = timezone.now()
    # log.save()

    logger.info(
        f"Task completed: id={log_id}, status={data['status']}, "
        f"duration={data['duration_ms']}ms"
    )

    return Response({'status': 'ok'}, status=status.HTTP_200_OK)


# =============================================================================
# Database Credentials Endpoint
# =============================================================================

@api_view(['GET'])
@permission_classes([IsInternalService])
def database_credentials(request, database_id):
    """
    GET /api/internal/databases/{id}/credentials

    Get database credentials for OData access.
    Called by Go Worker to fetch credentials for batch operations.

    Response:
    {
        "odata_url": "http://localhost:8080/base/odata/standard.odata",
        "username": "admin",
        "password": "secret",
        "cluster_id": "550e8400-e29b-41d4-a716-446655440000"
    }
    """
    from apps.databases.models import Database

    try:
        database = Database.objects.get(id=database_id)
    except Database.DoesNotExist:
        return Response(
            {'error': f'Database {database_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Return minimal credentials data
    data = {
        'odata_url': database.odata_url,
        'username': database.username,
        'password': database.password,  # EncryptedCharField auto-decrypts
        'cluster_id': database.cluster_id if database.cluster else None,
    }

    serializer = DatabaseCredentialsSerializer(data=data)
    serializer.is_valid()

    logger.debug(f"Credentials fetched for database: {database_id}")

    return Response(serializer.data, status=status.HTTP_200_OK)


# =============================================================================
# Health Status Update Endpoints
# =============================================================================

@api_view(['POST'])
@permission_classes([IsInternalService])
def database_health_update(request, database_id):
    """
    POST /api/internal/databases/{id}/health

    Update database health status.
    Called by Go Worker after health check execution.

    Request body:
    {
        "healthy": true,
        "error_message": "",
        "last_check_at": "2025-01-01T12:00:00Z"  // optional
    }

    Response:
    {
        "status": "ok"
    }
    """
    from apps.databases.models import Database

    serializer = HealthUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    try:
        database = Database.objects.get(id=database_id)
    except Database.DoesNotExist:
        return Response(
            {'error': f'Database {database_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Use existing mark_health_check method
    database.mark_health_check(
        success=data['healthy'],
        response_time=None  # Go Worker can extend to pass response_time
    )

    # If error_message provided and not healthy, store it in metadata
    if not data['healthy'] and data.get('error_message'):
        database.metadata['last_health_error'] = data['error_message']
        database.save(update_fields=['metadata', 'updated_at'])

    logger.info(
        f"Database health updated: id={database_id}, healthy={data['healthy']}"
    )

    return Response({'status': 'ok'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsInternalService])
def cluster_health_update(request, cluster_id):
    """
    POST /api/internal/clusters/{id}/health

    Update cluster health status.
    Called by Go Worker after health check execution.

    Request body:
    {
        "healthy": true,
        "error_message": "",
        "last_check_at": "2025-01-01T12:00:00Z"  // optional
    }

    Response:
    {
        "status": "ok"
    }
    """
    from apps.databases.models import Cluster

    serializer = HealthUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    try:
        cluster = Cluster.objects.get(id=cluster_id)
    except Cluster.DoesNotExist:
        return Response(
            {'error': f'Cluster {cluster_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Use existing mark_health_check method
    cluster.mark_health_check(
        success=data['healthy'],
        error_message=data.get('error_message') if not data['healthy'] else None
    )

    logger.info(
        f"Cluster health updated: id={cluster_id}, healthy={data['healthy']}"
    )

    return Response({'status': 'ok'}, status=status.HTTP_200_OK)
