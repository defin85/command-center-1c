from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.databases.models import Database
from apps.intercompany_pools.master_data_sync_apply import apply_master_data_outbox_to_ib
from apps.intercompany_pools.master_data_sync_outbox import build_master_data_mutation_payload_fingerprint
from apps.intercompany_pools.models import (
    PoolMasterDataBinding,
    PoolMasterDataEntityType,
    PoolMasterDataSyncOutbox,
    PoolMasterDataSyncOutboxStatus,
    PoolMasterParty,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"sync-apply-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


def _create_binding(*, tenant: Tenant, database: Database, fingerprint: str) -> PoolMasterDataBinding:
    return PoolMasterDataBinding.objects.create(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-001",
        database=database,
        ib_ref_key="ref-item-001",
        sync_status="resolved",
        fingerprint=fingerprint,
        metadata={},
    )


def _create_outbox(
    *,
    tenant: Tenant,
    database: Database,
    payload_fingerprint: str,
    mutation_kind: str = "binding_upsert",
) -> PoolMasterDataSyncOutbox:
    return PoolMasterDataSyncOutbox.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        status=PoolMasterDataSyncOutboxStatus.PENDING,
        dedupe_key=f"dedupe-{uuid4().hex[:8]}",
        origin_system="cc",
        origin_event_id=f"evt-{uuid4().hex[:8]}",
        payload={
            "mutation_kind": mutation_kind,
            "canonical_id": "item-001",
            "payload": {
                "canonical_id": "item-001",
                "ib_ref_key": "ref-item-001",
            },
            "payload_fingerprint": payload_fingerprint,
        },
        available_at=timezone.now() - timedelta(seconds=1),
    )


@pytest.mark.django_db
def test_apply_outbox_is_idempotent_when_binding_fingerprint_matches() -> None:
    tenant = Tenant.objects.create(slug=f"sync-apply-idem-{uuid4().hex[:6]}", name="Sync Apply Idem")
    database = _create_database(tenant=tenant, suffix="idem")
    payload_fingerprint = build_master_data_mutation_payload_fingerprint(
        payload={"canonical_id": "item-001", "ib_ref_key": "ref-item-001"}
    )
    binding = _create_binding(tenant=tenant, database=database, fingerprint=payload_fingerprint)
    outbox = _create_outbox(tenant=tenant, database=database, payload_fingerprint=payload_fingerprint)

    called = {"count": 0}

    def _ib_apply(_outbox):
        called["count"] += 1
        return {"status": "ok"}

    result = apply_master_data_outbox_to_ib(outbox=outbox, ib_apply=_ib_apply)

    assert result["idempotent"] is True
    assert result["applied"] is False
    assert called["count"] == 0
    binding.refresh_from_db()
    assert binding.last_synced_at is not None
    assert binding.metadata["sync_audit"][-1]["event"] == "idempotent_skip"


@pytest.mark.django_db
def test_apply_outbox_updates_binding_and_sanitizes_audit_metadata() -> None:
    tenant = Tenant.objects.create(slug=f"sync-apply-update-{uuid4().hex[:6]}", name="Sync Apply Update")
    database = _create_database(tenant=tenant, suffix="update")
    binding = _create_binding(tenant=tenant, database=database, fingerprint="old-fingerprint")
    payload_fingerprint = build_master_data_mutation_payload_fingerprint(
        payload={"canonical_id": "item-001", "ib_ref_key": "ref-item-001"}
    )
    outbox = _create_outbox(tenant=tenant, database=database, payload_fingerprint=payload_fingerprint)

    result = apply_master_data_outbox_to_ib(
        outbox=outbox,
        ib_apply=lambda _outbox: {
            "status": "ok",
            "password": "secret",
            "token": "token-value",
            "nested": {"secret": "nested-secret", "value": "safe"},
        },
    )

    assert result["applied"] is True
    assert result["idempotent"] is False
    assert result["binding_updated"] is True
    binding.refresh_from_db()
    assert binding.fingerprint == payload_fingerprint
    audit_entry = binding.metadata["sync_audit"][-1]
    assert audit_entry["event"] == "applied"
    assert audit_entry["transport_result"]["password"] == "***"
    assert audit_entry["transport_result"]["token"] == "***"
    assert audit_entry["transport_result"]["nested"]["secret"] == "***"
    assert audit_entry["transport_result"]["nested"]["value"] == "safe"


@pytest.mark.django_db
def test_apply_outbox_materializes_party_binding_and_metadata_from_transport_result() -> None:
    tenant = Tenant.objects.create(slug=f"sync-apply-party-{uuid4().hex[:6]}", name="Sync Apply Party")
    database = _create_database(tenant=tenant, suffix="party")
    party = PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id="party-001",
        name="Party 001",
        full_name="Party 001 LLC",
        inn="7701234567",
        kpp="770101001",
        is_counterparty=True,
        is_our_organization=False,
        metadata={},
    )
    payload = {
        "canonical_id": "party-001",
        "name": "Party 001",
        "full_name": "Party 001 LLC",
        "inn": "7701234567",
        "kpp": "770101001",
        "is_counterparty": True,
        "is_our_organization": False,
        "metadata": {},
    }
    payload_fingerprint = build_master_data_mutation_payload_fingerprint(payload=payload)
    outbox = PoolMasterDataSyncOutbox.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.PARTY,
        status=PoolMasterDataSyncOutboxStatus.PENDING,
        dedupe_key=f"dedupe-{uuid4().hex[:8]}",
        origin_system="cc",
        origin_event_id=f"evt-{uuid4().hex[:8]}",
        payload={
            "mutation_kind": "party_upsert",
            "canonical_id": "party-001",
            "payload": payload,
            "payload_fingerprint": payload_fingerprint,
        },
        available_at=timezone.now() - timedelta(seconds=1),
    )

    result = apply_master_data_outbox_to_ib(
        outbox=outbox,
        ib_apply=lambda _outbox: {
            "status": "ok",
            "ib_ref_key": "ref-party-001",
            "ib_catalog_kind": "counterparty",
        },
    )

    assert result["applied"] is True
    assert result["idempotent"] is False
    assert result["binding_updated"] is True

    binding = PoolMasterDataBinding.objects.get(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.PARTY,
        canonical_id="party-001",
        ib_catalog_kind="counterparty",
    )
    assert binding.ib_ref_key == "ref-party-001"

    party.refresh_from_db()
    assert party.metadata["ib_ref_keys"][str(database.id)]["counterparty"] == "ref-party-001"
