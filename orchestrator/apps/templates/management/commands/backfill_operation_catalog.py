from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError

from apps.templates.operation_catalog_backfill import run_unified_operation_catalog_backfill


class Command(BaseCommand):
    help = "Backfill unified operation catalog from OperationTemplate and ui.action_catalog sources."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run backfill without committing changes",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        try:
            with transaction.atomic():
                stats = run_unified_operation_catalog_backfill()
                self.stdout.write(self.style.SUCCESS("Unified operation catalog backfill finished"))
                for key, value in stats.to_dict().items():
                    self.stdout.write(f"{key}: {value}")
                if dry_run:
                    transaction.set_rollback(True)
                    self.stdout.write(self.style.WARNING("DRY RUN: transaction rolled back"))
        except (ProgrammingError, OperationalError) as exc:
            raise CommandError(
                "Unified operation catalog tables are missing. Run migrations first: "
                "`python manage.py migrate`."
            ) from exc
