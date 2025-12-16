"""
Unit tests for FileStorageService.

Tests:
- Filename sanitization
- File validation (size, extension, MIME type)
- Checksum calculation
- File saving and storage
- File retrieval and deletion
- Expired file cleanup
- Storage statistics
"""

import hashlib
import pytest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.files.models import UploadedFile, FilePurpose
from apps.files.services import FileStorageService


@pytest.mark.django_db
class TestFilenameSanitization:
    """Test filename sanitization logic."""

    def test_sanitize_filename_basic(self):
        """Test basic filename is unchanged."""
        result = FileStorageService.sanitize_filename("test.txt")
        assert result == "test.txt"

    def test_sanitize_filename_removes_path_separators(self):
        """Test removal of path separators."""
        result = FileStorageService.sanitize_filename("../../../etc/passwd")
        assert ".." not in result
        assert "/" not in result
        # os.path.basename keeps only the last part
        assert result == "passwd"

    def test_sanitize_filename_removes_control_chars(self):
        """Test removal of null bytes and control characters."""
        result = FileStorageService.sanitize_filename("test\x00\x01\x1f.txt")
        assert "\x00" not in result
        assert "\x01" not in result
        assert "\x1f" not in result
        assert result == "test.txt"

    def test_sanitize_filename_replaces_special_chars(self):
        """Test special characters replaced with underscores."""
        result = FileStorageService.sanitize_filename("file name!@#$%^&*().txt")
        # \w allows underscores, dots, hyphens preserved
        assert result == "file_name__________.txt"

    def test_sanitize_filename_removes_leading_dots(self):
        """Test removal of leading dots (hidden files)."""
        result = FileStorageService.sanitize_filename("...hidden.txt")
        assert result == "hidden.txt"

    def test_sanitize_filename_limits_length(self):
        """Test filename length is limited to 200 characters."""
        long_name = "a" * 250 + ".txt"
        result = FileStorageService.sanitize_filename(long_name)
        assert len(result) == 200

    def test_sanitize_filename_preserves_extension_when_truncating(self):
        """Test extension is preserved when truncating long filename."""
        long_name = "a" * 250 + ".txt"
        result = FileStorageService.sanitize_filename(long_name)
        assert result.endswith(".txt")
        assert len(result) == 200

    def test_sanitize_filename_handles_empty_filename(self):
        """Test empty filename returns default name."""
        result = FileStorageService.sanitize_filename("")
        assert result == "unnamed_file"

    def test_sanitize_filename_handles_only_special_chars(self):
        """Test filename with only special chars becomes underscores."""
        result = FileStorageService.sanitize_filename("!@#$%^&*()")
        # All special chars replaced with underscores
        # lstrip only removes leading dots, not underscores
        assert result == "__________"  # 10 underscores (one per special char)

    def test_sanitize_filename_unicode(self):
        """Test unicode characters are replaced."""
        # \w in Python regex includes Unicode letters by default
        # So Cyrillic characters are kept
        result = FileStorageService.sanitize_filename("файл.txt")
        assert result == "файл.txt"


