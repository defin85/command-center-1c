"""
Workflow endpoints for API v2.

Provides action-based endpoints for workflow management.
"""

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

_SENSITIVE_KEYS: set[str] = {
    "db_password",
    "db_pwd",
    "password",
    "secret",
    "token",
    "api_key",
    "access_key",
    "secret_key",
}


def _is_sensitive_key(key: str) -> bool:
    key_norm = (key or "").strip().lower()
    if not key_norm:
        return False
    if key_norm in _SENSITIVE_KEYS:
        return True
    if key_norm.endswith("_password") or key_norm.endswith("_pwd"):
        return True
    return False


def _mask_json_value(value):
    if isinstance(value, dict):
        return _mask_json_dict(value)
    if isinstance(value, list):
        return [_mask_json_value(item) for item in value]
    return value


def _mask_json_dict(data: dict):
    masked: dict = {}
    for key, value in data.items():
        key_str = str(key or "")
        if _is_sensitive_key(key_str):
            masked[key] = "***"
            continue
        masked[key] = _mask_json_value(value)
    return masked


def _permission_denied(message: str):
    return Response(
        {"success": False, "error": {"code": "PERMISSION_DENIED", "message": message}},
        status=403,
    )

_WORKFLOW_ASYNC_EXECUTOR = ThreadPoolExecutor(max_workers=4)


def _execute_workflow_in_background(execution_id: str) -> None:
    close_old_connections()
    try:
        from apps.templates.workflow.engine import WorkflowEngine

        execution = WorkflowExecution.objects.select_related('workflow_template').get(
            id=execution_id
        )
        engine = WorkflowEngine()
        engine.execute_sync(execution)
    except WorkflowExecution.DoesNotExist:
        logger.error(
            "Async workflow execution not found",
            extra={'execution_id': execution_id},
        )
    except Exception as exc:
        logger.exception(
            "Async workflow execution failed",
            extra={'execution_id': execution_id, 'error': str(exc)},
        )
    finally:
        close_old_connections()


def _start_async_workflow_execution(execution_id: str) -> bool:
    try:
        _WORKFLOW_ASYNC_EXECUTOR.submit(_execute_workflow_in_background, execution_id)
        return True
    except RuntimeError as exc:
        logger.error(
            "Async workflow executor unavailable",
            extra={'execution_id': execution_id, 'error': str(exc)},
        )
        return False


WORKFLOW_FILTER_FIELDS = {
    "name": {"field": "name", "type": "text"},
    "workflow_type": {"field": "workflow_type", "type": "enum"},
    "is_active": {"field": "is_active", "type": "bool"},
    "is_valid": {"field": "is_valid", "type": "bool"},
    "updated_at": {"field": "updated_at", "type": "datetime"},
}

WORKFLOW_SORT_FIELDS = {
    "name": "name",
    "workflow_type": "workflow_type",
    "is_active": "is_active",
    "updated_at": "updated_at",
    "created_at": "created_at",
}


def _parse_filters(raw_filters: str | None) -> tuple[dict, dict | None]:
    if not raw_filters:
        return {}, None
    try:
        payload = json.loads(raw_filters)
    except json.JSONDecodeError:
        return {}, {
            "code": "INVALID_FILTERS",
            "message": "filters must be valid JSON object",
        }
    if not isinstance(payload, dict):
        return {}, {
            "code": "INVALID_FILTERS",
            "message": "filters must be a JSON object",
        }
    return payload, None


def _parse_sort(raw_sort: str | None) -> tuple[dict | None, dict | None]:
    if not raw_sort:
        return None, None
    try:
        payload = json.loads(raw_sort)
    except json.JSONDecodeError:
        return None, {
            "code": "INVALID_SORT",
            "message": "sort must be valid JSON object",
        }
    if not isinstance(payload, dict):
        return None, {
            "code": "INVALID_SORT",
            "message": "sort must be a JSON object",
        }
    return payload, None


def _apply_text_filter(qs, field: str, op: str, value: str):
    if op == "contains":
        return qs.filter(**{f"{field}__icontains": value})
    if op == "eq":
        return qs.filter(**{field: value})
    return qs


