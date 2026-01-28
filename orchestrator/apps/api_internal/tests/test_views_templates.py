"""Tests for template v2 endpoints (Internal API)."""
from rest_framework import status

from ._internal_api_v2_base import InternalAPIV2BaseTestCase


class TemplateEndpointsV2Tests(InternalAPIV2BaseTestCase):
    def test_get_template_missing_id(self):
        response = self.client.get("/api/v2/internal/get-template")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("template_id", response.data["error"])

    def test_get_template_not_found(self):
        response = self.client.get("/api/v2/internal/get-template?template_id=nonexistent")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_get_template_unauthorized(self):
        client = self.get_unauthenticated_client()
        response = client.get("/api/v2/internal/get-template?template_id=test")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_render_template_missing_id(self):
        response = self.client.post(
            "/api/v2/internal/render-template",
            {"context": {}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("template_id", response.data["error"])

    def test_render_template_not_found(self):
        response = self.client.post(
            "/api/v2/internal/render-template?template_id=nonexistent",
            {"context": {}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_render_template_missing_context(self):
        response = self.client.post(
            "/api/v2/internal/render-template?template_id=test",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_render_template_unauthorized(self):
        client = self.get_unauthenticated_client()
        response = client.post(
            "/api/v2/internal/render-template?template_id=test",
            {"context": {}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

