from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from django.db import transaction

from apps.operations.services import OperationsService

from .factual_scheduling import (
    SERVER_AFFINITY_UNRESOLVED,
    build_factual_closed_quarter_reconcile_contract,
    build_factual_read_contract,
)
from .factual_sync_runtime import FactualSalesReportSyncScope
from .factual_workflow_contract import build_pool_factual_sync_workflow_input_context
from .factual_workflow_template import ensure_pool_factual_sync_workflow_template
from .runtime_template_registry import sync_pool_runtime_template_registry
from .models import PoolFactualLane, PoolFactualSyncCheckpoint


@dataclass(frozen=True)
class PoolFactualSyncWorkflowStartResult:
    checkpoint: PoolFactualSyncCheckpoint
    execution_id: str | None
    operation_id: str | None
    enqueue_success: bool
    enqueue_status: str
    enqueue_error: str | None
    created_execution: bool


def _normalize_operation_id(operation_id: str) -> str:
    return str(UUID(str(operation_id or "").strip()))


def _classify_scheduling_contract_error(error: ValueError) -> tuple[str, str]:
    detail = str(error or "").strip() or "Invalid factual scheduling contract"
    if detail == SERVER_AFFINITY_UNRESOLVED or detail.startswith(f"{SERVER_AFFINITY_UNRESOLVED}:"):
        return SERVER_AFFINITY_UNRESOLVED, detail
    return "POOL_FACTUAL_SCHEDULING_CONTRACT_INVALID", detail


def start_pool_factual_sync_workflow(
    *,
    checkpoint: PoolFactualSyncCheckpoint,
    database,
    organization_ids: tuple[str, ...],
    account_codes: tuple[str, ...],
    movement_kinds: tuple[str, ...],
    correlation_id: str,
    origin_system: str,
    origin_event_id: str,
    activity: str = "active",
    freeze_quarter: bool = False,
    scope: FactualSalesReportSyncScope | None = None,
):
    execution_id: str | None = None
    created_execution = False
    scheduling_contract: dict[str, str] = {}

    with transaction.atomic():
        locked_checkpoint = PoolFactualSyncCheckpoint.objects.select_for_update().get(id=checkpoint.id)
        current_status = str(locked_checkpoint.workflow_status or "").strip().lower()
        if locked_checkpoint.workflow_execution_id and current_status in {"pending", "running"}:
            existing_execution_id = str(locked_checkpoint.workflow_execution_id)
            existing_operation_id = (
                str(locked_checkpoint.operation_id)
                if locked_checkpoint.operation_id is not None
                else None
            )
            return PoolFactualSyncWorkflowStartResult(
                checkpoint=locked_checkpoint,
                execution_id=existing_execution_id,
                operation_id=existing_operation_id,
                enqueue_success=True,
                enqueue_status=current_status or "running",
                enqueue_error=None,
                created_execution=False,
            )

        try:
            if locked_checkpoint.lane == PoolFactualLane.READ:
                scheduling_contract = build_factual_read_contract(
                    database=database,
                    activity=activity,
                )
            else:
                scheduling_contract = build_factual_closed_quarter_reconcile_contract(
                    database=database,
                )
        except ValueError as exc:
            error_code, error_detail = _classify_scheduling_contract_error(exc)
            locked_checkpoint.workflow_status = "failed"
            locked_checkpoint.last_error_code = error_code
            locked_checkpoint.last_error = error_detail
            locked_checkpoint.save(
                update_fields=[
                    "workflow_status",
                    "last_error_code",
                    "last_error",
                    "updated_at",
                ]
            )
            return PoolFactualSyncWorkflowStartResult(
                checkpoint=locked_checkpoint,
                execution_id=None,
                operation_id=None,
                enqueue_success=False,
                enqueue_status="error",
                enqueue_error=error_detail,
                created_execution=False,
            )

        sync_pool_runtime_template_registry()
        workflow_template = ensure_pool_factual_sync_workflow_template()
        input_context = build_pool_factual_sync_workflow_input_context(
            checkpoint_id=str(locked_checkpoint.id),
            tenant_id=str(locked_checkpoint.tenant_id),
            pool_id=str(locked_checkpoint.pool_id),
            database=database,
            quarter_start=locked_checkpoint.quarter_start,
            quarter_end=locked_checkpoint.quarter_end,
            organization_ids=organization_ids,
            account_codes=account_codes,
            movement_kinds=movement_kinds,
            lane=locked_checkpoint.lane,
            correlation_id=correlation_id,
            origin_system=origin_system,
            origin_event_id=origin_event_id,
            activity=activity,
            freeze_quarter=freeze_quarter,
            scope=scope,
        )
        execution = workflow_template.create_execution(
            input_context,
            tenant=locked_checkpoint.tenant,
            execution_consumer="pools",
        )
        locked_checkpoint.workflow_execution_id = execution.id
        locked_checkpoint.workflow_status = "pending"
        locked_checkpoint.last_error_code = ""
        locked_checkpoint.last_error = ""
        locked_checkpoint.save(
            update_fields=[
                "workflow_execution_id",
                "workflow_status",
                "last_error_code",
                "last_error",
                "updated_at",
            ]
        )
        execution_id = str(execution.id)
        created_execution = True

    enqueue_result = OperationsService.enqueue_workflow_execution(
        execution_id=execution_id or "",
        workflow_config={
            "checkpoint_id": str(checkpoint.id),
            "execution_consumer": "pools",
            "idempotency_key": (
                f"pool.factual.sync:{scope.scope_fingerprint if scope is not None else checkpoint.scope_fingerprint or 'legacy'}:"
                f"{checkpoint.id}:{checkpoint.lane}:"
                f"{checkpoint.quarter_start.isoformat()}:{checkpoint.quarter_end.isoformat()}"
            ),
            "trace_id": str(correlation_id or "").strip(),
            **scheduling_contract,
        },
    )

    refreshed = PoolFactualSyncCheckpoint.objects.get(id=checkpoint.id)
    if enqueue_result.success:
        normalized_operation_id = _normalize_operation_id(enqueue_result.operation_id or (execution_id or ""))
        refreshed.operation_id = UUID(normalized_operation_id)
        refreshed.workflow_status = "running"
        refreshed.last_error_code = ""
        refreshed.last_error = ""
        refreshed.save(
            update_fields=[
                "operation_id",
                "workflow_status",
                "last_error_code",
                "last_error",
                "updated_at",
            ]
        )
        return PoolFactualSyncWorkflowStartResult(
            checkpoint=refreshed,
            execution_id=execution_id,
            operation_id=normalized_operation_id,
            enqueue_success=True,
            enqueue_status=enqueue_result.status,
            enqueue_error=None,
            created_execution=created_execution,
        )

    refreshed.workflow_status = "failed"
    refreshed.last_error_code = str(enqueue_result.error_code or "ENQUEUE_FAILED")
    refreshed.last_error = str(enqueue_result.error or "Failed to enqueue factual workflow execution")
    refreshed.save(
        update_fields=[
            "workflow_status",
            "last_error_code",
            "last_error",
            "updated_at",
        ]
    )
    return PoolFactualSyncWorkflowStartResult(
        checkpoint=refreshed,
        execution_id=execution_id,
        operation_id=None,
        enqueue_success=False,
        enqueue_status=enqueue_result.status,
        enqueue_error=refreshed.last_error,
        created_execution=created_execution,
    )


__all__ = [
    "PoolFactualSyncWorkflowStartResult",
    "start_pool_factual_sync_workflow",
]
