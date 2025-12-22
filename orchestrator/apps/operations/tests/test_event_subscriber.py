"""
Unit tests for Event Subscriber.

Tests Redis Streams integration, event processing, and Task status updates.
"""

from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
import json
import uuid

from apps.operations.event_subscriber import EventSubscriber
from apps.operations.models import BatchOperation, Task
from apps.databases.models import Database


@override_settings(
    REDIS_HOST='localhost',
    REDIS_PORT=6379,
)
class EventSubscriberTest(TestCase):
    """Test suite for EventSubscriber class."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._close_patcher = patch('apps.operations.event_subscriber.close_old_connections')
        cls._close_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls._close_patcher.stop()
        super().tearDownClass()

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
        self.assertIn('events:worker:cluster-synced', subscriber.streams)
        self.assertIn('events:worker:completed', subscriber.streams)

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
        subscriber.handle_cluster_synced = Mock()
        subscriber.handle_worker_completed = Mock()

        data = {
            'event_type': 'cluster.synced',
            'correlation_id': 'corr-123',
            'timestamp': '2025-11-12T10:30:00Z',
            'payload': json.dumps({'infobase_id': 'infobase-123'})
        }

        subscriber.process_message(
            'events:worker:cluster-synced',
            '1234567890-0',
            data
        )

        subscriber.handle_cluster_synced.assert_called_once()

        subscriber.process_message(
            'events:worker:completed',
            '1234567891-0',
            data
        )

        subscriber.handle_worker_completed.assert_called_once()

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_process_message_parses_json_payload(self, mock_redis_class):
        """Test JSON payload parsing."""
        subscriber = EventSubscriber()
        subscriber.handle_cluster_synced = Mock()

        payload_dict = {
            'cluster_id': 'cluster-uuid',
            'infobase_id': 'infobase-uuid',
            'reason': 'maintenance'
        }

        data = {
            'event_type': 'cluster.synced',
            'correlation_id': 'corr-123',
            'payload': json.dumps(payload_dict)  # JSON string
        }

        subscriber.process_message(
            'events:worker:cluster-synced',
            '1234567890-0',
            data
        )

        # Handler should receive parsed dict
        call_args = subscriber.handle_cluster_synced.call_args
        self.assertEqual(call_args[0][0], payload_dict)

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

    @patch('apps.operations.event_subscriber.operations_redis_client')
    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_handle_worker_completed_updates_restrictions(self, mock_redis_class, mock_ops_redis):
        subscriber = EventSubscriber()

        block_op = BatchOperation.objects.create(
            id=str(uuid.uuid4()),
            name='Block Sessions',
            operation_type=BatchOperation.TYPE_BLOCK_SESSIONS,
            target_entity='Infobase',
            status=BatchOperation.STATUS_PROCESSING,
            payload={
                'data': {
                    'message': 'Maintenance',
                    'permission_code': 'ALLOW',
                    'denied_from': '2025-01-01T00:00:00Z',
                    'denied_to': '2025-01-02T00:00:00Z',
                    'parameter': 'param',
                }
            },
        )

        subscriber.handle_worker_completed(
            {
                'operation_id': block_op.id,
                'results': [{'database_id': self.database.id, 'success': True}],
                'summary': {},
            },
            'corr-123',
        )

        self.database.refresh_from_db()
        self.assertTrue(self.database.metadata['sessions_deny'])
        self.assertEqual(self.database.metadata['denied_message'], 'Maintenance')
        self.assertEqual(self.database.metadata['permission_code'], 'ALLOW')
        self.assertEqual(self.database.metadata['denied_from'], '2025-01-01T00:00:00Z')
        self.assertEqual(self.database.metadata['denied_to'], '2025-01-02T00:00:00Z')
        self.assertEqual(self.database.metadata['denied_parameter'], 'param')

        unblock_op = BatchOperation.objects.create(
            id=str(uuid.uuid4()),
            name='Unblock Sessions',
            operation_type=BatchOperation.TYPE_UNBLOCK_SESSIONS,
            target_entity='Infobase',
            status=BatchOperation.STATUS_PROCESSING,
        )

        subscriber.handle_worker_completed(
            {
                'operation_id': unblock_op.id,
                'results': [{'database_id': self.database.id, 'success': True}],
                'summary': {},
            },
            'corr-456',
        )

        self.database.refresh_from_db()
        self.assertFalse(self.database.metadata['sessions_deny'])
        self.assertNotIn('denied_message', self.database.metadata)
        self.assertNotIn('permission_code', self.database.metadata)
        self.assertNotIn('denied_from', self.database.metadata)
        self.assertNotIn('denied_to', self.database.metadata)
        self.assertNotIn('denied_parameter', self.database.metadata)

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
            'event_type': 'cluster.synced',
            'correlation_id': 'corr-123',
            'payload': 'invalid-json{'  # Invalid JSON
        }

        # Should not raise exception
        try:
            subscriber.process_message(
                'events:worker:cluster-synced',
                '1234567890-0',
                data
            )
        except Exception as e:
            self.fail(f"process_message raised exception: {e}")


@override_settings(
    REDIS_HOST='localhost',
    REDIS_PORT=6379,
)
class EventSubscriberClusterInfoTest(TestCase):
    """Test suite for get-cluster-info handler."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._close_patcher = patch('apps.operations.event_subscriber.close_old_connections')
        cls._close_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls._close_patcher.stop()
        super().tearDownClass()

    def setUp(self):
        """Set up test fixtures with cluster configuration."""
        from apps.databases.models import Cluster

        # Create test Cluster with RAS configuration
        self.cluster = Cluster.objects.create(
            id=uuid.uuid4(),
            name='Test Cluster',
            ras_server='localhost:1545',
            ras_cluster_uuid=uuid.uuid4(),
            cluster_service_url='http://localhost:8188',
            status=Cluster.STATUS_ACTIVE,
        )

        # Create test Database with cluster
        self.database = Database.objects.create(
            id='db-with-cluster',
            name='Database With Cluster',
            host='localhost',
            port=80,
            odata_url='http://localhost/odata',
            username='admin',
            password='password',
            cluster=self.cluster,
            ras_infobase_id=uuid.uuid4(),
        )

        # Create Database without cluster
        self.database_no_cluster = Database.objects.create(
            id='db-no-cluster',
            name='Database Without Cluster',
            host='localhost',
            port=80,
            odata_url='http://localhost/odata',
            username='admin',
            password='password',
        )

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_handle_get_cluster_info_success(self, mock_redis_class):
        """Test successful cluster info retrieval."""
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()

        data = {
            'correlation_id': 'test-corr-123',
            'database_id': self.database.id,
            'timestamp': '2025-12-15T10:30:00Z',
        }

        # Call handler
        subscriber.handle_get_cluster_info(data, 'test-corr-123')

        # Verify xadd was called with correct response
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args

        # Check stream name
        self.assertEqual(
            call_args[0][0],
            'events:orchestrator:cluster-info-response'
        )

        # Check response content
        response = call_args[0][1]
        self.assertEqual(response['correlation_id'], 'test-corr-123')
        self.assertEqual(response['database_id'], self.database.id)
        self.assertEqual(response['success'], 'true')
        self.assertEqual(response['ras_server'], 'localhost:1545')
        self.assertNotEqual(response['ras_cluster_uuid'], '')
        self.assertNotEqual(response['infobase_id'], '')
        self.assertEqual(response['error'], '')

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_handle_get_database_credentials_success(self, mock_redis_class):
        """Test successful database credentials retrieval."""
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()

        data = {
            'correlation_id': 'test-creds-123',
            'database_id': self.database.id,
            'timestamp': '2025-12-16T10:30:00Z',
        }

        subscriber.handle_get_database_credentials(data, 'test-creds-123')

        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args

        self.assertEqual(call_args[0][0], 'events:orchestrator:database-credentials-response')

        response = call_args[0][1]
        self.assertEqual(response['correlation_id'], 'test-creds-123')
        self.assertEqual(response['database_id'], self.database.id)
        self.assertEqual(response['success'], 'true')
        self.assertEqual(response['error'], '')
        self.assertNotEqual(response['encrypted_data'], '')
        self.assertNotEqual(response['nonce'], '')
        self.assertNotEqual(response['expires_at'], '')
        self.assertNotEqual(response['encryption_version'], '')

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_handle_get_database_credentials_not_found(self, mock_redis_class):
        """Test database credentials handler for non-existent database."""
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()

        data = {
            'correlation_id': 'test-creds-404',
            'database_id': 'nonexistent-db',
            'timestamp': '2025-12-16T10:30:00Z',
        }

        subscriber.handle_get_database_credentials(data, 'test-creds-404')

        mock_redis.xadd.assert_called_once()
        response = mock_redis.xadd.call_args[0][1]

        self.assertEqual(response['correlation_id'], 'test-creds-404')
        self.assertEqual(response['database_id'], 'nonexistent-db')
        self.assertEqual(response['success'], 'false')
        self.assertIn('not found', response['error'])
        self.assertEqual(response['encrypted_data'], '')
        self.assertEqual(response['nonce'], '')
        self.assertEqual(response['expires_at'], '')
        self.assertEqual(response['encryption_version'], '')

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_handle_get_cluster_info_database_not_found(self, mock_redis_class):
        """Test cluster info for non-existent database."""
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()

        data = {
            'correlation_id': 'test-corr-456',
            'database_id': 'nonexistent-db',
            'timestamp': '2025-12-15T10:30:00Z',
        }

        subscriber.handle_get_cluster_info(data, 'test-corr-456')

        # Verify error response
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        response = call_args[0][1]

        self.assertEqual(response['correlation_id'], 'test-corr-456')
        self.assertEqual(response['database_id'], 'nonexistent-db')
        self.assertEqual(response['success'], 'false')
        self.assertIn('not found', response['error'])

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_handle_get_cluster_info_no_cluster(self, mock_redis_class):
        """Test cluster info for database without cluster."""
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()

        data = {
            'correlation_id': 'test-corr-789',
            'database_id': self.database_no_cluster.id,
            'timestamp': '2025-12-15T10:30:00Z',
        }

        subscriber.handle_get_cluster_info(data, 'test-corr-789')

        # Verify error response
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        response = call_args[0][1]

        self.assertEqual(response['correlation_id'], 'test-corr-789')
        self.assertEqual(response['success'], 'false')
        self.assertIn('no cluster', response['error'].lower())

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_handle_get_cluster_info_no_ras_cluster_uuid(self, mock_redis_class):
        """Test cluster info for cluster without ras_cluster_uuid."""
        from apps.databases.models import Cluster

        # Create cluster without ras_cluster_uuid
        cluster_no_uuid = Cluster.objects.create(
            id=uuid.uuid4(),
            name='Cluster Without UUID',
            ras_server='localhost:1545',
            ras_cluster_uuid=None,  # No UUID
            cluster_service_url='http://localhost:8188',
        )

        database = Database.objects.create(
            id='db-no-ras-uuid',
            name='DB No RAS UUID',
            host='localhost',
            port=80,
            odata_url='http://localhost/odata',
            username='admin',
            password='password',
            cluster=cluster_no_uuid,
        )

        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()

        data = {
            'correlation_id': 'test-corr-no-uuid',
            'database_id': database.id,
        }

        subscriber.handle_get_cluster_info(data, 'test-corr-no-uuid')

        response = mock_redis.xadd.call_args[0][1]
        self.assertEqual(response['success'], 'false')
        self.assertIn('ras_cluster_uuid', response['error'])

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_handle_get_cluster_info_no_infobase_id(self, mock_redis_class):
        """Test cluster info for database without ras_infobase_id."""
        from apps.databases.models import Cluster

        # Create cluster with UUID
        cluster = Cluster.objects.create(
            id=uuid.uuid4(),
            name='Cluster With UUID',
            ras_server='localhost:1545',
            ras_cluster_uuid=uuid.uuid4(),
            cluster_service_url='http://localhost:8188',
        )

        database = Database.objects.create(
            id='db-no-infobase-id',
            name='DB No Infobase ID',
            host='localhost',
            port=80,
            odata_url='http://localhost/odata',
            username='admin',
            password='password',
            cluster=cluster,
            ras_infobase_id=None,  # No infobase ID
        )

        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()

        data = {
            'correlation_id': 'test-corr-no-infobase',
            'database_id': database.id,
        }

        subscriber.handle_get_cluster_info(data, 'test-corr-no-infobase')

        response = mock_redis.xadd.call_args[0][1]
        self.assertEqual(response['success'], 'false')
        self.assertIn('ras_infobase_id', response['error'])

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_handle_get_cluster_info_success(self, mock_redis_class):
        """Test successful cluster info response."""
        from apps.databases.models import Cluster

        cluster_uuid = uuid.uuid4()
        infobase_uuid = uuid.uuid4()

        cluster = Cluster.objects.create(
            id=uuid.uuid4(),
            name='Cluster Success',
            ras_server='localhost:1545',
            ras_cluster_uuid=cluster_uuid,
            cluster_service_url='http://localhost:8188',
        )

        database = Database.objects.create(
            id='db-success',
            name='DB Success',
            host='localhost',
            port=80,
            odata_url='http://localhost/odata',
            username='admin',
            password='password',
            cluster=cluster,
            ras_infobase_id=infobase_uuid,
        )

        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()

        data = {
            'correlation_id': 'test-corr-success',
            'database_id': database.id,
        }

        subscriber.handle_get_cluster_info(data, 'test-corr-success')

        response = mock_redis.xadd.call_args[0][1]
        self.assertEqual(response['success'], 'true')
        self.assertEqual(response['cluster_id'], str(cluster_uuid))
        self.assertEqual(response['ras_cluster_uuid'], str(cluster_uuid))
        self.assertEqual(response['infobase_id'], str(infobase_uuid))

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_process_message_routes_to_get_cluster_info(self, mock_redis_class):
        """Test message routing to get_cluster_info handler."""
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()
        subscriber.handle_get_cluster_info = MagicMock()

        data = {
            'correlation_id': 'test-corr-routing',
            'database_id': 'db-123',
            'timestamp': '2025-12-15T10:30:00Z',
        }

        subscriber.process_message(
            'commands:orchestrator:get-cluster-info',
            '1234567890-0',
            data
        )

        subscriber.handle_get_cluster_info.assert_called_once()

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_process_message_routes_to_get_database_credentials(self, mock_redis_class):
        """Test message routing to get_database_credentials handler."""
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()
        subscriber.handle_get_database_credentials = MagicMock()

        data = {
            'correlation_id': 'test-creds-routing',
            'database_id': 'db-123',
            'timestamp': '2025-12-16T10:30:00Z',
        }

        subscriber.process_message(
            'commands:orchestrator:get-database-credentials',
            '1234567890-0',
            data
        )

        subscriber.handle_get_database_credentials.assert_called_once()

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_subscriber_streams_includes_get_cluster_info(self, mock_redis_class):
        """Test that subscriber streams include get-cluster-info command."""
        subscriber = EventSubscriber()

        self.assertIn(
            'commands:orchestrator:get-cluster-info',
            subscriber.streams
        )

    @patch('apps.operations.event_subscriber.redis.Redis')
    def test_subscriber_streams_includes_get_database_credentials(self, mock_redis_class):
        """Test that subscriber streams include get-database-credentials command."""
        subscriber = EventSubscriber()

        self.assertIn(
            'commands:orchestrator:get-database-credentials',
            subscriber.streams
        )
