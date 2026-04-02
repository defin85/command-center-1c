"""
Unit tests for PrometheusClient and Service Mesh metrics.

Tests:
- Prometheus HTTP client initialization and queries
- Service metrics aggregation
- Health status calculation
- Graceful degradation on Prometheus unavailability
- Historical metrics queries
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import httpx

from apps.operations.services.prometheus_client import (
    PrometheusClient,
    ServiceMetrics,
    ServiceConnection,
    SERVICE_CONFIG,
    SERVICE_TOPOLOGY,
)


class TestPrometheusClientInitialization:
    """Test PrometheusClient initialization and HTTP client management."""

    def test_client_initialization_with_default_url(self):
        """Test client initializes with default Prometheus URL."""
        client = PrometheusClient()
        assert client.base_url == 'http://localhost:9090'

    def test_client_initialization_with_custom_url(self):
        """Test client initializes with custom Prometheus URL."""
        custom_url = 'http://prometheus.example.com:9090'
        client = PrometheusClient(base_url=custom_url)
        assert client.base_url == custom_url

    def test_client_initialization_with_settings(self):
        """Test client reads PROMETHEUS_URL from Django settings."""
        with patch('apps.operations.services.prometheus_client.settings') as mock_settings:
            mock_settings.PROMETHEUS_URL = 'http://settings.prometheus:9090'
            client = PrometheusClient()
            assert client.base_url == 'http://settings.prometheus:9090'

    @pytest.mark.asyncio
    async def test_http_client_lazy_initialization(self):
        """Test HTTP client is created lazily on first use."""
        client = PrometheusClient()
        assert client._client is None

        # First call should create the client
        with patch('httpx.AsyncClient') as mock_async_client_class:
            mock_async_client = AsyncMock()
            mock_async_client_class.return_value = mock_async_client

            http_client = await client._get_client()
            assert http_client is not None
            mock_async_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_http_client_reuse(self):
        """Test HTTP client is reused on subsequent calls."""
        client = PrometheusClient()

        with patch('httpx.AsyncClient') as mock_async_client_class:
            mock_async_client = AsyncMock()
            mock_async_client.is_closed = False
            mock_async_client_class.return_value = mock_async_client

            # First call
            http_client1 = await client._get_client()
            # Second call
            http_client2 = await client._get_client()

            # Should be the same instance
            assert http_client1 is http_client2
            # Should only create once
            mock_async_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_http_client_recreation_when_closed(self):
        """Test HTTP client is recreated when it's closed."""
        client = PrometheusClient()

        with patch('httpx.AsyncClient') as mock_async_client_class:
            mock_client1 = AsyncMock()
            mock_client1.is_closed = False
            mock_client2 = AsyncMock()
            mock_client2.is_closed = False

            mock_async_client_class.side_effect = [mock_client1, mock_client2]

            # First call
            client1 = await client._get_client()
            # Mark as closed
            client1.is_closed = True
            # Second call should create a new one
            client2 = await client._get_client()

            assert client1 is not client2
            assert mock_async_client_class.call_count == 2

    @pytest.mark.asyncio
    async def test_client_close(self):
        """Test client cleanup."""
        client = PrometheusClient()

        with patch('httpx.AsyncClient') as mock_async_client_class:
            mock_async_client = AsyncMock()
            mock_async_client.is_closed = False
            mock_async_client_class.return_value = mock_async_client

            # Create client
            await client._get_client()
            # Close it
            await client.close()

            mock_async_client.aclose.assert_called_once()
            assert client._client is None


