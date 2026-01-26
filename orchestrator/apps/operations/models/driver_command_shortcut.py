"""DriverCommandShortcut model - per-user saved links to schema-driven commands."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class DriverCommandShortcut(models.Model):
    """Per-user shortcut to a schema-driven driver command (e.g. ibcmd command_id)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="driver_command_shortcuts",
    )

    driver = models.CharField(max_length=32, db_index=True)
    command_id = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    payload = models.JSONField(default=dict, blank=True)
    catalog_base_version = models.CharField(max_length=64, blank=True, default="")
    catalog_overrides_version = models.CharField(max_length=64, blank=True, default="")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "driver"]),
            models.Index(fields=["user", "driver", "command_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.driver}:{self.command_id} ({self.user_id})"
