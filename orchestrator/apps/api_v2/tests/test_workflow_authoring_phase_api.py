from __future__ import annotations

import uuid

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.runtime_settings.models import RuntimeSetting
from apps.templates.workflow.models import WorkflowCategory, WorkflowTemplate, WorkflowType


WORKFLOW_AUTHORING_PHASE_KEY = "workflows.authoring.phase"


@pytest.fixture
def staff_client(db):
    user = User.objects.create_user(
        username=f"workflow_authoring_staff_{uuid.uuid4().hex[:8]}",
        password="pass",
        is_staff=True,
        is_superuser=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _minimal_dag() -> dict[str, object]:
    return {
        "nodes": [
            {
                "id": "start",
                "name": "Start",
                "type": "operation",
                "template_id": "noop",
            }
        ],
        "edges": [],
    }


def _create_workflow(
    *,
    name: str,
    category: str,
    is_template: bool = True,
) -> WorkflowTemplate:
    return WorkflowTemplate.objects.create(
        name=name,
        description=f"{name} description",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure=_minimal_dag(),
        is_valid=True,
        is_active=True,
        category=category,
        is_template=is_template,
    )


@pytest.mark.django_db
def test_list_workflows_returns_active_authoring_phase_by_default(staff_client):
    response = staff_client.get("/api/v2/workflows/list-workflows/")

    assert response.status_code == 200
    payload = response.json()
    phase = payload["authoring_phase"]
    assert phase["phase"] == "workflow_centric_active"
    assert phase["is_prerequisite_platform_phase"] is False
    assert phase["analyst_surface"] == "/workflows"
    assert phase["source"] == "default"
    assert phase["rollout_scope"] == ["pool_distribution", "pool_publication"]
    assert phase["deferred_scope"] == ["extensions.*", "database.ib_user.*"]
    assert phase["follow_up_changes"] == ["add-13-service-workflow-automation"]
    assert phase["construct_visibility"]["contract_version"] == "workflow_construct_visibility.v1"
    assert phase["construct_visibility"]["public_constructs"] == [
        "operation_task",
        "decision_gate",
        "approval_gate",
        "subworkflow_call",
        "explicit_io",
        "pinned_template_binding",
        "pinned_subworkflow_binding",
        "decision_table",
    ]
    assert phase["construct_visibility"]["internal_runtime_only_constructs"] == [
        "condition",
        "parallel",
        "loop",
        "generated_runtime_projection",
        "compiled_document_policy",
        "document_plan_artifact",
    ]
    assert phase["construct_visibility"]["compatibility_constructs"] == [
        "template_id",
        "alias_latest_operation_binding",
        "workflow_executor_kind_template",
    ]


@pytest.mark.django_db
def test_list_workflows_respects_runtime_setting_for_authoring_phase(staff_client):
    RuntimeSetting.objects.update_or_create(
        key=WORKFLOW_AUTHORING_PHASE_KEY,
        defaults={"value": "legacy_technical_dag"},
    )

    response = staff_client.get("/api/v2/workflows/list-workflows/")

    assert response.status_code == 200
    payload = response.json()
    phase = payload["authoring_phase"]
    assert phase["phase"] == "legacy_technical_dag"
    assert phase["is_prerequisite_platform_phase"] is False
    assert phase["source"] == "global"
    assert phase["deferred_scope"] == []
    assert phase["follow_up_changes"] == []
    assert phase["construct_visibility"]["public_constructs"][0] == "operation_task"


@pytest.mark.django_db
def test_list_workflows_separates_authored_and_runtime_diagnostic_surfaces(staff_client):
    _create_workflow(name="Analyst Workflow", category=WorkflowCategory.CUSTOM)
    _create_workflow(
        name="Runtime Projection",
        category=WorkflowCategory.SYSTEM,
        is_template=False,
    )

    analyst_response = staff_client.get("/api/v2/workflows/list-workflows/")
    runtime_response = staff_client.get(
        "/api/v2/workflows/list-workflows/",
        {"surface": "runtime_diagnostics"},
    )

    assert analyst_response.status_code == 200
    analyst_workflows = analyst_response.json()["workflows"]
    assert [item["name"] for item in analyst_workflows] == ["Analyst Workflow"]
    assert analyst_workflows[0]["management_mode"] == "user_authored"
    assert analyst_workflows[0]["visibility_surface"] == "workflow_library"
    assert analyst_workflows[0]["is_system_managed"] is False

    assert runtime_response.status_code == 200
    runtime_workflows = runtime_response.json()["workflows"]
    assert [item["name"] for item in runtime_workflows] == ["Runtime Projection"]
    assert runtime_workflows[0]["management_mode"] == "system_managed"
    assert runtime_workflows[0]["visibility_surface"] == "runtime_diagnostics"
    assert runtime_workflows[0]["is_system_managed"] is True
    assert "read-only" in runtime_workflows[0]["read_only_reason"].lower()


@pytest.mark.django_db
def test_get_workflow_returns_management_metadata_for_runtime_projection(staff_client):
    workflow = _create_workflow(
        name="Runtime Projection",
        category=WorkflowCategory.SYSTEM,
        is_template=False,
    )

    response = staff_client.get(
        "/api/v2/workflows/get-workflow/",
        {"workflow_id": str(workflow.id)},
    )

    assert response.status_code == 200
    payload = response.json()["workflow"]
    assert payload["category"] == WorkflowCategory.SYSTEM
    assert payload["management_mode"] == "system_managed"
    assert payload["visibility_surface"] == "runtime_diagnostics"
    assert payload["is_system_managed"] is True
    assert "read-only" in payload["read_only_reason"].lower()


@pytest.mark.django_db
def test_system_managed_workflow_rejects_mutating_and_execute_endpoints(staff_client):
    workflow = _create_workflow(
        name="Runtime Projection",
        category=WorkflowCategory.SYSTEM,
        is_template=False,
    )

    responses = [
        staff_client.post(
            "/api/v2/workflows/update-workflow/",
            {"workflow_id": str(workflow.id), "name": "Updated"},
            format="json",
        ),
        staff_client.post(
            "/api/v2/workflows/clone-workflow/",
            {"workflow_id": str(workflow.id), "new_name": "Clone"},
            format="json",
        ),
        staff_client.post(
            "/api/v2/workflows/delete-workflow/",
            {"workflow_id": str(workflow.id)},
            format="json",
        ),
        staff_client.post(
            "/api/v2/workflows/validate-workflow/",
            {"workflow_id": str(workflow.id)},
            format="json",
        ),
        staff_client.post(
            "/api/v2/workflows/execute-workflow/",
            {"workflow_id": str(workflow.id), "input_context": {}, "mode": "async"},
            format="json",
        ),
    ]

    for response in responses:
        assert response.status_code == 409
        payload = response.json()
        assert payload["error"]["code"] == "WORKFLOW_SYSTEM_MANAGED_READ_ONLY"
