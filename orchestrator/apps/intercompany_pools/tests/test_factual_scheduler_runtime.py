from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.models import (
    OrganizationPool,
    PoolBatch,
    PoolBatchKind,
    PoolBatchSettlement,
    PoolBatchSettlementStatus,
    PoolBatchSourceType,
    PoolFactualLane,
    PoolFactualSyncCheckpoint,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"factual-scheduler-db-{suffix}-{uuid4().hex[:6]}",
        host="localhost",
        odata_url=f"http://localhost/odata/factual-scheduler-{suffix}.odata",
        username="admin",
        password="secret",
    )


def _create_pool(*, tenant: Tenant, suffix: str, is_active: bool = True) -> OrganizationPool:
    return OrganizationPool.objects.create(
        tenant=tenant,
        code=f"factual-scheduler-pool-{suffix}-{uuid4().hex[:6]}",
        name=f"Factual Scheduler Pool {suffix}",
        is_active=is_active,
    )


@pytest.mark.django_db
def test_trigger_pool_factual_active_sync_window_scans_only_active_pools_for_current_quarter() -> None:
    from apps.intercompany_pools.factual_scheduler_runtime import trigger_pool_factual_active_sync_window

    tenant = Tenant.objects.create(slug=f"factual-scheduler-active-{uuid4().hex[:6]}", name="Factual Scheduler Active")
    active_pool = _create_pool(tenant=tenant, suffix="active", is_active=True)
    _create_pool(tenant=tenant, suffix="inactive", is_active=False)
    fixed_now = datetime(2026, 4, 14, 10, 0, tzinfo=dt_timezone.utc)

    with patch(
        "apps.intercompany_pools.factual_scheduler_runtime.ensure_pool_factual_workspace_default_sync",
        return_value=tuple(),
    ) as ensure_sync:
        summary = trigger_pool_factual_active_sync_window(now=fixed_now)

    assert summary["quarter_start"] == "2026-04-01"
    assert summary["pools_scanned"] == 1
    ensure_sync.assert_called_once_with(
        pool=active_pool,
        quarter_start=date(2026, 4, 1),
        now=fixed_now,
        requested_activity="active",
    )


@pytest.mark.django_db
def test_trigger_pool_factual_active_sync_window_reuses_warm_activity_for_historical_open_context() -> None:
    from apps.intercompany_pools.factual_scheduler_runtime import trigger_pool_factual_active_sync_window

    tenant = Tenant.objects.create(
        slug=f"factual-scheduler-warm-{uuid4().hex[:6]}",
        name="Factual Scheduler Warm",
    )
    pool = _create_pool(tenant=tenant, suffix="warm", is_active=True)
    database = _create_database(tenant=tenant, suffix="warm")
    PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        metadata={"freshness_state": "fresh", "freshness_target_seconds": 120},
    )
    batch = PoolBatch.objects.create(
        tenant=tenant,
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.MANUAL,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        source_reference="receipt-q1-open",
    )
    PoolBatchSettlement.objects.create(
        tenant=tenant,
        batch=batch,
        status=PoolBatchSettlementStatus.CARRIED_FORWARD,
        incoming_amount="120.00",
        outgoing_amount="80.00",
        open_balance="40.00",
        summary={},
    )
    fixed_now = datetime(2026, 4, 14, 10, 0, tzinfo=dt_timezone.utc)

    with patch(
        "apps.intercompany_pools.factual_scheduler_runtime.ensure_pool_factual_workspace_default_sync",
        return_value=tuple(),
    ) as ensure_sync:
        trigger_pool_factual_active_sync_window(now=fixed_now)

    assert ensure_sync.call_count == 2
    active_call, warm_call = ensure_sync.call_args_list
    assert active_call.kwargs == {
        "pool": pool,
        "quarter_start": date(2026, 4, 1),
        "now": fixed_now,
        "requested_activity": "active",
    }
    assert warm_call.kwargs == {
        "pool": pool,
        "quarter_start": date(2026, 1, 1),
        "now": fixed_now,
        "requested_activity": "warm",
    }


@pytest.mark.django_db
def test_trigger_pool_factual_active_sync_window_skips_inactive_pool_checkpoint_contexts() -> None:
    from apps.intercompany_pools.factual_scheduler_runtime import trigger_pool_factual_active_sync_window

    tenant = Tenant.objects.create(
        slug=f"factual-scheduler-inactive-current-{uuid4().hex[:6]}",
        name="Factual Scheduler Inactive Current",
    )
    pool = _create_pool(tenant=tenant, suffix="inactive-current", is_active=False)
    database = _create_database(tenant=tenant, suffix="inactive-current")
    fixed_now = datetime(2026, 4, 14, 10, 0, tzinfo=dt_timezone.utc)
    PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 4, 1),
        quarter_end=date(2026, 6, 30),
        metadata={"freshness_state": "stale", "freshness_target_seconds": 120},
    )

    with patch(
        "apps.intercompany_pools.factual_scheduler_runtime.ensure_pool_factual_workspace_default_sync",
        return_value=tuple(),
    ) as ensure_sync:
        summary = trigger_pool_factual_active_sync_window(now=fixed_now)

    assert summary["quarter_start"] == "2026-04-01"
    assert summary["pools_scanned"] == 0
    assert summary["checkpoints_touched"] == 0
    assert summary["checkpoints_running"] == 0
    ensure_sync.assert_not_called()


