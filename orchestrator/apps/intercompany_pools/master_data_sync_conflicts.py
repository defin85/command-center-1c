from __future__ import annotations

import hashlib
from typing import Any, Mapping

from django.db import transaction
from django.utils import timezone

from .models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncConflictStatus,
)


MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION = "POLICY_VIOLATION"
MASTER_DATA_SYNC_CONFLICT_OWNERSHIP = "OWNERSHIP_CONFLICT"
MASTER_DATA_SYNC_CONFLICT_VERSION = "VERSION_CONFLICT"
MASTER_DATA_SYNC_CONFLICT_STATE = "CANONICAL_STATE_CONFLICT"
MASTER_DATA_SYNC_CONFLICT_ORIGIN = "ORIGIN_METADATA_CONFLICT"
MASTER_DATA_SYNC_CONFLICT_APPLY = "APPLY_CONFLICT"

MASTER_DATA_SYNC_CONFLICT_CODES = frozenset(
    [
        MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
        MASTER_DATA_SYNC_CONFLICT_OWNERSHIP,
        MASTER_DATA_SYNC_CONFLICT_VERSION,
        MASTER_DATA_SYNC_CONFLICT_STATE,
        MASTER_DATA_SYNC_CONFLICT_ORIGIN,
        MASTER_DATA_SYNC_CONFLICT_APPLY,
    ]
)


class MasterDataSyncConflictError(RuntimeError):
    def __init__(
        self,
        *,
        code: str,
        detail: str,
        conflict_id: str,
        entity_type: str,
        canonical_id: str,
        diagnostics: Mapping[str, Any] | None = None,
    ) -> None:
        self.code = str(code or "").strip()
        self.detail = str(detail or "").strip() or "master-data sync conflict detected"
        self.conflict_id = str(conflict_id or "").strip()
        self.entity_type = str(entity_type or "").strip()
        self.canonical_id = str(canonical_id or "").strip()
        self.diagnostics = dict(diagnostics or {})
        super().__init__(f"{self.code}: {self.detail}")

    def to_diagnostic(self) -> dict[str, Any]:
        return {
            "error_code": self.code,
            "detail": self.detail,
            "conflict_id": self.conflict_id,
            "entity_type": self.entity_type,
            "canonical_id": self.canonical_id,
            "diagnostics": self.diagnostics,
        }


def ensure_master_data_sync_conflict_code(*, conflict_code: str) -> str:
    normalized = str(conflict_code or "").strip().upper()
    if normalized not in MASTER_DATA_SYNC_CONFLICT_CODES:
        raise ValueError(
            "Unsupported master-data sync conflict code "
            f"'{conflict_code}'. Allowed: {', '.join(sorted(MASTER_DATA_SYNC_CONFLICT_CODES))}"
        )
    return normalized


