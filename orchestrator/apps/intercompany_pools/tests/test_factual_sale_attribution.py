from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolBatch,
    PoolBatchKind,
    PoolBatchSourceType,
    PoolEdgeVersion,
    PoolFactualBalanceSnapshot,
    PoolNodeVersion,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"sale-attribution-db-{suffix}-{uuid4().hex[:6]}",
        host="localhost",
        odata_url=f"http://localhost/odata/sale-attribution-{suffix}.odata",
        username="admin",
        password="secret",
    )


def _create_pool_scope(
    *,
    tenant: Tenant,
    suffix: str,
) -> tuple[OrganizationPool, Organization, Organization, PoolEdgeVersion, PoolEdgeVersion]:
    database_root = _create_database(tenant=tenant, suffix=f"{suffix}-root")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"sale-attribution-pool-{suffix}-{uuid4().hex[:6]}",
        name=f"Sale Attribution Pool {suffix}",
    )
    root = Organization.objects.create(
        tenant=tenant,
        database=database_root,
        name=f"Root {suffix}",
        inn=f"77020000{suffix[:4].zfill(4)}",
    )
    leaf = Organization.objects.create(
        tenant=tenant,
        name=f"Leaf {suffix}",
        inn=f"78020000{suffix[:4].zfill(4)}",
    )
    alt_root = Organization.objects.create(
        tenant=tenant,
        name=f"Alt Root {suffix}",
        inn=f"79020000{suffix[:4].zfill(4)}",
    )
    root_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=root,
        effective_from=date(2026, 1, 1),
        is_root=True,
    )
    alt_root_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=alt_root,
        effective_from=date(2026, 1, 1),
        is_root=False,
    )
    leaf_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=leaf,
        effective_from=date(2026, 1, 1),
        is_root=False,
    )
    edge_primary = PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=leaf_node,
        effective_from=date(2026, 1, 1),
        weight="1.0",
    )
    edge_secondary = PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=alt_root_node,
        child_node=leaf_node,
        effective_from=date(2026, 1, 1),
        weight="1.0",
    )
    return pool, root, leaf, edge_primary, edge_secondary


def _create_batch(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    start_organization: Organization,
    period_start: date,
) -> PoolBatch:
    quarter_end = {
        1: date(period_start.year, 3, 31),
        4: date(period_start.year, 6, 30),
        7: date(period_start.year, 9, 30),
        10: date(period_start.year, 12, 31),
    }[period_start.month]
    return PoolBatch.objects.create(
        tenant=tenant,
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
        period_start=period_start,
        period_end=quarter_end,
        start_organization=start_organization,
        source_reference=f"receipt-{period_start.isoformat()}",
    )


def _create_snapshot(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    batch: PoolBatch,
    organization: Organization,
    edge: PoolEdgeVersion,
    quarter_start: date,
    quarter_end: date,
    amount_with_vat: str,
    amount_without_vat: str,
    vat_amount: str,
    incoming_amount: str,
    outgoing_amount: str,
    open_balance: str,
) -> PoolFactualBalanceSnapshot:
    return PoolFactualBalanceSnapshot.objects.create(
        tenant=tenant,
        pool=pool,
        batch=batch,
        organization=organization,
        edge=edge,
        quarter_start=quarter_start,
        quarter_end=quarter_end,
        amount_with_vat=amount_with_vat,
        amount_without_vat=amount_without_vat,
        vat_amount=vat_amount,
        incoming_amount=incoming_amount,
        outgoing_amount=outgoing_amount,
        open_balance=open_balance,
    )


