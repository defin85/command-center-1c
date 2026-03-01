import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient
from unittest.mock import AsyncMock, MagicMock, patch

from apps.operations.services.prometheus_client import ServiceMetrics


@pytest.fixture
def authenticated_client():
    client = APIClient()
    user = User.objects.create_user(username="health_user", password="testpass")
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_system_health_uses_direct_fallback_when_prometheus_unavailable(authenticated_client):
    cache.clear()
    fake_fallback_results = [
        {
            "_service_key": "api-gateway",
            "name": "API Gateway",
            "type": "go-service",
            "url": "http://localhost:8180",
            "status": "online",
            "response_time_ms": 12.0,
            "last_check": "2026-01-01T00:00:00+00:00",
            "details": {"source": "direct"},
        },
        {
            "_service_key": "orchestrator",
            "name": "Orchestrator",
            "type": "django",
            "url": "http://localhost:8200",
            "status": "online",
            "response_time_ms": 9.0,
            "last_check": "2026-01-01T00:00:00+00:00",
            "details": {"source": "direct"},
        },
        {
            "_service_key": "frontend",
            "name": "Frontend",
            "type": "frontend",
            "url": "http://localhost:15173/",
            "status": "offline",
            "response_time_ms": None,
            "last_check": "2026-01-01T00:00:00+00:00",
            "details": {"source": "direct"},
        },
    ]

    mock_client = MagicMock()
    mock_client.get_all_services_metrics = AsyncMock(side_effect=RuntimeError("prometheus down"))

    with (
        patch("apps.api_v2.views.system.get_prometheus_client", return_value=mock_client),
        patch(
            "apps.api_v2.views.system.SystemHealthView._build_direct_fallback_results",
            return_value=fake_fallback_results,
        ) as fallback_mock,
    ):
        response = authenticated_client.get("/api/v2/system/health/")

    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] == "critical"
    assert data["statistics"]["total"] == 3
    assert data["statistics"]["offline"] == 1
    fallback_mock.assert_called_once()
    assert all("_service_key" not in service for service in data["services"])


@pytest.mark.django_db
def test_system_health_excludes_disabled_services_from_overall(authenticated_client, settings):
    cache.clear()
    settings.SYSTEM_HEALTH_DISABLED_SERVICES = ("frontend",)

    mock_client = MagicMock()
    mock_client.get_all_services_metrics = AsyncMock(
        return_value=[
            ServiceMetrics(
                name="frontend",
                display_name="Frontend",
                status="critical",
                ops_per_minute=0.0,
                active_operations=0,
                p95_latency_ms=0.0,
                error_rate=0.0,
            ),
            ServiceMetrics(
                name="api-gateway",
                display_name="API Gateway",
                status="healthy",
                ops_per_minute=100.0,
                active_operations=1,
                p95_latency_ms=10.0,
                error_rate=0.0,
            ),
        ]
    )
    mock_client.get_overall_health = AsyncMock(return_value="critical")

    with patch("apps.api_v2.views.system.get_prometheus_client", return_value=mock_client):
        response = authenticated_client.get("/api/v2/system/health/")

    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] == "healthy"
    assert data["statistics"] == {
        "total": 1,
        "online": 1,
        "offline": 0,
        "degraded": 0,
    }

    frontend = next(service for service in data["services"] if service["name"] == "Frontend")
    assert frontend["status"] == "degraded"
    assert frontend["details"]["disabled"] is True