@pytest.mark.django_db
def test_trigger_pool_factual_closed_quarter_reconcile_window_creates_reconcile_checkpoint() -> None:
    from apps.intercompany_pools.factual_scheduler_runtime import (
        FACTUAL_RECONCILE_SYNC_ORIGIN_SYSTEM,
        PoolFactualScope,
        trigger_pool_factual_closed_quarter_reconcile_window,
    )
    from apps.intercompany_pools.factual_sync_runtime import build_factual_sales_report_sync_scope

    tenant = Tenant.objects.create(
        slug=f"factual-scheduler-reconcile-{uuid4().hex[:6]}",
        name="Factual Scheduler Reconcile",
    )
    pool = _create_pool(tenant=tenant, suffix="reconcile")
    database = _create_database(tenant=tenant, suffix="reconcile")
    read_checkpoint = PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        metadata={"frozen_at": "2026-03-31T23:59:59+00:00"},
    )
    fixed_now = datetime(2026, 4, 14, 10, 0, tzinfo=dt_timezone.utc)
    factual_scope = build_factual_sales_report_sync_scope(
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        organization_ids=("org-1",),
        account_codes=("62.01", "90.01"),
        movement_kinds=("credit", "debit"),
    )

    with patch(
        "apps.intercompany_pools.factual_scheduler_runtime.resolve_pool_factual_scope",
        return_value=PoolFactualScope(
            organization_ids=("org-1",),
            databases=(database,),
            quarter_end=date(2026, 3, 31),
            freeze_quarter=True,
        ),
    ), patch(
        "apps.intercompany_pools.factual_scheduler_runtime.resolve_pool_factual_sync_scope_for_database",
        return_value=factual_scope,
    ), patch(
        "apps.intercompany_pools.factual_scheduler_runtime.start_pool_factual_sync_workflow",
        side_effect=lambda **kwargs: SimpleNamespace(
            checkpoint=kwargs["checkpoint"],
            enqueue_success=True,
            enqueue_status="running",
        ),
    ) as start_workflow:
        summary = trigger_pool_factual_closed_quarter_reconcile_window(now=fixed_now)

    reconcile_checkpoint = PoolFactualSyncCheckpoint.objects.get(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.RECONCILE,
        quarter_start=date(2026, 1, 1),
    )

    assert summary["read_checkpoints_scanned"] == 1
    assert summary["reconcile_checkpoints_created"] == 1
    assert summary["reconcile_checkpoints_running"] == 1
    assert summary["quarter_cutoff_start"] == "2026-04-01"
    start_workflow.assert_called_once()
    kwargs = start_workflow.call_args.kwargs
    assert kwargs["checkpoint"].id == reconcile_checkpoint.id
    assert kwargs["database"] == database
    assert kwargs["organization_ids"] == ("org-1",)
    assert kwargs["account_codes"] == ("62.01", "90.01")
    assert kwargs["movement_kinds"] == ("credit", "debit")
    assert kwargs["origin_system"] == FACTUAL_RECONCILE_SYNC_ORIGIN_SYSTEM
    assert kwargs["activity"] == "cold"
    assert kwargs["freeze_quarter"] is True
    assert str(read_checkpoint.id) != str(reconcile_checkpoint.id)


@pytest.mark.django_db
def test_trigger_pool_factual_closed_quarter_reconcile_window_skips_inactive_pool_contexts() -> None:
    from apps.intercompany_pools.factual_scheduler_runtime import (
        PoolFactualScope,
        trigger_pool_factual_closed_quarter_reconcile_window,
    )
    from apps.intercompany_pools.factual_sync_runtime import build_factual_sales_report_sync_scope

    tenant = Tenant.objects.create(
        slug=f"factual-scheduler-inactive-reconcile-{uuid4().hex[:6]}",
        name="Factual Scheduler Inactive Reconcile",
    )
    pool = _create_pool(tenant=tenant, suffix="inactive-reconcile", is_active=False)
    database = _create_database(tenant=tenant, suffix="inactive-reconcile")
    PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        metadata={"frozen_at": "2026-03-31T23:59:59+00:00"},
    )
    fixed_now = datetime(2026, 4, 14, 10, 0, tzinfo=dt_timezone.utc)
    factual_scope = build_factual_sales_report_sync_scope(
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        organization_ids=("org-1",),
        account_codes=("62.01", "90.01"),
        movement_kinds=("credit", "debit"),
    )

    with patch(
        "apps.intercompany_pools.factual_scheduler_runtime.resolve_pool_factual_scope",
        return_value=PoolFactualScope(
            organization_ids=("org-1",),
            databases=(database,),
            quarter_end=date(2026, 3, 31),
            freeze_quarter=True,
        ),
    ), patch(
        "apps.intercompany_pools.factual_scheduler_runtime.resolve_pool_factual_sync_scope_for_database",
        return_value=factual_scope,
    ), patch(
        "apps.intercompany_pools.factual_scheduler_runtime.start_pool_factual_sync_workflow",
        side_effect=lambda **kwargs: SimpleNamespace(
            checkpoint=kwargs["checkpoint"],
            enqueue_success=True,
            enqueue_status="running",
        ),
    ) as start_workflow:
        summary = trigger_pool_factual_closed_quarter_reconcile_window(now=fixed_now)

    assert summary["read_checkpoints_scanned"] == 0
    assert summary["reconcile_checkpoints_touched"] == 0
    assert summary["reconcile_checkpoints_created"] == 0
    assert summary["reconcile_checkpoints_running"] == 0
    start_workflow.assert_not_called()
    assert not PoolFactualSyncCheckpoint.objects.filter(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.RECONCILE,
        quarter_start=date(2026, 1, 1),
    ).exists()
