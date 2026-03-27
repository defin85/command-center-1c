from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from uuid import uuid4

import pytest

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
    PoolNodeVersion,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"carry-forward-db-{suffix}-{uuid4().hex[:6]}",
        host="localhost",
        odata_url=f"http://localhost/odata/carry-forward-{suffix}.odata",
        username="admin",
        password="secret",
        server_address="srv-carry",
        server_port=1540,
    )


def _create_scope(
    *,
    tenant: Tenant,
    suffix: str,
) -> tuple[OrganizationPool, Organization, Organization, Database, PoolEdgeVersion]:
    database = _create_database(tenant=tenant, suffix=suffix)
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"carry-forward-pool-{suffix}-{uuid4().hex[:6]}",
        name=f"Carry Forward Pool {suffix}",
    )
    root = Organization.objects.create(
        tenant=tenant,
        database=database,
        name=f"Root {suffix}",
        inn=f"77010000{suffix[:4].zfill(4)}",
    )
    leaf = Organization.objects.create(
        tenant=tenant,
        name=f"Leaf {suffix}",
        inn=f"78010000{suffix[:4].zfill(4)}",
    )
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
    edge = PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=leaf_node,
        effective_from=date(2026, 1, 1),
        weight="1.0",
    )
    return pool, root, leaf, database, edge


def _create_batch_with_settlement(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    start_organization: Organization,
) -> tuple[PoolBatch, PoolBatchSettlement]:
    batch = PoolBatch.objects.create(
        tenant=tenant,
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        start_organization=start_organization,
        source_reference="receipt-registry-q1",
    )
    settlement = PoolBatchSettlement.objects.create(
        tenant=tenant,
        batch=batch,
        status=PoolBatchSettlementStatus.PARTIALLY_CLOSED,
        incoming_amount="120.00",
        outgoing_amount="75.00",
        open_balance="45.00",
    )
    return batch, settlement


@pytest.mark.django_db
def test_materialize_factual_carry_forward_moves_open_balance_to_same_node_next_quarter() -> None:
    from apps.intercompany_pools.factual_carry_forward import materialize_factual_carry_forward

    tenant = Tenant.objects.create(slug=f"carry-forward-{uuid4().hex[:6]}", name="Carry Forward")
    pool, root, leaf, _database, edge = _create_scope(tenant=tenant, suffix="001")
    batch, settlement = _create_batch_with_settlement(
        tenant=tenant,
        pool=pool,
        start_organization=root,
    )
    freshness_at = datetime(2026, 3, 31, 20, 15, tzinfo=dt_timezone.utc)
    applied_at = datetime(2026, 4, 1, 0, 5, tzinfo=dt_timezone.utc)
    source_snapshot = PoolFactualBalanceSnapshot.objects.create(
        tenant=tenant,
        pool=pool,
        batch=batch,
        organization=leaf,
        edge=edge,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        amount_with_vat="45.00",
        amount_without_vat="37.50",
        vat_amount="7.50",
        incoming_amount="120.00",
        outgoing_amount="75.00",
        open_balance="45.00",
        freshness_at=freshness_at,
    )

    result = materialize_factual_carry_forward(
        source_snapshot=source_snapshot,
        applied_at=applied_at,
    )

    assert result is not None
    assert result.created is True
    assert result.target_snapshot.organization_id == leaf.id
    assert result.target_snapshot.edge_id == edge.id
    assert result.target_snapshot.batch_id == batch.id
    assert result.target_snapshot.quarter_start == date(2026, 4, 1)
    assert result.target_snapshot.quarter_end == date(2026, 6, 30)
    assert result.target_snapshot.amount_with_vat == Decimal("45.00")
    assert result.target_snapshot.amount_without_vat == Decimal("37.50")
    assert result.target_snapshot.vat_amount == Decimal("7.50")
    assert result.target_snapshot.incoming_amount == Decimal("45.00")
    assert result.target_snapshot.outgoing_amount == Decimal("0.00")
    assert result.target_snapshot.open_balance == Decimal("45.00")
    assert result.target_snapshot.metadata["carry_forward"]["source_snapshot_id"] == str(source_snapshot.id)
    assert result.target_snapshot.metadata["carry_forward"]["source_quarter_start"] == "2026-01-01"
    assert result.target_snapshot.metadata["carry_forward"]["applied_at"] == applied_at.isoformat()

    source_snapshot.refresh_from_db()
    settlement.refresh_from_db()
    assert source_snapshot.metadata["carry_forward"]["target_snapshot_id"] == str(result.target_snapshot.id)
    assert source_snapshot.metadata["carry_forward"]["target_quarter_start"] == "2026-04-01"
    assert settlement.status == PoolBatchSettlementStatus.CARRIED_FORWARD
    assert settlement.summary["carry_forward"]["target_snapshot_id"] == str(result.target_snapshot.id)
    assert settlement.summary["carry_forward"]["source_snapshot_id"] == str(source_snapshot.id)


@pytest.mark.django_db
def test_materialize_factual_carry_forward_skips_zero_open_balance() -> None:
    from apps.intercompany_pools.factual_carry_forward import materialize_factual_carry_forward

    tenant = Tenant.objects.create(slug=f"carry-forward-zero-{uuid4().hex[:6]}", name="Carry Forward Zero")
    pool, root, leaf, _database, edge = _create_scope(tenant=tenant, suffix="002")
    batch, _settlement = _create_batch_with_settlement(
        tenant=tenant,
        pool=pool,
        start_organization=root,
    )
    source_snapshot = PoolFactualBalanceSnapshot.objects.create(
        tenant=tenant,
        pool=pool,
        batch=batch,
        organization=leaf,
        edge=edge,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        amount_with_vat="0.00",
        amount_without_vat="0.00",
        vat_amount="0.00",
        incoming_amount="10.00",
        outgoing_amount="10.00",
        open_balance="0.00",
    )

    result = materialize_factual_carry_forward(source_snapshot=source_snapshot)

    assert result is None
    assert PoolFactualBalanceSnapshot.objects.filter(
        tenant=tenant,
        quarter_start=date(2026, 4, 1),
    ).count() == 0


@pytest.mark.django_db
def test_materialize_factual_carry_forward_is_idempotent_for_same_source_snapshot() -> None:
    from apps.intercompany_pools.factual_carry_forward import materialize_factual_carry_forward

    tenant = Tenant.objects.create(slug=f"carry-forward-idempotent-{uuid4().hex[:6]}", name="Carry Forward Idempotent")
    pool, root, leaf, _database, edge = _create_scope(tenant=tenant, suffix="003")
    batch, _settlement = _create_batch_with_settlement(
        tenant=tenant,
        pool=pool,
        start_organization=root,
    )
    source_snapshot = PoolFactualBalanceSnapshot.objects.create(
        tenant=tenant,
        pool=pool,
        batch=batch,
        organization=leaf,
        edge=edge,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        amount_with_vat="45.00",
        amount_without_vat="37.50",
        vat_amount="7.50",
        incoming_amount="120.00",
        outgoing_amount="75.00",
        open_balance="45.00",
    )

    first = materialize_factual_carry_forward(source_snapshot=source_snapshot)
    second = materialize_factual_carry_forward(source_snapshot=source_snapshot)

    assert first is not None
    assert second is not None
    assert first.target_snapshot.id == second.target_snapshot.id
    assert first.created is True
    assert second.created is False
