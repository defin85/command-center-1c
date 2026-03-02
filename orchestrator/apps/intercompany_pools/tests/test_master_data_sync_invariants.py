from __future__ import annotations

import pytest

from apps.intercompany_pools.master_data_sync_invariants import (
    MasterDataSyncInvariantError,
    build_inbound_dedupe_fingerprint,
    build_outbound_dedupe_key,
    require_origin_identifiers,
)
from apps.intercompany_pools.models import PoolMasterDataEntityType


def test_outbound_dedupe_key_is_deterministic_for_same_input() -> None:
    left = build_outbound_dedupe_key(
        tenant_id="tenant-1",
        database_id="db-1",
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-001",
        mutation_kind="upsert",
        payload_fingerprint="fp-1",
        origin_event_id="evt-1",
    )
    right = build_outbound_dedupe_key(
        tenant_id="tenant-1",
        database_id="db-1",
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-001",
        mutation_kind="upsert",
        payload_fingerprint="fp-1",
        origin_event_id="evt-1",
    )

    assert left == right
    assert len(left) == 64


def test_outbound_dedupe_key_changes_when_scope_changes() -> None:
    base = build_outbound_dedupe_key(
        tenant_id="tenant-1",
        database_id="db-1",
        entity_type=PoolMasterDataEntityType.CONTRACT,
        canonical_id="contract-001",
        mutation_kind="upsert",
        payload_fingerprint="fp-1",
        origin_event_id="evt-1",
    )
    changed = build_outbound_dedupe_key(
        tenant_id="tenant-1",
        database_id="db-2",
        entity_type=PoolMasterDataEntityType.CONTRACT,
        canonical_id="contract-001",
        mutation_kind="upsert",
        payload_fingerprint="fp-1",
        origin_event_id="evt-1",
    )

    assert base != changed


def test_inbound_fingerprint_changes_when_origin_event_changes() -> None:
    first = build_inbound_dedupe_fingerprint(
        tenant_id="tenant-1",
        database_id="db-1",
        entity_type=PoolMasterDataEntityType.PARTY,
        origin_system="ib",
        origin_event_id="evt-1",
        payload_fingerprint="fp-1",
    )
    second = build_inbound_dedupe_fingerprint(
        tenant_id="tenant-1",
        database_id="db-1",
        entity_type=PoolMasterDataEntityType.PARTY,
        origin_system="ib",
        origin_event_id="evt-2",
        payload_fingerprint="fp-1",
    )

    assert first != second


def test_origin_identifiers_fail_closed_when_missing() -> None:
    with pytest.raises(MasterDataSyncInvariantError) as exc_info:
        require_origin_identifiers(origin_system="", origin_event_id="")

    assert exc_info.value.code == "MASTER_DATA_SYNC_INVARIANT_INVALID"
