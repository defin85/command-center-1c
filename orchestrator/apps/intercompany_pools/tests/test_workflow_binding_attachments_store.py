from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from apps.intercompany_pools.binding_profiles_store import (
    create_canonical_binding_profile,
    deactivate_canonical_binding_profile,
)
from apps.intercompany_pools.models import BindingProfileRevision, OrganizationPool, PoolWorkflowBinding
from apps.intercompany_pools.workflow_bindings_store import upsert_canonical_pool_workflow_binding
from apps.intercompany_pools.workflow_binding_attachments_store import (
    PoolWorkflowBindingAttachmentLifecycleConflictError,
    PoolWorkflowBindingStoreError,
    get_pool_workflow_binding_attachment,
    list_pool_workflow_binding_attachments,
    upsert_pool_workflow_binding_attachment,
)
from apps.intercompany_pools.workflow_binding_attachments_contract import (
    POOL_WORKFLOW_BINDING_ATTACHMENT_CONTRACT_VERSION,
)
from apps.tenancy.models import Tenant


def _build_profile_revision_payload(*, workflow_revision: int = 3) -> dict[str, object]:
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


def _build_legacy_binding_payload(*, pool: OrganizationPool, workflow_revision: int = 3) -> dict[str, object]:
    return {
        "binding_id": f"legacy-{uuid4().hex[:10]}",
        "pool_id": str(pool.id),
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
        "selector": {
            "direction": "top_down",
            "mode": "safe",
            "tags": ["baseline"],
        },
        "effective_from": "2026-01-01",
        "status": "active",
    }


@pytest.mark.django_db
def test_upsert_pool_workflow_binding_attachment_persists_profile_refs_and_resolved_runtime_fields() -> None:
    tenant = Tenant.objects.create(slug=f"binding-attachment-{uuid4().hex[:8]}", name="Binding Attachment")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Binding Attachment Pool",
    )
    profile = create_canonical_binding_profile(
        tenant=tenant,
        binding_profile={
            "code": "services-publication-default",
            "name": "Services Publication",
            "revision": _build_profile_revision_payload(workflow_revision=3),
        },
        actor_username="architect",
    )
    revision_id = profile["latest_revision"]["binding_profile_revision_id"]

    saved_binding, created = upsert_pool_workflow_binding_attachment(
        pool=pool,
        workflow_binding={
            "binding_profile_revision_id": revision_id,
            "selector": {"direction": "top_down", "mode": "safe", "tags": ["baseline"]},
            "effective_from": "2026-01-01",
            "status": "active",
        },
        actor_username="operator",
    )

    assert created is True
    assert saved_binding["binding_profile_id"] == profile["binding_profile_id"]
    assert saved_binding["binding_profile_revision_id"] == revision_id
    assert saved_binding["binding_profile_revision_number"] == 1
    assert saved_binding["resolved_profile"]["workflow"]["workflow_revision"] == 3
    assert saved_binding["resolved_profile"]["parameters"] == {"publication_variant": "full"}
    assert saved_binding["profile_lifecycle_warning"] is None
    assert "workflow" not in saved_binding

    record = PoolWorkflowBinding.objects.get(binding_id=saved_binding["binding_id"])
    assert str(record.binding_profile_id) == profile["binding_profile_id"]
    assert record.binding_profile_revision_id == revision_id
    assert record.workflow_definition_key == "services-publication"
    assert record.parameters == {"publication_variant": "full"}
    assert record.role_mapping == {"initiator": "finance"}

    listed = list_pool_workflow_binding_attachments(pool=pool)
    assert listed == [saved_binding]
    resolved = get_pool_workflow_binding_attachment(pool=pool, binding_id=saved_binding["binding_id"])
    assert resolved == saved_binding


