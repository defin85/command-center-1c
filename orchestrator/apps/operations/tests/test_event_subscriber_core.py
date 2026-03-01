"""
Unit tests for EventSubscriber (core loop, routing, correlation parsing).
"""

import json
from unittest.mock import MagicMock, Mock, patch

from apps.databases.models import Database
from apps.operations.event_subscriber import EventSubscriber
from apps.operations.models import BatchOperation, Task

from ._event_subscriber_test_base import EventSubscriberBaseTestCase


class EventSubscriberTest(EventSubscriberBaseTestCase):
    """Core tests for EventSubscriber class."""

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

        self.batch_op = BatchOperation.objects.create(
            id="batch-123",
            name="Test Batch",
            operation_type=BatchOperation.TYPE_DESIGNER_CLI,
            target_entity="Extension",
            status=BatchOperation.STATUS_PROCESSING,
        )

        self.task = Task.objects.create(
            id="task-456",
            batch_operation=self.batch_op,
            database=self.database,
            status=Task.STATUS_PROCESSING,
        )

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_init(self, mock_redis_class):
        subscriber = EventSubscriber()
        mock_redis_class.assert_called_once()

        self.assertEqual(subscriber.consumer_group, "orchestrator-group")
        self.assertTrue(subscriber.consumer_name.startswith("orchestrator-"))

        self.assertIn("events:worker:cluster-synced", subscriber.streams)
        self.assertIn("events:worker:completed", subscriber.streams)

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_setup_consumer_groups_creates_groups(self, mock_redis_class):
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()
        subscriber.setup_consumer_groups()

        self.assertEqual(mock_redis.xgroup_create.call_count, len(subscriber.streams))

        first_stream = list(subscriber.streams.keys())[0]
        expected_first_id = "0" if first_stream.startswith("events:") else "$"
        mock_redis.xgroup_create.assert_any_call(
            first_stream,
            "orchestrator-group",
            id=expected_first_id,
            mkstream=True,
        )

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_setup_consumer_groups_handles_existing_group(self, mock_redis_class):
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        import redis as redis_module

        mock_redis.xgroup_create.side_effect = redis_module.ResponseError(
            "BUSYGROUP Consumer Group name already exists"
        )

        subscriber = EventSubscriber()
        try:
            subscriber.setup_consumer_groups()
        except Exception as e:
            self.fail(f"setup_consumer_groups raised exception: {e}")

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_ensure_consumer_registered_bootstraps_consumer(self, mock_redis_class):
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        mock_redis.xadd.return_value = "1700000000000-0"
        mock_redis.xreadgroup.return_value = [
            (
                "commands:orchestrator:get-cluster-info",
                [("1700000000000-0", {"__cc1c_bootstrap__": "1"})],
            )
        ]

        subscriber = EventSubscriber()
        subscriber.ensure_consumer_registered()

        mock_redis.xadd.assert_called_once()
        mock_redis.xreadgroup.assert_called_once_with(
            "orchestrator-group",
            subscriber.consumer_name,
            {"commands:orchestrator:get-cluster-info": ">"},
            count=1,
            block=100,
            noack=True,
        )
        mock_redis.xdel.assert_called_once_with(
            "commands:orchestrator:get-cluster-info",
            "1700000000000-0",
        )

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_ensure_consumer_registered_handles_redis_errors(self, mock_redis_class):
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        mock_redis.xadd.side_effect = RuntimeError("redis down")

        subscriber = EventSubscriber()
        try:
            subscriber.ensure_consumer_registered()
        except Exception as e:
            self.fail(f"ensure_consumer_registered raised exception: {e}")

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_process_message_routes_to_handler(self, mock_redis_class):
        subscriber = EventSubscriber()

        subscriber.handle_cluster_synced = Mock()
        subscriber.handle_worker_completed = Mock()

        data = {
            "event_type": "cluster.synced",
            "correlation_id": "corr-123",
            "timestamp": "2025-11-12T10:30:00Z",
            "payload": json.dumps({"infobase_id": "infobase-123"}),
        }

        subscriber.process_message("events:worker:cluster-synced", "1234567890-0", data)
        subscriber.handle_cluster_synced.assert_called_once()

        subscriber.process_message("events:worker:completed", "1234567891-0", data)
        subscriber.handle_worker_completed.assert_called_once()

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_process_message_parses_json_payload(self, mock_redis_class):
        subscriber = EventSubscriber()
        subscriber.handle_cluster_synced = Mock()

        payload_dict = {
            "cluster_id": "cluster-uuid",
            "infobase_id": "infobase-uuid",
            "reason": "maintenance",
        }
        data = {
            "event_type": "cluster.synced",
            "correlation_id": "corr-123",
            "payload": json.dumps(payload_dict),
        }

        subscriber.process_message("events:worker:cluster-synced", "1234567890-0", data)
        call_args = subscriber.handle_cluster_synced.call_args
        self.assertEqual(call_args[0][0], payload_dict)

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_update_task_status_parses_correlation_id(self, mock_redis_class):
        subscriber = EventSubscriber()

        correlation_id = f"batch-{self.batch_op.id}-{self.task.id}"
        result = {"test": "data"}

        subscriber._update_task_status_from_correlation_id(
            correlation_id=correlation_id,
            status=Task.STATUS_COMPLETED,
            result=result,
        )

        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.STATUS_COMPLETED)
        self.assertEqual(self.task.result, result)

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_update_task_status_handles_invalid_correlation_id(self, mock_redis_class):
        subscriber = EventSubscriber()
        try:
            subscriber._update_task_status_from_correlation_id(
                correlation_id="invalid-format",
                status=Task.STATUS_COMPLETED,
            )
        except Exception as e:
            self.fail(f"_update_task_status_from_correlation_id raised exception: {e}")

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_update_task_status_handles_nonexistent_task(self, mock_redis_class):
        subscriber = EventSubscriber()
        try:
            subscriber._update_task_status_from_correlation_id(
                correlation_id="batch-123-nonexistent-task-id",
                status=Task.STATUS_COMPLETED,
            )
        except Exception as e:
            self.fail(f"_update_task_status_from_correlation_id raised exception: {e}")

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_handle_infobase_locked(self, mock_redis_class):
        subscriber = EventSubscriber()
        payload = {
            "cluster_id": "cluster-uuid",
            "infobase_id": "infobase-uuid",
            "reason": "maintenance",
        }
        try:
            subscriber.handle_infobase_locked(payload, "corr-123")
        except Exception as e:
            self.fail(f"handle_infobase_locked raised exception: {e}")

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_handle_sessions_closed(self, mock_redis_class):
        subscriber = EventSubscriber()
        payload = {
            "cluster_id": "cluster-uuid",
            "infobase_id": "infobase-uuid",
            "sessions_closed": 5,
            "duration_seconds": 2.3,
        }
        try:
            subscriber.handle_sessions_closed(payload, "corr-123")
        except Exception as e:
            self.fail(f"handle_sessions_closed raised exception: {e}")

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    @patch("apps.operations.event_subscriber.subscriber.time.sleep")
    def test_run_forever_handles_connection_error(self, mock_sleep, mock_redis_class):
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        mock_redis.xgroup_create.return_value = True

        import redis as redis_module

        call_count = [0]

        def xreadgroup_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise redis_module.ConnectionError("Connection lost")
            return []

        mock_redis.xreadgroup.side_effect = xreadgroup_side_effect

        subscriber = EventSubscriber()
        subscriber.ensure_consumer_registered = Mock()

        def stop_after_sleep(*args, **kwargs):
            subscriber.running = False

        mock_sleep.side_effect = stop_after_sleep

        try:
            subscriber.run_forever()
        except Exception as e:
            self.fail(f"run_forever raised exception: {e}")

        mock_sleep.assert_called_with(5)

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_process_message_handles_invalid_json(self, mock_redis_class):
        subscriber = EventSubscriber()

        data = {
            "event_type": "cluster.synced",
            "correlation_id": "corr-123",
            "payload": "invalid-json{",
        }
        try:
            subscriber.process_message("events:worker:cluster-synced", "1234567890-0", data)
        except Exception as e:
            self.fail(f"process_message raised exception: {e}")
