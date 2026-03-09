from __future__ import annotations

import uuid

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient


@pytest.fixture
def staff_client(db):
    user = User.objects.create_user(
        username=f"decision_staff_{uuid.uuid4().hex[:8]}",
        password="pass",
        is_staff=True,
        is_superuser=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _build_decision_payload(*, decision_table_id: str | None = None) -> dict[str, object]:
    return {
        "decision_table_id": decision_table_id or f"decision-{uuid.uuid4().hex[:8]}",
        "decision_key": "document_policy",
        "name": "Document Policy Decision",
        "inputs": [
            {"name": "direction", "value_type": "string", "required": True},
            {"name": "mode", "value_type": "string", "required": True},
        ],
        "outputs": [
            {"name": "document_policy", "value_type": "json", "required": True},
        ],
        "rules": [
            {
                "rule_id": "bottom-up-safe",
                "priority": 0,
                "conditions": {
                    "direction": "bottom_up",
                    "mode": "safe",
                },
                "outputs": {
                    "document_policy": {
                        "version": "document_policy.v1",
                        "chains": [
                            {
                                "chain_id": "sale_chain",
                                "documents": [
                                    {
                                        "document_id": "sale",
                                        "entity_name": "Document_Sales",
                                        "document_role": "base",
                                        "field_mapping": {"Amount": "allocation.amount"},
                                        "table_parts_mapping": {},
                                        "link_rules": {},
                                        "invoice_mode": "required",
                                    },
                                    {
                                        "document_id": "invoice",
                                        "entity_name": "Document_Invoice",
                                        "document_role": "invoice",
                                        "field_mapping": {"BaseDocument": "sale.ref"},
                                        "table_parts_mapping": {},
                                        "link_rules": {"depends_on": "sale"},
                                        "link_to": "sale",
                                    },
                                ],
                            }
                        ],
                    }
                },
            }
        ],
    }


@pytest.mark.django_db
def test_decision_tables_api_create_list_and_detail_round_trip(staff_client: APIClient) -> None:
    create_response = staff_client.post(
        "/api/v2/decisions/",
        data=_build_decision_payload(),
        format="json",
    )

    assert create_response.status_code == 201
    created = create_response.json()["decision"]
    assert created["decision_revision"] == 1
    assert created["decision_key"] == "document_policy"
    assert created["outputs"][0]["name"] == "document_policy"

    list_response = staff_client.get("/api/v2/decisions/")
    assert list_response.status_code == 200
    listed = list_response.json()["decisions"]
    assert any(item["id"] == created["id"] for item in listed)

    detail_response = staff_client.get(f"/api/v2/decisions/{created['id']}/")
    assert detail_response.status_code == 200
    detailed = detail_response.json()["decision"]
    assert detailed["id"] == created["id"]
    assert detailed["decision_table_id"] == created["decision_table_id"]
    assert detailed["rules"][0]["outputs"]["document_policy"]["version"] == "document_policy.v1"


@pytest.mark.django_db
def test_decision_tables_api_can_create_new_revision_from_parent(staff_client: APIClient) -> None:
    first_response = staff_client.post(
        "/api/v2/decisions/",
        data=_build_decision_payload(decision_table_id="services-publication-policy"),
        format="json",
    )
    assert first_response.status_code == 201
    first = first_response.json()["decision"]

    second_response = staff_client.post(
        "/api/v2/decisions/",
        data={
            **_build_decision_payload(decision_table_id="services-publication-policy"),
            "parent_version_id": first["id"],
            "name": "Document Policy Decision v2",
        },
        format="json",
    )

    assert second_response.status_code == 201
    second = second_response.json()["decision"]
    assert second["decision_table_id"] == first["decision_table_id"]
    assert second["decision_revision"] == 2
    assert second["parent_version"] == first["id"]