@pytest.mark.django_db
def test_existing_attachment_on_deactivated_profile_remains_readable_but_new_attach_is_rejected() -> None:
    tenant = Tenant.objects.create(slug=f"binding-attachment-life-{uuid4().hex[:8]}", name="Binding Attachment")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Binding Attachment Pool",
    )
    first_profile = create_canonical_binding_profile(
        tenant=tenant,
        binding_profile={
            "code": "services-publication-default",
            "name": "Services Publication",
            "revision": _build_profile_revision_payload(workflow_revision=3),
        },
        actor_username="architect",
    )
    second_profile = create_canonical_binding_profile(
        tenant=tenant,
        binding_profile={
            "code": "services-publication-backup",
            "name": "Services Publication Backup",
            "revision": _build_profile_revision_payload(workflow_revision=4),
        },
        actor_username="architect",
    )
    first_revision_id = first_profile["latest_revision"]["binding_profile_revision_id"]
    second_revision_id = second_profile["latest_revision"]["binding_profile_revision_id"]

    attachment, _ = upsert_pool_workflow_binding_attachment(
        pool=pool,
        workflow_binding={
            "binding_profile_revision_id": first_revision_id,
            "selector": {"direction": "top_down", "mode": "safe", "tags": []},
            "effective_from": "2026-01-01",
            "status": "active",
        },
        actor_username="operator",
    )

    deactivate_canonical_binding_profile(
        tenant=tenant,
        binding_profile_id=first_profile["binding_profile_id"],
        actor_username="operator",
    )

    readable = get_pool_workflow_binding_attachment(pool=pool, binding_id=attachment["binding_id"])
    assert readable["binding_profile_revision_id"] == first_revision_id
    assert readable["profile_lifecycle_warning"] == {
        "code": "BINDING_PROFILE_DEACTIVATED",
        "title": "Binding profile is deactivated",
        "detail": "Pinned reusable binding profile is deactivated and requires planned migration.",
    }

    profile_revision = BindingProfileRevision.objects.get(binding_profile_revision_id=second_revision_id)
    profile_revision.profile.status = "deactivated"
    profile_revision.profile.save(update_fields=["status", "updated_at"])

    with pytest.raises(PoolWorkflowBindingAttachmentLifecycleConflictError):
        upsert_pool_workflow_binding_attachment(
            pool=pool,
            workflow_binding={
                "binding_profile_revision_id": second_revision_id,
                "selector": {"direction": "top_down", "mode": "safe", "tags": []},
                "effective_from": "2026-01-01",
                "status": "active",
            },
            actor_username="operator",
        )


@pytest.mark.django_db
def test_list_pool_workflow_binding_attachments_fails_closed_for_legacy_rows_without_profile_refs() -> None:
    tenant = Tenant.objects.create(slug=f"binding-attachment-legacy-{uuid4().hex[:8]}", name="Binding Attachment Legacy")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Binding Attachment Legacy Pool",
    )
    legacy_binding = PoolWorkflowBinding.objects.create(
        binding_id=str(uuid4()),
        tenant=tenant,
        pool=pool,
        contract_version="pool_workflow_binding.v1",
        status="active",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        direction="top_down",
        mode="safe",
        selector_tags=["baseline"],
        workflow_definition_key="services-publication",
        workflow_revision_id=str(uuid4()),
        workflow_revision=3,
        workflow_name="services_publication",
        decisions=[
            {
                "decision_table_id": "document-policy",
                "decision_key": "document_policy",
                "slot_key": "document_policy",
                "decision_revision": 2,
            }
        ],
        parameters={"publication_variant": "full"},
        role_mapping={"initiator": "finance"},
        revision=1,
        created_by="legacy-import",
        updated_by="legacy-import",
    )

    with pytest.raises(PoolWorkflowBindingStoreError) as exc_info:
        list_pool_workflow_binding_attachments(pool=pool)

    assert str(exc_info.value) == (
        f"POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING: Workflow binding '{legacy_binding.binding_id}' "
        "is missing binding_profile references."
    )

    persisted = PoolWorkflowBinding.objects.get(binding_id=legacy_binding.binding_id)
    assert persisted.binding_profile_id is None
    assert persisted.binding_profile_revision_id is None
    assert persisted.updated_by == "legacy-import"
    assert persisted.contract_version == "pool_workflow_binding.v1"


