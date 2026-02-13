import uuid

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import IsInternalService
from .serializers import WorkflowExecutionStatusUpdateSerializer
from .views_common import _model_dump, exclude_schema, logger

APPROVAL_STATE_NOT_REQUIRED = "not_required"
APPROVAL_STATE_PREPARING = "preparing"
APPROVAL_STATE_AWAITING_APPROVAL = "awaiting_approval"
APPROVAL_STATE_APPROVED = "approved"

PUBLICATION_STEP_STATE_NOT_ENQUEUED = "not_enqueued"
PUBLICATION_STEP_STATE_QUEUED = "queued"
PUBLICATION_STEP_STATE_STARTED = "started"
PUBLICATION_STEP_STATE_COMPLETED = "completed"


@exclude_schema
@api_view(["GET"])
@permission_classes([IsInternalService])
def get_workflow_execution(request):
    """
    GET /api/v2/internal/workflows/get-execution?execution_id=<uuid>

    Returns workflow execution data for Go Worker.
    """
    from apps.templates.workflow.models import WorkflowExecution

    execution_id = request.query_params.get("execution_id")
    if not execution_id:
        return Response({"success": False, "error": "execution_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        uuid.UUID(str(execution_id))
    except ValueError:
        return Response({"success": False, "error": "execution_id must be a valid UUID"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        execution = WorkflowExecution.objects.select_related("workflow_template").get(id=execution_id)
    except WorkflowExecution.DoesNotExist:
        return Response({"success": False, "error": "Workflow execution not found"}, status=status.HTTP_404_NOT_FOUND)

    template = execution.workflow_template

    response = {
        "id": str(execution.id),
        "workflow_template": {
            "id": str(template.id),
            "name": template.name,
            "description": template.description or "",
            "workflow_type": template.workflow_type,
            "dag_structure": _model_dump(template.dag_structure),
            "config": _model_dump(template.config),
            "is_valid": template.is_valid,
            "is_active": template.is_active,
            "version_number": template.version_number,
        },
        "input_context": execution.input_context or {},
        "status": execution.status,
        "current_node_id": execution.current_node_id,
        "completed_nodes": execution.completed_nodes or [],
        "failed_nodes": execution.failed_nodes or [],
    }

    return Response(response)


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def update_workflow_execution_status(request):
    """
    POST /api/v2/internal/workflows/update-execution-status

    Updates workflow execution status for Go Worker.
    """
    from apps.templates.workflow.models import WorkflowExecution

    serializer = WorkflowExecutionStatusUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    execution_id = data["execution_id"]
    target_status = data["status"]
    error_message = data.get("error_message") or ""
    result_payload = data.get("result") or {}

    try:
        execution = WorkflowExecution.objects.get(id=execution_id)
    except WorkflowExecution.DoesNotExist:
        return Response({"success": False, "error": "Workflow execution not found"}, status=status.HTTP_404_NOT_FOUND)

    if target_status == execution.status:
        if target_status == WorkflowExecution.STATUS_FAILED and error_message:
            execution.error_message = error_message
            execution.save(update_fields=["error_message"])
        return Response({"success": True, "execution_id": str(execution.id), "status": execution.status})

    try:
        if target_status == WorkflowExecution.STATUS_RUNNING:
            if execution.status != WorkflowExecution.STATUS_PENDING:
                return Response({"success": False, "error": "Execution is not pending"}, status=status.HTTP_409_CONFLICT)
            execution.start()

        elif target_status == WorkflowExecution.STATUS_COMPLETED:
            if execution.status == WorkflowExecution.STATUS_PENDING:
                execution.start()
            if execution.status != WorkflowExecution.STATUS_RUNNING:
                return Response({"success": False, "error": "Execution is not running"}, status=status.HTTP_409_CONFLICT)
            execution.complete(result_payload)

        elif target_status == WorkflowExecution.STATUS_FAILED:
            if execution.status == WorkflowExecution.STATUS_PENDING:
                execution.start()
            if execution.status != WorkflowExecution.STATUS_RUNNING:
                return Response({"success": False, "error": "Execution is not running"}, status=status.HTTP_409_CONFLICT)
            execution.fail(error_message or "Workflow failed")

        elif target_status == WorkflowExecution.STATUS_CANCELLED:
            if execution.status not in [WorkflowExecution.STATUS_PENDING, WorkflowExecution.STATUS_RUNNING]:
                return Response({"success": False, "error": "Execution cannot be cancelled"}, status=status.HTTP_409_CONFLICT)
            execution.cancel()
        else:
            return Response({"success": False, "error": "Unsupported status"}, status=status.HTTP_400_BAD_REQUEST)

        _advance_pools_runtime_metadata_on_status_update(execution=execution, target_status=target_status)
        execution.save()

    except Exception:
        logger.exception("Failed to update workflow execution status")
        return Response({"success": False, "error": "Failed to update execution status"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    logger.info("Workflow execution status updated", extra={"execution_id": str(execution.id), "status": execution.status})

    return Response({"success": True, "execution_id": str(execution.id), "status": execution.status})


def _advance_pools_runtime_metadata_on_status_update(*, execution, target_status: str) -> None:
    if execution.execution_consumer != "pools":
        return

    input_context = execution.input_context if isinstance(execution.input_context, dict) else {}
    if not input_context:
        return

    approval_required = bool(input_context.get("approval_required"))
    approved_at = input_context.get("approved_at")
    raw_state = str(input_context.get("approval_state") or "").strip().lower()

    next_approval_state = raw_state
    if approval_required and not approved_at:
        if target_status == execution.STATUS_COMPLETED and raw_state in {"", APPROVAL_STATE_PREPARING}:
            next_approval_state = APPROVAL_STATE_AWAITING_APPROVAL
    elif approval_required and approved_at:
        next_approval_state = APPROVAL_STATE_APPROVED
    elif not approval_required:
        next_approval_state = APPROVAL_STATE_NOT_REQUIRED

    raw_publication_state = str(input_context.get("publication_step_state") or "").strip().lower()
    next_publication_state = raw_publication_state
    if approval_required and not approved_at:
        if raw_publication_state == "":
            next_publication_state = PUBLICATION_STEP_STATE_NOT_ENQUEUED
    else:
        if raw_publication_state in {"", PUBLICATION_STEP_STATE_NOT_ENQUEUED}:
            next_publication_state = PUBLICATION_STEP_STATE_QUEUED
        if target_status == execution.STATUS_RUNNING:
            next_publication_state = PUBLICATION_STEP_STATE_STARTED
        elif target_status == execution.STATUS_COMPLETED:
            next_publication_state = PUBLICATION_STEP_STATE_COMPLETED

    if (
        next_approval_state != raw_state
        or next_publication_state != raw_publication_state
    ):
        updated_context = dict(input_context)
        if next_approval_state:
            updated_context["approval_state"] = next_approval_state
        if next_publication_state:
            updated_context["publication_step_state"] = next_publication_state
        execution.input_context = updated_context
