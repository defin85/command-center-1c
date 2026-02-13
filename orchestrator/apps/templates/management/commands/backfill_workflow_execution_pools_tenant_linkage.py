from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError

from apps.templates.workflow_execution_pools_tenant_backfill import (
    run_workflow_execution_pools_tenant_backfill,
)


class Command(BaseCommand):
    help = (
        "Backfill workflow execution tenant/consumer linkage for records associated with pools."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Analyze and report changes without persisting updates.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print result stats as JSON.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        as_json = bool(options.get("json"))
        try:
            with transaction.atomic():
                stats = run_workflow_execution_pools_tenant_backfill()
                payload = stats.to_dict()
                payload["dry_run"] = dry_run

                if as_json:
                    self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    self.stdout.write(
                        self.style.SUCCESS("Workflow execution pools tenant linkage backfill finished")
                    )
                    for key, value in payload.items():
                        self.stdout.write(f"{key}: {value}")

                if dry_run:
                    transaction.set_rollback(True)
                    self.stdout.write(self.style.WARNING("DRY RUN: transaction rolled back"))
        except (ProgrammingError, OperationalError) as exc:
            raise CommandError(
                "Workflow/pool tables are unavailable. Run migrations first: "
                "`python manage.py migrate`."
            ) from exc
