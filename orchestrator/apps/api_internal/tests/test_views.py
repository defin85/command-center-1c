"""
Tests for Internal API v2 endpoints.

All endpoints require X-Internal-Token authentication.
Tests cover:
- Scheduler endpoints (start/complete run)
- Task endpoints (start/complete task)
- Database endpoints (credentials, list, health update)
- Cluster endpoints (health update)
- Failed events endpoints (list, replay, mark failed, cleanup)
- Template endpoints (get, render)
- Authentication across all endpoints
"""
import uuid
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status

from apps.operations.models import BatchOperation


@override_settings(INTERNAL_API_TOKEN='test-internal-token')
class InternalAPIV2BaseTestCase(TestCase):
    """Base test case with authenticated client."""

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_X_INTERNAL_TOKEN='test-internal-token')

    def get_unauthenticated_client(self):
        """Return client without auth headers."""
        return APIClient()


class SchedulerEndpointsV2Tests(InternalAPIV2BaseTestCase):
    """Tests for scheduler v2 endpoints."""

    def test_start_scheduler_run_success(self):
        """Test starting a scheduler run."""
        response = self.client.post(
            '/api/v2/internal/start-scheduler-run',
            {'job_name': 'health_check', 'worker_instance': 'worker-1'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertIn('run_id', response.data)
        self.assertEqual(response.data['status'], 'running')
        self.assertGreater(response.data['run_id'], 0)

    def test_start_scheduler_run_unauthorized(self):
        """Test that unauthorized requests are rejected."""
        client = self.get_unauthenticated_client()
        response = client.post(
            '/api/v2/internal/start-scheduler-run',
            {'job_name': 'health_check', 'worker_instance': 'worker-1'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_start_scheduler_run_missing_job_name(self):
        """Test validation - missing job_name."""
        response = self.client.post(
            '/api/v2/internal/start-scheduler-run',
            {'worker_instance': 'worker-1'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('job_name', response.data['error'])

    def test_start_scheduler_run_missing_worker_instance(self):
        """Test validation - missing worker_instance."""
        response = self.client.post(
            '/api/v2/internal/start-scheduler-run',
            {'job_name': 'health_check'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('worker_instance', response.data['error'])

    def test_complete_scheduler_run_success(self):
        """Test completing a scheduler run."""
        start_resp = self.client.post(
            '/api/v2/internal/start-scheduler-run',
            {'job_name': 'health_check', 'worker_instance': 'worker-1'},
            format='json'
        )
        self.assertEqual(start_resp.status_code, status.HTTP_201_CREATED)
        run_id = start_resp.data['run_id']

        response = self.client.post(
            f'/api/v2/internal/complete-scheduler-run?run_id={run_id}',
            {'status': 'success', 'duration_ms': 1000},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['status'], 'success')

    def test_complete_scheduler_run_missing_run_id(self):
        """Test validation - missing run_id query param."""
        response = self.client.post(
            '/api/v2/internal/complete-scheduler-run',
            {'status': 'success', 'duration_ms': 1000},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('run_id', response.data['error'])

    def test_complete_scheduler_run_invalid_run_id(self):
        """Test validation - run_id must be integer."""
        response = self.client.post(
            '/api/v2/internal/complete-scheduler-run?run_id=invalid',
            {'status': 'success', 'duration_ms': 1000},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_complete_scheduler_run_missing_status(self):
        """Test validation - missing status."""
        response = self.client.post(
            '/api/v2/internal/complete-scheduler-run?run_id=1',
            {'duration_ms': 1000},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_complete_scheduler_run_missing_duration(self):
        """Test that duration_ms is optional."""
        start_resp = self.client.post(
            '/api/v2/internal/start-scheduler-run',
            {'job_name': 'health_check', 'worker_instance': 'worker-1'},
            format='json'
        )
        run_id = start_resp.data['run_id']

        response = self.client.post(
            f'/api/v2/internal/complete-scheduler-run?run_id={run_id}',
            {'status': 'success'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

    def test_complete_scheduler_run_invalid_status(self):
        """Test validation - invalid status choice."""
        response = self.client.post(
            '/api/v2/internal/complete-scheduler-run?run_id=1',
            {'status': 'invalid', 'duration_ms': 1000},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)


class TaskEndpointsV2Tests(InternalAPIV2BaseTestCase):
    """Tests for task execution v2 endpoints."""

    def _create_operation(self) -> BatchOperation:
        return BatchOperation.objects.create(
            id=str(uuid.uuid4()),
            name='Test operation',
            operation_type=BatchOperation.TYPE_QUERY,
            target_entity='TestEntity',
        )

    def test_start_task_success(self):
        """Test starting a task."""
        operation = self._create_operation()
        response = self.client.post(
            '/api/v2/internal/start-task',
            {
                'operation_id': operation.id,
                'task_type': 'health_check',
                'target_id': str(uuid.uuid4()),
                'target_type': 'database',
                'worker_instance': 'worker-1',
                'parameters': {'foo': 'bar'},
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertIn('task_id', response.data)
        self.assertEqual(response.data['status'], 'running')
        self.assertGreater(response.data['task_id'], 0)

    def test_start_task_with_operation_id(self):
        """Test starting a task."""
        operation = self._create_operation()
        response = self.client.post(
            '/api/v2/internal/start-task',
            {
                'operation_id': operation.id,
                'task_type': 'batch_operation',
                'target_id': str(uuid.uuid4()),
                'target_type': 'database',
                'worker_instance': 'worker-2',
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_start_task_missing_required_fields(self):
        """Test validation - missing required fields."""
        operation = self._create_operation()

        # Missing operation_id
        response = self.client.post(
            '/api/v2/internal/start-task',
            {
                'task_type': 'health_check',
                'target_id': str(uuid.uuid4()),
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Missing task_type
        response = self.client.post(
            '/api/v2/internal/start-task',
            {
                'operation_id': operation.id,
                'target_id': str(uuid.uuid4()),
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_start_task_unauthorized(self):
        """Test that unauthorized requests are rejected."""
        operation = self._create_operation()
        client = self.get_unauthenticated_client()
        response = client.post(
            '/api/v2/internal/start-task',
            {
                'operation_id': operation.id,
                'task_type': 'health_check',
                'target_id': str(uuid.uuid4()),
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_complete_task_success(self):
        """Test completing a task."""
        operation = self._create_operation()
        start_resp = self.client.post(
            '/api/v2/internal/start-task',
            {
                'operation_id': operation.id,
                'task_type': 'health_check',
                'target_id': str(uuid.uuid4()),
                'worker_instance': 'worker-1',
            },
            format='json'
        )
        self.assertEqual(start_resp.status_code, status.HTTP_201_CREATED)
        task_id = start_resp.data['task_id']

        response = self.client.post(
            f'/api/v2/internal/complete-task?task_id={task_id}',
            {'status': 'success', 'duration_ms': 500},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['status'], 'success')

    def test_complete_task_missing_task_id(self):
        """Test validation - missing task_id query param."""
        response = self.client.post(
            '/api/v2/internal/complete-task',
            {'status': 'success', 'duration_ms': 500},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('task_id', response.data['error'])

    def test_complete_task_invalid_task_id(self):
        """Test validation - task_id must be integer."""
        response = self.client.post(
            '/api/v2/internal/complete-task?task_id=invalid',
            {'status': 'success', 'duration_ms': 500},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_complete_task_with_error(self):
        """Test completing a task with error."""
        operation = self._create_operation()
        start_resp = self.client.post(
            '/api/v2/internal/start-task',
            {
                'operation_id': operation.id,
                'task_type': 'health_check',
                'target_id': str(uuid.uuid4()),
                'worker_instance': 'worker-1',
            },
            format='json'
        )
        task_id = start_resp.data['task_id']

        response = self.client.post(
            f'/api/v2/internal/complete-task?task_id={task_id}',
            {
                'status': 'failed',
                'duration_ms': 100,
                'error_message': 'Connection timeout',
                'error_code': 'NetworkError',
                'retry_count': 3
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])


class DatabaseEndpointsV2Tests(InternalAPIV2BaseTestCase):
    """Tests for database v2 endpoints."""

    def test_get_database_cluster_info_missing_id(self):
        """Test validation - missing database_id."""
        response = self.client.get('/api/v2/internal/get-database-cluster-info')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('database_id', response.data['error'])

    def test_get_database_cluster_info_not_found(self):
        """Test non-existent database."""
        response = self.client.get(
            f'/api/v2/internal/get-database-cluster-info?database_id={uuid.uuid4()}'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    def test_get_database_cluster_info_unauthorized(self):
        """Test that unauthorized requests are rejected."""
        client = self.get_unauthenticated_client()
        response = client.get(
            f'/api/v2/internal/get-database-cluster-info?database_id={uuid.uuid4()}'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_database_cluster_info_success(self):
        """Test cluster/infobase ids retrieval."""
        from apps.databases.models import Database

        ras_cluster_id = uuid.uuid4()
        ras_infobase_id = uuid.uuid4()
        db = Database.objects.create(
            id="db-cluster-info-1",
            name="DB Cluster Info 1",
            host="localhost",
            odata_url="http://localhost/odata",
            username="admin",
            password="secret",
            ras_cluster_id=ras_cluster_id,
            ras_infobase_id=ras_infobase_id,
        )

        response = self.client.get(
            f'/api/v2/internal/get-database-cluster-info?database_id={db.id}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['cluster_info']['database_id'], db.id)
        self.assertEqual(response.data['cluster_info']['cluster_id'], str(ras_cluster_id))
        self.assertEqual(response.data['cluster_info']['infobase_id'], str(ras_infobase_id))

    def test_list_databases_for_health_check(self):
        """Test listing databases for health check."""
        response = self.client.get('/api/v2/internal/list-databases-for-health-check')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('databases', response.data)
        self.assertIn('count', response.data)
        self.assertIsInstance(response.data['databases'], list)
        self.assertIsInstance(response.data['count'], int)

    def test_list_databases_for_health_check_unauthorized(self):
        """Test that unauthorized requests are rejected."""
        client = self.get_unauthenticated_client()
        response = client.get('/api/v2/internal/list-databases-for-health-check')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_database_health_missing_id(self):
        """Test validation - missing database_id."""
        response = self.client.post(
            '/api/v2/internal/update-database-health',
            {'healthy': True},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('database_id', response.data['error'])

    def test_update_database_health_not_found(self):
        """Test non-existent database."""
        response = self.client.post(
            f'/api/v2/internal/update-database-health?database_id={uuid.uuid4()}',
            {'healthy': True},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    def test_update_database_health_missing_healthy_field(self):
        """Test validation - missing healthy field."""
        response = self.client.post(
            f'/api/v2/internal/update-database-health?database_id={uuid.uuid4()}',
            {},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_update_database_health_unauthorized(self):
        """Test that unauthorized requests are rejected."""
        client = self.get_unauthenticated_client()
        response = client.post(
            f'/api/v2/internal/update-database-health?database_id={uuid.uuid4()}',
            {'healthy': True},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ClusterEndpointsV2Tests(InternalAPIV2BaseTestCase):
    """Tests for cluster v2 endpoints."""

    def test_update_cluster_health_missing_id(self):
        """Test validation - missing cluster_id."""
        response = self.client.post(
            '/api/v2/internal/update-cluster-health',
            {'healthy': True},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('cluster_id', response.data['error'])

    def test_update_cluster_health_not_found(self):
        """Test non-existent cluster."""
        response = self.client.post(
            f'/api/v2/internal/update-cluster-health?cluster_id={uuid.uuid4()}',
            {'healthy': True},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    def test_update_cluster_health_missing_healthy_field(self):
        """Test validation - missing healthy field."""
        response = self.client.post(
            f'/api/v2/internal/update-cluster-health?cluster_id={uuid.uuid4()}',
            {},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_update_cluster_health_unauthorized(self):
        """Test that unauthorized requests are rejected."""
        client = self.get_unauthenticated_client()
        response = client.post(
            f'/api/v2/internal/update-cluster-health?cluster_id={uuid.uuid4()}',
            {'healthy': True},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class FailedEventsEndpointsV2Tests(InternalAPIV2BaseTestCase):
    """Tests for failed events v2 endpoints."""

    def test_list_pending_failed_events(self):
        """Test listing pending failed events."""
        response = self.client.get('/api/v2/internal/list-pending-failed-events')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('events', response.data)
        self.assertIn('count', response.data)
        self.assertIsInstance(response.data['events'], list)
        self.assertIsInstance(response.data['count'], int)

    def test_list_pending_failed_events_with_batch_size(self):
        """Test listing with batch_size parameter."""
        response = self.client.get('/api/v2/internal/list-pending-failed-events?batch_size=50')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

    def test_list_pending_failed_events_invalid_batch_size(self):
        """Test with invalid batch_size - should use default."""
        response = self.client.get('/api/v2/internal/list-pending-failed-events?batch_size=invalid')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should not fail, just use default value

    def test_list_pending_failed_events_unauthorized(self):
        """Test that unauthorized requests are rejected."""
        client = self.get_unauthenticated_client()
        response = client.get('/api/v2/internal/list-pending-failed-events')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_mark_event_replayed_missing_id(self):
        """Test validation - missing event_id."""
        response = self.client.post(
            '/api/v2/internal/mark-event-replayed',
            {},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('event_id', response.data['error'])

    def test_mark_event_replayed_invalid_id(self):
        """Test validation - event_id must be integer."""
        response = self.client.post(
            '/api/v2/internal/mark-event-replayed?event_id=invalid',
            {},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mark_event_replayed_not_found(self):
        """Test non-existent event."""
        response = self.client.post(
            '/api/v2/internal/mark-event-replayed?event_id=99999',
            {},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    def test_mark_event_replayed_unauthorized(self):
        """Test that unauthorized requests are rejected."""
        client = self.get_unauthenticated_client()
        response = client.post(
            '/api/v2/internal/mark-event-replayed?event_id=1',
            {},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_mark_event_failed_missing_id(self):
        """Test validation - missing event_id."""
        response = self.client.post(
            '/api/v2/internal/mark-event-failed',
            {'error_message': 'Test error'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('event_id', response.data['error'])

    def test_mark_event_failed_invalid_id(self):
        """Test validation - event_id must be integer."""
        response = self.client.post(
            '/api/v2/internal/mark-event-failed?event_id=invalid',
            {'error_message': 'Test error'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mark_event_failed_missing_error_message(self):
        """Test validation - missing error_message."""
        response = self.client.post(
            '/api/v2/internal/mark-event-failed?event_id=1',
            {},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_mark_event_failed_not_found(self):
        """Test non-existent event."""
        response = self.client.post(
            '/api/v2/internal/mark-event-failed?event_id=99999',
            {'error_message': 'Test error'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    def test_mark_event_failed_unauthorized(self):
        """Test that unauthorized requests are rejected."""
        client = self.get_unauthenticated_client()
        response = client.post(
            '/api/v2/internal/mark-event-failed?event_id=1',
            {'error_message': 'Test error'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cleanup_failed_events(self):
        """Test cleanup endpoint."""
        response = self.client.post(
            '/api/v2/internal/cleanup-failed-events',
            {'retention_days': 7},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('deleted_count', response.data)
        self.assertIsInstance(response.data['deleted_count'], int)

    def test_cleanup_failed_events_default_retention(self):
        """Test cleanup with default retention_days."""
        response = self.client.post(
            '/api/v2/internal/cleanup-failed-events',
            {},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

    def test_cleanup_failed_events_invalid_retention(self):
        """Test cleanup with invalid retention_days."""
        response = self.client.post(
            '/api/v2/internal/cleanup-failed-events',
            {'retention_days': 0},  # Below min_value=1
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_cleanup_failed_events_unauthorized(self):
        """Test that unauthorized requests are rejected."""
        client = self.get_unauthenticated_client()
        response = client.post(
            '/api/v2/internal/cleanup-failed-events',
            {'retention_days': 7},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TemplateEndpointsV2Tests(InternalAPIV2BaseTestCase):
    """Tests for template v2 endpoints."""

    def test_get_template_missing_id(self):
        """Test validation - missing template_id."""
        response = self.client.get('/api/v2/internal/get-template')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('template_id', response.data['error'])

    def test_get_template_not_found(self):
        """Test non-existent template."""
        response = self.client.get('/api/v2/internal/get-template?template_id=nonexistent')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    def test_get_template_unauthorized(self):
        """Test that unauthorized requests are rejected."""
        client = self.get_unauthenticated_client()
        response = client.get('/api/v2/internal/get-template?template_id=test')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_render_template_missing_id(self):
        """Test validation - missing template_id."""
        response = self.client.post(
            '/api/v2/internal/render-template',
            {'context': {}},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('template_id', response.data['error'])

    def test_render_template_not_found(self):
        """Test non-existent template."""
        response = self.client.post(
            '/api/v2/internal/render-template?template_id=nonexistent',
            {'context': {}},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    def test_render_template_missing_context(self):
        """Test validation - missing context."""
        response = self.client.post(
            '/api/v2/internal/render-template?template_id=test',
            {},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_render_template_unauthorized(self):
        """Test that unauthorized requests are rejected."""
        client = self.get_unauthenticated_client()
        response = client.post(
            '/api/v2/internal/render-template?template_id=test',
            {'context': {}},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticationTests(InternalAPIV2BaseTestCase):
    """Tests for authentication across all endpoints."""

    def test_all_endpoints_require_auth(self):
        """Test that all v2 endpoints require authentication."""
        client = self.get_unauthenticated_client()

        endpoints = [
            ('post', '/api/v2/internal/start-scheduler-run'),
            ('post', '/api/v2/internal/complete-scheduler-run?run_id=1'),
            ('post', '/api/v2/internal/start-task'),
            ('post', '/api/v2/internal/complete-task?task_id=1'),
            ('get', '/api/v2/internal/list-databases-for-health-check'),
            ('post', '/api/v2/internal/update-database-health?database_id=00000000-0000-0000-0000-000000000000'),
            ('post', '/api/v2/internal/update-cluster-health?cluster_id=00000000-0000-0000-0000-000000000000'),
            ('get', '/api/v2/internal/list-pending-failed-events'),
            ('post', '/api/v2/internal/mark-event-replayed?event_id=1'),
            ('post', '/api/v2/internal/mark-event-failed?event_id=1'),
            ('post', '/api/v2/internal/cleanup-failed-events'),
            ('get', '/api/v2/internal/get-template?template_id=test'),
            ('post', '/api/v2/internal/render-template?template_id=test'),
        ]

        for method, url in endpoints:
            with self.subTest(url=url):
                if method == 'get':
                    response = client.get(url)
                else:
                    response = client.post(url, {}, format='json')
                self.assertEqual(
                    response.status_code,
                    status.HTTP_401_UNAUTHORIZED,
                    f"Expected 401 for {url}, got {response.status_code}"
                )

    def test_wrong_token_rejected(self):
        """Test that requests with wrong token are rejected."""
        client = APIClient()
        client.credentials(HTTP_X_INTERNAL_TOKEN='wrong-token')

        response = client.get('/api/v2/internal/list-databases-for-health-check')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_token_header_rejected(self):
        """Test that requests without X-Internal-Token header are rejected."""
        client = APIClient()
        # No credentials set

        response = client.get('/api/v2/internal/list-databases-for-health-check')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
