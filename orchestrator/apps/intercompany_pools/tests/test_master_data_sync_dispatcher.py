from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.databases.models import Database
from apps.intercompany_pools.master_data_sync_dispatcher import (
    MasterDataSyncTransportError,
    dispatch_pending_master_data_sync_outbox,
)
from apps.intercompany_pools.models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncConflictStatus,
    PoolMasterDataSyncOutbox,
    PoolMasterDataSyncOutboxStatus,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"sync-dispatch-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


def _create_outbox_row(
    *,
    tenant: Tenant,
    database: Database,
    dedupe_key: str,
    status: str = PoolMasterDataSyncOutboxStatus.PENDING,
    available_at=None,
    attempt_count: int = 0,
) -> PoolMasterDataSyncOutbox:
    return PoolMasterDataSyncOutbox.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        status=status,
        dedupe_key=dedupe_key,
        origin_system="cc",
        origin_event_id=f"evt-{dedupe_key}",
        payload={
            "mutation_kind": "item_upsert",
            "canonical_id": "item-001",
            "payload": {"name": "Item 001"},
            "payload_fingerprint": "fp",
        },
        available_at=available_at or timezone.now() - timedelta(seconds=1),
        attempt_count=attempt_count,
    )


@pytest.mark.django_db
def test_dispatcher_marks_pending_row_sent_on_transport_success() -> None:
    tenant = Tenant.objects.create(slug=f"sync-dispatch-ok-{uuid4().hex[:6]}", name="Sync Dispatch OK")
    database = _create_database(tenant=tenant, suffix="ok")
    row = _create_outbox_row(tenant=tenant, database=database, dedupe_key="dedupe-ok")

    result = dispatch_pending_master_data_sync_outbox(
        transport_apply=lambda outbox: {"transport_ref": f"ib:{outbox.id}"},
        batch_size=10,
    )

    assert result.claimed == 1
    assert result.sent == 1
    assert result.failed == 0

    refreshed = PoolMasterDataSyncOutbox.objects.get(id=row.id)
    assert refreshed.status == PoolMasterDataSyncOutboxStatus.SENT
    assert refreshed.dispatched_at is not None
    assert refreshed.attempt_count == 1
    assert refreshed.last_error_code == ""


@pytest.mark.django_db
def test_dispatcher_marks_row_failed_and_sets_backoff_on_transport_error() -> None:
    tenant = Tenant.objects.create(slug=f"sync-dispatch-fail-{uuid4().hex[:6]}", name="Sync Dispatch Fail")
    database = _create_database(tenant=tenant, suffix="fail")
    row = _create_outbox_row(tenant=tenant, database=database, dedupe_key="dedupe-fail")
    previous_available_at = row.available_at

    def _raise_transport_error(_outbox):
        raise MasterDataSyncTransportError(code="IB_HTTP_500", detail="ib endpoint failed")

    result = dispatch_pending_master_data_sync_outbox(
        transport_apply=_raise_transport_error,
        batch_size=10,
    )

    assert result.claimed == 1
    assert result.sent == 0
    assert result.failed == 1

    refreshed = PoolMasterDataSyncOutbox.objects.get(id=row.id)
    assert refreshed.status == PoolMasterDataSyncOutboxStatus.FAILED
    assert refreshed.last_error_code == "IB_HTTP_500"
    assert "ib endpoint failed" in refreshed.last_error
    assert refreshed.available_at > previous_available_at
    assert refreshed.attempt_count == 1


@pytest.mark.django_db
def test_dispatcher_redacts_sensitive_values_in_last_error() -> None:
    tenant = Tenant.objects.create(slug=f"sync-dispatch-redact-{uuid4().hex[:6]}", name="Sync Dispatch Redact")
    database = _create_database(tenant=tenant, suffix="redact")
    row = _create_outbox_row(tenant=tenant, database=database, dedupe_key="dedupe-redact")

    def _raise_transport_error(_outbox):
        raise MasterDataSyncTransportError(
            code="IB_HTTP_401",
            detail=(
                "auth failed password=super-secret "
                "checkpoint_token=cp-safe "
                "url=http://user:pwd@localhost/odata"
            ),
        )

    result = dispatch_pending_master_data_sync_outbox(
        transport_apply=_raise_transport_error,
        batch_size=10,
    )

    assert result.failed == 1
    refreshed = PoolMasterDataSyncOutbox.objects.get(id=row.id)
    assert refreshed.status == PoolMasterDataSyncOutboxStatus.FAILED
    assert refreshed.last_error_code == "IB_HTTP_401"
    assert "password=***" in refreshed.last_error
    assert "checkpoint_token=cp-safe" in refreshed.last_error
    assert "http://***:***@localhost/odata" in refreshed.last_error
    assert "super-secret" not in refreshed.last_error


