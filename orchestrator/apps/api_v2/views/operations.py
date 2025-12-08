"""
Operation endpoints for API v2.

Provides action-based endpoints for batch operations management.
"""

import logging

from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.operations.models import BatchOperation, Task
from apps.operations.serializers import BatchOperationSerializer, TaskSerializer

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
