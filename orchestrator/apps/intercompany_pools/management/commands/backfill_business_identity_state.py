from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.intercompany_pools.business_identity_backfill import run_business_identity_backfill


class Command(BaseCommand):
    help = (
        "Backfill business-identity metadata state for legacy snapshot/resolution rows "
        "and document_policy decision metadata contexts."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Analyze changes without persisting updates.")
        parser.add_argument("--json", action="store_true", help="Print result payload as JSON.")
        parser.add_argument("--tenant-id", dest="tenant_id", help="Limit backfill to a single tenant.")
        parser.add_argument("--database-id", dest="database_id", help="Limit scope backfill to one database.")
        parser.add_argument("--decision-id", dest="decision_id", help="Limit decision backfill to one decision id.")

    def handle(self, *args, **options):
        payload = run_business_identity_backfill(
            dry_run=bool(options.get("dry_run")),
            tenant_id=options.get("tenant_id"),
            database_id=options.get("database_id"),
            decision_id=options.get("decision_id"),
        )

        if options.get("json"):
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        self.stdout.write(self.style.SUCCESS("Business identity backfill finished"))
        for key, value in payload.items():
            self.stdout.write(f"{key}: {value}")
