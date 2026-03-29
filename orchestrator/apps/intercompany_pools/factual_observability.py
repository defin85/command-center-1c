from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.operations.prometheus_metrics import (
    set_pool_factual_actionable_alerts,
    set_pool_factual_read_metrics,
    set_pool_factual_review_metrics,
)

from .factual_failure_isolation import build_pool_factual_failure_isolation_snapshot
from .factual_scheduling import resolve_factual_rollout_envelope
from .models import (
    PoolFactualLane,
    PoolFactualReviewItem,
    PoolFactualReviewReason,
    PoolFactualReviewStatus,
    PoolFactualSyncCheckpoint,
)


POOL_FACTUAL_ALERT_FRESHNESS_LAG = "freshness_lag"
POOL_FACTUAL_ALERT_READ_BACKLOG = "read_backlog"
POOL_FACTUAL_ALERT_UNATTRIBUTED_VOLUME = "unattributed_volume"
POOL_FACTUAL_ALERT_LATE_CORRECTION_QUEUE = "late_correction_queue"

FACTUAL_FRESHNESS_WARNING_MULTIPLIER = 1
FACTUAL_FRESHNESS_CRITICAL_MULTIPLIER = 5
FACTUAL_FRESHNESS_CRITICAL_FLOOR_SECONDS = 600


def record_pool_factual_rollout_telemetry(*, now: datetime | None = None) -> dict[str, Any]:
    timestamp = _ensure_aware_datetime(now or timezone.now())
    read_summary = _build_factual_read_summary(now=timestamp)
    review_summary = _build_factual_review_summary()
    alerts = _build_actionable_alerts(
        read_summary=read_summary,
        review_summary=review_summary,
    )
    failure_isolation = build_pool_factual_failure_isolation_snapshot(alerts=alerts)

    set_pool_factual_read_metrics(
        freshness_lag_seconds=read_summary["freshness_lag_seconds"],
        backlog_total=read_summary["backlog_total"],
        source_state_totals=read_summary["source_state_totals"],
    )
    set_pool_factual_review_metrics(
        pending_totals=review_summary["pending_totals"],
        pending_amounts_with_vat=review_summary["pending_amounts_with_vat"],
        attention_required_totals=review_summary["attention_required_totals"],
    )
    set_pool_factual_actionable_alerts(alerts=alerts)

    return {
        "generated_at": timestamp.isoformat(),
        "read_summary": read_summary,
        "review_summary": review_summary,
        "alerts": alerts,
        "failure_isolation": failure_isolation,
    }


def build_pool_factual_read_summary(
    *,
    checkpoints: Iterable[PoolFactualSyncCheckpoint],
    now: datetime,
) -> dict[str, Any]:
    checkpoint_list = list(checkpoints)
    source_state_totals: Counter[str] = Counter()
    backlog_total = 0
    freshness_lag_seconds = 0.0
    max_freshness_target_seconds = 0

    for checkpoint in checkpoint_list:
        metadata = checkpoint.metadata if isinstance(checkpoint.metadata, dict) else {}
        source_state = str(metadata.get("source_availability") or "available").strip().lower() or "available"
        freshness_state = str(metadata.get("freshness_state") or "").strip().lower()
        freshness_target_seconds = _coerce_positive_int(metadata.get("freshness_target_seconds"), default=120)
        reference_at = _resolve_freshness_reference_at(checkpoint=checkpoint)

        source_state_totals[source_state] += 1
        max_freshness_target_seconds = max(max_freshness_target_seconds, freshness_target_seconds)

        checkpoint_lag_seconds = 0.0
        if reference_at is None:
            backlog_total += 1
            checkpoint_lag_seconds = float(freshness_target_seconds)
        else:
            due_at = reference_at + timedelta(seconds=freshness_target_seconds)
            checkpoint_lag_seconds = max((now - due_at).total_seconds(), 0.0)
            if checkpoint_lag_seconds > 0:
                backlog_total += 1

        if freshness_state == "stale" and checkpoint_lag_seconds <= 0:
            backlog_total += 1
        freshness_lag_seconds = max(freshness_lag_seconds, checkpoint_lag_seconds)

    return {
        "checkpoint_total": len(checkpoint_list),
        "freshness_lag_seconds": freshness_lag_seconds,
        "backlog_total": backlog_total,
        "source_state_totals": dict(source_state_totals),
        "max_freshness_target_seconds": max_freshness_target_seconds,
    }


