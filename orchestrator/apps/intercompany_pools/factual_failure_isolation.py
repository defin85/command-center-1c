from __future__ import annotations

from typing import Any, Iterable

POOL_FACTUAL_FAILURE_ISOLATION_CONTRACT = "pool_factual_failure_isolation.v1"
POOL_FACTUAL_OPERATOR_DECISION_NONE = "none"
POOL_FACTUAL_OPERATOR_DECISION_PAUSE_INTAKE = "pause_intake"

POOL_FACTUAL_ALERT_FRESHNESS_LAG = "freshness_lag"
POOL_FACTUAL_ALERT_READ_BACKLOG = "read_backlog"
POOL_FACTUAL_ALERT_UNATTRIBUTED_VOLUME = "unattributed_volume"
POOL_FACTUAL_ALERT_LATE_CORRECTION_QUEUE = "late_correction_queue"


def build_pool_factual_failure_isolation_snapshot(
    *,
    alerts: Iterable[dict[str, Any]],
    operator_decision: str | None = None,
) -> dict[str, Any]:
    normalized_decision = _normalize_operator_decision(operator_decision)
    alert_codes = _normalize_alert_codes(alerts)
    read_projection_signals = sorted(
        alert_codes.intersection(
            {
                POOL_FACTUAL_ALERT_FRESHNESS_LAG,
                POOL_FACTUAL_ALERT_READ_BACKLOG,
            }
        )
    )
    reconcile_review_signals = sorted(
        alert_codes.intersection(
            {
                POOL_FACTUAL_ALERT_UNATTRIBUTED_VOLUME,
                POOL_FACTUAL_ALERT_LATE_CORRECTION_QUEUE,
            }
        )
    )

    intake_state = "available"
    intake_action = "keep_running"
    intake_reason = (
        "Backlog, staleness, and review alerts stay isolated from intake until an operator explicitly pauses intake."
    )
    if normalized_decision == POOL_FACTUAL_OPERATOR_DECISION_PAUSE_INTAKE:
        intake_state = "paused_by_operator"
        intake_action = "pause_and_hold_new_batch_intake"
        intake_reason = "Intake is paused only because an explicit operator decision was recorded."

    return {
        "contract_version": POOL_FACTUAL_FAILURE_ISOLATION_CONTRACT,
        "operator_decision": normalized_decision,
        "intake": {
            "state": intake_state,
            "auto_disable_allowed": False,
            "action": intake_action,
            "reason": intake_reason,
        },
        "read_projection": {
            "state": "degraded" if read_projection_signals else "available",
            "signals": read_projection_signals,
            "action": (
                "raise_alerts_and_drain_backlog"
                if read_projection_signals
                else "monitor_only"
            ),
        },
        "reconcile_review": {
            "state": "degraded" if reconcile_review_signals else "available",
            "signals": reconcile_review_signals,
            "action": (
                "raise_alerts_and_process_review_queue"
                if reconcile_review_signals
                else "monitor_only"
            ),
        },
    }


def _normalize_operator_decision(raw_value: str | None) -> str:
    normalized = str(raw_value or "").strip().lower()
    if normalized == POOL_FACTUAL_OPERATOR_DECISION_PAUSE_INTAKE:
        return POOL_FACTUAL_OPERATOR_DECISION_PAUSE_INTAKE
    return POOL_FACTUAL_OPERATOR_DECISION_NONE


def _normalize_alert_codes(alerts: Iterable[dict[str, Any]]) -> set[str]:
    codes: set[str] = set()
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        code = str(alert.get("code") or "").strip().lower()
        if code:
            codes.add(code)
    return codes


__all__ = [
    "POOL_FACTUAL_FAILURE_ISOLATION_CONTRACT",
    "POOL_FACTUAL_OPERATOR_DECISION_NONE",
    "POOL_FACTUAL_OPERATOR_DECISION_PAUSE_INTAKE",
    "build_pool_factual_failure_isolation_snapshot",
]
