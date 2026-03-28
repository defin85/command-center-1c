"""Tests for authentication across Internal API v2 endpoints."""
from rest_framework import status
from rest_framework.test import APIClient

from ._internal_api_v2_base import InternalAPIV2BaseTestCase


class AuthenticationTests(InternalAPIV2BaseTestCase):
    def test_all_endpoints_require_auth(self):
        client = self.get_unauthenticated_client()

        endpoints = [
            ("post", "/api/v2/internal/start-scheduler-run"),
            ("post", "/api/v2/internal/complete-scheduler-run?run_id=1"),
            ("post", "/api/v2/internal/start-task"),
            ("post", "/api/v2/internal/complete-task?task_id=1"),
            ("get", "/api/v2/internal/list-databases-for-health-check"),
            (
                "post",
                "/api/v2/internal/update-database-health?database_id=00000000-0000-0000-0000-000000000000",
            ),
            (
                "post",
                "/api/v2/internal/update-cluster-health?cluster_id=00000000-0000-0000-0000-000000000000",
            ),
            ("get", "/api/v2/internal/list-pending-failed-events"),
            ("post", "/api/v2/internal/mark-event-replayed?event_id=1"),
            ("post", "/api/v2/internal/mark-event-failed?event_id=1"),
            ("post", "/api/v2/internal/cleanup-failed-events"),
            ("get", "/api/v2/internal/get-template?template_id=test"),
            ("post", "/api/v2/internal/render-template?template_id=test"),
            ("post", "/api/v2/internal/pools/factual/trigger-active-sync-window"),
            ("post", "/api/v2/internal/pools/factual/trigger-closed-quarter-reconcile-window"),
        ]

        for method, url in endpoints:
            with self.subTest(url=url):
                if method == "get":
                    response = client.get(url)
                else:
                    response = client.post(url, {}, format="json")
                self.assertEqual(
                    response.status_code,
                    status.HTTP_401_UNAUTHORIZED,
                    f"Expected 401 for {url}, got {response.status_code}",
                )

    def test_wrong_token_rejected(self):
        client = APIClient()
        client.credentials(HTTP_X_INTERNAL_TOKEN="wrong-token")

        response = client.get("/api/v2/internal/list-databases-for-health-check")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_token_header_rejected(self):
        client = APIClient()
        response = client.get("/api/v2/internal/list-databases-for-health-check")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
