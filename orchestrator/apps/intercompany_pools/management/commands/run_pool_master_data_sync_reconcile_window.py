from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.intercompany_pools.master_data_sync_reconcile_aggregator import (
    aggregate_pool_master_data_reconcile_window,
)
from apps.intercompany_pools.master_data_sync_reconcile_scheduler import (
    schedule_pool_master_data_reconcile_probe_jobs,
)


REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_RECONCILE_REPORT_PATH = (
    REPO_ROOT
    / "docs"
    / "observability"
    / "artifacts"
    / "refactor-08"
    / "pool-master-data-sync-reconcile-window-report.json"
)


class Command(BaseCommand):
    help = (
        "Run pool master-data reconcile window via runtime path "
        "(fan-out scheduling -> fan-in aggregation) and persist JSON report."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            default="",
            help="Optional tenant scope for reconcile window.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=720,
            help="Max scopes for fan-out scheduling (default: 720).",
        )
        parser.add_argument(
            "--window-seconds",
            type=int,
            default=120,
            help="Reconcile window SLA deadline in seconds (default: 120).",
        )
        parser.add_argument(
            "--max-enqueue-attempts",
            type=int,
            default=3,
            help="Max enqueue attempts per scope during fan-out (default: 3).",
        )
        parser.add_argument(
            "--retry-base-backoff-seconds",
            type=float,
            default=0.25,
            help="Base retry backoff seconds for fan-out retries (default: 0.25).",
        )
        parser.add_argument(
            "--retry-max-backoff-seconds",
            type=float,
            default=2.0,
            help="Max retry backoff seconds for fan-out retries (default: 2.0).",
        )
        parser.add_argument(
            "--backpressure-queue-depth-limit",
            type=int,
            default=0,
            help=(
                "Queue depth threshold for workflow stream backpressure. "
                "0 disables backpressure."
            ),
        )
        parser.add_argument(
            "--poll-interval-seconds",
            type=float,
            default=1.0,
            help="Fan-in aggregation polling interval in seconds (default: 1.0).",
        )
        parser.add_argument(
            "--report-path",
            default=str(DEFAULT_RECONCILE_REPORT_PATH),
            help=f"Path to JSON report (default: {DEFAULT_RECONCILE_REPORT_PATH}).",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print full JSON report payload to stdout.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        tenant_id = str(options.get("tenant_id") or "").strip() or None
        batch_size = int(options.get("batch_size") or 720)
        window_seconds = int(options.get("window_seconds") or 120)
        max_enqueue_attempts = int(options.get("max_enqueue_attempts") or 3)
        retry_base_backoff_seconds = float(options.get("retry_base_backoff_seconds") or 0.25)
        retry_max_backoff_seconds = float(options.get("retry_max_backoff_seconds") or 2.0)
        backpressure_queue_depth_limit = int(options.get("backpressure_queue_depth_limit") or 0)
        poll_interval_seconds = float(options.get("poll_interval_seconds") or 1.0)
        report_path = self._resolve_path(str(options.get("report_path") or str(DEFAULT_RECONCILE_REPORT_PATH)))
        as_json = bool(options.get("json"))

        if batch_size < 1:
            raise CommandError("batch_size must be >= 1")
        if window_seconds < 1:
            raise CommandError("window_seconds must be >= 1")
        if max_enqueue_attempts < 1:
            raise CommandError("max_enqueue_attempts must be >= 1")
        if retry_base_backoff_seconds < 0:
            raise CommandError("retry_base_backoff_seconds must be >= 0")
        if retry_max_backoff_seconds < retry_base_backoff_seconds:
            raise CommandError("retry_max_backoff_seconds must be >= retry_base_backoff_seconds")
        if backpressure_queue_depth_limit < 0:
            raise CommandError("backpressure_queue_depth_limit must be >= 0")
        if poll_interval_seconds < 0:
            raise CommandError("poll_interval_seconds must be >= 0")

        fanout = schedule_pool_master_data_reconcile_probe_jobs(
            tenant_id=tenant_id,
            batch_size=batch_size,
            window_seconds=window_seconds,
            max_enqueue_attempts=max_enqueue_attempts,
            retry_base_backoff_seconds=retry_base_backoff_seconds,
            retry_max_backoff_seconds=retry_max_backoff_seconds,
            backpressure_queue_depth_limit=backpressure_queue_depth_limit,
        )
        fanin = aggregate_pool_master_data_reconcile_window(
            fanout_result=fanout,
            poll_interval_seconds=poll_interval_seconds,
        )

        report = {
            "schema_version": "pool_master_data_sync_reconcile_window.v1",
            "overall_status": "pass" if fanin.outcome == "completed" else "partial",
            "fanout": fanout.to_report(),
            "fanin": fanin.to_report(),
        }

        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        if as_json:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return

        self.stdout.write(self.style.SUCCESS("pool master-data reconcile window report"))
        self.stdout.write(f"overall_status: {report['overall_status']}")
        self.stdout.write(f"reconcile_window_id: {fanout.reconcile_window_id}")
        self.stdout.write(f"fanout.scheduled: {fanout.scheduled}")
        self.stdout.write(f"fanout.skipped: {fanout.skipped}")
        self.stdout.write(f"fanout.failed: {fanout.failed}")
        self.stdout.write(f"fanin.outcome: {fanin.outcome}")
        self.stdout.write(f"fanin.deadline_state: {fanin.deadline_state}")
        self.stdout.write(f"fanin.coverage_ratio: {fanin.coverage_ratio}")
        self.stdout.write(f"report_path: {report_path}")

    def _resolve_path(self, raw_path: str) -> Path:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = (REPO_ROOT / candidate).resolve()
        return candidate
