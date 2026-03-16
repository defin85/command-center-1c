from __future__ import annotations

from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError

from apps.intercompany_pools.models import OrganizationPool, PoolWorkflowBinding
from apps.intercompany_pools.workflow_bindings_store import (
    PoolWorkflowBindingCollectionConflictError,
    PoolWorkflowBindingNotFoundError,
    PoolWorkflowBindingRevisionConflictError,
    PoolWorkflowBindingStoreError,
    delete_canonical_pool_workflow_binding,
    get_canonical_pool_workflow_binding_collection,
    get_canonical_pool_workflow_binding,
    list_canonical_pool_workflow_bindings,
    replace_canonical_pool_workflow_bindings_collection,
    upsert_canonical_pool_workflow_binding,
)
from apps.tenancy.models import Tenant


def _build_binding_payload(*, pool: OrganizationPool) -> dict[str, object]:
    return {
        "binding_id": str(uuid4()),
        "pool_id": str(pool.id),
        "workflow": {
            "workflow_definition_key": "services-publication",
            "workflow_revision_id": str(uuid4()),
            "workflow_revision": 3,
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
def test_upsert_canonical_pool_workflow_binding_persists_required_fields() -> None:
    tenant = Tenant.objects.create(slug=f"binding-store-{uuid4().hex[:8]}", name="Binding Store")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Binding Pool",
    )

    saved_binding, created = upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=_build_binding_payload(pool=pool),
        actor_username="architect",
    )

    assert created is True
    record = PoolWorkflowBinding.objects.get(binding_id=saved_binding["binding_id"])
    assert record.tenant_id == tenant.id
    assert record.pool_id == pool.id
    assert record.direction == "top_down"
    assert record.mode == "safe"
    assert record.selector_tags == ["baseline"]
    assert record.workflow_definition_key == "services-publication"
    assert record.workflow_revision == 3
    assert record.decisions == saved_binding["decisions"]
    assert record.parameters == {"publication_variant": "full"}
    assert record.role_mapping == {"initiator": "finance"}
    assert record.revision == 1
    assert record.created_by == "architect"
    assert record.updated_by == "architect"
    assert saved_binding["revision"] == 1

    listed = list_canonical_pool_workflow_bindings(pool=pool)
    assert listed == [saved_binding]
    resolved = get_canonical_pool_workflow_binding(pool=pool, binding_id=saved_binding["binding_id"])
    assert resolved == saved_binding


@pytest.mark.django_db
def test_get_canonical_pool_workflow_binding_collection_returns_etag_and_blocking_remediation() -> None:
    tenant = Tenant.objects.create(slug=f"binding-store-collection-{uuid4().hex[:8]}", name="Collection Tenant")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Collection Pool",
        metadata={
            "workflow_bindings": [
                {
                    "binding_id": "legacy-binding",
                    "workflow": {
                        "workflow_definition_key": "legacy-publication",
                        "workflow_revision_id": str(uuid4()),
                        "workflow_revision": 1,
                        "workflow_name": "legacy_publication",
                    },
                    "effective_from": "2026-01-01",
                    "status": "active",
                }
            ]
        },
    )

    collection = get_canonical_pool_workflow_binding_collection(pool=pool)

    assert collection["pool_id"] == str(pool.id)
    assert collection["workflow_bindings"] == []
    assert isinstance(collection["collection_etag"], str)
    assert collection["collection_etag"]
    assert collection["blocking_remediation"] == {
        "code": "LEGACY_METADATA_WORKFLOW_BINDINGS_PRESENT",
        "title": "Legacy workflow bindings remediation required",
        "detail": (
            "Canonical binding collection is empty while legacy pool.metadata.workflow_bindings "
            "payload is still present. Run explicit remediation before using the default workspace."
        ),
    }


@pytest.mark.django_db
def test_get_canonical_pool_workflow_binding_raises_for_missing_record() -> None:
    tenant = Tenant.objects.create(slug=f"binding-store-missing-{uuid4().hex[:8]}", name="Missing Binding")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Missing Binding Pool",
    )

    with pytest.raises(PoolWorkflowBindingNotFoundError):
        get_canonical_pool_workflow_binding(pool=pool, binding_id="missing-binding")


