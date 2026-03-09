from __future__ import annotations

import uuid

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.templates.workflow.models import WorkflowTemplate


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


def _build_create_payload(*, dag_structure: dict) -> dict:
    return {
        "name": f"wf-{uuid.uuid4().hex[:8]}",
        "description": "",
        "workflow_type": "complex",
        "dag_structure": dag_structure,
        "is_active": True,
    }


def _assert_boundary_violation(response, expected_kind: str) -> None:
    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "WORKFLOW_AUTHORING_BOUNDARY_VIOLATION"
    assert expected_kind in {
        violation["kind"]
        for violation in payload["error"]["details"]["violations"]
    }


@pytest.mark.django_db
def test_create_workflow_rejects_runtime_only_parallel_nodes_on_default_authoring_path(
    staff_client,
):
    response = staff_client.post(
        "/api/v2/workflows/create-workflow/",
        data=_build_create_payload(
            dag_structure={
                "nodes": [
                    {
                        "id": "parallel1",
                        "name": "Parallel Fan-out",
                        "type": "parallel",
                        "config": {},
                        "parallel_config": {
                            "parallel_nodes": ["step-a", "step-b"],
                            "wait_for": "all",
                        },
                    }
                ],
                "edges": [],
            }
        ),
        format="json",
    )

    _assert_boundary_violation(response, "runtime_only_node_type")


@pytest.mark.django_db
def test_create_workflow_rejects_condition_nodes_without_pinned_decision_ref(staff_client):
    response = staff_client.post(
        "/api/v2/workflows/create-workflow/",
        data=_build_create_payload(
            dag_structure={
                "nodes": [
                    {
                        "id": "gate1",
                        "name": "Invoice Gate",
                        "type": "condition",
                        "config": {
                            "expression": "{{ amount > 100 }}",
                        },
                    }
                ],
                "edges": [],
            }
        ),
        format="json",
    )

    _assert_boundary_violation(response, "condition_requires_decision_ref")


@pytest.mark.django_db
def test_create_workflow_accepts_condition_nodes_with_pinned_decision_ref(staff_client):
    response = staff_client.post(
        "/api/v2/workflows/create-workflow/",
        data=_build_create_payload(
            dag_structure={
                "nodes": [
                    {
                        "id": "gate1",
                        "name": "Invoice Gate",
                        "type": "condition",
                        "decision_ref": {
                            "decision_table_id": "decision-root",
                            "decision_key": "invoice_mode",
                            "decision_revision": 2,
                        },
                        "config": {},
                    }
                ],
                "edges": [],
            }
        ),
        format="json",
    )

    assert response.status_code == 201
    node = response.json()["workflow"]["dag_structure"]["nodes"][0]
    assert node["decision_ref"]["decision_key"] == "invoice_mode"
    assert node["config"]["expression"] == "{{ decisions.invoice_mode }}"


@pytest.mark.django_db
def test_update_workflow_rejects_existing_legacy_condition_graph_even_for_metadata_only_changes(
    staff_client,
):
    workflow = WorkflowTemplate.objects.create(
        name="Legacy Gate",
        workflow_type="complex",
        dag_structure={
            "nodes": [
                {
                    "id": "gate1",
                    "name": "Legacy Gate",
                    "type": "condition",
                    "config": {"expression": "{{ amount > 100 }}"},
                }
            ],
            "edges": [],
        },
        is_active=True,
        created_by=staff_client.handler._force_user,
    )

    response = staff_client.post(
        "/api/v2/workflows/update-workflow/",
        data={"workflow_id": str(workflow.id), "name": "Renamed Legacy Gate"},
        format="json",
    )

    _assert_boundary_violation(response, "condition_requires_decision_ref")


@pytest.mark.django_db
def test_clone_workflow_rejects_edge_level_conditions_from_legacy_graph(staff_client):
    workflow = WorkflowTemplate.objects.create(
        name="Legacy Edge Conditions",
        workflow_type="complex",
        dag_structure={
            "nodes": [
                {
                    "id": "step1",
                    "name": "Step 1",
                    "type": "operation",
                    "template_id": "tpl-test-step1",
                    "config": {},
                },
                {
                    "id": "step2",
                    "name": "Step 2",
                    "type": "operation",
                    "template_id": "tpl-test-step2",
                    "config": {},
                },
            ],
            "edges": [
                {
                    "from": "step1",
                    "to": "step2",
                    "condition": "{{ amount > 100 }}",
                }
            ],
        },
        is_active=True,
        created_by=staff_client.handler._force_user,
    )

    response = staff_client.post(
        "/api/v2/workflows/clone-workflow/",
        data={"workflow_id": str(workflow.id), "new_name": "Cloned Legacy Edge Conditions"},
        format="json",
    )

    _assert_boundary_violation(response, "edge_condition_not_supported")
