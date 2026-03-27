from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from django.core.exceptions import ValidationError

from apps.databases.models import Database
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
    PoolRun,
    PoolRunDirection,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"factual-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/factual-{suffix}.odata",
        username="admin",
        password="secret",
    )


def _create_pool_scope(*, tenant: Tenant, suffix: str) -> tuple[OrganizationPool, Organization, Organization, Database]:
    database = _create_database(tenant=tenant, suffix=suffix)
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"factual-pool-{suffix}",
        name=f"Factual Pool {suffix}",
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
    return pool, root, leaf, database


def _create_edge(*, pool: OrganizationPool, root: Organization, leaf: Organization, effective_from: date) -> PoolEdgeVersion:
    root_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=root,
        effective_from=effective_from,
        is_root=True,
    )
    leaf_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=leaf,
        effective_from=effective_from,
        is_root=False,
    )
    return PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=leaf_node,
        effective_from=effective_from,
        weight="1.0",
    )


@pytest.mark.django_db
def test_factual_boundary_models_do_not_change_pool_run_execution_store() -> None:
    tenant = Tenant.objects.create(slug="factual-boundary", name="Factual Boundary")
    pool, root, leaf, database = _create_pool_scope(tenant=tenant, suffix="001")
    edge = _create_edge(pool=pool, root=root, leaf=leaf, effective_from=date(2026, 1, 1))
    run = PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        direction=PoolRunDirection.TOP_DOWN,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
    )

    batch = PoolBatch.objects.create(
        tenant=tenant,
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        start_organization=root,
        run=run,
        source_reference="receipt-registry-001",
        raw_payload_ref="files/receipt-001.xlsx",
    )
    settlement = PoolBatchSettlement.objects.create(
        tenant=tenant,
        batch=batch,
        status=PoolBatchSettlementStatus.DISTRIBUTED,
        incoming_amount="120.00",
        outgoing_amount="0.00",
        open_balance="120.00",
    )
    projection = PoolFactualBalanceSnapshot.objects.create(
        tenant=tenant,
        pool=pool,
        batch=batch,
        organization=leaf,
        edge=edge,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        amount_with_vat="120.00",
        amount_without_vat="100.00",
        vat_amount="20.00",
        incoming_amount="120.00",
        outgoing_amount="0.00",
        open_balance="120.00",
    )
    checkpoint = PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        source_checkpoint_token="cp-001",
    )
    review_item = PoolFactualReviewItem.objects.create(
        tenant=tenant,
        pool=pool,
        batch=batch,
        organization=leaf,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.UNATTRIBUTED,
        status=PoolFactualReviewStatus.PENDING,
        source_document_ref="Document_РеализацияТоваровУслуг(guid'11111111-1111-1111-1111-111111111111')",
    )

    persisted_run = PoolRun.objects.values(
        "status",
        "runtime_projection_snapshot",
        "publication_summary",
    ).get(id=run.id)

    assert persisted_run["status"] == PoolRun.STATUS_DRAFT
    assert persisted_run["runtime_projection_snapshot"] == {}
    assert persisted_run["publication_summary"] == {}
    assert batch.settlement.id == settlement.id
    assert projection.batch_id == batch.id
    assert checkpoint.database_id == database.id
    assert review_item.reason == PoolFactualReviewReason.UNATTRIBUTED


@pytest.mark.django_db
def test_pool_batch_rejects_run_or_start_organization_outside_scope() -> None:
    tenant = Tenant.objects.create(slug="factual-batch-scope", name="Factual Batch Scope")
    foreign_tenant = Tenant.objects.create(slug="factual-batch-foreign", name="Factual Batch Foreign")
    pool, root, _, _ = _create_pool_scope(tenant=tenant, suffix="002")
    foreign_pool, foreign_root, _, _ = _create_pool_scope(tenant=foreign_tenant, suffix="003")
    foreign_run = PoolRun.objects.create(
        tenant=foreign_tenant,
        pool=foreign_pool,
        direction=PoolRunDirection.TOP_DOWN,
        period_start=date(2026, 1, 1),
    )

    with pytest.raises(ValidationError):
        PoolBatch(
            tenant=tenant,
            pool=pool,
            batch_kind=PoolBatchKind.RECEIPT,
            source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
            period_start=date(2026, 1, 1),
            start_organization=foreign_root,
        ).full_clean()

    with pytest.raises(ValidationError):
        PoolBatch(
            tenant=tenant,
            pool=pool,
            batch_kind=PoolBatchKind.RECEIPT,
            source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
            period_start=date(2026, 1, 1),
            start_organization=root,
            run=foreign_run,
        ).full_clean()


@pytest.mark.django_db
def test_factual_projection_rejects_edge_outside_batch_pool() -> None:
    tenant = Tenant.objects.create(slug="factual-projection-scope", name="Factual Projection Scope")
    pool, root, leaf, _ = _create_pool_scope(tenant=tenant, suffix="004")
    foreign_pool, foreign_root, foreign_leaf, _ = _create_pool_scope(tenant=tenant, suffix="005")
    foreign_edge = _create_edge(
        pool=foreign_pool,
        root=foreign_root,
        leaf=foreign_leaf,
        effective_from=date(2026, 1, 1),
    )
    batch = PoolBatch.objects.create(
        tenant=tenant,
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
        period_start=date(2026, 1, 1),
        start_organization=root,
    )

    with pytest.raises(ValidationError):
        PoolFactualBalanceSnapshot(
            tenant=tenant,
            pool=pool,
            batch=batch,
            organization=leaf,
            edge=foreign_edge,
            quarter_start=date(2026, 1, 1),
            quarter_end=date(2026, 3, 31),
            amount_with_vat="12.00",
            amount_without_vat="10.00",
            vat_amount="2.00",
            incoming_amount="12.00",
            outgoing_amount="0.00",
            open_balance="12.00",
        ).full_clean()


@pytest.mark.django_db
def test_factual_review_terminal_status_requires_resolution_timestamp() -> None:
    tenant = Tenant.objects.create(slug="factual-review-terminal", name="Factual Review Terminal")
    pool, _, leaf, _ = _create_pool_scope(tenant=tenant, suffix="006")

    with pytest.raises(ValidationError):
        PoolFactualReviewItem(
            tenant=tenant,
            pool=pool,
            organization=leaf,
            quarter_start=date(2026, 1, 1),
            quarter_end=date(2026, 3, 31),
            reason=PoolFactualReviewReason.LATE_CORRECTION,
            status=PoolFactualReviewStatus.RECONCILED,
        ).full_clean()

    review_item = PoolFactualReviewItem.objects.create(
        tenant=tenant,
        pool=pool,
        organization=leaf,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.LATE_CORRECTION,
        status=PoolFactualReviewStatus.RECONCILED,
        resolved_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    assert review_item.status == PoolFactualReviewStatus.RECONCILED
