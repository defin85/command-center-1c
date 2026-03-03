from __future__ import annotations

from typing import Any, Mapping

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import (
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncConflictStatus,
)


MASTER_DATA_SYNC_CONFLICT_ACTION_RETRY = "retry"
MASTER_DATA_SYNC_CONFLICT_ACTION_RECONCILE = "reconcile"
MASTER_DATA_SYNC_CONFLICT_ACTION_RESOLVE = "resolve"


def retry_master_data_sync_conflict(
    *,
    conflict_id: str,
    tenant_id: str,
    actor_id: str,
    note: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> PoolMasterDataSyncConflict:
    with transaction.atomic():
        conflict = PoolMasterDataSyncConflict.objects.select_for_update().get(
            id=conflict_id,
            tenant_id=tenant_id,
        )
        if conflict.status == PoolMasterDataSyncConflictStatus.RESOLVED:
            raise ValueError("Cannot retry resolved master-data sync conflict.")
        _append_operator_action_audit(
            conflict=conflict,
            action=MASTER_DATA_SYNC_CONFLICT_ACTION_RETRY,
            actor_id=actor_id,
            note=note,
            metadata=metadata,
        )
        conflict.status = PoolMasterDataSyncConflictStatus.RETRYING
        conflict.save(update_fields=["status", "metadata", "updated_at"])
    return conflict


def reconcile_master_data_sync_conflict(
    *,
    conflict_id: str,
    tenant_id: str,
    actor_id: str,
    reconcile_payload: Mapping[str, Any],
    note: str = "",
) -> PoolMasterDataSyncConflict:
    with transaction.atomic():
        conflict = PoolMasterDataSyncConflict.objects.select_for_update().get(
            id=conflict_id,
            tenant_id=tenant_id,
        )
        if conflict.status == PoolMasterDataSyncConflictStatus.RESOLVED:
            raise ValueError("Cannot reconcile resolved master-data sync conflict.")
        _append_operator_action_audit(
            conflict=conflict,
            action=MASTER_DATA_SYNC_CONFLICT_ACTION_RECONCILE,
            actor_id=actor_id,
            note=note,
            metadata=reconcile_payload,
        )
        conflict.status = PoolMasterDataSyncConflictStatus.RETRYING
        metadata_payload = dict(conflict.metadata or {})
        metadata_payload["last_reconcile_payload"] = dict(reconcile_payload or {})
        conflict.metadata = metadata_payload
        conflict.save(update_fields=["status", "metadata", "updated_at"])
    return conflict


def resolve_master_data_sync_conflict(
    *,
    conflict_id: str,
    tenant_id: str,
    actor_id: str,
    resolution_code: str,
    note: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> PoolMasterDataSyncConflict:
    normalized_resolution_code = str(resolution_code or "").strip()
    if not normalized_resolution_code:
        raise ValueError("resolution_code is required")

    User = get_user_model()
    with transaction.atomic():
        conflict = PoolMasterDataSyncConflict.objects.select_for_update().get(
            id=conflict_id,
            tenant_id=tenant_id,
        )
        if conflict.status == PoolMasterDataSyncConflictStatus.RESOLVED:
            raise ValueError("Conflict is already resolved.")
        actor = User.objects.get(id=actor_id)
        _append_operator_action_audit(
            conflict=conflict,
            action=MASTER_DATA_SYNC_CONFLICT_ACTION_RESOLVE,
            actor_id=actor_id,
            note=note,
            metadata={
                "resolution_code": normalized_resolution_code,
                **dict(metadata or {}),
            },
        )
        conflict.status = PoolMasterDataSyncConflictStatus.RESOLVED
        conflict.resolved_at = timezone.now()
        conflict.resolved_by = actor
        conflict.save(update_fields=["status", "resolved_at", "resolved_by", "metadata", "updated_at"])
    return conflict


def _append_operator_action_audit(
    *,
    conflict: PoolMasterDataSyncConflict,
    action: str,
    actor_id: str,
    note: str,
    metadata: Mapping[str, Any] | None,
) -> None:
    metadata_payload = dict(conflict.metadata or {})
    audit = metadata_payload.get("operator_actions")
    history = list(audit) if isinstance(audit, list) else []
    history.append(
        {
            "action": str(action or "").strip(),
            "actor_id": str(actor_id or "").strip(),
            "at": timezone.now().isoformat(),
            "note": str(note or "").strip(),
            "metadata": dict(metadata or {}),
        }
    )
    metadata_payload["operator_actions"] = history[-50:]
    conflict.metadata = metadata_payload
