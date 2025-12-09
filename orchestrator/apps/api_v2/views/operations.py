"""
Operation endpoints for API v2.

Provides action-based endpoints for batch operations management.
"""

import json
import logging

import redis as redis_module
from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
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

logger = logging.getLogger(__name__)


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


@extend_schema(
    tags=['v2'],
    summary='List batch operations',
    description='List all batch operations with optional filtering by status, type, and creator.',
    parameters=[
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
        - status: Filter by status (pending, queued, processing, completed, failed, cancelled)
        - operation_type: Filter by type (create, update, delete, query, install_extension)
        - created_by: Filter by creator username
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
# SSE Streaming
# =============================================================================

@extend_schema(
    tags=['v2'],
    summary='Stream operation events (SSE)',
    description='''
    Real-time Server-Sent Events (SSE) stream for operation progress updates.

    **Authentication:** Token must be passed via query parameter because EventSource
    does not support custom headers.

    **Event format:**
    ```
    data: {"state": "PROCESSING", "microservice": "worker", "message": "...", "timestamp": "..."}
    ```

    **States flow:** PENDING -> QUEUED -> PROCESSING -> UPLOADING -> INSTALLING -> VERIFYING -> SUCCESS/FAILED
    ''',
    parameters=[
        OpenApiParameter(
            name='operation_id',
            type=str,
            required=True,
            description='Operation ID (UUID) to stream events for'
        ),
        OpenApiParameter(
            name='token',
            type=str,
            required=True,
            description='JWT access token for authentication'
        ),
    ],
    responses={
        200: OpenApiResponse(description='SSE stream (text/event-stream)'),
        400: ErrorResponseSerializer,
        401: ErrorResponseSerializer,
        404: ErrorResponseSerializer,
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])  # Auth via token query param (EventSource limitation)
def operation_stream(request):
    """
    GET /api/v2/operations/stream/?operation_id=xxx&token=xxx

    SSE endpoint for real-time operation updates.

    NOTE: EventSource does not support custom headers, so token is passed via query parameter.

    Client connects via EventSource and receives events in real-time:
    - PENDING -> QUEUED -> PROCESSING -> UPLOADING -> INSTALLING -> VERIFYING -> SUCCESS/FAILED

    Event format:
        data: {"state": "PROCESSING", "microservice": "worker", "message": "...", "timestamp": "..."}
    """
    operation_id = request.query_params.get('operation_id')
    token = request.query_params.get('token')

    # Validate required parameters
    if not operation_id:
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'operation_id is required'
            }
        }, status=400)

    if not token:
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'token is required'
            }
        }, status=401)

    # Manual JWT authentication (EventSource limitation)
    try:
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        if not user:
            raise AuthenticationFailed('User not found')
    except Exception as e:
        logger.error(f"SSE authentication failed: {e}")
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'INVALID_TOKEN',
                'message': 'Invalid or expired token'
            }
        }, status=401)

    logger.info(f"SSE stream requested for operation {operation_id} by user {user.username}")

    def event_generator():
        """Generator for SSE events."""
        logger.info(f"event_generator: Starting for operation {operation_id}")

        # Connect to Redis PubSub
        redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
        redis_conn = redis_module.from_url(redis_url, decode_responses=True)
        pubsub = redis_conn.pubsub()
        channel = f"operation:{operation_id}:events"
        pubsub.subscribe(channel)
        logger.info(f"event_generator: Subscribed to channel {channel}")

        # Send initial state
        try:
            operation = BatchOperation.objects.get(id=operation_id)
            logger.info(f"event_generator: Found operation with status {operation.status}")
            initial_event = {
                "version": "1.0",
                "operation_id": str(operation_id),
                "timestamp": timezone.now().isoformat(),
                "state": operation.status.upper(),
                "microservice": "orchestrator",
                "message": f"Operation status: {operation.status}",
                "metadata": {
                    "operation_type": operation.operation_type,
                    "created_at": operation.created_at.isoformat()
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
            pubsub.unsubscribe()
            pubsub.close()
            redis_conn.close()
            return

        # Listen for events from Redis PubSub
        try:
            for message in pubsub.listen():
                if message['type'] == 'message':
                    # Forward event to client
                    yield f"data: {message['data']}\n\n"
        except GeneratorExit:
            # Client disconnected
            logger.info(f"Client disconnected from SSE stream for operation {operation_id}")
        finally:
            pubsub.unsubscribe()
            pubsub.close()
            redis_conn.close()

    response = StreamingHttpResponse(
        event_generator(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
    return response
