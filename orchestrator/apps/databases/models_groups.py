from django.apps import apps
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from .models_database import Database


class DatabaseGroup(models.Model):
    """Represents a group of databases for bulk operations."""

    id = models.CharField(max_length=64, primary_key=True)
    name = models.CharField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True)
    databases = models.ManyToManyField(Database, related_name="groups")
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "database_groups"
        ordering = ["name"]
        verbose_name = "Database Group"
        verbose_name_plural = "Database Groups"

    def __str__(self):
        return self.name

    @property
    def database_count(self) -> int:
        return self.databases.count()

    @property
    def healthy_count(self) -> int:
        DatabaseModel = apps.get_model("databases", "Database")
        ok_status = getattr(DatabaseModel, "HEALTH_OK", "ok")
        return self.databases.filter(last_check_status=ok_status).count()


class StatusHistory(models.Model):
    """История изменений статусов для всех типов объектов"""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=255)
    content_object = GenericForeignKey("content_type", "object_id")

    old_status = models.CharField(max_length=50)
    new_status = models.CharField(max_length=50)
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)

    changed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "status_history"
        indexes = [
            models.Index(fields=["content_type", "object_id", "-changed_at"]),
            models.Index(fields=["new_status", "-changed_at"]),
        ]
        ordering = ["-changed_at"]
        verbose_name = "Status History"
        verbose_name_plural = "Status Histories"

    def __str__(self):
        return f"{self.content_type} {self.object_id}: {self.old_status} → {self.new_status}"