@pytest.mark.django_db
def test_dispatcher_respects_batch_size_and_availability_window() -> None:
    tenant = Tenant.objects.create(slug=f"sync-dispatch-batch-{uuid4().hex[:6]}", name="Sync Dispatch Batch")
    database = _create_database(tenant=tenant, suffix="batch")

    row_eligible = _create_outbox_row(tenant=tenant, database=database, dedupe_key="dedupe-1")
    _create_outbox_row(tenant=tenant, database=database, dedupe_key="dedupe-2")
    row_future = _create_outbox_row(
        tenant=tenant,
        database=database,
        dedupe_key="dedupe-future",
        available_at=timezone.now() + timedelta(hours=1),
    )

    result = dispatch_pending_master_data_sync_outbox(
        transport_apply=lambda _outbox: {},
        batch_size=1,
    )

    assert result.claimed == 1
    assert result.sent == 1
    assert result.failed == 0

    refreshed_first = PoolMasterDataSyncOutbox.objects.get(id=row_eligible.id)
    refreshed_future = PoolMasterDataSyncOutbox.objects.get(id=row_future.id)
    assert refreshed_first.status == PoolMasterDataSyncOutboxStatus.SENT
    assert refreshed_future.status == PoolMasterDataSyncOutboxStatus.PENDING


@pytest.mark.django_db
def test_dispatcher_records_master_data_sync_sli_metrics() -> None:
    tenant = Tenant.objects.create(slug=f"sync-dispatch-sli-{uuid4().hex[:6]}", name="Sync Dispatch SLI")
    database = _create_database(tenant=tenant, suffix="sli")
    now = timezone.now()

    _create_outbox_row(
        tenant=tenant,
        database=database,
        dedupe_key="dedupe-claimed",
        status=PoolMasterDataSyncOutboxStatus.PENDING,
        available_at=now - timedelta(minutes=10),
        attempt_count=0,
    )
    _create_outbox_row(
        tenant=tenant,
        database=database,
        dedupe_key="dedupe-saturated",
        status=PoolMasterDataSyncOutboxStatus.FAILED,
        available_at=now - timedelta(minutes=5),
        attempt_count=5,
    )
    PoolMasterDataSyncConflict.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        status=PoolMasterDataSyncConflictStatus.PENDING,
        conflict_code="POLICY_VIOLATION",
        canonical_id="item-001",
    )
    PoolMasterDataSyncConflict.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        status=PoolMasterDataSyncConflictStatus.RETRYING,
        conflict_code="POLICY_VIOLATION",
        canonical_id="item-002",
    )

    with (
        patch(
            "apps.intercompany_pools.master_data_sync_dispatcher.set_pool_master_data_sync_backlog_metrics"
        ) as set_backlog,
        patch(
            "apps.intercompany_pools.master_data_sync_dispatcher.set_pool_master_data_sync_conflict_metrics"
        ) as set_conflicts,
    ):
        result = dispatch_pending_master_data_sync_outbox(
            transport_apply=lambda _outbox: {},
            batch_size=1,
        )

    assert result.claimed == 1
    assert result.sent == 1
    assert result.failed == 0

    set_backlog.assert_called_once()
    backlog_kwargs = set_backlog.call_args.kwargs
    assert float(backlog_kwargs["lag_seconds"]) >= 0.0
    assert backlog_kwargs["pending_total"] == 0
    assert backlog_kwargs["retry_total"] == 1
    assert backlog_kwargs["saturated_total"] == 1

    set_conflicts.assert_called_once_with(pending_total=1, retrying_total=1)
