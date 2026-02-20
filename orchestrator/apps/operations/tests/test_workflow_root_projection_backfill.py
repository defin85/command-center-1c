from __future__ import annotations

import io
from datetime import timedelta
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.operations.models import BatchOperation
from apps.operations.workflow_root_projection_backfill import run_workflow_root_projection_backfill
from apps.templates.workflow.models import WorkflowTemplate, WorkflowType
from apps.tenancy.models import Tenant


def _create_template(name_suffix: str) -> WorkflowTemplate:
    return WorkflowTemplate.objects.create(
        name=f"workflow-root-backfill-{name_suffix}-{uuid4().hex[:8]}",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {
                    "id": "n1",
                    "name": "Node 1",
                    "type": "operation",
                    "template_id": "tpl-backfill",
                }
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
    )


def _create_running_execution(*, name_suffix: str, execution_consumer: str, started_at) -> str:
    template = _create_template(name_suffix)
    tenant = None
    if execution_consumer == "pools":
        tenant = Tenant.objects.create(
            slug=f"workflow-root-backfill-tenant-{uuid4().hex[:8]}",
            name="Workflow Root Backfill Tenant",
        )

    execution = template.create_execution(
        {"executed_by": "workflow-root-backfill"},
        tenant=tenant,
        execution_consumer=execution_consumer,
    )
    execution.start()
    execution.current_node_id = "n1"
    execution.trace_id = "a" * 32
    execution.started_at = started_at
    execution.save(update_fields=["status", "current_node_id", "trace_id", "started_at"])
    return str(execution.id)


@pytest.mark.django_db
def test_workflow_root_projection_backfill_repairs_missing_roots_and_tracks_sla():
    started_at = timezone.now() - timedelta(hours=2)
    execution_id = _create_running_execution(
        name_suffix="repair",
        execution_consumer="pools",
        started_at=started_at,
    )
    assert BatchOperation.objects.filter(id=execution_id).count() == 0

    stats = run_workflow_root_projection_backfill(sla_seconds=1800, chunk_size=10)
    payload = stats.to_dict()

    assert payload["executions_scanned"] == 1
    assert payload["executions_with_root"] == 0
    assert payload["executions_missing_root"] == 1
    assert payload["executions_repaired"] == 1
    assert payload["executions_repair_failed"] == 0
    assert payload["sla_evaluated"] == 1
    assert payload["sla_breaches"] == 1
    assert payload["max_lag_seconds"] >= 7200 - 5

    root = BatchOperation.objects.get(id=execution_id)
    assert root.status == BatchOperation.STATUS_PROCESSING
    assert root.metadata.get("workflow_execution_id") == execution_id
    assert root.metadata.get("root_operation_id") == execution_id
    assert root.metadata.get("workflow_status") == "running"
    assert root.metadata.get("execution_consumer") == "pools"
    assert root.metadata.get("lane") == "workflows"
    assert root.metadata.get("node_id") == "n1"
    assert root.metadata.get("trace_id") == "a" * 32


@pytest.mark.django_db
def test_workflow_root_projection_backfill_is_idempotent():
    execution_id = _create_running_execution(
        name_suffix="idempotent",
        execution_consumer="legacy",
        started_at=timezone.now(),
    )

    first = run_workflow_root_projection_backfill(sla_seconds=3600, chunk_size=10).to_dict()
    second = run_workflow_root_projection_backfill(sla_seconds=3600, chunk_size=10).to_dict()

    assert first["executions_missing_root"] == 1
    assert first["executions_repaired"] == 1
    assert second["executions_missing_root"] == 0
    assert second["executions_with_root"] == 1
    assert second["executions_repaired"] == 0
    assert BatchOperation.objects.filter(id=execution_id).count() == 1


@pytest.mark.django_db
def test_backfill_workflow_root_projections_command_dry_run_rolls_back():
    execution_id = _create_running_execution(
        name_suffix="dry-run",
        execution_consumer="legacy",
        started_at=timezone.now() - timedelta(minutes=10),
    )
    out = io.StringIO()

    call_command("backfill_workflow_root_projections", "--dry-run", stdout=out)
    output = out.getvalue()

    assert "Workflow root projection backfill finished" in output
    assert "executions_repaired: 1" in output
    assert "DRY RUN: transaction rolled back" in output
    assert BatchOperation.objects.filter(id=execution_id).count() == 0


@pytest.mark.django_db
def test_backfill_workflow_root_projections_command_strict_sla_rolls_back_on_breach():
    execution_id = _create_running_execution(
        name_suffix="strict-sla",
        execution_consumer="legacy",
        started_at=timezone.now() - timedelta(hours=3),
    )

    with pytest.raises(CommandError):
        call_command(
            "backfill_workflow_root_projections",
            "--strict-sla",
            "--sla-seconds",
            "60",
        )

    assert BatchOperation.objects.filter(id=execution_id).count() == 0