def _apply_datetime_filter(qs, field: str, op: str, value: str):
    from django.utils.dateparse import parse_datetime
    parsed = parse_datetime(value)
    if op in ("contains", "eq") and parsed is None:
        return qs.filter(**{f"{field}__icontains": value})
    if parsed:
        if op == "eq":
            return qs.filter(**{f"{field}__date": parsed.date()})
        if op == "before":
            return qs.filter(**{f"{field}__date__lt": parsed.date()})
        if op == "after":
            return qs.filter(**{f"{field}__date__gt": parsed.date()})
    return qs


def _apply_enum_filter(qs, field: str, op: str, value):
    if op == "in" and isinstance(value, list):
        return qs.filter(**{f"{field}__in": value})
    return qs.filter(**{field: value})


def _apply_bool_filter(qs, field: str, value):
    if isinstance(value, bool):
        return qs.filter(**{field: value})
    if isinstance(value, str):
        return qs.filter(**{field: value.lower() in ("true", "1", "yes")})
    return qs


def _apply_filters(qs, filters: dict) -> tuple:
    for key, payload in filters.items():
        if key not in WORKFLOW_FILTER_FIELDS:
            return qs, {
                "code": "UNKNOWN_FILTER",
                "message": f"Unknown filter key: {key}",
            }
        value = payload
        op = "eq"
        if isinstance(payload, dict):
            op = payload.get("op", "eq")
            value = payload.get("value")
        if value in (None, ""):
            continue
        config = WORKFLOW_FILTER_FIELDS[key]
        field = config["field"]
        field_type = config["type"]
        if field_type == "text":
            qs = _apply_text_filter(qs, field, op, str(value))
        elif field_type == "enum":
            qs = _apply_enum_filter(qs, field, op, value)
        elif field_type == "bool":
            qs = _apply_bool_filter(qs, field, value)
        elif field_type == "datetime":
            qs = _apply_datetime_filter(qs, field, op, str(value))
    return qs, None


def _apply_sort(qs, sort_payload: dict | None) -> tuple:
    if not sort_payload:
        return qs, None
    key = sort_payload.get("key")
    order = sort_payload.get("order")
    if key not in WORKFLOW_SORT_FIELDS:
        return qs, {
            "code": "UNKNOWN_SORT",
            "message": f"Unknown sort key: {key}",
        }
    field = WORKFLOW_SORT_FIELDS[key]
    if order == "desc":
        return qs.order_by(f"-{field}"), None
    if order == "asc":
        return qs.order_by(field), None
    return qs, {
        "code": "INVALID_SORT",
        "message": "sort order must be 'asc' or 'desc'",
    }


# --- Workflow Template Response Serializers ---

class WorkflowStatisticsSerializer(serializers.Serializer):
    """Statistics for a workflow template."""
    total_executions = serializers.IntegerField()
    successful = serializers.IntegerField()
    failed = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    running = serializers.IntegerField()
    average_duration = serializers.FloatField(allow_null=True)


class WorkflowListResponseSerializer(serializers.Serializer):
    """Response for list_workflows endpoint."""
    workflows = WorkflowTemplateListSerializer(many=True)
    count = serializers.IntegerField(help_text="Number of workflows in current page")
    total = serializers.IntegerField(help_text="Total number of workflows")


class WorkflowDetailResponseSerializer(serializers.Serializer):
    """Response for get_workflow endpoint."""
    workflow = WorkflowTemplateDetailSerializer()
    statistics = WorkflowStatisticsSerializer()
    executions = WorkflowExecutionListSerializer(many=True, required=False)


class WorkflowCreateResponseSerializer(serializers.Serializer):
    """Response for create_workflow endpoint."""
    workflow = WorkflowTemplateDetailSerializer()
    message = serializers.CharField()


class WorkflowUpdateResponseSerializer(serializers.Serializer):
    """Response for update_workflow endpoint."""
    workflow = WorkflowTemplateDetailSerializer()
    updated_fields = serializers.ListField(child=serializers.CharField())
    message = serializers.CharField()


