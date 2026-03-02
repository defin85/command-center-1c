from __future__ import annotations

from datetime import datetime
from typing import Any

from django.utils import timezone

from .models import (
    PoolMasterDataSyncCheckpoint,
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncConflictStatus,
    PoolMasterDataSyncOutbox,
    PoolMasterDataSyncOutboxStatus,
)


def list_master_data_sync_status_rows(
    *,
    tenant_id: str,
    database_id: str | None = None,
    entity_type: str | None = None,
) -> list[dict[str, Any]]:
    checkpoint_filters: dict[str, Any] = {"tenant_id": tenant_id}
    outbox_filters: dict[str, Any] = {"tenant_id": tenant_id}
    conflict_filters: dict[str, Any] = {"tenant_id": tenant_id}
    if database_id:
        checkpoint_filters["database_id"] = database_id
        outbox_filters["database_id"] = database_id
        conflict_filters["database_id"] = database_id
    if entity_type:
        checkpoint_filters["entity_type"] = entity_type
        outbox_filters["entity_type"] = entity_type
        conflict_filters["entity_type"] = entity_type

    scopes: dict[tuple[str, str], dict[str, Any]] = {}
    now = timezone.now()

    for checkpoint in PoolMasterDataSyncCheckpoint.objects.filter(**checkpoint_filters).order_by("database_id", "entity_type"):
        key = (str(checkpoint.database_id), str(checkpoint.entity_type))
        row = scopes.setdefault(key, _empty_scope_row(tenant_id=tenant_id, database_id=key[0], entity_type=key[1]))
        metadata = checkpoint.metadata if isinstance(checkpoint.metadata, dict) else {}
        row["checkpoint_token"] = str(checkpoint.checkpoint_token or "")
        row["pending_checkpoint_token"] = str(metadata.get("pending_checkpoint_token") or "")
        row["checkpoint_status"] = str(checkpoint.status or "")
        row["last_error_code"] = str(checkpoint.last_error_code or "")
        row["last_applied_at"] = checkpoint.last_applied_at
        row["last_success_at"] = _latest_dt(row.get("last_success_at"), checkpoint.last_applied_at)

    for outbox in PoolMasterDataSyncOutbox.objects.filter(**outbox_filters).order_by("database_id", "entity_type"):
        key = (str(outbox.database_id), str(outbox.entity_type))
        row = scopes.setdefault(key, _empty_scope_row(tenant_id=tenant_id, database_id=key[0], entity_type=key[1]))
        status = str(outbox.status or "")
        if status == PoolMasterDataSyncOutboxStatus.PENDING:
            row["pending_count"] += 1
            row["lag_seconds"] = _lag_seconds(now=now, current=row["lag_seconds"], candidate=outbox.available_at)
        elif status == PoolMasterDataSyncOutboxStatus.FAILED:
            row["retry_count"] += 1
            row["lag_seconds"] = _lag_seconds(now=now, current=row["lag_seconds"], candidate=outbox.available_at)
        row["last_success_at"] = _latest_dt(row.get("last_success_at"), outbox.dispatched_at)

    for conflict in PoolMasterDataSyncConflict.objects.filter(**conflict_filters).order_by("database_id", "entity_type"):
        key = (str(conflict.database_id), str(conflict.entity_type))
        row = scopes.setdefault(key, _empty_scope_row(tenant_id=tenant_id, database_id=key[0], entity_type=key[1]))
        status = str(conflict.status or "")
        if status == PoolMasterDataSyncConflictStatus.PENDING:
            row["conflict_pending_count"] += 1
        elif status == PoolMasterDataSyncConflictStatus.RETRYING:
            row["conflict_retrying_count"] += 1

    rows = list(scopes.values())
    rows.sort(key=lambda item: (str(item["database_id"]), str(item["entity_type"])))
    return rows


def _empty_scope_row(*, tenant_id: str, database_id: str, entity_type: str) -> dict[str, Any]:
    return {
        "tenant_id": str(tenant_id),
        "database_id": str(database_id),
        "entity_type": str(entity_type),
        "checkpoint_token": "",
        "pending_checkpoint_token": "",
        "checkpoint_status": "",
        "pending_count": 0,
        "retry_count": 0,
        "conflict_pending_count": 0,
        "conflict_retrying_count": 0,
        "lag_seconds": 0,
        "last_success_at": None,
        "last_applied_at": None,
        "last_error_code": "",
    }


def _lag_seconds(*, now: datetime, current: int, candidate: datetime | None) -> int:
    if candidate is None:
        return int(current or 0)
    delta_seconds = int(max(0.0, (now - candidate).total_seconds()))
    if current <= 0:
        return delta_seconds
    return max(current, delta_seconds)


def _latest_dt(current: datetime | None, candidate: datetime | None) -> datetime | None:
    if current is None:
        return candidate
    if candidate is None:
        return current
    return current if current >= candidate else candidate
