from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.templates.cutover_preflight import run_operation_exposure_cutover_preflight


class Command(BaseCommand):
    help = (
        "Run preflight checks for OperationExposure big-bang cutover "
        "(alias uniqueness, referential consistency, permission parity readiness)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print full report as JSON.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Fail with non-zero exit code when critical mismatches are present.",
        )

    def handle(self, *args: Any, **options: Any):
        report = run_operation_exposure_cutover_preflight()
        strict = bool(options.get("strict"))
        as_json = bool(options.get("json"))

        if as_json:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            self._print_human_report(report)

        critical_mismatches = int(report["summary"]["total_critical_mismatches"])
        if strict and critical_mismatches > 0:
            raise CommandError(
                "OperationExposure cutover preflight failed: "
                f"critical mismatches={critical_mismatches} (expected 0)."
            )

    def _print_human_report(self, report: dict[str, Any]) -> None:
        summary = report["summary"]
        direct_permissions_total = summary.get("direct_permissions_total", 0)
        group_permissions_total = summary.get("group_permissions_total", 0)
        self.stdout.write("operation exposure cutover preflight report")
        self.stdout.write(f"generated_at: {report['generated_at']}")
        self.stdout.write(f"template_exposures_total: {summary['template_exposures_total']}")
        self.stdout.write(f"template_definitions_total: {summary.get('template_definitions_total', 0)}")
        self.stdout.write(f"direct_permissions_total: {direct_permissions_total}")
        self.stdout.write(f"group_permissions_total: {group_permissions_total}")
        self.stdout.write(f"total_checks: {summary['total_checks']}")
        self.stdout.write(f"total_mismatches: {summary['total_mismatches']}")
        self.stdout.write(
            f"total_critical_mismatches: {summary['total_critical_mismatches']}"
        )

        checks = report.get("checks") or []
        for item in checks:
            key = str(item.get("key") or "")
            mismatches = int(item.get("mismatches") or 0)
            status = str(item.get("status") or "")
            critical = bool(item.get("critical"))
            self.stdout.write(
                f"- [{status}] key={key} critical={critical} mismatches={mismatches}"
            )
