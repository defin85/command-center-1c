"""
Internal API views for Go Worker communication.

These endpoints are for service-to-service calls only.
All endpoints require X-Internal-Token authentication.
"""

import logging
from django.db import models, transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .permissions import IsInternalService
from .serializers import (
    SchedulerRunStartSerializer,
    SchedulerRunCompleteSerializer,
    TaskStartSerializer,
    TaskCompleteSerializer,
    DatabaseCredentialsSerializer,
    HealthUpdateSerializer,
    FailedEventSerializer,
    FailedEventReplayedSerializer,
    FailedEventFailedSerializer,
    FailedEventsCleanupSerializer,
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
        "last_check_at": "2025-01-01T12:00:00Z",  // optional
        "response_time_ms": 250,  // optional
        "error_code": ""  // optional
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
        response_time=data.get('response_time_ms')
    )

    # Store additional error metadata if provided
    if not data['healthy']:
        metadata_updated = False
        if data.get('error_message'):
            database.metadata['last_health_error'] = data['error_message']
            metadata_updated = True
        if data.get('error_code'):
            database.metadata['last_health_error_code'] = data['error_code']
            metadata_updated = True

        if metadata_updated:
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


# =============================================================================
# Database List for Health Checks
# =============================================================================

class DatabasesForHealthCheckView(APIView):
    """
    GET /api/internal/databases/health-check-list

    Get list of databases for periodic health checks.
    Called by Go Worker to fetch databases that need health monitoring.

    Response:
    {
        "databases": [
            {
                "id": "db-123",
                "odata_url": "http://localhost:8080/base/odata/standard.odata",
                "name": "Production DB"
            }
        ],
        "count": 1
    }
    """
    permission_classes = [IsInternalService]

    def get(self, request):
        from apps.databases.models import Database

        # Get active databases with OData URL
        databases = Database.objects.filter(
            status=Database.STATUS_ACTIVE,
            odata_url__isnull=False
        ).exclude(odata_url='').values('id', 'odata_url', 'name')

        database_list = list(databases)

        logger.debug(f"Fetched {len(database_list)} databases for health check")

        return Response({
            'databases': database_list,
            'count': len(database_list)
        }, status=status.HTTP_200_OK)


# =============================================================================
# Failed Event Endpoints (Event Replay System)
# =============================================================================

@api_view(['GET'])
@permission_classes([IsInternalService])
def failed_events_pending(request):
    """
    GET /api/internal/failed-events/pending

    Get pending failed events for replay.
    Called by Go Worker to fetch events that need to be replayed to Redis.

    Query params:
        batch_size: int (default: 100, max: 1000)

    Response:
    {
        "events": [...],
        "count": 10
    }
    """
    from apps.operations.models import FailedEvent

    # Parse batch_size from query params
    try:
        batch_size = int(request.query_params.get('batch_size', 100))
        batch_size = min(max(batch_size, 1), 1000)  # Clamp to 1-1000
    except (ValueError, TypeError):
        batch_size = 100

    # Get pending events that haven't exceeded max retries
    events = FailedEvent.objects.filter(
        status=FailedEvent.STATUS_PENDING
    ).filter(
        retry_count__lt=models.F('max_retries')
    ).order_by('created_at')[:batch_size]

    serializer = FailedEventSerializer(events, many=True)

    logger.debug(f"Fetched {len(serializer.data)} pending failed events")

    return Response({
        'events': serializer.data,
        'count': len(serializer.data)
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsInternalService])
def failed_event_replayed(request, event_id):
    """
    POST /api/internal/failed-events/{id}/replayed

    Mark event as successfully replayed.
    Called by Go Worker after successfully publishing event to Redis.

    Request body:
    {
        "replayed_at": "2025-01-01T12:00:00Z"  // optional, defaults to now
    }

    Response:
    {
        "success": true
    }
    """
    from django.utils import timezone
    from apps.operations.models import FailedEvent

    serializer = FailedEventReplayedSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        event = FailedEvent.objects.get(id=event_id)
    except FailedEvent.DoesNotExist:
        return Response(
            {'error': f'FailedEvent {event_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Mark as replayed
    replayed_at = serializer.validated_data.get('replayed_at') or timezone.now()
    event.status = FailedEvent.STATUS_REPLAYED
    event.replayed_at = replayed_at
    event.save(update_fields=['status', 'replayed_at', 'updated_at'])

    logger.info(
        f"Failed event replayed: id={event_id}, "
        f"correlation_id={event.correlation_id}"
    )

    return Response({'success': True}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsInternalService])
def failed_event_failed(request, event_id):
    """
    POST /api/internal/failed-events/{id}/failed

    Mark event as failed (increment retry count).
    Called by Go Worker when replay attempt fails.

    Request body:
    {
        "error_message": "Connection refused",
        "increment_retry": true  // default: true
    }

    Response:
    {
        "success": true,
        "new_status": "pending",
        "retry_count": 3
    }
    """
    from apps.operations.models import FailedEvent

    serializer = FailedEventFailedSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    # Use select_for_update to prevent race condition on retry_count increment
    with transaction.atomic():
        try:
            event = FailedEvent.objects.select_for_update().get(id=event_id)
        except FailedEvent.DoesNotExist:
            return Response(
                {'error': f'FailedEvent {event_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Update error message
        event.last_error = data['error_message']

        # Increment retry count if requested
        if data.get('increment_retry', True):
            event.retry_count += 1

        # Check if max retries exceeded
        if event.retry_count >= event.max_retries:
            event.status = FailedEvent.STATUS_FAILED
        else:
            event.status = FailedEvent.STATUS_PENDING

        event.save(update_fields=['last_error', 'retry_count', 'status', 'updated_at'])

    logger.info(
        f"Failed event retry failed: id={event_id}, "
        f"retry_count={event.retry_count}, status={event.status}"
    )

    return Response({
        'success': True,
        'new_status': event.status,
        'retry_count': event.retry_count
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsInternalService])
def failed_events_cleanup(request):
    """
    POST /api/internal/failed-events/cleanup

    Delete old replayed events.
    Called by Go Worker periodically to clean up storage.

    Request body:
    {
        "retention_days": 7  // default: 7, events older than this will be deleted
    }

    Response:
    {
        "deleted_count": 150
    }
    """
    from django.utils import timezone
    from datetime import timedelta
    from apps.operations.models import FailedEvent

    serializer = FailedEventsCleanupSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    retention_days = serializer.validated_data.get('retention_days', 7)
    cutoff_date = timezone.now() - timedelta(days=retention_days)

    # Delete old replayed and failed events in a transaction
    with transaction.atomic():
        # Delete old replayed events
        deleted_count, _ = FailedEvent.objects.filter(
            status=FailedEvent.STATUS_REPLAYED,
            replayed_at__lt=cutoff_date
        ).delete()

        # Also delete old permanently failed events
        failed_deleted, _ = FailedEvent.objects.filter(
            status=FailedEvent.STATUS_FAILED,
            updated_at__lt=cutoff_date
        ).delete()

    total_deleted = deleted_count + failed_deleted

    logger.info(
        f"Failed events cleanup: deleted {total_deleted} events "
        f"(replayed: {deleted_count}, failed: {failed_deleted})"
    )

    return Response({'deleted_count': total_deleted}, status=status.HTTP_200_OK)