class WorkflowDeleteResponseSerializer(serializers.Serializer):
    """Response for delete_workflow endpoint."""
    workflow_id = serializers.UUIDField()
    deleted = serializers.BooleanField()
    message = serializers.CharField()


class ValidationIssueSerializer(serializers.Serializer):
    """Validation issue detail."""
    code = serializers.CharField()
    message = serializers.CharField()
    node_ids = serializers.ListField(child=serializers.CharField(), required=False)
    severity = serializers.CharField(required=False)
    details = serializers.DictField(required=False)


class WorkflowValidateResponseSerializer(serializers.Serializer):
    """Response for validate_workflow endpoint."""
    valid = serializers.BooleanField()
    errors = ValidationIssueSerializer(many=True, required=False)
    warnings = ValidationIssueSerializer(many=True, required=False)
    metadata = serializers.DictField(required=False)
    topological_order = serializers.ListField(
        child=serializers.CharField(), required=False
    )


class WorkflowCloneResponseSerializer(serializers.Serializer):
    """Response for clone_workflow endpoint."""
    workflow = WorkflowTemplateDetailSerializer()
    cloned_from = serializers.UUIDField()
    message = serializers.CharField()


# --- Workflow Execution Response Serializers ---

class ExecuteWorkflowRequestSerializer(serializers.Serializer):
    """Request for execute_workflow endpoint."""
    workflow_id = serializers.UUIDField(help_text="Workflow template UUID")
    input_context = serializers.DictField(
        required=False, default=dict, help_text="Initial context for workflow"
    )
    mode = serializers.ChoiceField(
        choices=['sync', 'async'], default='async',
        help_text="Execution mode: sync (blocking) or async (background)"
    )


class ExecuteWorkflowResponseSerializer(serializers.Serializer):
    """Response for execute_workflow endpoint."""
    execution_id = serializers.UUIDField()
    status = serializers.CharField()
    mode = serializers.CharField()
    message = serializers.CharField()
    task_id = serializers.CharField(required=False)
    final_result = serializers.DictField(required=False, allow_null=True)
    duration = serializers.FloatField(required=False, allow_null=True)
    error_message = serializers.CharField(required=False)


class ExecutionListResponseSerializer(serializers.Serializer):
    """Response for list_executions endpoint."""
    executions = WorkflowExecutionListSerializer(many=True)
    count = serializers.IntegerField(help_text="Number of executions in current page")
    total = serializers.IntegerField(help_text="Total number of executions")


class ExecutionDetailResponseSerializer(serializers.Serializer):
    """Response for get_execution endpoint."""
    execution = WorkflowExecutionDetailSerializer()
    execution_plan = ExecutionPlanSerializer(required=False)
    bindings = ExecutionBindingSerializer(many=True, required=False)
    steps = WorkflowStepResultSerializer(many=True)


class ExecutionCancelRequestSerializer(serializers.Serializer):
    """Request for cancel_execution endpoint."""
    execution_id = serializers.UUIDField(help_text="Execution UUID")


class ExecutionCancelResponseSerializer(serializers.Serializer):
    """Response for cancel_execution endpoint."""
    execution_id = serializers.UUIDField()
    cancelled = serializers.BooleanField()
    status = serializers.CharField()
    message = serializers.CharField()


class ExecutionStepsResponseSerializer(serializers.Serializer):
    """Response for get_execution_steps endpoint."""
    steps = WorkflowStepResultSerializer(many=True)
    count = serializers.IntegerField()


# --- Request Serializers ---

class CreateWorkflowRequestSerializer(serializers.Serializer):
    """Request for create_workflow endpoint."""
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    workflow_type = serializers.CharField(default='general')
    dag_structure = serializers.DictField(help_text="DAG structure with nodes and edges")
    is_active = serializers.BooleanField(default=True)


class UpdateWorkflowRequestSerializer(serializers.Serializer):
    """Request for update_workflow endpoint."""
    workflow_id = serializers.UUIDField()
    name = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    workflow_type = serializers.CharField(required=False)
    dag_structure = serializers.DictField(required=False)
    is_active = serializers.BooleanField(required=False)


