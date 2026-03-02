from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from django.db import transaction
from django.utils import timezone

from .master_data_sync_conflicts import MasterDataSyncConflictError
from .master_data_sync_invariants import build_inbound_dedupe_fingerprint
from .models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncCheckpoint,
    PoolMasterDataSyncCheckpointStatus,
)


SELECT_CHANGES_UNEXPECTED_ERROR_CODE = "SELECT_CHANGES_UNEXPECTED"
NOTIFY_CHANGES_UNEXPECTED_ERROR_CODE = "NOTIFY_CHANGES_UNEXPECTED"


class InboundPollerTransportError(RuntimeError):
    def __init__(self, *, code: str, detail: str) -> None:
        self.code = str(code or "").strip() or "SELECT_CHANGES_FAILED"
        self.detail = str(detail or "").strip() or "inbound select changes failed"
        super().__init__(f"{self.code}: {self.detail}")


@dataclass(frozen=True)
class MasterDataSyncInboundChange:
    origin_system: str
    origin_event_id: str
    canonical_id: str
    entity_type: str
    payload: dict[str, Any]
    payload_fingerprint: str


@dataclass(frozen=True)
class MasterDataSyncSelectChangesResult:
    changes: list[MasterDataSyncInboundChange]
    source_checkpoint_token: str
    next_checkpoint_token: str


@dataclass(frozen=True)
class MasterDataSyncInboundProcessResult:
    polled: int
    applied: int
    duplicates: int
    ack_scheduled: bool
    next_checkpoint_token: str


def process_master_data_sync_inbound_batch(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    select_changes: Callable[..., MasterDataSyncSelectChangesResult],
    apply_change: Callable[..., Any],
    notify_changes_received: Callable[..., Any],
    select_changes_kwargs: Mapping[str, Any] | None = None,
    notify_changes_received_kwargs: Mapping[str, Any] | None = None,
    max_dedupe_history_size: int = 512,
) -> MasterDataSyncInboundProcessResult:
    normalized_entity_type = _normalize_entity_type(entity_type=entity_type)
    poll_result = poll_master_data_sync_inbound_changes(
        tenant_id=str(tenant_id or "").strip(),
        database_id=str(database_id or "").strip(),
        entity_type=normalized_entity_type,
        select_changes=select_changes,
        select_changes_kwargs=select_changes_kwargs,
    )
    try:
        applied, duplicates = _apply_inbound_batch_with_dedupe(
            tenant_id=str(tenant_id or "").strip(),
            database_id=str(database_id or "").strip(),
            entity_type=normalized_entity_type,
            poll_result=poll_result,
            apply_change=apply_change,
            max_dedupe_history_size=max_dedupe_history_size,
        )
    except MasterDataSyncConflictError as exc:
        _mark_checkpoint_error_by_scope(
            tenant_id=str(tenant_id or "").strip(),
            database_id=str(database_id or "").strip(),
            entity_type=normalized_entity_type,
            error_code=exc.code,
            error_detail=exc.detail,
            metadata_timestamp_key="last_apply_error_at",
        )
        raise
    except Exception as exc:  # noqa: BLE001
        _mark_checkpoint_error_by_scope(
            tenant_id=str(tenant_id or "").strip(),
            database_id=str(database_id or "").strip(),
            entity_type=normalized_entity_type,
            error_code="INBOUND_APPLY_FAILED",
            error_detail=str(exc) or "inbound apply failed",
            metadata_timestamp_key="last_apply_error_at",
        )
        raise
    ack_scheduled = schedule_master_data_sync_notify_changes_received_after_commit(
        tenant_id=str(tenant_id or "").strip(),
        database_id=str(database_id or "").strip(),
        entity_type=normalized_entity_type,
        notify_changes_received=notify_changes_received,
        notify_changes_received_kwargs=notify_changes_received_kwargs,
    )
    return MasterDataSyncInboundProcessResult(
        polled=len(poll_result.changes),
        applied=applied,
        duplicates=duplicates,
        ack_scheduled=ack_scheduled,
        next_checkpoint_token=poll_result.next_checkpoint_token,
    )


