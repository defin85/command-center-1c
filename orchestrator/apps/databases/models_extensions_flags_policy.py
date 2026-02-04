from __future__ import annotations

from django.conf import settings
from django.db import models


class ExtensionFlagsPolicy(models.Model):
    """
    Tenant-scoped policy for extensions flags.

    Policy is stored per (tenant, extension_name) and contains desired values for:
      - active
      - safe_mode
      - unsafe_action_protection

    Null means "not specified".
    """

    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE, related_name="extensions_flags_policies")
    extension_name = models.CharField(max_length=255, db_index=True)

    active = models.BooleanField(null=True, blank=True)
    safe_mode = models.BooleanField(null=True, blank=True)
    unsafe_action_protection = models.BooleanField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="extensions_flags_policies_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="extensions_flags_policies_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "extensions_flags_policies"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "extension_name"], name="extensions_flags_policy_unique"),
        ]
        indexes = [
            models.Index(fields=["tenant", "extension_name"], name="extensions_flags_policy_tenant_name_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.extension_name}"

