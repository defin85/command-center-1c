from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any

from django.utils import timezone

from .models import PoolFactualLane
from .scheduling_primitives import (
    SERVER_AFFINITY_UNRESOLVED,
    SchedulingAffinityResolution,
    resolve_database_server_affinity,
)


@dataclass(frozen=True)
class FactualSchedulingProfile:
    use_case: str
    priority: str
    role: str
    deadline_seconds: int


@dataclass(frozen=True)
class FactualPollingTier:
    name: str
    interval_seconds: int


@dataclass(frozen=True)
class FactualRolloutEnvelope:
    write_lane_role: str
    read_lane_role: str
    reconcile_lane_role: str
    per_database_read_cap: int
    per_cluster_read_cap: int
    global_read_cap: int
    polling_tiers: tuple[FactualPollingTier, ...]
    closed_quarter_reconcile_schedule: str


FactualSchedulingAffinityResolution = SchedulingAffinityResolution


_PROFILE_MATRIX: dict[str, FactualSchedulingProfile] = {
    PoolFactualLane.READ: FactualSchedulingProfile(
        use_case="factual:read",
        priority="p1",
        role="read",
        deadline_seconds=120,
    ),
    PoolFactualLane.RECONCILE: FactualSchedulingProfile(
        use_case="factual:reconcile",
        priority="p2",
        role="reconcile",
        deadline_seconds=3600,
    ),
}

_POLLING_TIERS: dict[str, FactualPollingTier] = {
    "active": FactualPollingTier(name="active", interval_seconds=120),
    "warm": FactualPollingTier(name="warm", interval_seconds=600),
    "cold": FactualPollingTier(name="cold", interval_seconds=3600),
}

_ROLLOUT_ENVELOPE = FactualRolloutEnvelope(
    write_lane_role="write",
    read_lane_role="read",
    reconcile_lane_role="reconcile",
    per_database_read_cap=1,
    per_cluster_read_cap=2,
    global_read_cap=8,
    polling_tiers=tuple(_POLLING_TIERS[name] for name in ("active", "warm", "cold")),
    closed_quarter_reconcile_schedule="nightly",
)


def _format_rfc3339_utc(value: datetime) -> str:
    return value.astimezone(dt_timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_factual_scheduling_profile(*, lane: str) -> FactualSchedulingProfile:
    normalized_lane = str(lane or "").strip().lower()
    profile = _PROFILE_MATRIX.get(normalized_lane)
    if profile is not None:
        return profile
    raise ValueError(f"Unsupported factual scheduling lane '{normalized_lane}'")


def resolve_factual_polling_tier(*, activity: str) -> FactualPollingTier:
    normalized_activity = str(activity or "").strip().lower()
    tier = _POLLING_TIERS.get(normalized_activity)
    if tier is not None:
        return tier
    raise ValueError(f"Unsupported factual polling activity '{normalized_activity}'")


def resolve_factual_rollout_envelope() -> FactualRolloutEnvelope:
    return _ROLLOUT_ENVELOPE


def resolve_factual_server_affinity(*, database: Any) -> FactualSchedulingAffinityResolution:
    try:
        return resolve_database_server_affinity(
            database=database,
            metadata_namespace="pool_factual",
        )
    except ValueError as exc:
        raise ValueError(
            f"{SERVER_AFFINITY_UNRESOLVED}: unable to resolve factual server affinity for database "
            f"'{getattr(database, 'id', 'unknown')}'"
        ) from exc


def build_factual_scheduling_contract(
    *,
    database: Any,
    lane: str,
    now: datetime | None = None,
) -> dict[str, str]:
    profile = resolve_factual_scheduling_profile(lane=lane)
    affinity = resolve_factual_server_affinity(database=database)
    timestamp = now or timezone.now()
    deadline_at = timestamp.astimezone(dt_timezone.utc) + timedelta(seconds=int(profile.deadline_seconds))
    return {
        "priority": profile.priority,
        "role": profile.role,
        "server_affinity": affinity.server_affinity,
        "server_affinity_source": affinity.source,
        "deadline_at": _format_rfc3339_utc(deadline_at),
        "factual_use_case": profile.use_case,
        "lane": str(lane or "").strip().lower(),
    }


def build_factual_read_contract(
    *,
    database: Any,
    activity: str,
    now: datetime | None = None,
) -> dict[str, str]:
    contract = build_factual_scheduling_contract(
        database=database,
        lane=PoolFactualLane.READ,
        now=now,
    )
    tier = resolve_factual_polling_tier(activity=activity)
    envelope = resolve_factual_rollout_envelope()
    return {
        **contract,
        "per_database_cap": str(envelope.per_database_read_cap),
        "per_cluster_cap": str(envelope.per_cluster_read_cap),
        "global_cap": str(envelope.global_read_cap),
        "polling_tier": tier.name,
        "poll_interval_seconds": str(tier.interval_seconds),
        "freshness_target_seconds": str(tier.interval_seconds),
    }


def build_factual_closed_quarter_reconcile_contract(
    *,
    database: Any,
    now: datetime | None = None,
) -> dict[str, str]:
    envelope = resolve_factual_rollout_envelope()
    contract = build_factual_scheduling_contract(
        database=database,
        lane=PoolFactualLane.RECONCILE,
        now=now,
    )
    return {
        **contract,
        "quarter_scope": "closed",
        "schedule_window": envelope.closed_quarter_reconcile_schedule,
    }
