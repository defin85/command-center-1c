from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.operations.prometheus_metrics import (
    set_pool_run_command_outbox_lag_seconds,
    set_pool_run_command_outbox_retry_saturation,
)
from apps.operations.redis_client import redis_client

from .models import (
    PoolRun,
    PoolRunCommandLog,
    PoolRunCommandOutbox,
    PoolRunCommandOutboxIntent,
    PoolRunCommandOutboxStatus,
)


DEFAULT_OUTBOX_DISPATCH_BATCH_SIZE = 100
DEFAULT_OUTBOX_RETRY_BASE_SECONDS = 5
DEFAULT_OUTBOX_RETRY_CAP_SECONDS = 120
OUTBOX_RETRY_SATURATION_THRESHOLD_ATTEMPTS = 5


logger = logging.getLogger(__name__)


class PoolRunCommandOutboxConflict(ValueError):
    """Raised when an existing outbox entry has incompatible payload semantics."""

    def __init__(self, *, message: str, existing_entry: PoolRunCommandOutbox):
        super().__init__(message)
        self.existing_entry = existing_entry


@dataclass(frozen=True)
class PoolRunCommandOutboxEnqueueResult:
    entry: PoolRunCommandOutbox
    created: bool


@dataclass(frozen=True)
class PoolRunCommandOutboxDispatchStats:
    claimed: int
    dispatched: int
    failed: int


@dataclass(frozen=True)
class _ClaimedOutboxEntry:
    id: int
    stream_name: str
    message_payload: dict[str, Any]
    dispatch_attempts: int


def enqueue_pool_run_command_outbox_intent(
    *,
    run: PoolRun,
    intent_type: str,
    message_payload: dict[str, Any],
    command_log: PoolRunCommandLog | None = None,
    stream_name: str | None = None,
    next_retry_at: datetime | None = None,
) -> PoolRunCommandOutboxEnqueueResult:
    if intent_type not in PoolRunCommandOutboxIntent.values:
        raise ValueError(f"Unsupported intent_type '{intent_type}'")
    if not isinstance(message_payload, dict):
        raise ValueError("message_payload must be a JSON object")
    if command_log is not None and command_log.run_id != run.id:
        raise ValueError("command_log must belong to the same run")

    normalized_stream_name = str(stream_name or redis_client.STREAM_WORKFLOWS).strip()
    if not normalized_stream_name:
        raise ValueError("stream_name must be non-empty")

    retry_at = next_retry_at or timezone.now()

    with transaction.atomic():
        if command_log is not None:
            existing = (
                PoolRunCommandOutbox.objects.select_for_update()
                .filter(command_log=command_log, intent_type=intent_type)
                .first()
            )
            if existing is not None:
                if (
                    existing.run_id != run.id
                    or existing.stream_name != normalized_stream_name
                    or existing.message_payload != message_payload
                ):
                    raise PoolRunCommandOutboxConflict(
                        message="Outbox intent already exists with incompatible payload semantics.",
                        existing_entry=existing,
                    )
                return PoolRunCommandOutboxEnqueueResult(entry=existing, created=False)

        try:
            entry = PoolRunCommandOutbox.objects.create(
                run=run,
                tenant_id=run.tenant_id,
                command_log=command_log,
                intent_type=intent_type,
                stream_name=normalized_stream_name,
                message_payload=message_payload,
                next_retry_at=retry_at,
            )
            return PoolRunCommandOutboxEnqueueResult(entry=entry, created=True)
        except IntegrityError:
            # Handles uniqueness race on (command_log, intent_type).
            if command_log is None:
                raise
            existing = (
                PoolRunCommandOutbox.objects.select_for_update()
                .filter(command_log=command_log, intent_type=intent_type)
                .first()
            )
            if existing is None:
                raise
            if (
                existing.run_id != run.id
                or existing.stream_name != normalized_stream_name
                or existing.message_payload != message_payload
            ):
                raise PoolRunCommandOutboxConflict(
                    message="Outbox intent already exists with incompatible payload semantics.",
                    existing_entry=existing,
                )
            return PoolRunCommandOutboxEnqueueResult(entry=existing, created=False)


def dispatch_pool_run_command_outbox(
    *,
    batch_size: int = DEFAULT_OUTBOX_DISPATCH_BATCH_SIZE,
    now: datetime | None = None,
    retry_base_seconds: int = DEFAULT_OUTBOX_RETRY_BASE_SECONDS,
    retry_cap_seconds: int = DEFAULT_OUTBOX_RETRY_CAP_SECONDS,
) -> PoolRunCommandOutboxDispatchStats:
    dispatch_now = now or timezone.now()
    claimed = _claim_pending_entries(batch_size=max(1, int(batch_size)), now=dispatch_now)

    dispatched_count = 0
    failed_count = 0

    for claimed_entry in claimed:
        try:
            stream_message_id = redis_client.enqueue_operation_stream(
                claimed_entry.message_payload,
                stream_name=claimed_entry.stream_name,
            )
        except Exception as exc:
            failed_count += 1
            _mark_dispatch_failure(
                outbox_id=claimed_entry.id,
                dispatch_attempts=claimed_entry.dispatch_attempts,
                failed_at=dispatch_now,
                error=exc,
                retry_base_seconds=retry_base_seconds,
                retry_cap_seconds=retry_cap_seconds,
            )
            continue

        dispatched_count += 1
        _mark_dispatched(
            outbox_id=claimed_entry.id,
            stream_message_id=str(stream_message_id or ""),
            dispatched_at=dispatch_now,
        )

    _record_variant_a_sli_metrics(now=dispatch_now)

    return PoolRunCommandOutboxDispatchStats(
        claimed=len(claimed),
        dispatched=dispatched_count,
        failed=failed_count,
    )


