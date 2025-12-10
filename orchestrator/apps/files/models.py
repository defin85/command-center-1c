"""
Django models for file storage.

Provides UploadedFile model for tracking uploaded files
with automatic expiration and cleanup support.
"""

import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone


User = get_user_model()


class FilePurpose(models.TextChoices):
    """Purpose choices for uploaded files."""

    OPERATION_INPUT = "operation_input", "Operation Input"
    EXTENSION = "extension", "Extension File"
    EXPORT = "export", "Export File"


def get_default_expires_at():
    """Return default expiration time (24 hours from now)."""
    return timezone.now() + timedelta(hours=24)


class UploadedFile(models.Model):
    """
    Model for tracking uploaded files.

    Stores metadata about uploaded files with automatic
    expiration support for cleanup.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    filename = models.CharField(
        max_length=255,
        help_text="Stored filename (sanitized)"
    )
    original_filename = models.CharField(
        max_length=255,
        help_text="Original filename from upload"
    )
    file_path = models.CharField(
        max_length=500,
        help_text="Relative path in storage directory"
    )
    size = models.BigIntegerField(
        help_text="File size in bytes"
    )
    mime_type = models.CharField(
        max_length=100,
        help_text="MIME type of file"
    )
    purpose = models.CharField(
        max_length=50,
        choices=FilePurpose.choices,
        help_text="Purpose of the file"
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_files',
        help_text="User who uploaded the file"
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    expires_at = models.DateTimeField(
        default=get_default_expires_at,
        help_text="Auto-delete after this time"
    )
    is_processed = models.BooleanField(
        default=False,
        help_text="File has been processed by operation"
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 checksum of file"
    )

    class Meta:
        db_table = "uploaded_files"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["expires_at"]),
            models.Index(fields=["purpose", "created_at"]),
            models.Index(fields=["uploaded_by", "-created_at"]),
            models.Index(fields=["is_processed"]),
            models.Index(fields=["checksum"]),
        ]

    def __str__(self) -> str:
        return f"{self.original_filename} ({self.purpose})"

    @property
    def is_expired(self) -> bool:
        """Check if file has expired."""
        return timezone.now() > self.expires_at

    @property
    def size_human(self) -> str:
        """Return human-readable file size."""
        size = self.size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def extend_expiration(self, hours: int = 24) -> None:
        """Extend expiration time."""
        self.expires_at = timezone.now() + timedelta(hours=hours)
        self.save(update_fields=['expires_at'])

    def mark_processed(self) -> None:
        """Mark file as processed."""
        self.is_processed = True
        self.save(update_fields=['is_processed'])

    def get_absolute_path(self) -> str:
        """
        Return absolute path to file.

        Raises:
            ValueError: If path traversal attempt is detected.
        """
        from pathlib import Path

        upload_root = Path(getattr(settings, 'UPLOAD_ROOT', '/var/lib/1c/uploads'))
        full_path = (upload_root / self.file_path).resolve()

        # Security: prevent path traversal attacks
        if not str(full_path).startswith(str(upload_root.resolve())):
            raise ValueError("Path traversal attempt detected")

        return str(full_path)
