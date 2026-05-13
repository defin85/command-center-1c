from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.intercompany_pools.kvo18_advance_vat_offset_scheme import (
    ensure_kvo18_advance_vat_offset_scheme_assets,
)
from apps.tenancy.models import Tenant


class Command(BaseCommand):
    help = (
        "Bootstrap reusable KVO18 advance VAT offset pool scheme assets: "
        "schema template, topology template, document-policy slots, workflow, and execution pack."
    )

    def add_arguments(self, parser):
        parser.add_argument("--tenant-slug", required=True, help="Tenant slug that owns the scheme assets.")
        parser.add_argument(
            "--actor-username",
            default="",
            help="Actor username recorded in scheme asset audit fields.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Evaluate bootstrap plan and roll back changes.")
        parser.add_argument("--json", action="store_true", help="Print machine-readable JSON result.")

    def handle(self, *args, **options):
        tenant_slug = str(options["tenant_slug"])
        actor_username = str(options.get("actor_username") or "")
        dry_run = bool(options.get("dry_run"))
        as_json = bool(options.get("json"))

        tenant = Tenant.objects.filter(slug=tenant_slug).first()
        if tenant is None:
            raise CommandError(f"Tenant '{tenant_slug}' not found.")
        actor = None
        if actor_username:
            actor = get_user_model().objects.filter(username=actor_username).first()

        try:
            with transaction.atomic():
                payload = ensure_kvo18_advance_vat_offset_scheme_assets(
                    tenant=tenant,
                    actor_username=actor_username,
                    created_by=actor,
                )
                payload["dry_run"] = dry_run
                payload["tenant"] = {"id": str(tenant.id), "slug": tenant.slug}
                if as_json:
                    self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
                else:
                    self.stdout.write(self.style.SUCCESS("KVO18 advance VAT offset scheme assets prepared"))
                    self.stdout.write(f"tenant_slug: {tenant.slug}")
                    self.stdout.write(f"binding_profile_code: {payload['binding_profile']['code']}")
                    self.stdout.write(f"dry_run: {dry_run}")
                if dry_run:
                    transaction.set_rollback(True)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
