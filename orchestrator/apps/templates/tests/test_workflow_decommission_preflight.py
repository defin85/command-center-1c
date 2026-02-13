from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.templates.workflow.models import WorkflowTemplate, WorkflowType


def _create_workflow_template(name: str) -> WorkflowTemplate:
    return WorkflowTemplate.objects.create(
        name=name,
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
def test_workflow_decommission_preflight_returns_no_go_from_registry() -> None:
    out = StringIO()
    call_command("preflight_workflow_decommission_consumers", "--json", stdout=out)
    payload = json.loads(out.getvalue())

    assert payload["decision"] == "no_go"
    checks = {item["key"]: item for item in payload["checks"]}
    assert checks["registry_schema"]["ok"] is True
    assert checks["all_consumers_migrated"]["ok"] is False
    assert "pools" in checks["all_consumers_migrated"]["unmigrated_consumers"]
    assert "legacy" in checks["all_consumers_migrated"]["unmigrated_consumers"]


@pytest.mark.django_db
def test_workflow_decommission_preflight_strict_mode_fails_for_no_go() -> None:
    with pytest.raises(CommandError):
        call_command("preflight_workflow_decommission_consumers", "--strict")


@pytest.mark.django_db
def test_workflow_decommission_preflight_allows_nullable_transition_mode_for_legacy() -> None:
    template = _create_workflow_template("decommission-preflight-legacy")
    template.create_execution(
        {"operation": "legacy-no-tenant"},
        execution_consumer="legacy",
    )

    out = StringIO()
    call_command("preflight_workflow_decommission_consumers", "--json", stdout=out)
    payload = json.loads(out.getvalue())
    checks = {item["key"]: item for item in payload["checks"]}
    tenant_mode_check = checks["tenant_mode_requirements"]

    assert tenant_mode_check["ok"] is True
    assert tenant_mode_check["violations"] == []
    assert any(
        item["consumer"] == "legacy" and item["null_tenant_total"] >= 1
        for item in tenant_mode_check["transition_null_tenant_consumers"]
    )