def _build_factual_read_summary(*, now: datetime) -> dict[str, Any]:
    return build_pool_factual_read_summary(
        checkpoints=PoolFactualSyncCheckpoint.objects.filter(lane=PoolFactualLane.READ),
        now=now,
    )


def _build_factual_review_summary() -> dict[str, Any]:
    pending_items = list(
        PoolFactualReviewItem.objects.filter(status=PoolFactualReviewStatus.PENDING)
    )
    pending_totals: Counter[str] = Counter()
    pending_amounts: dict[str, Decimal] = {}
    attention_required_totals: Counter[str] = Counter()

    for item in pending_items:
        reason = str(item.reason or "unknown").strip().lower() or "unknown"
        pending_totals[reason] += 1
        pending_amounts[reason] = pending_amounts.get(reason, Decimal("0.00")) + _extract_review_amount_with_vat(item)
        if item.reason == PoolFactualReviewReason.LATE_CORRECTION:
            attention_required_totals[reason] += 1

    return {
        "pending_totals": dict(pending_totals),
        "pending_amounts_with_vat": {
            reason: float(amount)
            for reason, amount in pending_amounts.items()
        },
        "attention_required_totals": dict(attention_required_totals),
    }


def _build_actionable_alerts(
    *,
    read_summary: dict[str, Any],
    review_summary: dict[str, Any],
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    source_state_totals = dict(read_summary.get("source_state_totals") or {})
    max_target_seconds = max(120, int(read_summary.get("max_freshness_target_seconds") or 120))
    freshness_lag_seconds = float(read_summary.get("freshness_lag_seconds") or 0.0)
    backlog_total = int(read_summary.get("backlog_total") or 0)
    rollout_envelope = resolve_factual_rollout_envelope()

    blocked_total = int(source_state_totals.get("blocked_external_sessions", 0) or 0)
    unavailable_total = int(source_state_totals.get("unavailable", 0) or 0)
    maintenance_total = int(source_state_totals.get("maintenance", 0) or 0)
    freshness_critical_threshold = max(
        FACTUAL_FRESHNESS_CRITICAL_FLOOR_SECONDS,
        max_target_seconds * FACTUAL_FRESHNESS_CRITICAL_MULTIPLIER,
    )
    freshness_warning_threshold = max_target_seconds * FACTUAL_FRESHNESS_WARNING_MULTIPLIER

    if blocked_total > 0 or unavailable_total > 0 or maintenance_total > 0 or freshness_lag_seconds > freshness_warning_threshold:
        severity = "warning"
        if blocked_total > 0 or unavailable_total > 0 or freshness_lag_seconds >= freshness_critical_threshold:
            severity = "critical"
        alerts.append(
            {
                "code": POOL_FACTUAL_ALERT_FRESHNESS_LAG,
                "severity": severity,
                "summary": (
                    f"Freshness lag is {freshness_lag_seconds:.0f}s with source states "
                    f"{_format_state_totals(source_state_totals)}."
                ),
                "action": (
                    "Inspect factual read checkpoints and source availability before widening rollout; "
                    "keep intake enabled unless the operator explicitly stops it."
                ),
            }
        )

    if backlog_total > 0:
        severity = "critical" if backlog_total >= int(rollout_envelope.global_read_cap) else "warning"
        alerts.append(
            {
                "code": POOL_FACTUAL_ALERT_READ_BACKLOG,
                "severity": severity,
                "summary": (
                    f"Read backlog has {backlog_total} overdue checkpoint(s); rollout global cap is "
                    f"{rollout_envelope.global_read_cap}."
                ),
                "action": (
                    "Drain overdue read checkpoints or reduce cohort size; backlog must not silently disable intake."
                ),
            }
        )

    unattributed_total = int(
        dict(review_summary.get("pending_totals") or {}).get(PoolFactualReviewReason.UNATTRIBUTED, 0) or 0
    )
    unattributed_amount = float(
        dict(review_summary.get("pending_amounts_with_vat") or {}).get(PoolFactualReviewReason.UNATTRIBUTED, 0.0)
        or 0.0
    )
    if unattributed_total > 0:
        alerts.append(
            {
                "code": POOL_FACTUAL_ALERT_UNATTRIBUTED_VOLUME,
                "severity": "warning",
                "summary": (
                    f"Unattributed queue contains {unattributed_total} document(s) / {unattributed_amount:.2f} with VAT."
                ),
                "action": (
                    "Review and attribute manual documents in the factual workspace before widening the rollout cohort."
                ),
            }
        )

    late_correction_total = int(
        dict(review_summary.get("pending_totals") or {}).get(PoolFactualReviewReason.LATE_CORRECTION, 0) or 0
    )
    late_correction_amount = float(
        dict(review_summary.get("pending_amounts_with_vat") or {}).get(PoolFactualReviewReason.LATE_CORRECTION, 0.0)
        or 0.0
    )
    if late_correction_total > 0:
        alerts.append(
            {
                "code": POOL_FACTUAL_ALERT_LATE_CORRECTION_QUEUE,
                "severity": "critical",
                "summary": (
                    f"Late-correction queue contains {late_correction_total} frozen-quarter item(s) / "
                    f"{late_correction_amount:.2f} with VAT."
                ),
                "action": (
                    "Run manual reconcile for frozen-quarter corrections before period close or further rollout."
                ),
            }
        )

    return alerts


def _resolve_freshness_reference_at(*, checkpoint: PoolFactualSyncCheckpoint) -> datetime | None:
    metadata = checkpoint.metadata if isinstance(checkpoint.metadata, dict) else {}
    freshness_at = _parse_optional_datetime(metadata.get("freshness_at"))
    if freshness_at is not None:
        return freshness_at
    if checkpoint.last_synced_at is not None:
        return _ensure_aware_datetime(checkpoint.last_synced_at)
    return None


def _extract_review_amount_with_vat(item: PoolFactualReviewItem) -> Decimal:
    delta_payload = item.delta_payload if isinstance(item.delta_payload, dict) else {}
    if not delta_payload:
        metadata = item.metadata if isinstance(item.metadata, dict) else {}
        nested_delta_payload = metadata.get("delta_payload")
        if isinstance(nested_delta_payload, dict):
            delta_payload = nested_delta_payload
    for field_name in ("amount_with_vat", "open_balance", "delta_amount", "total_amount_with_vat"):
        value = delta_payload.get(field_name)
        if value is None:
            continue
        try:
            return Decimal(str(value)).copy_abs()
        except (InvalidOperation, ValueError):
            continue
    return Decimal("0.00")


def _format_state_totals(source_state_totals: dict[str, int]) -> str:
    parts = [
        f"{state}={int(total or 0)}"
        for state, total in sorted(source_state_totals.items())
        if int(total or 0) > 0
    ]
    return ", ".join(parts) if parts else "available=0"


def _coerce_positive_int(raw_value: Any, *, default: int) -> int:
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _parse_optional_datetime(raw_value: Any) -> datetime | None:
    if isinstance(raw_value, datetime):
        return _ensure_aware_datetime(raw_value)
    parsed = parse_datetime(str(raw_value or "").strip())
    if parsed is None:
        return None
    return _ensure_aware_datetime(parsed)


def _ensure_aware_datetime(value: datetime) -> datetime:
    if timezone.is_naive(value):
        return timezone.make_aware(value, dt_timezone.utc)
    return value.astimezone(dt_timezone.utc)


__all__ = [
    "POOL_FACTUAL_ALERT_FRESHNESS_LAG",
    "POOL_FACTUAL_ALERT_LATE_CORRECTION_QUEUE",
    "POOL_FACTUAL_ALERT_READ_BACKLOG",
    "POOL_FACTUAL_ALERT_UNATTRIBUTED_VOLUME",
    "record_pool_factual_rollout_telemetry",
]
