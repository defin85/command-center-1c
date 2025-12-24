"""
Operation endpoints for API v2.

Provides action-based endpoints for batch operations management.
"""

import json
import logging
import secrets
import time

import redis as redis_module
import redis.asyncio as redis_async
from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from asgiref.sync import sync_to_async
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.throttling import UserRateThrottle
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.operations.models import BatchOperation, Task
from apps.operations.serializers import BatchOperationSerializer, TaskSerializer
from apps.operations.services import OperationsService
from apps.databases.permissions import CanExecuteOperation
from apps.operations.prometheus_metrics import (
    record_api_v2_duration,
    record_api_v2_error,
    record_sse_ticket,
    sse_connection_open,
    sse_connection_close,
    record_sse_stream_error,
    record_sse_loop_duration,
)

logger = logging.getLogger(__name__)

# =============================================================================
# SSE Ticket Constants
# =============================================================================
SSE_TICKET_TTL = 30  # seconds
SSE_TICKET_PREFIX = "sse_ticket:"
SSE_BLOCK_MS = 1000
SSE_HEARTBEAT_INTERVAL_SECONDS = 10
OP_SSE_ACTIVE_PREFIX = "op_sse_active:"
OP_SSE_ACTIVE_TTL = 120


# =============================================================================
# Response Serializers for OpenAPI documentation
# =============================================================================

class ErrorDetailSerializer(serializers.Serializer):
    """Error detail structure."""
    code = serializers.CharField(help_text="Error code (e.g., MISSING_PARAMETER)")
    message = serializers.CharField(help_text="Human-readable error message")
    details = serializers.DictField(required=False, help_text="Additional error details")


class ErrorResponseSerializer(serializers.Serializer):
    """Standard error response."""
    success = serializers.BooleanField(default=False)
    error = ErrorDetailSerializer()


class OperationProgressSerializer(serializers.Serializer):
    """Progress information for an operation."""
    total = serializers.IntegerField(help_text="Total number of tasks")
    completed = serializers.IntegerField(help_text="Number of completed tasks")
    failed = serializers.IntegerField(help_text="Number of failed tasks")
    pending = serializers.IntegerField(help_text="Number of pending/queued tasks")
    processing = serializers.IntegerField(help_text="Number of processing tasks")
    percent = serializers.IntegerField(help_text="Completion percentage (0-100)")


class OperationListResponseSerializer(serializers.Serializer):
    """Response for list_operations endpoint."""
    operations = BatchOperationSerializer(many=True)
    count = serializers.IntegerField(help_text="Number of operations in current page")
    total = serializers.IntegerField(help_text="Total number of operations matching filters")


class OperationDetailResponseSerializer(serializers.Serializer):
    """Response for get_operation endpoint."""
    operation = BatchOperationSerializer()
    tasks = TaskSerializer(many=True, required=False, help_text="Task details (if include_tasks=true)")
    progress = OperationProgressSerializer()


class OperationCancelResponseSerializer(serializers.Serializer):
    """Response for cancel_operation endpoint."""
    operation_id = serializers.CharField(help_text="ID of the cancelled operation")
    cancelled = serializers.BooleanField(help_text="Whether cancellation was successful")
    message = serializers.CharField(help_text="Status message")


# =============================================================================
# Execute Operation Serializers
# =============================================================================

class ExecuteOperationRequestSerializer(serializers.Serializer):
    """Request body for execute_operation endpoint."""
    RAS_OPERATION_TYPES = [
        ('lock_scheduled_jobs', 'Lock Scheduled Jobs'),
        ('unlock_scheduled_jobs', 'Unlock Scheduled Jobs'),
        ('block_sessions', 'Block Sessions'),
        ('unblock_sessions', 'Unblock Sessions'),
        ('terminate_sessions', 'Terminate Sessions'),
    ]

    operation_type = serializers.ChoiceField(
        choices=RAS_OPERATION_TYPES,
        help_text="Type of RAS operation to execute"
    )
    database_ids = serializers.ListField(
        child=serializers.UUIDField(format='hex_verbose'),
        min_length=1,
        max_length=500,
        help_text="List of database UUIDs"
    )
    config = serializers.DictField(
        required=False,
        default=dict,
        help_text="Operation-specific configuration (e.g., message for block_sessions)"
    )


