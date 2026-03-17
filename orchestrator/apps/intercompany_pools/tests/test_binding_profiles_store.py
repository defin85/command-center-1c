from __future__ import annotations

from uuid import uuid4

import pytest

from apps.intercompany_pools.binding_profiles_store import (
    BindingProfileCodeConflictError,
    BindingProfileLifecycleConflictError,
    create_canonical_binding_profile,
    deactivate_canonical_binding_profile,
    get_canonical_binding_profile,
    list_canonical_binding_profiles,
    revise_canonical_binding_profile,
)
from apps.intercompany_pools.models import BindingProfile, BindingProfileRevision
from apps.tenancy.models import Tenant


def _build_revision_payload(*, workflow_revision: int = 3) -> dict[str, object]:
    return {
        "workflow": {
            "workflow_definition_key": "services-publication",
            "workflow_revision_id": str(uuid4()),
            "workflow_revision": workflow_revision,
            "workflow_name": "services_publication",
        },
        "decisions": [
            {
                "decision_table_id": "document-policy",
                "decision_key": "document_policy",
                "slot_key": "document_policy",
                "decision_revision": 2,
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
    assert revision.metadata == {"source": "manual"}
    assert revision.created_by == "architect"

    listed = list_canonical_binding_profiles(tenant=tenant)
    assert len(listed) == 1
    assert listed[0]["binding_profile_id"] == profile["binding_profile_id"]
    assert listed[0]["latest_revision_number"] == 1
    assert listed[0]["latest_revision"]["binding_profile_revision_id"] == revision.binding_profile_revision_id

    resolved = get_canonical_binding_profile(tenant=tenant, binding_profile_id=profile["binding_profile_id"])
    assert resolved["binding_profile_id"] == profile["binding_profile_id"]
    assert [item["revision_number"] for item in resolved["revisions"]] == [1]


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
