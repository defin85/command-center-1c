from __future__ import annotations

from dataclasses import dataclass


MASTER_DATA_SYNC_ORIGIN_CC = "cc"
MASTER_DATA_SYNC_ORIGIN_IB = "ib"


@dataclass(frozen=True)
class MasterDataSyncOrigin:
    origin_system: str
    origin_event_id: str


def normalize_master_data_sync_origin(
    *,
    origin_system: str,
    origin_event_id: str,
    default_origin_system: str = MASTER_DATA_SYNC_ORIGIN_CC,
) -> MasterDataSyncOrigin:
    normalized_system = str(origin_system or default_origin_system).strip().lower()
    if not normalized_system:
        normalized_system = default_origin_system
    normalized_event_id = str(origin_event_id or "").strip()
    if normalized_system != MASTER_DATA_SYNC_ORIGIN_CC and not normalized_event_id:
        raise ValueError("origin_event_id is required for non-CC origin")
    return MasterDataSyncOrigin(
        origin_system=normalized_system,
        origin_event_id=normalized_event_id,
    )


def should_skip_outbound_sync_for_origin(
    *,
    origin_system: str,
    origin_event_id: str,
    target_system: str = MASTER_DATA_SYNC_ORIGIN_IB,
) -> bool:
    normalized_system = str(origin_system or "").strip().lower()
    normalized_target = str(target_system or "").strip().lower()
    normalized_event_id = str(origin_event_id or "").strip()
    if not normalized_event_id:
        return False
    return normalized_system == normalized_target