class ExecuteOperationResponseSerializer(serializers.Serializer):
    """Response for execute_operation endpoint."""
    operation_id = serializers.CharField(help_text="ID of the created operation")
    status = serializers.CharField(help_text="Operation status (queued)")
    total_tasks = serializers.IntegerField(help_text="Number of tasks created")
    message = serializers.CharField(help_text="Status message")


class ExecuteOperationThrottle(UserRateThrottle):
    """Rate limit: 30 operations per minute per user."""
    rate = '30/min'
    scope = 'execute_operation'


class ExecuteIbcmdOperationRequestSerializer(serializers.Serializer):
    """Request body for execute_ibcmd_operation endpoint."""
    IBCMD_OPERATION_TYPES = [
        ('ibcmd_backup', 'IBCMD Backup'),
        ('ibcmd_restore', 'IBCMD Restore'),
        ('ibcmd_replicate', 'IBCMD Replicate'),
        ('ibcmd_create', 'IBCMD Create'),
    ]

    operation_type = serializers.ChoiceField(
        choices=IBCMD_OPERATION_TYPES,
        help_text="Type of IBCMD operation to execute"
    )
    database_ids = serializers.ListField(
        child=serializers.UUIDField(format='hex_verbose'),
        min_length=1,
        max_length=200,
        help_text="List of database UUIDs"
    )
    config = serializers.DictField(
        required=False,
        default=dict,
        help_text="Operation-specific configuration (dbms, db_server, db_name, etc.)"
    )


class ExecuteIbcmdOperationThrottle(UserRateThrottle):
    """Rate limit: 10 IBCMD operations per minute per user."""
    rate = '10/min'
    scope = 'execute_ibcmd_operation'


# =============================================================================
# SSE Ticket Serializers
# =============================================================================

class SSETicketRequestSerializer(serializers.Serializer):
    """Request body for get_stream_ticket endpoint."""
    operation_id = serializers.CharField(help_text="Operation ID to subscribe to")


class SSETicketResponseSerializer(serializers.Serializer):
    """Response for get_stream_ticket endpoint."""
    ticket = serializers.CharField(help_text="Short-lived ticket for SSE connection")
    expires_in = serializers.IntegerField(help_text="Seconds until ticket expires")
    stream_url = serializers.CharField(help_text="SSE endpoint URL to connect to")


