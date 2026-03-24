from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from apps.intercompany_pools.top_down_execution_pack_alias_adoption import (
    DEFAULT_TOP_DOWN_CONTRACT_CANONICAL_ID,
    TOP_DOWN_EXECUTION_PACK_CODE,
    adopt_top_down_execution_pack_aliases,
)


class Command(BaseCommand):
    help = "Create topology-aware decision revisions for the top-down execution pack and repin its attachments."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--actor", required=True, help="Username recorded as the actor for the new revision.")
        parser.add_argument(
            "--tenant-slug",
            default="",
            help="Optional tenant slug when multiple tenants contain the same execution-pack code.",
        )
        parser.add_argument(
            "--binding-profile-code",
            default=TOP_DOWN_EXECUTION_PACK_CODE,
            help="Execution-pack code to revise.",
        )
        parser.add_argument(
            "--contract-canonical-id",
            default=DEFAULT_TOP_DOWN_CONTRACT_CANONICAL_ID,
            help="Canonical contract id used for realization/receipt aliases.",
        )

    def handle(self, *args, **options):
        try:
            result = adopt_top_down_execution_pack_aliases(
                actor_username=str(options["actor"] or "").strip(),
                tenant_slug=str(options["tenant_slug"] or "").strip() or None,
                binding_profile_code=str(options["binding_profile_code"] or "").strip() or TOP_DOWN_EXECUTION_PACK_CODE,
                contract_canonical_id=str(options["contract_canonical_id"] or "").strip()
                or DEFAULT_TOP_DOWN_CONTRACT_CANONICAL_ID,
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
