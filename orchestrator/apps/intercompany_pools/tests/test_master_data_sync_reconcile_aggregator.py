from __future__ import annotations

from datetime import timedelta, timezone as dt_timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.databases.models import Database
from apps.intercompany_pools.master_data_sync_reconcile_aggregator import (
    aggregate_pool_master_data_reconcile_window,
)
from apps.intercompany_pools.master_data_sync_reconcile_scheduler import (
    MasterDataSyncReconcileFanOutResult,
)
from apps.intercompany_pools.models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncDirection,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncJobStatus,
    PoolMasterDataSyncPolicy,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"sync-reconcile-aggregator-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


def _to_rfc3339_utc(dt_value) -> str:
    return dt_value.astimezone(dt_timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@pytest.mark.django_db
def test_reconcile_fanin_aggregator_marks_window_completed_when_all_scopes_finish_before_deadline() -> None:
    now = timezone.now().astimezone(dt_timezone.utc).replace(microsecond=0)
    deadline = now + timedelta(seconds=120)
    tenant = Tenant.objects.create(slug=f"sync-reconcile-agg-ok-{uuid4().hex[:6]}", name="Sync Reconcile Agg OK")
    db1 = _create_database(tenant=tenant, suffix="ok-1")
    db2 = _create_database(tenant=tenant, suffix="ok-2")
    window_id = f"reconcile-window-{uuid4()}"

    PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=db1,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
        direction=PoolMasterDataSyncDirection.BIDIRECTIONAL,
        status=PoolMasterDataSyncJobStatus.SUCCEEDED,
        finished_at=now + timedelta(seconds=5),
        metadata={"last_trigger": {"reconcile_window_id": window_id}},
    )
    PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=db2,
        entity_type=PoolMasterDataEntityType.PARTY,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
        direction=PoolMasterDataSyncDirection.BIDIRECTIONAL,
        status=PoolMasterDataSyncJobStatus.FAILED,
        finished_at=now + timedelta(seconds=10),
        metadata={"last_trigger": {"reconcile_window_id": window_id}},
    )

    fanout_result = MasterDataSyncReconcileFanOutResult(
        reconcile_window_id=window_id,
        started_at=_to_rfc3339_utc(now),
        deadline_at=_to_rfc3339_utc(deadline),
        total_scopes=2,
        scheduled=2,
        skipped=0,
        failed=0,
        scope_results=(
            {
                "tenant_id": str(tenant.id),
                "database_id": str(db1.id),
                "entity_type": PoolMasterDataEntityType.ITEM,
                "status": "scheduled",
            },
            {
                "tenant_id": str(tenant.id),
                "database_id": str(db2.id),
                "entity_type": PoolMasterDataEntityType.PARTY,
                "status": "scheduled",
            },
        ),
    )

    result = aggregate_pool_master_data_reconcile_window(
        fanout_result=fanout_result,
        now_fn=lambda: now + timedelta(seconds=20),
        sleep_fn=lambda _delay: None,
    )

    assert result.outcome == "completed"
    assert result.deadline_state == "met"
    assert result.on_time_completed == 2
    assert result.late_completed == 0
    assert result.pending == 0
    assert result.coverage_ratio == 1.0


@pytest.mark.django_db
def test_reconcile_fanin_aggregator_returns_partial_when_deadline_is_missed() -> None:
    now = timezone.now().astimezone(dt_timezone.utc).replace(microsecond=0)
    deadline = now - timedelta(seconds=10)
    tenant = Tenant.objects.create(slug=f"sync-reconcile-agg-partial-{uuid4().hex[:6]}", name="Sync Reconcile Agg Partial")
    db1 = _create_database(tenant=tenant, suffix="partial-1")
    db2 = _create_database(tenant=tenant, suffix="partial-2")
    window_id = f"reconcile-window-{uuid4()}"

    PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=db1,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
        direction=PoolMasterDataSyncDirection.BIDIRECTIONAL,
        status=PoolMasterDataSyncJobStatus.RUNNING,
        metadata={"last_trigger": {"reconcile_window_id": window_id}},
    )
    PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=db2,
        entity_type=PoolMasterDataEntityType.PARTY,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
        direction=PoolMasterDataSyncDirection.BIDIRECTIONAL,
        status=PoolMasterDataSyncJobStatus.SUCCEEDED,
        finished_at=now,
        metadata={"last_trigger": {"reconcile_window_id": window_id}},
    )

    fanout_result = MasterDataSyncReconcileFanOutResult(
        reconcile_window_id=window_id,
        started_at=_to_rfc3339_utc(now - timedelta(seconds=120)),
        deadline_at=_to_rfc3339_utc(deadline),
        total_scopes=2,
        scheduled=2,
        skipped=0,
        failed=0,
        scope_results=(
            {
                "tenant_id": str(tenant.id),
                "database_id": str(db1.id),
                "entity_type": PoolMasterDataEntityType.ITEM,
                "status": "scheduled",
            },
            {
                "tenant_id": str(tenant.id),
                "database_id": str(db2.id),
                "entity_type": PoolMasterDataEntityType.PARTY,
                "status": "scheduled",
            },
        ),
    )

    result = aggregate_pool_master_data_reconcile_window(
        fanout_result=fanout_result,
        now_fn=lambda: now,
        sleep_fn=lambda _delay: None,
    )

    assert result.outcome == "partial"
    assert result.deadline_state == "missed"
    assert result.on_time_completed == 0
    assert result.late_completed == 1
    assert result.pending == 1
    assert result.coverage_ratio == 0.0


def test_reconcile_fanin_aggregator_records_reconcile_window_metrics() -> None:
    now = timezone.now().astimezone(dt_timezone.utc).replace(microsecond=0)
    fanout_result = MasterDataSyncReconcileFanOutResult(
        reconcile_window_id=f"reconcile-window-{uuid4()}",
        started_at=_to_rfc3339_utc(now - timedelta(seconds=30)),
        deadline_at=_to_rfc3339_utc(now + timedelta(seconds=120)),
        total_scopes=0,
        scheduled=0,
        skipped=0,
        failed=0,
        scope_results=(),
    )

    with patch(
        "apps.intercompany_pools.master_data_sync_reconcile_aggregator.record_pool_master_data_sync_reconcile_window_metrics"
    ) as metrics_mock:
        result = aggregate_pool_master_data_reconcile_window(
            fanout_result=fanout_result,
            now_fn=lambda: now,
            sleep_fn=lambda _delay: None,
            jobs_loader=lambda _window_id: [],
        )

    assert result.outcome == "completed"
    metrics_mock.assert_called_once()
    metrics_kwargs = metrics_mock.call_args.kwargs
    assert metrics_kwargs["outcome"] == "completed"
    assert metrics_kwargs["deadline_state"] == "met"
    assert metrics_kwargs["coverage_ratio"] == 1.0
    assert float(metrics_kwargs["latency_seconds"]) >= 0.0
