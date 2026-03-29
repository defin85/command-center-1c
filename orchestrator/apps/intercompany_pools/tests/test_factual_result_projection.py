from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model

from apps.databases.models import Database
from apps.intercompany_pools.factual_review_queue import (
    FACTUAL_REVIEW_ACTION_ATTRIBUTE,
    FACTUAL_REVIEW_ACTION_RECONCILE,
    apply_pool_factual_review_action,
)
from apps.intercompany_pools.factual_workflow_contract import build_pool_factual_sync_workflow_input_context
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolBatch,
    PoolBatchKind,
    PoolBatchSettlement,
    PoolBatchSettlementStatus,
    PoolBatchSourceType,
    PoolEdgeVersion,
    PoolFactualBalanceSnapshot,
    PoolFactualLane,
    PoolFactualReviewItem,
    PoolFactualReviewReason,
    PoolFactualReviewStatus,
    PoolFactualSyncCheckpoint,
    PoolNodeVersion,
)
from apps.tenancy.models import Tenant


User = get_user_model()


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"factual-result-db-{suffix}-{uuid4().hex[:6]}",
        host="localhost",
        odata_url=f"http://localhost/odata/factual-result-{suffix}.odata",
        username="admin",
        password="secret",
    )


def _create_pool_scope(*, tenant: Tenant, suffix: str) -> tuple[OrganizationPool, Organization, Organization, Database]:
    database = _create_database(tenant=tenant, suffix=suffix)
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"factual-result-pool-{suffix}-{uuid4().hex[:6]}",
        name=f"Factual Result Pool {suffix}",
    )
    root = Organization.objects.create(
        tenant=tenant,
        database=database,
        name=f"Root {suffix}",
        inn=f"77030000{suffix[:4].zfill(4)}",
    )
    leaf = Organization.objects.create(
        tenant=tenant,
        name=f"Leaf {suffix}",
        inn=f"78030000{suffix[:4].zfill(4)}",
    )
    return pool, root, leaf, database


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


def _create_batch(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    root: Organization,
    suffix: str,
) -> PoolBatch:
    return PoolBatch.objects.create(
        tenant=tenant,
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        start_organization=root,
        source_reference=f"receipt-{suffix}",
    )


def _build_execution(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    database: Database,
    checkpoint: PoolFactualSyncCheckpoint,
    organization_id: str,
    lane: str,
    payload: dict[str, object],
):
    input_context = build_pool_factual_sync_workflow_input_context(
        checkpoint_id=str(checkpoint.id),
        tenant_id=str(tenant.id),
        pool_id=str(pool.id),
        database=database,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        organization_ids=[organization_id],
        account_codes=["62.01"],
        movement_kinds=["credit"],
        lane=lane,
        correlation_id=f"corr-{uuid4().hex[:6]}",
        origin_system="tests",
        origin_event_id=f"event-{uuid4().hex[:6]}",
    )
    return SimpleNamespace(
        status="completed",
        input_context=input_context,
        final_result=payload,
        id=uuid4(),
        error_code="",
        error_message="",
    )


