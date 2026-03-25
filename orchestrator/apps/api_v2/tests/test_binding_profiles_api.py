from __future__ import annotations

from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.intercompany_pools.document_policy_contract import DOCUMENT_POLICY_VERSION
from apps.intercompany_pools.models import OrganizationPool
from apps.intercompany_pools.workflow_binding_attachments_store import upsert_pool_workflow_binding_attachment
from apps.templates.workflow.decision_tables import create_decision_table_revision
from apps.tenancy.models import Tenant, TenantMember


def _assert_problem_details_response(response, *, status_code: int, code: str) -> dict:
    assert response.status_code == status_code
    assert response.headers.get("Content-Type", "").startswith("application/problem+json")
    payload = response.json()
    assert payload.get("code") == code
    return payload


def _create_document_policy_decision(*, token: str) -> tuple[str, int]:
    decision_table_id = f"document-policy-{uuid4().hex[:8]}"
    first_revision = create_decision_table_revision(
        contract={
            "decision_table_id": decision_table_id,
            "decision_key": "document_policy",
            "name": "Document Policy",
            "inputs": [],
            "outputs": [{"name": "document_policy", "value_type": "json", "required": True}],
            "rules": [
                {
                    "rule_id": "default",
                    "priority": 0,
                    "conditions": {},
                    "outputs": {
                        "document_policy": {
                            "version": DOCUMENT_POLICY_VERSION,
                            "chains": [
                                {
                                    "chain_id": "sale_chain",
                                    "documents": [
                                        {
                                            "document_id": "sale",
                                            "entity_name": "Document_Sales",
                                            "document_role": "base",
                                            "field_mapping": {"Контрагент_Key": token},
                                            "table_parts_mapping": {},
                                            "link_rules": {},
                                        }
                                    ],
                                }
                            ],
                        }
                    },
                }
            ],
        },
    )
    latest_revision = create_decision_table_revision(
        contract={
            "decision_table_id": decision_table_id,
            "decision_key": "document_policy",
            "name": "Document Policy",
            "inputs": [],
            "outputs": [{"name": "document_policy", "value_type": "json", "required": True}],
            "rules": list(first_revision.rules or []),
        },
        parent_version=first_revision,
    )
    return decision_table_id, latest_revision.version_number


def _build_revision_payload(
    *,
    workflow_revision: int = 3,
    token: str = "master_data.party.edge.child.counterparty.ref",
) -> dict[str, object]:
    decision_table_id, decision_revision = _create_document_policy_decision(token=token)
    return {
        "workflow": {
            "workflow_definition_key": "services-publication",
            "workflow_revision_id": str(uuid4()),
            "workflow_revision": workflow_revision,
            "workflow_name": "services_publication",
        },
        "decisions": [
            {
                "decision_table_id": decision_table_id,
                "decision_key": "document_policy",
                "slot_key": "document_policy",
                "decision_revision": decision_revision,
            }
        ],
        "parameters": {
            "publication_variant": "full",
        },
        "role_mapping": {
            "initiator": "finance",
        },
        "metadata": {
            "source": "manual",
        },
    }


@pytest.fixture
def default_tenant() -> Tenant:
    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    return tenant


@pytest.fixture
def user(default_tenant: Tenant) -> User:
    user = User.objects.create_user(username=f"binding-profile-user-{uuid4().hex[:8]}", password="pass")
    TenantMember.objects.get_or_create(
        tenant=default_tenant,
        user=user,
        defaults={"role": TenantMember.ROLE_ADMIN},
    )
    return user


@pytest.fixture
def authenticated_client(user: User, default_tenant: Tenant) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_CC1C_TENANT_ID=str(default_tenant.id))
    return client


@pytest.mark.django_db
def test_binding_profiles_api_create_list_detail_revise_and_deactivate_roundtrip(
    authenticated_client: APIClient,
) -> None:
    create_response = authenticated_client.post(
        "/api/v2/pools/binding-profiles/",
        {
            "code": "services-publication-default",
            "name": "Services Publication",
            "description": "Reusable publication scheme",
            "revision": _build_revision_payload(),
        },
        format="json",
    )

    assert create_response.status_code == 201
    created_payload = create_response.json()
    binding_profile_id = created_payload["binding_profile"]["binding_profile_id"]
    assert created_payload["binding_profile"]["status"] == "active"
    assert created_payload["binding_profile"]["latest_revision_number"] == 1

    list_response = authenticated_client.get("/api/v2/pools/binding-profiles/")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["count"] == 1
    assert list_payload["binding_profiles"][0]["binding_profile_id"] == binding_profile_id

    detail_response = authenticated_client.get(f"/api/v2/pools/binding-profiles/{binding_profile_id}/")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["binding_profile"]["code"] == "services-publication-default"
    assert [item["revision_number"] for item in detail_payload["binding_profile"]["revisions"]] == [1]

    revise_response = authenticated_client.post(
        f"/api/v2/pools/binding-profiles/{binding_profile_id}/revisions/",
        {
            "revision": _build_revision_payload(workflow_revision=4),
        },
        format="json",
    )
    assert revise_response.status_code == 201
    revised_payload = revise_response.json()
    assert revised_payload["binding_profile"]["latest_revision_number"] == 2
    assert [item["revision_number"] for item in revised_payload["binding_profile"]["revisions"]] == [2, 1]

    deactivate_response = authenticated_client.post(
        f"/api/v2/pools/binding-profiles/{binding_profile_id}/deactivate/",
        {},
        format="json",
    )
    assert deactivate_response.status_code == 200
    deactivate_payload = deactivate_response.json()
    assert deactivate_payload["binding_profile"]["status"] == "deactivated"
    assert deactivate_payload["binding_profile"]["deactivated_at"] is not None

    revise_after_deactivate = authenticated_client.post(
        f"/api/v2/pools/binding-profiles/{binding_profile_id}/revisions/",
        {
            "revision": _build_revision_payload(workflow_revision=5),
        },
        format="json",
    )
    _assert_problem_details_response(
        revise_after_deactivate,
        status_code=409,
        code="BINDING_PROFILE_LIFECYCLE_CONFLICT",
    )
    lifecycle_payload = revise_after_deactivate.json()
    assert lifecycle_payload["title"] == "Execution Pack Lifecycle Conflict"
    assert "Execution pack lifecycle conflict" in lifecycle_payload["detail"]


