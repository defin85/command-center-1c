from __future__ import annotations

import json
from datetime import date
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.intercompany_pools.factual_preflight import run_pool_factual_sync_preflight


class Command(BaseCommand):
    help = (
        "Run live preflight for pool factual sync published 1C surfaces using "
        "Command Center metadata refresh and bounded read-only OData probes."
    )

    def add_arguments(self, parser):
        parser.add_argument("--pool-id", required=True, help="Target pool UUID.")
        parser.add_argument(
            "--quarter-start",
            default="",
            help="Quarter start in YYYY-MM-DD format. Defaults to current quarter.",
        )
        parser.add_argument(
            "--requested-by-username",
            default="",
            help="Actor username for metadata refresh path when no service mapping is configured.",
        )
        parser.add_argument(
            "--database-id",
            action="append",
            default=[],
            help="Optional database UUID filter; repeat flag to limit preflight to pilot infobases.",
        )
        parser.add_argument("--json", action="store_true", help="Print JSON report.")
        parser.add_argument("--strict", action="store_true", help="Fail on no-go decision.")

    def handle(self, *args: Any, **options: Any):
        quarter_start = self._parse_quarter_start(str(options.get("quarter_start") or "").strip())
        report = run_pool_factual_sync_preflight(
            pool_id=str(options.get("pool_id") or "").strip(),
            quarter_start=quarter_start,
            requested_by_username=str(options.get("requested_by_username") or "").strip(),
            database_ids=options.get("database_id") or [],
        )

        if bool(options.get("json")):
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            self._print_human_report(report)

        if bool(options.get("strict")) and report.get("decision") != "go":
            raise CommandError(
                "Pool factual sync preflight failed: "
                f"decision={report.get('decision')}, "
                f"failed_databases={report.get('summary', {}).get('failed_databases', 0)}."
            )

    def _parse_quarter_start(self, raw_value: str) -> date:
        if raw_value:
            try:
                return date.fromisoformat(raw_value)
            except ValueError as exc:
                raise CommandError("--quarter-start must be in YYYY-MM-DD format.") from exc
        return _current_quarter_start(date.today())

    def _print_human_report(self, report: dict[str, Any]) -> None:
        summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
        self.stdout.write("pool factual sync preflight report")
        self.stdout.write(f"decision: {report.get('decision', 'no_go')}")
        self.stdout.write(f"pool_id: {report.get('pool_id', '')}")
        self.stdout.write(f"quarter_start: {report.get('quarter_start', '')}")
        self.stdout.write(f"quarter_end: {report.get('quarter_end', '')}")
        self.stdout.write(f"database_count: {summary.get('database_count', 0)}")
        self.stdout.write(f"failed_databases: {summary.get('failed_databases', 0)}")
        for database_report in report.get("databases") or []:
            self.stdout.write(
                f"- {database_report.get('database_name', '')} "
                f"({database_report.get('database_id', '')}): {database_report.get('decision', 'no_go')}"
            )


def _current_quarter_start(current_date: date) -> date:
    month = ((current_date.month - 1) // 3) * 3 + 1
    return date(current_date.year, month, 1)
