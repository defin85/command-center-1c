from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model

from apps.databases.models import Database
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolBatch,
    PoolBatchKind,
    PoolBatchSourceType,
    PoolEdgeVersion,
    PoolFactualReviewItem,
    PoolFactualReviewReason,
    PoolFactualReviewStatus,
    PoolNodeVersion,
)
from apps.tenancy.models import Tenant


User = get_user_model()


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"factual-review-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/factual-review-{suffix}.odata",
        username="admin",
        password="secret",
    )


def _create_pool_scope(*, tenant: Tenant, suffix: str) -> tuple[OrganizationPool, Organization, Organization]:
    database = _create_database(tenant=tenant, suffix=suffix)
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"factual-review-pool-{suffix}",
        name=f"Factual Review Pool {suffix}",
    )
    root = Organization.objects.create(
        tenant=tenant,
        database=database,
        name=f"Root {suffix}",
        inn=f"77000000{suffix[:4].zfill(4)}",
    )
    leaf = Organization.objects.create(
        tenant=tenant,
        name=f"Leaf {suffix}",
        inn=f"78000000{suffix[:4].zfill(4)}",
    )
    return pool, root, leaf


def _create_edge(*, pool: OrganizationPool, root: Organization, leaf: Organization) -> PoolEdgeVersion:
    root_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=root,
        effective_from=date(2026, 1, 1),
        is_root=True,
    )
    leaf_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=leaf,
        effective_from=date(2026, 1, 1),
        is_root=False,
    )
    return PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=leaf_node,
        effective_from=date(2026, 1, 1),
        weight="1.0",
    )


@pytest.mark.django_db
def test_apply_pool_factual_review_action_attributes_unattributed_item_with_explicit_target() -> None:
    from apps.intercompany_pools.factual_review_queue import (
        FACTUAL_REVIEW_ACTION_ATTRIBUTE,
        apply_pool_factual_review_action,
    )

    tenant = Tenant.objects.create(slug=f"factual-review-attr-{uuid4().hex[:6]}", name="Factual Review Attr")
    pool, root, leaf = _create_pool_scope(tenant=tenant, suffix="001")
    edge = _create_edge(pool=pool, root=root, leaf=leaf)
    batch = PoolBatch.objects.create(
        tenant=tenant,
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        start_organization=root,
        source_reference="receipt-001",
        raw_payload_ref="files/receipt-001.xlsx",
    )
    actor = User.objects.create_user(username=f"factual-review-attr-{uuid4().hex[:6]}", password="pass")
    review_item = PoolFactualReviewItem.objects.create(
        tenant=tenant,
        pool=pool,
        organization=leaf,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.UNATTRIBUTED,
        source_document_ref="Document_РеализацияТоваровУслуг(guid'11111111-1111-1111-1111-111111111111')",
    )

    with pytest.raises(ValueError, match="requires at least one attribution target"):
        apply_pool_factual_review_action(
            review_item_id=str(review_item.id),
            tenant_id=str(tenant.id),
            actor_id=str(actor.id),
            action=FACTUAL_REVIEW_ACTION_ATTRIBUTE,
        )

    updated = apply_pool_factual_review_action(
        review_item_id=str(review_item.id),
        tenant_id=str(tenant.id),
        actor_id=str(actor.id),
        action=FACTUAL_REVIEW_ACTION_ATTRIBUTE,
        batch_id=str(batch.id),
        edge_id=str(edge.id),
        organization_id=str(leaf.id),
        note="manual attribution from factual workspace",
        metadata={"source": "ui"},
    )

    updated.refresh_from_db()
    assert updated.status == PoolFactualReviewStatus.ATTRIBUTED
    assert updated.batch_id == batch.id
    assert updated.edge_id == edge.id
    assert updated.organization_id == leaf.id
    assert updated.resolved_by_id == actor.id
    assert updated.resolved_at is not None
    assert updated.metadata["operator_actions"][-1]["action"] == FACTUAL_REVIEW_ACTION_ATTRIBUTE
    assert updated.metadata["operator_actions"][-1]["note"] == "manual attribution from factual workspace"
    assert updated.metadata["operator_actions"][-1]["metadata"]["source"] == "ui"


@pytest.mark.django_db
def test_apply_pool_factual_review_action_rejects_attribute_for_late_correction_and_reconciles() -> None:
    from apps.intercompany_pools.factual_review_queue import (
        FACTUAL_REVIEW_ACTION_ATTRIBUTE,
        FACTUAL_REVIEW_ACTION_RECONCILE,
        apply_pool_factual_review_action,
    )

    tenant = Tenant.objects.create(
        slug=f"factual-review-reconcile-{uuid4().hex[:6]}",
        name="Factual Review Reconcile",
    )
    pool, _, leaf = _create_pool_scope(tenant=tenant, suffix="002")
    actor = User.objects.create_user(username=f"factual-review-reconcile-{uuid4().hex[:6]}", password="pass")
    review_item = PoolFactualReviewItem.objects.create(
        tenant=tenant,
        pool=pool,
        organization=leaf,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.LATE_CORRECTION,
        source_document_ref="Document_КорректировкаРеализации(guid'22222222-2222-2222-2222-222222222222')",
        metadata={"delta_payload": {"amount_with_vat": "15.00"}},
    )

    with pytest.raises(ValueError, match="is not allowed for reason 'late_correction'"):
        apply_pool_factual_review_action(
            review_item_id=str(review_item.id),
            tenant_id=str(tenant.id),
            actor_id=str(actor.id),
            action=FACTUAL_REVIEW_ACTION_ATTRIBUTE,
        )

    updated = apply_pool_factual_review_action(
        review_item_id=str(review_item.id),
        tenant_id=str(tenant.id),
        actor_id=str(actor.id),
        action=FACTUAL_REVIEW_ACTION_RECONCILE,
        note="late correction acknowledged",
        metadata={"resolution_code": "MANUAL_RECONCILE"},
    )

    updated.refresh_from_db()
    assert updated.status == PoolFactualReviewStatus.RECONCILED
    assert updated.resolved_by_id == actor.id
    assert updated.metadata["operator_actions"][-1]["action"] == FACTUAL_REVIEW_ACTION_RECONCILE
    assert updated.metadata["operator_actions"][-1]["metadata"]["resolution_code"] == "MANUAL_RECONCILE"


