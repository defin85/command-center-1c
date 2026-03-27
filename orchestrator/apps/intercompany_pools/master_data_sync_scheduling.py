from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone

from django.utils import timezone

from .models import PoolMasterDataSyncDirection, PoolMasterDataSyncJob, PoolMasterDataSyncPolicy
from .scheduling_primitives import (
    SERVER_AFFINITY_UNRESOLVED,
    SchedulingAffinityResolution,
    resolve_database_server_affinity,
)


@dataclass(frozen=True)
class MasterDataSyncSchedulingProfile:
    use_case: str
    priority: str
    role: str
    deadline_seconds: int


MasterDataSyncAffinityResolution = SchedulingAffinityResolution


_PROFILE_MATRIX: dict[tuple[str, str], MasterDataSyncSchedulingProfile] = {
    (PoolMasterDataSyncPolicy.CC_MASTER, PoolMasterDataSyncDirection.OUTBOUND): MasterDataSyncSchedulingProfile(
        use_case="cc_master:outbound",
        priority="p1",
        role="outbound",
        deadline_seconds=90,
    ),
    (PoolMasterDataSyncPolicy.CC_MASTER, PoolMasterDataSyncDirection.INBOUND): MasterDataSyncSchedulingProfile(
        use_case="cc_master:inbound",
        priority="p2",
        role="inbound",
        deadline_seconds=180,
    ),
    (PoolMasterDataSyncPolicy.CC_MASTER, PoolMasterDataSyncDirection.BIDIRECTIONAL): MasterDataSyncSchedulingProfile(
        use_case="cc_master:bidirectional",
        priority="p1",
        role="reconcile",
        deadline_seconds=120,
    ),
    (PoolMasterDataSyncPolicy.IB_MASTER, PoolMasterDataSyncDirection.OUTBOUND): MasterDataSyncSchedulingProfile(
        use_case="ib_master:outbound",
        priority="p2",
        role="outbound",
        deadline_seconds=180,
    ),
    (PoolMasterDataSyncPolicy.IB_MASTER, PoolMasterDataSyncDirection.INBOUND): MasterDataSyncSchedulingProfile(
        use_case="ib_master:inbound",
        priority="p1",
        role="inbound",
        deadline_seconds=90,
    ),
    (PoolMasterDataSyncPolicy.IB_MASTER, PoolMasterDataSyncDirection.BIDIRECTIONAL): MasterDataSyncSchedulingProfile(
        use_case="ib_master:bidirectional",
        priority="p1",
        role="reconcile",
        deadline_seconds=120,
    ),
    (
        PoolMasterDataSyncPolicy.BIDIRECTIONAL,
        PoolMasterDataSyncDirection.OUTBOUND,
    ): MasterDataSyncSchedulingProfile(
        use_case="bidirectional:outbound",
        priority="p2",
        role="outbound",
        deadline_seconds=180,
    ),
    (PoolMasterDataSyncPolicy.BIDIRECTIONAL, PoolMasterDataSyncDirection.INBOUND): MasterDataSyncSchedulingProfile(
        use_case="bidirectional:inbound",
        priority="p2",
        role="inbound",
        deadline_seconds=180,
    ),
    (
        PoolMasterDataSyncPolicy.BIDIRECTIONAL,
        PoolMasterDataSyncDirection.BIDIRECTIONAL,
    ): MasterDataSyncSchedulingProfile(
        use_case="bidirectional:bidirectional",
        priority="p2",
        role="reconcile",
        deadline_seconds=120,
    ),
}


def _format_rfc3339_utc(value: datetime) -> str:
    return value.astimezone(dt_timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_master_data_sync_server_affinity(
    *,
    sync_job: PoolMasterDataSyncJob,
) -> MasterDataSyncAffinityResolution:
    try:
        return resolve_database_server_affinity(
            database=sync_job.database,
            metadata_namespace="pool_master_data_sync",
        )
    except ValueError as exc:
        raise ValueError(
            f"{SERVER_AFFINITY_UNRESOLVED}: unable to resolve server affinity for sync_job '{sync_job.id}'"
        ) from exc


def resolve_master_data_sync_scheduling_profile(
    *,
    policy: str,
    direction: str,
) -> MasterDataSyncSchedulingProfile:
    normalized_policy = str(policy or "").strip().lower()
    normalized_direction = str(direction or "").strip().lower()
    profile = _PROFILE_MATRIX.get((normalized_policy, normalized_direction))
    if profile is not None:
        return profile
    raise ValueError(
        "Unsupported sync scheduling mapping "
        f"(policy='{normalized_policy}', direction='{normalized_direction}')"
    )


def build_master_data_sync_scheduling_contract(
    *,
    sync_job: PoolMasterDataSyncJob,
    now: datetime | None = None,
) -> dict[str, str]:
    profile = resolve_master_data_sync_scheduling_profile(
        policy=sync_job.policy,
        direction=sync_job.direction,
    )
    affinity = resolve_master_data_sync_server_affinity(sync_job=sync_job)
    timestamp = now or timezone.now()
    deadline_at = timestamp.astimezone(dt_timezone.utc) + timedelta(seconds=int(profile.deadline_seconds))
    return {
        "priority": profile.priority,
        "role": profile.role,
        "server_affinity": affinity.server_affinity,
        "server_affinity_source": affinity.source,
        "deadline_at": _format_rfc3339_utc(deadline_at),
        "sync_use_case": profile.use_case,
    }
