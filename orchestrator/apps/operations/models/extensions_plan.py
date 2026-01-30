from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ExtensionsPlan(models.Model):
    """
    Stored plan for extensions apply (tenant-scoped).

    MVP: plan captures per-database snapshot hash preconditions + executor config.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE, related_name="extensions_plans")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    database_ids = models.JSONField(default=list)
    preconditions = models.JSONField(default=dict, help_text="database_id -> {hash, at}")
    executor = models.JSONField(default=dict, help_text="Executor config for apply")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "extensions_plans"
        indexes = [
            models.Index(fields=["tenant", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.id}"

