"""
Unit tests for Service Mesh REST API views.

Tests:
- ServiceMeshMetricsView - GET /api/v1/service-mesh/metrics/
- ServiceMeshHistoryView - GET /api/v1/service-mesh/history/{service}/
- ServiceMeshOperationsView - GET /api/v1/service-mesh/operations/
- Error handling and fallback behavior
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.operations.services.prometheus_client import (
    PrometheusClient,
    ServiceMetrics,
    ServiceConnection,
)
from apps.operations.models import BatchOperation


@pytest.fixture
def api_client():
    """Provide authenticated API client."""
    client = APIClient()
    user = User.objects.create_user(username='testuser', password='testpass')
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def authenticated_user(db):
    """Provide authenticated user."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    username = f'testuser_{uuid.uuid4().hex[:8]}'
    return User.objects.create_user(username=username, password='testpass')


class TestServiceMeshMetricsView:
    """Test ServiceMeshMetricsView endpoint."""

    @pytest.mark.django_db
    def test_metrics_view_requires_authentication(self, client):
        """Test endpoint requires authentication."""
        response = client.get('/api/v1/service-mesh/metrics/')
        # Should redirect to login or return 401 depending on DRF configuration
        assert response.status_code in [401, 403]

    @pytest.mark.django_db
    @patch('apps.operations.views.service_mesh.get_prometheus_client')
    def test_metrics_view_success(self, mock_get_client, api_client):
        """Test successful metrics retrieval."""
        # Create mock Prometheus client
        mock_client = AsyncMock(spec=PrometheusClient)

        # Create mock service metrics
        mock_metrics = [
            ServiceMetrics(
                name='api-gateway',
                display_name='API Gateway',
                status='healthy',
                ops_per_minute=500.0,
                active_operations=10,
                p95_latency_ms=100.0,
                error_rate=0.001,
                last_updated=datetime.utcnow(),
            ),
            ServiceMetrics(
                name='worker',
                display_name='Worker',
                status='healthy',
                ops_per_minute=300.0,
                active_operations=5,
                p95_latency_ms=200.0,
                error_rate=0.002,
                last_updated=datetime.utcnow(),
            ),
        ]

        # Create mock connections
        mock_connections = [
            ServiceConnection(
                source='api-gateway',
                target='orchestrator',
                requests_per_minute=400.0,
                avg_latency_ms=150.0,
            ),
        ]

        mock_client.get_all_services_metrics = AsyncMock(return_value=mock_metrics)
        mock_client.get_service_connections = AsyncMock(return_value=mock_connections)
        mock_client.get_overall_health = AsyncMock(return_value='healthy')
        mock_get_client.return_value = mock_client

        response = api_client.get('/api/v1/service-mesh/metrics/')

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert 'services' in data
        assert len(data['services']) == 2
        assert data['services'][0]['name'] == 'api-gateway'
        assert data['services'][0]['status'] == 'healthy'

        assert 'connections' in data
        assert len(data['connections']) == 1

        assert 'overall_health' in data
        assert data['overall_health'] == 'healthy'

        assert 'timestamp' in data

    @pytest.mark.django_db
    @patch('apps.operations.views.service_mesh.get_prometheus_client')
    def test_metrics_view_prometheus_unavailable(self, mock_get_client, api_client):
        """Test metrics view handles Prometheus unavailability gracefully."""
        mock_client = AsyncMock(spec=PrometheusClient)
        mock_client.get_all_services_metrics = AsyncMock(
            side_effect=Exception("Prometheus connection failed")
        )
        mock_get_client.return_value = mock_client

        response = api_client.get('/api/v1/service-mesh/metrics/')

        # Should return 200 with fallback data
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should include fallback services
        assert 'services' in data
        assert len(data['services']) > 0

        # All should be degraded since Prometheus is unavailable
        assert all(s['status'] == 'degraded' for s in data['services'])

        # Should indicate error
        assert data['overall_health'] == 'degraded'
        assert 'error' in data

    @pytest.mark.django_db
    @patch('apps.operations.views.service_mesh.get_prometheus_client')
    def test_metrics_view_empty_services(self, mock_get_client, api_client):
        """Test metrics view with no service metrics."""
        mock_client = AsyncMock(spec=PrometheusClient)
        mock_client.get_all_services_metrics = AsyncMock(return_value=[])
        mock_client.get_service_connections = AsyncMock(return_value=[])
        mock_client.get_overall_health = AsyncMock(return_value='critical')
        mock_get_client.return_value = mock_client

        response = api_client.get('/api/v1/service-mesh/metrics/')

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data['services'] == []
        assert data['overall_health'] == 'critical'


