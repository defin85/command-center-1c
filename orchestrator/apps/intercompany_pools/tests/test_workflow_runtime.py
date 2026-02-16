from __future__ import annotations

from datetime import date
from uuid import uuid4
from unittest.mock import patch

import pytest

from apps.intercompany_pools.models import (
    OrganizationPool,
    PoolRun,
    PoolRunDirection,
    PoolRunMode,
)
from apps.intercompany_pools.runs import build_pool_run_idempotency_key
from apps.intercompany_pools.workflow_runtime import (
    start_pool_run_retry_workflow_execution,
    start_pool_run_workflow_execution,
)
from apps.operations.services.operations_service.types import EnqueueResult
from apps.templates.workflow.models import WorkflowExecution
from apps.tenancy.models import Tenant


def _create_pool_run(*, mode: str) -> PoolRun:
    tenant = Tenant.objects.create(
        slug=f"pool-runtime-{uuid4().hex[:8]}",
        name="Pool Runtime",
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Pool Runtime",
    )
    return PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        mode=mode,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        run_input={"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
    )


def _create_pool_run_for_pool(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    mode: str,
    period_start: date,
    period_end: date | None,
    run_input: dict[str, object],
    seed: int | None = None,
) -> PoolRun:
    idempotency_key = build_pool_run_idempotency_key(
        pool_id=str(pool.id),
        period_start=period_start,
        period_end=period_end,
        direction=PoolRunDirection.BOTTOM_UP,
        run_input=run_input,
    )
    return PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        mode=mode,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=period_start,
        period_end=period_end,
        run_input=run_input,
        idempotency_key=idempotency_key,
        seed=seed,
    )


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_persists_pinned_binding_snapshot() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-1",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        result = start_pool_run_workflow_execution(run=run)

    execution = WorkflowExecution.objects.get(id=result.execution_id)
    operation_bindings = execution.execution_plan.get("operation_bindings")
    assert isinstance(operation_bindings, list)
    assert len(operation_bindings) >= 4
    assert all(item.get("binding_mode") == "pinned_exposure" for item in operation_bindings)
    assert all(str(item.get("template_exposure_id") or "").strip() for item in operation_bindings)
    assert all(int(item.get("template_exposure_revision") or 0) >= 1 for item in operation_bindings)

    binding_entries = [
        item
        for item in execution.bindings
        if str(item.get("target_ref") or "").startswith("workflow.operation_ref.")
    ]
    assert len(binding_entries) == len(operation_bindings)
    assert all(item.get("binding_mode") == "pinned_exposure" for item in binding_entries)


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_reuses_definition_for_same_pool_structure() -> None:
    tenant = Tenant.objects.create(slug=f"pool-runtime-reuse-{uuid4().hex[:8]}", name="Pool Runtime Reuse")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Pool Runtime Reuse",
    )
    run_1 = _create_pool_run_for_pool(
        tenant=tenant,
        pool=pool,
        mode=PoolRunMode.SAFE,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        run_input={"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
        seed=101,
    )
    run_2 = _create_pool_run_for_pool(
        tenant=tenant,
        pool=pool,
        mode=PoolRunMode.SAFE,
        period_start=date(2026, 2, 1),
        period_end=date(2026, 2, 28),
        run_input={"source_payload": [{"inn": "730000000999", "amount": "999.00"}]},
        seed=202,
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-reuse",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        result_1 = start_pool_run_workflow_execution(run=run_1)
        result_2 = start_pool_run_workflow_execution(run=run_2)

    execution_1 = WorkflowExecution.objects.get(id=result_1.execution_id)
    execution_2 = WorkflowExecution.objects.get(id=result_2.execution_id)
    assert execution_1.workflow_template_id == execution_2.workflow_template_id

    definition_1 = execution_1.execution_plan.get("definition") if isinstance(execution_1.execution_plan, dict) else {}
    definition_2 = execution_2.execution_plan.get("definition") if isinstance(execution_2.execution_plan, dict) else {}
    assert isinstance(definition_1, dict)
    assert isinstance(definition_2, dict)
    assert definition_1.get("definition_key")
    assert definition_1.get("definition_key") == definition_2.get("definition_key")

    snapshot_1 = execution_1.execution_plan.get("execution_snapshot") if isinstance(execution_1.execution_plan, dict) else {}
    snapshot_2 = execution_2.execution_plan.get("execution_snapshot") if isinstance(execution_2.execution_plan, dict) else {}
    assert isinstance(snapshot_1, dict)
    assert isinstance(snapshot_2, dict)
    assert snapshot_1.get("period_start") == "2026-01-01"
    assert snapshot_2.get("period_start") == "2026-02-01"
    assert snapshot_1.get("run_input") != snapshot_2.get("run_input")


@pytest.mark.django_db
def test_retry_workflow_execution_keeps_operation_binding_snapshot() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-initial",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        first = start_pool_run_workflow_execution(run=run)

    retry_payload = {
        "entity_name": "Document_IntercompanyPoolDistribution",
        "documents_by_database": {},
        "max_attempts": 1,
        "retry_interval_seconds": 0,
        "external_key_field": "ExternalRunKey",
    }
    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-retry",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        retry = start_pool_run_retry_workflow_execution(run=run, retry_request=retry_payload)

    assert first.execution_id != retry.execution_id

    first_execution = WorkflowExecution.objects.get(id=first.execution_id)
    execution = WorkflowExecution.objects.get(id=retry.execution_id)
    operation_bindings = execution.execution_plan.get("operation_bindings")
    assert isinstance(operation_bindings, list)
    assert len(operation_bindings) >= 4
    assert all(item.get("binding_mode") == "pinned_exposure" for item in operation_bindings)
    assert all(str(item.get("template_exposure_id") or "").strip() for item in operation_bindings)

    first_definition = first_execution.execution_plan.get("definition")
    assert isinstance(first_definition, dict)
    assert str(first_definition.get("definition_key") or "").strip()

    definition = execution.execution_plan.get("definition")
    assert isinstance(definition, dict)
    assert str(definition.get("definition_key") or "").strip()
    assert definition.get("definition_key") == first_definition.get("definition_key")
    assert definition.get("workflow_template_id") == str(execution.workflow_template_id)

    execution_snapshot = execution.execution_plan.get("execution_snapshot")
    assert isinstance(execution_snapshot, dict)
    lineage = execution_snapshot.get("lineage")
    assert isinstance(lineage, dict)
    assert lineage.get("attempt_kind") == "retry"
    assert int(lineage.get("attempt_number") or 0) >= 2
    assert str(lineage.get("parent_workflow_run_id") or "").strip()