@extend_schema(
    tags=['v2'],
    summary='List batch operations',
    description='List all batch operations with optional filtering by status, type, and creator.',
    parameters=[
        OpenApiParameter(
            name='operation_id',
            type=str,
            required=False,
            description='Filter by operation ID'
        ),
        OpenApiParameter(
            name='status',
            type=str,
            required=False,
            description='Filter by status (pending, queued, processing, completed, failed, cancelled)'
        ),
        OpenApiParameter(
            name='operation_type',
            type=str,
            required=False,
            description='Filter by type (create, update, delete, query, install_extension)'
        ),
        OpenApiParameter(
            name='created_by',
            type=str,
            required=False,
            description='Filter by creator username'
        ),
        OpenApiParameter(
            name='workflow_execution_id',
            type=str,
            required=False,
            description='Filter by workflow execution ID'
        ),
        OpenApiParameter(
            name='node_id',
            type=str,
            required=False,
            description='Filter by workflow node ID'
        ),
        OpenApiParameter(
            name='limit',
            type=int,
            required=False,
            description='Maximum results (default: 50, max: 1000)'
        ),
        OpenApiParameter(
            name='offset',
            type=int,
            required=False,
            description='Pagination offset (default: 0)'
        ),
    ],
    responses={
        200: OperationListResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_operations(request):
    """
    GET /api/v2/operations/list-operations/

    List all batch operations with optional filtering.

    Query Parameters:
        - operation_id: Filter by operation ID
        - status: Filter by status (pending, queued, processing, completed, failed, cancelled)
        - operation_type: Filter by type (create, update, delete, query, install_extension)
        - created_by: Filter by creator username
        - workflow_execution_id: Filter by workflow execution ID
        - node_id: Filter by workflow node ID
        - limit: Maximum results (default: 50)
        - offset: Pagination offset (default: 0)

    Response:
        {
            "operations": [...],
            "count": 50,
            "total": 200
        }
    """
    status = request.query_params.get('status')
    operation_type = request.query_params.get('operation_type')
    created_by = request.query_params.get('created_by')
    operation_id = request.query_params.get('operation_id')
    workflow_execution_id = request.query_params.get('workflow_execution_id')
    node_id = request.query_params.get('node_id')

    # Safely parse integer parameters with validation
    try:
        limit = int(request.query_params.get('limit', 50))
        limit = max(1, min(limit, 1000))  # Clamp to [1, 1000]
    except (ValueError, TypeError):
        limit = 50

    try:
        offset = int(request.query_params.get('offset', 0))
        offset = max(0, offset)
    except (ValueError, TypeError):
        offset = 0

    qs = BatchOperation.objects.prefetch_related('target_databases')

    if status:
        qs = qs.filter(status=status)
    if operation_type:
        qs = qs.filter(operation_type=operation_type)
    if created_by:
        qs = qs.filter(created_by=created_by)
    if operation_id:
        qs = qs.filter(id=operation_id)
    if workflow_execution_id:
        qs = qs.filter(metadata__workflow_execution_id=workflow_execution_id)
    if node_id:
        qs = qs.filter(metadata__node_id=node_id)

    # Order by most recent first
    qs = qs.order_by('-created_at')

    total = qs.count()
    qs = qs[offset:offset + limit]

    serializer = BatchOperationSerializer(qs, many=True)

    return Response({
        'operations': serializer.data,
        'count': len(serializer.data),
        'total': total,
    })


@extend_schema(
    tags=['v2'],
    summary='Get operation details',
    description='Get detailed information about a specific operation including tasks and progress.',
    parameters=[
        OpenApiParameter(
            name='operation_id',
            type=str,
            required=True,
            description='Operation ID (UUID)'
        ),
        OpenApiParameter(
            name='include_tasks',
            type=bool,
            required=False,
            description='Include task details (default: true, max 100 tasks)'
        ),
    ],
    responses={
        200: OperationDetailResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_operation(request):
    """
    GET /api/v2/operations/get-operation/?operation_id=X

    Get detailed information about a specific operation.

    Query Parameters:
        - operation_id: Operation ID (required)
        - include_tasks: Include task details (default: true)

    Response:
        {
            "operation": {...},
            "tasks": [...],
            "progress": {
                "total": 100,
                "completed": 95,
                "failed": 5,
                "pending": 0,
                "percent": 100
            }
        }
    """
    operation_id = request.query_params.get('operation_id')
    include_tasks = request.query_params.get('include_tasks', 'true').lower() == 'true'

    if not operation_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'operation_id is required'
            }
        }, status=400)

    try:
        operation = BatchOperation.objects.prefetch_related(
            'tasks', 'target_databases'
        ).get(id=operation_id)
    except BatchOperation.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'OPERATION_NOT_FOUND',
                'message': 'Operation not found'
            }
        }, status=404)

    serializer = BatchOperationSerializer(operation)

    # Build progress info
    tasks = operation.tasks.all()
    progress = {
        'total': tasks.count(),
        'completed': tasks.filter(status=Task.STATUS_COMPLETED).count(),
        'failed': tasks.filter(status=Task.STATUS_FAILED).count(),
        'pending': tasks.filter(status__in=[Task.STATUS_PENDING, Task.STATUS_QUEUED]).count(),
        'processing': tasks.filter(status=Task.STATUS_PROCESSING).count(),
        'percent': operation.progress,
    }

    response_data = {
        'operation': serializer.data,
        'progress': progress,
    }

    if include_tasks:
        task_serializer = TaskSerializer(tasks[:100], many=True)  # Limit to 100 tasks
        response_data['tasks'] = task_serializer.data

    return Response(response_data)


