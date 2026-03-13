from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.intercompany_pools.workflow_hardening_cutover_evidence import (
    verify_workflow_hardening_cutover_evidence,
)


class Command(BaseCommand):
    help = (
        "Verify tenant-scoped workflow hardening cutover evidence bundle and emit "
        "a machine-readable go/no-go verdict."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "bundle_path_or_uri",
            help="Bundle path or file:// URI for workflow hardening cutover evidence.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        verdict = verify_workflow_hardening_cutover_evidence(
            str(options.get("bundle_path_or_uri") or "")
        )
        self.stdout.write(json.dumps(verdict, ensure_ascii=False, indent=2))

        if verdict.get("status") == "passed" and verdict.get("go_no_go") == "go":
            return

        raise CommandError(
            "Workflow hardening cutover evidence verification failed: "
            f"status={verdict.get('status')} go_no_go={verdict.get('go_no_go')}."
        )