class DeleteWorkflowRequestSerializer(serializers.Serializer):
    """Request for delete_workflow endpoint."""
    workflow_id = serializers.UUIDField()
    force = serializers.BooleanField(default=False)


class ValidateWorkflowRequestSerializer(serializers.Serializer):
    """Request for validate_workflow endpoint."""
    workflow_id = serializers.UUIDField(required=False)
    dag_structure = serializers.DictField(required=False)


class CloneWorkflowRequestSerializer(serializers.Serializer):
    """Request for clone_workflow endpoint."""
    workflow_id = serializers.UUIDField()
    new_name = serializers.CharField(max_length=200, required=False)


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

    return Response({
        'workflows': serializer.data,
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
    description='Execute a workflow template. Supports sync (blocking) and async (Go Worker if enabled, else in-process background runner) modes.',
    request=ExecuteWorkflowRequestSerializer,
    responses={
        200: ExecuteWorkflowResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
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

        # Execute asynchronously via Go Worker (feature-flag), legacy Celery, or in-process runner
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

        if OperationsService.is_celery_enabled():
            # Legacy Celery path (feature flag enabled)
            try:
                from apps.templates.tasks import execute_existing_workflow
                task = execute_existing_workflow.delay(str(execution.id))

                logger.info(
                    "Workflow execution started via Celery (legacy mode)",
                    extra={
                        'execution_id': str(execution.id),
                        'workflow_id': str(workflow_id),
                        'executed_by': request.user.username if request.user else 'anonymous',
                        'mode': 'async_celery',
                        'task_id': task.id,
                    }
                )

                return Response({
                    'execution_id': str(execution.id),
                    'status': 'pending',
                    'mode': 'async',
                    'task_id': task.id,
                    'message': 'Workflow execution started (Celery)',
                })
            except Exception as e:
                logger.warning(f"Celery unavailable, falling back to background runner: {e}")
        elif is_go_workflow_engine_enabled():
            # Go Workflow Engine path (Go Worker executes workflow DAG)
            try:
                result = OperationsService.enqueue_workflow_execution(str(execution.id))

                if result.success:
                    logger.info(
                        "Workflow execution started via Go Worker",
                        extra={
                            'execution_id': str(execution.id),
                            'workflow_id': str(workflow_id),
                            'executed_by': request.user.username if request.user else 'anonymous',
                            'mode': 'async_go_worker',
                            'operation_id': result.operation_id,
                        }
                    )

                    return Response({
                        'execution_id': str(execution.id),
                        'status': 'pending',
                        'mode': 'async',
                        'operation_id': result.operation_id,
                        'message': 'Workflow execution started (Go Worker)',
                    })
                else:
                    logger.warning(
                        f"Go Worker enqueue failed: {result.error}, falling back to sync"
                    )
            except Exception as e:
                logger.warning(f"Go Worker unavailable, falling back to sync: {e}")
        else:
            logger.info(
                "Go workflow engine disabled (ENABLE_GO_WORKFLOW_ENGINE=false), falling back to background runner",
                extra={
                    'execution_id': str(execution.id),
                    'workflow_id': str(workflow_id),
                    'executed_by': request.user.username if request.user else 'anonymous',
                    'mode': 'async_runner_disabled_go_engine',
                }
            )

        # Async fallback: execute in-process without blocking the request.
        # Celery is removed; this is a lightweight background runner for dev/hybrid mode.
        if _start_async_workflow_execution(str(execution.id)):
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


@extend_schema(
    tags=['v2'],
    summary='Create workflow template',
    description='Create a new workflow template. The DAG structure is auto-validated.',
    request=CreateWorkflowRequestSerializer,
    responses={
        201: WorkflowCreateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_workflow(request):
    """
    POST /api/v2/workflows/create-workflow/

    Create a new workflow template.

    Request Body:
        {
            "name": "My Workflow",
            "description": "Optional description",
            "workflow_type": "general",
            "dag_structure": {
                "nodes": [...],
                "edges": [...]
            },
            "is_active": true
        }

    Response (201):
        {
            "workflow": {...},
            "message": "Workflow created successfully"
        }
    """
    if not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_WORKFLOW_TEMPLATE):
        return _permission_denied("You do not have permission to manage workflows.")

    name = request.data.get('name')
    description = request.data.get('description', '')
    workflow_type = request.data.get('workflow_type', 'general')
    dag_structure = request.data.get('dag_structure')
    is_active = request.data.get('is_active', True)

    # Validate required fields
    if not name:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'name is required'
            }
        }, status=400)

    if not dag_structure:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'dag_structure is required'
            }
        }, status=400)

    try:
        # Create workflow template
        workflow = WorkflowTemplate.objects.create(
            name=name,
            description=description,
            workflow_type=workflow_type,
            dag_structure=dag_structure,
            is_active=is_active,
            created_by=request.user,
        )

        # Auto-validate DAG
        try:
            workflow.validate()
            workflow.save(update_fields=['is_valid'])
        except ValueError as ve:
            # Keep workflow but mark as invalid
            logger.warning(f"Workflow created but validation failed: {ve}")

        serializer = WorkflowTemplateDetailSerializer(workflow)

        logger.info(
            f"Workflow created: {workflow.name} ({workflow.id}) by {request.user.username}"
        )

        return Response({
            'workflow': serializer.data,
            'message': 'Workflow created successfully',
        }, status=201)

    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        return Response({
            'success': False,
            'error': {
                'code': 'CREATE_ERROR',
                'message': str(e)
            }
        }, status=400)