class CancelOperationRequestSerializer(serializers.Serializer):
    """Request body for cancel_operation endpoint."""
    operation_id = serializers.CharField(help_text="ID of the operation to cancel (UUID)")


@extend_schema(
    tags=['v2'],
    summary='Cancel operation',
    description='Cancel a running or pending operation. Already completed or cancelled operations cannot be cancelled.',
    request=CancelOperationRequestSerializer,
    responses={
        200: OperationCancelResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_operation(request):
    """
    POST /api/v2/operations/cancel-operation/

    Cancel a running or pending operation.

    Request Body:
        {
            "operation_id": "string"
        }

    Response:
        {
            "operation_id": "string",
            "cancelled": true,
            "message": "Operation cancelled successfully"
        }
    """
    operation_id = request.data.get('operation_id')

    if not operation_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'operation_id is required'
            }
        }, status=400)

    try:
        operation = BatchOperation.objects.get(id=operation_id)
    except BatchOperation.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'OPERATION_NOT_FOUND',
                'message': 'Operation not found'
            }
        }, status=404)

    # Check if operation can be cancelled
    if operation.status in [BatchOperation.STATUS_COMPLETED, BatchOperation.STATUS_CANCELLED]:
        return Response({
            'operation_id': operation_id,
            'cancelled': False,
            'message': f'Operation cannot be cancelled (status: {operation.status})',
        }, status=400)

    # Cancel the operation
    operation.status = BatchOperation.STATUS_CANCELLED
    operation.completed_at = timezone.now()
    operation.save(update_fields=['status', 'completed_at', 'updated_at'])

    # Cancel pending tasks
    cancelled_tasks = Task.objects.filter(
        batch_operation=operation,
        status__in=[Task.STATUS_PENDING, Task.STATUS_QUEUED]
    ).update(status=Task.STATUS_CANCELLED)

    # Note: Go Worker handles task cancellation via Redis events
    # No need to revoke tasks here - operation status change triggers cancellation

    # Audit logging
    logger.info(
        "Operation cancelled by user",
        extra={
            'operation_id': operation_id,
            'operation_type': operation.operation_type,
            'cancelled_by': request.user.username if request.user else 'anonymous',
            'cancelled_tasks_count': cancelled_tasks,
        }
    )

    return Response({
        'operation_id': operation_id,
        'cancelled': True,
        'message': 'Operation cancelled successfully',
    })


# =============================================================================
# Execute RAS Operation
# =============================================================================

@extend_schema(
    tags=['v2'],
    summary='Execute RAS operation',
    description='''
    Queue a RAS operation for execution on selected databases.

    **Supported operation types:**
    - `lock_scheduled_jobs` - Lock scheduled jobs on databases
    - `unlock_scheduled_jobs` - Unlock scheduled jobs on databases
    - `block_sessions` - Block new sessions (with optional message)
    - `unblock_sessions` - Unblock sessions
    - `terminate_sessions` - Terminate all active sessions

    **Config options for block_sessions:**
    - `message` - Message displayed to users
    - `permission_code` - Code allowing entry despite block
    ''',
    request=ExecuteOperationRequestSerializer,
    responses={
        202: ExecuteOperationResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, CanExecuteOperation])
