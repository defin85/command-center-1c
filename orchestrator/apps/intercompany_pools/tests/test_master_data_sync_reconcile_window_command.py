from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.intercompany_pools.master_data_sync_reconcile_aggregator import MasterDataSyncReconcileFanInResult
from apps.intercompany_pools.master_data_sync_reconcile_scheduler import MasterDataSyncReconcileFanOutResult


@pytest.mark.django_db
def test_reconcile_window_command_runs_fanout_and_fanin_and_writes_report(tmp_path) -> None:
    report_path = tmp_path / "reconcile-window-report.json"
    fanout_result = MasterDataSyncReconcileFanOutResult(
        reconcile_window_id="reconcile-window-1",
        started_at="2026-03-04T00:00:00Z",
        deadline_at="2026-03-04T00:02:00Z",
        total_scopes=2,
        scheduled=2,
        skipped=0,
        failed=0,
        scope_results=(
            {"tenant_id": "t1", "database_id": "d1", "entity_type": "item", "status": "scheduled"},
            {"tenant_id": "t1", "database_id": "d2", "entity_type": "party", "status": "scheduled"},
        ),
    )
    fanin_result = MasterDataSyncReconcileFanInResult(
        reconcile_window_id="reconcile-window-1",
        started_at="2026-03-04T00:00:00Z",
        deadline_at="2026-03-04T00:02:00Z",
        finished_at="2026-03-04T00:01:10Z",
        outcome="completed",
        deadline_state="met",
        total_scopes=2,
        scheduled=2,
        skipped=0,
        failed=0,
        on_time_completed=2,
        late_completed=0,
        pending=0,
        coverage_ratio=1.0,
        on_time_scope_results=(
            {"tenant_id": "t1", "database_id": "d1", "entity_type": "item", "job_status": "succeeded"},
            {"tenant_id": "t1", "database_id": "d2", "entity_type": "party", "job_status": "succeeded"},
        ),
        late_scope_results=(),
        pending_scope_results=(),
    )

    stdout = StringIO()
    with (
        patch(
            "apps.intercompany_pools.management.commands.run_pool_master_data_sync_reconcile_window.schedule_pool_master_data_reconcile_probe_jobs",
            return_value=fanout_result,
        ) as fanout_mock,
        patch(
            "apps.intercompany_pools.management.commands.run_pool_master_data_sync_reconcile_window.aggregate_pool_master_data_reconcile_window",
            return_value=fanin_result,
        ) as fanin_mock,
    ):
        call_command(
            "run_pool_master_data_sync_reconcile_window",
            "--report-path",
            str(report_path),
            "--json",
            stdout=stdout,
        )

    fanout_mock.assert_called_once()
    fanin_mock.assert_called_once_with(
        fanout_result=fanout_result,
        poll_interval_seconds=1.0,
    )
    payload = json.loads(stdout.getvalue())
    assert payload["schema_version"] == "pool_master_data_sync_reconcile_window.v1"
    assert payload["overall_status"] == "pass"
    assert payload["fanout"]["reconcile_window_id"] == "reconcile-window-1"
    assert payload["fanin"]["outcome"] == "completed"

    persisted_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted_payload["schema_version"] == "pool_master_data_sync_reconcile_window.v1"
    assert persisted_payload["fanout"]["scheduled"] == 2
    assert persisted_payload["fanin"]["coverage_ratio"] == 1.0


@pytest.mark.django_db
def test_reconcile_window_command_rejects_negative_backpressure_limit() -> None:
    with pytest.raises(CommandError, match="backpressure_queue_depth_limit must be >= 0"):
        call_command(
            "run_pool_master_data_sync_reconcile_window",
            "--backpressure-queue-depth-limit",
            "-1",
        )
