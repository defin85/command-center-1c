from __future__ import annotations

from django.db import models
from django.utils import timezone


class CommandResultSnapshot(models.Model):
    """
    Append-only snapshots of command results (raw + normalized + canonical + hashes).

    MVP usage:
      - extensions.list / extensions.sync produce per-database snapshots.
    """

    tenant = models.ForeignKey(
        "tenancy.Tenant",
        on_delete=models.CASCADE,
        related_name="command_result_snapshots",
    )
    operation = models.ForeignKey(
        "operations.BatchOperation",
        on_delete=models.CASCADE,
        related_name="command_result_snapshots",
        db_column="operation_id",
    )
    database = models.ForeignKey(
        "databases.Database",
        on_delete=models.CASCADE,
        related_name="command_result_snapshots",
        null=True,
        blank=True,
    )

    driver = models.CharField(max_length=64, db_index=True)
    command_id = models.CharField(max_length=255, db_index=True)

    raw_payload = models.JSONField(default=dict, blank=True)
    normalized_payload = models.JSONField(default=dict, blank=True)
    canonical_payload = models.JSONField(default=dict, blank=True)
    canonical_hash = models.CharField(max_length=64, db_index=True)

    captured_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "command_result_snapshots"
        indexes = [
            models.Index(fields=["tenant", "command_id", "-captured_at"]),
            models.Index(fields=["tenant", "database", "command_id", "-captured_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.command_id}:{self.database_id or '-'}@{self.captured_at}"

