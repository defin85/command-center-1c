from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.master_data_sync_execution import PoolMasterDataSyncTriggerResult
from apps.intercompany_pools.master_data_sync_reconcile_scheduler import (
    RECONCILE_BACKPRESSURE_EXHAUSTED,
    _default_queue_depth_provider,
    schedule_pool_master_data_reconcile_probe_jobs,
)
from apps.intercompany_pools.models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncPolicy,
    PoolMasterDataSyncScope,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"sync-reconcile-scheduler-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


@pytest.mark.django_db
def test_reconcile_fanout_scheduler_triggers_each_scope_with_window_metadata() -> None:
    tenant = Tenant.objects.create(slug=f"sync-reconcile-scheduler-{uuid4().hex[:6]}", name="Sync Reconcile Scheduler")
    db1 = _create_database(tenant=tenant, suffix="db1")
    db2 = _create_database(tenant=tenant, suffix="db2")
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=db1,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=db2,
        entity_type=PoolMasterDataEntityType.PARTY,
        policy=PoolMasterDataSyncPolicy.CC_MASTER,
    )

    captured_calls: list[dict[str, str]] = []

    def _trigger(**kwargs) -> PoolMasterDataSyncTriggerResult:
        captured_calls.append({key: str(value or "") for key, value in kwargs.items()})
        return PoolMasterDataSyncTriggerResult(
            sync_job=SimpleNamespace(id=f"job-{len(captured_calls)}"),
            created_job=True,
            started_workflow=True,
            skipped=False,
            skip_reason=None,
            policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
            policy_source="database_scope",
            start_result=None,
        )

    result = schedule_pool_master_data_reconcile_probe_jobs(
        tenant_id=str(tenant.id),
        batch_size=10,
        trigger_reconcile=_trigger,
    )

    assert result.total_scopes == 2
    assert result.scheduled == 2
    assert result.skipped == 0
    assert result.failed == 0
    assert result.deadline_at.endswith("Z")
    assert len(captured_calls) == 2
    assert all(call["reconcile_window_id"] == result.reconcile_window_id for call in captured_calls)
    assert all(call["reconcile_window_deadline_at"] == result.deadline_at for call in captured_calls)


@pytest.mark.django_db
def test_reconcile_fanout_scheduler_reports_skipped_and_failed_scopes() -> None:
    tenant = Tenant.objects.create(slug=f"sync-reconcile-partial-{uuid4().hex[:6]}", name="Sync Reconcile Partial")
    db = _create_database(tenant=tenant, suffix="partial")
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=db,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )

    def _trigger_skipped(**_kwargs) -> PoolMasterDataSyncTriggerResult:
        return PoolMasterDataSyncTriggerResult(
            sync_job=None,
            created_job=False,
            started_workflow=False,
            skipped=True,
            skip_reason="MASTER_DATA_SYNC_DISABLED",
            policy=None,
            policy_source=None,
            start_result=None,
        )

    skipped_result = schedule_pool_master_data_reconcile_probe_jobs(
        tenant_id=str(tenant.id),
        trigger_reconcile=_trigger_skipped,
    )
    assert skipped_result.total_scopes == 1
    assert skipped_result.scheduled == 0
    assert skipped_result.skipped == 1
    assert skipped_result.failed == 0

    def _trigger_failed(**_kwargs):
        raise ValueError("boom")

    failed_result = schedule_pool_master_data_reconcile_probe_jobs(
        tenant_id=str(tenant.id),
        trigger_reconcile=_trigger_failed,
    )
    assert failed_result.total_scopes == 1
    assert failed_result.scheduled == 0
    assert failed_result.skipped == 0
    assert failed_result.failed == 1
    assert failed_result.scope_results[0]["status"] == "failed"


@pytest.mark.django_db
def test_reconcile_fanout_scheduler_applies_backpressure_retries_before_success() -> None:
    tenant = Tenant.objects.create(slug=f"sync-reconcile-backpressure-{uuid4().hex[:6]}", name="Sync Reconcile Backpressure")
    db = _create_database(tenant=tenant, suffix="backpressure")
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=db,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )

    queue_depth_samples = [500, 300, 10]
    queue_depth_calls = {"count": 0}
    captured_delays: list[float] = []
    trigger_calls = {"count": 0}

    def _queue_depth() -> int:
        idx = min(queue_depth_calls["count"], len(queue_depth_samples) - 1)
        queue_depth_calls["count"] += 1
        return queue_depth_samples[idx]

    def _sleep(delay: float) -> None:
        captured_delays.append(delay)

    def _trigger(**_kwargs) -> PoolMasterDataSyncTriggerResult:
        trigger_calls["count"] += 1
        return PoolMasterDataSyncTriggerResult(
            sync_job=SimpleNamespace(id="job-backpressure-ok"),
            created_job=True,
            started_workflow=True,
            skipped=False,
            skip_reason=None,
            policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
            policy_source="database_scope",
            start_result=None,
        )

    result = schedule_pool_master_data_reconcile_probe_jobs(
        tenant_id=str(tenant.id),
        trigger_reconcile=_trigger,
        queue_depth_provider=_queue_depth,
        backpressure_queue_depth_limit=100,
        max_enqueue_attempts=4,
        retry_base_backoff_seconds=0.01,
        retry_max_backoff_seconds=0.05,
        sleep_fn=_sleep,
    )

    assert result.total_scopes == 1
    assert result.scheduled == 1
    assert result.skipped == 0
    assert result.failed == 0
    assert trigger_calls["count"] == 1
    assert queue_depth_calls["count"] == 3
    assert len(captured_delays) == 2
    assert result.scope_results[0]["status"] == "scheduled"
    assert result.scope_results[0]["attempts"] == "3"
    assert result.scope_results[0]["retry_attempts"] == "2"
    assert result.scope_results[0]["backpressure_retries"] == "2"