@extend_schema(
    tags=['v2'],
    summary='Update workflow template',
    description='Update an existing workflow template. Supports partial updates. Cannot update if workflow has running executions.',
    request=UpdateWorkflowRequestSerializer,
    responses={
        200: WorkflowUpdateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
        409: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_workflow(request):
    """
    POST /api/v2/workflows/update-workflow/

    Update an existing workflow template.

    Request Body:
        {
            "workflow_id": "uuid",
            "name": "Updated Name",
            "description": "Updated description",
            "dag_structure": {...},
            "is_active": true
        }

    Response (200):
        {
            "workflow": {...},
            "updated_fields": [...],
            "message": "Workflow updated successfully"
        }
    """
    workflow_id = request.data.get('workflow_id')

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

    if not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_WORKFLOW_TEMPLATE, workflow):
        return _permission_denied("You do not have permission to manage this workflow.")

    # Check for running executions
    running_count = workflow.executions.filter(
        status__in=[WorkflowExecution.STATUS_PENDING, WorkflowExecution.STATUS_RUNNING]
    ).count()

    if running_count > 0:
        return Response({
            'success': False,
            'error': {
                'code': 'WORKFLOW_HAS_RUNNING_EXECUTIONS',
                'message': f'Cannot update workflow with {running_count} running execution(s)'
            }
        }, status=409)

    # Track updated fields
    updated_fields = []

    # Update fields if provided
    if 'name' in request.data:
        workflow.name = request.data['name']
        updated_fields.append('name')

    if 'description' in request.data:
        workflow.description = request.data['description']
        updated_fields.append('description')

    if 'workflow_type' in request.data:
        workflow.workflow_type = request.data['workflow_type']
        updated_fields.append('workflow_type')

    if 'is_active' in request.data:
        workflow.is_active = request.data['is_active']
        updated_fields.append('is_active')

    if 'dag_structure' in request.data:
        workflow.dag_structure = request.data['dag_structure']
        workflow.is_valid = False  # Mark as needing revalidation
        updated_fields.append('dag_structure')

    try:
        workflow.save()

        # Re-validate if DAG changed
        if 'dag_structure' in request.data:
            try:
                workflow.validate()
                workflow.save(update_fields=['is_valid'])
            except ValueError as ve:
                logger.warning(f"Workflow updated but validation failed: {ve}")

        serializer = WorkflowTemplateDetailSerializer(workflow)

        logger.info(
            f"Workflow updated: {workflow.name} ({workflow.id}) by {request.user.username}, "
            f"fields: {updated_fields}"
        )

        return Response({
            'workflow': serializer.data,
            'updated_fields': updated_fields,
            'message': 'Workflow updated successfully',
        })

    except Exception as e:
        logger.error(f"Failed to update workflow: {e}")
        return Response({
            'success': False,
            'error': {
                'code': 'UPDATE_ERROR',
                'message': str(e)
            }
        }, status=400)


@extend_schema(
    tags=['v2'],
    summary='Delete workflow template',
    description='Delete a workflow template (soft delete - deactivates). Use force=true to also cancel running executions.',
    request=DeleteWorkflowRequestSerializer,
    responses={
        200: WorkflowDeleteResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
        409: ErrorResponseSerializer,
        500: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_workflow(request):
    """
    POST /api/v2/workflows/delete-workflow/

    Delete a workflow template (soft delete by default).

    Request Body:
        {
            "workflow_id": "uuid",
            "force": false
        }

    Response (200):
        {
            "workflow_id": "uuid",
            "deleted": true,
            "message": "Workflow deleted successfully"
        }
    """
    workflow_id = request.data.get('workflow_id')
    force = request.data.get('force', False)

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

    if not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_WORKFLOW_TEMPLATE, workflow):
        return _permission_denied("You do not have permission to manage this workflow.")

    workflow_name = workflow.name

    # Check for running executions
    running_count = workflow.executions.filter(
        status__in=[WorkflowExecution.STATUS_PENDING, WorkflowExecution.STATUS_RUNNING]
    ).count()

    if running_count > 0 and not force:
        return Response({
            'success': False,
            'error': {
                'code': 'WORKFLOW_HAS_RUNNING_EXECUTIONS',
                'message': f'Cannot delete workflow with {running_count} running execution(s). Use force=true to override.'
            }
        }, status=409)

    try:
        if force:
            # Cancel running executions first
            for execution in workflow.executions.filter(
                status__in=[WorkflowExecution.STATUS_PENDING, WorkflowExecution.STATUS_RUNNING]
            ):
                execution.cancel()
                execution.save()

        # Soft delete - just deactivate
        workflow.is_active = False
        workflow.save(update_fields=['is_active', 'updated_at'])

        logger.info(
            f"Workflow deleted (soft): {workflow_name} ({workflow_id}) by {request.user.username}"
        )

        return Response({
            'workflow_id': str(workflow_id),
            'deleted': True,
            'message': 'Workflow deleted successfully',
        })

    except Exception as e:
        logger.error(f"Failed to delete workflow: {e}")
        return Response({
            'success': False,
            'error': {
                'code': 'DELETE_ERROR',
                'message': str(e)
            }
        }, status=500)


@extend_schema(
    tags=['v2'],
    summary='Validate workflow DAG',
    description='Validate a workflow DAG structure. Can validate by workflow_id or by providing dag_structure directly.',
    request=ValidateWorkflowRequestSerializer,
    responses={
        200: WorkflowValidateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_workflow(request):
    """
    POST /api/v2/workflows/validate-workflow/

    Validate a workflow DAG structure.

    Request Body:
        {
            "workflow_id": "uuid"
        }
        OR
        {
            "dag_structure": {...}
        }

    Response (200):
        {
            "valid": true/false,
            "errors": [...],
            "warnings": [...],
            "metadata": {...}
        }
    """
    if not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_WORKFLOW_TEMPLATE):
        return _permission_denied("You do not have permission to manage workflows.")

    workflow_id = request.data.get('workflow_id')
    dag_structure = request.data.get('dag_structure')

    if not workflow_id and not dag_structure:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'Either workflow_id or dag_structure is required'
            }
        }, status=400)

    try:
        from apps.templates.workflow.validator import DAGValidator
        from apps.templates.workflow.models import DAGStructure

        if workflow_id:
            try:
                workflow = WorkflowTemplate.objects.get(id=workflow_id)
                dag = workflow.dag_structure
            except WorkflowTemplate.DoesNotExist:
                return Response({
                    'success': False,
                    'error': {
                        'code': 'WORKFLOW_NOT_FOUND',
                        'message': 'Workflow not found'
                    }
                }, status=404)
            if not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_WORKFLOW_TEMPLATE, workflow):
                return _permission_denied("You do not have permission to manage this workflow.")
        else:
            # Parse dag_structure directly
            try:
                dag = DAGStructure(**dag_structure)
            except Exception as e:
                return Response({
                    'valid': False,
                    'errors': [{
                        'code': 'SCHEMA_ERROR',
                        'message': str(e)
                    }],
                    'warnings': [],
                    'metadata': {}
                })

        # Run DAGValidator
        validator = DAGValidator(dag)
        result = validator.validate()

        def _issue_payload(issue):
            node_ids = list(getattr(issue, "node_ids", []) or [])
            severity = issue.severity.value if hasattr(issue.severity, "value") else issue.severity
            return {
                'code': getattr(issue, "code", "VALIDATION_ERROR"),
                'message': issue.message,
                'node_ids': node_ids,
                'severity': severity,
                'details': getattr(issue, "details", {}) or {},
            }

        # Format errors and warnings
        errors = [_issue_payload(issue) for issue in result.errors]
        warnings = [_issue_payload(issue) for issue in result.warnings]

        # Update workflow is_valid if validating by ID
        if workflow_id and result.is_valid:
            workflow.is_valid = True
            workflow.save(update_fields=['is_valid', 'updated_at'])

        return Response({
            'valid': result.is_valid,
            'errors': errors,
            'warnings': warnings,
            'metadata': result.metadata,
            'topological_order': result.topological_order,
        })

    except Exception as e:
        logger.error(f"Failed to validate workflow: {e}")
        return Response({
            'valid': False,
            'errors': [{
                'code': 'VALIDATION_ERROR',
                'message': str(e)
            }],
            'warnings': [],
            'metadata': {}
        })