def schedule_master_data_sync_notify_changes_received_after_commit(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    notify_changes_received: Callable[..., Any],
    notify_changes_received_kwargs: Mapping[str, Any] | None = None,
) -> bool:
    normalized_entity_type = _normalize_entity_type(entity_type=entity_type)
    checkpoint = _get_or_create_checkpoint(
        tenant_id=str(tenant_id or "").strip(),
        database_id=str(database_id or "").strip(),
        entity_type=normalized_entity_type,
    )
    source_checkpoint_token, pending_checkpoint_token = _resolve_checkpoint_ack_tokens(checkpoint=checkpoint)
    if not pending_checkpoint_token:
        return False

    kwargs = dict(notify_changes_received_kwargs or {})

    def _run_acknowledge() -> None:
        _acknowledge_checkpoint_pending_token(
            checkpoint_id=str(checkpoint.id),
            source_checkpoint_token=source_checkpoint_token,
            pending_checkpoint_token=pending_checkpoint_token,
            notify_changes_received=notify_changes_received,
            notify_changes_received_kwargs=kwargs,
        )

    transaction.on_commit(_run_acknowledge)
    return True


def poll_master_data_sync_inbound_changes(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    select_changes: Callable[..., MasterDataSyncSelectChangesResult],
    select_changes_kwargs: Mapping[str, Any] | None = None,
) -> MasterDataSyncSelectChangesResult:
    normalized_entity_type = _normalize_entity_type(entity_type=entity_type)
    checkpoint = _get_or_create_checkpoint(
        tenant_id=str(tenant_id or "").strip(),
        database_id=str(database_id or "").strip(),
        entity_type=normalized_entity_type,
    )
    checkpoint_token = str(checkpoint.checkpoint_token or "")

    kwargs = dict(select_changes_kwargs or {})
    try:
        raw_result = select_changes(
            checkpoint_token=checkpoint_token,
            tenant_id=str(tenant_id or "").strip(),
            database_id=str(database_id or "").strip(),
            entity_type=normalized_entity_type,
            **kwargs,
        )
        result = _normalize_select_changes_result(
            result=raw_result,
            checkpoint_token=checkpoint_token,
        )
    except InboundPollerTransportError as exc:
        _mark_checkpoint_error(checkpoint=checkpoint, error_code=exc.code, error_detail=exc.detail)
        raise
    except Exception as exc:  # noqa: BLE001
        wrapped = InboundPollerTransportError(
            code=SELECT_CHANGES_UNEXPECTED_ERROR_CODE,
            detail=str(exc) or "unexpected inbound select changes failure",
        )
        _mark_checkpoint_error(checkpoint=checkpoint, error_code=wrapped.code, error_detail=wrapped.detail)
        raise wrapped from exc

    _mark_checkpoint_polled(
        checkpoint=checkpoint,
        source_checkpoint_token=result.source_checkpoint_token,
        next_checkpoint_token=result.next_checkpoint_token,
    )
    return result


def _normalize_entity_type(*, entity_type: str) -> str:
    normalized = str(entity_type or "").strip()
    if normalized not in set(PoolMasterDataEntityType.values):
        raise ValueError(f"Unsupported master-data entity_type '{entity_type}'")
    return normalized


def _get_or_create_checkpoint(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
) -> PoolMasterDataSyncCheckpoint:
    with transaction.atomic():
        checkpoint, _ = PoolMasterDataSyncCheckpoint.objects.select_for_update().get_or_create(
            tenant_id=tenant_id,
            database_id=database_id,
            entity_type=entity_type,
            defaults={
                "status": PoolMasterDataSyncCheckpointStatus.ACTIVE,
                "checkpoint_token": "",
            },
        )
    return checkpoint


def _normalize_select_changes_result(
    *,
    result: MasterDataSyncSelectChangesResult,
    checkpoint_token: str,
) -> MasterDataSyncSelectChangesResult:
    if not isinstance(result, MasterDataSyncSelectChangesResult):
        raise InboundPollerTransportError(
            code="SELECT_CHANGES_INVALID_RESULT",
            detail="SelectChanges callback must return MasterDataSyncSelectChangesResult",
        )

    return MasterDataSyncSelectChangesResult(
        changes=list(result.changes or []),
        source_checkpoint_token=str(result.source_checkpoint_token or checkpoint_token),
        next_checkpoint_token=str(result.next_checkpoint_token or checkpoint_token),
    )


