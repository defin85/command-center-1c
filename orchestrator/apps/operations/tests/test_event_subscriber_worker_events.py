"""Unit tests for worker event handlers (EventSubscriber)."""

import uuid
from unittest.mock import patch

from apps.databases.models import Database
from apps.operations.event_subscriber import EventSubscriber
from apps.operations.models import BatchOperation, Task

from ._event_subscriber_test_base import EventSubscriberBaseTestCase


class EventSubscriberWorkerEventsTest(EventSubscriberBaseTestCase):
    def setUp(self):
        self.database = Database.objects.create(
            id="db-123",
            name="Test Database",
            host="localhost",
            port=80,
            odata_url="http://localhost/odata",
            username="admin",
            password="password",
        )

    @patch("apps.operations.event_subscriber.runtime.operations_redis_client")
    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_handle_worker_completed_updates_restrictions(self, mock_redis_class, mock_ops_redis):
        subscriber = EventSubscriber()

        block_op = BatchOperation.objects.create(
            id=str(uuid.uuid4()),
            name="Block Sessions",
            operation_type=BatchOperation.TYPE_BLOCK_SESSIONS,
            target_entity="Infobase",
            status=BatchOperation.STATUS_PROCESSING,
            payload={
                "data": {
                    "message": "Maintenance",
                    "permission_code": "ALLOW",
                    "denied_from": "2025-01-01T00:00:00Z",
                    "denied_to": "2025-01-02T00:00:00Z",
                    "parameter": "param",
                }
            },
        )

        subscriber.handle_worker_completed(
            {
                "operation_id": block_op.id,
                "results": [{"database_id": self.database.id, "success": True}],
                "summary": {},
            },
            "corr-123",
        )

        self.database.refresh_from_db()
        self.assertTrue(self.database.metadata["sessions_deny"])
        self.assertEqual(self.database.metadata["denied_message"], "Maintenance")
        self.assertEqual(self.database.metadata["permission_code"], "ALLOW")
        self.assertEqual(self.database.metadata["denied_from"], "2025-01-01T00:00:00Z")
        self.assertEqual(self.database.metadata["denied_to"], "2025-01-02T00:00:00Z")
        self.assertEqual(self.database.metadata["denied_parameter"], "param")

        unblock_op = BatchOperation.objects.create(
            id=str(uuid.uuid4()),
            name="Unblock Sessions",
            operation_type=BatchOperation.TYPE_UNBLOCK_SESSIONS,
            target_entity="Infobase",
            status=BatchOperation.STATUS_PROCESSING,
        )

        subscriber.handle_worker_completed(
            {
                "operation_id": unblock_op.id,
                "results": [{"database_id": self.database.id, "success": True}],
                "summary": {},
            },
            "corr-456",
        )

        self.database.refresh_from_db()
        self.assertFalse(self.database.metadata["sessions_deny"])
        self.assertNotIn("denied_message", self.database.metadata)
        self.assertNotIn("permission_code", self.database.metadata)
        self.assertNotIn("denied_from", self.database.metadata)
        self.assertNotIn("denied_to", self.database.metadata)
        self.assertNotIn("denied_parameter", self.database.metadata)

    @patch("apps.operations.event_subscriber.runtime.operations_redis_client")
    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_handle_worker_completed_updates_global_task(self, mock_redis_class, mock_ops_redis):
        subscriber = EventSubscriber()

        global_op = BatchOperation.objects.create(
            id=str(uuid.uuid4()),
            name="Global Operation",
            operation_type=BatchOperation.TYPE_DESIGNER_CLI,
            target_entity="Infobase",
            status=BatchOperation.STATUS_PROCESSING,
            metadata={"target_scope": "global", "target_ref": "deadbeef"},
        )
        global_task = Task.objects.create(
            id="task-global",
            batch_operation=global_op,
            database=None,
            status=Task.STATUS_PROCESSING,
        )

        subscriber.handle_worker_completed(
            {
                "operation_id": global_op.id,
                "status": "completed",
                "results": [{"database_id": "", "success": True, "data": {"ok": True}}],
                "summary": {"total": 1, "succeeded": 1, "failed": 0},
            },
            "corr-789",
        )

        global_task.refresh_from_db()
        self.assertEqual(global_task.status, Task.STATUS_COMPLETED)
        self.assertEqual(global_task.result, {"ok": True})
        self.assertEqual(global_task.error_message, "")
        self.assertEqual(global_task.error_code, "")
        mock_ops_redis.release_global_target_lock.assert_called_with("deadbeef")

    @patch("apps.operations.event_subscriber.runtime.operations_redis_client")
    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_handle_worker_completed_failed_task_preserves_result_data(
        self, mock_redis_class, mock_ops_redis
    ):
        subscriber = EventSubscriber()

        op = BatchOperation.objects.create(
            id=str(uuid.uuid4()),
            name="IBCMD Failed",
            operation_type=BatchOperation.TYPE_IBCMD_CLI,
            target_entity="Infobase",
            status=BatchOperation.STATUS_PROCESSING,
        )
        task = Task.objects.create(
            id="task-1",
            batch_operation=op,
            database=self.database,
            status=Task.STATUS_PROCESSING,
        )

        subscriber.handle_worker_completed(
            {
                "operation_id": op.id,
                "status": "failed",
                "results": [
                    {
                        "database_id": str(self.database.id),
                        "success": False,
                        "error": "exit status 2",
                        "error_code": "IBCMD_ERROR",
                        "data": {
                            "exit_code": 2,
                            "stderr": "boom",
                            "runtime_bindings": [
                                {
                                    "target_ref": "infobase_auth",
                                    "source_ref": "credentials.ib_user_mapping",
                                    "resolve_at": "worker",
                                    "sensitive": True,
                                    "status": "skipped",
                                    "reason": "unsupported_for_command",
                                },
                            ],
                        },
                    }
                ],
                "summary": {"total": 1, "succeeded": 0, "failed": 1},
            },
            "corr-999",
        )

        task.refresh_from_db()
        self.assertEqual(task.status, Task.STATUS_FAILED)
        self.assertEqual(task.error_message, "exit status 2")
        self.assertEqual(task.error_code, "IBCMD_ERROR")
        self.assertEqual(
            task.result,
            {
                "exit_code": 2,
                "stderr": "boom",
                "runtime_bindings": [
                    {
                        "target_ref": "infobase_auth",
                        "source_ref": "credentials.ib_user_mapping",
                        "resolve_at": "worker",
                        "sensitive": True,
                        "status": "skipped",
                        "reason": "unsupported_for_command",
                    },
                ],
            },
        )

    @patch("apps.operations.event_subscriber.runtime.operations_redis_client")
    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_handle_worker_failed_updates_global_task(self, mock_redis_class, mock_ops_redis):
        subscriber = EventSubscriber()

        global_op = BatchOperation.objects.create(
            id=str(uuid.uuid4()),
            name="Global Operation Failed",
            operation_type=BatchOperation.TYPE_DESIGNER_CLI,
            target_entity="Infobase",
            status=BatchOperation.STATUS_PROCESSING,
            metadata={"target_scope": "global", "target_ref": "deadbeef"},
        )
        global_task = Task.objects.create(
            id="task-global-fail",
            batch_operation=global_op,
            database=None,
            status=Task.STATUS_PROCESSING,
        )

        subscriber.handle_worker_failed(
            {
                "operation_id": global_op.id,
                "error": "boom",
            },
            "corr-790",
        )

        global_task.refresh_from_db()
        self.assertEqual(global_task.status, Task.STATUS_FAILED)
        self.assertEqual(global_task.error_message, "boom")
        self.assertEqual(global_task.error_code, "WORKER_FAILED")
        mock_ops_redis.release_global_target_lock.assert_called_with("deadbeef")

    @patch("apps.operations.event_subscriber.runtime.operations_redis_client")
    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_handle_worker_completed_releases_sync_cluster_idempotency_lock(
        self, mock_redis_class, mock_ops_redis
    ):
        subscriber = EventSubscriber()

        cluster_id = str(uuid.uuid4())
        op = BatchOperation.objects.create(
            id=str(uuid.uuid4()),
            name="Sync cluster",
            operation_type=BatchOperation.TYPE_SYNC_CLUSTER,
            target_entity="Cluster",
            status=BatchOperation.STATUS_PROCESSING,
            payload={"cluster_id": cluster_id},
        )

        subscriber.handle_worker_completed(
            {
                "operation_id": op.id,
                "status": "failed",
                "results": [],
                "summary": {"total": 1, "succeeded": 0, "failed": 1},
            },
            "corr-sync-1",
        )

        mock_ops_redis.release_lock.assert_any_call(f"sync_cluster:{cluster_id}")

    @patch("apps.operations.event_subscriber.runtime.operations_redis_client")
    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_handle_worker_completed_releases_discover_clusters_idempotency_lock(
        self, mock_redis_class, mock_ops_redis
    ):
        subscriber = EventSubscriber()

        ras_server = "127.0.0.1:1545"
        op = BatchOperation.objects.create(
            id=str(uuid.uuid4()),
            name="Discover clusters",
            operation_type=BatchOperation.TYPE_DISCOVER_CLUSTERS,
            target_entity="Cluster",
            status=BatchOperation.STATUS_PROCESSING,
            payload={"ras_server": ras_server},
        )

        subscriber.handle_worker_completed(
            {
                "operation_id": op.id,
                "status": "failed",
                "results": [],
                "summary": {"total": 1, "succeeded": 0, "failed": 1},
            },
            "corr-discover-1",
        )

        mock_ops_redis.release_lock.assert_any_call(f"discover_clusters:{ras_server}")