@pytest.mark.django_db
def test_apply_pool_factual_review_action_resolves_without_change_without_rewriting_targets() -> None:
    from apps.intercompany_pools.factual_review_queue import (
        FACTUAL_REVIEW_ACTION_RESOLVE_WITHOUT_CHANGE,
        apply_pool_factual_review_action,
    )

    tenant = Tenant.objects.create(
        slug=f"factual-review-resolve-{uuid4().hex[:6]}",
        name="Factual Review Resolve",
    )
    pool, _, leaf = _create_pool_scope(tenant=tenant, suffix="004")
    actor = User.objects.create_user(username=f"factual-review-resolve-{uuid4().hex[:6]}", password="pass")
    review_item = PoolFactualReviewItem.objects.create(
        tenant=tenant,
        pool=pool,
        organization=leaf,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.UNATTRIBUTED,
        source_document_ref="Document_РеализацияТоваровУслуг(guid'55555555-5555-5555-5555-555555555555')",
        metadata={"raw_organization_id": str(leaf.id)},
    )

    updated = apply_pool_factual_review_action(
        review_item_id=str(review_item.id),
        tenant_id=str(tenant.id),
        actor_id=str(actor.id),
        action=FACTUAL_REVIEW_ACTION_RESOLVE_WITHOUT_CHANGE,
        note="accepted as external-only correction",
        metadata={"resolution_code": "NO_ATTRIBUTION_REQUIRED"},
    )

    updated.refresh_from_db()
    assert updated.status == PoolFactualReviewStatus.RESOLVED_WITHOUT_CHANGE
    assert updated.batch_id is None
    assert updated.edge_id is None
    assert updated.organization_id == leaf.id
    assert updated.resolved_by_id == actor.id
    assert updated.metadata["operator_actions"][-1]["action"] == FACTUAL_REVIEW_ACTION_RESOLVE_WITHOUT_CHANGE
    assert updated.metadata["operator_actions"][-1]["note"] == "accepted as external-only correction"
    assert (
        updated.metadata["operator_actions"][-1]["metadata"]["resolution_code"]
        == "NO_ATTRIBUTION_REQUIRED"
    )


@pytest.mark.django_db
def test_build_pool_factual_review_queue_snapshot_exposes_reason_specific_actions_and_summary() -> None:
    from apps.intercompany_pools.factual_review_queue import (
        FACTUAL_REVIEW_ACTION_ATTRIBUTE,
        FACTUAL_REVIEW_ACTION_RECONCILE,
        FACTUAL_REVIEW_ACTION_RESOLVE_WITHOUT_CHANGE,
        build_pool_factual_review_queue_snapshot,
    )

    tenant = Tenant.objects.create(slug=f"factual-review-snapshot-{uuid4().hex[:6]}", name="Factual Review Snapshot")
    pool, _, leaf = _create_pool_scope(tenant=tenant, suffix="003")
    unattributed = PoolFactualReviewItem.objects.create(
        tenant=tenant,
        pool=pool,
        organization=leaf,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.UNATTRIBUTED,
        source_document_ref="Document_РеализацияТоваровУслуг(guid'33333333-3333-3333-3333-333333333333')",
    )
    late_correction = PoolFactualReviewItem.objects.create(
        tenant=tenant,
        pool=pool,
        organization=leaf,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.LATE_CORRECTION,
        source_document_ref="Document_КорректировкаРеализации(guid'44444444-4444-4444-4444-444444444444')",
    )

    snapshot = build_pool_factual_review_queue_snapshot(
        review_items=PoolFactualReviewItem.objects.filter(pool=pool),
    )

    assert snapshot["contract_version"] == "pool_factual_review_queue.v1"
    assert snapshot["subsystem"] == "reconcile_review"
    assert snapshot["summary"] == {
        "pending_total": 2,
        "unattributed_total": 1,
        "late_correction_total": 1,
        "attention_required_total": 1,
    }
    items_by_id = {item["id"]: item for item in snapshot["items"]}
    assert items_by_id[str(unattributed.id)]["allowed_actions"] == [
        FACTUAL_REVIEW_ACTION_ATTRIBUTE,
        FACTUAL_REVIEW_ACTION_RESOLVE_WITHOUT_CHANGE,
    ]
    assert items_by_id[str(late_correction.id)]["allowed_actions"] == [
        FACTUAL_REVIEW_ACTION_RECONCILE,
        FACTUAL_REVIEW_ACTION_RESOLVE_WITHOUT_CHANGE,
    ]
    assert items_by_id[str(late_correction.id)]["attention_required"] is True
