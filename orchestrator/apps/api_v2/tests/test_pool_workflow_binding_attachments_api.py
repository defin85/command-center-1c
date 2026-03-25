from __future__ import annotations

from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.intercompany_pools.document_policy_contract import DOCUMENT_POLICY_VERSION
from apps.intercompany_pools.binding_profiles_store import (
    create_canonical_binding_profile,
    deactivate_canonical_binding_profile,
)
from apps.intercompany_pools.models import OrganizationPool, PoolWorkflowBinding
from apps.intercompany_pools.topology_template_contract import POOL_TOPOLOGY_TEMPLATE_INSTANTIATION_METADATA_KEY
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


def _build_profile_revision_payload(
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
    user = User.objects.create_user(username=f"binding-attachment-user-{uuid4().hex[:8]}", password="pass")
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
def test_pool_workflow_bindings_api_uses_attachment_contract_with_profile_refs(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    profile = create_canonical_binding_profile(
        tenant=default_tenant,
        binding_profile={
            "code": "services-publication-default",
            "name": "Services Publication",
            "revision": _build_profile_revision_payload(),
        },
        actor_username="architect",
    )
    pool_id = authenticated_client.post(
        "/api/v2/pools/upsert/",
        {
            "code": f"pool-{uuid4().hex[:6]}",
            "name": "Attachment Pool",
            "description": "",
            "is_active": True,
        },
        format="json",
    ).json()["pool"]["id"]

    create_response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": pool_id,
            "workflow_binding": {
                "binding_profile_revision_id": profile["latest_revision"]["binding_profile_revision_id"],
                "selector": {"direction": "top_down", "mode": "safe", "tags": ["baseline"]},
                "effective_from": "2026-01-01",
                "status": "active",
            },
        },
        format="json",
    )

    assert create_response.status_code == 201
    created_payload = create_response.json()["workflow_binding"]
    assert created_payload["binding_profile_id"] == profile["binding_profile_id"]
    assert created_payload["binding_profile_revision_id"] == profile["latest_revision"]["binding_profile_revision_id"]
    assert created_payload["binding_profile_revision_number"] == 1
    assert created_payload["resolved_profile"]["workflow"]["workflow_revision"] == 3
    assert created_payload["resolved_profile"]["parameters"] == {"publication_variant": "full"}
    assert created_payload["profile_lifecycle_warning"] is None
    assert "workflow" not in created_payload
    assert "decisions" not in created_payload

    list_response = authenticated_client.get(f"/api/v2/pools/workflow-bindings/?pool_id={pool_id}")
    assert list_response.status_code == 200
    listed_payload = list_response.json()
    assert listed_payload["workflow_bindings"][0]["binding_profile_revision_id"] == (
        profile["latest_revision"]["binding_profile_revision_id"]
    )
    assert listed_payload["workflow_bindings"][0]["resolved_profile"]["workflow"]["workflow_name"] == (
        "services_publication"
    )

    detail_response = authenticated_client.get(
        f"/api/v2/pools/workflow-bindings/{created_payload['binding_id']}/?pool_id={pool_id}"
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()["workflow_binding"]
    assert detail_payload["binding_profile_revision_id"] == created_payload["binding_profile_revision_id"]


@pytest.mark.django_db
def test_pool_workflow_bindings_api_rejects_new_attach_to_deactivated_profile_revision(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    profile = create_canonical_binding_profile(
        tenant=default_tenant,
        binding_profile={
            "code": "services-publication-default",
            "name": "Services Publication",
            "revision": _build_profile_revision_payload(),
        },
        actor_username="architect",
    )
    deactivate_canonical_binding_profile(
        tenant=default_tenant,
        binding_profile_id=profile["binding_profile_id"],
        actor_username="operator",
    )
    pool_id = authenticated_client.post(
        "/api/v2/pools/upsert/",
        {
            "code": f"pool-{uuid4().hex[:6]}",
            "name": "Attachment Pool",
            "description": "",
            "is_active": True,
        },
        format="json",
    ).json()["pool"]["id"]

    response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": pool_id,
            "workflow_binding": {
                "binding_profile_revision_id": profile["latest_revision"]["binding_profile_revision_id"],
                "selector": {"direction": "top_down", "mode": "safe", "tags": []},
                "effective_from": "2026-01-01",
                "status": "active",
            },
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=409,
        code="POOL_WORKFLOW_BINDING_PROFILE_LIFECYCLE_CONFLICT",
    )
    assert payload["title"] == "Pool Workflow Execution Pack Lifecycle Conflict"
    assert payload["detail"] == (
        "Pinned execution-pack revision is deactivated and cannot be attached via the default "
        "workflow binding path."
    )


@pytest.mark.django_db
def test_pool_workflow_bindings_api_fails_closed_for_legacy_rows_without_profile_refs(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    pool = OrganizationPool.objects.create(
        tenant=default_tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Attachment Pool",
    )
    legacy_binding = PoolWorkflowBinding.objects.create(
        binding_id=str(uuid4()),
        tenant=default_tenant,
        pool=pool,
        contract_version="pool_workflow_binding.v1",
        status="active",
        effective_from="2026-01-01",
        effective_to=None,
        direction="top_down",
        mode="safe",
        selector_tags=["baseline"],
        workflow_definition_key="services-publication",
        workflow_revision_id=str(uuid4()),
        workflow_revision=3,
        workflow_name="services_publication",
        decisions=[],
        parameters={"publication_variant": "full"},
        role_mapping={"initiator": "finance"},
        revision=1,
        created_by="legacy-import",
        updated_by="legacy-import",
    )

    list_response = authenticated_client.get(f"/api/v2/pools/workflow-bindings/?pool_id={pool.id}")
    list_payload = _assert_problem_details_response(
        list_response,
        status_code=400,
        code="POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING",
    )
    assert legacy_binding.binding_id in list_payload["detail"]

    detail_response = authenticated_client.get(f"/api/v2/pools/workflow-bindings/{legacy_binding.binding_id}/?pool_id={pool.id}")
    detail_payload = _assert_problem_details_response(
        detail_response,
        status_code=400,
        code="POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING",
    )
    assert legacy_binding.binding_id in detail_payload["detail"]


@pytest.mark.django_db
def test_pool_workflow_bindings_api_rejects_template_pool_attach_for_incompatible_execution_pack(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    profile = create_canonical_binding_profile(
        tenant=default_tenant,
        binding_profile={
            "code": "services-publication-default",
            "name": "Services Publication",
            "revision": _build_profile_revision_payload(),
        },
        actor_username="architect",
    )
    incompatible_decision_table_id, incompatible_decision_revision = _create_document_policy_decision(
        token="master_data.party.party_001.counterparty.ref",
    )
    profile_revision = profile["latest_revision"]
    from apps.intercompany_pools.models import BindingProfileRevision  # local import keeps test scope minimal
    record = BindingProfileRevision.objects.get(
        binding_profile_revision_id=profile_revision["binding_profile_revision_id"]
    )
    record.decisions = [
        {
            "decision_table_id": incompatible_decision_table_id,
            "decision_key": "document_policy",
            "slot_key": "document_policy",
            "decision_revision": incompatible_decision_revision,
        }
    ]
    record.metadata = {"source": "manual"}
    record.save(update_fields=["decisions", "metadata"])
    pool = OrganizationPool.objects.create(
        tenant=default_tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Attachment Pool",
        metadata={
            POOL_TOPOLOGY_TEMPLATE_INSTANTIATION_METADATA_KEY: {
                "topology_template_revision_id": "template-r1",
            }
        },
    )

    response = authenticated_client.post(
        "/api/v2/pools/workflow-bindings/upsert/",
        {
            "pool_id": str(pool.id),
            "workflow_binding": {
                "binding_profile_revision_id": profile["latest_revision"]["binding_profile_revision_id"],
                "selector": {"direction": "top_down", "mode": "safe", "tags": []},
                "effective_from": "2026-01-01",
                "status": "active",
            },
        },
        format="json",
    )

    payload = _assert_problem_details_response(
        response,
        status_code=400,
        code="EXECUTION_PACK_TEMPLATE_INCOMPATIBLE",
    )
    assert payload["title"] == "Execution Pack Template Incompatible"
    assert "/pools/execution-packs" in payload["detail"]
    assert payload["errors"][0]["slot_key"] == "document_policy"
