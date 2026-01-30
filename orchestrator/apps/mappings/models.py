from __future__ import annotations

from django.db import models


class TenantMappingSpec(models.Model):
    ENTITY_EXTENSIONS_INVENTORY = "extensions_inventory"

    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PUBLISHED, "Published"),
    ]

    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE, related_name="mapping_specs")
    entity_kind = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    spec = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tenant_mapping_specs"
        unique_together = [("tenant", "entity_kind", "status")]
        indexes = [
            models.Index(fields=["tenant", "entity_kind", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.entity_kind} ({self.status})"

