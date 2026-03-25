from __future__ import annotations

from uuid import uuid4

import pytest

from apps.intercompany_pools.binding_profile_topology_compatibility import (
    EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED,
)
from apps.intercompany_pools.binding_profiles_store import (
    BindingProfileCodeConflictError,
    BindingProfileLifecycleConflictError,
    BindingProfileTopologyCompatibilityError,
    create_canonical_binding_profile,
    deactivate_canonical_binding_profile,
    get_canonical_binding_profile,
    list_canonical_binding_profiles,
    revise_canonical_binding_profile,
)
from apps.intercompany_pools.document_policy_contract import DOCUMENT_POLICY_VERSION
from apps.intercompany_pools.models import BindingProfile, BindingProfileRevision
from apps.templates.workflow.decision_tables import create_decision_table_revision
from apps.tenancy.models import Tenant


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


@pytest.mark.django_db
def test_create_binding_profile_persists_initial_revision_and_latest_summary() -> None:
    tenant = Tenant.objects.create(slug=f"binding-profile-{uuid4().hex[:8]}", name="Binding Profiles")

    profile = create_canonical_binding_profile(
        tenant=tenant,
        binding_profile={
            "code": "services-publication-default",
            "name": "Services Publication",
            "description": "Reusable publication scheme",
            "revision": _build_revision_payload(),
        },
        actor_username="architect",
    )

    record = BindingProfile.objects.get(id=profile["binding_profile_id"])
    revision = BindingProfileRevision.objects.get(profile=record, revision_number=1)

    assert record.tenant_id == tenant.id
    assert record.code == "services-publication-default"
    assert record.status == "active"
    assert record.created_by == "architect"
    assert record.updated_by == "architect"

    assert revision.binding_profile_revision_id == profile["latest_revision"]["binding_profile_revision_id"]
    assert revision.workflow_definition_key == "services-publication"
    assert revision.workflow_revision == 3
    assert revision.decisions == profile["latest_revision"]["decisions"]
    assert revision.parameters == {"publication_variant": "full"}
    assert revision.role_mapping == {"initiator": "finance"}
    assert revision.metadata == {
        "source": "manual",
        "_topology_template_compatibility": {
            "status": "compatible",
            "topology_aware_ready": True,
            "covered_slot_keys": ["document_policy"],
            "diagnostics": [],
        },
    }
    assert revision.created_by == "architect"

    listed = list_canonical_binding_profiles(tenant=tenant)
    assert len(listed) == 1
    assert listed[0]["binding_profile_id"] == profile["binding_profile_id"]
    assert listed[0]["latest_revision_number"] == 1
    assert listed[0]["latest_revision"]["binding_profile_revision_id"] == revision.binding_profile_revision_id

    resolved = get_canonical_binding_profile(tenant=tenant, binding_profile_id=profile["binding_profile_id"])
    assert resolved["binding_profile_id"] == profile["binding_profile_id"]
    assert [item["revision_number"] for item in resolved["revisions"]] == [1]
    assert resolved["latest_revision"]["topology_template_compatibility"]["status"] == "compatible"
    assert resolved["latest_revision"]["topology_template_compatibility"]["covered_slot_keys"] == ["document_policy"]


@pytest.mark.django_db
def test_revise_binding_profile_creates_new_immutable_revision_without_rewriting_previous_one() -> None:
    tenant = Tenant.objects.create(slug=f"binding-profile-revise-{uuid4().hex[:8]}", name="Binding Profiles")
    created = create_canonical_binding_profile(
        tenant=tenant,
        binding_profile={
            "code": "services-publication-default",
            "name": "Services Publication",
            "revision": _build_revision_payload(workflow_revision=3),
        },
        actor_username="architect",
    )
    first_revision_id = created["latest_revision"]["binding_profile_revision_id"]

    revised = revise_canonical_binding_profile(
        tenant=tenant,
        binding_profile_id=created["binding_profile_id"],
        revision=_build_revision_payload(workflow_revision=4),
        actor_username="editor",
    )

    revisions = list(
        BindingProfileRevision.objects.filter(profile_id=created["binding_profile_id"]).order_by("revision_number")
    )
    assert [item.revision_number for item in revisions] == [1, 2]
    assert revisions[0].binding_profile_revision_id == first_revision_id
    assert revisions[0].workflow_revision == 3
    assert revisions[1].workflow_revision == 4
    assert revised["latest_revision_number"] == 2
    assert revised["latest_revision"]["binding_profile_revision_id"] != first_revision_id
    assert [item["revision_number"] for item in revised["revisions"]] == [2, 1]


