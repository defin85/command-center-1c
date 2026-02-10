from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.templates.models import OperationExposure, OperationMigrationIssue
from apps.templates.operation_catalog_service import list_set_flags_apply_mask_preset_findings

ISSUE_CODE = "SET_FLAGS_APPLY_MASK_PRESET"


class Command(BaseCommand):
    help = (
        "Report action catalog exposures with forbidden set_flags apply_mask presets "
        "(definition.executor_payload.fixed.apply_mask / capability_config.apply_mask)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--status",
            action="append",
            choices=[
                OperationExposure.STATUS_DRAFT,
                OperationExposure.STATUS_PUBLISHED,
                OperationExposure.STATUS_INVALID,
            ],
            help="Filter by exposure status (can be used multiple times). Default: published only.",
        )
        parser.add_argument(
            "--all-statuses",
            action="store_true",
            help="Include draft/published/invalid exposures.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print findings as JSON.",
        )
        parser.add_argument(
            "--write-issues",
            action="store_true",
            help="Write findings into operation_migration_issues (code=SET_FLAGS_APPLY_MASK_PRESET).",
        )
        parser.add_argument(
            "--fail-on-findings",
            action="store_true",
            help="Return non-zero exit code when findings are detected.",
        )

    def handle(self, *args: Any, **options: Any):
        statuses = self._resolve_statuses(options)
        findings = list_set_flags_apply_mask_preset_findings(statuses=statuses)
        issues_written = 0

        if bool(options.get("write_issues")):
            issues_written = self._write_migration_issues(findings)

        if bool(options.get("json")):
            payload = {
                "generated_at": timezone.now().isoformat(),
                "statuses": statuses,
                "count": len(findings),
                "issues_written": issues_written,
                "findings": findings,
            }
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            self._print_human_report(statuses=statuses, findings=findings)
            if bool(options.get("write_issues")):
                self.stdout.write(f"migration issues written: {issues_written}")

        if bool(options.get("fail_on_findings")) and findings:
            raise CommandError(f"Found {len(findings)} set_flags exposures with apply_mask preset")

    def _resolve_statuses(self, options: dict[str, Any]) -> list[str]:
        if bool(options.get("all_statuses")):
            return [
                OperationExposure.STATUS_DRAFT,
                OperationExposure.STATUS_PUBLISHED,
                OperationExposure.STATUS_INVALID,
            ]
        explicit = options.get("status") or []
        if explicit:
            return [str(item) for item in explicit]
        return [OperationExposure.STATUS_PUBLISHED]

    def _print_human_report(self, *, statuses: list[str], findings: list[dict[str, Any]]):
        self.stdout.write("set_flags apply_mask preset migration report")
        self.stdout.write(f"statuses: {', '.join(statuses)}")
        self.stdout.write(f"findings: {len(findings)}")
        if not findings:
            self.stdout.write(self.style.SUCCESS("No forbidden presets found."))
            return

        for item in findings:
            alias = str(item.get("alias") or "")
            tenant = str(item.get("tenant_id") or "global")
            status = str(item.get("status") or "")
            paths = item.get("paths") or []
            path_text = ", ".join([str(p) for p in paths]) if isinstance(paths, list) else str(paths)
            self.stdout.write(
                f"- alias={alias} tenant={tenant} status={status} paths=[{path_text}]"
            )

    def _write_migration_issues(self, findings: list[dict[str, Any]]) -> int:
        created = 0
        for item in findings:
            source_id = str(item.get("exposure_id") or "").strip()
            if not source_id:
                continue
            exposure = OperationExposure.objects.filter(id=source_id).first()
            if exposure is None:
                continue
            OperationMigrationIssue.objects.filter(
                source_type="operation_exposure",
                source_id=source_id,
                code=ISSUE_CODE,
            ).delete()
            details = {
                "alias": item.get("alias"),
                "status": item.get("status"),
                "paths": item.get("paths"),
                "messages": item.get("messages"),
            }
            OperationMigrationIssue.objects.create(
                source_type="operation_exposure",
                source_id=source_id,
                tenant=exposure.tenant,
                exposure=exposure,
                severity=OperationMigrationIssue.SEVERITY_ERROR,
                code=ISSUE_CODE,
                message="extensions.set_flags exposure contains forbidden apply_mask preset",
                details=details,
            )
            created += 1
        return created
