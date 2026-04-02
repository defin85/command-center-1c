"""
Unit tests for Service Mesh API v2 endpoints.

Tests:
- GET /api/v2/service-mesh/get-metrics/ - Get service mesh metrics
- GET /api/v2/service-mesh/get-history/?service=api-gateway - Get historical metrics
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.operations.services.prometheus_client import ServiceMetrics


@pytest.fixture
def authenticated_client():
    """Provide authenticated API client."""
    client = APIClient()
    user = User.objects.create_user(username='testuser', password='testpass')
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def mock_prometheus_client():
    """Mock Prometheus client used by service mesh endpoints."""
    with patch("apps.api_v2.views.service_mesh.get_prometheus_client") as mock:
        client = MagicMock()
        client.get_all_services_metrics = AsyncMock(return_value=[
            ServiceMetrics(
                name="api-gateway",
                display_name="API Gateway",
                status="healthy",
                ops_per_minute=120.0,
                active_operations=1,
                p95_latency_ms=50.0,
                error_rate=0.0,
            )
        ])
        mock.return_value = client
        yield mock


class TestServiceMeshGetMetrics:
    """Test GET /api/v2/service-mesh/get-metrics/ endpoint."""

    @pytest.mark.django_db
    def test_get_metrics_requires_authentication(self, client):
        """Test endpoint requires authentication."""
        response = client.get('/api/v2/service-mesh/get-metrics/')
        assert response.status_code in [401, 403]

    @pytest.mark.django_db
    def test_get_metrics_success(self, authenticated_client, mock_prometheus_client):
        """Test successful metrics retrieval."""
        response = authenticated_client.get('/api/v2/service-mesh/get-metrics/')
        assert response.status_code == 200

        data = response.json()
        assert 'status' in data
        assert 'services' in data
        assert 'summary' in data
        assert 'timestamp' in data
        assert data['status'] in ['healthy', 'degraded', 'unhealthy']

    @pytest.mark.django_db
    def test_get_metrics_maps_critical_but_available_service_to_degraded(self, authenticated_client):
        mock_client = MagicMock()
        mock_client.get_all_services_metrics = AsyncMock(return_value=[
            ServiceMetrics(
                name="worker-workflows",
                display_name="Worker Workflows",
                status="critical",
                availability_status="available",
                ops_per_minute=12.0,
                active_operations=1,
                p95_latency_ms=850.0,
                error_rate=1.0,
            )
        ])

        with patch("apps.api_v2.views.service_mesh.get_prometheus_client", return_value=mock_client):
            response = authenticated_client.get('/api/v2/service-mesh/get-metrics/')

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["summary"] == {
            "total": 1,
            "healthy": 0,
            "degraded": 1,
            "unreachable": 0,
            "error": 0,
        }
        service = data["services"][0]
        assert service["status"] == "degraded"
        assert service["details"]["severity"] == "critical"
        assert service["details"]["availability_status"] == "available"

    @pytest.mark.django_db
    def test_get_metrics_maps_unavailable_service_to_unreachable(self, authenticated_client):
        mock_client = MagicMock()
        mock_client.get_all_services_metrics = AsyncMock(return_value=[
            ServiceMetrics(
                name="worker-workflows",
                display_name="Worker Workflows",
                status="critical",
                availability_status="unavailable",
                ops_per_minute=0.0,
                active_operations=0,
                p95_latency_ms=0.0,
                error_rate=0.0,
            )
        ])

        with patch("apps.api_v2.views.service_mesh.get_prometheus_client", return_value=mock_client):
            response = authenticated_client.get('/api/v2/service-mesh/get-metrics/')

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["summary"] == {
            "total": 1,
            "healthy": 0,
            "degraded": 0,
            "unreachable": 1,
            "error": 0,
        }
        service = data["services"][0]
        assert service["status"] == "unreachable"
        assert service["details"]["severity"] == "critical"
        assert service["details"]["availability_status"] == "unavailable"


class TestServiceMeshGetHistory:
    """Test GET /api/v2/service-mesh/get-history/ endpoint."""

    @pytest.mark.django_db
    def test_get_history_requires_authentication(self, client):
        """Test endpoint requires authentication."""
        response = client.get('/api/v2/service-mesh/get-history/?service=api-gateway')
        assert response.status_code in [401, 403]

    @pytest.mark.django_db
    def test_get_history_requires_service_parameter(self, authenticated_client):
        """Test endpoint requires service parameter."""
        response = authenticated_client.get('/api/v2/service-mesh/get-history/')
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
        assert data['error']['code'] == 'MISSING_PARAMETER'

    @pytest.mark.django_db
    def test_get_history_with_valid_service(self, authenticated_client):
        """Test historical metrics with valid service."""
        with patch('apps.operations.services.prometheus_client.get_prometheus_client') as mock_client:
            # Mock Prometheus client to return empty data
            mock_instance = MagicMock()
            mock_instance.get_historical_metrics.return_value = []
            mock_client.return_value = mock_instance

            response = authenticated_client.get('/api/v2/service-mesh/get-history/?service=api-gateway')
            assert response.status_code == 200

            data = response.json()
            assert data['service'] == 'api-gateway'
            assert 'display_name' in data
            assert data['minutes'] == 30  # Default value
            assert 'data_points' in data
            assert isinstance(data['data_points'], list)

    @pytest.mark.django_db
    def test_get_history_invalid_service(self, authenticated_client):
        """Test history with invalid service name."""
        response = authenticated_client.get('/api/v2/service-mesh/get-history/?service=nonexistent')
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
        assert data['error']['code'] == 'UNKNOWN_SERVICE'

    @pytest.mark.django_db
    def test_get_history_with_custom_minutes(self, authenticated_client):
        """Test historical metrics with custom time range."""
        with patch('apps.operations.services.prometheus_client.get_prometheus_client') as mock_client:
            mock_instance = MagicMock()
            mock_instance.get_historical_metrics.return_value = []
            mock_client.return_value = mock_instance

            response = authenticated_client.get('/api/v2/service-mesh/get-history/?service=api-gateway&minutes=60')
            assert response.status_code == 200

            data = response.json()
            assert data['minutes'] == 60