@pytest.mark.django_db
def test_project_pool_factual_result_from_execution_applies_leaf_sale_attribution_to_edge_less_sales() -> None:
    from apps.intercompany_pools.factual_result_projection import project_pool_factual_result_from_execution

    tenant = Tenant.objects.create(slug=f"factual-result-sale-{uuid4().hex[:6]}", name="Factual Result Sale")
    pool, root, leaf, database = _create_pool_scope(tenant=tenant, suffix="001")
    edge = _create_edge(pool=pool, root=root, leaf=leaf)
    batch = _create_batch(tenant=tenant, pool=pool, root=root, suffix="sale-001")
    checkpoint = PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
    )
    payload = {
        "node_results": {
            "factual_sync_source_slice": {
                "step": "factual_sync_source_slice",
                "pool_id": str(pool.id),
                "database_id": str(database.id),
                "lane": "read",
                "quarter_start": "2026-01-01",
                "quarter_end": "2026-03-31",
                "boundary_reads": {
                    "accounting_register": 1,
                    "information_register": 1,
                    "Document_РеализацияТоваровУслуг": 2,
                },
                "source_checkpoint_token": "cp-sale-001",
                "factual_documents": [
                    {
                        "source_document_ref": "Document_ПоступлениеТоваровУслуг(guid'receipt-1')",
                        "organization_id": str(leaf.id),
                        "batch_id": str(batch.id),
                        "edge_id": str(edge.id),
                        "amount_with_vat": "45.00",
                        "amount_without_vat": "37.50",
                        "vat_amount": "7.50",
                        "comment": (
                            f"CCPOOL:v=1;pool={pool.id};run=-;batch={batch.id};org={leaf.id};q=2026Q1;kind=receipt"
                        ),
                        "kind": "receipt",
                        "modified_at": "2026-03-26T09:00:00Z",
                    },
                    {
                        "source_document_ref": "Document_РеализацияТоваровУслуг(guid'sale-1')",
                        "organization_id": str(leaf.id),
                        "batch_id": str(batch.id),
                        "edge_id": None,
                        "amount_with_vat": "30.00",
                        "amount_without_vat": "25.00",
                        "vat_amount": "5.00",
                        "comment": (
                            f"CCPOOL:v=1;pool={pool.id};run=-;batch={batch.id};org={leaf.id};q=2026Q1;kind=sale"
                        ),
                        "kind": "sale",
                        "modified_at": "2026-03-27T10:00:00Z",
                    },
                ],
            }
        }
    }
    execution = _build_execution(
        tenant=tenant,
        pool=pool,
        database=database,
        checkpoint=checkpoint,
        organization_id=str(leaf.id),
        lane=PoolFactualLane.READ,
        payload=payload,
    )

    assert project_pool_factual_result_from_execution(execution=execution, result_payload=payload) is True

    snapshot = PoolFactualBalanceSnapshot.objects.get(
        tenant=tenant,
        pool=pool,
        batch=batch,
        organization=leaf,
        edge=edge,
    )
    assert snapshot.amount_with_vat == Decimal("15.00")
    assert snapshot.amount_without_vat == Decimal("12.50")
    assert snapshot.vat_amount == Decimal("2.50")
    assert snapshot.incoming_amount == Decimal("45.00")
    assert snapshot.outgoing_amount == Decimal("30.00")
    assert snapshot.open_balance == Decimal("15.00")
    assert not PoolFactualBalanceSnapshot.objects.filter(
        tenant=tenant,
        pool=pool,
        organization=leaf,
        edge__isnull=True,
    ).exists()
    assert not PoolFactualReviewItem.objects.filter(
        tenant=tenant,
        pool=pool,
        reason=PoolFactualReviewReason.UNATTRIBUTED,
        status=PoolFactualReviewStatus.PENDING,
    ).exists()


