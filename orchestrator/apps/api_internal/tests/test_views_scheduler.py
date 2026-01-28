"""Tests for scheduler v2 endpoints (Internal API)."""
from rest_framework import status

from ._internal_api_v2_base import InternalAPIV2BaseTestCase


class SchedulerEndpointsV2Tests(InternalAPIV2BaseTestCase):
    def test_start_scheduler_run_success(self):
        response = self.client.post(
            "/api/v2/internal/start-scheduler-run",
            {"job_name": "health_check", "worker_instance": "worker-1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertIn("run_id", response.data)
        self.assertEqual(response.data["status"], "running")
        self.assertGreater(response.data["run_id"], 0)

    def test_start_scheduler_run_unauthorized(self):
        client = self.get_unauthenticated_client()
        response = client.post(
            "/api/v2/internal/start-scheduler-run",
            {"job_name": "health_check", "worker_instance": "worker-1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_start_scheduler_run_missing_job_name(self):
        response = self.client.post(
            "/api/v2/internal/start-scheduler-run",
            {"worker_instance": "worker-1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("job_name", response.data["error"])

    def test_start_scheduler_run_missing_worker_instance(self):
        response = self.client.post(
            "/api/v2/internal/start-scheduler-run",
            {"job_name": "health_check"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("worker_instance", response.data["error"])

    def test_complete_scheduler_run_success(self):
        start_resp = self.client.post(
            "/api/v2/internal/start-scheduler-run",
            {"job_name": "health_check", "worker_instance": "worker-1"},
            format="json",
        )
        self.assertEqual(start_resp.status_code, status.HTTP_201_CREATED)
        run_id = start_resp.data["run_id"]

        response = self.client.post(
            f"/api/v2/internal/complete-scheduler-run?run_id={run_id}",
            {"status": "success", "duration_ms": 1000},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["status"], "success")

    def test_complete_scheduler_run_missing_run_id(self):
        response = self.client.post(
            "/api/v2/internal/complete-scheduler-run",
            {"status": "success", "duration_ms": 1000},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("run_id", response.data["error"])

    def test_complete_scheduler_run_invalid_run_id(self):
        response = self.client.post(
            "/api/v2/internal/complete-scheduler-run?run_id=invalid",
            {"status": "success", "duration_ms": 1000},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_complete_scheduler_run_missing_status(self):
        response = self.client.post(
            "/api/v2/internal/complete-scheduler-run?run_id=1",
            {"duration_ms": 1000},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_complete_scheduler_run_missing_duration(self):
        start_resp = self.client.post(
            "/api/v2/internal/start-scheduler-run",
            {"job_name": "health_check", "worker_instance": "worker-1"},
            format="json",
        )
        run_id = start_resp.data["run_id"]

        response = self.client.post(
            f"/api/v2/internal/complete-scheduler-run?run_id={run_id}",
            {"status": "success"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

    def test_complete_scheduler_run_invalid_status(self):
        response = self.client.post(
            "/api/v2/internal/complete-scheduler-run?run_id=1",
            {"status": "invalid", "duration_ms": 1000},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

