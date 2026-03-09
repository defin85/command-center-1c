"""Workflow template endpoints (list/get/execute)."""

from __future__ import annotations

import logging

from django.db.models import Count, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse


from apps.core import permission_codes as perms
from apps.databases.models import PermissionLevel
from apps.templates.rbac import TemplatePermissionService
from apps.templates.workflow.models import WorkflowCategory, WorkflowTemplate, WorkflowExecution
from apps.templates.workflow.serializers import (
    WorkflowTemplateListSerializer,
    WorkflowTemplateDetailSerializer,
    WorkflowExecutionListSerializer,
)
from apps.api_v2.serializers.common import ErrorResponseSerializer
from apps.operations.utils.feature_flags import (
    is_production_execution_profile,
    is_workflow_debug_fallback_enabled,
)
from apps.templates.workflow.authoring_phase import get_workflow_authoring_phase_summary
from apps.templates.workflow.management_mode import (
    WORKFLOW_SYSTEM_MANAGED_READ_ONLY_CODE,
    WORKFLOW_SYSTEM_MANAGED_READ_ONLY_REASON,
    WORKFLOW_VISIBILITY_SURFACE_LIBRARY,
    WORKFLOW_VISIBILITY_SURFACE_RUNTIME_DIAGNOSTICS,
    is_system_managed_workflow,
)

from .common import (
    _apply_filters,
    _apply_sort,
    _is_sensitive_key,
    _mask_json_dict,
    _parse_filters,
    _parse_sort,
    _permission_denied,
    ExecuteWorkflowRequestSerializer,
    ExecuteWorkflowResponseSerializer,
    WorkflowEnqueueFailClosedErrorResponseSerializer,
    WorkflowDetailResponseSerializer,
    WorkflowListResponseSerializer,
)

logger = logging.getLogger(__name__)


def _build_workflow_enqueue_fail_closed_response(
    *,
    execution_id: str,
    enqueue_error_code: str | None = None,
) -> Response:
    details = {"execution_id": execution_id}
    normalized_code = str(enqueue_error_code or "").strip()
    if normalized_code:
        details["enqueue_error_code"] = normalized_code
    return Response(
        {
            "success": False,
            "error": {
                "code": "WORKFLOW_ENQUEUE_FAILED",
                "message": "Failed to enqueue workflow execution",
                "details": details,
            },
        },
        status=503,
    )

