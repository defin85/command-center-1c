from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.db.utils import OperationalError, ProgrammingError

from apps.templates.workflow_decommission_preflight import run_workflow_decommission_preflight


class Command(BaseCommand):
    help = (
        "Run Go/No-Go preflight for workflow decommission readiness based on execution consumers registry."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print report as JSON.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Fail with non-zero exit code when decision is No-Go.",
        )

    def handle(self, *args, **options):
        as_json = bool(options.get("json"))
        strict = bool(options.get("strict"))
        try:
            report = run_workflow_decommission_preflight()
        except (ProgrammingError, OperationalError) as exc:
            raise CommandError(
                "Workflow tables are unavailable. Run migrations first: `python manage.py migrate`."
            ) from exc
        except (FileNotFoundError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        if as_json:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            self.stdout.write("workflow decommission preflight report")
            self.stdout.write(f"decision: {report['decision']}")
            self.stdout.write(f"failed_checks: {report['summary']['failed_checks']}")
            for check in report["checks"]:
                status = "PASS" if check.get("ok") else "FAIL"
                self.stdout.write(f"- {check['key']}: {status}")

        if strict and report.get("decision") != "go":
            raise CommandError("Workflow decommission preflight failed: decision=No-Go")