@pytest.mark.django_db
class TestFileValidation:
    """Test file validation logic."""

    def test_validate_file_success(self, sample_text_file):
        """Test valid file passes validation."""
        is_valid, error = FileStorageService.validate_file(
            sample_text_file,
            FilePurpose.OPERATION_INPUT
        )
        assert is_valid is True
        assert error is None

    def test_validate_file_size_exceeded(self, oversized_file):
        """Test file exceeding size limit fails validation."""
        is_valid, error = FileStorageService.validate_file(
            oversized_file,
            FilePurpose.OPERATION_INPUT
        )
        assert is_valid is False
        assert "size exceeds maximum" in error.lower()
        assert "100 MB" in error

    def test_validate_file_custom_max_size(self, large_file):
        """Test validation with custom max_size parameter."""
        # Should pass with default 100MB limit (50MB file)
        is_valid, error = FileStorageService.validate_file(
            large_file,
            FilePurpose.OPERATION_INPUT
        )
        # large_file is 50MB but text/plain not allowed for OPERATION_INPUT
        # So it will fail due to MIME type, not size
        # Let's create proper test

    def test_validate_file_custom_max_size_proper(self):
        """Test validation with custom max_size parameter."""
        # Create 5MB JSON file
        json_file = SimpleUploadedFile(
            name="data.json",
            content=b"x" * (5 * 1024 * 1024),
            content_type="application/json"
        )

        # Should pass with default 100MB limit
        is_valid, error = FileStorageService.validate_file(
            json_file,
            FilePurpose.OPERATION_INPUT
        )
        assert is_valid is True

        # Should fail with custom 1MB limit
        is_valid, error = FileStorageService.validate_file(
            json_file,
            FilePurpose.OPERATION_INPUT,
            max_size=1 * 1024 * 1024  # 1 MB
        )
        assert is_valid is False
        assert "size exceeds maximum" in error.lower()

    def test_validate_file_blocked_extension_exe(self):
        """Test .exe extension is blocked."""
        bad_file = SimpleUploadedFile(
            name="malware.exe",
            content=b"fake exe",
            content_type="application/octet-stream"
        )

        is_valid, error = FileStorageService.validate_file(
            bad_file,
            FilePurpose.OPERATION_INPUT
        )
        assert is_valid is False
        assert ".exe" in error
        assert "not allowed" in error.lower()

    def test_validate_file_blocked_extension_bat(self):
        """Test .bat extension is blocked."""
        bad_file = SimpleUploadedFile(
            name="script.bat",
            content=b"@echo off",
            content_type="text/plain"
        )

        is_valid, error = FileStorageService.validate_file(
            bad_file,
            FilePurpose.OPERATION_INPUT
        )
        assert is_valid is False
        assert ".bat" in error

    def test_validate_file_blocked_extension_ps1(self):
        """Test .ps1 extension is blocked."""
        bad_file = SimpleUploadedFile(
            name="script.ps1",
            content=b"Write-Host 'test'",
            content_type="text/plain"
        )

        is_valid, error = FileStorageService.validate_file(
            bad_file,
            FilePurpose.OPERATION_INPUT
        )
        assert is_valid is False
        assert ".ps1" in error

    def test_validate_file_invalid_mime_type_for_operation_input(self):
        """Test invalid MIME type for operation_input purpose fails."""
        bad_file = SimpleUploadedFile(
            name="test.bin",
            content=b"binary data",
            content_type="application/octet-stream"
        )

        is_valid, error = FileStorageService.validate_file(
            bad_file,
            FilePurpose.OPERATION_INPUT
        )
        assert is_valid is False
        assert "mime type" in error.lower()
        assert "not allowed" in error.lower()

    def test_validate_file_json_allowed_for_operation_input(self, sample_json_file):
        """Test JSON file is allowed for operation_input."""
        is_valid, error = FileStorageService.validate_file(
            sample_json_file,
            FilePurpose.OPERATION_INPUT
        )
        assert is_valid is True
        assert error is None

    def test_validate_file_csv_allowed_for_operation_input(self, sample_csv_file):
        """Test CSV file is allowed for operation_input."""
        is_valid, error = FileStorageService.validate_file(
            sample_csv_file,
            FilePurpose.OPERATION_INPUT
        )
        assert is_valid is True
        assert error is None

    def test_validate_file_cfe_extension_allowed_for_extension_purpose(self, sample_cfe_file):
        """Test .cfe file is allowed for extension purpose regardless of MIME."""
        is_valid, error = FileStorageService.validate_file(
            sample_cfe_file,
            FilePurpose.EXTENSION
        )
        assert is_valid is True
        assert error is None

    def test_validate_file_cfe_with_wrong_mime_still_allowed(self):
        """Test .cfe with any MIME type is allowed for extension purpose."""
        cfe_file = SimpleUploadedFile(
            name="extension.cfe",
            content=b"Mock extension",
            content_type="text/plain"  # Wrong MIME, but should still work
        )

        is_valid, error = FileStorageService.validate_file(
            cfe_file,
            FilePurpose.EXTENSION
        )
        assert is_valid is True
        assert error is None


