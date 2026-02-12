from __future__ import annotations

import json
import uuid

import pytest
from django.contrib.auth.models import User
from django.db import connection
from rest_framework.test import APIClient

from apps.runtime_settings.models import RuntimeSetting


ENFORCE_PINNED_KEY = "workflows.operation_binding.enforce_pinned"


@pytest.fixture
def staff_client(db):
    user = User.objects.create_user(
        username=f"workflow_binding_staff_{uuid.uuid4().hex[:8]}",
        password="pass",
        is_staff=True,
        is_superuser=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _build_create_payload(*, pinned: bool, io: dict | None = None) -> dict:
    node: dict = {
        "id": "step1",
        "name": "Step 1",
        "type": "operation",
        "template_id": "tpl-test-step1",
        "config": {},
    }
    if io is not None:
        node["io"] = io
    if pinned:
        node["operation_ref"] = {
            "alias": "tpl-test-step1",
            "binding_mode": "pinned_exposure",
            "template_exposure_id": str(uuid.uuid4()),
            "template_exposure_revision": 1,
        }
    return {
        "name": f"wf-{uuid.uuid4().hex[:8]}",
        "description": "",
        "workflow_type": "complex",
        "dag_structure": {"nodes": [node], "edges": []},
        "is_active": True,
    }


@pytest.mark.django_db
def test_create_workflow_allows_alias_latest_when_enforcement_disabled(staff_client):
    response = staff_client.post(
        "/api/v2/workflows/create-workflow/",
        data=_build_create_payload(pinned=False),
        format="json",
    )

    assert response.status_code == 201
    node = response.json()["workflow"]["dag_structure"]["nodes"][0]
    assert node["template_id"] == "tpl-test-step1"
    assert node["operation_ref"]["alias"] == "tpl-test-step1"
    assert node["operation_ref"]["binding_mode"] == "alias_latest"
    assert node["io"]["mode"] == "implicit_legacy"
    assert node["io"]["input_mapping"] == {}
    assert node["io"]["output_mapping"] == {}


@pytest.mark.django_db
def test_create_workflow_rejects_alias_latest_when_enforcement_enabled(staff_client):
    RuntimeSetting.objects.update_or_create(
        key=ENFORCE_PINNED_KEY,
        defaults={"value": True},
    )

    response = staff_client.post(
        "/api/v2/workflows/create-workflow/",
        data=_build_create_payload(pinned=False),
        format="json",
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "TEMPLATE_PIN_REQUIRED"
    assert payload["error"]["details"]["node_ids"] == ["step1"]


@pytest.mark.django_db
def test_create_workflow_accepts_pinned_binding_when_enforcement_enabled(staff_client):
    RuntimeSetting.objects.update_or_create(
        key=ENFORCE_PINNED_KEY,
        defaults={"value": True},
    )

    response = staff_client.post(
        "/api/v2/workflows/create-workflow/",
        data=_build_create_payload(pinned=True),
        format="json",
    )

    assert response.status_code == 201
    node = response.json()["workflow"]["dag_structure"]["nodes"][0]
    assert node["operation_ref"]["binding_mode"] == "pinned_exposure"
    assert node["operation_ref"]["template_exposure_id"]
    assert node["operation_ref"]["template_exposure_revision"] == 1


@pytest.mark.django_db
def test_update_workflow_rejects_non_pinned_existing_dag_when_enforcement_enabled(staff_client):
    create_response = staff_client.post(
        "/api/v2/workflows/create-workflow/",
        data=_build_create_payload(pinned=False),
        format="json",
    )
    assert create_response.status_code == 201
    workflow_id = create_response.json()["workflow"]["id"]

    RuntimeSetting.objects.update_or_create(
        key=ENFORCE_PINNED_KEY,
        defaults={"value": True},
    )

    response = staff_client.post(
        "/api/v2/workflows/update-workflow/",
        data={"workflow_id": workflow_id, "name": "Renamed"},
        format="json",
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "TEMPLATE_PIN_REQUIRED"
    assert payload["error"]["details"]["node_ids"] == ["step1"]


@pytest.mark.django_db
def test_update_workflow_lazy_upgrades_template_id_only_dag(staff_client):
    create_response = staff_client.post(
        "/api/v2/workflows/create-workflow/",
        data=_build_create_payload(pinned=False),
        format="json",
    )
    assert create_response.status_code == 201
    workflow_id = create_response.json()["workflow"]["id"]

    legacy_dag = {
        "nodes": [
            {
                "id": "step1",
                "name": "Step 1",
                "type": "operation",
                "template_id": "tpl-test-step1",
                "config": {},
            }
        ],
        "edges": [],
    }

    response = staff_client.post(
        "/api/v2/workflows/update-workflow/",
        data={"workflow_id": workflow_id, "dag_structure": legacy_dag},
        format="json",
    )

    assert response.status_code == 200
    node = response.json()["workflow"]["dag_structure"]["nodes"][0]
    assert node["template_id"] == "tpl-test-step1"
    assert node["operation_ref"]["alias"] == "tpl-test-step1"
    assert node["operation_ref"]["binding_mode"] == "alias_latest"
    assert node["io"]["mode"] == "implicit_legacy"


@pytest.mark.django_db
def test_update_workflow_preserves_explicit_io_contract(staff_client):
    create_response = staff_client.post(
        "/api/v2/workflows/create-workflow/",
        data=_build_create_payload(
            pinned=False,
            io={
                "mode": "explicit_strict",
                "input_mapping": {"params.database_id": "workflow.input.database.id"},
                "output_mapping": {"workflow.state.result": "result"},
            },
        ),
        format="json",
    )
    assert create_response.status_code == 201
    workflow_id = create_response.json()["workflow"]["id"]

    updated_dag = {
        "nodes": [
            {
                "id": "step1",
                "name": "Step 1",
                "type": "operation",
                "template_id": "tpl-test-step1",
                "config": {},
                "io": {
                    "mode": "explicit_strict",
                    "input_mapping": {"params.database_id": "workflow.input.database.id"},
                    "output_mapping": {"workflow.state.result": "result"},
                },
            }
        ],
        "edges": [],
    }

    update_response = staff_client.post(
        "/api/v2/workflows/update-workflow/",
        data={"workflow_id": workflow_id, "dag_structure": updated_dag},
        format="json",
    )
    assert update_response.status_code == 200
    updated_node = update_response.json()["workflow"]["dag_structure"]["nodes"][0]
    assert updated_node["io"]["mode"] == "explicit_strict"
    assert updated_node["io"]["input_mapping"] == {
        "params.database_id": "workflow.input.database.id",
    }
    assert updated_node["io"]["output_mapping"] == {
        "workflow.state.result": "result",
    }

    get_response = staff_client.get(
        "/api/v2/workflows/get-workflow/",
        {"workflow_id": workflow_id},
    )
    assert get_response.status_code == 200
    persisted_node = get_response.json()["workflow"]["dag_structure"]["nodes"][0]
    assert persisted_node["io"]["mode"] == "explicit_strict"
    assert persisted_node["io"]["input_mapping"] == {
        "params.database_id": "workflow.input.database.id",
    }
    assert persisted_node["io"]["output_mapping"] == {
        "workflow.state.result": "result",
    }


@pytest.mark.django_db
def test_create_workflow_rejects_reserved_io_target_path(staff_client):
    response = staff_client.post(
        "/api/v2/workflows/create-workflow/",
        data=_build_create_payload(
            pinned=False,
            io={
                "mode": "explicit_strict",
                "input_mapping": {"nodes.step1": "workflow.input.database.id"},
            },
        ),
        format="json",
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "CREATE_ERROR"
    assert "reserved root 'nodes'" in payload["error"]["message"]


@pytest.mark.django_db
def test_update_workflow_rejects_invalid_io_path_format(staff_client):
    create_response = staff_client.post(
        "/api/v2/workflows/create-workflow/",
        data=_build_create_payload(pinned=False),
        format="json",
    )
    assert create_response.status_code == 201
    workflow_id = create_response.json()["workflow"]["id"]

    invalid_dag = {
        "nodes": [
            {
                "id": "step1",
                "name": "Step 1",
                "type": "operation",
                "template_id": "tpl-test-step1",
                "config": {},
                "io": {
                    "mode": "explicit_strict",
                    "input_mapping": {"params..database_id": "workflow.input.database.id"},
                },
            }
        ],
        "edges": [],
    }

    response = staff_client.post(
        "/api/v2/workflows/update-workflow/",
        data={"workflow_id": workflow_id, "dag_structure": invalid_dag},
        format="json",
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "UPDATE_ERROR"
    assert "dot-notation without empty segments" in payload["error"]["message"]


@pytest.mark.django_db
def test_get_workflow_read_path_supports_legacy_dag_without_operation_ref(staff_client):
    create_response = staff_client.post(
        "/api/v2/workflows/create-workflow/",
        data=_build_create_payload(pinned=False),
        format="json",
    )
    assert create_response.status_code == 201
    workflow_id = create_response.json()["workflow"]["id"]

    legacy_dag = {
        "nodes": [
            {
                "id": "step1",
                "name": "Step 1",
                "type": "operation",
                "template_id": "tpl-test-step1",
                "config": {},
            }
        ],
        "edges": [],
    }
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE workflow_templates SET dag_structure = %s WHERE id = %s",
            [json.dumps(legacy_dag), workflow_id],
        )

    response = staff_client.get(
        "/api/v2/workflows/get-workflow/",
        {"workflow_id": workflow_id},
    )

    assert response.status_code == 200
    node = response.json()["workflow"]["dag_structure"]["nodes"][0]
    assert node["template_id"] == "tpl-test-step1"
    assert node["operation_ref"]["alias"] == "tpl-test-step1"
