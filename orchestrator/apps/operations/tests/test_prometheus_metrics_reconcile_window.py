from __future__ import annotations

from apps.operations.prometheus_metrics import (
    pool_master_data_sync_reconcile_window_coverage_ratio,
    pool_master_data_sync_reconcile_window_deadline_miss_total,
    pool_master_data_sync_reconcile_window_partial_total,
    pool_master_data_sync_reconcile_window_total,
    record_pool_master_data_sync_reconcile_window_metrics,
)


def _counter_value(counter) -> float:
    return float(counter._value.get())


def _counter_vec_value(counter_vec, **labels: str) -> float:
    return float(counter_vec.labels(**labels)._value.get())


def _gauge_value(gauge) -> float:
    return float(gauge._value.get())


def test_reconcile_window_metrics_increment_deadline_and_partial_counters() -> None:
    before_total = _counter_vec_value(
        pool_master_data_sync_reconcile_window_total,
        outcome="partial",
        deadline_state="missed",
    )
    before_deadline_miss = _counter_value(pool_master_data_sync_reconcile_window_deadline_miss_total)
    before_partial = _counter_value(pool_master_data_sync_reconcile_window_partial_total)

    record_pool_master_data_sync_reconcile_window_metrics(
        coverage_ratio=1.25,
        deadline_state="MISSED",
        outcome="PARTIAL",
        latency_seconds=12.5,
    )

    assert _counter_vec_value(
        pool_master_data_sync_reconcile_window_total,
        outcome="partial",
        deadline_state="missed",
    ) == before_total + 1.0
    assert _counter_value(pool_master_data_sync_reconcile_window_deadline_miss_total) == before_deadline_miss + 1.0
    assert _counter_value(pool_master_data_sync_reconcile_window_partial_total) == before_partial + 1.0
    assert _gauge_value(pool_master_data_sync_reconcile_window_coverage_ratio) == 1.0


def test_reconcile_window_metrics_do_not_increment_partial_or_deadline_counters_for_completed_window() -> None:
    before_total = _counter_vec_value(
        pool_master_data_sync_reconcile_window_total,
        outcome="completed",
        deadline_state="met",
    )
    before_deadline_miss = _counter_value(pool_master_data_sync_reconcile_window_deadline_miss_total)
    before_partial = _counter_value(pool_master_data_sync_reconcile_window_partial_total)

    record_pool_master_data_sync_reconcile_window_metrics(
        coverage_ratio=-0.1,
        deadline_state="MET",
        outcome="COMPLETED",
        latency_seconds=-3.0,
    )

    assert _counter_vec_value(
        pool_master_data_sync_reconcile_window_total,
        outcome="completed",
        deadline_state="met",
    ) == before_total + 1.0
    assert _counter_value(pool_master_data_sync_reconcile_window_deadline_miss_total) == before_deadline_miss
    assert _counter_value(pool_master_data_sync_reconcile_window_partial_total) == before_partial
    assert _gauge_value(pool_master_data_sync_reconcile_window_coverage_ratio) == 0.0
