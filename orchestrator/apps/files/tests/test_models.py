"""
Unit tests for UploadedFile model.

Tests:
- Model creation and defaults
- String representation
- Expiration handling
- File size formatting
- Helper methods (extend_expiration, mark_processed, get_absolute_path)
"""

import pytest
from datetime import timedelta
from django.utils import timezone

from apps.files.models import UploadedFile, FilePurpose, get_default_expires_at


@pytest.mark.django_db
class TestUploadedFileModel:
    """Test UploadedFile model."""

    def test_uploaded_file_creation(self, admin_user):
        """Test creating UploadedFile record with all fields."""
        now = timezone.now()
        expires_at = now + timedelta(hours=48)

        uploaded_file = UploadedFile.objects.create(
            filename="sanitized.txt",
            original_filename="Original File.txt",
            file_path="2025/12/abc-123/sanitized.txt",
            size=1024,
            mime_type="text/plain",
            purpose=FilePurpose.OPERATION_INPUT,
            uploaded_by=admin_user,
            expires_at=expires_at,
            checksum="abc123def456",
        )

        assert uploaded_file.id is not None  # UUID auto-generated
        assert uploaded_file.filename == "sanitized.txt"
        assert uploaded_file.original_filename == "Original File.txt"
        assert uploaded_file.size == 1024
        assert uploaded_file.purpose == FilePurpose.OPERATION_INPUT
        assert uploaded_file.uploaded_by == admin_user
        assert uploaded_file.expires_at == expires_at
        assert uploaded_file.is_processed is False  # Default
        assert uploaded_file.checksum == "abc123def456"

    def test_uploaded_file_str(self, admin_user):
        """Test __str__ method returns original filename and purpose."""
        uploaded_file = UploadedFile.objects.create(
            filename="test.txt",
            original_filename="My Document.txt",
            file_path="2025/12/abc/test.txt",
            size=100,
            mime_type="text/plain",
            purpose=FilePurpose.EXTENSION,
            uploaded_by=admin_user,
        )

        expected = "My Document.txt (extension)"
        assert str(uploaded_file) == expected

    def test_get_default_expires_at(self):
        """Test get_default_expires_at returns 24 hours from now."""
        before = timezone.now()
        expires_at = get_default_expires_at()
        after = timezone.now()

        # Should be approximately 24 hours from now
        expected_min = before + timedelta(hours=24)
        expected_max = after + timedelta(hours=24)

        assert expected_min <= expires_at <= expected_max

    def test_uploaded_file_default_expiry(self, admin_user):
        """Test UploadedFile uses default expiration (24 hours)."""
        before = timezone.now() + timedelta(hours=24)

        uploaded_file = UploadedFile.objects.create(
            filename="test.txt",
            original_filename="test.txt",
            file_path="2025/12/abc/test.txt",
            size=100,
            mime_type="text/plain",
            purpose=FilePurpose.OPERATION_INPUT,
            uploaded_by=admin_user,
        )

        after = timezone.now() + timedelta(hours=24)

        # expires_at should be ~24 hours from creation
        assert before <= uploaded_file.expires_at <= after

    def test_is_expired_property_false(self, uploaded_file_record):
        """Test is_expired property returns False for valid file."""
        assert uploaded_file_record.is_expired is False

    def test_is_expired_property_true(self, expired_file_record):
        """Test is_expired property returns True for expired file."""
        assert expired_file_record.is_expired is True

    def test_size_human_bytes(self, admin_user):
        """Test size_human returns bytes format."""
        uploaded_file = UploadedFile.objects.create(
            filename="tiny.txt",
            original_filename="tiny.txt",
            file_path="2025/12/abc/tiny.txt",
            size=512,
            mime_type="text/plain",
            purpose=FilePurpose.OPERATION_INPUT,
            uploaded_by=admin_user,
        )

        assert uploaded_file.size_human == "512.0 B"

    def test_size_human_kilobytes(self, admin_user):
        """Test size_human returns KB format."""
        uploaded_file = UploadedFile.objects.create(
            filename="small.txt",
            original_filename="small.txt",
            file_path="2025/12/abc/small.txt",
            size=10 * 1024,  # 10 KB
            mime_type="text/plain",
            purpose=FilePurpose.OPERATION_INPUT,
            uploaded_by=admin_user,
        )

        assert uploaded_file.size_human == "10.0 KB"

    def test_size_human_megabytes(self, admin_user):
        """Test size_human returns MB format."""
        uploaded_file = UploadedFile.objects.create(
            filename="medium.txt",
            original_filename="medium.txt",
            file_path="2025/12/abc/medium.txt",
            size=5 * 1024 * 1024,  # 5 MB
            mime_type="text/plain",
            purpose=FilePurpose.OPERATION_INPUT,
            uploaded_by=admin_user,
        )

        assert uploaded_file.size_human == "5.0 MB"

    def test_size_human_gigabytes(self, admin_user):
        """Test size_human returns GB format."""
        uploaded_file = UploadedFile.objects.create(
            filename="large.txt",
            original_filename="large.txt",
            file_path="2025/12/abc/large.txt",
            size=2 * 1024 * 1024 * 1024,  # 2 GB
            mime_type="text/plain",
            purpose=FilePurpose.OPERATION_INPUT,
            uploaded_by=admin_user,
        )

        assert uploaded_file.size_human == "2.0 GB"

    def test_extend_expiration(self, uploaded_file_record):
        """Test extend_expiration extends file expiration."""
        original_expires = uploaded_file_record.expires_at

        # Extend by 48 hours
        uploaded_file_record.extend_expiration(hours=48)
        uploaded_file_record.refresh_from_db()

        # New expiration should be ~48 hours from now (not from original)
        expected = timezone.now() + timedelta(hours=48)

        # Allow 1 second tolerance
        assert abs((uploaded_file_record.expires_at - expected).total_seconds()) < 1
        assert uploaded_file_record.expires_at > original_expires

    def test_mark_processed(self, uploaded_file_record):
        """Test mark_processed sets is_processed to True."""
        assert uploaded_file_record.is_processed is False

        uploaded_file_record.mark_processed()
        uploaded_file_record.refresh_from_db()

        assert uploaded_file_record.is_processed is True

    def test_get_absolute_path(self, uploaded_file_record, mock_upload_root):
        """Test get_absolute_path returns full filesystem path."""
        expected_path = f"{mock_upload_root}/{uploaded_file_record.file_path}"
        actual_path = uploaded_file_record.get_absolute_path()

        assert actual_path == expected_path

    def test_get_absolute_path_with_custom_upload_root(self, admin_user, settings):
        """Test get_absolute_path uses UPLOAD_ROOT from settings."""
        settings.UPLOAD_ROOT = "/custom/upload/path"

        uploaded_file = UploadedFile.objects.create(
            filename="test.txt",
            original_filename="test.txt",
            file_path="2025/12/abc/test.txt",
            size=100,
            mime_type="text/plain",
            purpose=FilePurpose.OPERATION_INPUT,
            uploaded_by=admin_user,
        )

        expected = "/custom/upload/path/2025/12/abc/test.txt"
        assert uploaded_file.get_absolute_path() == expected

    def test_uploaded_file_ordering(self, multiple_files):
        """Test UploadedFile default ordering by -created_at."""
        files = UploadedFile.objects.all()

        # Should be ordered by created_at descending (newest first)
        for i in range(len(files) - 1):
            assert files[i].created_at >= files[i + 1].created_at

    def test_file_purpose_choices(self):
        """Test FilePurpose enum has correct values."""
        assert FilePurpose.OPERATION_INPUT == "operation_input"
        assert FilePurpose.EXTENSION == "extension"
        assert FilePurpose.EXPORT == "export"

        # Test choices
        choices_dict = dict(FilePurpose.choices)
        assert choices_dict["operation_input"] == "Operation Input"
        assert choices_dict["extension"] == "Extension File"
        assert choices_dict["export"] == "Export File"
