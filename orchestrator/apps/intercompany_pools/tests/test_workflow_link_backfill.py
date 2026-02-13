from __future__ import annotations

import io
from datetime import date
from uuid import uuid4

import pytest
from django.core.management import call_command

from apps.intercompany_pools.models import OrganizationPool, PoolRun, PoolRunDirection
from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate, WorkflowType
from apps.tenancy.models import Tenant


def _create_pool_run() -> PoolRun:
    tenant = Tenant.objects.create(slug=f"wf-backfill-{uuid4().hex[:8]}", name="WF Backfill")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Pool Backfill",
    )
    return PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
    )


def _create_workflow_execution_for_run(*, run: PoolRun) -> WorkflowExecution:
    workflow_template = WorkflowTemplate.objects.create(
        name=f"pool-backfill-template-{uuid4().hex[:8]}",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {
                    "id": "publication_odata",
                    "name": "Publication OData",
                    "type": "operation",
                    "template_id": "pool.publication_odata",
                }
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
    )
    execution = workflow_template.create_execution(
        {
            "pool_run_id": str(run.id),
            "approval_required": False,
            "approval_state": "not_required",
            "publication_step_state": "queued",
        },
        tenant=run.tenant,
        execution_consumer="pools",
    )
    execution.start()
    execution.save(update_fields=["status", "started_at"])
    return execution


@pytest.mark.django_db
def test_backfill_pool_run_workflow_links_dry_run_does_not_mutate() -> None:
    run = _create_pool_run()
    _create_workflow_execution_for_run(run=run)
    assert run.workflow_execution_id is None

    out = io.StringIO()
    call_command("backfill_pool_run_workflow_links", "--dry-run", stdout=out)
    output = out.getvalue()

    reloaded = PoolRun.objects.get(id=run.id)
    assert reloaded.workflow_execution_id is None
    assert "runs_linked: 1" in output
    assert "DRY RUN: transaction rolled back" in output


@pytest.mark.django_db
def test_backfill_pool_run_workflow_links_apply_links_run_and_metadata() -> None:
    run = _create_pool_run()
    execution = _create_workflow_execution_for_run(run=run)
    out = io.StringIO()

    call_command("backfill_pool_run_workflow_links", stdout=out)
    output = out.getvalue()

    reloaded = PoolRun.objects.get(id=run.id)
    assert reloaded.workflow_execution_id == execution.id
    assert reloaded.workflow_status == execution.status
    assert reloaded.execution_backend == "workflow_core"
    assert reloaded.workflow_template_name == execution.workflow_template.name
    assert "runs_linked: 1" in output


@pytest.mark.django_db
def test_backfill_pool_run_workflow_links_skips_ambiguous_candidates() -> None:
    run = _create_pool_run()
    execution_one = _create_workflow_execution_for_run(run=run)
    execution_two = _create_workflow_execution_for_run(run=run)
    assert execution_one.id != execution_two.id

    out = io.StringIO()
    call_command("backfill_pool_run_workflow_links", stdout=out)
    output = out.getvalue()

    reloaded = PoolRun.objects.get(id=run.id)
    assert reloaded.workflow_execution_id is None
    assert reloaded.execution_backend == "legacy_pool_runtime"
    assert "runs_ambiguous: 1" in output
