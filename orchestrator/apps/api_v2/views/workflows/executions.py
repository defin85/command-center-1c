"""Workflow execution endpoints."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import logging

from django.db import close_old_connections
from django.db.models import Count, Q
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

import uuid

from apps.core import permission_codes as perms
from apps.databases.models import PermissionLevel
from apps.templates.rbac import TemplatePermissionService
from apps.templates.workflow.models import WorkflowTemplate, WorkflowExecution, WorkflowStepResult
from apps.templates.workflow.serializers import (
    WorkflowTemplateListSerializer,
    WorkflowTemplateDetailSerializer,
    WorkflowExecutionListSerializer,
    WorkflowExecutionDetailSerializer,
    WorkflowStepResultSerializer,
)
from apps.api_v2.serializers.common import ErrorResponseSerializer, ExecutionBindingSerializer, ExecutionPlanSerializer
from apps.operations.utils.feature_flags import is_go_workflow_engine_enabled

logger = logging.getLogger(__name__)

from .common import (
    _permission_denied,
    ExecutionCancelRequestSerializer,
    ExecutionCancelResponseSerializer,
    ExecutionDetailResponseSerializer,
    ExecutionListResponseSerializer,
    ExecutionStepsResponseSerializer,
)

@extend_schema(
    tags=['v2'],
    summary='List workflow executions',
    description='List workflow executions with optional filtering by workflow template and status.',
    parameters=[
        OpenApiParameter(
            name='workflow_id', type=str, required=False,
            description='Filter by workflow template UUID'
        ),
        OpenApiParameter(
            name='status', type=str, required=False,
            description='Filter by status (pending, running, completed, failed, cancelled)'
        ),
        OpenApiParameter(
            name='limit', type=int, required=False,
            description='Maximum results (default: 50, max: 1000)'
        ),
        OpenApiParameter(
            name='offset', type=int, required=False,
            description='Pagination offset (default: 0)'
        ),
    ],
    responses={
        200: ExecutionListResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_executions(request):
    """
    GET /api/v2/workflows/list-executions/

    List workflow executions with optional filtering.

    Query Parameters:
        - workflow_id: Filter by workflow template UUID (optional)
        - status: Filter by status (pending, running, completed, failed, cancelled)
        - limit: Maximum results (default: 50, max: 1000)
        - offset: Pagination offset (default: 0)

    Response:
        {
            "executions": [...],
            "count": 50,
            "total": 100
        }
    """
    if not request.user.has_perm(perms.PERM_TEMPLATES_VIEW_WORKFLOW_TEMPLATE):
        return _permission_denied("You do not have permission to view workflows.")

    workflow_id = request.query_params.get('workflow_id')
    status_filter = request.query_params.get('status')

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

    # Validate workflow_id UUID format if provided
    if workflow_id:
        try:
            uuid.UUID(workflow_id)
        except ValueError:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_UUID',
                    'message': 'workflow_id must be a valid UUID'
                }
            }, status=400)

    # Validate status if provided
    valid_statuses = [
        WorkflowExecution.STATUS_PENDING,
        WorkflowExecution.STATUS_RUNNING,
        WorkflowExecution.STATUS_COMPLETED,
        WorkflowExecution.STATUS_FAILED,
        WorkflowExecution.STATUS_CANCELLED,
    ]
    if status_filter and status_filter not in valid_statuses:
        return Response({
            'success': False,
            'error': {
                'code': 'INVALID_STATUS',
                'message': f'status must be one of: {", ".join(valid_statuses)}'
            }
        }, status=400)

    # Build queryset with select_related for performance
    qs = WorkflowExecution.objects.select_related('workflow_template')

    if workflow_id:
        qs = qs.filter(workflow_template_id=workflow_id)
    if status_filter:
        qs = qs.filter(status=status_filter)

    qs = qs.order_by('-started_at')

    if not request.user.is_staff:
        qs = TemplatePermissionService.filter_accessible_workflow_executions(
            request.user,
            qs,
            min_level=PermissionLevel.VIEW,
        )

    total = qs.count()
    qs = qs[offset:offset + limit]

    serializer = WorkflowExecutionListSerializer(qs, many=True)

    logger.debug(
        "Listed workflow executions",
        extra={
            'user': request.user.username,
            'workflow_id': workflow_id,
            'status_filter': status_filter,
            'count': len(serializer.data),
            'total': total,
        }
    )

    return Response({
        'executions': serializer.data,
        'count': len(serializer.data),
        'total': total,
    })


@extend_schema(
    tags=['v2'],
    summary='Get execution details',
    description='Get detailed information about a specific workflow execution including step results.',
    parameters=[
        OpenApiParameter(
            name='execution_id', type=str, required=True,
            description='Execution UUID'
        ),
    ],
    responses={
        200: ExecutionDetailResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_execution(request):
    """
    GET /api/v2/workflows/get-execution/?execution_id=X

    Get detailed information about a specific workflow execution.

    Query Parameters:
        - execution_id: Execution UUID (required)

    Response:
        {
            "execution": {...},
            "steps": [...]
        }
    """
    execution_id = request.query_params.get('execution_id')

    if not execution_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'execution_id is required'
            }
        }, status=400)

    # Validate UUID format
    try:
        uuid.UUID(execution_id)
    except ValueError:
        return Response({
            'success': False,
            'error': {
                'code': 'INVALID_UUID',
                'message': 'execution_id must be a valid UUID'
            }
        }, status=400)

    try:
        execution = WorkflowExecution.objects.select_related(
            'workflow_template'
        ).prefetch_related(
            'step_results'
        ).get(id=execution_id)
    except WorkflowExecution.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'EXECUTION_NOT_FOUND',
                'message': 'Execution not found'
            }
        }, status=404)

    if not request.user.has_perm(perms.PERM_TEMPLATES_VIEW_WORKFLOW_TEMPLATE, execution):
        return _permission_denied("You do not have permission to access this execution.")

    execution_serializer = WorkflowExecutionDetailSerializer(execution)
    steps_serializer = WorkflowStepResultSerializer(
        execution.step_results.order_by('started_at'),
        many=True
    )

    logger.info(
        "Retrieved workflow execution details",
        extra={
            'user': request.user.username,
            'execution_id': str(execution_id),
            'status': execution.status,
        }
    )

    response_data = {
        'execution': execution_serializer.data,
        'steps': steps_serializer.data,
    }
    if getattr(request.user, "is_staff", False):
        if isinstance(getattr(execution, "execution_plan", None), dict) and execution.execution_plan:
            response_data["execution_plan"] = execution.execution_plan
        if isinstance(getattr(execution, "bindings", None), list) and execution.bindings:
            response_data["bindings"] = execution.bindings

    return Response(response_data)


@extend_schema(
    tags=['v2'],
    summary='Cancel execution',
    description='Cancel a running or pending workflow execution. Only pending or running executions can be cancelled.',
    request=ExecutionCancelRequestSerializer,
    responses={
        200: ExecutionCancelResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
        409: ErrorResponseSerializer,
        500: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_execution(request):
    """
    POST /api/v2/workflows/cancel-execution/

    Cancel a running or pending workflow execution.

    Request Body:
        {
            "execution_id": "uuid"
        }

    Response:
        {
            "execution_id": "uuid",
            "cancelled": true,
            "status": "cancelled",
            "message": "Execution cancelled successfully"
        }
    """
    execution_id = request.data.get('execution_id')

    if not execution_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'execution_id is required'
            }
        }, status=400)

    # Validate UUID format
    try:
        uuid.UUID(str(execution_id))
    except ValueError:
        return Response({
            'success': False,
            'error': {
                'code': 'INVALID_UUID',
                'message': 'execution_id must be a valid UUID'
            }
        }, status=400)

    try:
        execution = WorkflowExecution.objects.get(id=execution_id)
    except WorkflowExecution.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'EXECUTION_NOT_FOUND',
                'message': 'Execution not found'
            }
        }, status=404)

    if not request.user.has_perm(perms.PERM_TEMPLATES_EXECUTE_WORKFLOW_TEMPLATE, execution):
        return _permission_denied("You do not have permission to cancel this execution.")

    # Check if execution can be cancelled (FSM allows pending or running)
    cancellable_statuses = [
        WorkflowExecution.STATUS_PENDING,
        WorkflowExecution.STATUS_RUNNING,
    ]
    if execution.status not in cancellable_statuses:
        return Response({
            'success': False,
            'error': {
                'code': 'EXECUTION_NOT_CANCELLABLE',
                'message': f'Cannot cancel execution in status "{execution.status}". '
                           f'Only pending or running executions can be cancelled.'
            }
        }, status=409)

    # Save previous status BEFORE FSM transition
    previous_status = execution.status

    try:
        # Use FSM transition
        execution.cancel()
        execution.save()

        logger.info(
            "Workflow execution cancelled",
            extra={
                'user': request.user.username,
                'execution_id': str(execution_id),
                'previous_status': previous_status,
            }
        )

        return Response({
            'execution_id': str(execution.id),
            'cancelled': True,
            'status': execution.status,
            'message': 'Execution cancelled successfully',
        })

    except Exception:
        logger.exception("Failed to cancel execution")
        return Response({
            'success': False,
            'error': {
                'code': 'CANCEL_ERROR',
                'message': 'Failed to cancel execution. Please try again.'
            }
        }, status=500)


@extend_schema(
    tags=['v2'],
    summary='Get execution steps',
    description='Get all step results for a workflow execution with optional filtering by step status.',
    parameters=[
        OpenApiParameter(
            name='execution_id', type=str, required=True,
            description='Execution UUID'
        ),
        OpenApiParameter(
            name='status', type=str, required=False,
            description='Filter by step status (pending, running, completed, failed, skipped)'
        ),
    ],
    responses={
        200: ExecutionStepsResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_execution_steps(request):
    """
    GET /api/v2/workflows/get-execution-steps/?execution_id=X

    Get all step results for a workflow execution.

    Query Parameters:
        - execution_id: Execution UUID (required)
        - status: Filter by step status (optional)

    Response:
        {
            "steps": [...],
            "count": 5
        }
    """
    execution_id = request.query_params.get('execution_id')
    status_filter = request.query_params.get('status')

    if not execution_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'execution_id is required'
            }
        }, status=400)

    # Validate UUID format
    try:
        uuid.UUID(execution_id)
    except ValueError:
        return Response({
            'success': False,
            'error': {
                'code': 'INVALID_UUID',
                'message': 'execution_id must be a valid UUID'
            }
        }, status=400)

    # Validate status if provided
    valid_step_statuses = [
        WorkflowStepResult.STATUS_PENDING,
        WorkflowStepResult.STATUS_RUNNING,
        WorkflowStepResult.STATUS_COMPLETED,
        WorkflowStepResult.STATUS_FAILED,
        WorkflowStepResult.STATUS_SKIPPED,
    ]
    if status_filter and status_filter not in valid_step_statuses:
        return Response({
            'success': False,
            'error': {
                'code': 'INVALID_STATUS',
                'message': f'status must be one of: {", ".join(valid_step_statuses)}'
            }
        }, status=400)

    try:
        execution = WorkflowExecution.objects.select_related("workflow_template").get(
            id=execution_id
        )
    except WorkflowExecution.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'EXECUTION_NOT_FOUND',
                'message': 'Execution not found'
            }
        }, status=404)

    if not request.user.has_perm(perms.PERM_TEMPLATES_VIEW_WORKFLOW_TEMPLATE, execution):
        return _permission_denied("You do not have permission to access this execution.")

    # Build queryset
    qs = WorkflowStepResult.objects.filter(workflow_execution_id=execution_id)

    if status_filter:
        qs = qs.filter(status=status_filter)

    qs = qs.order_by('started_at')

    serializer = WorkflowStepResultSerializer(qs, many=True)

    logger.info(
        "Retrieved workflow execution steps",
        extra={
            'user': request.user.username,
            'execution_id': str(execution_id),
            'status_filter': status_filter,
            'count': len(serializer.data),
        }
    )

    return Response({
        'steps': serializer.data,
        'count': len(serializer.data),
    })


# ============================================================================
# Template Endpoints (Phase 5.1 - Operations Center)
# ============================================================================


class TemplateListItemSerializer(serializers.Serializer):
    """Serializer for template list items."""

    id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    category = serializers.CharField()
    icon = serializers.CharField()
    workflow_type = serializers.CharField()
    version_number = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class TemplateListResponseSerializer(serializers.Serializer):
    """Response for list_templates endpoint."""

    templates = TemplateListItemSerializer(many=True)
    count = serializers.IntegerField()


class TemplateSchemaResponseSerializer(serializers.Serializer):
    """Response for get_template_schema endpoint."""

    workflow_id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    category = serializers.CharField()
    icon = serializers.CharField()
    input_schema = serializers.DictField(allow_null=True)



