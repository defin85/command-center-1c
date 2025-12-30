"""
Pytest fixtures for files app tests.
"""

import pytest
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.files.models import UploadedFile, FilePurpose


User = get_user_model()


@pytest.fixture
def admin_user(db):
    """Create admin user for tests."""
    # Cleanup: delete existing user if present
    User.objects.filter(username='testadmin').delete()

    return User.objects.create_user(
        username='testadmin',
        email='admin@test.com',
        password='testpass123',
        is_staff=True
    )


@pytest.fixture
def regular_user(db):
    """Create regular user for tests."""
    # Cleanup: delete existing user if present
    User.objects.filter(username='testuser').delete()

    return User.objects.create_user(
        username='testuser',
        email='user@test.com',
        password='testpass123',
    )


@pytest.fixture
def other_user(db):
    """Create another user for IDOR tests."""
    # Cleanup: delete existing user if present
    User.objects.filter(username='otheruser').delete()

    return User.objects.create_user(
        username='otheruser',
        email='other@test.com',
        password='testpass123',
    )


@pytest.fixture
def other_user_client(api_client, other_user):
    """Create authenticated API client for other_user."""
    api_client.force_authenticate(user=other_user)
    return api_client


@pytest.fixture
def regular_user_client(api_client, regular_user):
    """Create authenticated API client for regular_user."""
    api_client.force_authenticate(user=regular_user)
    return api_client


@pytest.fixture
def api_client():
    """Create DRF API client."""
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, admin_user):
    """Create authenticated API client."""
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def mock_upload_root(tmp_path, settings):
    """Set UPLOAD_ROOT to temporary directory."""
    upload_root = tmp_path / "uploads"
    upload_root.mkdir(exist_ok=True)
    settings.UPLOAD_ROOT = str(upload_root)
    return upload_root


@pytest.fixture
def sample_text_file():
    """Create sample text file for uploads."""
    content = b"Hello, World! This is a test file."
    return SimpleUploadedFile(
        name="test.txt",
        content=content,
        content_type="text/plain"
    )


@pytest.fixture
def sample_json_file():
    """Create sample JSON file for uploads."""
    content = b'{"key": "value", "number": 42}'
    return SimpleUploadedFile(
        name="data.json",
        content=content,
        content_type="application/json"
    )


@pytest.fixture
def sample_csv_file():
    """Create sample CSV file for uploads."""
    content = b"id,name,value\n1,test,100\n2,demo,200"
    return SimpleUploadedFile(
        name="data.csv",
        content=content,
        content_type="text/csv"
    )


@pytest.fixture
def sample_cfe_file():
    """Create sample .cfe file (1C extension)."""
    content = b"\x00\x01\x02\x03" + b"Mock 1C Extension File" + b"\x00" * 100
    return SimpleUploadedFile(
        name="extension.cfe",
        content=content,
        content_type="application/octet-stream"
    )


@pytest.fixture
def large_file():
    """Create large file (50MB) for size validation tests."""
    size = 50 * 1024 * 1024  # 50 MB
    content = b"x" * size
    return SimpleUploadedFile(
        name="large.bin",
        content=content,
        content_type="application/octet-stream"
    )


@pytest.fixture
def oversized_file():
    """Create oversized file (150MB) exceeding limit."""
    size = 150 * 1024 * 1024  # 150 MB
    # Don't actually create 150MB in memory - mock it
    file = SimpleUploadedFile(
        name="huge.bin",
        content=b"x" * 1024,  # Small actual content
        content_type="application/octet-stream"
    )
    file.size = size  # Override size
    return file


@pytest.fixture
def uploaded_file_record(db, admin_user, mock_upload_root):
    """Create UploadedFile record with actual file on disk."""
    # Create file on disk
    now = timezone.now()
    file_id = "12345678-1234-5678-1234-567812345678"
    relative_path = f"{now.year}/{now.month:02d}/{file_id}"
    file_path = mock_upload_root / relative_path
    file_path.mkdir(parents=True, exist_ok=True)

    test_file = file_path / "test.txt"
    test_file.write_text("Test content")

    # Create database record
    return UploadedFile.objects.create(
        id=file_id,
        filename="test.txt",
        original_filename="test.txt",
        file_path=f"{relative_path}/test.txt",
        size=len("Test content"),
        mime_type="text/plain",
        purpose=FilePurpose.OPERATION_INPUT,
        uploaded_by=admin_user,
        expires_at=now + timedelta(hours=24),
        checksum="abc123def456",
    )


@pytest.fixture
def expired_file_record(db, admin_user, mock_upload_root):
    """Create expired UploadedFile record."""
    # Create file on disk
    now = timezone.now()
    file_id = "87654321-4321-8765-4321-876543218765"
    relative_path = f"{now.year}/{now.month:02d}/{file_id}"
    file_path = mock_upload_root / relative_path
    file_path.mkdir(parents=True, exist_ok=True)

    expired_file = file_path / "expired.txt"
    expired_file.write_text("Expired content")

    # Create database record with past expiration
    return UploadedFile.objects.create(
        id=file_id,
        filename="expired.txt",
        original_filename="expired.txt",
        file_path=f"{relative_path}/expired.txt",
        size=len("Expired content"),
        mime_type="text/plain",
        purpose=FilePurpose.EXPORT,
        uploaded_by=admin_user,
        expires_at=now - timedelta(hours=1),  # Expired 1 hour ago
        checksum="expired123",
    )


@pytest.fixture
def multiple_files(db, admin_user, mock_upload_root):
    """Create multiple UploadedFile records for testing queries."""
    now = timezone.now()
    files = []

    for i in range(5):
        file_id = f"00000000-0000-0000-0000-{i:012d}"
        relative_path = f"{now.year}/{now.month:02d}/{file_id}"
        file_path = mock_upload_root / relative_path
        file_path.mkdir(parents=True, exist_ok=True)

        test_file = file_path / f"file_{i}.txt"
        test_file.write_text(f"Content {i}")

        uploaded = UploadedFile.objects.create(
            id=file_id,
            filename=f"file_{i}.txt",
            original_filename=f"file_{i}.txt",
            file_path=f"{relative_path}/file_{i}.txt",
            size=len(f"Content {i}"),
            mime_type="text/plain",
            purpose=FilePurpose.OPERATION_INPUT if i % 2 == 0 else FilePurpose.EXPORT,
            uploaded_by=admin_user,
            expires_at=now + timedelta(hours=24),
            checksum=f"checksum_{i}",
        )
        files.append(uploaded)

    return files