@pytest.mark.django_db
def test_reconcile_fanout_scheduler_fails_when_backpressure_retry_budget_exhausted() -> None:
    tenant = Tenant.objects.create(slug=f"sync-reconcile-overload-{uuid4().hex[:6]}", name="Sync Reconcile Overload")
    db = _create_database(tenant=tenant, suffix="overload")
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=db,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )

    trigger_calls = {"count": 0}

    def _trigger(**_kwargs) -> PoolMasterDataSyncTriggerResult:
        trigger_calls["count"] += 1
        return PoolMasterDataSyncTriggerResult(
            sync_job=None,
            created_job=False,
            started_workflow=False,
            skipped=True,
            skip_reason="SHOULD_NOT_BE_CALLED",
            policy=None,
            policy_source=None,
            start_result=None,
        )

    result = schedule_pool_master_data_reconcile_probe_jobs(
        tenant_id=str(tenant.id),
        trigger_reconcile=_trigger,
        queue_depth_provider=lambda: 999,
        backpressure_queue_depth_limit=100,
        max_enqueue_attempts=2,
        retry_base_backoff_seconds=0.01,
        retry_max_backoff_seconds=0.02,
        sleep_fn=lambda _delay: None,
    )

    assert result.total_scopes == 1
    assert result.scheduled == 0
    assert result.skipped == 0
    assert result.failed == 1
    assert trigger_calls["count"] == 0
    assert result.scope_results[0]["status"] == "failed"
    assert result.scope_results[0]["error_code"] == RECONCILE_BACKPRESSURE_EXHAUSTED
    assert result.scope_results[0]["attempts"] == "2"
    assert result.scope_results[0]["retry_attempts"] == "1"


@pytest.mark.django_db
def test_reconcile_fanout_scheduler_retries_retryable_enqueue_failure() -> None:
    tenant = Tenant.objects.create(slug=f"sync-reconcile-retry-{uuid4().hex[:6]}", name="Sync Reconcile Retry")
    db = _create_database(tenant=tenant, suffix="retry")
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=db,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )

    trigger_calls = {"count": 0}

    def _trigger(**_kwargs) -> PoolMasterDataSyncTriggerResult:
        trigger_calls["count"] += 1
        if trigger_calls["count"] == 1:
            return PoolMasterDataSyncTriggerResult(
                sync_job=SimpleNamespace(
                    id="job-retry",
                    last_error_code="ENQUEUE_FAILED",
                    last_error="redis unavailable",
                ),
                created_job=True,
                started_workflow=False,
                skipped=False,
                skip_reason=None,
                policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
                policy_source="database_scope",
                start_result=SimpleNamespace(enqueue_error="redis unavailable"),
            )
        return PoolMasterDataSyncTriggerResult(
            sync_job=SimpleNamespace(id="job-retry"),
            created_job=True,
            started_workflow=True,
            skipped=False,
            skip_reason=None,
            policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
            policy_source="database_scope",
            start_result=None,
        )

    delays: list[float] = []
    result = schedule_pool_master_data_reconcile_probe_jobs(
        tenant_id=str(tenant.id),
        trigger_reconcile=_trigger,
        max_enqueue_attempts=3,
        retry_base_backoff_seconds=0.01,
        retry_max_backoff_seconds=0.05,
        sleep_fn=lambda delay: delays.append(delay),
    )

    assert result.total_scopes == 1
    assert result.scheduled == 1
    assert result.failed == 0
    assert trigger_calls["count"] == 2
    assert len(delays) == 1
    assert result.scope_results[0]["status"] == "scheduled"
    assert result.scope_results[0]["attempts"] == "2"
    assert result.scope_results[0]["retry_attempts"] == "1"


def test_default_queue_depth_provider_reads_workflow_stream_depth() -> None:
    with patch(
        "apps.intercompany_pools.master_data_sync_reconcile_scheduler.OperationsService.get_queue_depth",
        return_value=42,
    ) as get_queue_depth_mock:
        depth = _default_queue_depth_provider()

    assert depth == 42
    get_queue_depth_mock.assert_called_once_with(queue_name="commands:worker:workflows")