class TestPrometheusQuery:
    """Test Prometheus query execution."""

    @pytest.mark.asyncio
    async def test_query_success(self):
        """Test successful instant query."""
        expected_response = {
            'status': 'success',
            'data': {
                'resultType': 'vector',
                'result': [
                    {'metric': {'job': 'api_gateway'}, 'value': ['1234567890', '42.5']}
                ]
            }
        }

        mock_response = AsyncMock()
        mock_response.json = MagicMock(return_value=expected_response)

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.is_closed = False

        with patch('apps.operations.services.prometheus_client.httpx.AsyncClient') as mock_client_class:
            mock_client_class.return_value = mock_http_client

            client = PrometheusClient()
            result = await client.query('up{job="api_gateway"}')

            assert result == expected_response
            mock_http_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_http_error(self):
        """Test query handles HTTP errors gracefully."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock(side_effect=httpx.HTTPError("Connection failed"))

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.is_closed = False

        with patch('apps.operations.services.prometheus_client.httpx.AsyncClient') as mock_client_class:
            mock_client_class.return_value = mock_http_client

            client = PrometheusClient()
            result = await client.query('invalid_query')

            assert result['status'] == 'error'
            assert result['data']['result'] == []

    @pytest.mark.asyncio
    async def test_query_unexpected_error(self):
        """Test query handles unexpected errors gracefully."""
        client = PrometheusClient()

        with patch.object(client, '_get_client') as mock_get_client:
            mock_get_client.side_effect = RuntimeError("Unexpected error")

            result = await client.query('some_query')

            assert result['status'] == 'error'
            assert result['data']['result'] == []

    @pytest.mark.asyncio
    async def test_query_range_success(self):
        """Test successful range query."""
        expected_response = {
            'status': 'success',
            'data': {
                'resultType': 'matrix',
                'result': [
                    {
                        'metric': {'job': 'api_gateway'},
                        'values': [
                            ['1234567890', '42.5'],
                            ['1234567920', '43.2']
                        ]
                    }
                ]
            }
        }

        mock_response = AsyncMock()
        mock_response.json = MagicMock(return_value=expected_response)

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.is_closed = False

        with patch('apps.operations.services.prometheus_client.httpx.AsyncClient') as mock_client_class:
            mock_client_class.return_value = mock_http_client

            client = PrometheusClient()
            start = datetime.utcnow() - timedelta(minutes=5)
            end = datetime.utcnow()

            result = await client.query_range('rate(cc1c_requests_total[1m])', start, end)

            assert result == expected_response
            mock_http_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_range_http_error(self):
        """Test range query handles HTTP errors gracefully."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock(side_effect=httpx.HTTPError("Timeout"))

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.is_closed = False

        with patch('apps.operations.services.prometheus_client.httpx.AsyncClient') as mock_client_class:
            mock_client_class.return_value = mock_http_client

            client = PrometheusClient()
            start = datetime.utcnow() - timedelta(hours=1)
            end = datetime.utcnow()

            result = await client.query_range('some_metric', start, end)

            assert result['status'] == 'error'
            assert result['data']['result'] == []


class TestValueExtraction:
    """Test Prometheus result value extraction."""

    @pytest.fixture
    def client(self):
        """Provide PrometheusClient instance."""
        return PrometheusClient()

    def test_extract_value_from_valid_result(self, client):
        """Test extracting value from valid Prometheus result."""
        result = {
            'data': {
                'result': [
                    {'value': ['1234567890', '42.5']}
                ]
            }
        }
        value = client._extract_value(result)
        assert value == 42.5

    def test_extract_value_with_default(self, client):
        """Test default value when result is empty."""
        result = {'data': {'result': []}}
        value = client._extract_value(result, default=10.0)
        assert value == 10.0

    def test_extract_value_with_nan(self, client):
        """Test handling NaN values."""
        result = {
            'data': {
                'result': [
                    {'value': ['1234567890', 'NaN']}
                ]
            }
        }
        value = client._extract_value(result)
        # Should not raise, just return NaN which can be checked later
        assert str(value).lower() in ['nan', 'inf', '-inf'] or value == float('nan')

    def test_extract_value_with_malformed_result(self, client):
        """Test handling malformed result."""
        result = {'data': {}}  # Missing 'result' key
        value = client._extract_value(result)
        assert value == 0.0

    def test_extract_value_with_invalid_value_type(self, client):
        """Test handling invalid value type."""
        result = {
            'data': {
                'result': [
                    {'value': 'not_a_list'}
                ]
            }
        }
        value = client._extract_value(result)
        assert value == 0.0


