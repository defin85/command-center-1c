from __future__ import annotations

from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.master_data_sync_outbox import (
    enqueue_master_data_sync_outbox_intent,
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
        name=f"sync-outbox-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


@pytest.mark.django_db
def test_enqueue_sync_outbox_intent_persists_scope_payload_and_status() -> None:
    tenant = Tenant.objects.create(slug=f"sync-outbox-{uuid4().hex[:6]}", name="Sync Outbox")
    database = _create_database(tenant=tenant, suffix="create")

    row = enqueue_master_data_sync_outbox_intent(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-001",
        mutation_kind="item_upsert",
        payload={"name": "Item 001", "sku": "SKU-001"},
        origin_system="cc",
        origin_event_id="evt-001",
    )

    assert row.status == PoolMasterDataSyncOutboxStatus.PENDING
    assert row.origin_system == "cc"
    assert row.origin_event_id == "evt-001"
    assert row.payload["mutation_kind"] == "item_upsert"
    assert row.payload["canonical_id"] == "item-001"
    assert row.payload["payload"]["sku"] == "SKU-001"
    assert row.dedupe_key


@pytest.mark.django_db
def test_enqueue_sync_outbox_intent_is_idempotent_for_same_scope_payload_and_origin() -> None:
    tenant = Tenant.objects.create(slug=f"sync-outbox-idem-{uuid4().hex[:6]}", name="Sync Outbox Idem")
    database = _create_database(tenant=tenant, suffix="idem")

    first = enqueue_master_data_sync_outbox_intent(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=PoolMasterDataEntityType.PARTY,
        canonical_id="party-001",
        mutation_kind="party_upsert",
        payload={"name": "Party 001"},
        origin_system="cc",
        origin_event_id="evt-001",
    )
    second = enqueue_master_data_sync_outbox_intent(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=PoolMasterDataEntityType.PARTY,
        canonical_id="party-001",
        mutation_kind="party_upsert",
        payload={"name": "Party 001"},
        origin_system="cc",
        origin_event_id="evt-001",
    )

    assert first.id == second.id
    assert (
        PoolMasterDataSyncOutbox.objects.filter(
            tenant=tenant,
            database=database,
            entity_type=PoolMasterDataEntityType.PARTY,
        ).count()
        == 1
    )
