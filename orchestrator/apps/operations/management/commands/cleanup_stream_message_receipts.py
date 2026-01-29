"""
Cleanup old StreamMessageReceipt rows.

This is a maintenance command intended to be run periodically (e.g. via cron/systemd timer).

Usage:
  python manage.py cleanup_stream_message_receipts --retention-days 90 --apply
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.operations.models import StreamMessageReceipt


class Command(BaseCommand):
    help = "Delete old StreamMessageReceipt rows (idempotency receipts)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--retention-days",
            type=int,
            default=90,
            help="Delete receipts older than this many days (default: 90)",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually delete rows (default: dry-run)",
        )

    def handle(self, *args, **options):
        retention_days = int(options.get("retention_days", 90))
        apply_delete = bool(options.get("apply", False))

        if retention_days < 1:
            raise ValueError("--retention-days must be >= 1")

        cutoff = timezone.now() - timedelta(days=retention_days)
        qs = StreamMessageReceipt.objects.filter(processed_at__lt=cutoff)

        total = qs.count()
        self.stdout.write(f"StreamMessageReceipt older than {retention_days} days: {total}")

        if not apply_delete:
            self.stdout.write("Dry-run mode (no deletions). Pass --apply to delete.")
            return

        with transaction.atomic():
            deleted, _ = qs.delete()

        self.stdout.write(self.style.SUCCESS(f"Deleted StreamMessageReceipt rows: {deleted}"))

