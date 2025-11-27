"""
Workflow endpoints for API v2.

Provides action-based endpoints for workflow management.
"""

import logging

from django.db.models import Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.templates.workflow.models import WorkflowTemplate, WorkflowExecution
from apps.templates.workflow.serializers import (
    WorkflowTemplateListSerializer,
    WorkflowTemplateDetailSerializer,
    WorkflowExecutionListSerializer,
)

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_workflows(request):
    """
    GET /api/v2/workflows/list-workflows/

    List all workflow templates with optional filtering.

    Query Parameters:
        - workflow_type: Filter by type (general, user_management, database_ops, etc.)
        - is_active: Filter by active status (true/false)
        - is_valid: Filter by valid status (true/false)
        - search: Search by name or description
        - limit: Maximum results (default: 50)
        - offset: Pagination offset (default: 0)

    Response:
        {
            "workflows": [...],
            "count": 50,
            "total": 100
        }
    """
    workflow_type = request.query_params.get('workflow_type')
    is_active = request.query_params.get('is_active')
    is_valid = request.query_params.get('is_valid')
    search = request.query_params.get('search')

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

    qs = WorkflowTemplate.objects.annotate(
        _execution_count=Count('executions')
    )

    if workflow_type:
        qs = qs.filter(workflow_type=workflow_type)
    if is_active is not None:
        qs = qs.filter(is_active=is_active.lower() == 'true')
    if is_valid is not None:
        qs = qs.filter(is_valid=is_valid.lower() == 'true')
    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    qs = qs.order_by('-created_at')

    total = qs.count()
    qs = qs[offset:offset + limit]

    serializer = WorkflowTemplateListSerializer(qs, many=True)

    return Response({
        'workflows': serializer.data,
        'count': len(serializer.data),
        'total': total,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_workflow(request):
    """
    GET /api/v2/workflows/get-workflow/?workflow_id=X

    Get detailed information about a specific workflow template.

    Query Parameters:
        - workflow_id: Workflow template UUID (required)
        - include_executions: Include recent executions (default: true)

    Response:
        {
            "workflow": {...},
            "executions": [...],
            "statistics": {
                "total_executions": 100,
                "successful": 90,
                "failed": 10,
                "average_duration": 120.5
            }
        }
    """
    workflow_id = request.query_params.get('workflow_id')
    include_executions = request.query_params.get('include_executions', 'true').lower() == 'true'

    if not workflow_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'workflow_id is required'
            }
        }, status=400)

    try:
        workflow = WorkflowTemplate.objects.prefetch_related('executions').get(id=workflow_id)
    except WorkflowTemplate.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'WORKFLOW_NOT_FOUND',
                'message': 'Workflow not found'
            }
        }, status=404)

    serializer = WorkflowTemplateDetailSerializer(workflow)

    # Calculate statistics
    executions = workflow.executions.all()
    completed_execs = executions.filter(status=WorkflowExecution.STATUS_COMPLETED)

    # Calculate average duration
    durations = [e.duration for e in completed_execs if e.duration is not None]
    avg_duration = sum(durations) / len(durations) if durations else None

    statistics = {
        'total_executions': executions.count(),
        'successful': completed_execs.count(),
        'failed': executions.filter(status=WorkflowExecution.STATUS_FAILED).count(),
        'cancelled': executions.filter(status=WorkflowExecution.STATUS_CANCELLED).count(),
        'running': executions.filter(status=WorkflowExecution.STATUS_RUNNING).count(),
        'average_duration': round(avg_duration, 2) if avg_duration else None,
    }

    response_data = {
        'workflow': serializer.data,
        'statistics': statistics,
    }

    if include_executions:
        recent_executions = executions.order_by('-started_at')[:10]
        exec_serializer = WorkflowExecutionListSerializer(recent_executions, many=True)
        response_data['executions'] = exec_serializer.data

    return Response(response_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def execute_workflow(request):
    """
    POST /api/v2/workflows/execute-workflow/

    Execute a workflow template.

    Request Body:
        {
            "workflow_id": "uuid",
            "input_context": {...},
            "mode": "async"  // "sync" or "async"
        }

    Response:
        {
            "execution_id": "uuid",
            "status": "pending|running",
            "mode": "async",
            "message": "Workflow execution started"
        }
    """
    workflow_id = request.data.get('workflow_id')
    input_context = request.data.get('input_context', {})
    mode = request.data.get('mode', 'async')

    if not workflow_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'workflow_id is required'
            }
        }, status=400)

    try:
        workflow = WorkflowTemplate.objects.get(id=workflow_id)
    except WorkflowTemplate.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'WORKFLOW_NOT_FOUND',
                'message': 'Workflow not found'
            }
        }, status=404)

    # Validate workflow is executable
    if not workflow.is_active:
        return Response({
            'success': False,
            'error': {
                'code': 'WORKFLOW_NOT_ACTIVE',
                'message': 'Workflow is not active',
                'workflow_id': str(workflow_id)
            }
        }, status=400)

    if not workflow.is_valid:
        return Response({
            'success': False,
            'error': {
                'code': 'WORKFLOW_NOT_VALID',
                'message': 'Workflow is not validated',
                'workflow_id': str(workflow_id)
            }
        }, status=400)

    try:
        # Create execution instance
        execution = workflow.create_execution(input_context)

        if mode == 'sync':
            # Execute synchronously (blocking)
            try:
                from apps.templates.workflow.engine import WorkflowEngine
                engine = WorkflowEngine()
                engine.execute(execution)

                # Audit logging
                logger.info(
                    "Workflow executed synchronously",
                    extra={
                        'execution_id': str(execution.id),
                        'workflow_id': str(workflow_id),
                        'executed_by': request.user.username if request.user else 'anonymous',
                        'mode': 'sync',
                        'status': execution.status,
                    }
                )

                return Response({
                    'execution_id': str(execution.id),
                    'status': execution.status,
                    'mode': 'sync',
                    'final_result': execution.final_result,
                    'duration': execution.duration,
                    'message': 'Workflow execution completed',
                })
            except Exception as e:
                logger.error(f"Sync workflow execution failed: {e}")
                return Response({
                    'execution_id': str(execution.id),
                    'status': execution.status,
                    'mode': 'sync',
                    'error_message': str(e),
                    'message': 'Workflow execution failed',
                }, status=500)
        else:
            # Execute asynchronously via Celery
            try:
                from apps.templates.workflow.tasks import execute_workflow_task
                task = execute_workflow_task.delay(str(execution.id))

                # Audit logging
                logger.info(
                    "Workflow execution started asynchronously",
                    extra={
                        'execution_id': str(execution.id),
                        'workflow_id': str(workflow_id),
                        'executed_by': request.user.username if request.user else 'anonymous',
                        'mode': 'async',
                        'celery_task_id': task.id,
                    }
                )

                return Response({
                    'execution_id': str(execution.id),
                    'status': 'pending',
                    'mode': 'async',
                    'celery_task_id': task.id,
                    'message': 'Workflow execution started',
                })
            except Exception as e:
                logger.warning(f"Celery unavailable, falling back to sync: {e}")
                logger.warning("Workflow executed synchronously due to Celery unavailability")
                # Fallback to sync execution
                from apps.templates.workflow.engine import WorkflowEngine
                engine = WorkflowEngine()
                engine.execute(execution)

                # Audit logging for fallback
                logger.info(
                    "Workflow executed synchronously (Celery fallback)",
                    extra={
                        'execution_id': str(execution.id),
                        'workflow_id': str(workflow_id),
                        'executed_by': request.user.username if request.user else 'anonymous',
                        'mode': 'sync_fallback',
                        'status': execution.status,
                    }
                )

                return Response({
                    'execution_id': str(execution.id),
                    'status': execution.status,
                    'mode': 'sync',
                    'message': 'Workflow executed synchronously (Celery unavailable)',
                })

    except ValueError as e:
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': str(e)
            }
        }, status=400)
    except Exception as e:
        logger.error(f"Failed to execute workflow: {e}")
        return Response({
            'success': False,
            'error': {
                'code': 'EXECUTION_ERROR',
                'message': 'Failed to execute workflow'
            }
        }, status=500)