def _apply_inbound_batch_with_dedupe(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    poll_result: MasterDataSyncSelectChangesResult,
    apply_change: Callable[..., Any],
    max_dedupe_history_size: int,
) -> tuple[int, int]:
    now = timezone.now()
    safe_history_size = max(1, int(max_dedupe_history_size))
    with transaction.atomic():
        checkpoint = PoolMasterDataSyncCheckpoint.objects.select_for_update().get(
            tenant_id=tenant_id,
            database_id=database_id,
            entity_type=entity_type,
        )
        dedupe_history = _read_dedupe_history(checkpoint=checkpoint)
        dedupe_set = set(dedupe_history)
        applied = 0
        duplicates = 0

        for change in poll_result.changes:
            dedupe_fingerprint = build_inbound_dedupe_fingerprint(
                tenant_id=tenant_id,
                database_id=database_id,
                entity_type=entity_type,
                origin_system=str(change.origin_system or ""),
                origin_event_id=str(change.origin_event_id or ""),
                payload_fingerprint=str(change.payload_fingerprint or ""),
            )
            if dedupe_fingerprint in dedupe_set:
                duplicates += 1
                continue

            apply_change(
                change=change,
                tenant_id=tenant_id,
                database_id=database_id,
                entity_type=entity_type,
                dedupe_fingerprint=dedupe_fingerprint,
            )

            dedupe_history.append(dedupe_fingerprint)
            dedupe_set.add(dedupe_fingerprint)
            checkpoint.last_origin_event_id = str(change.origin_event_id or "")
            checkpoint.last_applied_at = now
            applied += 1

        metadata = dict(checkpoint.metadata or {})
        metadata["inbound_applied_fingerprints"] = dedupe_history[-safe_history_size:]
        checkpoint.metadata = metadata
        checkpoint.status = PoolMasterDataSyncCheckpointStatus.ACTIVE
        checkpoint.last_error_code = ""
        checkpoint.last_error = ""
        checkpoint.save(
            update_fields=[
                "last_origin_event_id",
                "last_applied_at",
                "metadata",
                "status",
                "last_error_code",
                "last_error",
                "updated_at",
            ]
        )

    return applied, duplicates


def _read_dedupe_history(*, checkpoint: PoolMasterDataSyncCheckpoint) -> list[str]:
    metadata = checkpoint.metadata if isinstance(checkpoint.metadata, dict) else {}
    raw_history = metadata.get("inbound_applied_fingerprints")
    if not isinstance(raw_history, list):
        return []
    history: list[str] = []
    for value in raw_history:
        token = str(value or "").strip()
        if token:
            history.append(token)
    return history


def _resolve_checkpoint_ack_tokens(*, checkpoint: PoolMasterDataSyncCheckpoint) -> tuple[str, str]:
    metadata = checkpoint.metadata if isinstance(checkpoint.metadata, dict) else {}
    source_checkpoint_token = str(metadata.get("source_checkpoint_token") or checkpoint.checkpoint_token or "")
    pending_checkpoint_token = str(metadata.get("pending_checkpoint_token") or "")
    return source_checkpoint_token, pending_checkpoint_token


def _acknowledge_checkpoint_pending_token(
    *,
    checkpoint_id: str,
    source_checkpoint_token: str,
    pending_checkpoint_token: str,
    notify_changes_received: Callable[..., Any],
    notify_changes_received_kwargs: Mapping[str, Any],
) -> None:
    with transaction.atomic():
        checkpoint = PoolMasterDataSyncCheckpoint.objects.select_for_update().get(id=checkpoint_id)
        current_source_checkpoint_token, current_pending_checkpoint_token = _resolve_checkpoint_ack_tokens(
            checkpoint=checkpoint
        )
        source_token = str(source_checkpoint_token or current_source_checkpoint_token or "")
        pending_token = str(pending_checkpoint_token or current_pending_checkpoint_token or "")
        if not pending_token:
            return
        if pending_token != current_pending_checkpoint_token:
            return
        checkpoint_pk = str(checkpoint.id)
        tenant_id = str(checkpoint.tenant_id)
        database_id = str(checkpoint.database_id)
        entity_type = str(checkpoint.entity_type)

    kwargs = dict(notify_changes_received_kwargs or {})
    try:
        notify_changes_received(
            checkpoint_token=source_token,
            next_checkpoint_token=pending_token,
            tenant_id=tenant_id,
            database_id=database_id,
            entity_type=entity_type,
            **kwargs,
        )
    except InboundPollerTransportError as exc:
        _mark_checkpoint_error_by_id(
            checkpoint_id=checkpoint_pk,
            error_code=exc.code,
            error_detail=exc.detail,
            metadata_timestamp_key="last_notify_error_at",
        )
        raise
    except Exception as exc:  # noqa: BLE001
        wrapped = InboundPollerTransportError(
            code=NOTIFY_CHANGES_UNEXPECTED_ERROR_CODE,
            detail=str(exc) or "unexpected notify changes failure",
        )
        _mark_checkpoint_error_by_id(
            checkpoint_id=checkpoint_pk,
            error_code=wrapped.code,
            error_detail=wrapped.detail,
            metadata_timestamp_key="last_notify_error_at",
        )
        raise wrapped from exc

    _mark_checkpoint_acknowledged_if_pending(
        checkpoint_id=checkpoint_pk,
        acknowledged_checkpoint_token=pending_token,
    )


