from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from apps.intercompany_pools.binding_profiles_store import (
    create_canonical_binding_profile,
    deactivate_canonical_binding_profile,
)
from apps.intercompany_pools.document_policy_contract import DOCUMENT_POLICY_VERSION
from apps.intercompany_pools.models import BindingProfileRevision, OrganizationPool, PoolWorkflowBinding
from apps.intercompany_pools.topology_template_contract import POOL_TOPOLOGY_TEMPLATE_INSTANTIATION_METADATA_KEY
from apps.intercompany_pools.workflow_bindings_store import upsert_canonical_pool_workflow_binding
from apps.intercompany_pools.workflow_binding_attachments_store import (
    PoolWorkflowBindingAttachmentLifecycleConflictError,
    PoolWorkflowBindingStoreError,
    PoolWorkflowBindingTemplateCompatibilityError,
    get_pool_workflow_binding_attachments_collection,
    get_pool_workflow_binding_attachment,
    list_pool_workflow_binding_attachments,
    upsert_pool_workflow_binding_attachment,
)
from apps.intercompany_pools.workflow_binding_attachments_contract import (
    POOL_WORKFLOW_BINDING_ATTACHMENT_CONTRACT_VERSION,
)
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
    assert saved_binding["resolved_profile"]["topology_template_compatibility"]["status"] == "compatible"
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
        "title": "Execution pack is deactivated",
        "detail": "Pinned reusable execution-pack revision is deactivated and requires planned migration.",
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
def test_legacy_bindings_without_profile_refs_fail_closed_independently_across_pools() -> None:
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

    with pytest.raises(PoolWorkflowBindingStoreError) as first_exc:
        list_pool_workflow_binding_attachments(pool=first_pool)
    with pytest.raises(PoolWorkflowBindingStoreError) as second_exc:
        list_pool_workflow_binding_attachments(pool=second_pool)

    assert str(first_exc.value) == (
        f"POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING: Workflow binding '{first_binding['binding_id']}' "
        "is missing binding_profile references."
    )
    assert str(second_exc.value) == (
        f"POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING: Workflow binding '{second_binding['binding_id']}' "
        "is missing binding_profile references."
    )

    first_record = PoolWorkflowBinding.objects.get(binding_id=first_binding["binding_id"])
    second_record = PoolWorkflowBinding.objects.get(binding_id=second_binding["binding_id"])
    assert first_record.binding_profile_id is None
    assert first_record.binding_profile_revision_id is None
    assert second_record.binding_profile_id is None
    assert second_record.binding_profile_revision_id is None


@pytest.mark.django_db
def test_template_pool_attachment_rejects_execution_pack_with_concrete_participant_refs() -> None:
    tenant = Tenant.objects.create(slug=f"binding-attachment-template-{uuid4().hex[:8]}", name="Binding Attachment")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Template Attachment Pool",
        metadata={
            POOL_TOPOLOGY_TEMPLATE_INSTANTIATION_METADATA_KEY: {
                "topology_template_revision_id": "template-r1",
            }
        },
    )
    profile = create_canonical_binding_profile(
        tenant=tenant,
        binding_profile={
            "code": "services-publication-default",
            "name": "Services Publication",
            "revision": _build_profile_revision_payload(),
        },
        actor_username="architect",
    )
    revision_id = profile["latest_revision"]["binding_profile_revision_id"]
    incompatible_decision_table_id, incompatible_decision_revision = _create_document_policy_decision(
        token="master_data.party.party_001.counterparty.ref",
    )
    profile_revision = BindingProfileRevision.objects.get(binding_profile_revision_id=revision_id)
    profile_revision.decisions = [
        {
            "decision_table_id": incompatible_decision_table_id,
            "decision_key": "document_policy",
            "slot_key": "document_policy",
            "decision_revision": incompatible_decision_revision,
        }
    ]
    profile_revision.metadata = {"source": "manual"}
    profile_revision.save(update_fields=["decisions", "metadata"])

    with pytest.raises(PoolWorkflowBindingTemplateCompatibilityError) as exc_info:
        upsert_pool_workflow_binding_attachment(
            pool=pool,
            workflow_binding={
                "binding_profile_revision_id": revision_id,
                "selector": {"direction": "top_down", "mode": "safe", "tags": ["baseline"]},
                "effective_from": "2026-01-01",
                "status": "active",
            },
            actor_username="operator",
        )

    assert exc_info.value.code == "EXECUTION_PACK_TEMPLATE_INCOMPATIBLE"
    assert "/pools/execution-packs" in exc_info.value.detail
    assert exc_info.value.errors[0]["slot_key"] == "document_policy"


@pytest.mark.django_db
def test_template_pool_binding_collection_surfaces_blocking_remediation_for_incompatible_attachment() -> None:
    tenant = Tenant.objects.create(slug=f"binding-attachment-summary-{uuid4().hex[:8]}", name="Binding Attachment")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Template Attachment Pool",
        metadata={
            POOL_TOPOLOGY_TEMPLATE_INSTANTIATION_METADATA_KEY: {
                "topology_template_revision_id": "template-r1",
            }
        },
    )
    compatible_profile = create_canonical_binding_profile(
        tenant=tenant,
        binding_profile={
            "code": "services-publication-default",
            "name": "Services Publication",
            "revision": _build_profile_revision_payload(),
        },
        actor_username="architect",
    )
    binding, _ = upsert_pool_workflow_binding_attachment(
        pool=pool,
        workflow_binding={
            "binding_profile_revision_id": compatible_profile["latest_revision"]["binding_profile_revision_id"],
            "selector": {"direction": "top_down", "mode": "safe", "tags": ["baseline"]},
            "effective_from": "2026-01-01",
            "status": "active",
        },
        actor_username="operator",
    )
    record = PoolWorkflowBinding.objects.get(binding_id=binding["binding_id"])
    incompatible_decision_table_id, incompatible_decision_revision = _create_document_policy_decision(
        token="master_data.party.party_001.counterparty.ref",
    )
    incompatible_revision = BindingProfileRevision.objects.get(
        binding_profile_revision_id=compatible_profile["latest_revision"]["binding_profile_revision_id"]
    )
    incompatible_revision.decisions = [
        {
            "decision_table_id": incompatible_decision_table_id,
            "decision_key": "document_policy",
            "slot_key": "document_policy",
            "decision_revision": incompatible_decision_revision,
        }
    ]
    incompatible_revision.metadata = {"source": "manual"}
    incompatible_revision.save(update_fields=["decisions", "metadata"])
    record.binding_profile = incompatible_revision.profile
    record.binding_profile_revision = incompatible_revision
    record.workflow_definition_key = incompatible_revision.workflow_definition_key
    record.workflow_revision_id = incompatible_revision.workflow_revision_id
    record.workflow_revision = incompatible_revision.workflow_revision
    record.workflow_name = incompatible_revision.workflow_name
    record.decisions = list(incompatible_revision.decisions)
    record.parameters = dict(incompatible_revision.parameters)
    record.role_mapping = dict(incompatible_revision.role_mapping)
    record.save()

    collection = get_pool_workflow_binding_attachments_collection(pool=pool)

    assert collection["blocking_remediation"]["code"] == "EXECUTION_PACK_TEMPLATE_INCOMPATIBLE"
    assert "/decisions" in collection["blocking_remediation"]["detail"]
    resolved_profile = collection["workflow_bindings"][0]["resolved_profile"]
    assert resolved_profile["topology_template_compatibility"]["status"] == "incompatible"
    assert resolved_profile["topology_template_compatibility"]["diagnostics"][0]["slot_key"] == "document_policy"
