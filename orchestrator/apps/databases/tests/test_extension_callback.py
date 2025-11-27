"""
Tests for extension installation callback endpoint.
Tests the /api/v1/extensions/installation/callback/ endpoint behavior.
"""

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
import json
import uuid

from apps.databases.models import Database, ExtensionInstallation


class ExtensionInstallationCallbackTestCase(TestCase):
    """Test cases for extension installation callback endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.callback_url = '/api/v1/extensions/installation/callback/'

        # Create a test database
        self.database = Database.objects.create(
            id=uuid.uuid4(),
            name='Test Database',
            host='localhost',
            port=1541,
            username='admin',
            password='password',
            status='active'
        )

        # Create a pending extension installation
        self.installation = ExtensionInstallation.objects.create(
            database=self.database,
            extension_name='TestExtension',
            status='pending',
            metadata={
                'extension_path': '/path/to/test.cfe'
            }
        )

    def test_callback_success(self):
        """Test successful callback with completion status."""
        payload = {
            'database_id': str(self.database.id),
            'extension_name': 'TestExtension',
            'status': 'completed',
            'duration_seconds': 45.5,
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200

        # Verify installation status was updated
        self.installation.refresh_from_db()
        assert self.installation.status == 'completed'
        assert self.installation.duration_seconds == 45
        assert self.installation.completed_at is not None

    def test_callback_failure(self):
        """Test callback with failure status."""
        payload = {
            'database_id': str(self.database.id),
            'extension_name': 'TestExtension',
            'status': 'failed',
            'error_message': 'Extension not found in repository',
            'duration_seconds': 10.2,
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200

        # Verify installation was marked as failed
        self.installation.refresh_from_db()
        assert self.installation.status == 'failed'
        assert self.installation.error_message == 'Extension not found in repository'
        assert self.installation.duration_seconds == 10

    def test_callback_missing_database_id(self):
        """Test callback with missing database_id."""
        payload = {
            'extension_name': 'TestExtension',
            'status': 'completed',
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 400
        assert 'database_id' in response.data['error'].lower() or 'required' in response.data['error'].lower()

    def test_callback_missing_extension_name(self):
        """Test callback with missing extension_name."""
        payload = {
            'database_id': str(self.database.id),
            'status': 'completed',
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_callback_missing_status(self):
        """Test callback with missing status."""
        payload = {
            'database_id': str(self.database.id),
            'extension_name': 'TestExtension',
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_callback_invalid_status(self):
        """Test callback with invalid status value."""
        payload = {
            'database_id': str(self.database.id),
            'extension_name': 'TestExtension',
            'status': 'invalid_status',
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 400
        assert 'completed' in response.data['error'] or 'failed' in response.data['error']

    def test_callback_nonexistent_database(self):
        """Test callback for non-existent database."""
        fake_db_id = str(uuid.uuid4())
        payload = {
            'database_id': fake_db_id,
            'extension_name': 'TestExtension',
            'status': 'completed',
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 404

    def test_callback_nonexistent_installation(self):
        """Test callback for installation that doesn't exist."""
        payload = {
            'database_id': str(self.database.id),
            'extension_name': 'NonExistentExtension',
            'status': 'completed',
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 404

    def test_callback_completed_installation_ignored(self):
        """Test that callback for already completed installation is ignored."""
        # Mark installation as completed
        self.installation.status = 'completed'
        self.installation.completed_at = timezone.now()
        self.installation.duration_seconds = 30
        self.installation.save()

        payload = {
            'database_id': str(self.database.id),
            'extension_name': 'TestExtension',
            'status': 'failed',  # Try to change to failed
            'error_message': 'Should be ignored',
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        # Should return 404 because status is not in ['pending', 'in_progress']
        assert response.status_code == 404

        # Verify status wasn't changed
        self.installation.refresh_from_db()
        assert self.installation.status == 'completed'
        # error_message should not be updated (can be empty or None)
        assert not self.installation.error_message or self.installation.error_message == ''

    def test_callback_with_all_fields(self):
        """Test callback with all optional fields."""
        payload = {
            'database_id': str(self.database.id),
            'extension_name': 'TestExtension',
            'status': 'completed',
            'duration_seconds': 123.45,
            'error_message': '',  # Empty even for success
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200

        self.installation.refresh_from_db()
        assert self.installation.status == 'completed'
        assert self.installation.duration_seconds == 123

    def test_callback_duration_seconds_conversion(self):
        """Test that duration_seconds is properly converted to integer."""
        payload = {
            'database_id': str(self.database.id),
            'extension_name': 'TestExtension',
            'status': 'completed',
            'duration_seconds': 45.987,
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200

        self.installation.refresh_from_db()
        # Should be truncated to integer
        assert self.installation.duration_seconds == 45

    def test_callback_zero_duration(self):
        """Test callback with zero duration."""
        payload = {
            'database_id': str(self.database.id),
            'extension_name': 'TestExtension',
            'status': 'completed',
            'duration_seconds': 0,
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200

        self.installation.refresh_from_db()
        assert self.installation.duration_seconds == 0

    def test_callback_very_long_duration(self):
        """Test callback with very long operation duration."""
        payload = {
            'database_id': str(self.database.id),
            'extension_name': 'TestExtension',
            'status': 'completed',
            'duration_seconds': 999999.99,
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200

        self.installation.refresh_from_db()
        assert self.installation.duration_seconds == 999999

    def test_callback_special_characters_in_extension_name(self):
        """Test callback with special characters in extension name."""
        # Create installation with special characters
        special_ext = ExtensionInstallation.objects.create(
            database=self.database,
            extension_name='Тестовое_Расширение-v2.0',
            status='pending',
        )

        payload = {
            'database_id': str(self.database.id),
            'extension_name': 'Тестовое_Расширение-v2.0',
            'status': 'completed',
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200

        special_ext.refresh_from_db()
        assert special_ext.status == 'completed'

    def test_callback_long_error_message(self):
        """Test callback with very long error message."""
        long_error = 'Error: ' + 'A' * 1000
        payload = {
            'database_id': str(self.database.id),
            'extension_name': 'TestExtension',
            'status': 'failed',
            'error_message': long_error,
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200

        self.installation.refresh_from_db()
        assert long_error in self.installation.error_message

    def test_callback_json_parsing_error(self):
        """Test callback with invalid JSON."""
        response = self.client.post(
            self.callback_url,
            data='invalid json {',
            content_type='application/json'
        )

        # Should return 400 due to JSON parsing error
        assert response.status_code == 400

    def test_callback_empty_payload(self):
        """Test callback with empty JSON object."""
        payload = {}

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_callback_no_authentication_required(self):
        """Test that callback endpoint doesn't require authentication."""
        # The endpoint should be accessible without any auth headers
        payload = {
            'database_id': str(self.database.id),
            'extension_name': 'TestExtension',
            'status': 'completed',
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        # Should work without auth
        assert response.status_code == 200

    def test_callback_multiple_installations_same_db(self):
        """Test callback when database has multiple extension installations."""
        ext2 = ExtensionInstallation.objects.create(
            database=self.database,
            extension_name='OtherExtension',
            status='pending',
        )

        payload = {
            'database_id': str(self.database.id),
            'extension_name': 'TestExtension',
            'status': 'completed',
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200

        # Only TestExtension should be updated
        self.installation.refresh_from_db()
        assert self.installation.status == 'completed'

        # OtherExtension should remain pending
        ext2.refresh_from_db()
        assert ext2.status == 'pending'

    def test_callback_in_progress_installation(self):
        """Test callback for installation marked as in_progress."""
        self.installation.status = 'in_progress'
        self.installation.save()

        payload = {
            'database_id': str(self.database.id),
            'extension_name': 'TestExtension',
            'status': 'completed',
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200

        self.installation.refresh_from_db()
        assert self.installation.status == 'completed'

    def test_callback_updates_completed_at_timestamp(self):
        """Test that completed_at is set properly."""
        before_call = timezone.now()

        payload = {
            'database_id': str(self.database.id),
            'extension_name': 'TestExtension',
            'status': 'completed',
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        after_call = timezone.now()

        assert response.status_code == 200

        self.installation.refresh_from_db()
        assert self.installation.completed_at is not None
        assert before_call <= self.installation.completed_at <= after_call

    def test_callback_uuid_format_validation(self):
        """Test callback with invalid UUID format."""
        payload = {
            'database_id': 'not-a-uuid',
            'extension_name': 'TestExtension',
            'status': 'completed',
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        # Should fail because database won't be found
        assert response.status_code == 404

    def test_callback_response_format(self):
        """Test that callback response has expected format."""
        payload = {
            'database_id': str(self.database.id),
            'extension_name': 'TestExtension',
            'status': 'completed',
        }

        response = self.client.post(
            self.callback_url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        # Response should be JSON
        data = response.json()
        assert isinstance(data, dict)