def enqueue_master_data_sync_conflict(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    conflict_code: str,
    canonical_id: str = "",
    origin_system: str = "",
    origin_event_id: str = "",
    diagnostics: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PoolMasterDataSyncConflict:
    normalized_entity_type = _normalize_entity_type(entity_type=entity_type)
    normalized_conflict_code = ensure_master_data_sync_conflict_code(conflict_code=conflict_code)
    normalized_canonical_id = str(canonical_id or "").strip()
    normalized_origin_system = str(origin_system or "").strip()
    normalized_origin_event_id = str(origin_event_id or "").strip()
    diagnostics_payload = dict(diagnostics or {})
    metadata_payload = dict(metadata or {})
    queue_key = build_master_data_sync_conflict_queue_key(
        tenant_id=str(tenant_id or "").strip(),
        database_id=str(database_id or "").strip(),
        entity_type=normalized_entity_type,
        conflict_code=normalized_conflict_code,
        canonical_id=normalized_canonical_id,
        origin_system=normalized_origin_system,
        origin_event_id=normalized_origin_event_id,
    )
    now = timezone.now()

    with transaction.atomic():
        existing = (
            PoolMasterDataSyncConflict.objects.select_for_update()
            .filter(
                tenant_id=str(tenant_id or "").strip(),
                database_id=str(database_id or "").strip(),
                entity_type=normalized_entity_type,
                conflict_code=normalized_conflict_code,
                canonical_id=normalized_canonical_id,
                origin_system=normalized_origin_system,
                origin_event_id=normalized_origin_event_id,
                status__in=[
                    PoolMasterDataSyncConflictStatus.PENDING,
                    PoolMasterDataSyncConflictStatus.RETRYING,
                ],
            )
            .order_by("-created_at")
            .first()
        )
        if existing is not None:
            existing_metadata = dict(existing.metadata or {})
            existing_metadata["queue_key"] = queue_key
            existing_metadata["repeat_count"] = int(existing_metadata.get("repeat_count") or 1) + 1
            existing_metadata["last_seen_at"] = now.isoformat()
            if metadata_payload:
                existing_metadata["last_context"] = metadata_payload
            existing.metadata = existing_metadata
            if diagnostics_payload:
                existing.diagnostics = diagnostics_payload
            existing.save(update_fields=["metadata", "diagnostics", "updated_at"])
            return existing

        conflict_metadata = {
            "queue_key": queue_key,
            "repeat_count": 1,
            "first_seen_at": now.isoformat(),
            "last_seen_at": now.isoformat(),
        }
        if metadata_payload:
            conflict_metadata["last_context"] = metadata_payload

        return PoolMasterDataSyncConflict.objects.create(
            tenant_id=str(tenant_id or "").strip(),
            database_id=str(database_id or "").strip(),
            entity_type=normalized_entity_type,
            status=PoolMasterDataSyncConflictStatus.PENDING,
            conflict_code=normalized_conflict_code,
            canonical_id=normalized_canonical_id,
            origin_system=normalized_origin_system,
            origin_event_id=normalized_origin_event_id,
            diagnostics=diagnostics_payload,
            metadata=conflict_metadata,
        )


def raise_fail_closed_master_data_sync_conflict(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    conflict_code: str,
    detail: str,
    canonical_id: str = "",
    origin_system: str = "",
    origin_event_id: str = "",
    diagnostics: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    diagnostics_payload = dict(diagnostics or {})
    if detail and "detail" not in diagnostics_payload:
        diagnostics_payload["detail"] = str(detail)
    conflict = enqueue_master_data_sync_conflict(
        tenant_id=tenant_id,
        database_id=database_id,
        entity_type=entity_type,
        conflict_code=conflict_code,
        canonical_id=canonical_id,
        origin_system=origin_system,
        origin_event_id=origin_event_id,
        diagnostics=diagnostics_payload,
        metadata=metadata,
    )
    raise MasterDataSyncConflictError(
        code=str(conflict.conflict_code),
        detail=str(detail or "master-data sync conflict detected"),
        conflict_id=str(conflict.id),
        entity_type=str(conflict.entity_type),
        canonical_id=str(conflict.canonical_id or ""),
        diagnostics=dict(conflict.diagnostics or {}),
    )


def build_master_data_sync_conflict_queue_key(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    conflict_code: str,
    canonical_id: str,
    origin_system: str,
    origin_event_id: str,
) -> str:
    raw = "|".join(
        [
            str(tenant_id or "").strip(),
            str(database_id or "").strip(),
            str(entity_type or "").strip(),
            str(conflict_code or "").strip(),
            str(canonical_id or "").strip(),
            str(origin_system or "").strip(),
            str(origin_event_id or "").strip(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_entity_type(*, entity_type: str) -> str:
    normalized = str(entity_type or "").strip()
    if normalized not in set(PoolMasterDataEntityType.values):
        raise ValueError(f"Unsupported master-data entity_type '{entity_type}'")
    return normalized