@pytest.mark.django_db
def test_build_leaf_sale_attribution_plan_allocates_oldest_first() -> None:
    from apps.intercompany_pools.factual_sale_attribution import build_leaf_sale_attribution_plan

    tenant = Tenant.objects.create(slug=f"sale-attribution-plan-{uuid4().hex[:6]}", name="Sale Attribution Plan")
    pool, root, leaf, edge_primary, edge_secondary = _create_pool_scope(tenant=tenant, suffix="001")
    batch_q1 = _create_batch(tenant=tenant, pool=pool, start_organization=root, period_start=date(2026, 1, 1))
    batch_q2 = _create_batch(tenant=tenant, pool=pool, start_organization=root, period_start=date(2026, 4, 1))
    older_snapshot = _create_snapshot(
        tenant=tenant,
        pool=pool,
        batch=batch_q1,
        organization=leaf,
        edge=edge_primary,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        amount_with_vat="30.00",
        amount_without_vat="25.00",
        vat_amount="5.00",
        incoming_amount="30.00",
        outgoing_amount="0.00",
        open_balance="30.00",
    )
    newer_snapshot = _create_snapshot(
        tenant=tenant,
        pool=pool,
        batch=batch_q2,
        organization=leaf,
        edge=edge_secondary,
        quarter_start=date(2026, 4, 1),
        quarter_end=date(2026, 6, 30),
        amount_with_vat="50.00",
        amount_without_vat="41.67",
        vat_amount="8.33",
        incoming_amount="50.00",
        outgoing_amount="0.00",
        open_balance="50.00",
    )

    plan = build_leaf_sale_attribution_plan(
        organization=leaf,
        snapshots=[newer_snapshot, older_snapshot],
        sale_amount="60.00",
    )

    assert [item.snapshot_id for item in plan.allocations] == [older_snapshot.id, newer_snapshot.id]
    assert [item.attributed_amount for item in plan.allocations] == [Decimal("30.00"), Decimal("30.00")]
    assert plan.unattributed_amount == Decimal("0.00")


@pytest.mark.django_db
def test_build_leaf_sale_attribution_plan_leaves_overage_unattributed() -> None:
    from apps.intercompany_pools.factual_sale_attribution import build_leaf_sale_attribution_plan

    tenant = Tenant.objects.create(slug=f"sale-attribution-over-{uuid4().hex[:6]}", name="Sale Attribution Over")
    pool, root, leaf, edge_primary, _edge_secondary = _create_pool_scope(tenant=tenant, suffix="002")
    batch = _create_batch(tenant=tenant, pool=pool, start_organization=root, period_start=date(2026, 1, 1))
    snapshot = _create_snapshot(
        tenant=tenant,
        pool=pool,
        batch=batch,
        organization=leaf,
        edge=edge_primary,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        amount_with_vat="40.00",
        amount_without_vat="33.33",
        vat_amount="6.67",
        incoming_amount="40.00",
        outgoing_amount="0.00",
        open_balance="40.00",
    )

    plan = build_leaf_sale_attribution_plan(
        organization=leaf,
        snapshots=[snapshot],
        sale_amount="55.00",
    )

    assert len(plan.allocations) == 1
    assert plan.allocations[0].attributed_amount == Decimal("40.00")
    assert plan.unattributed_amount == Decimal("15.00")


@pytest.mark.django_db
def test_apply_leaf_sale_attribution_plan_updates_snapshots_proportionally() -> None:
    from apps.intercompany_pools.factual_sale_attribution import (
        apply_leaf_sale_attribution_plan,
        build_leaf_sale_attribution_plan,
    )

    tenant = Tenant.objects.create(slug=f"sale-attribution-apply-{uuid4().hex[:6]}", name="Sale Attribution Apply")
    pool, root, leaf, edge_primary, _edge_secondary = _create_pool_scope(tenant=tenant, suffix="003")
    batch = _create_batch(tenant=tenant, pool=pool, start_organization=root, period_start=date(2026, 1, 1))
    snapshot = _create_snapshot(
        tenant=tenant,
        pool=pool,
        batch=batch,
        organization=leaf,
        edge=edge_primary,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        amount_with_vat="120.00",
        amount_without_vat="100.00",
        vat_amount="20.00",
        incoming_amount="120.00",
        outgoing_amount="0.00",
        open_balance="120.00",
    )

    plan = build_leaf_sale_attribution_plan(
        organization=leaf,
        snapshots=[snapshot],
        sale_amount="60.00",
    )
    result = apply_leaf_sale_attribution_plan(plan=plan)

    snapshot.refresh_from_db()
    assert result.unattributed_amount == Decimal("0.00")
    assert snapshot.outgoing_amount == Decimal("60.00")
    assert snapshot.open_balance == Decimal("60.00")
    assert snapshot.amount_with_vat == Decimal("60.00")
    assert snapshot.amount_without_vat == Decimal("50.00")
    assert snapshot.vat_amount == Decimal("10.00")
    assert snapshot.metadata["sale_attribution_history"][0]["attributed_amount"] == "60.00"
