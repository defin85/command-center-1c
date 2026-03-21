from __future__ import annotations

import json
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError

from apps.intercompany_pools.distribution_domain_reset import run_distribution_domain_reset
from apps.tenancy.models import Tenant


class Command(BaseCommand):
    help = (
        "Hard reset distribution-domain artifacts for one tenant while preserving "
        "Organizations and master-data state."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            required=True,
            help="Explicit tenant UUID selector.",
        )
        mode_group = parser.add_mutually_exclusive_group(required=True)
        mode_group.add_argument(
            "--dry-run",
            action="store_true",
            help="Analyze the reset scope without destructive mutations.",
        )
        mode_group.add_argument(
            "--apply",
            action="store_true",
            help="Execute destructive cleanup after fail-closed preflight passes.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print machine-readable reset summary as JSON.",
        )

    def handle(self, *args, **options):
        try:
            tenant_id = UUID(str(options["tenant_id"]))
        except (TypeError, ValueError, AttributeError) as exc:
            raise CommandError("--tenant-id must be a valid UUID.") from exc

        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Tenant '{tenant_id}' was not found.") from exc

        apply = bool(options.get("apply"))
        as_json = bool(options.get("json"))

        try:
            with transaction.atomic():
                result = run_distribution_domain_reset(tenant=tenant, apply=apply)
                payload = result.to_dict()
                if as_json:
                    self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Distribution-domain reset finished with status={payload['overall_status']}"
                        )
                    )
                    for key, value in payload.items():
                        self.stdout.write(f"{key}: {value}")

                if not apply:
                    transaction.set_rollback(True)
                    if not as_json:
                        self.stdout.write(self.style.WARNING("DRY RUN: transaction rolled back"))
        except (ProgrammingError, OperationalError) as exc:
            raise CommandError(
                "Distribution-domain reset tables are unavailable. Run migrations first: "
                "`python manage.py migrate`."
            ) from exc
