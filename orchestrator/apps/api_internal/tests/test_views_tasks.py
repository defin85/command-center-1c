"""Tests for task execution v2 endpoints (Internal API)."""
import uuid

from rest_framework import status

from apps.operations.models import BatchOperation

from ._internal_api_v2_base import InternalAPIV2BaseTestCase


class TaskEndpointsV2Tests(InternalAPIV2BaseTestCase):
    def _create_operation(self) -> BatchOperation:
        return BatchOperation.objects.create(
            id=str(uuid.uuid4()),
            name="Test operation",
            operation_type=BatchOperation.TYPE_QUERY,
            target_entity="TestEntity",
        )

    def test_start_task_success(self):
        operation = self._create_operation()
        response = self.client.post(
            "/api/v2/internal/start-task",
            {
                "operation_id": operation.id,
                "task_type": "health_check",
                "target_id": str(uuid.uuid4()),
                "target_type": "database",
                "worker_instance": "worker-1",
                "parameters": {"foo": "bar"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertIn("task_id", response.data)
        self.assertEqual(response.data["status"], "running")
        self.assertGreater(response.data["task_id"], 0)

    def test_start_task_with_operation_id(self):
        operation = self._create_operation()
        response = self.client.post(
            "/api/v2/internal/start-task",
            {
                "operation_id": operation.id,
                "task_type": "batch_operation",
                "target_id": str(uuid.uuid4()),
                "target_type": "database",
                "worker_instance": "worker-2",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_start_task_missing_required_fields(self):
        operation = self._create_operation()

        response = self.client.post(
            "/api/v2/internal/start-task",
            {
                "task_type": "health_check",
                "target_id": str(uuid.uuid4()),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            "/api/v2/internal/start-task",
            {
                "operation_id": operation.id,
                "target_id": str(uuid.uuid4()),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_start_task_unauthorized(self):
        operation = self._create_operation()
        client = self.get_unauthenticated_client()
        response = client.post(
            "/api/v2/internal/start-task",
            {
                "operation_id": operation.id,
                "task_type": "health_check",
                "target_id": str(uuid.uuid4()),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_complete_task_success(self):
        operation = self._create_operation()
        start_resp = self.client.post(
            "/api/v2/internal/start-task",
            {
                "operation_id": operation.id,
                "task_type": "health_check",
                "target_id": str(uuid.uuid4()),
                "worker_instance": "worker-1",
            },
            format="json",
        )
        self.assertEqual(start_resp.status_code, status.HTTP_201_CREATED)
        task_id = start_resp.data["task_id"]

        response = self.client.post(
            f"/api/v2/internal/complete-task?task_id={task_id}",
            {"status": "success", "duration_ms": 500},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["status"], "success")

    def test_complete_task_missing_task_id(self):
        response = self.client.post(
            "/api/v2/internal/complete-task",
            {"status": "success", "duration_ms": 500},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("task_id", response.data["error"])

    def test_complete_task_invalid_task_id(self):
        response = self.client.post(
            "/api/v2/internal/complete-task?task_id=invalid",
            {"status": "success", "duration_ms": 500},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_complete_task_with_error(self):
        operation = self._create_operation()
        start_resp = self.client.post(
            "/api/v2/internal/start-task",
            {
                "operation_id": operation.id,
                "task_type": "health_check",
                "target_id": str(uuid.uuid4()),
                "worker_instance": "worker-1",
            },
            format="json",
        )
        task_id = start_resp.data["task_id"]

        response = self.client.post(
            f"/api/v2/internal/complete-task?task_id={task_id}",
            {
                "status": "failed",
                "duration_ms": 100,
                "error_message": "Connection timeout",
                "error_code": "NetworkError",
                "retry_count": 3,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