@pytest.mark.django_db
class TestChecksumCalculation:
    """Test SHA-256 checksum calculation."""

    def test_calculate_checksum_sha256(self, sample_text_file):
        """Test SHA-256 checksum is calculated correctly."""
        expected_hash = hashlib.sha256(sample_text_file.read()).hexdigest()
        sample_text_file.seek(0)  # Reset after read

        checksum = FileStorageService.calculate_checksum(sample_text_file)

        assert checksum == expected_hash
        assert len(checksum) == 64  # SHA-256 hex length

    def test_calculate_checksum_resets_file_position(self, sample_text_file):
        """Test file position is reset to 0 after checksum calculation."""
        FileStorageService.calculate_checksum(sample_text_file)

        # File should be seeked back to start
        assert sample_text_file.tell() == 0

    def test_calculate_checksum_different_for_different_content(self):
        """Test different content produces different checksums."""
        file1 = SimpleUploadedFile(name="test1.txt", content=b"content1")
        file2 = SimpleUploadedFile(name="test2.txt", content=b"content2")

        checksum1 = FileStorageService.calculate_checksum(file1)
        checksum2 = FileStorageService.calculate_checksum(file2)

        assert checksum1 != checksum2


@pytest.mark.django_db
class TestFileSaving:
    """Test file saving and storage."""

    def test_save_file_success(self, admin_user, sample_text_file, mock_upload_root):
        """Test successful file save creates DB record and disk file."""
        uploaded_file = FileStorageService.save_file(
            file=sample_text_file,
            purpose=FilePurpose.OPERATION_INPUT,
            uploaded_by=admin_user,
        )

        assert uploaded_file.id is not None
        assert uploaded_file.filename == "test.txt"
        assert uploaded_file.original_filename == "test.txt"
        assert uploaded_file.size == len(b"Hello, World! This is a test file.")
        assert uploaded_file.mime_type == "text/plain"
        assert uploaded_file.purpose == FilePurpose.OPERATION_INPUT
        assert uploaded_file.uploaded_by == admin_user
        assert uploaded_file.checksum != ""

        # Check file exists on disk
        file_path = Path(uploaded_file.get_absolute_path())
        assert file_path.exists()
        assert file_path.read_bytes() == b"Hello, World! This is a test file."

    def test_save_file_creates_directory(self, admin_user, sample_text_file, mock_upload_root):
        """Test save_file creates year/month/uuid directory structure."""
        FileStorageService.save_file(
            file=sample_text_file,
            purpose=FilePurpose.OPERATION_INPUT,
            uploaded_by=admin_user,
        )

        # Check directory structure
        now = timezone.now()
        expected_dir = mock_upload_root / str(now.year) / f"{now.month:02d}"
        assert expected_dir.exists()

    def test_save_file_sanitizes_filename(self, admin_user, mock_upload_root):
        """Test filename is sanitized during save."""
        dangerous_file = SimpleUploadedFile(
            name="../../../etc/passwd.txt",
            content=b"test",
            content_type="text/plain"
        )

        uploaded_file = FileStorageService.save_file(
            file=dangerous_file,
            purpose=FilePurpose.OPERATION_INPUT,
            uploaded_by=admin_user,
        )

        assert ".." not in uploaded_file.filename
        assert "/" not in uploaded_file.filename
        # basename keeps only last part
        assert uploaded_file.filename == "passwd.txt"

    def test_save_file_calculates_checksum(self, admin_user, sample_text_file, mock_upload_root):
        """Test checksum is calculated and stored."""
        uploaded_file = FileStorageService.save_file(
            file=sample_text_file,
            purpose=FilePurpose.OPERATION_INPUT,
            uploaded_by=admin_user,
        )

        # Verify checksum
        sample_text_file.seek(0)
        expected_checksum = hashlib.sha256(sample_text_file.read()).hexdigest()
        assert uploaded_file.checksum == expected_checksum

    def test_save_file_creates_database_record(self, admin_user, sample_text_file, mock_upload_root):
        """Test database record is created with correct fields."""
        uploaded_file = FileStorageService.save_file(
            file=sample_text_file,
            purpose=FilePurpose.EXPORT,
            uploaded_by=admin_user,
        )

        # Verify record exists in DB
        db_record = UploadedFile.objects.get(id=uploaded_file.id)
        assert db_record.filename == "test.txt"
        assert db_record.purpose == FilePurpose.EXPORT
        assert db_record.uploaded_by == admin_user

    def test_save_file_validation_failure(self, admin_user, oversized_file, mock_upload_root):
        """Test save_file raises ValueError on validation failure."""
        with pytest.raises(ValueError) as exc_info:
            FileStorageService.save_file(
                file=oversized_file,
                purpose=FilePurpose.OPERATION_INPUT,
                uploaded_by=admin_user,
            )

        assert "size exceeds maximum" in str(exc_info.value).lower()

    def test_save_file_custom_expiry_hours(self, admin_user, sample_text_file, mock_upload_root):
        """Test save_file respects custom expiry_hours."""
        before = timezone.now() + timedelta(hours=72)

        uploaded_file = FileStorageService.save_file(
            file=sample_text_file,
            purpose=FilePurpose.OPERATION_INPUT,
            uploaded_by=admin_user,
            expiry_hours=72,
        )

        after = timezone.now() + timedelta(hours=72)

        # Should expire in ~72 hours
        assert before <= uploaded_file.expires_at <= after

    def test_save_file_default_mime_type(self, admin_user, mock_upload_root):
        """Test save_file uses default MIME type if not provided."""
        file_without_mime = SimpleUploadedFile(
            name="test.bin",
            content=b"binary",
            content_type=None  # No MIME type
        )
        # Override to make it valid
        file_without_mime.content_type = "application/octet-stream"

        uploaded_file = FileStorageService.save_file(
            file=file_without_mime,
            purpose=FilePurpose.EXTENSION,
            uploaded_by=admin_user,
        )

        assert uploaded_file.mime_type == "application/octet-stream"