@extend_schema(
    tags=['v2'],
    summary='Clone workflow template',
    description='Clone a workflow template. If new_name is provided, creates as new workflow (v1). Otherwise, creates as new version.',
    request=CloneWorkflowRequestSerializer,
    responses={
        201: WorkflowCloneResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clone_workflow(request):
    """
    POST /api/v2/workflows/clone-workflow/

    Clone a workflow template as a new version.

    Request Body:
        {
            "workflow_id": "uuid",
            "new_name": "Optional new name"
        }

    Response (201):
        {
            "workflow": {...},
            "cloned_from": "uuid",
            "message": "Workflow cloned successfully"
        }
    """
    workflow_id = request.data.get('workflow_id')
    new_name = request.data.get('new_name')

    if not workflow_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'workflow_id is required'
            }
        }, status=400)

    try:
        source_workflow = WorkflowTemplate.objects.get(id=workflow_id)
    except WorkflowTemplate.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'WORKFLOW_NOT_FOUND',
                'message': 'Workflow not found'
            }
        }, status=404)

    if not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_WORKFLOW_TEMPLATE, source_workflow):
        return _permission_denied("You do not have permission to manage this workflow.")

    try:
        if new_name:
            # Create with new name (fresh workflow, version 1)
            cloned = WorkflowTemplate.objects.create(
                name=new_name,
                description=source_workflow.description,
                workflow_type=source_workflow.workflow_type,
                dag_structure=source_workflow.dag_structure,
                config=source_workflow.config,
                is_valid=source_workflow.is_valid,
                is_active=True,
                created_by=request.user,
                version_number=1,
            )
        else:
            # Clone as new version (same name, incremented version)
            cloned = source_workflow.clone_as_new_version(created_by=request.user)

        serializer = WorkflowTemplateDetailSerializer(cloned)

        logger.info(
            f"Workflow cloned: {source_workflow.name} ({source_workflow.id}) -> "
            f"{cloned.name} ({cloned.id}) by {request.user.username}"
        )

        return Response({
            'workflow': serializer.data,
            'cloned_from': str(workflow_id),
            'message': 'Workflow cloned successfully',
        }, status=201)

    except Exception as e:
        logger.error(f"Failed to clone workflow: {e}")
        return Response({
            'success': False,
            'error': {
                'code': 'CLONE_ERROR',
                'message': str(e)
            }
        }, status=400)


