from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db import transaction

from apps.operations.services import OperationsService

from .master_data_sync_launch_workflow_contract import build_master_data_sync_launch_workflow_input_context
from .master_data_sync_launch_workflow_template import ensure_pool_master_data_sync_launch_workflow_template
from .master_data_sync_redaction import sanitize_master_data_sync_text
from .models import PoolMasterDataSyncLaunchRequest, PoolMasterDataSyncLaunchStatus
from .runtime_template_registry import sync_pool_runtime_template_registry


@dataclass
class PoolMasterDataSyncLaunchWorkflowStartResult:
    launch_request: PoolMasterDataSyncLaunchRequest
    execution_id: str | None
    operation_id: str | None
    enqueue_success: bool
    enqueue_status: str
    enqueue_error: str | None
    created_execution: bool


def start_pool_master_data_sync_launch_request_workflow(
    *,
    launch_request: PoolMasterDataSyncLaunchRequest,
    correlation_id: str,
    origin_system: str,
    origin_event_id: str,
    actor_username: str = "",
) -> PoolMasterDataSyncLaunchWorkflowStartResult:
    execution_id: str | None = None
    created_execution = False

    with transaction.atomic():
        locked_request = PoolMasterDataSyncLaunchRequest.objects.select_for_update().get(id=launch_request.id)
        if locked_request.workflow_execution_id and locked_request.operation_id:
            existing_execution_id = str(locked_request.workflow_execution_id)
            existing_operation_id = (
                str(locked_request.operation_id)
                if locked_request.operation_id is not None
                else None
            )
            return PoolMasterDataSyncLaunchWorkflowStartResult(
                launch_request=locked_request,
                execution_id=existing_execution_id,
                operation_id=existing_operation_id,
                enqueue_success=True,
                enqueue_status=str(locked_request.status or "").strip() or "pending",
                enqueue_error=None,
                created_execution=False,
            )

        if locked_request.workflow_execution_id:
            execution_id = str(locked_request.workflow_execution_id)
        else:
            sync_pool_runtime_template_registry()
            workflow_template = ensure_pool_master_data_sync_launch_workflow_template()
            input_context = build_master_data_sync_launch_workflow_input_context(
                launch_request=locked_request,
                correlation_id=correlation_id,
                origin_system=origin_system,
                origin_event_id=origin_event_id,
                actor_username=actor_username,
            )
            execution = workflow_template.create_execution(
                input_context,
                tenant=locked_request.tenant,
                execution_consumer="pools",
            )
            locked_request.workflow_execution_id = execution.id
            locked_request.status = PoolMasterDataSyncLaunchStatus.PENDING
            locked_request.last_error_code = ""
            locked_request.last_error = ""
            locked_request.save(
                update_fields=[
                    "workflow_execution_id",
                    "status",
                    "last_error_code",
                    "last_error",
                    "updated_at",
                ]
            )
            execution_id = str(execution.id)
            created_execution = True

    if transaction.get_connection().in_atomic_block:
        deferred_result = PoolMasterDataSyncLaunchWorkflowStartResult(
            launch_request=PoolMasterDataSyncLaunchRequest.objects.get(id=launch_request.id),
            execution_id=execution_id,
            operation_id=None,
            enqueue_success=True,
            enqueue_status="deferred",
            enqueue_error=None,
            created_execution=created_execution,
        )

        def _enqueue_after_commit() -> None:
            final_result = _enqueue_pool_master_data_sync_launch_request_workflow(
                launch_request_id=str(launch_request.id),
                execution_id=execution_id,
                created_execution=created_execution,
                correlation_id=correlation_id,
                actor_username=actor_username,
            )
            _copy_start_result(target=deferred_result, source=final_result)

        transaction.on_commit(_enqueue_after_commit)
        return deferred_result

    return _enqueue_pool_master_data_sync_launch_request_workflow(
        launch_request_id=str(launch_request.id),
        execution_id=execution_id,
        created_execution=created_execution,
        correlation_id=correlation_id,
        actor_username=actor_username,
    )


def _enqueue_pool_master_data_sync_launch_request_workflow(
    *,
    launch_request_id: str,
    execution_id: str | None,
    created_execution: bool,
    correlation_id: str,
    actor_username: str,
) -> PoolMasterDataSyncLaunchWorkflowStartResult:
    refreshed = PoolMasterDataSyncLaunchRequest.objects.get(id=launch_request_id)
    linked_execution_id = str(refreshed.workflow_execution_id or execution_id or "").strip()
    if not linked_execution_id:
        raise ValueError("Sync launch request is not linked to workflow execution.")

    enqueue_result = OperationsService.enqueue_workflow_execution(
        execution_id=linked_execution_id,
        workflow_config={
            "launch_request_id": str(refreshed.id),
            "execution_consumer": "pools",
            "idempotency_key": f"pool.master_data.sync.launch:{refreshed.id}",
            "trace_id": str(correlation_id or "").strip(),
            "requested_by": str(actor_username or "").strip(),
        },
    )
    if enqueue_result.success:
        normalized_operation_id = _normalize_operation_id(enqueue_result.operation_id or linked_execution_id)
        refreshed.operation_id = UUID(normalized_operation_id) if normalized_operation_id is not None else None
        refreshed.status = PoolMasterDataSyncLaunchStatus.RUNNING
        refreshed.last_error_code = ""
        refreshed.last_error = ""
        refreshed.save(
            update_fields=[
                "operation_id",
                "status",
                "last_error_code",
                "last_error",
                "updated_at",
            ]
        )
        return PoolMasterDataSyncLaunchWorkflowStartResult(
            launch_request=refreshed,
            execution_id=linked_execution_id,
            operation_id=normalized_operation_id,
            enqueue_success=True,
            enqueue_status=enqueue_result.status,
            enqueue_error=None,
            created_execution=created_execution,
        )

    refreshed.status = PoolMasterDataSyncLaunchStatus.FAILED
    refreshed.last_error_code = str(enqueue_result.error_code or "ENQUEUE_FAILED").strip() or "ENQUEUE_FAILED"
    refreshed.last_error = sanitize_master_data_sync_text(
        str(enqueue_result.error or "Failed to enqueue workflow execution")
    )
    refreshed.save(
        update_fields=[
            "status",
            "last_error_code",
            "last_error",
            "updated_at",
        ]
    )
    return PoolMasterDataSyncLaunchWorkflowStartResult(
        launch_request=refreshed,
        execution_id=linked_execution_id,
        operation_id=None,
        enqueue_success=False,
        enqueue_status=enqueue_result.status,
        enqueue_error=refreshed.last_error or None,
        created_execution=created_execution,
    )


def _copy_start_result(
    *,
    target: PoolMasterDataSyncLaunchWorkflowStartResult,
    source: PoolMasterDataSyncLaunchWorkflowStartResult,
) -> None:
    target.launch_request = source.launch_request
    target.execution_id = source.execution_id
    target.operation_id = source.operation_id
    target.enqueue_success = source.enqueue_success
    target.enqueue_status = source.enqueue_status
    target.enqueue_error = source.enqueue_error
    target.created_execution = source.created_execution


def _normalize_operation_id(raw_value: str | None) -> str | None:
    token = str(raw_value or "").strip()
    if not token:
        return None
    try:
        return str(UUID(token))
    except ValueError:
        return None
