import uuid

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models

from apps.databases.models import PermissionLevel


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
        permissions = (
            ("manage_artifact", "Can manage artifacts"),
        )

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
        permissions = (
            ("upload_artifact_version", "Can upload artifact versions"),
            ("download_artifact_version", "Can download artifact versions"),
        )

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


class ArtifactPermission(models.Model):
    """
    User permission for a specific artifact.
    Rights on the artifact apply to its versions and aliases (inheritance).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="artifact_permissions",
    )
    artifact = models.ForeignKey(
        Artifact,
        on_delete=models.CASCADE,
        related_name="user_permissions",
    )
    level = models.IntegerField(
        choices=PermissionLevel.choices,
        default=PermissionLevel.VIEW,
    )

    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "artifacts_artifact_permissions"
        unique_together = [
            ("user", "artifact"),
        ]
        indexes = [
            models.Index(fields=["user", "artifact"], name="ap_user_art_idx"),
            models.Index(fields=["artifact", "level"], name="ap_art_level_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.artifact.name} ({self.get_level_display()})"


class ArtifactGroupPermission(models.Model):
    """
    Group permission for a specific artifact.
    Rights on the artifact apply to its versions and aliases (inheritance).
    """
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="artifact_permissions",
    )
    artifact = models.ForeignKey(
        Artifact,
        on_delete=models.CASCADE,
        related_name="group_permissions",
    )
    level = models.IntegerField(
        choices=PermissionLevel.choices,
        default=PermissionLevel.VIEW,
    )

    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "artifacts_artifact_group_permissions"
        unique_together = [
            ("group", "artifact"),
        ]
        indexes = [
            models.Index(fields=["group", "artifact"], name="agp_group_art_idx"),
            models.Index(fields=["artifact", "level"], name="agp_art_level_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.group.name} -> {self.artifact.name} ({self.get_level_display()})"
