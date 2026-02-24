from __future__ import annotations

import logging
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.intercompany_pools.command_outbox import (
    DEFAULT_OUTBOX_DISPATCH_BATCH_SIZE,
    DEFAULT_OUTBOX_RETRY_BASE_SECONDS,
    DEFAULT_OUTBOX_RETRY_CAP_SECONDS,
    dispatch_pool_run_command_outbox,
)
from apps.intercompany_pools.outbox_dispatcher_runtime import (
    DEFAULT_POOL_OUTBOX_DISPATCHER_HEARTBEAT_TTL_SECONDS,
    write_pool_outbox_dispatcher_heartbeat,
)


logger = logging.getLogger(__name__)

DEFAULT_DISPATCH_INTERVAL_SECONDS = 2.0
MIN_DISPATCH_INTERVAL_SECONDS = 0.1


class Command(BaseCommand):
    help = "Run continuous dispatcher for pool_run command outbox."

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval-seconds",
            type=float,
            default=DEFAULT_DISPATCH_INTERVAL_SECONDS,
            help="Polling interval between dispatch cycles.",
        )
        parser.add_argument(
            "--heartbeat-ttl-seconds",
            type=int,
            default=DEFAULT_POOL_OUTBOX_DISPATCHER_HEARTBEAT_TTL_SECONDS,
            help="Redis key TTL for runtime heartbeat.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_OUTBOX_DISPATCH_BATCH_SIZE,
            help="Maximum pending outbox entries to dispatch per cycle.",
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
        interval_seconds = max(
            float(options["interval_seconds"]),
            MIN_DISPATCH_INTERVAL_SECONDS,
        )
        heartbeat_ttl_seconds = max(1, int(options["heartbeat_ttl_seconds"]))
        batch_size = max(1, int(options["batch_size"]))
        retry_base_seconds = max(1, int(options["retry_base_seconds"]))
        retry_cap_seconds = max(retry_base_seconds, int(options["retry_cap_seconds"]))

        self.stdout.write(
            self.style.SUCCESS(
                "Starting pool_run command outbox dispatcher "
                f"(interval={interval_seconds:.2f}s, batch_size={batch_size})"
            )
        )

        while True:
            cycle_started_at = time.monotonic()
            cycle_now = timezone.now()
            claimed = 0
            dispatched = 0
            failed = 0

            try:
                stats = dispatch_pool_run_command_outbox(
                    batch_size=batch_size,
                    retry_base_seconds=retry_base_seconds,
                    retry_cap_seconds=retry_cap_seconds,
                )
                claimed = stats.claimed
                dispatched = stats.dispatched
                failed = stats.failed

                if claimed > 0 or failed > 0:
                    logger.info(
                        "Pool outbox cycle: claimed=%s dispatched=%s failed=%s",
                        claimed,
                        dispatched,
                        failed,
                    )
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("\nPool outbox dispatcher interrupted"))
                return
            except Exception:
                logger.exception("Pool outbox dispatcher cycle failed")
                failed = max(failed, 1)
            finally:
                write_pool_outbox_dispatcher_heartbeat(
                    claimed=claimed,
                    dispatched=dispatched,
                    failed=failed,
                    interval_seconds=interval_seconds,
                    heartbeat_ttl_seconds=heartbeat_ttl_seconds,
                    now=cycle_now,
                )

            elapsed = time.monotonic() - cycle_started_at
            sleep_seconds = max(
                MIN_DISPATCH_INTERVAL_SECONDS,
                interval_seconds - elapsed,
            )
            time.sleep(sleep_seconds)
