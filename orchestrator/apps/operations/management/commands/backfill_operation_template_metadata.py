from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError

from apps.operations.metadata_backfill import run_template_metadata_backfill


class Command(BaseCommand):
    help = (
        "Backfill BatchOperation metadata for template-based operations: "
        "template_id (alias) + template_exposure_id."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run backfill without committing metadata changes.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print stats as JSON.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Return non-zero exit code when missing exposures are detected.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        strict = bool(options.get("strict"))
        as_json = bool(options.get("json"))

        try:
            with transaction.atomic():
                stats = run_template_metadata_backfill()
                payload = stats.to_dict()

                if as_json:
                    self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    self.stdout.write(self.style.SUCCESS("Operation template metadata backfill finished"))
                    for key, value in payload.items():
                        self.stdout.write(f"{key}: {value}")

                missing_exposure = int(payload["missing_exposure"])
                if strict and missing_exposure > 0:
                    raise CommandError(
                        "Template metadata backfill found unresolved template exposures: "
                        f"missing_exposure={missing_exposure}"
                    )

                if dry_run:
                    transaction.set_rollback(True)
                    self.stdout.write(self.style.WARNING("DRY RUN: transaction rolled back"))
        except (ProgrammingError, OperationalError) as exc:
            raise CommandError(
                "Required operation/template tables are missing. Run migrations first: "
                "`python manage.py migrate`."
            ) from exc
