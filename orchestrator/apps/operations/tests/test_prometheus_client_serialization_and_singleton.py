"""Additional tests for Prometheus client helpers."""

from datetime import datetime

from apps.operations.services.prometheus_client import ServiceMetrics, get_prometheus_client


class TestServiceMetricsSerialization:
    """Test ServiceMetrics dataclass serialization."""

    def test_service_metrics_to_dict(self):
        now = datetime.utcnow()
        metrics = ServiceMetrics(
            name="api-gateway",
            display_name="API Gateway",
            status="healthy",
            ops_per_minute=123.456,
            active_operations=42,
            p95_latency_ms=500.789,
            error_rate=0.0012345,
            last_updated=now,
        )

        data = metrics.to_dict()

        assert data["name"] == "api-gateway"
        assert data["display_name"] == "API Gateway"
        assert data["status"] == "healthy"
        assert data["availability_status"] == "available"
        assert data["ops_per_minute"] == 123.46
        assert data["active_operations"] == 42
        assert data["p95_latency_ms"] == 500.79
        assert data["error_rate"] == 0.0012
        assert "last_updated" in data


class TestGetPrometheusClientSingleton:
    """Test Prometheus client singleton factory."""

    def test_get_prometheus_client_returns_singleton(self):
        import apps.operations.services.prometheus_client as prom_module

        prom_module._prometheus_client = None

        client1 = get_prometheus_client()
        client2 = get_prometheus_client()

        assert client1 is client2

    def test_get_prometheus_client_multiple_calls(self):
        import apps.operations.services.prometheus_client as prom_module

        prom_module._prometheus_client = None

        clients = [get_prometheus_client() for _ in range(5)]
        assert len(set(id(c) for c in clients)) == 1
