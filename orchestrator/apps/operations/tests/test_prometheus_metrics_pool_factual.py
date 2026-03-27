from __future__ import annotations

from apps.operations.prometheus_metrics import (
    pool_factual_actionable_alert_state,
    pool_factual_read_backlog_total,
    pool_factual_read_freshness_lag_seconds,
    pool_factual_read_source_state_total,
    pool_factual_review_attention_required_total,
    pool_factual_review_pending_amount_with_vat,
    pool_factual_review_pending_total,
    set_pool_factual_actionable_alerts,
    set_pool_factual_read_metrics,
    set_pool_factual_review_metrics,
)


def _gauge_value(gauge) -> float:
    return float(gauge._value.get())


def _gauge_vec_value(gauge_vec, **labels: str) -> float:
    return float(gauge_vec.labels(**labels)._value.get())


def test_set_pool_factual_read_metrics_sets_freshness_backlog_and_source_states() -> None:
    set_pool_factual_read_metrics(
        freshness_lag_seconds=245.5,
        backlog_total=3,
        source_state_totals={
            "available": 4,
            "blocked_external_sessions": 2,
        },
    )

    assert _gauge_value(pool_factual_read_freshness_lag_seconds) == 245.5
    assert _gauge_value(pool_factual_read_backlog_total) == 3.0
    assert _gauge_vec_value(
        pool_factual_read_source_state_total,
        source_state="available",
    ) == 4.0
    assert _gauge_vec_value(
        pool_factual_read_source_state_total,
        source_state="blocked_external_sessions",
    ) == 2.0


def test_set_pool_factual_review_metrics_sets_pending_amounts_and_attention_totals() -> None:
    set_pool_factual_review_metrics(
        pending_totals={
            "unattributed": 3,
            "late_correction": 1,
        },
        pending_amounts_with_vat={
            "unattributed": 150.5,
            "late_correction": 42.0,
        },
        attention_required_totals={
            "late_correction": 1,
        },
    )

    assert _gauge_vec_value(pool_factual_review_pending_total, reason="unattributed") == 3.0
    assert _gauge_vec_value(pool_factual_review_pending_total, reason="late_correction") == 1.0
    assert _gauge_vec_value(
        pool_factual_review_pending_amount_with_vat,
        reason="unattributed",
    ) == 150.5
    assert _gauge_vec_value(
        pool_factual_review_pending_amount_with_vat,
        reason="late_correction",
    ) == 42.0
    assert _gauge_vec_value(
        pool_factual_review_attention_required_total,
        reason="late_correction",
    ) == 1.0


def test_set_pool_factual_actionable_alerts_exposes_active_alerts() -> None:
    set_pool_factual_actionable_alerts(
        alerts=[
            {
                "code": "freshness_lag",
                "severity": "critical",
            },
            {
                "code": "unattributed_volume",
                "severity": "warning",
            },
        ]
    )

    assert _gauge_vec_value(
        pool_factual_actionable_alert_state,
        alert_code="freshness_lag",
        severity="critical",
    ) == 1.0
    assert _gauge_vec_value(
        pool_factual_actionable_alert_state,
        alert_code="unattributed_volume",
        severity="warning",
    ) == 1.0