@throttle_classes([ExecuteOperationThrottle])
def execute_operation(request):
    """
    POST /api/v2/operations/execute/

    Queue a RAS operation (lock/unlock/block/terminate) for multiple databases.

    Request Body:
        {
            "operation_type": "lock_scheduled_jobs",
            "database_ids": ["uuid1", "uuid2"],
            "config": {}  // optional
        }

    Response (202 Accepted):
        {
            "operation_id": "uuid",
            "status": "queued",
            "total_tasks": 2,
            "message": "lock_scheduled_jobs queued for 2 database(s)"
        }
    """
    serializer = ExecuteOperationRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    operation_type = serializer.validated_data['operation_type']
    database_ids = serializer.validated_data['database_ids']
    config = serializer.validated_data.get('config', {})

    try:
        batch_operation = OperationsService.enqueue_ras_operation(
            operation_type=operation_type,
            database_ids=database_ids,
            config=config,
            user=request.user,
        )

        logger.info(
            f"RAS operation {operation_type} queued",
            extra={
                'operation_id': str(batch_operation.id),
                'operation_type': operation_type,
                'database_count': len(database_ids),
                'created_by': request.user.username if request.user else 'anonymous',
            }
        )

        return Response({
            'operation_id': str(batch_operation.id),
            'status': batch_operation.status,
            'total_tasks': batch_operation.total_tasks,
            'message': f'{operation_type} queued for {len(database_ids)} database(s)',
        }, status=http_status.HTTP_202_ACCEPTED)

    except ValueError as e:
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': str(e)
            }
        }, status=400)

    except Exception as e:
        logger.error(f"Error executing RAS operation: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'Failed to queue operation'
            }
        }, status=500)


# =============================================================================
# Execute IBCMD Operation
# =============================================================================

@extend_schema(
    tags=['v2'],
    summary='Execute IBCMD operation',
    description='''
    Queue an IBCMD operation for execution on selected databases.

    **Supported operation types:**
    - `ibcmd_backup` - Backup infobase
    - `ibcmd_restore` - Restore infobase from backup
    - `ibcmd_replicate` - Replicate infobase to another server
    - `ibcmd_create` - Create new infobase
    ''',
    request=ExecuteIbcmdOperationRequestSerializer,
    responses={
        202: ExecuteOperationResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, CanExecuteOperation])
@throttle_classes([ExecuteIbcmdOperationThrottle])
def execute_ibcmd_operation(request):
    """
    POST /api/v2/operations/execute-ibcmd/

    Queue an IBCMD operation (backup/restore/replicate/create) for multiple databases.
    """
    serializer = ExecuteIbcmdOperationRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    operation_type = serializer.validated_data['operation_type']
    database_ids = serializer.validated_data['database_ids']
    config = serializer.validated_data.get('config', {})

    try:
        batch_operation = OperationsService.enqueue_ibcmd_operation(
            operation_type=operation_type,
            database_ids=database_ids,
            config=config,
            user=request.user,
        )

        logger.info(
            f"IBCMD operation {operation_type} queued",
            extra={
                'operation_id': str(batch_operation.id),
                'operation_type': operation_type,
                'database_count': len(database_ids),
                'created_by': request.user.username if request.user else 'anonymous',
            }
        )

        return Response({
            'operation_id': str(batch_operation.id),
            'status': batch_operation.status,
            'total_tasks': batch_operation.total_tasks,
            'message': f'{operation_type} queued for {len(database_ids)} database(s)',
        }, status=http_status.HTTP_202_ACCEPTED)

    except ValueError as e:
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': str(e)
            }
        }, status=400)

    except Exception as e:
        logger.error(f"Error executing IBCMD operation: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'Failed to queue operation'
            }
        }, status=500)


# =============================================================================
# SSE Streaming
# =============================================================================


def _get_redis_connection():
    """Get Redis connection for SSE tickets."""
    redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    return redis_module.from_url(redis_url, decode_responses=True)


def _get_async_redis_connection():
    redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    return redis_async.from_url(redis_url, decode_responses=True)


