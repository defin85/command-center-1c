"""
Internal API v2 views for Go Worker communication.

Action-based API style consistent with public API v2.
All endpoints require X-Internal-Token authentication.

URL prefix: /api/v2/internal/
"""

import logging
from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

from .permissions import IsInternalService
from .serializers import (
    SchedulerRunStartSerializer,
    SchedulerRunCompleteSerializer,
    TaskExecutionStartSerializer,
    TaskExecutionCompleteSerializer,
    HealthUpdateSerializer,
    FailedEventSerializer,
    FailedEventReplayedSerializer,
    FailedEventFailedSerializer,
    FailedEventsCleanupSerializer,
    TemplateRenderRequestSerializer,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Scheduler Job History Endpoints (v2)
# =============================================================================

@api_view(['POST'])
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
        return Response(
            {'success': False, 'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    data = serializer.validated_data

    from apps.operations.models import SchedulerJobRun

    run = SchedulerJobRun.objects.create(
        job_name=data['job_name'],
        worker_instance=data['worker_instance'],
        status=SchedulerJobRun.STATUS_RUNNING,
        started_at=timezone.now(),
        job_config=data.get('job_config') or {},
    )

    logger.info(
        f"Scheduler run started: job={data['job_name']}, "
        f"worker={data['worker_instance']}"
    )

    return Response({
        'success': True,
        'run_id': run.id,
        'status': 'running'
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
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
    run_id = request.query_params.get('run_id')
    if not run_id:
        return Response(
            {'success': False, 'error': {'run_id': 'This query parameter is required'}},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        run_id = int(run_id)
    except ValueError:
        return Response(
            {'success': False, 'error': {'run_id': 'Must be an integer'}},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = SchedulerRunCompleteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    data = serializer.validated_data

    from apps.operations.models import SchedulerJobRun

    try:
        run = SchedulerJobRun.objects.get(id=run_id)
    except SchedulerJobRun.DoesNotExist:
        return Response(
            {'success': False, 'error': f'Scheduler run {run_id} not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    run.status = data['status']
    run.finished_at = timezone.now()
    run.duration_ms = data.get('duration_ms', 0)
    run.result_summary = data.get('result_summary', '')
    run.error_message = data.get('error_message', '')
    run.items_processed = data.get('items_processed', 0)
    run.items_failed = data.get('items_failed', 0)
    run.save(
        update_fields=[
            'status',
            'finished_at',
            'duration_ms',
            'result_summary',
            'error_message',
            'items_processed',
            'items_failed',
        ],
    )

    logger.info(
        f"Scheduler run completed: id={run_id}, status={data['status']}, "
        f"duration={data['duration_ms']}ms"
    )

    return Response({
        'success': True,
        'run_id': run_id,
        'status': data['status']
    }, status=status.HTTP_200_OK)


# =============================================================================
# Task Execution Log Endpoints (v2)
# =============================================================================

@api_view(['POST'])
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
        return Response(
            {'success': False, 'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    data = serializer.validated_data

    from apps.operations.models import BatchOperation, TaskExecutionLog

    try:
        operation = BatchOperation.objects.get(id=data['operation_id'])
    except BatchOperation.DoesNotExist:
        return Response(
            {'success': False, 'error': f"Batch operation {data['operation_id']} not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    log = TaskExecutionLog.objects.create(
        operation=operation,
        task_type=data['task_type'],
        queue_name='internal',
        worker_instance=data.get('worker_instance') or 'worker',
        status=TaskExecutionLog.STATUS_RUNNING,
        started_at=timezone.now(),
        input_summary={
            'target_id': data['target_id'],
            'target_type': data.get('target_type') or '',
            'parameters': data.get('parameters') or {},
        },
    )

    logger.info(
        "Task started",
        extra={
            'task_id': log.id,
            'task_type': data['task_type'],
            'operation_id': data['operation_id'],
        },
    )

    return Response({
        'success': True,
        'task_id': log.id,
        'status': 'running',
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
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
    task_id = request.query_params.get('task_id')
    if not task_id:
        return Response(
            {'success': False, 'error': {'task_id': 'This query parameter is required'}},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        task_id = int(task_id)
    except ValueError:
        return Response(
            {'success': False, 'error': {'task_id': 'Must be an integer'}},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = TaskExecutionCompleteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    data = serializer.validated_data

    from apps.operations.models import TaskExecutionLog

    try:
        log = TaskExecutionLog.objects.get(id=task_id)
    except TaskExecutionLog.DoesNotExist:
        return Response(
            {'success': False, 'error': f'Task {task_id} not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    log.status = data['status']
    log.finished_at = timezone.now()
    log.duration_ms = data.get('duration_ms', 0)
    log.result_summary = data.get('result') or {}
    log.error_message = data.get('error_message', '')
    log.error_type = data.get('error_code', '')
    log.retry_count = data.get('retry_count', 0)
    log.save(
        update_fields=[
            'status',
            'finished_at',
            'duration_ms',
            'result_summary',
            'error_message',
            'error_type',
            'retry_count',
        ],
    )

    logger.info(
        f"Task completed: id={task_id}, status={data['status']}, "
        f"duration={data.get('duration_ms', 0)}ms"
    )

    return Response({
        'success': True,
        'task_id': task_id,
        'status': data['status']
    }, status=status.HTTP_200_OK)


# =============================================================================
# Database Endpoints (v2)
# =============================================================================

@api_view(['GET'])
@permission_classes([IsInternalService])
def get_database_credentials(request):
    """
    GET /api/v2/internal/get-database-credentials?database_id=X

    Get database credentials for OData access.
    Called by Go Worker to fetch credentials for batch operations.

    Query params:
        database_id: uuid (required)

    Response:
    {
        "success": true,
        "credentials": {
            "odata_url": "http://localhost:8080/base/odata/standard.odata",
            "username": "admin",
            "password": "secret",
            "cluster_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    }
    """
    from apps.databases.models import Database

    database_id = request.query_params.get('database_id')
    if not database_id:
        return Response(
            {'success': False, 'error': {'database_id': 'This query parameter is required'}},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        database = Database.objects.get(id=database_id)
    except Database.DoesNotExist:
        return Response(
            {'success': False, 'error': f'Database {database_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    from apps.databases.encryption import encrypt_credentials_for_transport

    credentials_dict = {
        "database_id": str(database.id),
        "odata_url": database.odata_url,
        "username": database.username,
        "password": database.password,  # EncryptedCharField auto-decrypts
        # Legacy fields (some workers still rely on them)
        "host": database.host,
        "port": database.port,
        "base_name": database.base_name,
        # DESIGNER connection fields
        "server_address": database.server_address,
        "server_port": database.server_port,
        "infobase_name": database.infobase_name or database.name,
    }

    encrypted_payload = encrypt_credentials_for_transport(credentials_dict)

    logger.debug("Credentials encrypted for database: %s", database_id)

    return Response(
        {
            'success': True,
            'credentials': encrypted_payload,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsInternalService])
def get_database_cluster_info(request):
    """
    GET /api/v2/internal/get-database-cluster-info?database_id=X

    Get RAS cluster/infobase identifiers for a database.
    Used as HTTP fallback for worker when Streams are unavailable.

    Query params:
        database_id: string (required)

    Response:
    {
        "success": true,
        "cluster_info": {
            "database_id": "db-123",
            "cluster_id": "550e8400-e29b-41d4-a716-446655440000",
            "infobase_id": "550e8400-e29b-41d4-a716-446655440001"
        }
    }
    """
    from apps.databases.models import Database

    database_id = request.query_params.get('database_id')
    if not database_id:
        return Response(
            {'success': False, 'error': {'database_id': 'This query parameter is required'}},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        database = Database.objects.get(id=database_id)
    except Database.DoesNotExist:
        return Response(
            {'success': False, 'error': f'Database {database_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not database.ras_cluster_id:
        return Response(
            {'success': False, 'error': {'ras_cluster_id': 'RAS cluster metadata is not configured'}},
            status=status.HTTP_400_BAD_REQUEST
        )

    infobase_id = str(database.ras_infobase_id) if database.ras_infobase_id else str(database.id)

    return Response(
        {
            'success': True,
            'cluster_info': {
                'database_id': str(database.id),
                'cluster_id': str(database.ras_cluster_id),
                'infobase_id': infobase_id,
            },
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsInternalService])
def list_databases_for_health_check(request):
    """
    GET /api/v2/internal/list-databases-for-health-check

    Get list of databases for periodic health checks.
    Called by Go Worker to fetch databases that need health monitoring.

    Response:
    {
        "success": true,
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
    from apps.databases.models import Database

    # Get active databases with OData URL
    databases = Database.objects.filter(
        status=Database.STATUS_ACTIVE,
        odata_url__isnull=False
    ).exclude(odata_url='').values('id', 'odata_url', 'name')

    database_list = [
        {'id': str(db['id']), 'odata_url': db['odata_url'], 'name': db['name']}
        for db in databases
    ]

    logger.debug(f"Fetched {len(database_list)} databases for health check")

    return Response({
        'success': True,
        'databases': database_list,
        'count': len(database_list)
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsInternalService])
def update_database_health(request):
    """
    POST /api/v2/internal/update-database-health?database_id=X

    Update database health status.
    Called by Go Worker after health check execution.

    Query params:
        database_id: uuid (required)

    Request body:
    {
        "healthy": true,
        "error_message": "",
        "response_time_ms": 250,
        "error_code": ""
    }

    Response:
    {
        "success": true,
        "database_id": "...",
        "healthy": true
    }
    """
    from apps.databases.models import Database

    database_id = request.query_params.get('database_id')
    if not database_id:
        return Response(
            {'success': False, 'error': {'database_id': 'This query parameter is required'}},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = HealthUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    data = serializer.validated_data

    try:
        database = Database.objects.get(id=database_id)
    except Database.DoesNotExist:
        return Response(
            {'success': False, 'error': f'Database {database_id} not found'},
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

    return Response({
        'success': True,
        'database_id': str(database_id),
        'healthy': data['healthy']
    }, status=status.HTTP_200_OK)


# =============================================================================
# Cluster Endpoints (v2)
# =============================================================================

@api_view(['POST'])
@permission_classes([IsInternalService])
def update_cluster_health(request):
    """
    POST /api/v2/internal/update-cluster-health?cluster_id=X

    Update cluster health status.
    Called by Go Worker after health check execution.

    Query params:
        cluster_id: uuid (required)

    Request body:
    {
        "healthy": true,
        "error_message": "",
        "response_time_ms": 100
    }

    Response:
    {
        "success": true,
        "cluster_id": "...",
        "healthy": true
    }
    """
    from apps.databases.models import Cluster

    cluster_id = request.query_params.get('cluster_id')
    if not cluster_id:
        return Response(
            {'success': False, 'error': {'cluster_id': 'This query parameter is required'}},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = HealthUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    data = serializer.validated_data

    try:
        cluster = Cluster.objects.get(id=cluster_id)
    except Cluster.DoesNotExist:
        return Response(
            {'success': False, 'error': f'Cluster {cluster_id} not found'},
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

    return Response({
        'success': True,
        'cluster_id': str(cluster_id),
        'healthy': data['healthy']
    }, status=status.HTTP_200_OK)


# =============================================================================
# Failed Events Endpoints (v2)
# =============================================================================

@api_view(['GET'])
@permission_classes([IsInternalService])
def list_pending_failed_events(request):
    """
    GET /api/v2/internal/list-pending-failed-events?batch_size=100

    Get pending failed events for replay.
    Called by Go Worker to fetch events that need to be replayed to Redis.

    Query params:
        batch_size: int (default: 100, max: 1000)

    Response:
    {
        "success": true,
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
        'success': True,
        'events': serializer.data,
        'count': len(serializer.data)
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsInternalService])
def mark_event_replayed(request):
    """
    POST /api/v2/internal/mark-event-replayed?event_id=X

    Mark event as successfully replayed.
    Called by Go Worker after successfully publishing event to Redis.

    Query params:
        event_id: int (required)

    Request body:
    {
        "replayed_at": "2025-01-01T12:00:00Z"  // optional
    }

    Response:
    {
        "success": true,
        "event_id": 123,
        "status": "replayed"
    }
    """
    from apps.operations.models import FailedEvent

    event_id = request.query_params.get('event_id')
    if not event_id:
        return Response(
            {'success': False, 'error': {'event_id': 'This query parameter is required'}},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        event_id = int(event_id)
    except ValueError:
        return Response(
            {'success': False, 'error': {'event_id': 'Must be an integer'}},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = FailedEventReplayedSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        event = FailedEvent.objects.get(id=event_id)
    except FailedEvent.DoesNotExist:
        return Response(
            {'success': False, 'error': f'FailedEvent {event_id} not found'},
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

    return Response({
        'success': True,
        'event_id': event_id,
        'status': 'replayed'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsInternalService])
def mark_event_failed(request):
    """
    POST /api/v2/internal/mark-event-failed?event_id=X

    Mark event as failed (increment retry count).
    Called by Go Worker when replay attempt fails.

    Query params:
        event_id: int (required)

    Request body:
    {
        "error_message": "Connection refused",
        "increment_retry": true  // default: true
    }

    Response:
    {
        "success": true,
        "event_id": 123,
        "new_status": "pending",
        "retry_count": 3
    }
    """
    from apps.operations.models import FailedEvent

    event_id = request.query_params.get('event_id')
    if not event_id:
        return Response(
            {'success': False, 'error': {'event_id': 'This query parameter is required'}},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        event_id = int(event_id)
    except ValueError:
        return Response(
            {'success': False, 'error': {'event_id': 'Must be an integer'}},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = FailedEventFailedSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    data = serializer.validated_data

    # Use select_for_update to prevent race condition
    with transaction.atomic():
        try:
            event = FailedEvent.objects.select_for_update().get(id=event_id)
        except FailedEvent.DoesNotExist:
            return Response(
                {'success': False, 'error': f'FailedEvent {event_id} not found'},
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
        'event_id': event_id,
        'new_status': event.status,
        'retry_count': event.retry_count
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsInternalService])
def cleanup_failed_events(request):
    """
    POST /api/v2/internal/cleanup-failed-events

    Delete old replayed events.
    Called by Go Worker periodically to clean up storage.

    Request body:
    {
        "retention_days": 7  // default: 7
    }

    Response:
    {
        "success": true,
        "deleted_count": 150
    }
    """
    from apps.operations.models import FailedEvent

    serializer = FailedEventsCleanupSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    retention_days = serializer.validated_data.get('retention_days', 7)
    cutoff_date = timezone.now() - timedelta(days=retention_days)

    # Delete old events in a transaction
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

    return Response({
        'success': True,
        'deleted_count': total_deleted
    }, status=status.HTTP_200_OK)


# =============================================================================
# Template Endpoints (v2)
# =============================================================================

@api_view(['GET'])
@permission_classes([IsInternalService])
def get_template(request):
    """
    GET /api/v2/internal/get-template?template_id=X

    Get template data for Go Worker.
    Returns template definition including template_data for rendering.

    Query params:
        template_id: str (required)

    Response:
    {
        "success": true,
        "template": {
            "id": "create_document",
            "name": "Create Document Template",
            "operation_type": "create",
            "target_entity": "Document.ЗаказКлиента",
            "template_data": {...},
            "version": 1,
            "is_active": true
        }
    }
    """
    from apps.templates.models import OperationTemplate

    template_id = request.query_params.get('template_id')
    if not template_id:
        return Response(
            {'success': False, 'error': {'template_id': 'This query parameter is required'}},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        template = OperationTemplate.objects.get(id=template_id)
    except OperationTemplate.DoesNotExist:
        return Response(
            {'success': False, 'error': f'Template {template_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not template.is_active:
        logger.warning(f"Template {template_id} is inactive")

    template_data = {
        'id': template.id,
        'name': template.name,
        'operation_type': template.operation_type,
        'target_entity': template.target_entity,
        'template_data': template.template_data,
        'version': 1,  # TODO: Add version field to model
        'is_active': template.is_active,
    }

    logger.debug(f"Template fetched: {template_id}")

    return Response({
        'success': True,
        'template': template_data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsInternalService])
def render_template(request):
    """
    POST /api/v2/internal/render-template?template_id=X

    Render template using Python Jinja2 (fallback for Go pongo2).
    Called by Go Worker when pongo2 encounters incompatible syntax.

    Query params:
        template_id: str (required)

    Request body:
    {
        "context": {
            "order_number": "12345",
            "items": [{"name": "Item1", "qty": 10}]
        }
    }

    Response:
    {
        "success": true,
        "rendered": {...},
        "error": ""
    }
    """
    from apps.templates.models import OperationTemplate
    from jinja2 import TemplateSyntaxError

    template_id = request.query_params.get('template_id')
    if not template_id:
        return Response(
            {'success': False, 'error': {'template_id': 'This query parameter is required'}},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate request
    req_serializer = TemplateRenderRequestSerializer(data=request.data)
    if not req_serializer.is_valid():
        return Response(
            {'success': False, 'error': req_serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    context = req_serializer.validated_data['context']

    # Get template
    try:
        template = OperationTemplate.objects.get(id=template_id)
    except OperationTemplate.DoesNotExist:
        return Response(
            {'success': False, 'error': f'Template {template_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Render template_data recursively
    try:
        rendered = _render_template_data(template.template_data, context)

        logger.debug(f"Template rendered: {template_id}")

        return Response({
            'success': True,
            'rendered': rendered,
            'error': ''
        }, status=status.HTTP_200_OK)

    except TemplateSyntaxError as e:
        logger.error(f"Template syntax error in {template_id}: {e}")
        return Response({
            'success': False,
            'rendered': {},
            'error': f'Template syntax error: {str(e)}'
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Template render error in {template_id}: {e}")
        return Response({
            'success': False,
            'rendered': {},
            'error': f'Render error: {str(e)}'
        }, status=status.HTTP_200_OK)


def _render_template_data(data, context):
    """
    Recursively render Jinja2 templates in data structure.

    Supports:
    - Strings with {{ }} expressions
    - Nested dicts and lists
    - Non-template values (int, float, bool, None) are passed through

    Security:
    - Uses SandboxedEnvironment to prevent code injection
    - Blocks access to dangerous attributes and methods
    """
    from jinja2 import BaseLoader
    from jinja2.sandbox import SandboxedEnvironment

    # Create sandboxed Jinja2 environment for security
    env = SandboxedEnvironment(loader=BaseLoader())

    if isinstance(data, str):
        # Check if string contains template expressions
        if '{{' in data or '{%' in data:
            template = env.from_string(data)
            return template.render(context)
        return data

    elif isinstance(data, dict):
        return {key: _render_template_data(value, context) for key, value in data.items()}

    elif isinstance(data, list):
        return [_render_template_data(item, context) for item in data]

    else:
        # Return non-template values as-is
        return data


# =============================================================================
# Timeline Endpoints (Operation Observability)
# =============================================================================

@api_view(['POST'])
@permission_classes([IsInternalService])
def get_operation_timeline(request):
    """
    POST /api/v2/internal/get-operation-timeline

    Get operation execution timeline from Redis.

    NOTE: Internal endpoint - no ownership check (service-to-service).
    For public access with ownership validation, use:
    POST /api/v2/operations/get-operation-timeline/

    Request body:
        operation_id: str (required)
        limit: int (default: 100, max: 500)
        offset: int (default: 0)

    Response:
    {
        "operation_id": "op-123",
        "timeline": [
            {
                "timestamp": 1734567890123,
                "event": "operation.started",
                "service": "worker",
                "metadata": {}
            }
        ],
        "total_events": 5,
        "duration_ms": 1234
    }
    """
    from apps.operations.services import TimelineService

    # Parse request body
    operation_id = request.data.get('operation_id')
    if not operation_id:
        return Response(
            {'success': False, 'error': 'operation_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Parse params from body
    try:
        limit = min(int(request.data.get('limit', 100)), 500)
        offset = max(int(request.data.get('offset', 0)), 0)
    except (ValueError, TypeError):
        limit, offset = 100, 0

    # Get timeline via service (user=None skips ownership check for internal calls)
    result = TimelineService.get_timeline(
        operation_id=operation_id,
        limit=limit,
        offset=offset,
        user=None  # Internal endpoint - no ownership check
    )

    if not result.success:
        from apps.operations.services.timeline_service import TimelineErrorCode

        error_msg = result.error or "Unknown error"

        # Use error_code instead of string matching
        if result.error_code == TimelineErrorCode.NOT_FOUND:
            return Response(
                {'success': False, 'error': error_msg},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(
            {'success': False, 'error': error_msg},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return Response({
        'operation_id': result.operation_id,
        'timeline': result.timeline,
        'total_events': result.total_events,
        'duration_ms': result.duration_ms
    }, status=status.HTTP_200_OK)
