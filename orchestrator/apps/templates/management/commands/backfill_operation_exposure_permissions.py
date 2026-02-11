from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError

from apps.templates.operation_exposure_permissions_backfill import (
    run_operation_exposure_permissions_backfill,
)


class Command(BaseCommand):
    help = (
        "Backfill legacy OperationTemplate permissions into exposure-oriented "
        "template permission tables with parity checks."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run backfill and parity checks without committing changes.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print stats as JSON.",
        )
        parser.add_argument(
            "--strict-parity",
            action="store_true",
            help="Return non-zero exit code when parity mismatches or missing exposures are detected.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        strict_parity = bool(options.get("strict_parity"))
        as_json = bool(options.get("json"))

        try:
            with transaction.atomic():
                stats = run_operation_exposure_permissions_backfill()
                payload = stats.to_dict()

                if as_json:
                    self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    self.stdout.write(self.style.SUCCESS("Operation exposure permissions backfill finished"))
                    for key, value in payload.items():
                        self.stdout.write(f"{key}: {value}")

                parity_errors = int(payload["parity_mismatches_total"])
                missing_exposure = int(payload["direct_missing_exposure"]) + int(payload["group_missing_exposure"])

                if strict_parity and (parity_errors > 0 or missing_exposure > 0):
                    raise CommandError(
                        "Permission backfill parity failed: "
                        f"parity_mismatches_total={parity_errors}, missing_exposure={missing_exposure}"
                    )

                if dry_run:
                    transaction.set_rollback(True)
                    self.stdout.write(self.style.WARNING("DRY RUN: transaction rolled back"))
        except (ProgrammingError, OperationalError) as exc:
            raise CommandError(
                "Required permission tables are missing. Run migrations first: "
                "`python manage.py migrate`."
            ) from exc