@pytest.mark.django_db
def test_project_pool_factual_result_from_execution_reuses_resolved_unattributed_review_targets() -> None:
    from apps.intercompany_pools.factual_result_projection import project_pool_factual_result_from_execution

    tenant = Tenant.objects.create(slug=f"factual-result-resolution-{uuid4().hex[:6]}", name="Factual Result Resolution")
    pool, root, leaf, database = _create_pool_scope(tenant=tenant, suffix="002")
    edge = _create_edge(pool=pool, root=root, leaf=leaf)
    batch = _create_batch(tenant=tenant, pool=pool, root=root, suffix="resolution-001")
    checkpoint = PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
    )
    review_item = PoolFactualReviewItem.objects.create(
        tenant=tenant,
        pool=pool,
        batch=batch,
        organization=leaf,
        edge=edge,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.UNATTRIBUTED,
        status=PoolFactualReviewStatus.PENDING,
        source_document_ref="Document_РеализацияТоваровУслуг(guid'sale-2')",
        delta_payload={
            "amount_with_vat": "15.00",
            "amount_without_vat": "12.50",
            "vat_amount": "2.50",
            "kind": "sale",
        },
        metadata={
            "database_id": str(database.id),
            "lane": PoolFactualLane.READ,
            "raw_organization_id": str(leaf.id),
            "raw_batch_id": "",
            "raw_edge_id": "",
        },
    )
    actor = User.objects.create_user(username=f"factual-result-actor-{uuid4().hex[:6]}", password="pass")
    apply_pool_factual_review_action(
        review_item_id=str(review_item.id),
        tenant_id=str(tenant.id),
        actor_id=str(actor.id),
        action=FACTUAL_REVIEW_ACTION_ATTRIBUTE,
        batch_id=str(batch.id),
        edge_id=str(edge.id),
        organization_id=str(leaf.id),
        note="resolve unattributed target before replay",
    )
    payload = {
        "node_results": {
            "factual_sync_source_slice": {
                "step": "factual_sync_source_slice",
                "pool_id": str(pool.id),
                "database_id": str(database.id),
                "lane": "read",
                "quarter_start": "2026-01-01",
                "quarter_end": "2026-03-31",
                "boundary_reads": {
                    "accounting_register": 1,
                    "information_register": 1,
                    "Document_РеализацияТоваровУслуг": 2,
                },
                "source_checkpoint_token": "cp-resolution-001",
                "factual_documents": [
                    {
                        "source_document_ref": "Document_ПоступлениеТоваровУслуг(guid'receipt-2')",
                        "organization_id": str(leaf.id),
                        "batch_id": str(batch.id),
                        "edge_id": str(edge.id),
                        "amount_with_vat": "15.00",
                        "amount_without_vat": "12.50",
                        "vat_amount": "2.50",
                        "comment": (
                            f"CCPOOL:v=1;pool={pool.id};run=-;batch={batch.id};org={leaf.id};q=2026Q1;kind=receipt"
                        ),
                        "kind": "receipt",
                        "modified_at": "2026-03-26T09:00:00Z",
                    },
                    {
                        "source_document_ref": "Document_РеализацияТоваровУслуг(guid'sale-2')",
                        "organization_id": str(leaf.id),
                        "batch_id": None,
                        "edge_id": None,
                        "amount_with_vat": "15.00",
                        "amount_without_vat": "12.50",
                        "vat_amount": "2.50",
                        "comment": "manual unattributed sale",
                        "kind": "sale",
                        "modified_at": "2026-03-27T10:00:00Z",
                    },
                ],
            }
        }
    }
    execution = _build_execution(
        tenant=tenant,
        pool=pool,
        database=database,
        checkpoint=checkpoint,
        organization_id=str(leaf.id),
        lane=PoolFactualLane.READ,
        payload=payload,
    )

    assert project_pool_factual_result_from_execution(execution=execution, result_payload=payload) is True

    snapshot = PoolFactualBalanceSnapshot.objects.get(
        tenant=tenant,
        pool=pool,
        batch=batch,
        organization=leaf,
        edge=edge,
    )
    assert snapshot.amount_with_vat == Decimal("0.00")
    assert snapshot.amount_without_vat == Decimal("0.00")
    assert snapshot.vat_amount == Decimal("0.00")
    assert snapshot.incoming_amount == Decimal("15.00")
    assert snapshot.outgoing_amount == Decimal("15.00")
    assert snapshot.open_balance == Decimal("0.00")
    assert not PoolFactualReviewItem.objects.filter(
        tenant=tenant,
        pool=pool,
        reason=PoolFactualReviewReason.UNATTRIBUTED,
        status=PoolFactualReviewStatus.PENDING,
    ).exists()


