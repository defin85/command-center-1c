from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from apps.intercompany_pools.models import (
    OrganizationPool,
    PoolRun,
    PoolRunDirection,
    PoolRunMode,
)
from apps.intercompany_pools.pool_domain_steps import execute_pool_runtime_step
from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate, WorkflowType
from apps.tenancy.models import Tenant


def _create_pool_run(*, mode: str) -> PoolRun:
    tenant = Tenant.objects.create(
        slug=f"pool-domain-{uuid4().hex[:8]}",
        name="Pool Domain",
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Pool Domain",
    )
    run_input: dict[str, object] = {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]}
    run = PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        mode=mode,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        run_input=run_input,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save(update_fields=["status", "validated_at", "validation_summary", "diagnostics", "updated_at"])
    return run


def _attach_execution(*, run: PoolRun, input_context: dict[str, object]) -> WorkflowExecution:
    template = WorkflowTemplate.objects.create(
        name=f"pool-domain-{run.id.hex[:8]}",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {
                    "id": "pool_step",
                    "name": "Pool Step",
                    "type": "operation",
                    "template_id": "pool.prepare_input",
                }
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
    )
    execution = template.create_execution(
        input_context,
        tenant=run.tenant,
        execution_consumer="pools",
    )
    run.workflow_execution_id = execution.id
    run.workflow_status = execution.status
    run.execution_backend = "workflow_core"
    run.workflow_template_name = template.name
    run.save(
        update_fields=[
            "workflow_execution_id",
            "workflow_status",
            "execution_backend",
            "workflow_template_name",
            "updated_at",
        ]
    )
    return execution


@pytest.mark.django_db
def test_prepare_input_updates_safe_context_states() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "approval_state": "preparing",
            "publication_step_state": "not_enqueued",
            "approved_at": None,
        },
    )

    output = execute_pool_runtime_step(
        operation_type="pool.prepare_input",
        rendered_data={"pool_runtime": {"step_id": "prepare_input"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )

    execution.refresh_from_db(fields=["input_context"])
    assert output["step"] == "prepare_input"
    assert output["approval_state"] == "preparing"
    assert output["publication_step_state"] == "not_enqueued"
    assert execution.input_context.get("approval_state") == "preparing"
    assert execution.input_context.get("publication_step_state") == "not_enqueued"


@pytest.mark.django_db
def test_approval_gate_sets_awaiting_approval_for_safe_unconfirmed_run() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "approval_state": "preparing",
            "publication_step_state": "not_enqueued",
            "approved_at": None,
        },
    )

    output = execute_pool_runtime_step(
        operation_type="pool.approval_gate",
        rendered_data={"pool_runtime": {"step_id": "approval_gate"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )

    execution.refresh_from_db(fields=["input_context"])
    assert output["step"] == "approval_gate"
    assert output["awaiting_approval"] is True
    assert execution.input_context.get("approval_state") == "awaiting_approval"
    assert execution.input_context.get("publication_step_state") == "not_enqueued"


@pytest.mark.django_db
def test_publication_step_requires_approval_in_safe_mode() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "approval_state": "awaiting_approval",
            "publication_step_state": "not_enqueued",
            "approved_at": None,
        },
    )

    with pytest.raises(ValueError, match="POOL_RUNTIME_APPROVAL_REQUIRED"):
        execute_pool_runtime_step(
            operation_type="pool.publication_odata",
            rendered_data={"pool_runtime": {"step_id": "publication_odata"}},
            context={"pool_run_id": str(run.id)},
            execution=execution,
        )


@pytest.mark.django_db
def test_publication_step_without_targets_completes_context() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)
    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "approval_state": "not_required",
            "publication_step_state": "queued",
            "approved_at": None,
        },
    )

    output = execute_pool_runtime_step(
        operation_type="pool.publication_odata",
        rendered_data={"pool_runtime": {"step_id": "publication_odata"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )

    execution.refresh_from_db(fields=["input_context"])
    assert output["step"] == "publication_odata"
    assert output["status"] == "skipped_no_targets"
    assert execution.input_context.get("publication_step_state") == "completed"
