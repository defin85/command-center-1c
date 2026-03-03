from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace

import pytest

from apps.intercompany_pools.master_data_sync_scheduling import (
    SERVER_AFFINITY_UNRESOLVED,
    build_master_data_sync_scheduling_contract,
    resolve_master_data_sync_scheduling_profile,
    resolve_master_data_sync_server_affinity,
)
from apps.intercompany_pools.models import (
    PoolMasterDataSyncDirection,
    PoolMasterDataSyncPolicy,
)


@pytest.mark.parametrize(
    ("policy", "direction", "expected_priority", "expected_role", "expected_deadline_seconds"),
    [
        (PoolMasterDataSyncPolicy.CC_MASTER, PoolMasterDataSyncDirection.OUTBOUND, "p1", "outbound", 90),
        (PoolMasterDataSyncPolicy.CC_MASTER, PoolMasterDataSyncDirection.INBOUND, "p2", "inbound", 180),
        (PoolMasterDataSyncPolicy.IB_MASTER, PoolMasterDataSyncDirection.OUTBOUND, "p2", "outbound", 180),
        (PoolMasterDataSyncPolicy.IB_MASTER, PoolMasterDataSyncDirection.INBOUND, "p1", "inbound", 90),
        (
            PoolMasterDataSyncPolicy.BIDIRECTIONAL,
            PoolMasterDataSyncDirection.BIDIRECTIONAL,
            "p2",
            "reconcile",
            120,
        ),
    ],
)
def test_resolve_sync_scheduling_profile_is_policy_and_direction_aware(
    policy: str,
    direction: str,
    expected_priority: str,
    expected_role: str,
    expected_deadline_seconds: int,
) -> None:
    profile = resolve_master_data_sync_scheduling_profile(policy=policy, direction=direction)

    assert profile.use_case == f"{policy}:{direction}"
    assert profile.priority == expected_priority
    assert profile.role == expected_role
    assert profile.deadline_seconds == expected_deadline_seconds


def test_build_sync_scheduling_contract_uses_profile_affinity_and_rfc3339_utc_deadline() -> None:
    fixed_now = datetime(2026, 3, 3, 12, 0, tzinfo=dt_timezone.utc)
    database = SimpleNamespace(
        metadata={},
        cluster=None,
        server_address="srv-db",
        server_port=1540,
        host="db.internal",
        port=80,
    )
    sync_job = SimpleNamespace(
        id="job-123",
        policy=PoolMasterDataSyncPolicy.CC_MASTER,
        direction=PoolMasterDataSyncDirection.OUTBOUND,
        database=database,
    )

    contract = build_master_data_sync_scheduling_contract(sync_job=sync_job, now=fixed_now)

    assert contract["priority"] == "p1"
    assert contract["role"] == "outbound"
    assert contract["server_affinity"] == "srv:srv-db:1540"
    assert contract["server_affinity_source"] == "derived_endpoint"
    assert contract["deadline_at"] == "2026-03-03T12:01:30Z"
    assert contract["sync_use_case"] == "cc_master:outbound"


def test_resolve_sync_scheduling_profile_rejects_unknown_mapping() -> None:
    with pytest.raises(ValueError, match="Unsupported sync scheduling mapping"):
        resolve_master_data_sync_scheduling_profile(policy="unknown", direction="invalid")


def test_resolve_server_affinity_prefers_database_override() -> None:
    sync_job = SimpleNamespace(
        id="job-db-override",
        database=SimpleNamespace(
            metadata={"pool_master_data_sync_server_affinity": "srv-db-override"},
            cluster=SimpleNamespace(metadata={"sync_server_affinity": "srv-cluster"}),
            server_address="srv-fallback",
            server_port=1540,
            host="db.internal",
            port=80,
        ),
    )

    resolution = resolve_master_data_sync_server_affinity(sync_job=sync_job)
    assert resolution.server_affinity == "srv-db-override"
    assert resolution.source == "database_override"


def test_resolve_server_affinity_uses_cluster_mapping_when_database_override_missing() -> None:
    sync_job = SimpleNamespace(
        id="job-cluster-map",
        database=SimpleNamespace(
            metadata={},
            cluster=SimpleNamespace(
                metadata={"pool_master_data_sync": {"server_affinity": "srv-cluster-map"}},
                ras_server="cluster-host:1545",
                ras_host="cluster-host",
                ras_port=1545,
            ),
            server_address="srv-fallback",
            server_port=1540,
            host="db.internal",
            port=80,
        ),
    )

    resolution = resolve_master_data_sync_server_affinity(sync_job=sync_job)
    assert resolution.server_affinity == "srv-cluster-map"
    assert resolution.source == "cluster_mapping"


def test_resolve_server_affinity_derives_from_endpoint_when_no_overrides() -> None:
    sync_job = SimpleNamespace(
        id="job-derived",
        database=SimpleNamespace(
            metadata={},
            cluster=SimpleNamespace(metadata={}, ras_server="RAS-Host.EXAMPLE:1545"),
            server_address="srv-fallback",
            server_port=1540,
            host="db.internal",
            port=80,
        ),
    )

    resolution = resolve_master_data_sync_server_affinity(sync_job=sync_job)
    assert resolution.server_affinity == "srv:ras-host.example:1545"
    assert resolution.source == "derived_endpoint"


def test_resolve_server_affinity_fails_closed_when_unresolvable() -> None:
    sync_job = SimpleNamespace(
        id="job-unresolved",
        database=SimpleNamespace(
            metadata={},
            cluster=SimpleNamespace(metadata={}, ras_server="", ras_host="", ras_port=None),
            server_address="",
            server_port=None,
            host="",
            port=None,
        ),
    )

    with pytest.raises(ValueError, match=SERVER_AFFINITY_UNRESOLVED):
        resolve_master_data_sync_server_affinity(sync_job=sync_job)