@pytest.mark.django_db
def test_upsert_canonical_pool_workflow_binding_requires_matching_revision_for_update() -> None:
    tenant = Tenant.objects.create(slug=f"binding-store-revision-{uuid4().hex[:8]}", name="Revision Tenant")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Revision Pool",
    )
    created_binding, _ = upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=_build_binding_payload(pool=pool),
        actor_username="creator",
    )

    updated_binding, created = upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding={
            **created_binding,
            "revision": created_binding["revision"],
            "status": "inactive",
        },
        actor_username="editor",
    )

    assert created is False
    assert updated_binding["revision"] == 2
    assert updated_binding["status"] == "inactive"
    record = PoolWorkflowBinding.objects.get(binding_id=created_binding["binding_id"])
    assert record.revision == 2
    assert record.updated_by == "editor"


@pytest.mark.django_db
def test_upsert_canonical_pool_workflow_binding_allows_reusing_document_policy_across_slots() -> None:
    tenant = Tenant.objects.create(slug=f"binding-store-shared-policy-{uuid4().hex[:8]}", name="Shared Policy Tenant")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Shared Policy Pool",
    )

    saved_binding, created = upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding={
            **_build_binding_payload(pool=pool),
            "decisions": [
                {
                    "decision_table_id": "document-policy-shared",
                    "decision_key": "document_policy",
                    "slot_key": "sale",
                    "decision_revision": 2,
                },
                {
                    "decision_table_id": "document-policy-shared",
                    "decision_key": "document_policy",
                    "slot_key": "purchase",
                    "decision_revision": 2,
                },
            ],
        },
        actor_username="creator",
    )

    assert created is True
    assert [decision["slot_key"] for decision in saved_binding["decisions"]] == ["sale", "purchase"]


@pytest.mark.django_db
def test_upsert_canonical_pool_workflow_binding_rejects_duplicate_slot_key() -> None:
    tenant = Tenant.objects.create(slug=f"binding-store-duplicate-slot-{uuid4().hex[:8]}", name="Duplicate Slot Tenant")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Duplicate Slot Pool",
    )

    with pytest.raises(PoolWorkflowBindingStoreError, match="POOL_DOCUMENT_POLICY_SLOT_DUPLICATE"):
        upsert_canonical_pool_workflow_binding(
            pool=pool,
            workflow_binding={
                **_build_binding_payload(pool=pool),
                "decisions": [
                    {
                        "decision_table_id": "document-policy-a",
                        "decision_key": "document_policy",
                        "slot_key": "shared_slot",
                        "decision_revision": 2,
                    },
                    {
                        "decision_table_id": "document-policy-b",
                        "decision_key": "document_policy",
                        "slot_key": "shared_slot",
                        "decision_revision": 3,
                    },
                ],
            },
            actor_username="creator",
        )

    assert list_canonical_pool_workflow_bindings(pool=pool) == []


@pytest.mark.django_db
def test_upsert_canonical_pool_workflow_binding_raises_conflict_for_stale_revision() -> None:
    tenant = Tenant.objects.create(slug=f"binding-store-conflict-{uuid4().hex[:8]}", name="Conflict Tenant")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Conflict Pool",
    )
    created_binding, _ = upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=_build_binding_payload(pool=pool),
        actor_username="creator",
    )
    upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding={
            **created_binding,
            "revision": created_binding["revision"],
            "status": "inactive",
        },
        actor_username="editor",
    )

    with pytest.raises(PoolWorkflowBindingRevisionConflictError) as exc_info:
        upsert_canonical_pool_workflow_binding(
            pool=pool,
            workflow_binding={
                **created_binding,
                "revision": created_binding["revision"],
                "status": "draft",
            },
            actor_username="stale-editor",
        )

    assert exc_info.value.binding_id == created_binding["binding_id"]
    assert exc_info.value.expected_revision == 1
    assert exc_info.value.actual_revision == 2