def _claim_pending_entries(*, batch_size: int, now: datetime) -> list[_ClaimedOutboxEntry]:
    with transaction.atomic():
        rows = list(
            PoolRunCommandOutbox.objects.select_for_update(skip_locked=True)
            .filter(
                status=PoolRunCommandOutboxStatus.PENDING,
                next_retry_at__lte=now,
            )
            .order_by("id")[:batch_size]
        )
        if not rows:
            return []

        row_ids = [row.id for row in rows]
        PoolRunCommandOutbox.objects.filter(id__in=row_ids).update(
            dispatch_attempts=F("dispatch_attempts") + 1,
            last_attempted_at=now,
        )

        claimed_rows = list(
            PoolRunCommandOutbox.objects.filter(id__in=row_ids)
            .order_by("id")
            .values("id", "stream_name", "message_payload", "dispatch_attempts")
        )

    return [
        _ClaimedOutboxEntry(
            id=int(row["id"]),
            stream_name=str(row["stream_name"]),
            message_payload=row["message_payload"] if isinstance(row["message_payload"], dict) else {},
            dispatch_attempts=int(row["dispatch_attempts"]),
        )
        for row in claimed_rows
    ]


def _mark_dispatched(*, outbox_id: int, stream_message_id: str, dispatched_at: datetime) -> None:
    with transaction.atomic():
        outbox = (
            PoolRunCommandOutbox.objects.select_for_update()
            .filter(id=outbox_id, status=PoolRunCommandOutboxStatus.PENDING)
            .first()
        )
        if outbox is None:
            return

        outbox.status = PoolRunCommandOutboxStatus.DISPATCHED
        outbox.dispatched_at = dispatched_at
        outbox.stream_message_id = stream_message_id[:64]
        outbox.last_error_code = ""
        outbox.last_error = ""
        outbox.next_retry_at = dispatched_at
        outbox.save(
            update_fields=[
                "status",
                "dispatched_at",
                "stream_message_id",
                "last_error_code",
                "last_error",
                "next_retry_at",
                "updated_at",
            ]
        )


def _mark_dispatch_failure(
    *,
    outbox_id: int,
    dispatch_attempts: int,
    failed_at: datetime,
    error: Exception,
    retry_base_seconds: int,
    retry_cap_seconds: int,
) -> None:
    backoff_seconds = _calculate_retry_backoff_seconds(
        dispatch_attempts=dispatch_attempts,
        retry_base_seconds=retry_base_seconds,
        retry_cap_seconds=retry_cap_seconds,
    )
    error_code = type(error).__name__[:64]
    error_message = str(error or "").strip()[:4000]

    with transaction.atomic():
        outbox = (
            PoolRunCommandOutbox.objects.select_for_update()
            .filter(id=outbox_id, status=PoolRunCommandOutboxStatus.PENDING)
            .first()
        )
        if outbox is None:
            return

        outbox.last_error_code = error_code
        outbox.last_error = error_message
        outbox.next_retry_at = failed_at + timedelta(seconds=backoff_seconds)
        outbox.save(update_fields=["last_error_code", "last_error", "next_retry_at", "updated_at"])


def _record_variant_a_sli_metrics(*, now: datetime) -> None:
    try:
        pending_entries = PoolRunCommandOutbox.objects.filter(status=PoolRunCommandOutboxStatus.PENDING)
        total_pending = pending_entries.count()
        saturated_pending = pending_entries.filter(
            dispatch_attempts__gte=OUTBOX_RETRY_SATURATION_THRESHOLD_ATTEMPTS
        ).count()
        saturation_ratio = (saturated_pending / total_pending) if total_pending else 0.0
        set_pool_run_command_outbox_retry_saturation(
            saturation_ratio,
            saturated_pending=saturated_pending,
            total_pending=total_pending,
        )

        oldest_next_retry_at = (
            pending_entries.order_by("next_retry_at")
            .values_list("next_retry_at", flat=True)
            .first()
        )
        lag_seconds = 0.0
        if oldest_next_retry_at is not None:
            lag_seconds = max((now - oldest_next_retry_at).total_seconds(), 0.0)
        set_pool_run_command_outbox_lag_seconds(lag_seconds)
    except Exception as exc:
        logger.debug("Failed to record pool_run outbox SLI metrics: %s", exc)


def _calculate_retry_backoff_seconds(
    *,
    dispatch_attempts: int,
    retry_base_seconds: int,
    retry_cap_seconds: int,
) -> int:
    safe_base = max(1, int(retry_base_seconds))
    safe_cap = max(safe_base, int(retry_cap_seconds))
    exponent = max(0, int(dispatch_attempts) - 1)
    delay = safe_base * (2 ** exponent)
    return min(delay, safe_cap)
