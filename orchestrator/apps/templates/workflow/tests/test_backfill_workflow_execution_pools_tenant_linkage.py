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
    tenant = Tenant.objects.create(slug=f"wf-tenant-link-{uuid4().hex[:8]}", name="WF Tenant Link")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Pool Tenant Link",
    )
    return PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
    )


def _create_template(name_suffix: str) -> WorkflowTemplate:
    return WorkflowTemplate.objects.create(
        name=f"wf-tenant-link-{name_suffix}-{uuid4().hex[:8]}",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {
                    "id": "n1",
                    "name": "Node 1",
                    "type": "operation",
                    "template_id": "tpl-test",
                }
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
    )


@pytest.mark.django_db
def test_backfill_workflow_execution_pools_tenant_linkage_updates_legacy_execution() -> None:
    run = _create_pool_run()
    template = _create_template("apply")
    execution = template.create_execution(
        {"pool_run_id": str(run.id)},
        execution_consumer="legacy",
    )
    assert execution.tenant_id is None
    assert execution.execution_consumer == "legacy"

    out = io.StringIO()
    call_command("backfill_workflow_execution_pools_tenant_linkage", stdout=out)
    output = out.getvalue()

    reloaded = WorkflowExecution.objects.get(id=execution.id)
    assert reloaded.tenant_id == run.tenant_id
    assert reloaded.execution_consumer == "pools"
    assert "executions_updated: 1" in output
    assert "tenant_linked: 1" in output
    assert "consumer_corrected: 1" in output


@pytest.mark.django_db
def test_backfill_workflow_execution_pools_tenant_linkage_dry_run_does_not_mutate() -> None:
    run = _create_pool_run()
    template = _create_template("dry-run")
    execution = template.create_execution(
        {"pool_run_id": str(run.id)},
        execution_consumer="legacy",
    )
    assert execution.tenant_id is None

    out = io.StringIO()
    call_command("backfill_workflow_execution_pools_tenant_linkage", "--dry-run", stdout=out)
    output = out.getvalue()

    reloaded = WorkflowExecution.objects.get(id=execution.id)
    assert reloaded.tenant_id is None
    assert reloaded.execution_consumer == "legacy"
    assert "executions_updated: 1" in output
    assert "DRY RUN: transaction rolled back" in output


@pytest.mark.django_db
def test_backfill_workflow_execution_pools_tenant_linkage_counts_invalid_pool_run_id() -> None:
    template = _create_template("invalid")
    execution = template.create_execution(
        {"pool_run_id": "not-a-uuid"},
        execution_consumer="legacy",
    )

    out = io.StringIO()
    call_command("backfill_workflow_execution_pools_tenant_linkage", stdout=out)
    output = out.getvalue()

    reloaded = WorkflowExecution.objects.get(id=execution.id)
    assert reloaded.tenant_id is None
    assert reloaded.execution_consumer == "legacy"
    assert "executions_invalid_pool_run_id: 1" in output
    assert "executions_updated: 0" in output
