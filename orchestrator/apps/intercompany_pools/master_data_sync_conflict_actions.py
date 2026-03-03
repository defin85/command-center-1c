from __future__ import annotations

from typing import Any, Mapping

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .master_data_sync_execution import trigger_pool_master_data_outbound_sync_job
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
    return _trigger_conflict_reprocess_or_revert(
        conflict=conflict,
        tenant_id=tenant_id,
        action=MASTER_DATA_SYNC_CONFLICT_ACTION_RETRY,
    )


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
    return _trigger_conflict_reprocess_or_revert(
        conflict=conflict,
        tenant_id=tenant_id,
        action=MASTER_DATA_SYNC_CONFLICT_ACTION_RECONCILE,
    )


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


def _trigger_conflict_reprocess_or_revert(
    *,
    conflict: PoolMasterDataSyncConflict,
    tenant_id: str,
    action: str,
) -> PoolMasterDataSyncConflict:
    trigger_result = trigger_pool_master_data_outbound_sync_job(
        tenant_id=str(conflict.tenant_id),
        database_id=str(conflict.database_id),
        entity_type=str(conflict.entity_type),
        canonical_id=str(conflict.canonical_id or ""),
        origin_system=str(conflict.origin_system or "cc"),
        origin_event_id=str(conflict.origin_event_id or ""),
    )
    started_workflow = bool(getattr(trigger_result, "started_workflow", False))
    skipped = bool(getattr(trigger_result, "skipped", False))
    skip_reason = str(getattr(trigger_result, "skip_reason", "") or "")
    sync_job = getattr(trigger_result, "sync_job", None)
    start_result = getattr(trigger_result, "start_result", None)
    dispatch_summary = {
        "action": str(action or "").strip(),
        "started_workflow": started_workflow,
        "skipped": skipped,
        "skip_reason": skip_reason,
        "sync_job_id": str(getattr(sync_job, "id", "") or ""),
        "workflow_execution_id": str(getattr(start_result, "execution_id", "") or ""),
        "operation_id": str(getattr(start_result, "operation_id", "") or ""),
        "enqueue_status": str(getattr(start_result, "enqueue_status", "") or ""),
        "enqueue_error": str(getattr(start_result, "enqueue_error", "") or ""),
        "at": timezone.now().isoformat(),
    }
    if started_workflow and not skipped:
        return _persist_conflict_retry_dispatch_state(
            conflict_id=str(conflict.id),
            tenant_id=tenant_id,
            dispatch_summary=dispatch_summary,
            revert_to_pending=False,
        )

    _persist_conflict_retry_dispatch_state(
        conflict_id=str(conflict.id),
        tenant_id=tenant_id,
        dispatch_summary=dispatch_summary,
        revert_to_pending=True,
    )
    reason = skip_reason or str(getattr(start_result, "enqueue_error", "") or "").strip() or "unknown trigger failure"
    raise ValueError(f"Failed to initiate sync workflow for conflict retry/reconcile: {reason}")


def _persist_conflict_retry_dispatch_state(
    *,
    conflict_id: str,
    tenant_id: str,
    dispatch_summary: Mapping[str, Any],
    revert_to_pending: bool,
) -> PoolMasterDataSyncConflict:
    with transaction.atomic():
        conflict = PoolMasterDataSyncConflict.objects.select_for_update().get(
            id=conflict_id,
            tenant_id=tenant_id,
        )
        metadata_payload = dict(conflict.metadata or {})
        metadata_payload["last_retry_dispatch"] = dict(dispatch_summary or {})
        conflict.metadata = metadata_payload
        update_fields = ["metadata", "updated_at"]
        if revert_to_pending and conflict.status == PoolMasterDataSyncConflictStatus.RETRYING:
            conflict.status = PoolMasterDataSyncConflictStatus.PENDING
            update_fields.append("status")
        conflict.save(update_fields=update_fields)
    return conflict
