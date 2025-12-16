"""AdminActionAuditLog model - audit log for operator/admin actions via API v2."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class AdminActionAuditLog(models.Model):
    """
    Minimal audit log for operator-facing actions.

    The goal is to have a single place to inspect who did what and when
    for SPA-primary admin flows (DLQ retry, templates sync, RBAC changes, etc.).
    """

    OUTCOME_SUCCESS = "success"
    OUTCOME_ERROR = "error"
    OUTCOME_CHOICES = [
        (OUTCOME_SUCCESS, "success"),
        (OUTCOME_ERROR, "error"),
    ]

    action = models.CharField(max_length=128, db_index=True, help_text="Action identifier (e.g. dlq.retry)")
    outcome = models.CharField(max_length=16, choices=OUTCOME_CHOICES, db_index=True)

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="admin_action_audit_logs",
    )
    actor_username = models.CharField(max_length=150, blank=True, default="")
    actor_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=256, blank=True, default="")

    target_type = models.CharField(max_length=64, blank=True, default="", db_index=True)
    target_id = models.CharField(max_length=128, blank=True, default="", db_index=True)

    metadata = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Admin Action Audit Log"
        verbose_name_plural = "Admin Action Audit Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} ({self.outcome}) at {self.created_at:%Y-%m-%d %H:%M:%S}"