@pytest.mark.django_db
def test_list_pool_workflow_binding_attachments_fails_closed_for_legacy_binding_without_profile_refs() -> None:
    tenant = Tenant.objects.create(slug=f"binding-attachment-legacy-{uuid4().hex[:8]}", name="Binding Attachment")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Binding Attachment Pool",
    )

    legacy_binding, _ = upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=_build_legacy_binding_payload(pool=pool, workflow_revision=3),
        actor_username="legacy-import",
    )

    record = PoolWorkflowBinding.objects.get(binding_id=legacy_binding["binding_id"])
    assert record.binding_profile_id is None
    assert record.binding_profile_revision_id is None

    with pytest.raises(PoolWorkflowBindingStoreError) as exc_info:
        list_pool_workflow_binding_attachments(pool=pool)

    assert str(exc_info.value) == (
        f"POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING: Workflow binding '{legacy_binding['binding_id']}' "
        "is missing binding_profile references."
    )

    record.refresh_from_db()
    assert record.binding_profile_id is None
    assert record.binding_profile_revision_id is None
    assert record.updated_by == "legacy-import"


@pytest.mark.django_db
def test_get_pool_workflow_binding_attachment_fails_closed_for_missing_profile_refs() -> None:
    tenant = Tenant.objects.create(slug=f"binding-attachment-detail-{uuid4().hex[:8]}", name="Binding Attachment")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Binding Attachment Pool",
    )
    legacy_binding = PoolWorkflowBinding.objects.create(
        binding_id=str(uuid4()),
        tenant=tenant,
        pool=pool,
        contract_version=POOL_WORKFLOW_BINDING_ATTACHMENT_CONTRACT_VERSION,
        status="active",
        effective_from=date(2026, 1, 1),
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

    with pytest.raises(PoolWorkflowBindingStoreError) as exc_info:
        get_pool_workflow_binding_attachment(pool=pool, binding_id=legacy_binding.binding_id)

    assert str(exc_info.value) == (
        f"POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING: Workflow binding '{legacy_binding.binding_id}' "
        "is missing binding_profile references."
    )


@pytest.mark.django_db
def test_legacy_binding_materialization_does_not_merge_profiles_across_pools() -> None:
    tenant = Tenant.objects.create(slug=f"binding-attachment-dedupe-{uuid4().hex[:8]}", name="Binding Attachment")
    first_pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="First Pool",
    )
    second_pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Second Pool",
    )

    first_binding, _ = upsert_canonical_pool_workflow_binding(
        pool=first_pool,
        workflow_binding=_build_legacy_binding_payload(pool=first_pool, workflow_revision=3),
        actor_username="legacy-import",
    )
    second_binding, _ = upsert_canonical_pool_workflow_binding(
        pool=second_pool,
        workflow_binding=_build_legacy_binding_payload(pool=second_pool, workflow_revision=3),
        actor_username="legacy-import",
    )

    first_listed = list_pool_workflow_binding_attachments(pool=first_pool)
    second_listed = list_pool_workflow_binding_attachments(pool=second_pool)

    assert first_listed[0]["binding_profile_id"] != second_listed[0]["binding_profile_id"]
    assert first_listed[0]["binding_profile_revision_id"] != second_listed[0]["binding_profile_revision_id"]

    first_record = PoolWorkflowBinding.objects.get(binding_id=first_binding["binding_id"])
    second_record = PoolWorkflowBinding.objects.get(binding_id=second_binding["binding_id"])
    assert first_record.binding_profile_revision.metadata["generated_from_pool_id"] == str(first_pool.id)
    assert second_record.binding_profile_revision.metadata["generated_from_pool_id"] == str(second_pool.id)