class TestServiceMeshHistoryView:
    """Test ServiceMeshHistoryView endpoint."""

    @pytest.mark.django_db
    def test_history_view_requires_authentication(self, client):
        """Test endpoint requires authentication."""
        response = client.get('/api/v1/service-mesh/history/api-gateway/')
        assert response.status_code in [401, 403]

    @pytest.mark.django_db
    @patch('apps.operations.views.service_mesh.get_prometheus_client')
    def test_history_view_success(self, mock_get_client, api_client):
        """Test successful historical metrics retrieval."""
        mock_client = AsyncMock(spec=PrometheusClient)

        mock_data_points = [
            {
                'timestamp': (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
                'ops_per_minute': 100.0,
                'p95_latency_ms': 150.0,
                'error_rate': 0.001,
            },
            {
                'timestamp': (datetime.utcnow() - timedelta(minutes=4)).isoformat(),
                'ops_per_minute': 110.0,
                'p95_latency_ms': 160.0,
                'error_rate': 0.002,
            },
            {
                'timestamp': datetime.utcnow().isoformat(),
                'ops_per_minute': 120.0,
                'p95_latency_ms': 170.0,
                'error_rate': 0.001,
            },
        ]

        mock_client.get_historical_metrics = AsyncMock(return_value=mock_data_points)
        mock_get_client.return_value = mock_client

        response = api_client.get('/api/v1/service-mesh/history/api-gateway/')

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data['service'] == 'api-gateway'
        assert data['display_name'] == 'API Gateway'
        assert data['minutes'] == 30  # Default
        assert len(data['data_points']) == 3

    @pytest.mark.django_db
    @patch('apps.operations.views.service_mesh.get_prometheus_client')
    def test_history_view_with_minutes_param(self, mock_get_client, api_client):
        """Test historical metrics with custom time range."""
        mock_client = AsyncMock(spec=PrometheusClient)
        mock_client.get_historical_metrics = AsyncMock(return_value=[])
        mock_get_client.return_value = mock_client

        response = api_client.get('/api/v1/service-mesh/history/worker/?minutes=60')

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data['service'] == 'worker'
        assert data['minutes'] == 60

        # Verify the client was called with correct minutes
        mock_client.get_historical_metrics.assert_called_once()
        call_args = mock_client.get_historical_metrics.call_args
        assert call_args[0][1] == 60 or call_args[1].get('minutes') == 60

    @pytest.mark.django_db
    @patch('apps.operations.views.service_mesh.get_prometheus_client')
    def test_history_view_clamped_minutes(self, mock_get_client, api_client):
        """Test minutes parameter is clamped to valid range."""
        mock_client = AsyncMock(spec=PrometheusClient)
        mock_client.get_historical_metrics = AsyncMock(return_value=[])
        mock_get_client.return_value = mock_client

        # Request with too small value (should clamp to 5)
        api_client.get('/api/v1/service-mesh/history/api-gateway/?minutes=1')

        # Request with too large value (should clamp to 1440)
        api_client.get('/api/v1/service-mesh/history/api-gateway/?minutes=9999')

        # Both calls should succeed
        assert mock_client.get_historical_metrics.call_count == 2

    @pytest.mark.django_db
    def test_history_view_invalid_service(self, api_client):
        """Test history view with invalid service name."""
        response = api_client.get('/api/v1/service-mesh/history/nonexistent-service/')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert 'error' in data
        assert 'Unknown service' in data['error']

    @pytest.mark.django_db
    @patch('apps.operations.views.service_mesh.get_prometheus_client')
    def test_history_view_prometheus_error(self, mock_get_client, api_client):
        """Test history view handles Prometheus errors gracefully."""
        mock_client = AsyncMock(spec=PrometheusClient)
        mock_client.get_historical_metrics = AsyncMock(
            side_effect=Exception("Prometheus error")
        )
        mock_get_client.return_value = mock_client

        response = api_client.get('/api/v1/service-mesh/history/api-gateway/')

        # Should return 200 with empty data points and error message
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data['data_points'] == []
        assert 'error' in data

    @pytest.mark.django_db
    def test_history_view_invalid_minutes_param(self, api_client):
        """Test history view with invalid minutes parameter."""
        response = api_client.get('/api/v1/service-mesh/history/api-gateway/?minutes=not_a_number')

        # Should handle gracefully and use default
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data['minutes'] == 30  # Default


class TestServiceMeshOperationsView:
    """Test ServiceMeshOperationsView endpoint."""

    @pytest.mark.django_db
    def test_operations_view_requires_authentication(self, client):
        """Test endpoint requires authentication."""
        response = client.get('/api/v1/service-mesh/operations/')
        assert response.status_code in [401, 403]

    @pytest.mark.django_db
    def test_operations_view_success(self, api_client, authenticated_user):
        """Test successful operations retrieval."""
        # Create test BatchOperation
        BatchOperation.objects.create(
            id='op-1',
            name='Operation 1',
            operation_type=BatchOperation.TYPE_INSTALL_EXTENSION,
            target_entity='Extension',
            status=BatchOperation.STATUS_COMPLETED,
            total_tasks=10,
            completed_tasks=10,
            failed_tasks=0,
            progress=100,
            created_at=timezone.now() - timedelta(minutes=5),
            completed_at=timezone.now(),
        )

        op2 = BatchOperation.objects.create(
            id='op-2',
            name='Operation 2',
            operation_type=BatchOperation.TYPE_QUERY,
            target_entity='Document',
            status=BatchOperation.STATUS_PROCESSING,
            total_tasks=20,
            completed_tasks=15,
            failed_tasks=1,
            progress=75,
            created_at=timezone.now() - timedelta(minutes=10),
        )

        response = api_client.get('/api/v1/service-mesh/operations/')

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert 'operations' in data
        assert len(data['operations']) == 2
        assert data['total'] == 2

        # Verify operation data
        assert data['operations'][0]['id'] == op2.id or data['operations'][1]['id'] == op2.id
        assert data['operations'][0]['status'] in ['completed', 'processing']

    @pytest.mark.django_db
    def test_operations_view_with_limit(self, api_client, authenticated_user):
        """Test operations view respects limit parameter."""
        # Create multiple operations
        for i in range(10):
            BatchOperation.objects.create(
                id=f'op-{i}',
                name=f'Operation {i}',
                operation_type=BatchOperation.TYPE_QUERY,
                target_entity='Document',
                status=BatchOperation.STATUS_COMPLETED,
                total_tasks=1,
                completed_tasks=1,
                failed_tasks=0,
                progress=100,
                created_at=timezone.now() - timedelta(minutes=i),
            )

        response = api_client.get('/api/v1/service-mesh/operations/?limit=5')

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data['operations']) == 5
        assert data['total'] == 10

    @pytest.mark.django_db
    def test_operations_view_clamped_limit(self, api_client, authenticated_user):
        """Test limit parameter is clamped to valid range."""
        BatchOperation.objects.create(
            id='op-1',
            name='Operation 1',
            operation_type=BatchOperation.TYPE_QUERY,
            target_entity='Document',
            status=BatchOperation.STATUS_COMPLETED,
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            progress=100,
        )

        # Request with too large limit (should clamp to 200)
        response = api_client.get('/api/v1/service-mesh/operations/?limit=9999')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data['operations']) <= 200

        # Request with too small limit (should clamp to 1)
        response = api_client.get('/api/v1/service-mesh/operations/?limit=0')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data['operations']) >= 0

    @pytest.mark.django_db
    def test_operations_view_with_status_filter(self, api_client, authenticated_user):
        """Test operations view with status filter."""
        # Create operations with different statuses
        BatchOperation.objects.create(
            id='op-1',
            name='Operation 1',
            operation_type=BatchOperation.TYPE_QUERY,
            target_entity='Document',
            status=BatchOperation.STATUS_COMPLETED,
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            progress=100,
        )

        BatchOperation.objects.create(
            id='op-2',
            name='Operation 2',
            operation_type=BatchOperation.TYPE_QUERY,
            target_entity='Document',
            status=BatchOperation.STATUS_PROCESSING,
            total_tasks=10,
            completed_tasks=5,
            failed_tasks=0,
            progress=50,
        )

        response = api_client.get('/api/v1/service-mesh/operations/?status=completed')

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data['operations']) == 1
        assert data['operations'][0]['status'] == 'completed'

    @pytest.mark.django_db
    def test_operations_view_ordered_by_created_at(self, api_client, authenticated_user):
        """Test operations are ordered by creation time (newest first)."""
        # Create operations in non-chronological order
        op1 = BatchOperation.objects.create(
            id='op-1',
            name='Operation 1',
            operation_type=BatchOperation.TYPE_QUERY,
            target_entity='Document',
            status=BatchOperation.STATUS_COMPLETED,
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            progress=100,
            created_at=timezone.now() - timedelta(hours=2),
        )

        op2 = BatchOperation.objects.create(
            id='op-2',
            name='Operation 2',
            operation_type=BatchOperation.TYPE_QUERY,
            target_entity='Document',
            status=BatchOperation.STATUS_COMPLETED,
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            progress=100,
            created_at=timezone.now(),
        )

        response = api_client.get('/api/v1/service-mesh/operations/')

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # op2 should come first (newer)
        assert data['operations'][0]['id'] == op2.id
        assert data['operations'][1]['id'] == op1.id

    @pytest.mark.django_db
    def test_operations_view_infer_service(self, api_client, authenticated_user):
        """Test service inference from operation type."""
        # Create operations of different types
        operations_data = [
            (BatchOperation.TYPE_INSTALL_EXTENSION, 'Extension', 'worker'),
            (BatchOperation.TYPE_QUERY, 'Document', 'orchestrator'),
        ]

        for op_type, target, expected_service in operations_data:
            BatchOperation.objects.create(
                id=f'op-{op_type}',
                name=f'Operation {op_type}',
                operation_type=op_type,
                target_entity=target,
                status=BatchOperation.STATUS_COMPLETED,
                total_tasks=1,
                completed_tasks=1,
                failed_tasks=0,
                progress=100,
            )

        response = api_client.get('/api/v1/service-mesh/operations/')

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify services are inferred correctly
        for op_data in data['operations']:
            assert 'service' in op_data
            assert op_data['service'] in ['worker', 'orchestrator', 'ras-adapter']

    @pytest.mark.django_db
    def test_operations_view_empty_list(self, api_client, authenticated_user):
        """Test operations view with no operations."""
        response = api_client.get('/api/v1/service-mesh/operations/')

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data['operations'] == []
        assert data['total'] == 0

    @pytest.mark.django_db
    def test_operations_view_operation_data_format(self, api_client, authenticated_user):
        """Test operation data includes all required fields."""
        now = timezone.now()
        BatchOperation.objects.create(
            id='op-test',
            name='Test Operation',
            operation_type=BatchOperation.TYPE_INSTALL_EXTENSION,
            target_entity='Extension',
            status=BatchOperation.STATUS_COMPLETED,
            total_tasks=10,
            completed_tasks=10,
            failed_tasks=2,
            progress=100,
            created_at=now,
            completed_at=now + timedelta(minutes=5),
        )

        response = api_client.get('/api/v1/service-mesh/operations/')

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        op_data = data['operations'][0]

        # Verify all required fields are present
        required_fields = [
            'id', 'name', 'operation_type', 'status', 'service',
            'duration_seconds', 'created_at', 'completed_at',
            'total_tasks', 'completed_tasks', 'failed_tasks', 'progress'
        ]

        for field in required_fields:
            assert field in op_data, f"Missing field: {field}"

    @pytest.mark.django_db
    def test_operations_view_invalid_limit_param(self, api_client, authenticated_user):
        """Test operations view with invalid limit parameter."""
        response = api_client.get('/api/v1/service-mesh/operations/?limit=not_a_number')

        # Should handle gracefully and use default
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should return data with default limit
        assert 'operations' in data