@pytest.mark.django_db
def test_deactivate_binding_profile_blocks_new_revisions_but_keeps_existing_revisions_readable() -> None:
    tenant = Tenant.objects.create(slug=f"binding-profile-deactivate-{uuid4().hex[:8]}", name="Binding Profiles")
    created = create_canonical_binding_profile(
        tenant=tenant,
        binding_profile={
            "code": "services-publication-default",
            "name": "Services Publication",
            "revision": _build_revision_payload(),
        },
        actor_username="architect",
    )

    deactivated = deactivate_canonical_binding_profile(
        tenant=tenant,
        binding_profile_id=created["binding_profile_id"],
        actor_username="operator",
    )

    assert deactivated["status"] == "deactivated"
    assert deactivated["deactivated_by"] == "operator"
    assert deactivated["deactivated_at"] is not None
    assert deactivated["latest_revision"]["binding_profile_revision_id"] == created["latest_revision"]["binding_profile_revision_id"]

    with pytest.raises(BindingProfileLifecycleConflictError):
        revise_canonical_binding_profile(
            tenant=tenant,
            binding_profile_id=created["binding_profile_id"],
            revision=_build_revision_payload(workflow_revision=4),
            actor_username="editor",
        )

    resolved = get_canonical_binding_profile(tenant=tenant, binding_profile_id=created["binding_profile_id"])
    assert resolved["status"] == "deactivated"
    assert [item["revision_number"] for item in resolved["revisions"]] == [1]


@pytest.mark.django_db
def test_create_binding_profile_rejects_duplicate_code_within_tenant() -> None:
    tenant = Tenant.objects.create(slug=f"binding-profile-code-{uuid4().hex[:8]}", name="Binding Profiles")
    create_canonical_binding_profile(
        tenant=tenant,
        binding_profile={
            "code": "services-publication-default",
            "name": "Services Publication",
            "revision": _build_revision_payload(),
        },
        actor_username="architect",
    )

    with pytest.raises(BindingProfileCodeConflictError):
        create_canonical_binding_profile(
            tenant=tenant,
            binding_profile={
                "code": "services-publication-default",
                "name": "Services Publication Duplicate",
                "revision": _build_revision_payload(workflow_revision=4),
            },
            actor_username="architect",
        )


@pytest.mark.django_db
def test_create_binding_profile_rejects_concrete_participant_refs_for_template_reusable_authoring() -> None:
    tenant = Tenant.objects.create(slug=f"binding-profile-topology-{uuid4().hex[:8]}", name="Binding Profiles")

    with pytest.raises(BindingProfileTopologyCompatibilityError) as exc_info:
        create_canonical_binding_profile(
            tenant=tenant,
            binding_profile={
                "code": "services-publication-default",
                "name": "Services Publication",
                "revision": _build_revision_payload(
                    token="master_data.party.party_001.counterparty.ref",
                ),
            },
            actor_username="architect",
        )

    assert str(exc_info.value) == "Execution pack revision is not reusable for template-based topology authoring."
    assert exc_info.value.code == EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED
    assert exc_info.value.errors == [
        {
            "code": EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED,
            "slot_key": "document_policy",
            "decision_table_id": exc_info.value.errors[0]["decision_table_id"],
            "decision_revision": 2,
            "field_or_table_path": "document_policy.chains[0].documents[0].field_mapping.Контрагент_Key",
            "detail": (
                "Reusable execution-pack participant refs must use topology-aware aliases "
                "instead of concrete master_data.party/master_data.contract refs."
            ),
        }
    ]