@pytest.mark.django_db
def test_project_pool_factual_result_from_execution_refreshes_settlement_for_batch_inside_quarter() -> None:
    from apps.intercompany_pools.factual_result_projection import project_pool_factual_result_from_execution

    tenant = Tenant.objects.create(slug=f"factual-result-mid-quarter-{uuid4().hex[:6]}", name="Factual Result Mid Quarter")
    pool, root, leaf, database = _create_pool_scope(tenant=tenant, suffix="mid-quarter")
    edge = _create_edge(pool=pool, root=root, leaf=leaf)
    batch = PoolBatch.objects.create(
        tenant=tenant,
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
        period_start=date(2026, 2, 1),
        period_end=date(2026, 2, 28),
        start_organization=root,
        source_reference="receipt-mid-quarter",
    )
    settlement = PoolBatchSettlement.objects.create(
        tenant=tenant,
        batch=batch,
        status=PoolBatchSettlementStatus.INGESTED,
    )
    checkpoint = PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
    )
    payload = {
        "node_results": {
            "factual_sync_source_slice": {
                "step": "factual_sync_source_slice",
                "pool_id": str(pool.id),
                "database_id": str(database.id),
                "lane": "read",
                "quarter_start": "2026-01-01",
                "quarter_end": "2026-03-31",
                "boundary_reads": {
                    "accounting_register": 1,
                    "information_register": 1,
                    "Document_ПоступлениеТоваровУслуг": 1,
                },
                "source_checkpoint_token": "cp-mid-quarter-001",
                "factual_documents": [
                    {
                        "source_document_ref": "Document_ПоступлениеТоваровУслуг(guid'mid-quarter-1')",
                        "organization_id": str(leaf.id),
                        "batch_id": str(batch.id),
                        "edge_id": str(edge.id),
                        "amount_with_vat": "45.00",
                        "amount_without_vat": "37.50",
                        "vat_amount": "7.50",
                        "comment": (
                            f"CCPOOL:v=1;pool={pool.id};run=-;batch={batch.id};org={leaf.id};q=2026Q1;kind=receipt"
                        ),
                        "kind": "receipt",
                        "modified_at": "2026-02-14T09:00:00Z",
                    }
                ],
            }
        }
    }
    execution = _build_execution(
        tenant=tenant,
        pool=pool,
        database=database,
        checkpoint=checkpoint,
        organization_id=str(leaf.id),
        lane=PoolFactualLane.READ,
        payload=payload,
    )

    assert project_pool_factual_result_from_execution(execution=execution, result_payload=payload) is True

    settlement.refresh_from_db()
    assert settlement.status == PoolBatchSettlementStatus.DISTRIBUTED
    assert settlement.incoming_amount == Decimal("45.00")
    assert settlement.outgoing_amount == Decimal("0.00")
    assert settlement.open_balance == Decimal("45.00")


