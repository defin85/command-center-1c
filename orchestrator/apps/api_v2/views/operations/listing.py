"""Operations endpoints: list/get/cancel."""

from __future__ import annotations

import logging

from django.db.models import Count, F, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.databases.models import Database, PermissionLevel
from apps.databases.services import PermissionService
from apps.operations.models import BatchOperation, Task
from apps.operations.serializers import BatchOperationSerializer, TaskSerializer

from .access import resolve_operation_access
from .filtering import (
    OPERATION_FILTER_FIELDS,
    OPERATION_SORT_FIELDS,
    TASK_FILTER_FIELDS,
    TASK_SORT_FIELDS,
    _apply_filters,
    _apply_sort,
    _parse_filters,
    _parse_sort,
)
from .schemas import (
    CancelOperationRequestSerializer,
    OperationCancelResponseSerializer,
    OperationDetailResponseSerializer,
    OperationErrorResponseSerializer,
    OperationListResponseSerializer,
)

logger = logging.getLogger(__name__)

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
            description='Filter by type (create, update, delete, query, designer_cli)'
        ),
        OpenApiParameter(
            name='created_by',
            type=str,
            required=False,
            description='Filter by creator username'
        ),
        OpenApiParameter(
            name='search',
            type=str,
            required=False,
            description='Search by name, description, or ID'
        ),
        OpenApiParameter(
            name='filters',
            type=str,
            required=False,
            description='JSON object with filter conditions'
        ),
        OpenApiParameter(
            name='sort',
            type=str,
            required=False,
            description='JSON object with sort configuration'
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
        400: OperationErrorResponseSerializer,
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
        - operation_type: Filter by type (create, update, delete, query, designer_cli)
        - created_by: Filter by creator username
        - search: Search by name, description, or ID
        - filters: JSON object with filter conditions
        - sort: JSON object with sort configuration
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
    search = request.query_params.get('search')
    raw_filters = request.query_params.get('filters')
    raw_sort = request.query_params.get('sort')

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
        operation_id = operation_id.strip()
    if operation_id:
        qs = qs.filter(id__iexact=operation_id)
    if workflow_execution_id:
        qs = qs.filter(metadata__workflow_execution_id=workflow_execution_id)
    if node_id:
        qs = qs.filter(metadata__node_id=node_id)

    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(description__icontains=search)
            | Q(id__icontains=search)
            | Q(created_by__icontains=search)
        )

    filters_payload, filters_error = _parse_filters(raw_filters)
    if filters_error:
        return Response({"success": False, "error": filters_error}, status=400)
    if filters_payload:
        qs, apply_error = _apply_filters(qs, filters_payload, OPERATION_FILTER_FIELDS)
        if apply_error:
            return Response({"success": False, "error": apply_error}, status=400)

    sort_payload, sort_error = _parse_sort(raw_sort)
    if sort_error:
        return Response({"success": False, "error": sort_error}, status=400)
    if sort_payload:
        qs, apply_sort_error = _apply_sort(qs, sort_payload, OPERATION_SORT_FIELDS)
        if apply_sort_error:
            return Response({"success": False, "error": apply_sort_error}, status=400)
    else:
        # Order by most recent first
        qs = qs.order_by('-created_at')

    if not request.user.is_staff:
        accessible_db_ids = PermissionService.filter_accessible_databases(
            request.user,
            Database.objects.all(),
            PermissionLevel.VIEW,
        ).values_list("id", flat=True)

        qs = qs.annotate(
            total_db_count=Count("target_databases", distinct=True),
            accessible_db_count=Count(
                "target_databases",
                filter=Q(target_databases__id__in=accessible_db_ids),
                distinct=True,
            ),
        ).filter(
            Q(created_by=request.user.username)
            | Q(total_db_count=F("accessible_db_count"), total_db_count__gt=0)
        )

    total = qs.count()
    qs = qs[offset:offset + limit]

    serializer = BatchOperationSerializer(qs, many=True, context={"request": request})

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
            description='Include task details (default: true)'
        ),
        OpenApiParameter(
            name='task_limit',
            type=int,
            required=False,
            description='Maximum tasks returned (default: 100)'
        ),
        OpenApiParameter(
            name='task_offset',
            type=int,
            required=False,
            description='Task pagination offset (default: 0)'
        ),
        OpenApiParameter(
            name='task_filters',
            type=str,
            required=False,
            description='JSON object with task filter conditions'
        ),
        OpenApiParameter(
            name='task_sort',
            type=str,
            required=False,
            description='JSON object with task sort configuration'
        ),
    ],
    responses={
        200: OperationDetailResponseSerializer,
        400: OperationErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: OperationErrorResponseSerializer,
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
        - task_limit: Maximum tasks returned (default: 100)
        - task_offset: Task pagination offset (default: 0)
        - task_filters: JSON object with task filter conditions
        - task_sort: JSON object with task sort configuration

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
    raw_task_filters = request.query_params.get('task_filters')
    raw_task_sort = request.query_params.get('task_sort')

    try:
        task_limit = int(request.query_params.get('task_limit', 100))
    except (TypeError, ValueError):
        task_limit = 100
    task_limit = max(1, min(task_limit, 500))

    try:
        task_offset = int(request.query_params.get('task_offset', 0))
    except (TypeError, ValueError):
        task_offset = 0
    task_offset = max(0, task_offset)

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

    allowed, _denied = resolve_operation_access(request.user, [operation])
    if str(operation.id) not in allowed:
        return Response({
            'success': False,
            'error': {
                'code': 'FORBIDDEN',
                'message': 'You do not have permission to view this operation',
            }
        }, status=403)

    serializer = BatchOperationSerializer(operation, context={"request": request})

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

    if getattr(request.user, "is_staff", False):
        metadata = operation.metadata if isinstance(operation.metadata, dict) else {}
        execution_plan = metadata.get("execution_plan")
        bindings = metadata.get("bindings")
        if isinstance(execution_plan, dict):
            response_data["execution_plan"] = execution_plan
        if isinstance(bindings, list):
            response_data["bindings"] = bindings

    if include_tasks:
        tasks_qs = tasks

        task_filters_payload, task_filters_error = _parse_filters(raw_task_filters)
        if task_filters_error:
            return Response({"success": False, "error": task_filters_error}, status=400)
        if task_filters_payload:
            tasks_qs, apply_error = _apply_filters(tasks_qs, task_filters_payload, TASK_FILTER_FIELDS)
            if apply_error:
                return Response({"success": False, "error": apply_error}, status=400)

        task_sort_payload, task_sort_error = _parse_sort(raw_task_sort)
        if task_sort_error:
            return Response({"success": False, "error": task_sort_error}, status=400)
        if task_sort_payload:
            tasks_qs, apply_sort_error = _apply_sort(tasks_qs, task_sort_payload, TASK_SORT_FIELDS)
            if apply_sort_error:
                return Response({"success": False, "error": apply_sort_error}, status=400)

        task_serializer = TaskSerializer(tasks_qs[task_offset:task_offset + task_limit], many=True, context={"request": request})
        response_data['tasks'] = task_serializer.data

    return Response(response_data)


@extend_schema(
    tags=['v2'],
    summary='Cancel operation',
    description='Cancel a running or pending operation. Already completed or cancelled operations cannot be cancelled.',
    request=CancelOperationRequestSerializer,
    responses={
        200: OperationCancelResponseSerializer,
        400: OperationErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: OperationErrorResponseSerializer,
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

    if not request.user.is_staff and operation.created_by != request.user.username:
        target_ids = list(operation.target_databases.values_list("id", flat=True))
        if not target_ids:
            return Response({
                'success': False,
                'error': {
                    'code': 'FORBIDDEN',
                    'message': 'You do not have permission to cancel this operation',
                }
            }, status=403)

        allowed, denied = PermissionService.check_bulk_permission(
            request.user,
            [str(db_id) for db_id in target_ids],
            PermissionLevel.MANAGE,
        )
        if not allowed:
            denied_str = ", ".join(denied[:5])
            msg = f"Access denied for databases: {denied_str}"
            if len(denied) > 5:
                msg += f" and {len(denied) - 5} more"
            return Response({
                'success': False,
                'error': {
                    'code': 'FORBIDDEN',
                    'message': msg,
                }
            }, status=403)

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

