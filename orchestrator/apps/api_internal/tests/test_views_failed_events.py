"""Tests for failed events v2 endpoints (Internal API)."""
from rest_framework import status

from ._internal_api_v2_base import InternalAPIV2BaseTestCase


class FailedEventsEndpointsV2Tests(InternalAPIV2BaseTestCase):
    def test_list_pending_failed_events(self):
        response = self.client.get("/api/v2/internal/list-pending-failed-events")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIn("events", response.data)
        self.assertIn("count", response.data)
        self.assertIsInstance(response.data["events"], list)
        self.assertIsInstance(response.data["count"], int)

    def test_list_pending_failed_events_with_batch_size(self):
        response = self.client.get("/api/v2/internal/list-pending-failed-events?batch_size=50")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

    def test_list_pending_failed_events_invalid_batch_size(self):
        response = self.client.get(
            "/api/v2/internal/list-pending-failed-events?batch_size=invalid"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_pending_failed_events_unauthorized(self):
        client = self.get_unauthenticated_client()
        response = client.get("/api/v2/internal/list-pending-failed-events")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_mark_event_replayed_missing_id(self):
        response = self.client.post(
            "/api/v2/internal/mark-event-replayed",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("event_id", response.data["error"])

    def test_mark_event_replayed_invalid_id(self):
        response = self.client.post(
            "/api/v2/internal/mark-event-replayed?event_id=invalid",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mark_event_replayed_not_found(self):
        response = self.client.post(
            "/api/v2/internal/mark-event-replayed?event_id=99999",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_mark_event_replayed_unauthorized(self):
        client = self.get_unauthenticated_client()
        response = client.post(
            "/api/v2/internal/mark-event-replayed?event_id=1",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_mark_event_failed_missing_id(self):
        response = self.client.post(
            "/api/v2/internal/mark-event-failed",
            {"error_message": "Test error"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("event_id", response.data["error"])

    def test_mark_event_failed_invalid_id(self):
        response = self.client.post(
            "/api/v2/internal/mark-event-failed?event_id=invalid",
            {"error_message": "Test error"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mark_event_failed_missing_error_message(self):
        response = self.client.post(
            "/api/v2/internal/mark-event-failed?event_id=1",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_mark_event_failed_not_found(self):
        response = self.client.post(
            "/api/v2/internal/mark-event-failed?event_id=99999",
            {"error_message": "Test error"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_mark_event_failed_unauthorized(self):
        client = self.get_unauthenticated_client()
        response = client.post(
            "/api/v2/internal/mark-event-failed?event_id=1",
            {"error_message": "Test error"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cleanup_failed_events(self):
        response = self.client.post(
            "/api/v2/internal/cleanup-failed-events",
            {"retention_days": 7},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIn("deleted_count", response.data)
        self.assertIsInstance(response.data["deleted_count"], int)

    def test_cleanup_failed_events_default_retention(self):
        response = self.client.post(
            "/api/v2/internal/cleanup-failed-events",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

    def test_cleanup_failed_events_invalid_retention(self):
        response = self.client.post(
            "/api/v2/internal/cleanup-failed-events",
            {"retention_days": 0},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_cleanup_failed_events_unauthorized(self):
        client = self.get_unauthenticated_client()
        response = client.post(
            "/api/v2/internal/cleanup-failed-events",
            {"retention_days": 7},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

