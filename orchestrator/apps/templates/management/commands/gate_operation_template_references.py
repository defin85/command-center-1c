from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.templates.cutover_gate import (
    DEFAULT_SWITCH_CONTOUR_PATHS,
    run_operation_template_reference_gate,
)


class Command(BaseCommand):
    help = (
        "Gate runtime/internal/rbac switch contour against legacy OperationTemplate* references."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            action="append",
            default=[],
            help=(
                "Path to scan (can be specified multiple times). "
                "When omitted, default switch contour paths are used."
            ),
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print report as JSON.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Fail with non-zero exit code if any violations or missing paths are found.",
        )

    def handle(self, *args: Any, **options: Any):
        selected_paths = [str(item) for item in (options.get("path") or []) if str(item).strip()]
        report = run_operation_template_reference_gate(paths=selected_paths or None)

        if bool(options.get("json")):
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            self._print_human_report(report, selected_paths=selected_paths)

        strict = bool(options.get("strict"))
        if strict and report["status"] != "pass":
            raise CommandError(
                "OperationTemplate reference gate failed: "
                f"violations={report['violation_count']} missing_paths={len(report['missing_paths'])}."
            )

    def _print_human_report(self, report: dict[str, Any], *, selected_paths: list[str]) -> None:
        self.stdout.write("operation template switch-contour gate")
        if selected_paths:
            self.stdout.write(f"mode: custom_paths ({len(selected_paths)})")
        else:
            self.stdout.write(
                f"mode: default_switch_contour ({len(DEFAULT_SWITCH_CONTOUR_PATHS)} paths)"
            )
        self.stdout.write(f"scanned_files: {report['scanned_files']}")
        self.stdout.write(f"missing_paths: {len(report['missing_paths'])}")
        self.stdout.write(f"violation_count: {report['violation_count']}")
        self.stdout.write(f"status: {report['status']}")

        for path in report.get("missing_paths") or []:
            self.stdout.write(f"- [missing] {path}")

        for item in report.get("violations") or []:
            self.stdout.write(
                f"- [violation] {item['path']}:{item['line']} token={item['token']} snippet={item['snippet']}"
            )

