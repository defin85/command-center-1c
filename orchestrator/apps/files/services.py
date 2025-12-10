"""
File storage service for handling file uploads.

Provides secure file storage with:
- Filename sanitization
- Size validation
- SHA-256 checksums
- Automatic cleanup of expired files
"""

import hashlib
import logging
import os
import re
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Optional, Tuple

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile as DjangoUploadedFile
from django.utils import timezone

from .models import FilePurpose, UploadedFile


logger = logging.getLogger(__name__)


class FileStorageService:
    """
    Service for managing file uploads and storage.

    Storage path structure:
    UPLOAD_ROOT/{year}/{month}/{uuid}/filename

    Example:
    /var/lib/1c/uploads/2025/12/abc123.../document.pdf
    """

    # Maximum file size (100 MB)
    MAX_FILE_SIZE = 100 * 1024 * 1024

    # Default expiration (24 hours)
    DEFAULT_EXPIRY_HOURS = 24

    # Allowed MIME types by purpose
    ALLOWED_MIME_TYPES = {
        FilePurpose.OPERATION_INPUT: [
            'application/json',
            'application/xml',
            'text/plain',
            'text/csv',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        ],
        FilePurpose.EXTENSION: [
            'application/octet-stream',
            'application/x-1c-extension',
        ],
        FilePurpose.EXPORT: [
            'application/json',
            'application/xml',
            'text/plain',
            'text/csv',
            'application/zip',
        ],
    }

    # Dangerous file extensions to block
    BLOCKED_EXTENSIONS = {
        '.exe', '.bat', '.cmd', '.com', '.scr', '.pif',
        '.js', '.vbs', '.wsf', '.ps1', '.sh', '.bash',
    }

    @classmethod
    def get_upload_root(cls) -> Path:
        """Get upload root directory from settings."""
        upload_root = getattr(
            settings,
            'UPLOAD_ROOT',
            '/var/lib/1c/uploads'
        )
        return Path(upload_root)

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Sanitize filename by removing dangerous characters.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove path separators
        filename = os.path.basename(filename)

        # Remove null bytes and control characters
        filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)

        # Replace spaces and special chars with underscore
        filename = re.sub(r'[^\w\.\-]', '_', filename)

        # Remove leading dots (hidden files)
        filename = filename.lstrip('.')

        # Limit length
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200 - len(ext)] + ext

        # Ensure non-empty filename
        if not filename:
            filename = 'unnamed_file'

        return filename

    @classmethod
    def validate_file(
        cls,
        file: DjangoUploadedFile,
        purpose: str,
        max_size: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate uploaded file.

        Args:
            file: Django uploaded file object
            purpose: File purpose
            max_size: Optional max file size override

        Returns:
            Tuple of (is_valid, error_message)
        """
        max_size = max_size or cls.MAX_FILE_SIZE

        # Check file size
        if file.size > max_size:
            max_mb = max_size / (1024 * 1024)
            return False, f"File size exceeds maximum allowed ({max_mb:.0f} MB)"

        # Check file extension
        _, ext = os.path.splitext(file.name.lower())
        if ext in cls.BLOCKED_EXTENSIONS:
            return False, f"File type '{ext}' is not allowed"

        # Check MIME type for known purposes
        if purpose in cls.ALLOWED_MIME_TYPES:
            allowed_types = cls.ALLOWED_MIME_TYPES[purpose]
            if file.content_type not in allowed_types:
                # Extension file (.cfe) may have various MIME types
                if purpose == FilePurpose.EXTENSION and ext == '.cfe':
                    pass  # Allow .cfe files regardless of MIME type
                else:
                    return False, f"MIME type '{file.content_type}' not allowed for {purpose}"

        # Optional magic bytes validation (if python-magic is installed)
        try:
            import magic
            file.seek(0)
            detected_mime = magic.from_buffer(file.read(2048), mime=True)
            file.seek(0)

            # Warn if detected MIME type differs from claimed
            if detected_mime != file.content_type:
                logger.warning(
                    f"MIME type mismatch: claimed '{file.content_type}', "
                    f"detected '{detected_mime}' for file {file.name}"
                )
        except ImportError:
            # python-magic not installed, skip validation
            logger.debug("python-magic not installed, skipping magic bytes validation")
        except Exception as e:
            logger.warning(f"Magic bytes validation failed: {e}")

        return True, None

    @classmethod
    def calculate_checksum(cls, file: DjangoUploadedFile) -> str:
        """
        Calculate SHA-256 checksum of file.

        Args:
            file: Django uploaded file object

        Returns:
            Hexadecimal SHA-256 checksum
        """
        sha256 = hashlib.sha256()

        # Reset file position
        file.seek(0)

        # Read in chunks for large files
        for chunk in file.chunks(chunk_size=8192):
            sha256.update(chunk)

        # Reset file position for subsequent reads
        file.seek(0)

        return sha256.hexdigest()

    @classmethod
    def save_file(
        cls,
        file: DjangoUploadedFile,
        purpose: str,
        uploaded_by=None,
        expiry_hours: Optional[int] = None
    ) -> UploadedFile:
        """
        Save uploaded file to storage.

        Args:
            file: Django uploaded file object
            purpose: File purpose (operation_input, extension, export)
            uploaded_by: User who uploaded the file
            expiry_hours: Custom expiration hours

        Returns:
            UploadedFile model instance

        Raises:
            ValueError: If file validation fails
        """
        # Validate file
        is_valid, error = cls.validate_file(file, purpose)
        if not is_valid:
            raise ValueError(error)

        # Generate storage path
        now = timezone.now()
        file_id = uuid.uuid4()
        relative_path = f"{now.year}/{now.month:02d}/{file_id}"

        # Sanitize filename
        sanitized_name = cls.sanitize_filename(file.name)

        # Create directory
        upload_root = cls.get_upload_root()
        dir_path = upload_root / relative_path
        dir_path.mkdir(parents=True, exist_ok=True)

        # Calculate checksum
        checksum = cls.calculate_checksum(file)

        # Save file to disk
        file_path = dir_path / sanitized_name
        with open(file_path, 'wb') as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        # Calculate expiration
        expiry_hours = expiry_hours or cls.DEFAULT_EXPIRY_HOURS
        expires_at = now + timedelta(hours=expiry_hours)

        # Create database record
        uploaded_file = UploadedFile.objects.create(
            id=file_id,
            filename=sanitized_name,
            original_filename=file.name,
            file_path=f"{relative_path}/{sanitized_name}",
            size=file.size,
            mime_type=file.content_type or 'application/octet-stream',
            purpose=purpose,
            uploaded_by=uploaded_by,
            expires_at=expires_at,
            checksum=checksum,
        )

        logger.info(
            f"File saved: {uploaded_file.original_filename} -> {uploaded_file.file_path}",
            extra={
                'file_id': str(file_id),
                'size': file.size,
                'purpose': purpose,
                'uploaded_by': uploaded_by.username if uploaded_by else None,
            }
        )

        return uploaded_file

    @classmethod
    def get_file_path(cls, file_id: uuid.UUID) -> Optional[str]:
        """
        Get absolute path to file by ID.

        Args:
            file_id: UploadedFile UUID

        Returns:
            Absolute file path or None if not found
        """
        try:
            uploaded_file = UploadedFile.objects.get(id=file_id)
            return uploaded_file.get_absolute_path()
        except UploadedFile.DoesNotExist:
            return None

    @classmethod
    def delete_file(cls, file_id: uuid.UUID) -> bool:
        """
        Delete file from storage and database.

        Uses select_for_update to prevent race conditions.

        Args:
            file_id: UploadedFile UUID

        Returns:
            True if deleted, False if not found
        """
        from django.db import transaction

        abs_path = None

        # Use transaction with select_for_update to prevent race conditions
        with transaction.atomic():
            try:
                uploaded_file = UploadedFile.objects.select_for_update().get(id=file_id)
            except UploadedFile.DoesNotExist:
                return False

            # Get absolute path before deleting record
            try:
                abs_path = uploaded_file.get_absolute_path()
            except ValueError as e:
                logger.error(f"Path traversal attempt during delete: {e}")
                # Still delete the database record
                uploaded_file.delete()
                return True

            # Delete from database
            uploaded_file.delete()

        # Delete file from disk (outside transaction to avoid holding lock)
        if abs_path:
            file_path = Path(abs_path)
            if file_path.exists():
                try:
                    file_path.unlink()

                    # Try to remove empty parent directories
                    parent = file_path.parent
                    if parent.exists() and not any(parent.iterdir()):
                        parent.rmdir()

                    logger.info(f"Deleted file: {abs_path}")
                except OSError as e:
                    logger.warning(f"Failed to delete file {abs_path}: {e}")

        return True

    @classmethod
    def cleanup_expired(cls, batch_size: int = 100) -> int:
        """
        Delete all expired files in batches.

        Args:
            batch_size: Number of files to process per batch (default: 100)

        Returns:
            Number of files deleted
        """
        now = timezone.now()
        count = 0

        # Process in batches to avoid memory issues with large datasets
        while True:
            # Get batch of expired file IDs
            expired_ids = list(
                UploadedFile.objects
                .filter(expires_at__lte=now)
                .values_list('id', flat=True)[:batch_size]
            )

            if not expired_ids:
                break

            for file_id in expired_ids:
                if cls.delete_file(file_id):
                    count += 1

        if count > 0:
            logger.info(f"Cleaned up {count} expired files")

        return count

    @classmethod
    def get_storage_stats(cls) -> dict:
        """
        Get storage statistics.

        Returns:
            Dictionary with storage statistics
        """
        from django.db.models import Sum, Count

        stats = UploadedFile.objects.aggregate(
            total_files=Count('id'),
            total_size=Sum('size'),
        )

        expired_count = UploadedFile.objects.filter(
            expires_at__lte=timezone.now()
        ).count()

        by_purpose = UploadedFile.objects.values('purpose').annotate(
            count=Count('id'),
            size=Sum('size'),
        )

        return {
            'total_files': stats['total_files'] or 0,
            'total_size': stats['total_size'] or 0,
            'expired_files': expired_count,
            'by_purpose': {
                item['purpose']: {
                    'count': item['count'],
                    'size': item['size'] or 0,
                }
                for item in by_purpose
            },
        }