@pytest.mark.django_db
def test_replace_canonical_pool_workflow_bindings_collection_applies_atomic_diff() -> None:
    tenant = Tenant.objects.create(slug=f"binding-store-replace-{uuid4().hex[:8]}", name="Replace Tenant")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Replace Pool",
    )
    first_binding, _ = upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=_build_binding_payload(pool=pool),
        actor_username="creator",
    )
    second_binding, _ = upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding={
            **_build_binding_payload(pool=pool),
            "binding_id": str(uuid4()),
            "workflow": {
                "workflow_definition_key": "bottom-up-import",
                "workflow_revision_id": str(uuid4()),
                "workflow_revision": 5,
                "workflow_name": "bottom_up_import",
            },
            "selector": {
                "direction": "bottom_up",
                "mode": "safe",
                "tags": ["monthly"],
            },
        },
        actor_username="creator",
    )
    initial_collection = get_canonical_pool_workflow_binding_collection(pool=pool)

    replaced_collection = replace_canonical_pool_workflow_bindings_collection(
        pool=pool,
        expected_collection_etag=initial_collection["collection_etag"],
        workflow_bindings=[
            {
                **first_binding,
                "workflow": {
                    **first_binding["workflow"],
                    "workflow_revision": 4,
                },
                "status": "inactive",
            },
            {
                **_build_binding_payload(pool=pool),
                "binding_id": str(uuid4()),
                "workflow": {
                    "workflow_definition_key": "services-publication-v2",
                    "workflow_revision_id": str(uuid4()),
                    "workflow_revision": 7,
                    "workflow_name": "services_publication_v2",
                },
                "selector": {
                    "direction": "top_down",
                    "mode": "unsafe",
                    "tags": ["cutover"],
                },
            },
        ],
        actor_username="editor",
    )

    assert replaced_collection["pool_id"] == str(pool.id)
    assert replaced_collection["collection_etag"] != initial_collection["collection_etag"]
    assert [item["binding_id"] for item in replaced_collection["workflow_bindings"]] == [
        first_binding["binding_id"],
        replaced_collection["workflow_bindings"][1]["binding_id"],
    ]
    assert replaced_collection["workflow_bindings"][0]["revision"] == 2
    assert replaced_collection["workflow_bindings"][0]["workflow"]["workflow_revision"] == 4
    assert replaced_collection["workflow_bindings"][0]["status"] == "inactive"
    assert replaced_collection["workflow_bindings"][1]["revision"] == 1
    assert {
        item["binding_id"] for item in list_canonical_pool_workflow_bindings(pool=pool)
    } == {
        first_binding["binding_id"],
        replaced_collection["workflow_bindings"][1]["binding_id"],
    }
    assert second_binding["binding_id"] not in {
        item["binding_id"] for item in list_canonical_pool_workflow_bindings(pool=pool)
    }


@pytest.mark.django_db
def test_replace_canonical_pool_workflow_bindings_collection_rejects_stale_etag_without_partial_apply() -> None:
    tenant = Tenant.objects.create(slug=f"binding-store-stale-{uuid4().hex[:8]}", name="Stale Tenant")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Stale Pool",
    )
    created_binding, _ = upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=_build_binding_payload(pool=pool),
        actor_username="creator",
    )
    stale_collection = get_canonical_pool_workflow_binding_collection(pool=pool)
    winner_collection = replace_canonical_pool_workflow_bindings_collection(
        pool=pool,
        expected_collection_etag=stale_collection["collection_etag"],
        workflow_bindings=[
            {
                **created_binding,
                "status": "inactive",
            }
        ],
        actor_username="winner",
    )

    with pytest.raises(PoolWorkflowBindingCollectionConflictError) as exc_info:
        replace_canonical_pool_workflow_bindings_collection(
            pool=pool,
            expected_collection_etag=stale_collection["collection_etag"],
            workflow_bindings=[
                {
                    **created_binding,
                    "status": "draft",
                },
                {
                    **_build_binding_payload(pool=pool),
                    "binding_id": str(uuid4()),
                    "workflow": {
                        "workflow_definition_key": "late-binding",
                        "workflow_revision_id": str(uuid4()),
                        "workflow_revision": 8,
                        "workflow_name": "late_binding",
                    },
                },
            ],
            actor_username="stale-editor",
        )

    assert exc_info.value.expected_collection_etag == stale_collection["collection_etag"]
    assert exc_info.value.actual_collection_etag == winner_collection["collection_etag"]
    assert get_canonical_pool_workflow_binding_collection(pool=pool) == winner_collection