class TestHealthStatus:
    """Test health status determination."""

    @pytest.fixture
    def client(self):
        """Provide PrometheusClient instance."""
        return PrometheusClient()

    def test_healthy_status(self, client):
        """Test service is marked as healthy."""
        status = client._determine_status(
            error_rate=0.001,  # < 1%
            p95_latency_ms=500,  # < 1000ms
            ops_per_minute=100,
        )
        assert status == 'healthy'

    def test_degraded_status_high_error_rate(self, client):
        """Test service is degraded with high error rate."""
        status = client._determine_status(
            error_rate=0.05,  # 5% - between 1% and 10%
            p95_latency_ms=500,
            ops_per_minute=100,
        )
        assert status == 'degraded'

    def test_degraded_status_high_latency(self, client):
        """Test service is degraded with high latency."""
        status = client._determine_status(
            error_rate=0.001,
            p95_latency_ms=2000,  # Between 1000 and 5000
            ops_per_minute=100,
        )
        assert status == 'degraded'

    def test_critical_status_very_high_error(self, client):
        """Test service is critical with very high error rate."""
        status = client._determine_status(
            error_rate=0.15,  # > 10%
            p95_latency_ms=500,
            ops_per_minute=100,
        )
        assert status == 'critical'

    def test_critical_status_very_high_latency(self, client):
        """Test service is critical with very high latency."""
        status = client._determine_status(
            error_rate=0.001,
            p95_latency_ms=6000,  # > 5000ms
            ops_per_minute=100,
        )
        assert status == 'critical'

    def test_custom_thresholds_for_tasks(self, client):
        """Test custom thresholds (e.g., worker task p95) don't mark long tasks as critical."""
        status = client._determine_status(
            error_rate=0.0,
            p95_latency_ms=30_000,  # 30s
            ops_per_minute=1,
            thresholds={
                'critical_p95_ms': 60_000,
                'degraded_p95_ms': 15_000,
                'critical_error_rate': 0.10,
                'degraded_error_rate': 0.01,
            }
        )
        assert status == 'degraded'