@extend_schema(
    tags=['v2'],
    summary='List workflow templates',
    description='List all workflow templates with optional filtering by type, active status, and search.',
    parameters=[
        OpenApiParameter(
            name='workflow_type', type=str, required=False,
            description='Filter by workflow type (general, user_management, database_ops, etc.)'
        ),
        OpenApiParameter(
            name='is_active', type=str, required=False,
            description='Filter by active status (true/false)'
        ),
        OpenApiParameter(
            name='is_valid', type=str, required=False,
            description='Filter by validation status (true/false)'
        ),
        OpenApiParameter(
            name='search', type=str, required=False,
            description='Search by name or description'
        ),
        OpenApiParameter(
            name='surface', type=str, required=False,
            description='Visibility surface: workflow_library (default) or runtime_diagnostics'
        ),
        OpenApiParameter(
            name='filters', type=str, required=False,
            description='JSON object with filter conditions'
        ),
        OpenApiParameter(
            name='sort', type=str, required=False,
            description='JSON object with sort configuration'
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
        200: WorkflowListResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
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
        - filters: JSON object with filter conditions
        - sort: JSON object with sort configuration
        - limit: Maximum results (default: 50)
        - offset: Pagination offset (default: 0)

    Response:
        {
            "workflows": [...],
            "count": 50,
            "total": 100
        }
    """
    if not request.user.has_perm(perms.PERM_TEMPLATES_VIEW_WORKFLOW_TEMPLATE):
        return _permission_denied("You do not have permission to view workflows.")

    workflow_type = request.query_params.get('workflow_type')
    is_active = request.query_params.get('is_active')
    is_valid = request.query_params.get('is_valid')
    search = request.query_params.get('search')
    surface = str(
        request.query_params.get('surface') or WORKFLOW_VISIBILITY_SURFACE_LIBRARY
    ).strip() or WORKFLOW_VISIBILITY_SURFACE_LIBRARY
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

    qs = WorkflowTemplate.objects.annotate(
        _execution_count=Count('executions')
    )

    system_managed_filter = Q(
        category=WorkflowCategory.SYSTEM,
        is_template=False,
    )
    if surface == WORKFLOW_VISIBILITY_SURFACE_RUNTIME_DIAGNOSTICS:
        qs = qs.filter(system_managed_filter)
    else:
        qs = qs.exclude(system_managed_filter)

    if workflow_type:
        qs = qs.filter(workflow_type=workflow_type)
    if is_active is not None:
        qs = qs.filter(is_active=is_active.lower() == 'true')
    if is_valid is not None:
        qs = qs.filter(is_valid=is_valid.lower() == 'true')
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))

    filters_payload, filters_error = _parse_filters(raw_filters)
    if filters_error:
        return Response({"success": False, "error": filters_error}, status=400)
    if filters_payload:
        qs, apply_error = _apply_filters(qs, filters_payload)
        if apply_error:
            return Response({"success": False, "error": apply_error}, status=400)

    sort_payload, sort_error = _parse_sort(raw_sort)
    if sort_error:
        return Response({"success": False, "error": sort_error}, status=400)
    if sort_payload:
        qs, apply_sort_error = _apply_sort(qs, sort_payload)
        if apply_sort_error:
            return Response({"success": False, "error": apply_sort_error}, status=400)
    else:
        qs = qs.order_by('-created_at')

    if not request.user.is_staff:
        qs = TemplatePermissionService.filter_accessible_workflow_templates(
            request.user,
            qs,
            min_level=PermissionLevel.VIEW,
        )

    total = qs.count()
    qs = qs[offset:offset + limit]

    serializer = WorkflowTemplateListSerializer(qs, many=True)
    authoring_phase = get_workflow_authoring_phase_summary(
        tenant_id=str(getattr(getattr(request, "tenant", None), "id", "") or "") or None
    )

    return Response({
        'workflows': serializer.data,
        'authoring_phase': authoring_phase,
        'count': len(serializer.data),
        'total': total,
    })


@extend_schema(
    tags=['v2'],
    summary='Get workflow template details',
    description='Get detailed information about a specific workflow template including statistics and recent executions.',
    parameters=[
        OpenApiParameter(
            name='workflow_id', type=str, required=True,
            description='Workflow template UUID'
        ),
        OpenApiParameter(
            name='include_executions', type=str, required=False,
            description='Include recent executions (default: true)'
        ),
    ],
    responses={
        200: WorkflowDetailResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
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

    if not request.user.has_perm(perms.PERM_TEMPLATES_VIEW_WORKFLOW_TEMPLATE, workflow):
        return _permission_denied("You do not have permission to access this workflow.")

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


@extend_schema(
    tags=['v2'],
    summary='Execute workflow',
    description=(
        'Execute a workflow template. '
        'Sync mode is blocking. '
        'Async production profile is queue-only with fail-closed enqueue errors. '
        'Workflow enqueue uses transactional outbox; root operation projection is queued only after dispatch succeeds. '
        'Local debug fallback is available only with explicit non-production flag.'
    ),
    request=ExecuteWorkflowRequestSerializer,
    responses={
        200: ExecuteWorkflowResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
        503: WorkflowEnqueueFailClosedErrorResponseSerializer,
        500: ErrorResponseSerializer,
    }
)
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
    raw_input_context = request.data.get('input_context', {}) or {}
    mode = request.data.get('mode', 'async')

    if not isinstance(raw_input_context, dict):
        return Response({
            'success': False,
            'error': {
                'code': 'INVALID_INPUT_CONTEXT',
                'message': 'input_context must be a JSON object',
            }
        }, status=400)

    input_context = dict(raw_input_context)

    executed_by_username = None
    if request.user and getattr(request.user, "is_authenticated", False):
        executed_by_username = request.user.get_username() or request.user.username
        input_context["executed_by"] = executed_by_username

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

    if not request.user.has_perm(perms.PERM_TEMPLATES_EXECUTE_WORKFLOW_TEMPLATE, workflow):
        return _permission_denied("You do not have permission to execute this workflow.")
    if is_system_managed_workflow(workflow):
        return Response(
            {
                'success': False,
                'error': {
                    'code': WORKFLOW_SYSTEM_MANAGED_READ_ONLY_CODE,
                    'message': WORKFLOW_SYSTEM_MANAGED_READ_ONLY_REASON,
                }
            },
            status=409,
        )

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
        if mode == 'sync':
            # Execute synchronously (blocking)
            try:
                from apps.templates.workflow.engine import WorkflowEngine
                engine = WorkflowEngine()
                execution = engine.execute_workflow_sync(workflow, input_context)
                try:
                    raw_database_ids = input_context.get("database_ids")
                    database_ids = raw_database_ids if isinstance(raw_database_ids, list) else []

                    bindings = [
                        {
                            "target_ref": "workflow_id",
                            "source_ref": "request.workflow_id",
                            "resolve_at": "api",
                            "sensitive": False,
                            "status": "applied",
                        },
                    ]
                    for key in sorted(input_context.keys()):
                        if key == "executed_by" and executed_by_username:
                            bindings.append(
                                {
                                    "target_ref": "input_context.executed_by",
                                    "source_ref": "api.user.username",
                                    "resolve_at": "api",
                                    "sensitive": False,
                                    "status": "applied",
                                }
                            )
                            continue
                        bindings.append(
                            {
                                "target_ref": f"input_context.{key}",
                                "source_ref": f"request.input_context.{key}",
                                "resolve_at": "api",
                                "sensitive": _is_sensitive_key(str(key)),
                                "status": "applied",
                            }
                        )

                    execution.execution_plan = {
                        "kind": "workflow",
                        "plan_version": 1,
                        "workflow_id": str(workflow_id),
                        "input_context_masked": _mask_json_dict(input_context),
                        "targets": {"database_ids_count": len(database_ids)},
                    }
                    execution.bindings = bindings
                    execution.save(update_fields=["execution_plan", "bindings"])
                except Exception:
                    pass

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
                    'execution_id': None,
                    'status': WorkflowExecution.STATUS_FAILED,
                    'mode': 'sync',
                    'error_message': str(e),
                    'message': 'Workflow execution failed',
                }, status=500)

        # Execute asynchronously via unified enqueue contract with optional debug fallback.
        execution = workflow.create_execution(input_context)
        try:
            raw_database_ids = input_context.get("database_ids")
            database_ids = raw_database_ids if isinstance(raw_database_ids, list) else []

            bindings = [
                {
                    "target_ref": "workflow_id",
                    "source_ref": "request.workflow_id",
                    "resolve_at": "api",
                    "sensitive": False,
                    "status": "applied",
                },
            ]
            for key in sorted(input_context.keys()):
                if key == "executed_by" and executed_by_username:
                    bindings.append(
                        {
                            "target_ref": "input_context.executed_by",
                            "source_ref": "api.user.username",
                            "resolve_at": "api",
                            "sensitive": False,
                            "status": "applied",
                        }
                    )
                    continue
                bindings.append(
                    {
                        "target_ref": f"input_context.{key}",
                        "source_ref": f"request.input_context.{key}",
                        "resolve_at": "api",
                        "sensitive": _is_sensitive_key(str(key)),
                        "status": "applied",
                    }
                )

            execution.execution_plan = {
                "kind": "workflow",
                "plan_version": 1,
                "workflow_id": str(workflow_id),
                "input_context_masked": _mask_json_dict(input_context),
                "targets": {"database_ids_count": len(database_ids)},
            }
            execution.bindings = bindings
            execution.save(update_fields=["execution_plan", "bindings"])
        except Exception:
            # Best-effort: never block execution because of plan/provenance generation
            pass

        from apps.operations.services import OperationsService

        production_profile = is_production_execution_profile()
        debug_fallback_enabled = is_workflow_debug_fallback_enabled()
        allow_local_debug_fallback = debug_fallback_enabled and not production_profile
        enqueue_mode = "async_go_worker_production" if production_profile else "async_go_worker"

        try:
            result = OperationsService.enqueue_workflow_execution(str(execution.id))
        except Exception:
            logger.exception(
                "Workflow enqueue failed",
                extra={
                    'execution_id': str(execution.id),
                    'workflow_id': str(workflow_id),
                    'executed_by': request.user.username if request.user else 'anonymous',
                    'mode': enqueue_mode,
                    'profile': 'production' if production_profile else 'non_production',
                },
            )
            if not allow_local_debug_fallback:
                return _build_workflow_enqueue_fail_closed_response(
                    execution_id=str(execution.id),
                    enqueue_error_code="GO_WORKER_UNAVAILABLE",
                )
            result = None

        if result is not None and result.success:
            logger.info(
                "Workflow execution started via Go Worker",
                extra={
                    'execution_id': str(execution.id),
                    'workflow_id': str(workflow_id),
                    'executed_by': request.user.username if request.user else 'anonymous',
                    'mode': enqueue_mode,
                    'profile': 'production' if production_profile else 'non_production',
                    'operation_id': result.operation_id,
                },
            )
            return Response({
                'execution_id': str(execution.id),
                'status': 'pending',
                'mode': 'async',
                'operation_id': result.operation_id,
                'message': 'Workflow execution started (Go Worker)',
            })

        if result is not None:
            logger.warning(
                "Workflow enqueue rejected",
                extra={
                    'execution_id': str(execution.id),
                    'workflow_id': str(workflow_id),
                    'executed_by': request.user.username if request.user else 'anonymous',
                    'mode': enqueue_mode,
                    'profile': 'production' if production_profile else 'non_production',
                    'enqueue_error_code': result.error_code,
                    'debug_fallback_enabled': allow_local_debug_fallback,
                },
            )
            if not allow_local_debug_fallback:
                return _build_workflow_enqueue_fail_closed_response(
                    execution_id=str(execution.id),
                    enqueue_error_code=result.error_code,
                )

        if not allow_local_debug_fallback:
            return _build_workflow_enqueue_fail_closed_response(
                execution_id=str(execution.id),
                enqueue_error_code="LOCAL_FALLBACK_DISABLED",
            )

        # Async fallback: execute in-process without blocking the request.
        # Celery is removed; this is a lightweight background runner for dev/hybrid mode.
        # NOTE: keep lookup via package attribute so tests can patch
        # `apps.api_v2.views.workflows._start_async_workflow_execution`.
        import apps.api_v2.views.workflows as workflows_view

        if workflows_view._start_async_workflow_execution(str(execution.id)):
            return Response({
                'execution_id': str(execution.id),
                'status': 'pending',
                'mode': 'async',
                'message': 'Workflow execution started (Orchestrator background runner)',
            })

        # Last resort: synchronous fallback execution
        from apps.templates.workflow.engine import WorkflowEngine
        engine = WorkflowEngine()
        engine.execute_sync(execution)

        logger.info(
            "Workflow executed synchronously (fallback)",
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
            'message': 'Workflow executed synchronously (async worker unavailable)',
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