@pytest.mark.django_db
def test_binding_profiles_api_rejects_duplicate_code_with_conflict(authenticated_client: APIClient) -> None:
    payload = {
        "code": "services-publication-default",
        "name": "Services Publication",
        "revision": _build_revision_payload(),
    }
    first = authenticated_client.post("/api/v2/pools/binding-profiles/", payload, format="json")
    assert first.status_code == 201

    duplicate = authenticated_client.post("/api/v2/pools/binding-profiles/", payload, format="json")
    _assert_problem_details_response(
        duplicate,
        status_code=409,
        code="BINDING_PROFILE_CODE_CONFLICT",
    )
    duplicate_payload = duplicate.json()
    assert duplicate_payload["title"] == "Execution Pack Code Conflict"
    assert "Execution pack code conflict" in duplicate_payload["detail"]


@pytest.mark.django_db
def test_binding_profile_detail_includes_scoped_attachment_usage_summary(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    create_response = authenticated_client.post(
        "/api/v2/pools/binding-profiles/",
        {
            "code": "services-publication-default",
            "name": "Services Publication",
            "description": "Reusable publication scheme",
            "revision": _build_revision_payload(),
        },
        format="json",
    )
    assert create_response.status_code == 201
    binding_profile = create_response.json()["binding_profile"]
    binding_profile_id = binding_profile["binding_profile_id"]
    first_revision_id = binding_profile["latest_revision"]["binding_profile_revision_id"]

    revise_response = authenticated_client.post(
        f"/api/v2/pools/binding-profiles/{binding_profile_id}/revisions/",
        {
            "revision": _build_revision_payload(workflow_revision=4),
        },
        format="json",
    )
    assert revise_response.status_code == 201
    revised_binding_profile = revise_response.json()["binding_profile"]
    second_revision_id = revised_binding_profile["latest_revision"]["binding_profile_revision_id"]

    first_pool = OrganizationPool.objects.create(
        tenant=default_tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="First Pool",
    )
    second_pool = OrganizationPool.objects.create(
        tenant=default_tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Second Pool",
    )

    upsert_pool_workflow_binding_attachment(
        pool=first_pool,
        workflow_binding={
            "binding_profile_revision_id": first_revision_id,
            "selector": {"direction": "top_down", "mode": "safe", "tags": ["baseline"]},
            "effective_from": "2026-01-01",
            "status": "active",
        },
        actor_username="operator",
    )
    upsert_pool_workflow_binding_attachment(
        pool=second_pool,
        workflow_binding={
            "binding_profile_revision_id": second_revision_id,
            "selector": {"direction": "bottom_up", "mode": "safe", "tags": []},
            "effective_from": "2026-02-01",
            "status": "draft",
        },
        actor_username="operator",
    )

    detail_response = authenticated_client.get(f"/api/v2/pools/binding-profiles/{binding_profile_id}/")
    assert detail_response.status_code == 200
    usage_summary = detail_response.json()["binding_profile"]["usage_summary"]

    assert usage_summary["attachment_count"] == 2
    assert len(usage_summary["revision_summary"]) == 2
    assert {item["binding_profile_revision_id"] for item in usage_summary["revision_summary"]} == {
        first_revision_id,
        second_revision_id,
    }
    attachments_by_pool_id = {
        item["pool_id"]: item
        for item in usage_summary["attachments"]
    }
    assert set(attachments_by_pool_id) == {str(first_pool.id), str(second_pool.id)}
    first_attachment = attachments_by_pool_id[str(first_pool.id)]
    assert first_attachment["pool_code"] == first_pool.code
    assert first_attachment["binding_id"]
    assert first_attachment["binding_profile_revision_id"] == first_revision_id
    assert first_attachment["selector"] == {
        "direction": "top_down",
        "mode": "safe",
        "tags": ["baseline"],
    }


@pytest.mark.django_db
def test_binding_profiles_api_rejects_concrete_participant_refs_with_machine_readable_diagnostics(
    authenticated_client: APIClient,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/binding-profiles/",
        {
            "code": "services-publication-default",
            "name": "Services Publication",
            "description": "Reusable publication scheme",
            "revision": _build_revision_payload(
                token="master_data.party.party_001.counterparty.ref",
            ),
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED",
    )
    assert payload["title"] == "Execution Pack Topology Alias Required"
    assert "/decisions" in payload["detail"]
    assert payload["errors"] == [
        {
            "code": "EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED",
            "slot_key": "document_policy",
            "decision_table_id": payload["errors"][0]["decision_table_id"],
            "decision_revision": 2,
            "field_or_table_path": "document_policy.chains[0].documents[0].field_mapping.Контрагент_Key",
            "detail": (
                "Reusable execution-pack participant refs must use topology-aware aliases "
                "instead of concrete master_data.party/master_data.contract refs."
            ),
        }
    ]