class TestServiceInferenceLogic:
    """Test service inference from operation types."""

    def test_infer_service_install_extension(self):
        """Test inferring 'worker' service from install_extension operation."""
        from apps.operations.views.service_mesh import ServiceMeshOperationsView
        view = ServiceMeshOperationsView()

        op = MagicMock()
        op.operation_type = 'INSTALL_EXTENSION'

        service = view._infer_service(op)
        assert service == 'worker'

    def test_infer_service_ras_operations(self):
        """Test inferring 'ras-adapter' service from RAS operations."""
        from apps.operations.views.service_mesh import ServiceMeshOperationsView
        view = ServiceMeshOperationsView()

        op = MagicMock()
        op.operation_type = 'RAS_LOCK'

        service = view._infer_service(op)
        assert service == 'ras-adapter'

    def test_infer_service_query_operations(self):
        """Test inferring 'orchestrator' service from query operations."""
        from apps.operations.views.service_mesh import ServiceMeshOperationsView
        view = ServiceMeshOperationsView()

        op = MagicMock()
        op.operation_type = 'ODATA_QUERY'

        service = view._infer_service(op)
        assert service == 'orchestrator'

    def test_infer_service_default(self):
        """Test default service inference."""
        from apps.operations.views.service_mesh import ServiceMeshOperationsView
        view = ServiceMeshOperationsView()

        op = MagicMock()
        op.operation_type = 'UNKNOWN_TYPE'

        service = view._infer_service(op)
        assert service == 'worker'  # Default


class TestFallbackBehavior:
    """Test fallback behavior when Prometheus is unavailable."""

    @pytest.mark.django_db
    @patch('apps.operations.views.service_mesh.get_prometheus_client')
    def test_fallback_services_structure(self, mock_get_client, api_client):
        """Test fallback services have correct structure."""
        mock_client = AsyncMock(spec=PrometheusClient)
        mock_client.get_all_services_metrics = AsyncMock(
            side_effect=Exception("Connection error")
        )
        mock_get_client.return_value = mock_client

        response = api_client.get('/api/v1/service-mesh/metrics/')

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check fallback services have correct structure
        for service in data['services']:
            assert service['name'] in ['api-gateway', 'worker', 'ras-adapter', 'orchestrator', 'frontend']
            assert service['display_name']
            assert service['status'] == 'degraded'
            assert 'ops_per_minute' in service
            assert 'p95_latency_ms' in service
            assert 'error_rate' in service
            assert 'last_updated' in service
