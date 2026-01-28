"""Tests for cluster v2 endpoints (Internal API)."""
import uuid

from rest_framework import status

from ._internal_api_v2_base import InternalAPIV2BaseTestCase


class ClusterEndpointsV2Tests(InternalAPIV2BaseTestCase):
    def test_update_cluster_health_missing_id(self):
        response = self.client.post(
            "/api/v2/internal/update-cluster-health",
            {"healthy": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("cluster_id", response.data["error"])

    def test_update_cluster_health_not_found(self):
        response = self.client.post(
            f"/api/v2/internal/update-cluster-health?cluster_id={uuid.uuid4()}",
            {"healthy": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_update_cluster_health_missing_healthy_field(self):
        response = self.client.post(
            f"/api/v2/internal/update-cluster-health?cluster_id={uuid.uuid4()}",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_update_cluster_health_unauthorized(self):
        client = self.get_unauthenticated_client()
        response = client.post(
            f"/api/v2/internal/update-cluster-health?cluster_id={uuid.uuid4()}",
            {"healthy": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

