from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db import transaction

from apps.operations.services import OperationsService

from .master_data_sync_redaction import sanitize_master_data_sync_text
from .master_data_sync_workflow_contract import build_master_data_sync_workflow_input_context
from .master_data_sync_scheduling import (
    SERVER_AFFINITY_UNRESOLVED,
    build_master_data_sync_scheduling_contract,
)
from .master_data_sync_workflow_template import ensure_pool_master_data_sync_workflow_template
from .runtime_template_registry import sync_pool_runtime_template_registry
from .models import PoolMasterDataSyncJob, PoolMasterDataSyncJobStatus


@dataclass(frozen=True)
class PoolMasterDataSyncWorkflowStartResult:
    sync_job: PoolMasterDataSyncJob
    execution_id: str | None
    operation_id: str | None
    enqueue_success: bool
    enqueue_status: str
    enqueue_error: str | None
    created_execution: bool


def _normalize_operation_id(operation_id: str) -> str:
    return str(UUID(str(operation_id or "").strip()))


def _classify_scheduling_contract_error(error: ValueError) -> tuple[str, str]:
    detail = str(error or "").strip() or "Invalid scheduling contract"
    if detail == SERVER_AFFINITY_UNRESOLVED or detail.startswith(f"{SERVER_AFFINITY_UNRESOLVED}:"):
        return SERVER_AFFINITY_UNRESOLVED, detail
    return "SCHEDULING_CONTRACT_INVALID", detail


def start_pool_master_data_sync_job_workflow(
    *,
    sync_job: PoolMasterDataSyncJob,
    correlation_id: str,
    origin_system: str,
    origin_event_id: str,
):
    execution_id: str | None = None
    created_execution = False
    scheduling_contract: dict[str, str] = {}

    with transaction.atomic():
        locked_job = PoolMasterDataSyncJob.objects.select_for_update().get(id=sync_job.id)
        if locked_job.workflow_execution_id:
            existing_execution_id = str(locked_job.workflow_execution_id)
            existing_operation_id = (
                str(locked_job.operation_id)
                if locked_job.operation_id is not None
                else None
            )
            return PoolMasterDataSyncWorkflowStartResult(
                sync_job=locked_job,
                execution_id=existing_execution_id,
                operation_id=existing_operation_id,
                enqueue_success=True,
                enqueue_status=locked_job.status,
                enqueue_error=None,
                created_execution=False,
            )

        try:
            scheduling_contract = build_master_data_sync_scheduling_contract(sync_job=locked_job)
        except ValueError as exc:
            error_code, error_detail = _classify_scheduling_contract_error(exc)
            sanitized_error_detail = sanitize_master_data_sync_text(error_detail)
            locked_job.status = PoolMasterDataSyncJobStatus.FAILED
            locked_job.last_error_code = error_code
            locked_job.last_error = sanitized_error_detail
            locked_job.save(
                update_fields=[
                    "status",
                    "last_error_code",
                    "last_error",
                    "updated_at",
                ]
            )
            return PoolMasterDataSyncWorkflowStartResult(
                sync_job=locked_job,
                execution_id=None,
                operation_id=None,
                enqueue_success=False,
                enqueue_status="error",
                enqueue_error=sanitized_error_detail,
                created_execution=False,
            )

        sync_pool_runtime_template_registry()
        workflow_template = ensure_pool_master_data_sync_workflow_template()
        input_context = build_master_data_sync_workflow_input_context(
            sync_job=locked_job,
            correlation_id=correlation_id,
            origin_system=origin_system,
            origin_event_id=origin_event_id,
        )
        execution = workflow_template.create_execution(
            input_context,
            tenant=locked_job.tenant,
            execution_consumer="pools",
        )
        locked_job.workflow_execution_id = execution.id
        locked_job.save(update_fields=["workflow_execution_id", "updated_at"])
        execution_id = str(execution.id)
        created_execution = True

    enqueue_result = OperationsService.enqueue_workflow_execution(
        execution_id=execution_id or "",
        workflow_config={
            "sync_job_id": str(sync_job.id),
            "execution_consumer": "pools",
            "idempotency_key": f"pool.master_data.sync:{sync_job.id}",
            "trace_id": str(correlation_id or "").strip(),
            **scheduling_contract,
        },
    )

    refreshed = PoolMasterDataSyncJob.objects.get(id=sync_job.id)

    if enqueue_result.success:
        normalized_operation_id = _normalize_operation_id(enqueue_result.operation_id or (execution_id or ""))
        refreshed.operation_id = UUID(normalized_operation_id)
        refreshed.status = PoolMasterDataSyncJobStatus.RUNNING
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
        return PoolMasterDataSyncWorkflowStartResult(
            sync_job=refreshed,
            execution_id=execution_id,
            operation_id=normalized_operation_id,
            enqueue_success=True,
            enqueue_status=enqueue_result.status,
            enqueue_error=None,
            created_execution=created_execution,
        )

    refreshed.status = PoolMasterDataSyncJobStatus.FAILED
    refreshed.last_error_code = str(enqueue_result.error_code or "ENQUEUE_FAILED")
    sanitized_enqueue_error = sanitize_master_data_sync_text(
        enqueue_result.error or "Failed to enqueue workflow execution"
    )
    refreshed.last_error = sanitized_enqueue_error
    refreshed.save(
        update_fields=[
            "status",
            "last_error_code",
            "last_error",
            "updated_at",
        ]
    )
    return PoolMasterDataSyncWorkflowStartResult(
        sync_job=refreshed,
        execution_id=execution_id,
        operation_id=None,
        enqueue_success=False,
        enqueue_status=enqueue_result.status,
        enqueue_error=sanitized_enqueue_error,
        created_execution=created_execution,
    )
