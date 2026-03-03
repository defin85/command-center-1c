from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.db.utils import OperationalError, ProgrammingError

from apps.operations.services import OperationsService


class Command(BaseCommand):
    help = (
        "Dispatch pending workflow_enqueue_outbox rows (deferred relay) "
        "with retry/backoff/idempotent publish semantics."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Maximum pending outbox rows to relay in one run (default: 100).",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print stats as JSON.",
        )

    def handle(self, *args, **options):
        batch_size = int(options.get("batch_size") or 100)
        if batch_size < 1:
            raise CommandError("batch_size must be >= 1")

        as_json = bool(options.get("json"))
        try:
            stats = OperationsService.dispatch_pending_workflow_enqueue_outbox(
                batch_size=batch_size,
            )
        except (ProgrammingError, OperationalError) as exc:
            raise CommandError(
                "Required operations/outbox tables are missing. Run migrations first: "
                "`python manage.py migrate`."
            ) from exc

        payload = {
            "batch_size": batch_size,
            "claimed": int(stats.get("claimed") or 0),
            "dispatched": int(stats.get("dispatched") or 0),
            "failed": int(stats.get("failed") or 0),
        }
        if as_json:
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        self.stdout.write(self.style.SUCCESS("Workflow enqueue outbox dispatch finished"))
        for key, value in payload.items():
            self.stdout.write(f"{key}: {value}")
