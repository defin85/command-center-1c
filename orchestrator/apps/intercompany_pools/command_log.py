from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import (
    PoolRun,
    PoolRunCommandCasOutcome,
    PoolRunCommandLog,
    PoolRunCommandResultClass,
    PoolRunCommandType,
)


class PoolRunCommandIdempotencyConflict(ValueError):
    """Raised when a key is reused for incompatible command semantics."""

    def __init__(self, *, message: str, existing_entry: PoolRunCommandLog):
        super().__init__(message)
        self.existing_entry = existing_entry


@dataclass(frozen=True)
class PoolRunCommandLogWriteResult:
    entry: PoolRunCommandLog
    replayed: bool


def record_pool_run_command_outcome(
    *,
    run: PoolRun,
    command_type: str,
    idempotency_key: str,
    command_fingerprint: str,
    result_class: str,
    response_status_code: int,
    response_snapshot: dict[str, Any] | None,
    cas_outcome: str = PoolRunCommandCasOutcome.NOT_APPLICABLE,
    created_by=None,
    now: datetime | None = None,
) -> PoolRunCommandLogWriteResult:
    if command_type not in PoolRunCommandType.values:
        raise ValueError(f"Unsupported command_type '{command_type}'")
    if result_class not in PoolRunCommandResultClass.values:
        raise ValueError(f"Unsupported result_class '{result_class}'")
    if cas_outcome not in PoolRunCommandCasOutcome.values:
        raise ValueError(f"Unsupported cas_outcome '{cas_outcome}'")

    normalized_key = str(idempotency_key or "").strip()
    if not normalized_key:
        raise ValueError("Idempotency key must be non-empty")
    normalized_fingerprint = str(command_fingerprint or "").strip()

    replay_time = now or timezone.now()
    payload_snapshot = response_snapshot if isinstance(response_snapshot, dict) else {}

    with transaction.atomic():
        existing_cross_command = (
            PoolRunCommandLog.objects.select_for_update()
            .filter(run=run, idempotency_key=normalized_key)
            .exclude(command_type=command_type)
            .order_by("id")
            .first()
        )
        if existing_cross_command is not None:
            raise PoolRunCommandIdempotencyConflict(
                message="Idempotency key already used for another command type.",
                existing_entry=existing_cross_command,
            )

        existing = (
            PoolRunCommandLog.objects.select_for_update()
            .filter(
                run=run,
                command_type=command_type,
                idempotency_key=normalized_key,
            )
            .first()
        )
        if existing is not None:
            if existing.command_fingerprint != normalized_fingerprint:
                raise PoolRunCommandIdempotencyConflict(
                    message="Idempotency key reused with incompatible command fingerprint.",
                    existing_entry=existing,
                )
            return _mark_replay(existing=existing, replay_time=replay_time)

        try:
            created = PoolRunCommandLog.objects.create(
                run=run,
                tenant_id=run.tenant_id,
                command_type=command_type,
                idempotency_key=normalized_key,
                command_fingerprint=normalized_fingerprint,
                result_class=result_class,
                cas_outcome=cas_outcome,
                response_status_code=response_status_code,
                response_snapshot=payload_snapshot,
                created_by=created_by,
            )
            return PoolRunCommandLogWriteResult(entry=created, replayed=False)
        except IntegrityError:
            # Handles race on the uniqueness scope (run, command_type, idempotency_key).
            existing = (
                PoolRunCommandLog.objects.select_for_update()
                .filter(
                    run=run,
                    command_type=command_type,
                    idempotency_key=normalized_key,
                )
                .first()
            )
            if existing is None:
                raise
            if existing.command_fingerprint != normalized_fingerprint:
                raise PoolRunCommandIdempotencyConflict(
                    message="Idempotency key reused with incompatible command fingerprint.",
                    existing_entry=existing,
                )
            return _mark_replay(existing=existing, replay_time=replay_time)


def cleanup_expired_pool_run_command_logs(*, now: datetime | None = None, batch_size: int = 1000) -> int:
    cutoff = now or timezone.now()
    chunk_size = max(1, int(batch_size))
    deleted_total = 0

    while True:
        ids = list(
            PoolRunCommandLog.objects.filter(expires_at__lte=cutoff)
            .order_by("id")
            .values_list("id", flat=True)[:chunk_size]
        )
        if not ids:
            break
        deleted_count, _ = PoolRunCommandLog.objects.filter(id__in=ids).delete()
        deleted_total += deleted_count
    return deleted_total


def _mark_replay(*, existing: PoolRunCommandLog, replay_time: datetime) -> PoolRunCommandLogWriteResult:
    PoolRunCommandLog.objects.filter(id=existing.id).update(
        replay_count=F("replay_count") + 1,
        last_replayed_at=replay_time,
    )
    existing.refresh_from_db(fields=["replay_count", "last_replayed_at"])
    return PoolRunCommandLogWriteResult(entry=existing, replayed=True)