class TestServiceMetrics:
    """Test service metrics aggregation."""

    @pytest.fixture
    def client(self):
        """Provide PrometheusClient instance."""
        return PrometheusClient()

    @pytest.mark.asyncio
    async def test_get_service_metrics_success(self, client):
        """Test successful service metrics retrieval."""
        # Mock the query method
        with patch.object(client, 'query') as mock_query:
            mock_query.side_effect = [
                # ops query
                {'data': {'result': [{'value': ['1234567890', '150']}]}},
                # latency query
                {'data': {'result': [{'value': ['1234567890', '500']}]}},
                # error query
                {'data': {'result': [{'value': ['1234567890', '0.005']}]}},
                # active query
                {'data': {'result': [{'value': ['1234567890', '3']}]}}
            ]

            with patch.object(client, '_execute_queries', new_callable=AsyncMock) as mock_execute:
                mock_execute.return_value = [
                    {'data': {'result': [{'value': ['1234567890', '150']}]}},
                    {'data': {'result': [{'value': ['1234567890', '500']}]}},
                    {'data': {'result': [{'value': ['1234567890', '0.005']}]}},
                    {'data': {'result': [{'value': ['1234567890', '3']}]}},
                    {'data': {'result': [{'value': ['1234567890', '1']}]}}
                ]

                metrics = await client.get_service_metrics('api-gateway')

                assert metrics.name == 'api-gateway'
                assert metrics.display_name == 'API Gateway'
                assert metrics.status == 'healthy'
                assert metrics.availability_status == 'available'
                assert metrics.ops_per_minute == 150.0
                assert metrics.p95_latency_ms == 500.0
                assert metrics.error_rate == 0.005
                assert metrics.active_operations == 3

    @pytest.mark.asyncio
    async def test_get_service_metrics_degraded(self, client):
        """Test service metrics with degraded status."""
        with patch.object(client, '_execute_queries', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = [
                # High ops/min
                {'data': {'result': [{'value': ['1234567890', '5000']}]}},
                # High latency (degraded)
                {'data': {'result': [{'value': ['1234567890', '1500']}]}},
                # Moderate error rate
                {'data': {'result': [{'value': ['1234567890', '0.02']}]}},
                # Low active operations
                {'data': {'result': []}},
                {'data': {'result': [{'value': ['1234567890', '1']}]}}
            ]

            metrics = await client.get_service_metrics('worker')

            assert metrics.status == 'degraded'
            assert metrics.availability_status == 'available'
            assert metrics.p95_latency_ms == 1500.0

    @pytest.mark.asyncio
    async def test_get_service_metrics_critical_but_available(self, client):
        """Test severe metrics do not imply service unavailability."""
        with patch.object(client, '_execute_queries', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = [
                {'data': {'result': [{'value': ['1234567890', '5000']}]}},
                {'data': {'result': [{'value': ['1234567890', '1500']}]}},
                {'data': {'result': [{'value': ['1234567890', '0.15']}]}},
                {'data': {'result': []}},
                {'data': {'result': [{'value': ['1234567890', '1']}]}}
            ]

            metrics = await client.get_service_metrics('worker-workflows')

            assert metrics.status == 'critical'
            assert metrics.availability_status == 'available'

    @pytest.mark.asyncio
    async def test_get_service_metrics_marks_missing_up_as_unavailable(self, client):
        """Test down targets are the only source of unavailable status."""
        with patch.object(client, '_execute_queries', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = [
                {'data': {'result': [{'value': ['1234567890', '10']}]}},
                {'data': {'result': [{'value': ['1234567890', '500']}]}},
                {'data': {'result': [{'value': ['1234567890', '0.0']}]}},
                {'data': {'result': []}},
                {'data': {'result': [{'value': ['1234567890', '0']}]}}
            ]

            metrics = await client.get_service_metrics('worker')

            assert metrics.status == 'critical'
            assert metrics.availability_status == 'unavailable'

    @pytest.mark.asyncio
    async def test_get_service_metrics_nan_handling(self, client):
        """Test NaN value handling in metrics."""
        with patch.object(client, '_execute_queries', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = [
                # NaN latency
                {'data': {'result': [{'value': ['1234567890', 'NaN']}]}},
                {'data': {'result': [{'value': ['1234567890', 'NaN']}]}},
                {'data': {'result': [{'value': ['1234567890', 'NaN']}]}},
                {'data': {'result': []}},
                {'data': {'result': [{'value': ['1234567890', '1']}]}}
            ]

            metrics = await client.get_service_metrics('worker')

            # Should convert NaN to 0
            assert metrics.p95_latency_ms == 0.0
            assert metrics.error_rate == 0.0

    @pytest.mark.asyncio
    async def test_get_service_metrics_pool_outbox_dispatcher_healthy(self, client):
        """Test pool outbox dispatcher service health calculation."""
        with patch.object(client, '_execute_queries', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = [
                {'data': {'result': [{'value': ['1234567890', '1']}]}},    # up
                {'data': {'result': [{'value': ['1234567890', '2']}]}},    # heartbeat age
                {'data': {'result': [{'value': ['1234567890', '0']}]}},    # pending
                {'data': {'result': [{'value': ['1234567890', '0']}]}},    # lag
                {'data': {'result': [{'value': ['1234567890', '0']}]}},    # saturated
                {'data': {'result': [{'value': ['1234567890', '3']}]}},    # dispatched
                {'data': {'result': [{'value': ['1234567890', '0']}]}},    # failed
            ]

            metrics = await client.get_service_metrics('pool-outbox-dispatcher')

            assert metrics.status == 'healthy'
            assert metrics.availability_status == 'available'
            assert metrics.ops_per_minute == 3.0
            assert metrics.active_operations == 0
            assert metrics.error_rate == 0.0

    @pytest.mark.asyncio
    async def test_get_service_metrics_pool_outbox_dispatcher_critical_but_available_on_lag(self, client):
        """Test severe dispatcher lag does not imply service unreachability."""
        with patch.object(client, '_execute_queries', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = [
                {'data': {'result': [{'value': ['1234567890', '1']}]}},    # up
                {'data': {'result': [{'value': ['1234567890', '120']}]}},  # heartbeat age
                {'data': {'result': [{'value': ['1234567890', '4']}]}},    # pending
                {'data': {'result': [{'value': ['1234567890', '400']}]}},  # lag
                {'data': {'result': [{'value': ['1234567890', '0']}]}},    # saturated
                {'data': {'result': [{'value': ['1234567890', '0']}]}},    # dispatched
                {'data': {'result': [{'value': ['1234567890', '0']}]}},    # failed
            ]

            metrics = await client.get_service_metrics('pool-outbox-dispatcher')

            assert metrics.status == 'critical'
            assert metrics.availability_status == 'available'

    @pytest.mark.asyncio
    async def test_get_service_metrics_pool_outbox_dispatcher_critical_when_down(self, client):
        """Test pool outbox dispatcher is critical when heartbeat is down."""
        with patch.object(client, '_execute_queries', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = [
                {'data': {'result': [{'value': ['1234567890', '0']}]}},    # up
                {'data': {'result': [{'value': ['1234567890', '120']}]}},  # heartbeat age
                {'data': {'result': [{'value': ['1234567890', '4']}]}},    # pending
                {'data': {'result': [{'value': ['1234567890', '40']}]}},   # lag
                {'data': {'result': [{'value': ['1234567890', '0']}]}},    # saturated
                {'data': {'result': [{'value': ['1234567890', '0']}]}},    # dispatched
                {'data': {'result': [{'value': ['1234567890', '0']}]}},    # failed
            ]

            metrics = await client.get_service_metrics('pool-outbox-dispatcher')

            assert metrics.status == 'critical'
            assert metrics.availability_status == 'unavailable'
            assert metrics.active_operations == 4

    @pytest.mark.asyncio
    async def test_get_all_services_metrics(self, client):
        """Test retrieving metrics for all configured services."""
        with patch.object(client, 'get_service_metrics', new_callable=AsyncMock) as mock_get:
            # Create mock metrics for each service
            def create_metrics(service):
                return ServiceMetrics(
                    name=service,
                    display_name=SERVICE_CONFIG[service]['display_name'],
                    status='healthy',
                    ops_per_minute=100,
                    active_operations=5,
                    p95_latency_ms=100,
                    error_rate=0.001,
                )

            mock_get.side_effect = [create_metrics(s) for s in SERVICE_CONFIG.keys()]

            all_metrics = await client.get_all_services_metrics()

            assert len(all_metrics) == len(SERVICE_CONFIG)
            assert all(m.status == 'healthy' for m in all_metrics)

    @pytest.mark.asyncio
    async def test_get_all_services_metrics_with_errors(self, client):
        """Test get_all_services_metrics handles individual service errors gracefully."""
        with patch.object(client, 'get_service_metrics', new_callable=AsyncMock) as mock_get:
            # First call succeeds, second raises error
            mock_get.side_effect = [
                ServiceMetrics(
                    name='api-gateway',
                    display_name='API Gateway',
                    status='healthy',
                ),
                Exception("Prometheus error"),
            ]

            all_metrics = await client.get_all_services_metrics()

            # Should include metrics for first service and degraded fallback for second
            assert len(all_metrics) == len(SERVICE_CONFIG)
            assert any(m.status == 'degraded' for m in all_metrics)


class TestServiceConnections:
    """Test service-to-service connections."""

    @pytest.fixture
    def client(self):
        """Provide PrometheusClient instance."""
        return PrometheusClient()

    @pytest.mark.asyncio
    async def test_get_service_connections(self, client):
        """Test retrieving service connections."""
        with patch.object(client, 'query', new_callable=AsyncMock) as mock_query:
            # SERVICE_TOPOLOGY connections, each needs 2 queries (rpm + latency)
            def _vector_result(value: float):
                return {'data': {'result': [{'value': ['1234567890', str(value)]}]}}

            responses = []
            for idx, _connection in enumerate(SERVICE_TOPOLOGY):
                rpm = 500.0 if idx == 0 else float(100 + idx)
                latency = 100.0 if idx == 0 else float(10 + idx)
                responses.extend([_vector_result(rpm), _vector_result(latency)])
            mock_query.side_effect = responses

            connections = await client.get_service_connections()

            # Should have connections for each pair in SERVICE_TOPOLOGY
            assert len(connections) == len(SERVICE_TOPOLOGY)
            assert all(isinstance(c, ServiceConnection) for c in connections)
            # Verify some connections have expected values
            assert connections[0].requests_per_minute == 500.0
            assert connections[0].avg_latency_ms == 100.0

    @pytest.mark.asyncio
    async def test_service_connection_to_dict(self):
        """Test ServiceConnection serialization."""
        connection = ServiceConnection(
            source='api-gateway',
            target='orchestrator',
            requests_per_minute=500.5555,
            avg_latency_ms=100.1234,
        )

        data = connection.to_dict()

        assert data['source'] == 'api-gateway'
        assert data['target'] == 'orchestrator'
        assert data['requests_per_minute'] == 500.56  # Rounded
        assert data['avg_latency_ms'] == 100.12  # Rounded


class TestHistoricalMetrics:
    """Test historical metrics retrieval."""

    @pytest.fixture
    def client(self):
        """Provide PrometheusClient instance."""
        return PrometheusClient()

    @pytest.mark.asyncio
    async def test_get_historical_metrics_30_minutes(self, client):
        """Test retrieving 30 minutes of historical data."""
        # Create timestamps that are integers (Unix epoch)
        base_time = int(datetime.utcnow().timestamp())
        mock_range_result = {
            'data': {
                'result': [
                    {
                        'metric': {'job': 'api_gateway'},
                        'values': [
                            [base_time, '100'],
                            [base_time + 30, '110'],
                            [base_time + 60, '105'],
                        ]
                    }
                ]
            }
        }

        with patch.object(client, 'query_range', new_callable=AsyncMock) as mock_qr:
            mock_qr.return_value = mock_range_result

            data_points = await client.get_historical_metrics('api-gateway', minutes=30)

            # Should return data points with timestamps and metrics
            assert len(data_points) == 3
            for point in data_points:
                assert 'timestamp' in point
                assert 'ops_per_minute' in point
                assert 'p95_latency_ms' in point
                assert 'error_rate' in point

    @pytest.mark.asyncio
    async def test_get_historical_metrics_step_selection(self, client):
        """Test correct step selection based on time range."""
        with patch.object(client, 'query_range', new_callable=AsyncMock) as mock_qr:
            mock_qr.return_value = {'data': {'result': []}}

            # 30 minutes - should use 30s step
            await client.get_historical_metrics('api-gateway', minutes=30)
            call_args = mock_qr.call_args
            assert '30s' in str(call_args)

            # 60 minutes - should use 1m step
            await client.get_historical_metrics('api-gateway', minutes=60)
            call_args = mock_qr.call_args
            assert '1m' in str(call_args)

            # 120 minutes - should use 2m step
            await client.get_historical_metrics('api-gateway', minutes=120)
            call_args = mock_qr.call_args
            assert '2m' in str(call_args)


class TestOverallHealth:
    """Test overall system health calculation."""

    @pytest.fixture
    def client(self):
        """Provide PrometheusClient instance."""
        return PrometheusClient()

    @pytest.mark.asyncio
    async def test_overall_health_all_healthy(self, client):
        """Test overall health when all services are healthy."""
        metrics = [
            ServiceMetrics('api-gateway', 'API Gateway', 'healthy'),
            ServiceMetrics('worker', 'Worker', 'healthy'),
            ServiceMetrics('orchestrator', 'Orchestrator', 'healthy'),
        ]

        health = await client.get_overall_health(metrics)
        assert health == 'healthy'

    @pytest.mark.asyncio
    async def test_overall_health_some_degraded(self, client):
        """Test overall health when some services are degraded."""
        metrics = [
            ServiceMetrics('api-gateway', 'API Gateway', 'healthy'),
            ServiceMetrics('worker', 'Worker', 'degraded'),
            ServiceMetrics('orchestrator', 'Orchestrator', 'healthy'),
        ]

        health = await client.get_overall_health(metrics)
        assert health == 'degraded'

    @pytest.mark.asyncio
    async def test_overall_health_any_critical(self, client):
        """Test overall health when any service is critical."""
        metrics = [
            ServiceMetrics('api-gateway', 'API Gateway', 'healthy'),
            ServiceMetrics('worker', 'Worker', 'critical'),
            ServiceMetrics('orchestrator', 'Orchestrator', 'degraded'),
        ]

        health = await client.get_overall_health(metrics)
        assert health == 'critical'

    @pytest.mark.asyncio
    async def test_overall_health_empty_metrics(self, client):
        """Test overall health with empty metrics list."""
        health = await client.get_overall_health([])
        assert health == 'critical'