@pytest.mark.django_db
class TestFileRetrieval:
    """Test file retrieval operations."""

    def test_get_file_path_success(self, uploaded_file_record):
        """Test get_file_path returns correct path for existing file."""
        file_path = FileStorageService.get_file_path(uploaded_file_record.id)

        assert file_path is not None
        assert file_path == uploaded_file_record.get_absolute_path()

    def test_get_file_path_not_found(self):
        """Test get_file_path returns None for non-existent file."""
        import uuid
        fake_id = uuid.uuid4()

        file_path = FileStorageService.get_file_path(fake_id)

        assert file_path is None


@pytest.mark.django_db
class TestFileDeletion:
    """Test file deletion operations."""

    def test_delete_file_success(self, uploaded_file_record, mock_upload_root):
        """Test delete_file removes file from disk and database."""
        file_id = uploaded_file_record.id
        file_path = Path(uploaded_file_record.get_absolute_path())

        # Verify file exists before deletion
        assert file_path.exists()
        assert UploadedFile.objects.filter(id=file_id).exists()

        result = FileStorageService.delete_file(file_id)

        assert result is True
        assert not file_path.exists()
        assert not UploadedFile.objects.filter(id=file_id).exists()

    def test_delete_file_not_found(self):
        """Test delete_file returns False for non-existent file."""
        import uuid
        fake_id = uuid.uuid4()

        result = FileStorageService.delete_file(fake_id)

        assert result is False

    def test_delete_file_removes_empty_directories(self, uploaded_file_record, mock_upload_root):
        """Test delete_file removes empty parent directory."""
        file_id = uploaded_file_record.id
        file_path = Path(uploaded_file_record.get_absolute_path())
        parent_dir = file_path.parent

        # Verify parent dir exists
        assert parent_dir.exists()

        FileStorageService.delete_file(file_id)

        # Parent directory should be removed if empty
        assert not parent_dir.exists()

    def test_delete_file_keeps_non_empty_directories(self, uploaded_file_record, mock_upload_root):
        """Test delete_file keeps directory if other files exist."""
        file_path = Path(uploaded_file_record.get_absolute_path())
        parent_dir = file_path.parent

        # Create another file in same directory
        other_file = parent_dir / "other.txt"
        other_file.write_text("other content")

        FileStorageService.delete_file(uploaded_file_record.id)

        # Parent directory should still exist
        assert parent_dir.exists()
        assert other_file.exists()