async def _validate_sse_ticket_async(ticket: str) -> tuple:
    """
    Validate and consume SSE ticket (async).

    Returns:
        (ticket_data, error_message) - ticket_data is None if validation failed
    """
    redis_conn = _get_async_redis_connection()
    try:
        ticket_key = f"{SSE_TICKET_PREFIX}{ticket}"
        pipe = redis_conn.pipeline()
        pipe.get(ticket_key)
        pipe.delete(ticket_key)
        results = await pipe.execute()

        ticket_data_raw = results[0]
        if not ticket_data_raw:
            return None, "Invalid or expired ticket"

        return json.loads(ticket_data_raw), None
    finally:
        await redis_conn.close()


@extend_schema(
    tags=['v2'],
    summary='Get SSE stream ticket',
    description='''
    Obtain a short-lived, single-use ticket for SSE stream authentication.

    The ticket is valid for 30 seconds and can only be used once.
    This allows secure SSE connections without exposing JWT tokens in URLs.
    ''',
    request=SSETicketRequestSerializer,
    responses={
        200: SSETicketResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_stream_ticket(request):
    """
    POST /api/v2/operations/stream-ticket/

    Get a short-lived ticket for SSE stream authentication.

    Request Body:
        {"operation_id": "uuid"}

    Response:
        {
            "ticket": "random_string",
            "expires_in": 30,
            "stream_url": "/api/v2/operations/stream/?ticket=..."
        }
    """
    start_time = time.monotonic()
    endpoint = "operations.stream_ticket"
    serializer = SSETicketRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    operation_id = serializer.validated_data['operation_id']

    # Verify operation exists and user has permission
    operation = BatchOperation.objects.filter(id=operation_id).first()
    if not operation:
        record_api_v2_duration(endpoint, "not_found", time.monotonic() - start_time)
        record_sse_ticket("operations", "not_found")
        return Response({
            'success': False,
            'error': {
                'code': 'OPERATION_NOT_FOUND',
                'message': 'Operation not found'
            }
        }, status=404)

    # Authorization check: user must own the operation or be superuser
    if operation.created_by != request.user.username and not request.user.is_superuser:
        record_api_v2_duration(endpoint, "forbidden", time.monotonic() - start_time)
        record_sse_ticket("operations", "forbidden")
        return Response({
            'success': False,
            'error': {
                'code': 'FORBIDDEN',
                'message': 'You do not have permission to subscribe to this operation'
            }
        }, status=403)

    redis_conn = _get_redis_connection()
    active_key = f"{OP_SSE_ACTIVE_PREFIX}{request.user.id}:{operation_id}"

    try:
        ttl = redis_conn.ttl(active_key)
        if ttl and ttl > 0:
            record_api_v2_duration(endpoint, "conflict", time.monotonic() - start_time)
            record_sse_ticket("operations", "conflict")
            response = Response({
                'success': False,
                'error': {
                    'code': 'STREAM_ALREADY_ACTIVE',
                    'message': 'Operation stream already active for this user',
                    'retry_after': ttl,
                }
            }, status=429)
            response['Retry-After'] = str(ttl)
            return response

        # Generate secure random ticket
        ticket = secrets.token_urlsafe(32)

        ticket_data = {
            'user_id': request.user.id,
            'username': request.user.username,
            'operation_id': operation_id,
            'created_at': timezone.now().isoformat(),
        }

        redis_conn.setex(
            f"{SSE_TICKET_PREFIX}{ticket}",
            SSE_TICKET_TTL,
            json.dumps(ticket_data)
        )
        record_api_v2_duration(endpoint, "ok", time.monotonic() - start_time)
        record_sse_ticket("operations", "ok")
    except Exception as exc:
        record_api_v2_duration(endpoint, "error", time.monotonic() - start_time)
        record_api_v2_error(endpoint, exc.__class__.__name__)
        record_sse_ticket("operations", "error")
        raise
    finally:
        redis_conn.close()

    return Response({
        'ticket': ticket,
        'expires_in': SSE_TICKET_TTL,
        'stream_url': f'/api/v2/operations/stream/?ticket={ticket}'
    })


async def operation_stream(request):
    """
    GET /api/v2/operations/stream/?ticket=xxx
    GET /api/v2/operations/stream/?operation_id=xxx&token=xxx (deprecated)

    SSE endpoint for real-time operation updates.

    Prefer ticket-based auth via /stream-ticket/ endpoint for security.
    """
    start_time = time.monotonic()
    endpoint = "operations.stream"
    ticket = request.GET.get('ticket')
    token = request.GET.get('token')
    operation_id = request.GET.get('operation_id')

        # Validate: need either ticket or (token + operation_id)
    if not ticket and not token:
        record_api_v2_duration(endpoint, "unauthorized", time.monotonic() - start_time)
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'ticket is required (use /stream-ticket/ to obtain)'
            }
        }, status=401)

        # Prefer ticket-based auth (secure)
    if ticket:
        ticket_data, error = await _validate_sse_ticket_async(ticket)
        if error:
            record_api_v2_duration(endpoint, "unauthorized", time.monotonic() - start_time)
            return JsonResponse({
                'success': False,
                'error': {
                    'code': 'INVALID_TICKET',
                    'message': error
                }
            }, status=401)

        operation_id = ticket_data['operation_id']
        username = ticket_data['username']

    else:
        # Legacy token auth (deprecated - log warning)
        logger.warning(
            "SSE stream using deprecated token auth. "
            "Please migrate to ticket-based auth via /stream-ticket/"
        )

        if not operation_id:
            record_api_v2_duration(endpoint, "bad_request", time.monotonic() - start_time)
            return JsonResponse({
                'success': False,
                'error': {
                    'code': 'MISSING_PARAMETER',
                    'message': 'operation_id is required with token auth'
                }
            }, status=400)

        # Manual JWT authentication
        async def _authenticate_legacy_token(raw_token: str):
            def _sync_auth():
                jwt_auth = JWTAuthentication()
                validated_token = jwt_auth.get_validated_token(raw_token)
                user = jwt_auth.get_user(validated_token)
                if not user:
                    raise AuthenticationFailed('User not found')
                return user

            return await sync_to_async(_sync_auth, thread_sensitive=True)()

        try:
            user = await _authenticate_legacy_token(token)
            username = user.username
        except Exception as e:
            logger.error(f"SSE authentication failed: {e}")
            record_api_v2_duration(endpoint, "unauthorized", time.monotonic() - start_time)
            record_api_v2_error(endpoint, e.__class__.__name__)
            return JsonResponse({
                'success': False,
                'error': {
                    'code': 'INVALID_TOKEN',
                    'message': 'Invalid or expired token'
                }
            }, status=401)

    logger.info(f"SSE stream started for operation {operation_id} by user {username}")

    active_key = None
    active_value = None
    if ticket:
        user_id = ticket_data.get("user_id")
        if user_id:
            active_key = f"{OP_SSE_ACTIVE_PREFIX}{user_id}:{operation_id}"
            active_value = secrets.token_urlsafe(12)
            active_conn = _get_async_redis_connection()
            try:
                if not await active_conn.set(active_key, active_value, nx=True, ex=OP_SSE_ACTIVE_TTL):
                    record_api_v2_duration(endpoint, "conflict", time.monotonic() - start_time)
                    return JsonResponse({
                        'success': False,
                        'error': {
                            'code': 'STREAM_ALREADY_ACTIVE',
                            'message': 'Operation stream already active for this user'
                        }
                    }, status=429)
            finally:
                await active_conn.close()

    async def event_generator():
        """Generator for SSE events using Redis Streams (XREAD)."""
        logger.info(f"event_generator: Starting for operation {operation_id}")
        sse_connection_open("operations")

        # Connect to Redis
        redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
        redis_conn = redis_async.from_url(redis_url, decode_responses=True)
        stream_name = f"events:operation:{operation_id}"
        logger.info(f"event_generator: Will read from stream {stream_name}")

        # Send initial state
        try:
            operation = await sync_to_async(BatchOperation.objects.get, thread_sensitive=True)(id=operation_id)
            logger.info(f"event_generator: Found operation with status {operation.status}")
            operation_metadata = operation.metadata or {}
            initial_event = {
                "version": "1.0",
                "operation_id": str(operation_id),
                "timestamp": timezone.now().isoformat(),
                "state": operation.status.upper(),
                "microservice": "orchestrator",
                "message": f"Operation status: {operation.status}",
                "trace_id": operation_metadata.get("trace_id"),
                "workflow_execution_id": operation_metadata.get("workflow_execution_id"),
                "node_id": operation_metadata.get("node_id"),
                "metadata": {
                    "operation_type": operation.operation_type,
                    "created_at": operation.created_at.isoformat(),
                }
            }
            logger.info("event_generator: Sending initial event")
            yield f"data: {json.dumps(initial_event)}\n\n"
            logger.info("event_generator: Initial event sent")
        except BatchOperation.DoesNotExist:
            error_event = {
                "error": "Operation not found",
                "operation_id": str(operation_id)
            }
            yield f"data: {json.dumps(error_event)}\n\n"
            await redis_conn.close()
            record_sse_stream_error("operations", "missing_operation")
            return

        # Read events from Redis Stream using XREAD
        # Start with '0-0' to read from beginning for complete operation history
        # (MAXLEN=1000 ensures all events of typical operation are preserved)
        last_event_id = request.headers.get("Last-Event-ID")
        last_id = last_event_id or '0-0'
        last_heartbeat = time.monotonic()

        try:
            while True:
                loop_start = time.monotonic()
                # XREAD with short block timeout
                # Returns: [(stream_name, [(msg_id, {fields}), ...])] or None on timeout
                messages = await redis_conn.xread({stream_name: last_id}, block=SSE_BLOCK_MS, count=10)

                if not messages:
                    # Timeout - send heartbeat comment to keep connection alive
                    now = time.monotonic()
                    if now - last_heartbeat >= SSE_HEARTBEAT_INTERVAL_SECONDS:
                        if active_key:
                            try:
                                await redis_conn.expire(active_key, OP_SSE_ACTIVE_TTL)
                            except Exception:
                                pass
                        yield ": heartbeat\n\n"
                        last_heartbeat = now
                    record_sse_loop_duration("operations", time.monotonic() - loop_start)
                    continue

                for stream, stream_messages in messages:
                    for msg_id, fields in stream_messages:
                        # Extract event data from stream message
                        # Format: {"event_type": "...", "data": "json_string", "operation_id": "..."}
                        event_data = fields.get('data', '{}')
                        event_type = fields.get('event_type') or 'message'
                        if active_key:
                            try:
                                await redis_conn.expire(active_key, OP_SSE_ACTIVE_TTL)
                            except Exception:
                                pass
                        yield f"event: {event_type}\n"
                        yield f"id: {msg_id}\n"
                        yield f"data: {event_data}\n\n"
                        last_id = msg_id
                loop_duration = time.monotonic() - loop_start
                record_sse_loop_duration("operations", loop_duration)
                if loop_duration > 5:
                    logger.warning("operation_stream: slow loop %.2fs (operation_id=%s)", loop_duration, operation_id)

        except GeneratorExit:
            # Client disconnected
            logger.info(f"Client disconnected from SSE stream for operation {operation_id}")
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            record_sse_stream_error("operations", "event_loop")
            raise
        finally:
            try:
                if active_key and active_value:
                    current_value = await redis_conn.get(active_key)
                    if current_value == active_value:
                        await redis_conn.delete(active_key)
                await redis_conn.close()
            except Exception:
                pass  # Игнорируем ошибки при закрытии
            sse_connection_close("operations")

    record_api_v2_duration(endpoint, "stream_start", time.monotonic() - start_time)
    response = StreamingHttpResponse(
        event_generator(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
    return response
