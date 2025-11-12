"""
Unit tests for Event Subscriber.

Tests Redis Streams integration, event processing, and Task status updates.
"""

from unittest.mock import Mock, patch, MagicMock, call
from django.test import TestCase, override_settings
from django.utils import timezone
import json

from apps.operations.event_subscriber import EventSubscriber
from apps.operations.models import BatchOperation, Task
from apps.databases.models import Database


@override_settings(
    REDIS_HOST='localhost',
    REDIS_PORT=6379,
)
class EventSubscriberTest(TestCase):
    """Test suite for EventSubscriber class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create test Database (required for Task foreign key)
        self.database = Database.objects.create(
            id='db-123',
            name='Test Database',
            host='localhost',
            port=80,
            odata_url='http://localhost/odata',
            username='admin',
            password='password',  # Will be encrypted
        )

        # Create test BatchOperation
        self.batch_op = BatchOperation.objects.create(
            id='batch-123',
            name='Test Batch',
            operation_type=BatchOperation.TYPE_INSTALL_EXTENSION,
            target_entity='Extension',
            status=BatchOperation.STATUS_PROCESSING,
        )

        # Create test Task
        self.task = Task.objects.create(
            id='task-456',
            batch_operation=self.batch_op,
            database=self.database,
            status=Task.STATUS_PROCESSING,
        )

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_init(self, mock_redis_class):
        """Test EventSubscriber initialization."""
        subscriber = EventSubscriber()

        # Should create Redis client
        mock_redis_class.assert_called_once()

        # Should set consumer group and name
        self.assertEqual(subscriber.consumer_group, 'orchestrator-group')
        self.assertTrue(subscriber.consumer_name.startswith('orchestrator-'))

        # Should subscribe to expected streams
        self.assertIn('events:batch-service:extension:installed', subscriber.streams)
        self.assertIn('events:batch-service:extension:install-failed', subscriber.streams)
        self.assertIn('events:cluster-service:infobase:locked', subscriber.streams)

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_setup_consumer_groups_creates_groups(self, mock_redis_class):
        """Test consumer group creation."""
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()
        subscriber.setup_consumer_groups()

        # Should call xgroup_create for each stream
        self.assertEqual(
            mock_redis.xgroup_create.call_count,
            len(subscriber.streams)
        )

        # Verify call arguments for first stream
        first_stream = list(subscriber.streams.keys())[0]
        mock_redis.xgroup_create.assert_any_call(
            first_stream,
            'orchestrator-group',
            id='$',
            mkstream=True
        )

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_setup_consumer_groups_handles_existing_group(self, mock_redis_class):
        """Test handling of already existing consumer groups."""
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        # Simulate BUSYGROUP error (group already exists)
        import redis as redis_module
        mock_redis.xgroup_create.side_effect = redis_module.ResponseError("BUSYGROUP Consumer Group name already exists")

        subscriber = EventSubscriber()

        # Should not raise exception
        try:
            subscriber.setup_consumer_groups()
        except Exception as e:
            self.fail(f"setup_consumer_groups raised exception: {e}")

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_process_message_routes_to_handler(self, mock_redis_class):
        """Test message routing to appropriate handler."""
        subscriber = EventSubscriber()

        # Mock handlers
        subscriber.handle_extension_installed = Mock()
        subscriber.handle_extension_failed = Mock()
        subscriber.handle_infobase_locked = Mock()

        # Test extension:installed routing
        data = {
            'event_type': 'extension.installed',
            'correlation_id': 'corr-123',
            'timestamp': '2025-11-12T10:30:00Z',
            'payload': json.dumps({'database_id': 'db-123'})
        }

        subscriber.process_message(
            'events:batch-service:extension:installed',
            '1234567890-0',
            data
        )

        subscriber.handle_extension_installed.assert_called_once()

        # Test extension:install-failed routing
        subscriber.handle_extension_failed.reset_mock()
        subscriber.process_message(
            'events:batch-service:extension:install-failed',
            '1234567891-0',
            data
        )

        subscriber.handle_extension_failed.assert_called_once()

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_process_message_parses_json_payload(self, mock_redis_class):
        """Test JSON payload parsing."""
        subscriber = EventSubscriber()
        subscriber.handle_extension_installed = Mock()

        payload_dict = {
            'database_id': 'db-123',
            'extension_name': 'TestExtension',
            'duration_seconds': 45.2
        }

        data = {
            'event_type': 'extension.installed',
            'correlation_id': 'corr-123',
            'payload': json.dumps(payload_dict)  # JSON string
        }

        subscriber.process_message(
            'events:batch-service:extension:installed',
            '1234567890-0',
            data
        )

        # Handler should receive parsed dict
        call_args = subscriber.handle_extension_installed.call_args
        self.assertEqual(call_args[0][0], payload_dict)

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_handle_extension_installed(self, mock_redis_class):
        """Test extension installed event processing."""
        subscriber = EventSubscriber()

        payload = {
            'database_id': 'db-123',
            'extension_name': 'TestExtension',
            'duration_seconds': 45.2,
            'output': 'Success'
        }

        correlation_id = f'batch-{self.batch_op.id}-{self.task.id}'

        # Process event
        subscriber.handle_extension_installed(payload, correlation_id)

        # Task should be marked as completed
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.STATUS_COMPLETED)
        self.assertIsNotNone(self.task.result)
        self.assertEqual(self.task.result['database_id'], 'db-123')

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_handle_extension_failed(self, mock_redis_class):
        """Test extension install failed event processing."""
        subscriber = EventSubscriber()

        payload = {
            'database_id': 'db-123',
            'extension_name': 'TestExtension',
            'error': 'Connection timeout',
            'error_code': 'TIMEOUT',
            'duration_seconds': 30.0
        }

        correlation_id = f'batch-{self.batch_op.id}-{self.task.id}'

        # Process event
        subscriber.handle_extension_failed(payload, correlation_id)

        # Task should be marked as failed or retry
        self.task.refresh_from_db()
        self.assertIn(self.task.status, [Task.STATUS_FAILED, Task.STATUS_RETRY])
        self.assertEqual(self.task.error_message, 'Connection timeout')
        self.assertEqual(self.task.error_code, 'TIMEOUT')

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_update_task_status_parses_correlation_id(self, mock_redis_class):
        """Test correlation_id parsing and task lookup."""
        subscriber = EventSubscriber()

        correlation_id = f'batch-{self.batch_op.id}-{self.task.id}'

        result = {'test': 'data'}

        # Update task status
        subscriber._update_task_status_from_correlation_id(
            correlation_id=correlation_id,
            status=Task.STATUS_COMPLETED,
            result=result
        )

        # Task should be updated
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.STATUS_COMPLETED)
        self.assertEqual(self.task.result, result)

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_update_task_status_handles_invalid_correlation_id(self, mock_redis_class):
        """Test handling of invalid correlation_id format."""
        subscriber = EventSubscriber()

        # Should not raise exception
        try:
            subscriber._update_task_status_from_correlation_id(
                correlation_id='invalid-format',
                status=Task.STATUS_COMPLETED
            )
        except Exception as e:
            self.fail(f"_update_task_status_from_correlation_id raised exception: {e}")

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_update_task_status_handles_nonexistent_task(self, mock_redis_class):
        """Test handling of nonexistent task."""
        subscriber = EventSubscriber()

        correlation_id = 'batch-123-nonexistent-task-id'

        # Should not raise exception
        try:
            subscriber._update_task_status_from_correlation_id(
                correlation_id=correlation_id,
                status=Task.STATUS_COMPLETED
            )
        except Exception as e:
            self.fail(f"_update_task_status_from_correlation_id raised exception: {e}")

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_handle_infobase_locked(self, mock_redis_class):
        """Test infobase locked event processing."""
        subscriber = EventSubscriber()

        payload = {
            'cluster_id': 'cluster-uuid',
            'infobase_id': 'infobase-uuid',
            'reason': 'maintenance'
        }

        # Should not raise exception (TODO: Update when Database model implemented)
        try:
            subscriber.handle_infobase_locked(payload, 'corr-123')
        except Exception as e:
            self.fail(f"handle_infobase_locked raised exception: {e}")

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_handle_sessions_closed(self, mock_redis_class):
        """Test sessions closed event processing."""
        subscriber = EventSubscriber()

        payload = {
            'cluster_id': 'cluster-uuid',
            'infobase_id': 'infobase-uuid',
            'sessions_closed': 5,
            'duration_seconds': 2.3
        }

        # Should not raise exception
        try:
            subscriber.handle_sessions_closed(payload, 'corr-123')
        except Exception as e:
            self.fail(f"handle_sessions_closed raised exception: {e}")

    @patch('apps.operations.event_subscriber.redis.Redis')
    @patch('apps.operations.event_subscriber.time.sleep')
    def test_run_forever_handles_connection_error(self, mock_sleep, mock_redis_class):
        """Test graceful handling of Redis connection errors."""
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        # Mock xgroup_create to succeed
        mock_redis.xgroup_create.return_value = True

        # Simulate connection error then running = False to stop
        import redis as redis_module

        call_count = [0]
        def xreadgroup_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise redis_module.ConnectionError("Connection lost")
            # On second call, subscriber.running will be False, loop exits
            return []

        mock_redis.xreadgroup.side_effect = xreadgroup_side_effect

        subscriber = EventSubscriber()

        # Stop after handling connection error
        original_process = subscriber.process_message
        def stop_after_sleep(*args, **kwargs):
            subscriber.running = False
        mock_sleep.side_effect = stop_after_sleep

        try:
            subscriber.run_forever()
        except Exception as e:
            self.fail(f"run_forever raised exception: {e}")

        # Should have called sleep with 5 seconds
        mock_sleep.assert_called_with(5)

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_process_message_handles_invalid_json(self, mock_redis_class):
        """Test handling of invalid JSON payload."""
        subscriber = EventSubscriber()

        data = {
            'event_type': 'extension.installed',
            'correlation_id': 'corr-123',
            'payload': 'invalid-json{'  # Invalid JSON
        }

        # Should not raise exception
        try:
            subscriber.process_message(
                'events:batch-service:extension:installed',
                '1234567890-0',
                data
            )
        except Exception as e:
            self.fail(f"process_message raised exception: {e}")
