from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.db.utils import OperationalError, ProgrammingError

from apps.operations.workflow_enqueue_repair import (
    DEFAULT_DIAGNOSTIC_SAMPLE_LIMIT,
    DEFAULT_REPAIR_RELAY_BATCH_SIZE,
    DEFAULT_STUCK_OUTBOX_AGE_SECONDS,
    DEFAULT_STUCK_OUTBOX_RETRY_SATURATION_ATTEMPTS,
    run_workflow_enqueue_detect_repair,
)
from apps.operations.workflow_root_projection_backfill import (
    DEFAULT_BACKFILL_CHUNK_SIZE,
    DEFAULT_BACKFILL_SLA_SECONDS,
)


class Command(BaseCommand):
    help = (
        "Detect + repair workflow enqueue consistency issues: "
        "stuck workflow_enqueue_outbox rows and missing root operation projections."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--relay-batch-size",
            type=int,
            default=DEFAULT_REPAIR_RELAY_BATCH_SIZE,
            help=f"Deferred relay batch size (default: {DEFAULT_REPAIR_RELAY_BATCH_SIZE}).",
        )
        parser.add_argument(
            "--stuck-age-seconds",
            type=int,
            default=DEFAULT_STUCK_OUTBOX_AGE_SECONDS,
            help=f"Age threshold for stuck outbox detection (default: {DEFAULT_STUCK_OUTBOX_AGE_SECONDS}).",
        )
        parser.add_argument(
            "--retry-saturation-attempts",
            type=int,
            default=DEFAULT_STUCK_OUTBOX_RETRY_SATURATION_ATTEMPTS,
            help=(
                "Dispatch attempts threshold to treat outbox rows as stuck "
                f"(default: {DEFAULT_STUCK_OUTBOX_RETRY_SATURATION_ATTEMPTS})."
            ),
        )
        parser.add_argument(
            "--root-backfill-sla-seconds",
            type=int,
            default=DEFAULT_BACKFILL_SLA_SECONDS,
            help=f"Root projection backfill SLA threshold (default: {DEFAULT_BACKFILL_SLA_SECONDS}).",
        )
        parser.add_argument(
            "--root-backfill-chunk-size",
            type=int,
            default=DEFAULT_BACKFILL_CHUNK_SIZE,
            help=f"Root projection backfill chunk size (default: {DEFAULT_BACKFILL_CHUNK_SIZE}).",
        )
        parser.add_argument(
            "--sample-limit",
            type=int,
            default=DEFAULT_DIAGNOSTIC_SAMPLE_LIMIT,
            help=f"Max diagnostic samples per section (default: {DEFAULT_DIAGNOSTIC_SAMPLE_LIMIT}).",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print machine-readable JSON report.",
        )

    def handle(self, *args, **options):
        relay_batch_size = int(options.get("relay_batch_size") or DEFAULT_REPAIR_RELAY_BATCH_SIZE)
        stuck_age_seconds = int(options.get("stuck_age_seconds") or DEFAULT_STUCK_OUTBOX_AGE_SECONDS)
        retry_saturation_attempts = int(
            options.get("retry_saturation_attempts") or DEFAULT_STUCK_OUTBOX_RETRY_SATURATION_ATTEMPTS
        )
        root_backfill_sla_seconds = int(options.get("root_backfill_sla_seconds") or DEFAULT_BACKFILL_SLA_SECONDS)
        root_backfill_chunk_size = int(options.get("root_backfill_chunk_size") or DEFAULT_BACKFILL_CHUNK_SIZE)
        sample_limit = int(options.get("sample_limit") or DEFAULT_DIAGNOSTIC_SAMPLE_LIMIT)
        as_json = bool(options.get("json"))

        if relay_batch_size < 1:
            raise CommandError("relay_batch_size must be >= 1")
        if stuck_age_seconds < 1:
            raise CommandError("stuck_age_seconds must be >= 1")
        if retry_saturation_attempts < 1:
            raise CommandError("retry_saturation_attempts must be >= 1")
        if root_backfill_chunk_size < 1:
            raise CommandError("root_backfill_chunk_size must be >= 1")
        if sample_limit < 1:
            raise CommandError("sample_limit must be >= 1")

        try:
            report = run_workflow_enqueue_detect_repair(
                relay_batch_size=relay_batch_size,
                stuck_age_seconds=stuck_age_seconds,
                retry_saturation_attempts=retry_saturation_attempts,
                root_backfill_sla_seconds=root_backfill_sla_seconds,
                root_backfill_chunk_size=root_backfill_chunk_size,
                diagnostic_sample_limit=sample_limit,
            )
        except (ProgrammingError, OperationalError) as exc:
            raise CommandError(
                "Required workflow/operations tables are missing. Run migrations first: "
                "`python manage.py migrate`."
            ) from exc

        payload = report.to_dict()
        if as_json:
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            self.stdout.write(self.style.SUCCESS("Workflow enqueue consistency repair finished"))
            self.stdout.write(f"status: {payload['status']}")
            self.stdout.write(f"stuck_outbox_candidates_before: {payload['stuck_outbox_candidates_before']}")
            self.stdout.write(f"stuck_outbox_candidates_after: {payload['stuck_outbox_candidates_after']}")
            self.stdout.write(f"relay.claimed: {payload['relay']['claimed']}")
            self.stdout.write(f"relay.dispatched: {payload['relay']['dispatched']}")
            self.stdout.write(f"relay.failed: {payload['relay']['failed']}")
            self.stdout.write(
                f"root_projection_backfill.missing_before: {payload['root_projection_backfill']['missing_before']}"
            )
            self.stdout.write(f"root_projection_backfill.repaired: {payload['root_projection_backfill']['repaired']}")
            self.stdout.write(
                f"root_projection_backfill.repair_failed: {payload['root_projection_backfill']['repair_failed']}"
            )
