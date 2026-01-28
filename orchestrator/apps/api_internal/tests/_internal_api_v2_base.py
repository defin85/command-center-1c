"""
Shared helpers for Internal API v2 endpoint tests.

All endpoints require X-Internal-Token authentication.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


@override_settings(INTERNAL_API_TOKEN="test-internal-token")
class InternalAPIV2BaseTestCase(TestCase):
    """Base test case with authenticated client."""

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_X_INTERNAL_TOKEN="test-internal-token")

    def get_unauthenticated_client(self):
        """Return client without auth headers."""
        return APIClient()

