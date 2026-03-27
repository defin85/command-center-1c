from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace

import pytest

from apps.intercompany_pools.factual_scheduling import (
    SERVER_AFFINITY_UNRESOLVED,
    build_factual_closed_quarter_reconcile_contract,
    build_factual_read_contract,
    build_factual_scheduling_contract,
    resolve_factual_polling_tier,
    resolve_factual_rollout_envelope,
    resolve_factual_scheduling_profile,
    resolve_factual_server_affinity,
)
from apps.intercompany_pools.models import PoolFactualLane


@pytest.mark.parametrize(
    ("lane", "expected_priority", "expected_role", "expected_deadline_seconds"),
    [
        (PoolFactualLane.READ, "p1", "read", 120),
        (PoolFactualLane.RECONCILE, "p2", "reconcile", 3600),
    ],
)
def test_resolve_factual_scheduling_profile_is_lane_aware(
    lane: str,
    expected_priority: str,
    expected_role: str,
    expected_deadline_seconds: int,
) -> None:
    profile = resolve_factual_scheduling_profile(lane=lane)

    assert profile.use_case == f"factual:{lane}"
    assert profile.priority == expected_priority
    assert profile.role == expected_role
    assert profile.deadline_seconds == expected_deadline_seconds


def test_build_factual_scheduling_contract_reuses_worker_metadata_fields() -> None:
    fixed_now = datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc)
    database = SimpleNamespace(
        metadata={},
        cluster=None,
        server_address="srv-factual",
        server_port=1540,
        host="db.internal",
        port=80,
    )

    contract = build_factual_scheduling_contract(
        database=database,
        lane=PoolFactualLane.READ,
        now=fixed_now,
    )

    assert contract["priority"] == "p1"
    assert contract["role"] == "read"
    assert contract["server_affinity"] == "srv:srv-factual:1540"
    assert contract["server_affinity_source"] == "derived_endpoint"
    assert contract["deadline_at"] == "2026-03-27T10:02:00Z"
    assert contract["factual_use_case"] == "factual:read"
    assert contract["lane"] == "read"


def test_resolve_factual_server_affinity_prefers_factual_override_namespace() -> None:
    database = SimpleNamespace(
        id="db-factual-override",
        metadata={"pool_factual_server_affinity": "srv-factual-override"},
        cluster=SimpleNamespace(metadata={"server_affinity": "srv-cluster-fallback"}),
        server_address="srv-fallback",
        server_port=1540,
        host="db.internal",
        port=80,
    )

    resolution = resolve_factual_server_affinity(database=database)

    assert resolution.server_affinity == "srv-factual-override"
    assert resolution.source == "database_override"


def test_resolve_factual_server_affinity_fails_closed_when_unresolvable() -> None:
    database = SimpleNamespace(
        id="db-factual-unresolved",
        metadata={},
        cluster=SimpleNamespace(metadata={}, ras_server="", ras_host="", ras_port=None),
        server_address="",
        server_port=None,
        host="",
        port=None,
    )

    with pytest.raises(ValueError, match=SERVER_AFFINITY_UNRESOLVED):
        resolve_factual_server_affinity(database=database)


@pytest.mark.parametrize(
    ("activity", "expected_interval_seconds"),
    [
        ("active", 120),
        ("warm", 600),
        ("cold", 3600),
    ],
)
def test_resolve_factual_polling_tier_uses_rollout_tiers(
    activity: str,
    expected_interval_seconds: int,
) -> None:
    tier = resolve_factual_polling_tier(activity=activity)

    assert tier.name == activity
    assert tier.interval_seconds == expected_interval_seconds


def test_resolve_factual_rollout_envelope_exposes_caps_and_nightly_reconcile() -> None:
    envelope = resolve_factual_rollout_envelope()

    assert envelope.write_lane_role == "write"
    assert envelope.read_lane_role == "read"
    assert envelope.reconcile_lane_role == "reconcile"
    assert envelope.per_database_read_cap == 1
    assert envelope.per_cluster_read_cap == 2
    assert envelope.global_read_cap == 8
    assert [tier.name for tier in envelope.polling_tiers] == ["active", "warm", "cold"]
    assert envelope.closed_quarter_reconcile_schedule == "nightly"


def test_build_factual_read_contract_adds_caps_and_polling_tier() -> None:
    fixed_now = datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc)
    database = SimpleNamespace(
        metadata={},
        cluster=None,
        server_address="srv-factual",
        server_port=1540,
        host="db.internal",
        port=80,
    )

    contract = build_factual_read_contract(
        database=database,
        activity="warm",
        now=fixed_now,
    )

    assert contract["role"] == "read"
    assert contract["per_database_cap"] == "1"
    assert contract["per_cluster_cap"] == "2"
    assert contract["global_cap"] == "8"
    assert contract["polling_tier"] == "warm"
    assert contract["poll_interval_seconds"] == "600"


def test_build_factual_closed_quarter_reconcile_contract_marks_nightly_window() -> None:
    fixed_now = datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc)
    database = SimpleNamespace(
        metadata={},
        cluster=None,
        server_address="srv-factual",
        server_port=1540,
        host="db.internal",
        port=80,
    )

    contract = build_factual_closed_quarter_reconcile_contract(
        database=database,
        now=fixed_now,
    )

    assert contract["role"] == "reconcile"
    assert contract["quarter_scope"] == "closed"
    assert contract["schedule_window"] == "nightly"