# ============================================================================
# Workflow Execution Endpoints (Phase 4)
# ============================================================================


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


@extend_schema(
    tags=['v2'],
    summary='List workflow templates for Operations Center',
    description='List all active workflow templates available for Operations Center (is_template=true, is_active=true).',
    parameters=[
        OpenApiParameter(
            name='category', type=str, required=False,
            description='Filter by category (ras, odata, system, custom)'
        ),
        OpenApiParameter(
            name='search', type=str, required=False,
            description='Search by name or description'
        ),
    ],
    responses={
        200: TemplateListResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_templates(request):
    """
    GET /api/v2/workflows/list-templates/

    List all workflow templates available for Operations Center.

    Query Parameters:
        - category: Filter by category (ras, odata, system, custom)
        - search: Search by name or description

    Response:
        {
            "templates": [...],
            "count": 10
        }
    """
    if not request.user.has_perm(perms.PERM_TEMPLATES_VIEW_WORKFLOW_TEMPLATE):
        return _permission_denied("You do not have permission to view workflows.")

    category = request.query_params.get('category')
    search = request.query_params.get('search')

    # Only show active templates marked for Operations Center
    qs = WorkflowTemplate.objects.filter(
        is_template=True,
        is_active=True,
        is_valid=True,
    )

    if category:
        qs = qs.filter(category=category)

    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    qs = qs.order_by('category', 'name')

    if not request.user.is_staff:
        qs = TemplatePermissionService.filter_accessible_workflow_templates(
            request.user,
            qs,
            min_level=PermissionLevel.VIEW,
        )

    templates_data = []
    for template in qs:
        templates_data.append({
            'id': template.id,
            'name': template.name,
            'description': template.description,
            'category': template.category,
            'icon': template.icon,
            'workflow_type': template.workflow_type,
            'version_number': template.version_number,
            'created_at': template.created_at,
        })

    logger.debug(
        "Listed workflow templates for Operations Center",
        extra={
            'user': request.user.username,
            'category': category,
            'search': search,
            'count': len(templates_data),
        }
    )

    return Response({
        'templates': templates_data,
        'count': len(templates_data),
    })


@extend_schema(
    tags=['v2'],
    summary='Get workflow template schema',
    description='Get the input schema for a specific workflow template (for dynamic form generation).',
    parameters=[
        OpenApiParameter(
            name='workflow_id', type=str, required=True,
            description='Workflow template UUID'
        ),
    ],
    responses={
        200: TemplateSchemaResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_template_schema(request):
    """
    GET /api/v2/workflows/get-template-schema/?workflow_id=X

    Get the input schema for a workflow template.

    Query Parameters:
        - workflow_id: Workflow template UUID (required)

    Response:
        {
            "workflow_id": "uuid",
            "name": "Template Name",
            "description": "...",
            "category": "ras",
            "icon": "PlayCircleOutlined",
            "input_schema": {...}
        }
    """
    workflow_id = request.query_params.get('workflow_id')

    if not workflow_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'workflow_id is required'
            }
        }, status=400)

    # Validate UUID format
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

    try:
        template = WorkflowTemplate.objects.get(
            id=workflow_id,
            is_template=True,
            is_active=True,
        )
    except WorkflowTemplate.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'TEMPLATE_NOT_FOUND',
                'message': 'Workflow template not found or not available for Operations Center'
            }
        }, status=404)

    if not request.user.has_perm(perms.PERM_TEMPLATES_VIEW_WORKFLOW_TEMPLATE, template):
        return _permission_denied("You do not have permission to access this workflow.")

    logger.info(
        "Retrieved workflow template schema",
        extra={
            'user': request.user.username,
            'workflow_id': str(workflow_id),
            'template_name': template.name,
        }
    )

    return Response({
        'workflow_id': str(template.id),
        'name': template.name,
        'description': template.description,
        'category': template.category,
        'icon': template.icon,
        'input_schema': template.input_schema,
    })
