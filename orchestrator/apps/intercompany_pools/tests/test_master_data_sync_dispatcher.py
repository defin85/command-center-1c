from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.databases.models import Database, InfobaseUserMapping
from apps.intercompany_pools.master_data_sync_dispatcher import (
    MasterDataSyncTransportError,
    dispatch_pending_master_data_sync_outbox,
)
from apps.intercompany_pools.models import (
    PoolMasterDataBinding,
    PoolMasterDataEntityType,
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncConflictStatus,
    PoolMasterDataSyncOutbox,
    PoolMasterDataSyncOutboxStatus,
    PoolMasterItem,
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


def _create_service_mapping(*, database: Database, username: str = "svc-user", password: str = "svc-pass") -> None:
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username=username,
        ib_password=password,
        is_service=True,
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
def test_dispatcher_uses_live_odata_item_transport_by_default_and_materializes_binding() -> None:
    tenant = Tenant.objects.create(slug=f"sync-dispatch-live-{uuid4().hex[:6]}", name="Sync Dispatch Live")
    database = _create_database(tenant=tenant, suffix="live")
    _create_service_mapping(database=database)
    item = PoolMasterItem.objects.create(
        tenant=tenant,
        canonical_id="item-live-001",
        name="Live Item",
        sku="SKU-LIVE-001",
        metadata={
            "code": "00-100001",
            "item_kind_ref": "kind-live-001",
            "unit_ref": "unit-live-001",
        },
    )
    row = PoolMasterDataSyncOutbox.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        status=PoolMasterDataSyncOutboxStatus.PENDING,
        dedupe_key=f"dedupe-live-{uuid4().hex[:8]}",
        origin_system="manual_sync_launch",
        origin_event_id=f"evt-live-{uuid4().hex[:8]}",
        payload={
            "mutation_kind": "item_upsert",
            "canonical_id": "item-live-001",
            "payload": {
                "canonical_id": "item-live-001",
                "name": "Live Item",
                "sku": "SKU-LIVE-001",
                "metadata": dict(item.metadata),
            },
            "payload_fingerprint": "fp-live-001",
        },
        available_at=timezone.now() - timedelta(seconds=1),
        attempt_count=0,
    )

    client_inits: list[dict[str, object]] = []
    create_calls: list[dict[str, object]] = []

    class _FakeODataClient:
        def __init__(self, **kwargs):
            client_inits.append(dict(kwargs))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_entities(self, entity_name, filter_query=None, select_fields=None, top=None, skip=None):
            _ = (filter_query, select_fields, top, skip)
            return []

        def create_entity(self, entity_name, entity_data):
            create_calls.append({"entity_name": entity_name, "entity_data": dict(entity_data)})
            return {"Ref_Key": "target-live-item-001"}

        def update_entity(self, entity_name, entity_id, entity_data):
            raise AssertionError(f"unexpected update for {entity_name} {entity_id} {entity_data}")

    with patch(
        "apps.intercompany_pools.master_data_sync_live_odata_transport.ODataClient",
        _FakeODataClient,
    ):
        result = dispatch_pending_master_data_sync_outbox(batch_size=10)

    assert result.claimed == 1
    assert result.sent == 1
    assert result.failed == 0
    refreshed_row = PoolMasterDataSyncOutbox.objects.get(id=row.id)
    assert refreshed_row.status == PoolMasterDataSyncOutboxStatus.SENT
    binding = PoolMasterDataBinding.objects.get(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-live-001",
    )
    assert binding.ib_ref_key == "target-live-item-001"
    item.refresh_from_db()
    assert item.metadata["ib_ref_keys"][str(database.id)] == "target-live-item-001"
    assert create_calls == [
        {
            "entity_name": "Catalog_Номенклатура",
            "entity_data": {
                "Description": "Live Item",
                "НаименованиеПолное": "Live Item",
                "ВидНоменклатуры_Key": "kind-live-001",
                "Parent_Key": "00000000-0000-0000-0000-000000000000",
                "IsFolder": False,
                "DeletionMark": False,
                "Услуга": False,
                "Code": "00-100001",
                "Артикул": "SKU-LIVE-001",
                "ЕдиницаИзмерения_Key": "unit-live-001",
            },
        }
    ]
    assert client_inits
    assert client_inits[0]["verify_tls"] is True


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
