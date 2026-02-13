from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.intercompany_pools.command_outbox import (
    DEFAULT_OUTBOX_DISPATCH_BATCH_SIZE,
    DEFAULT_OUTBOX_RETRY_BASE_SECONDS,
    DEFAULT_OUTBOX_RETRY_CAP_SECONDS,
    dispatch_pool_run_command_outbox,
)


class Command(BaseCommand):
    help = "Dispatch pending pool_run command outbox intents into commands:worker:workflows stream."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_OUTBOX_DISPATCH_BATCH_SIZE,
            help="Maximum pending outbox entries to dispatch in one run.",
        )
        parser.add_argument(
            "--retry-base-seconds",
            type=int,
            default=DEFAULT_OUTBOX_RETRY_BASE_SECONDS,
            help="Base retry delay (seconds) for exponential backoff.",
        )
        parser.add_argument(
            "--retry-cap-seconds",
            type=int,
            default=DEFAULT_OUTBOX_RETRY_CAP_SECONDS,
            help="Maximum retry delay (seconds) for exponential backoff.",
        )

    def handle(self, *args, **options):
        stats = dispatch_pool_run_command_outbox(
            batch_size=int(options["batch_size"]),
            retry_base_seconds=int(options["retry_base_seconds"]),
            retry_cap_seconds=int(options["retry_cap_seconds"]),
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Pool run command outbox dispatch completed: "
                f"claimed={stats.claimed}, dispatched={stats.dispatched}, failed={stats.failed}"
            )
        )
