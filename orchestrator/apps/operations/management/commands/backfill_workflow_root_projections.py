from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError

from apps.operations.workflow_root_projection_backfill import (
    DEFAULT_BACKFILL_CHUNK_SIZE,
    DEFAULT_BACKFILL_SLA_SECONDS,
    run_workflow_root_projection_backfill,
)


class Command(BaseCommand):
    help = (
        "Backfill missing workflow root BatchOperation projection records for historical executions "
        "with SLA lag diagnostics."
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
            help="Print stats as JSON.",
        )
        parser.add_argument(
            "--sla-seconds",
            type=int,
            default=DEFAULT_BACKFILL_SLA_SECONDS,
            help=f"SLA threshold for lag diagnostics in seconds (default: {DEFAULT_BACKFILL_SLA_SECONDS}).",
        )
        parser.add_argument(
            "--strict-sla",
            action="store_true",
            help="Return non-zero exit code when SLA breaches are detected.",
        )
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=DEFAULT_BACKFILL_CHUNK_SIZE,
            help=f"Execution scan chunk size (default: {DEFAULT_BACKFILL_CHUNK_SIZE}).",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        as_json = bool(options.get("json"))
        strict_sla = bool(options.get("strict_sla"))
        sla_seconds = int(options.get("sla_seconds") or DEFAULT_BACKFILL_SLA_SECONDS)
        chunk_size = int(options.get("chunk_size") or DEFAULT_BACKFILL_CHUNK_SIZE)

        if chunk_size < 1:
            raise CommandError("chunk_size must be >= 1")

        try:
            with transaction.atomic():
                stats = run_workflow_root_projection_backfill(
                    sla_seconds=sla_seconds,
                    chunk_size=chunk_size,
                )
                payload = stats.to_dict()
                payload["sla_seconds"] = max(0, int(sla_seconds))
                payload["chunk_size"] = chunk_size
                payload["dry_run"] = dry_run

                if as_json:
                    self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    self.stdout.write(self.style.SUCCESS("Workflow root projection backfill finished"))
                    for key, value in payload.items():
                        self.stdout.write(f"{key}: {value}")

                if strict_sla and int(payload["sla_breaches"]) > 0:
                    raise CommandError(
                        "Workflow root projection backfill SLA breached: "
                        f"sla_breaches={payload['sla_breaches']}, "
                        f"max_lag_seconds={payload['max_lag_seconds']}, "
                        f"sla_seconds={payload['sla_seconds']}"
                    )

                if dry_run:
                    transaction.set_rollback(True)
                    self.stdout.write(self.style.WARNING("DRY RUN: transaction rolled back"))
        except (ProgrammingError, OperationalError) as exc:
            raise CommandError(
                "Required workflow/operations tables are missing. Run migrations first: "
                "`python manage.py migrate`."
            ) from exc

