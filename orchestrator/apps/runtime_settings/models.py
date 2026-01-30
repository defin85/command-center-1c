from django.db import models


class RuntimeSetting(models.Model):
    """Runtime-configurable settings stored in the database."""

    key = models.CharField(max_length=128, unique=True)
    value = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'runtime_settings'
        ordering = ['key']
        verbose_name = 'Runtime Setting'
        verbose_name_plural = 'Runtime Settings'

    def __str__(self) -> str:
        return f"{self.key}={self.value}"


class TenantRuntimeSettingOverride(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PUBLISHED, "Published"),
    ]

    tenant = models.ForeignKey(
        "tenancy.Tenant",
        on_delete=models.CASCADE,
        related_name="runtime_setting_overrides",
    )
    key = models.CharField(max_length=128)
    value = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tenant_runtime_setting_overrides"
        ordering = ["tenant_id", "key"]
        unique_together = [("tenant", "key")]
        verbose_name = "Tenant Runtime Setting Override"
        verbose_name_plural = "Tenant Runtime Setting Overrides"

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.key} ({self.status})"
