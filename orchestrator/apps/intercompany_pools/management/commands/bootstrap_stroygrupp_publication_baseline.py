from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.intercompany_pools.stroygrupp_publication_baseline import (
    bootstrap_stroygrupp_publication_baseline,
)


class Command(BaseCommand):
    help = (
        "Bootstrap deterministic dev baseline for STROYGRUPP full publication: "
        "dedicated pool, single-edge topology, canonical master data, bindings, "
        "and actor mapping for UI-driven pool run."
    )

    def add_arguments(self, parser):
        parser.add_argument("--tenant-slug", required=True, help="Tenant slug that owns the baseline data.")
        parser.add_argument("--actor-username", required=True, help="UI actor username for actor auth mapping.")
        parser.add_argument(
            "--actor-ib-username",
            default="",
            help="Dedicated IB username for actor mapping. If omitted, command reports UI blocker instead of creating mapping.",
        )
        parser.add_argument(
            "--actor-ib-password",
            default="",
            help="Dedicated IB password for actor mapping.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Evaluate bootstrap plan and roll back changes.")
        parser.add_argument("--json", action="store_true", help="Print machine-readable JSON result.")

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        as_json = bool(options.get("json"))
        tenant_slug = str(options["tenant_slug"])
        actor_username = str(options["actor_username"])
        actor_ib_username = str(options.get("actor_ib_username") or "")
        actor_ib_password = str(options.get("actor_ib_password") or "")

        try:
            with transaction.atomic():
                payload = bootstrap_stroygrupp_publication_baseline(
                    tenant_slug=tenant_slug,
                    actor_username=actor_username,
                    actor_ib_username=actor_ib_username,
                    actor_ib_password=actor_ib_password,
                    dry_run=dry_run,
                )
                if as_json:
                    self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    self.stdout.write(self.style.SUCCESS("STROYGRUPP publication baseline prepared"))
                    self.stdout.write(f"tenant_slug: {tenant_slug}")
                    self.stdout.write(f"actor_username: {actor_username}")
                    self.stdout.write(f"pool_code: {payload['pool']['code']}")
                    self.stdout.write(f"dry_run: {dry_run}")
                if dry_run:
                    transaction.set_rollback(True)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
