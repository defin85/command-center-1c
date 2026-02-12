from __future__ import annotations

import io
import json

import pytest
from django.core.management import call_command
from django.db import connection

from apps.templates.workflow.models import WorkflowTemplate


def _legacy_dag(template_id: str = "tpl-legacy") -> dict:
    return {
        "nodes": [
            {
                "id": "step1",
                "name": "Step 1",
                "type": "operation",
                "template_id": template_id,
                "config": {},
            }
        ],
        "edges": [],
    }


def _force_raw_legacy_dag(workflow_id, dag: dict) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE workflow_templates SET dag_structure = %s WHERE id = %s",
            [json.dumps(dag), str(workflow_id)],
        )


def _raw_dag(workflow_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT dag_structure FROM workflow_templates WHERE id = %s", [str(workflow_id)])
        row = cursor.fetchone()
    if not row:
        raise AssertionError(f"workflow {workflow_id} not found")
    value = row[0]
    if isinstance(value, str):
        return json.loads(value)
    return value


@pytest.mark.django_db
def test_backfill_workflow_operation_refs_dry_run_does_not_mutate(admin_user):
    workflow = WorkflowTemplate.objects.create(
        name="Backfill Dry Run",
        workflow_type="complex",
        dag_structure=_legacy_dag("tpl-dry"),
        created_by=admin_user,
        is_valid=True,
        is_active=True,
    )
    _force_raw_legacy_dag(workflow.id, _legacy_dag("tpl-dry"))
    assert "operation_ref" not in _raw_dag(workflow.id)["nodes"][0]

    out = io.StringIO()
    call_command("backfill_workflow_operation_refs", "--dry-run", stdout=out)
    output = out.getvalue()

    assert "changed: 1" in output
    assert "updated: 0" in output
    assert "DRY RUN: transaction rolled back" in output
    assert "operation_ref" not in _raw_dag(workflow.id)["nodes"][0]


@pytest.mark.django_db
def test_backfill_workflow_operation_refs_apply_updates_legacy_dag(admin_user):
    workflow = WorkflowTemplate.objects.create(
        name="Backfill Apply",
        workflow_type="complex",
        dag_structure=_legacy_dag("tpl-apply"),
        created_by=admin_user,
        is_valid=True,
        is_active=True,
    )
    _force_raw_legacy_dag(workflow.id, _legacy_dag("tpl-apply"))
    assert "operation_ref" not in _raw_dag(workflow.id)["nodes"][0]

    out = io.StringIO()
    call_command("backfill_workflow_operation_refs", stdout=out)
    output = out.getvalue()

    assert "changed: 1" in output
    assert "updated: 1" in output

    node = _raw_dag(workflow.id)["nodes"][0]
    assert node["template_id"] == "tpl-apply"
    assert node["operation_ref"]["alias"] == "tpl-apply"
    assert node["operation_ref"]["binding_mode"] == "alias_latest"


@pytest.mark.django_db
def test_backfill_workflow_operation_refs_is_idempotent(admin_user):
    workflow = WorkflowTemplate.objects.create(
        name="Backfill Idempotent",
        workflow_type="complex",
        dag_structure=_legacy_dag("tpl-idem"),
        created_by=admin_user,
        is_valid=True,
        is_active=True,
    )
    _force_raw_legacy_dag(workflow.id, _legacy_dag("tpl-idem"))

    call_command("backfill_workflow_operation_refs")

    out = io.StringIO()
    call_command("backfill_workflow_operation_refs", stdout=out)
    output = out.getvalue()
    assert "changed: 0" in output
    assert "updated: 0" in output
