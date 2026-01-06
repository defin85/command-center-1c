import uuid

from django.conf import settings
from django.db import models


class ArtifactKind(models.TextChoices):
    EXTENSION = "extension", "Extension"
    CONFIG_CF = "config_cf", "Config CF"
    CONFIG_XML = "config_xml", "Config XML"
    DT_BACKUP = "dt_backup", "DT Backup"
    EPF = "epf", "EPF"
    ERF = "erf", "ERF"
    IBCMD_PACKAGE = "ibcmd_package", "IBCMD Package"
    DRIVER_CATALOG = "driver_catalog", "Driver Catalog"
    RAS_SCRIPT = "ras_script", "RAS Script"
    OTHER = "other", "Other"


class Artifact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=64, choices=ArtifactKind.choices)
    is_versioned = models.BooleanField(default=True)
    tags = models.JSONField(default=list, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="artifacts_deleted",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="artifacts_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["kind", "name"]),
        ]
        unique_together = [
            ("name", "kind"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.kind})"


class ArtifactVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    artifact = models.ForeignKey(
        Artifact,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version = models.CharField(max_length=64)
    filename = models.CharField(max_length=255, unique=True)
    storage_key = models.CharField(max_length=512)
    size = models.BigIntegerField()
    checksum = models.CharField(max_length=128)
    content_type = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="artifact_versions_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["storage_key"]),
            models.Index(fields=["artifact", "version"]),
        ]
        unique_together = [
            ("artifact", "version"),
        ]

    def __str__(self) -> str:
        return f"{self.artifact.name}@{self.version}"


class ArtifactAlias(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    artifact = models.ForeignKey(
        Artifact,
        on_delete=models.CASCADE,
        related_name="aliases",
    )
    alias = models.CharField(max_length=64)
    version = models.ForeignKey(
        ArtifactVersion,
        on_delete=models.CASCADE,
        related_name="aliases",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [
            ("artifact", "alias"),
        ]
        indexes = [
            models.Index(fields=["artifact", "alias"]),
        ]

    def __str__(self) -> str:
        return f"{self.artifact.name}:{self.alias}"


class ArtifactUsage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    artifact = models.ForeignKey(
        Artifact,
        on_delete=models.CASCADE,
        related_name="usage",
    )
    version = models.ForeignKey(
        ArtifactVersion,
        on_delete=models.CASCADE,
        related_name="usage",
    )
    operation = models.ForeignKey(
        "operations.BatchOperation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="artifact_usage",
    )
    database = models.ForeignKey(
        "databases.Database",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="artifact_usage",
    )
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-used_at"]
        indexes = [
            models.Index(fields=["artifact", "version"]),
        ]

    def __str__(self) -> str:
        return f"{self.artifact.name}@{self.version.version}"