def _mark_checkpoint_polled(
    *,
    checkpoint: PoolMasterDataSyncCheckpoint,
    source_checkpoint_token: str,
    next_checkpoint_token: str,
) -> None:
    metadata = dict(checkpoint.metadata or {})
    metadata["source_checkpoint_token"] = str(source_checkpoint_token or "")
    metadata["pending_checkpoint_token"] = str(next_checkpoint_token or "")
    metadata["last_polled_at"] = timezone.now().isoformat()
    checkpoint.status = PoolMasterDataSyncCheckpointStatus.ACTIVE
    checkpoint.last_error_code = ""
    checkpoint.last_error = ""
    checkpoint.metadata = metadata
    checkpoint.save(update_fields=["status", "last_error_code", "last_error", "metadata", "updated_at"])


def _mark_checkpoint_acknowledged_if_pending(
    *,
    checkpoint_id: str,
    acknowledged_checkpoint_token: str,
) -> None:
    with transaction.atomic():
        checkpoint = PoolMasterDataSyncCheckpoint.objects.select_for_update().get(id=checkpoint_id)
        _source_checkpoint_token, current_pending_checkpoint_token = _resolve_checkpoint_ack_tokens(checkpoint=checkpoint)
        next_token = str(acknowledged_checkpoint_token or "")
        if not next_token:
            return
        if next_token != current_pending_checkpoint_token:
            return

        metadata = dict(checkpoint.metadata or {})
        metadata.pop("pending_checkpoint_token", None)
        metadata["source_checkpoint_token"] = next_token
        metadata["last_acknowledged_at"] = timezone.now().isoformat()
        checkpoint.checkpoint_token = next_token
        checkpoint.status = PoolMasterDataSyncCheckpointStatus.ACTIVE
        checkpoint.last_error_code = ""
        checkpoint.last_error = ""
        checkpoint.metadata = metadata
        checkpoint.last_applied_at = timezone.now()
        checkpoint.save(
            update_fields=[
                "checkpoint_token",
                "status",
                "last_error_code",
                "last_error",
                "metadata",
                "last_applied_at",
                "updated_at",
            ]
        )


def _mark_checkpoint_error_by_id(
    *,
    checkpoint_id: str,
    error_code: str,
    error_detail: str,
    metadata_timestamp_key: str = "last_poll_error_at",
) -> None:
    with transaction.atomic():
        checkpoint = PoolMasterDataSyncCheckpoint.objects.select_for_update().get(id=checkpoint_id)
        _mark_checkpoint_error(
            checkpoint=checkpoint,
            error_code=error_code,
            error_detail=error_detail,
            metadata_timestamp_key=metadata_timestamp_key,
        )


def _mark_checkpoint_error_by_scope(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    error_code: str,
    error_detail: str,
    metadata_timestamp_key: str = "last_poll_error_at",
) -> None:
    with transaction.atomic():
        checkpoint = PoolMasterDataSyncCheckpoint.objects.select_for_update().get(
            tenant_id=tenant_id,
            database_id=database_id,
            entity_type=entity_type,
        )
        _mark_checkpoint_error(
            checkpoint=checkpoint,
            error_code=error_code,
            error_detail=error_detail,
            metadata_timestamp_key=metadata_timestamp_key,
        )


def _mark_checkpoint_error(
    *,
    checkpoint: PoolMasterDataSyncCheckpoint,
    error_code: str,
    error_detail: str,
    metadata_timestamp_key: str = "last_poll_error_at",
) -> None:
    metadata = dict(checkpoint.metadata or {})
    metadata[str(metadata_timestamp_key or "last_poll_error_at")] = timezone.now().isoformat()
    checkpoint.status = PoolMasterDataSyncCheckpointStatus.ERROR
    checkpoint.last_error_code = str(error_code or "SELECT_CHANGES_FAILED")
    checkpoint.last_error = str(error_detail or "inbound select changes failed")
    checkpoint.metadata = metadata
    checkpoint.save(update_fields=["status", "last_error_code", "last_error", "metadata", "updated_at"])
