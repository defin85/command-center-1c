from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
import re
from typing import Any

from django.utils import timezone

from .models import PoolMasterDataSyncDirection, PoolMasterDataSyncJob, PoolMasterDataSyncPolicy


@dataclass(frozen=True)
class MasterDataSyncSchedulingProfile:
    use_case: str
    priority: str
    role: str
    deadline_seconds: int


SERVER_AFFINITY_UNRESOLVED = "SERVER_AFFINITY_UNRESOLVED"


@dataclass(frozen=True)
class MasterDataSyncAffinityResolution:
    server_affinity: str
    source: str


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


def _normalize_affinity_token(value: Any) -> str:
    token = str(value or "").strip().lower()
    if not token:
        return ""
    if "://" in token:
        token = token.split("://", 1)[1]
    token = token.strip().strip("/")
    token = re.sub(r"[^a-z0-9._:-]+", "-", token)
    token = token.strip("-")
    return token


def _resolve_affinity_override(metadata: Any) -> str:
    if not isinstance(metadata, dict):
        return ""

    nested = metadata.get("pool_master_data_sync")
    if isinstance(nested, dict):
        value = _normalize_affinity_token(nested.get("server_affinity"))
        if value:
            return value

    for key in (
        "pool_master_data_sync_server_affinity",
        "sync_server_affinity",
        "server_affinity",
    ):
        value = _normalize_affinity_token(metadata.get(key))
        if value:
            return value
    return ""


def _resolve_database_endpoint(sync_job: PoolMasterDataSyncJob) -> str:
    database = sync_job.database
    cluster = getattr(database, "cluster", None)
    if cluster is not None:
        ras_server = _normalize_affinity_token(getattr(cluster, "ras_server", ""))
        if ras_server:
            return ras_server
        ras_host = _normalize_affinity_token(getattr(cluster, "ras_host", ""))
        ras_port = int(getattr(cluster, "ras_port", 0) or 0)
        if ras_host:
            return f"{ras_host}:{ras_port}" if ras_port > 0 else ras_host

    server_address = _normalize_affinity_token(getattr(database, "server_address", ""))
    server_port = int(getattr(database, "server_port", 0) or 0)
    if server_address:
        return f"{server_address}:{server_port}" if server_port > 0 else server_address

    host = _normalize_affinity_token(getattr(database, "host", ""))
    port = int(getattr(database, "port", 0) or 0)
    if host:
        return f"{host}:{port}" if port > 0 else host
    return ""


def resolve_master_data_sync_server_affinity(
    *,
    sync_job: PoolMasterDataSyncJob,
) -> MasterDataSyncAffinityResolution:
    database = sync_job.database
    cluster = getattr(database, "cluster", None)

    database_override = _resolve_affinity_override(getattr(database, "metadata", None))
    if database_override:
        return MasterDataSyncAffinityResolution(server_affinity=database_override, source="database_override")

    cluster_override = _resolve_affinity_override(getattr(cluster, "metadata", None))
    if cluster_override:
        return MasterDataSyncAffinityResolution(server_affinity=cluster_override, source="cluster_mapping")

    endpoint = _resolve_database_endpoint(sync_job)
    if endpoint:
        return MasterDataSyncAffinityResolution(server_affinity=f"srv:{endpoint}", source="derived_endpoint")

    raise ValueError(
        f"{SERVER_AFFINITY_UNRESOLVED}: unable to resolve server affinity for sync_job '{sync_job.id}'"
    )


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