@pytest.mark.django_db
def test_project_pool_factual_result_from_execution_only_raises_late_correction_for_frozen_delta() -> None:
    from apps.intercompany_pools.factual_result_projection import project_pool_factual_result_from_execution

    tenant = Tenant.objects.create(slug=f"factual-result-late-{uuid4().hex[:6]}", name="Factual Result Late")
    pool, root, leaf, database = _create_pool_scope(tenant=tenant, suffix="003")
    edge = _create_edge(pool=pool, root=root, leaf=leaf)
    batch = _create_batch(tenant=tenant, pool=pool, root=root, suffix="late-001")
    checkpoint = PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
    )
    initial_payload = {
        "node_results": {
            "factual_sync_source_slice": {
                "step": "factual_sync_source_slice",
                "pool_id": str(pool.id),
                "database_id": str(database.id),
                "lane": "read",
                "quarter_start": "2026-01-01",
                "quarter_end": "2026-03-31",
                "boundary_reads": {
                    "accounting_register": 1,
                    "information_register": 1,
                    "Document_КорректировкаРеализации": 1,
                },
                "source_checkpoint_token": "cp-late-001",
                "factual_documents": [
                    {
                        "source_document_ref": "Document_КорректировкаРеализации(guid'late-1')",
                        "organization_id": str(leaf.id),
                        "batch_id": str(batch.id),
                        "edge_id": str(edge.id),
                        "amount_with_vat": "10.00",
                        "amount_without_vat": "8.33",
                        "vat_amount": "1.67",
                        "comment": (
                            f"CCPOOL:v=1;pool={pool.id};run=-;batch={batch.id};org={leaf.id};q=2026Q1;kind=receipt"
                        ),
                        "kind": "receipt",
                        "modified_at": "2026-03-26T09:00:00Z",
                    }
                ],
            }
        }
    }
    changed_payload = {
        "node_results": {
            "factual_sync_source_slice": {
                "step": "factual_sync_source_slice",
                "pool_id": str(pool.id),
                "database_id": str(database.id),
                "lane": "read",
                "quarter_start": "2026-01-01",
                "quarter_end": "2026-03-31",
                "boundary_reads": {
                    "accounting_register": 1,
                    "information_register": 1,
                    "Document_КорректировкаРеализации": 1,
                },
                "source_checkpoint_token": "cp-late-002",
                "factual_documents": [
                    {
                        "source_document_ref": "Document_КорректировкаРеализации(guid'late-1')",
                        "organization_id": str(leaf.id),
                        "batch_id": str(batch.id),
                        "edge_id": str(edge.id),
                        "amount_with_vat": "20.00",
                        "amount_without_vat": "16.67",
                        "vat_amount": "3.33",
                        "comment": (
                            f"CCPOOL:v=1;pool={pool.id};run=-;batch={batch.id};org={leaf.id};q=2026Q1;kind=receipt"
                        ),
                        "kind": "receipt",
                        "modified_at": "2026-03-28T09:00:00Z",
                    }
                ],
            }
        }
    }
    initial_execution = _build_execution(
        tenant=tenant,
        pool=pool,
        database=database,
        checkpoint=checkpoint,
        organization_id=str(leaf.id),
        lane=PoolFactualLane.READ,
        payload=initial_payload,
    )
    changed_execution = _build_execution(
        tenant=tenant,
        pool=pool,
        database=database,
        checkpoint=checkpoint,
        organization_id=str(leaf.id),
        lane=PoolFactualLane.READ,
        payload=changed_payload,
    )

    assert project_pool_factual_result_from_execution(execution=initial_execution, result_payload=initial_payload) is True
    checkpoint.refresh_from_db()
    checkpoint.metadata = {
        **dict(checkpoint.metadata or {}),
        "frozen_at": "2026-03-31T23:59:59+00:00",
        "frozen_source_documents": dict(checkpoint.metadata.get("latest_source_documents") or {}),
    }
    checkpoint.save(update_fields=["metadata", "updated_at"])

    assert project_pool_factual_result_from_execution(execution=initial_execution, result_payload=initial_payload) is True
    assert not PoolFactualReviewItem.objects.filter(
        tenant=tenant,
        pool=pool,
        reason=PoolFactualReviewReason.LATE_CORRECTION,
    ).exists()

    assert project_pool_factual_result_from_execution(execution=changed_execution, result_payload=changed_payload) is True
    review_item = PoolFactualReviewItem.objects.get(
        tenant=tenant,
        pool=pool,
        reason=PoolFactualReviewReason.LATE_CORRECTION,
        source_document_ref="Document_КорректировкаРеализации(guid'late-1')",
    )
    snapshot_before = PoolFactualBalanceSnapshot.objects.get(
        tenant=tenant,
        pool=pool,
        batch=batch,
        organization=leaf,
        edge=edge,
    )
    assert review_item.status == PoolFactualReviewStatus.PENDING
    assert review_item.metadata["change_type"] == "changed"
    actor = User.objects.create_user(username=f"factual-result-review-{uuid4().hex[:6]}", password="pass")

    apply_pool_factual_review_action(
        review_item_id=str(review_item.id),
        tenant_id=str(tenant.id),
        actor_id=str(actor.id),
        action=FACTUAL_REVIEW_ACTION_RECONCILE,
        note="manual reconcile",
    )

    review_item.refresh_from_db()
    snapshot_after = PoolFactualBalanceSnapshot.objects.get(id=snapshot_before.id)
    assert review_item.status == PoolFactualReviewStatus.RECONCILED
    assert snapshot_after.amount_with_vat == snapshot_before.amount_with_vat
    assert snapshot_after.amount_without_vat == snapshot_before.amount_without_vat
    assert snapshot_after.vat_amount == snapshot_before.vat_amount
    assert snapshot_after.open_balance == snapshot_before.open_balance

    assert project_pool_factual_result_from_execution(execution=changed_execution, result_payload=changed_payload) is True
    review_item.refresh_from_db()
    assert review_item.status == PoolFactualReviewStatus.RECONCILED
    assert (
        PoolFactualReviewItem.objects.filter(
            tenant=tenant,
            pool=pool,
            reason=PoolFactualReviewReason.LATE_CORRECTION,
            source_document_ref="Document_КорректировкаРеализации(guid'late-1')",
        ).count()
        == 1
    )
