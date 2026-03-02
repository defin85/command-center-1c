from __future__ import annotations

from datetime import timedelta
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
