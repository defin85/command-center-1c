"""
Workflow endpoints for API v2.

Provides action-based endpoints for workflow management.
"""

from concurrent.futures import ThreadPoolExecutor
import json
import logging

from django.db import close_old_connections
from rest_framework import serializers
from rest_framework.response import Response


from apps.templates.workflow.models import WorkflowExecution
from apps.templates.workflow.serializers import (
    WorkflowTemplateListSerializer,
    WorkflowTemplateDetailSerializer,
    WorkflowExecutionListSerializer,
    WorkflowExecutionDetailSerializer,
    WorkflowStepResultSerializer,
)
from apps.api_v2.serializers.common import ExecutionBindingSerializer, ExecutionPlanSerializer

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


class WorkflowAuthoringPhaseSerializer(serializers.Serializer):
    """Workflow authoring phase summary for rollout diagnostics."""

    class WorkflowConstructVisibilitySerializer(serializers.Serializer):
        contract_version = serializers.CharField()
        public_constructs = serializers.ListField(child=serializers.CharField())
        internal_runtime_only_constructs = serializers.ListField(
            child=serializers.CharField()
        )
        compatibility_constructs = serializers.ListField(child=serializers.CharField())

    phase = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField()
    is_prerequisite_platform_phase = serializers.BooleanField()
    analyst_surface = serializers.CharField()
    rollout_scope = serializers.ListField(child=serializers.CharField())
    deferred_scope = serializers.ListField(child=serializers.CharField())
    follow_up_changes = serializers.ListField(child=serializers.CharField())
    construct_visibility = WorkflowConstructVisibilitySerializer()
    source = serializers.CharField()


class WorkflowListResponseSerializer(serializers.Serializer):
    """Response for list_workflows endpoint."""
    workflows = WorkflowTemplateListSerializer(many=True)
    authoring_phase = WorkflowAuthoringPhaseSerializer()
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
    operation_id = serializers.CharField(required=False)
    task_id = serializers.CharField(required=False)
    final_result = serializers.DictField(required=False, allow_null=True)
    duration = serializers.FloatField(required=False, allow_null=True)
    error_message = serializers.CharField(required=False)


class WorkflowEnqueueFailClosedErrorDetailsSerializer(serializers.Serializer):
    execution_id = serializers.UUIDField()
    enqueue_error_code = serializers.CharField(required=False)


class WorkflowEnqueueFailClosedErrorDetailSerializer(serializers.Serializer):
    code = serializers.CharField(default="WORKFLOW_ENQUEUE_FAILED")
    message = serializers.CharField()
    details = WorkflowEnqueueFailClosedErrorDetailsSerializer()


class WorkflowEnqueueFailClosedErrorResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=False)
    error = WorkflowEnqueueFailClosedErrorDetailSerializer()
    request_id = serializers.CharField()
    ui_action_id = serializers.CharField(required=False)


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
