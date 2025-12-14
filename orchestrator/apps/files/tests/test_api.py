"""
Unit tests for Files API endpoints.

Tests:
- POST /api/v2/files/upload/ - file upload
- GET /api/v2/files/download/<file_id>/ - file download
- DELETE /api/v2/files/delete/<file_id>/ - file deletion
"""

import pytest
import uuid
from unittest.mock import patch

from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.files.models import UploadedFile, FilePurpose


@pytest.mark.django_db
class TestFileUploadAPI:
    """Test POST /api/v2/files/upload/ endpoint."""

    def test_upload_file_success(self, authenticated_client, sample_text_file, mock_upload_root):
        """Test successful file upload returns 201 with file metadata."""
        url = '/api/v2/files/upload/'
        data = {
            'file': sample_text_file,
            'purpose': FilePurpose.OPERATION_INPUT,
        }

        response = authenticated_client.post(url, data, format='multipart')

        assert response.status_code == status.HTTP_201_CREATED
        assert 'file' in response.data
        assert 'message' in response.data

        file_data = response.data['file']
        assert file_data['filename'] == 'test.txt'
        assert file_data['original_filename'] == 'test.txt'
        assert file_data['purpose'] == FilePurpose.OPERATION_INPUT
        assert file_data['size'] > 0
        assert file_data['checksum'] != ''

        # Verify database record
        file_id = file_data['id']
        assert UploadedFile.objects.filter(id=file_id).exists()

    def test_upload_file_no_file(self, authenticated_client):
        """Test upload without file returns 400 MISSING_FILE."""
        url = '/api/v2/files/upload/'
        data = {
            'purpose': FilePurpose.OPERATION_INPUT,
        }

        response = authenticated_client.post(url, data, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'MISSING_FILE'

    def test_upload_file_missing_purpose(self, authenticated_client, sample_text_file):
        """Test upload without purpose returns 400 MISSING_PARAMETER."""
        url = '/api/v2/files/upload/'
        data = {
            'file': sample_text_file,
        }

        response = authenticated_client.post(url, data, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'MISSING_PARAMETER'
        assert 'purpose' in response.data['error']['message']

    def test_upload_file_invalid_purpose(self, authenticated_client, sample_text_file):
        """Test upload with invalid purpose returns 400 INVALID_PURPOSE."""
        url = '/api/v2/files/upload/'
        data = {
            'file': sample_text_file,
            'purpose': 'invalid_purpose',
        }

        response = authenticated_client.post(url, data, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'INVALID_PURPOSE'

    def test_upload_file_too_large(self, authenticated_client, mock_upload_root):
        """Test upload of oversized file returns 400 VALIDATION_ERROR."""
        # Create oversized file with proper MIME type for OPERATION_INPUT
        # Use patch to mock validate_file to return size error
        from apps.files.services import FileStorageService

        url = '/api/v2/files/upload/'
        sample_file = SimpleUploadedFile(
            name="test.json",
            content=b"test",
            content_type="application/json"
        )
        data = {
            'file': sample_file,
            'purpose': FilePurpose.OPERATION_INPUT,
        }

        with patch.object(FileStorageService, 'validate_file', return_value=(False, "File size exceeds maximum allowed (100 MB)")):
            response = authenticated_client.post(url, data, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'VALIDATION_ERROR'
        assert 'size' in response.data['error']['message'].lower()

    def test_upload_file_invalid_extension(self, authenticated_client, mock_upload_root):
        """Test upload of file with blocked extension returns 400."""
        bad_file = SimpleUploadedFile(
            name="malware.exe",
            content=b"fake executable",
            content_type="application/octet-stream"
        )

        url = '/api/v2/files/upload/'
        data = {
            'file': bad_file,
            'purpose': FilePurpose.OPERATION_INPUT,
        }

        response = authenticated_client.post(url, data, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'VALIDATION_ERROR'
        assert '.exe' in response.data['error']['message']

    def test_upload_file_invalid_mime_type(self, authenticated_client, mock_upload_root):
        """Test upload with invalid MIME type for purpose returns 400."""
        bad_file = SimpleUploadedFile(
            name="test.bin",
            content=b"binary data",
            content_type="application/octet-stream"
        )

        url = '/api/v2/files/upload/'
        data = {
            'file': bad_file,
            'purpose': FilePurpose.OPERATION_INPUT,
        }

        response = authenticated_client.post(url, data, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'VALIDATION_ERROR'
        assert 'mime type' in response.data['error']['message'].lower()

    def test_upload_file_custom_expiry_hours(self, authenticated_client, sample_text_file, mock_upload_root):
        """Test upload with custom expiry_hours."""
        url = '/api/v2/files/upload/'
        data = {
            'file': sample_text_file,
            'purpose': FilePurpose.OPERATION_INPUT,
            'expiry_hours': 48,
        }

        response = authenticated_client.post(url, data, format='multipart')

        assert response.status_code == status.HTTP_201_CREATED

        # Verify expiration is ~48 hours
        file_id = response.data['file']['id']
        uploaded_file = UploadedFile.objects.get(id=file_id)

        from datetime import timedelta
        from django.utils import timezone
        expected = timezone.now() + timedelta(hours=48)
        # Allow 2 second tolerance
        assert abs((uploaded_file.expires_at - expected).total_seconds()) < 2

    def test_upload_file_invalid_expiry_hours_too_small(self, authenticated_client, sample_text_file):
        """Test upload with expiry_hours < 1 returns 400."""
        url = '/api/v2/files/upload/'
        data = {
            'file': sample_text_file,
            'purpose': FilePurpose.OPERATION_INPUT,
            'expiry_hours': 0,
        }

        response = authenticated_client.post(url, data, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error']['code'] == 'INVALID_EXPIRY'

    def test_upload_file_invalid_expiry_hours_too_large(self, authenticated_client, sample_text_file):
        """Test upload with expiry_hours > 168 returns 400."""
        url = '/api/v2/files/upload/'
        data = {
            'file': sample_text_file,
            'purpose': FilePurpose.OPERATION_INPUT,
            'expiry_hours': 200,
        }

        response = authenticated_client.post(url, data, format='multipart')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error']['code'] == 'INVALID_EXPIRY'

    def test_upload_file_invalid_expiry_hours_ignored(self, authenticated_client, sample_text_file, mock_upload_root):
        """Test upload with non-numeric expiry_hours is ignored (uses default)."""
        url = '/api/v2/files/upload/'
        data = {
            'file': sample_text_file,
            'purpose': FilePurpose.OPERATION_INPUT,
            'expiry_hours': 'invalid',
        }

        response = authenticated_client.post(url, data, format='multipart')

        # Should succeed with default expiry
        assert response.status_code == status.HTTP_201_CREATED

    def test_upload_file_unauthenticated(self, api_client, sample_text_file):
        """Test upload without authentication returns 401."""
        url = '/api/v2/files/upload/'
        data = {
            'file': sample_text_file,
            'purpose': FilePurpose.OPERATION_INPUT,
        }

        response = api_client.post(url, data, format='multipart')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_upload_file_json_allowed(self, authenticated_client, sample_json_file, mock_upload_root):
        """Test uploading JSON file for operation_input succeeds."""
        url = '/api/v2/files/upload/'
        data = {
            'file': sample_json_file,
            'purpose': FilePurpose.OPERATION_INPUT,
        }

        response = authenticated_client.post(url, data, format='multipart')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['file']['mime_type'] == 'application/json'

    def test_upload_file_csv_allowed(self, authenticated_client, sample_csv_file, mock_upload_root):
        """Test uploading CSV file for operation_input succeeds."""
        url = '/api/v2/files/upload/'
        data = {
            'file': sample_csv_file,
            'purpose': FilePurpose.OPERATION_INPUT,
        }

        response = authenticated_client.post(url, data, format='multipart')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['file']['mime_type'] == 'text/csv'

    def test_upload_file_cfe_extension(self, authenticated_client, sample_cfe_file, mock_upload_root):
        """Test uploading .cfe extension file succeeds."""
        url = '/api/v2/files/upload/'
        data = {
            'file': sample_cfe_file,
            'purpose': FilePurpose.EXTENSION,
        }

        response = authenticated_client.post(url, data, format='multipart')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['file']['filename'] == 'extension.cfe'


@pytest.mark.django_db
class TestFileDownloadAPI:
    """Test GET /api/v2/files/download/<file_id>/ endpoint."""

    def test_download_file_success(self, authenticated_client, uploaded_file_record):
        """Test successful file download returns file content."""
        url = f'/api/v2/files/download/{uploaded_file_record.id}/'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'text/plain'
        assert 'attachment' in response['Content-Disposition']
        assert 'test.txt' in response['Content-Disposition']
        assert int(response['Content-Length']) == uploaded_file_record.size

    def test_download_file_invalid_uuid(self, authenticated_client):
        """Test download with invalid UUID returns 404 (URL not found)."""
        url = '/api/v2/files/download/not-a-uuid/'

        response = authenticated_client.get(url)

        # Django REST Framework returns 404 for invalid UUID in URL path
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_download_file_not_found(self, authenticated_client):
        """Test download of non-existent file returns 404."""
        fake_id = uuid.uuid4()
        url = f'/api/v2/files/download/{fake_id}/'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data['error']['code'] == 'FILE_NOT_FOUND'

    def test_download_file_expired(self, authenticated_client, expired_file_record):
        """Test download of expired file returns 410 GONE."""
        url = f'/api/v2/files/download/{expired_file_record.id}/'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_410_GONE
        assert response.data['error']['code'] == 'FILE_EXPIRED'

    def test_download_file_not_found_on_disk(self, authenticated_client, uploaded_file_record, mock_upload_root):
        """Test download when file exists in DB but not on disk returns 404."""
        # Delete file from disk but keep DB record
        from pathlib import Path
        file_path = Path(uploaded_file_record.get_absolute_path())
        file_path.unlink()

        url = f'/api/v2/files/download/{uploaded_file_record.id}/'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data['error']['code'] == 'FILE_NOT_FOUND'

    def test_download_file_headers(self, authenticated_client, uploaded_file_record):
        """Test download response has correct headers."""
        url = f'/api/v2/files/download/{uploaded_file_record.id}/'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == uploaded_file_record.mime_type
        assert 'attachment' in response['Content-Disposition']
        assert uploaded_file_record.original_filename in response['Content-Disposition']
        assert response['Content-Length'] == str(uploaded_file_record.size)

    def test_download_file_unauthenticated(self, api_client, uploaded_file_record):
        """Test download without authentication returns 401."""
        url = f'/api/v2/files/download/{uploaded_file_record.id}/'

        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestFileDeleteAPI:
    """Test DELETE /api/v2/files/delete/<file_id>/ endpoint."""

    def test_delete_file_success(self, authenticated_client, uploaded_file_record, mock_upload_root):
        """Test successful file deletion returns 200."""
        file_id = uploaded_file_record.id
        url = f'/api/v2/files/delete/{file_id}/'

        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['deleted'] is True
        assert response.data['file_id'] == str(file_id)
        assert 'successfully' in response.data['message'].lower()

        # Verify file is deleted from database
        assert not UploadedFile.objects.filter(id=file_id).exists()

    def test_delete_file_invalid_uuid(self, authenticated_client):
        """Test delete with invalid UUID returns 404 (URL not found)."""
        url = '/api/v2/files/delete/not-a-uuid/'

        response = authenticated_client.delete(url)

        # Django REST Framework returns 404 for invalid UUID in URL path
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_file_not_found(self, authenticated_client):
        """Test delete of non-existent file returns 404."""
        fake_id = uuid.uuid4()
        url = f'/api/v2/files/delete/{fake_id}/'

        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data['error']['code'] == 'FILE_NOT_FOUND'

    def test_delete_file_unauthenticated(self, api_client, uploaded_file_record):
        """Test delete without authentication returns 401."""
        url = f'/api/v2/files/delete/{uploaded_file_record.id}/'

        response = api_client.delete(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_file_removes_from_disk(self, authenticated_client, uploaded_file_record, mock_upload_root):
        """Test delete removes file from filesystem."""
        from pathlib import Path
        file_path = Path(uploaded_file_record.get_absolute_path())

        # Verify file exists before deletion
        assert file_path.exists()

        url = f'/api/v2/files/delete/{uploaded_file_record.id}/'
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_200_OK

        # Verify file is removed from disk
        assert not file_path.exists()


@pytest.mark.django_db
class TestFilePermissions:
    """Test IDOR protection for file access."""

    def test_download_file_by_other_user_denied(self, other_user_client, uploaded_file_record):
        """Test that user cannot download another user's file (IDOR protection)."""
        url = f'/api/v2/files/download/{uploaded_file_record.id}/'

        response = other_user_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data['error']['code'] == 'PERMISSION_DENIED'

    def test_download_file_by_owner_allowed(self, authenticated_client, uploaded_file_record):
        """Test that file owner can download their own file."""
        url = f'/api/v2/files/download/{uploaded_file_record.id}/'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK

    def test_download_file_by_staff_allowed(self, authenticated_client, uploaded_file_record, other_user):
        """Test that staff user can download any file."""
        # authenticated_client uses admin_user which is_staff=True
        url = f'/api/v2/files/download/{uploaded_file_record.id}/'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK

    def test_delete_file_by_other_user_denied(self, other_user_client, uploaded_file_record):
        """Test that user cannot delete another user's file (IDOR protection)."""
        url = f'/api/v2/files/delete/{uploaded_file_record.id}/'

        response = other_user_client.delete(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data['error']['code'] == 'PERMISSION_DENIED'

        # Verify file still exists
        assert UploadedFile.objects.filter(id=uploaded_file_record.id).exists()

    def test_delete_file_by_owner_allowed(self, authenticated_client, uploaded_file_record, mock_upload_root):
        """Test that file owner can delete their own file."""
        file_id = uploaded_file_record.id
        url = f'/api/v2/files/delete/{file_id}/'

        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['deleted'] is True

        # Verify file is deleted
        assert not UploadedFile.objects.filter(id=file_id).exists()

    def test_delete_file_by_staff_allowed(self, authenticated_client, uploaded_file_record, mock_upload_root, other_user):
        """Test that staff user can delete any file."""
        file_id = uploaded_file_record.id
        url = f'/api/v2/files/delete/{file_id}/'

        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['deleted'] is True


@pytest.mark.django_db
class TestFileAPIIntegration:
    """Integration tests for file upload-download-delete flow."""

    def test_full_file_lifecycle(self, authenticated_client, sample_text_file, mock_upload_root):
        """Test complete file lifecycle: upload -> download -> delete."""
        # 1. Upload
        upload_url = '/api/v2/files/upload/'
        upload_data = {
            'file': sample_text_file,
            'purpose': FilePurpose.OPERATION_INPUT,
        }

        upload_response = authenticated_client.post(upload_url, upload_data, format='multipart')
        assert upload_response.status_code == status.HTTP_201_CREATED
        file_id = upload_response.data['file']['id']

        # 2. Download
        download_url = f'/api/v2/files/download/{file_id}/'
        download_response = authenticated_client.get(download_url)
        assert download_response.status_code == status.HTTP_200_OK

        # 3. Delete
        delete_url = f'/api/v2/files/delete/{file_id}/'
        delete_response = authenticated_client.delete(delete_url)
        assert delete_response.status_code == status.HTTP_200_OK

        # 4. Verify file is gone
        download_response2 = authenticated_client.get(download_url)
        assert download_response2.status_code == status.HTTP_404_NOT_FOUND

    def test_upload_multiple_files_same_session(self, authenticated_client, mock_upload_root):
        """Test uploading multiple files in same session."""
        upload_url = '/api/v2/files/upload/'
        file_ids = []

        for i in range(3):
            test_file = SimpleUploadedFile(
                name=f"test_{i}.txt",
                content=f"Content {i}".encode(),
                content_type="text/plain"
            )

            upload_data = {
                'file': test_file,
                'purpose': FilePurpose.OPERATION_INPUT,
            }

            response = authenticated_client.post(upload_url, upload_data, format='multipart')
            assert response.status_code == status.HTTP_201_CREATED
            file_ids.append(response.data['file']['id'])

        # Verify all files exist
        assert len(file_ids) == 3
        assert UploadedFile.objects.filter(id__in=file_ids).count() == 3
