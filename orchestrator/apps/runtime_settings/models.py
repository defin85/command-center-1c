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