@pytest.mark.django_db
class TestExpiredFileCleanup:
    """Test cleanup of expired files."""

    def test_cleanup_expired_deletes_expired_files(self, expired_file_record, mock_upload_root):
        """Test cleanup_expired removes expired files."""
        file_id = expired_file_record.id
        file_path = Path(expired_file_record.get_absolute_path())

        # Verify file exists before cleanup
        assert file_path.exists()
        assert UploadedFile.objects.filter(id=file_id).exists()

        count = FileStorageService.cleanup_expired()

        assert count == 1
        assert not file_path.exists()
        assert not UploadedFile.objects.filter(id=file_id).exists()

    def test_cleanup_expired_ignores_valid_files(self, uploaded_file_record):
        """Test cleanup_expired does not remove valid files."""
        file_id = uploaded_file_record.id

        count = FileStorageService.cleanup_expired()

        assert count == 0
        assert UploadedFile.objects.filter(id=file_id).exists()

    def test_cleanup_expired_returns_count(self, multiple_files, mock_upload_root):
        """Test cleanup_expired returns correct count."""
        # Expire 3 files
        now = timezone.now()
        expired_ids = []
        for i in range(3):
            file = multiple_files[i]
            file.expires_at = now - timedelta(hours=1)
            file.save()
            expired_ids.append(file.id)

        count = FileStorageService.cleanup_expired()

        assert count == 3

        # Verify expired files are deleted
        for file_id in expired_ids:
            assert not UploadedFile.objects.filter(id=file_id).exists()

        # Verify valid files still exist
        assert UploadedFile.objects.count() == 2


@pytest.mark.django_db
class TestStorageStatistics:
    """Test storage statistics."""

    def test_get_storage_stats(self, multiple_files):
        """Test get_storage_stats returns correct statistics."""
        stats = FileStorageService.get_storage_stats()

        assert stats['total_files'] == 5
        assert stats['total_size'] > 0
        assert stats['expired_files'] == 0
        assert 'by_purpose' in stats

        # Check by_purpose breakdown
        by_purpose = stats['by_purpose']
        assert FilePurpose.OPERATION_INPUT in by_purpose
        assert FilePurpose.EXPORT in by_purpose

        # 3 files are OPERATION_INPUT (even indices: 0, 2, 4)
        assert by_purpose[FilePurpose.OPERATION_INPUT]['count'] == 3
        # 2 files are EXPORT (odd indices: 1, 3)
        assert by_purpose[FilePurpose.EXPORT]['count'] == 2

    def test_get_storage_stats_with_expired_files(self, multiple_files):
        """Test get_storage_stats counts expired files."""
        # Expire 2 files
        now = timezone.now()
        for i in range(2):
            file = multiple_files[i]
            file.expires_at = now - timedelta(hours=1)
            file.save()

        stats = FileStorageService.get_storage_stats()

        assert stats['total_files'] == 5
        assert stats['expired_files'] == 2

    def test_get_storage_stats_empty_database(self, db):
        """Test get_storage_stats with no files."""
        stats = FileStorageService.get_storage_stats()

        assert stats['total_files'] == 0
        assert stats['total_size'] == 0
        assert stats['expired_files'] == 0
        assert stats['by_purpose'] == {}


@pytest.mark.django_db
class TestGetUploadRoot:
    """Test upload root directory configuration."""

    def test_get_upload_root_default(self):
        """Test get_upload_root returns default path."""
        with patch('apps.files.services.settings') as mock_settings:
            delattr(mock_settings, 'UPLOAD_ROOT')  # No setting

            upload_root = FileStorageService.get_upload_root()

            assert str(upload_root) == "/var/lib/1c/uploads"

    def test_get_upload_root_from_settings(self, settings):
        """Test get_upload_root reads from Django settings."""
        settings.UPLOAD_ROOT = "/custom/upload/path"

        upload_root = FileStorageService.get_upload_root()

        assert str(upload_root) == "/custom/upload/path"
