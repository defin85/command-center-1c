from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError

from apps.intercompany_pools.organization_party_binding_backfill import (
    run_organization_party_binding_backfill,
)


class Command(BaseCommand):
    help = (
        "Backfill Organization -> PoolMasterParty bindings using deterministic "
        "tenant+inn(+kpp) matching and remediation list for unresolved rows."
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
            help="Print result stats (including remediation list) as JSON.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        as_json = bool(options.get("json"))
        try:
            with transaction.atomic():
                stats = run_organization_party_binding_backfill()
                payload = stats.to_dict()
                payload["dry_run"] = dry_run

                if as_json:
                    self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    self.stdout.write(self.style.SUCCESS("Organization master-party backfill finished"))
                    for key, value in payload.items():
                        if key == "remediation_list":
                            self.stdout.write(f"{key}: {len(value)} items")
                            continue
                        self.stdout.write(f"{key}: {value}")

                if dry_run:
                    transaction.set_rollback(True)
                    if not as_json:
                        self.stdout.write(self.style.WARNING("DRY RUN: transaction rolled back"))
        except (ProgrammingError, OperationalError) as exc:
            raise CommandError(
                "Intercompany pools tables are unavailable. Run migrations first: "
                "`python manage.py migrate`."
            ) from exc