@pytest.mark.django_db
def test_replace_canonical_pool_workflow_bindings_collection_rolls_back_on_validation_error() -> None:
    tenant = Tenant.objects.create(slug=f"binding-store-rollback-{uuid4().hex[:8]}", name="Rollback Tenant")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Rollback Pool",
    )
    created_binding, _ = upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=_build_binding_payload(pool=pool),
        actor_username="creator",
    )
    initial_collection = get_canonical_pool_workflow_binding_collection(pool=pool)

    with pytest.raises(PoolWorkflowBindingStoreError):
        replace_canonical_pool_workflow_bindings_collection(
            pool=pool,
            expected_collection_etag=initial_collection["collection_etag"],
            workflow_bindings=[
                {
                    **created_binding,
                    "status": "inactive",
                },
                {
                    **_build_binding_payload(pool=pool),
                    "binding_id": str(uuid4()),
                    "effective_to": "2025-01-01",
                },
            ],
            actor_username="editor",
        )

    assert get_canonical_pool_workflow_binding_collection(pool=pool) == initial_collection


@pytest.mark.django_db
def test_delete_canonical_pool_workflow_binding_requires_matching_revision() -> None:
    tenant = Tenant.objects.create(slug=f"binding-store-delete-{uuid4().hex[:8]}", name="Delete Tenant")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Delete Pool",
    )
    created_binding, _ = upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=_build_binding_payload(pool=pool),
        actor_username="creator",
    )

    with pytest.raises(PoolWorkflowBindingStoreError, match="revision is required"):
        delete_canonical_pool_workflow_binding(pool=pool, binding_id=created_binding["binding_id"])

    with pytest.raises(PoolWorkflowBindingRevisionConflictError) as exc_info:
        delete_canonical_pool_workflow_binding(
            pool=pool,
            binding_id=created_binding["binding_id"],
            revision=created_binding["revision"] + 1,
        )

    assert exc_info.value.expected_revision == 2
    assert exc_info.value.actual_revision == 1

    deleted_binding = delete_canonical_pool_workflow_binding(
        pool=pool,
        binding_id=created_binding["binding_id"],
        revision=created_binding["revision"],
    )

    assert deleted_binding["binding_id"] == created_binding["binding_id"]
    assert deleted_binding["revision"] == 1
    assert list_canonical_pool_workflow_bindings(pool=pool) == []


@pytest.mark.django_db
def test_pool_workflow_binding_model_rejects_cross_tenant_pool() -> None:
    pool_tenant = Tenant.objects.create(slug=f"binding-pool-{uuid4().hex[:8]}", name="Pool Tenant")
    foreign_tenant = Tenant.objects.create(slug=f"binding-foreign-{uuid4().hex[:8]}", name="Foreign Tenant")
    pool = OrganizationPool.objects.create(
        tenant=pool_tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Cross Tenant Pool",
    )

    record = PoolWorkflowBinding(
        binding_id=str(uuid4()),
        tenant=foreign_tenant,
        pool=pool,
        status="active",
        effective_from="2026-01-01",
        direction="top_down",
        mode="safe",
        workflow_definition_key="services-publication",
        workflow_revision_id=str(uuid4()),
        workflow_revision=1,
        workflow_name="services_publication",
    )

    with pytest.raises(ValidationError, match="same tenant"):
        record.full_clean()


@pytest.mark.django_db
def test_pool_workflow_binding_model_rejects_invalid_effective_range() -> None:
    tenant = Tenant.objects.create(slug=f"binding-range-{uuid4().hex[:8]}", name="Range Tenant")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Range Pool",
    )

    record = PoolWorkflowBinding(
        binding_id=str(uuid4()),
        tenant=tenant,
        pool=pool,
        status="active",
        effective_from="2026-02-01",
        effective_to="2026-01-01",
        direction="top_down",
        mode="safe",
        workflow_definition_key="services-publication",
        workflow_revision_id=str(uuid4()),
        workflow_revision=1,
        workflow_name="services_publication",
    )

    with pytest.raises(ValidationError):
        record.full_clean()
