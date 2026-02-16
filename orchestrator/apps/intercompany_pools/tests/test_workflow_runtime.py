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

    execution = WorkflowExecution.objects.get(id=retry.execution_id)
    operation_bindings = execution.execution_plan.get("operation_bindings")
    assert isinstance(operation_bindings, list)
    assert len(operation_bindings) >= 4
    assert all(item.get("binding_mode") == "pinned_exposure" for item in operation_bindings)
    assert all(str(item.get("template_exposure_id") or "").strip() for item in operation_bindings)
