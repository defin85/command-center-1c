"""
Prometheus client for fetching service mesh metrics.

Provides real-time and historical metrics for:
- API Gateway, Worker, RAS Adapter, Orchestrator services
- Request rates, latencies, error rates
- Active workers and queue depths
"""
import httpx
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class ServiceMetrics:
    """Aggregated metrics for a single service."""
    name: str
    display_name: str
    status: str  # 'healthy', 'degraded', 'critical'
    ops_per_minute: float = 0.0
    active_operations: int = 0
    p95_latency_ms: float = 0.0
    error_rate: float = 0.0  # 0.0 - 1.0
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'display_name': self.display_name,
            'status': self.status,
            'ops_per_minute': round(self.ops_per_minute, 2),
            'active_operations': self.active_operations,
            'p95_latency_ms': round(self.p95_latency_ms, 2),
            'error_rate': round(self.error_rate, 4),
            'last_updated': self.last_updated.isoformat(),
        }


@dataclass
class ServiceConnection:
    """Connection between two services with traffic metrics."""
    source: str
    target: str
    requests_per_minute: float = 0.0
    avg_latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'source': self.source,
            'target': self.target,
            'requests_per_minute': round(self.requests_per_minute, 2),
            'avg_latency_ms': round(self.avg_latency_ms, 2),
        }


# Service configuration mapping
SERVICE_CONFIG = {
    'api-gateway': {
        'display_name': 'API Gateway',
        'job_patterns': ['api_gateway', 'api-gateway', 'apigateway'],
        'namespace': 'cc1c',
    },
    'worker': {
        'display_name': 'Worker',
        'job_patterns': ['worker', 'go_worker'],
        'namespace': 'cc1c',
    },
    'ras-adapter': {
        'display_name': 'RAS Adapter',
        'job_patterns': ['ras_adapter', 'ras-adapter', 'rasadapter'],
        'namespace': 'cc1c',
    },
    'orchestrator': {
        'display_name': 'Orchestrator',
        'job_patterns': ['orchestrator', 'django'],
        'namespace': 'orchestrator',
    },
    'frontend': {
        'display_name': 'Frontend',
        'job_patterns': ['frontend', 'react'],
        'namespace': 'frontend',
    },
}

# Service mesh topology (connections between services)
SERVICE_TOPOLOGY = [
    ('frontend', 'api-gateway'),
    ('api-gateway', 'orchestrator'),
    ('api-gateway', 'worker'),
    ('api-gateway', 'ras-adapter'),
    ('orchestrator', 'worker'),
    ('worker', 'ras-adapter'),
]


class PrometheusClient:
    """
    Client for querying Prometheus metrics.

    Provides methods for:
    - Instant queries (current values)
    - Range queries (historical data)
    - Service-specific aggregated metrics
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or getattr(
            settings, 'PROMETHEUS_URL', 'http://localhost:9090'
        )
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=10.0,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def query(self, promql: str) -> Dict[str, Any]:
        """
        Execute instant PromQL query.

        Args:
            promql: PromQL query string

        Returns:
            Prometheus API response dict
        """
        try:
            client = await self._get_client()
            response = await client.get(
                '/api/v1/query',
                params={'query': promql}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Prometheus query failed: {e}")
            return {'status': 'error', 'error': str(e), 'data': {'result': []}}
        except Exception as e:
            logger.error(f"Unexpected error in Prometheus query: {e}")
            return {'status': 'error', 'error': str(e), 'data': {'result': []}}

    async def query_range(
        self,
        promql: str,
        start: datetime,
        end: datetime,
        step: str = "30s"
    ) -> Dict[str, Any]:
        """
        Execute range PromQL query for historical data.

        Args:
            promql: PromQL query string
            start: Start time
            end: End time
            step: Query resolution (e.g., "30s", "1m", "5m")

        Returns:
            Prometheus API response dict with time series data
        """
        try:
            client = await self._get_client()
            response = await client.get(
                '/api/v1/query_range',
                params={
                    'query': promql,
                    'start': start.timestamp(),
                    'end': end.timestamp(),
                    'step': step,
                }
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Prometheus range query failed: {e}")
            return {'status': 'error', 'error': str(e), 'data': {'result': []}}
        except Exception as e:
            logger.error(f"Unexpected error in Prometheus range query: {e}")
            return {'status': 'error', 'error': str(e), 'data': {'result': []}}

    def _extract_value(self, result: Dict[str, Any], default: float = 0.0) -> float:
        """Extract scalar value from Prometheus result."""
        try:
            data = result.get('data', {}).get('result', [])
            if data and len(data) > 0:
                value = data[0].get('value', [0, '0'])
                if len(value) >= 2:
                    return float(value[1])
        except (ValueError, TypeError, IndexError) as e:
            logger.debug(f"Error extracting Prometheus value: {e}")
        return default

    def _determine_status(
        self,
        error_rate: float,
        p95_latency_ms: float,
        ops_per_minute: float
    ) -> str:
        """
        Determine service health status based on metrics.

        Thresholds:
        - critical: error_rate > 10% OR p95 > 5000ms
        - degraded: error_rate > 1% OR p95 > 1000ms
        - healthy: otherwise
        """
        if error_rate > 0.10 or p95_latency_ms > 5000:
            return 'critical'
        elif error_rate > 0.01 or p95_latency_ms > 1000:
            return 'degraded'
        else:
            return 'healthy'

    async def get_service_metrics(self, service: str) -> ServiceMetrics:
        """
        Get aggregated metrics for a specific service.

        Args:
            service: Service name (e.g., 'api-gateway', 'worker')

        Returns:
            ServiceMetrics dataclass with current metrics
        """
        config = SERVICE_CONFIG.get(service, {})
        display_name = config.get('display_name', service.title())
        namespace = config.get('namespace', 'cc1c')
        job_patterns = config.get('job_patterns', [service])

        # Build job filter for PromQL
        job_filter = '|'.join(job_patterns)

        # Queries for different metrics
        ops_query = f'sum(rate({namespace}_requests_total{{job=~"{job_filter}"}}[5m])) * 60'
        latency_query = f'histogram_quantile(0.95, sum(rate({namespace}_request_duration_seconds_bucket{{job=~"{job_filter}"}}[5m])) by (le)) * 1000'
        error_query = f'sum(rate({namespace}_requests_total{{job=~"{job_filter}",status=~"5.."}}[5m])) / sum(rate({namespace}_requests_total{{job=~"{job_filter}"}}[5m]))'
        active_query = f'{namespace}_active_workers{{job=~"{job_filter}"}}'

        # Execute queries in parallel
        ops_result, latency_result, error_result, active_result = await self._execute_queries([
            ops_query, latency_query, error_query, active_query
        ])

        # Extract values
        ops_per_minute = self._extract_value(ops_result)
        p95_latency_ms = self._extract_value(latency_result)
        error_rate = self._extract_value(error_result)
        active_operations = int(self._extract_value(active_result))

        # Handle NaN values
        if str(p95_latency_ms).lower() == 'nan':
            p95_latency_ms = 0.0
        if str(error_rate).lower() == 'nan':
            error_rate = 0.0

        # Determine status
        status = self._determine_status(error_rate, p95_latency_ms, ops_per_minute)

        return ServiceMetrics(
            name=service,
            display_name=display_name,
            status=status,
            ops_per_minute=ops_per_minute,
            active_operations=active_operations,
            p95_latency_ms=p95_latency_ms,
            error_rate=error_rate,
            last_updated=datetime.utcnow(),
        )

    async def _execute_queries(self, queries: List[str]) -> List[Dict[str, Any]]:
        """Execute multiple queries in parallel using asyncio.gather."""
        return await asyncio.gather(*[self.query(q) for q in queries])

    async def get_all_services_metrics(self) -> List[ServiceMetrics]:
        """
        Get metrics for all configured services.

        Returns:
            List of ServiceMetrics for all services
        """
        services = list(SERVICE_CONFIG.keys())
        metrics = []

        for service in services:
            try:
                service_metrics = await self.get_service_metrics(service)
                metrics.append(service_metrics)
            except Exception as e:
                logger.error(f"Error fetching metrics for {service}: {e}")
                # Return degraded metrics on error
                config = SERVICE_CONFIG.get(service, {})
                metrics.append(ServiceMetrics(
                    name=service,
                    display_name=config.get('display_name', service.title()),
                    status='degraded',
                    ops_per_minute=0.0,
                    active_operations=0,
                    p95_latency_ms=0.0,
                    error_rate=0.0,
                    last_updated=datetime.utcnow(),
                ))

        return metrics

    async def get_service_connections(self) -> List[ServiceConnection]:
        """
        Get traffic metrics for service-to-service connections.

        Uses the SERVICE_TOPOLOGY to determine connections and
        queries for request rates between services.

        Returns:
            List of ServiceConnection objects
        """
        connections = []

        for source, target in SERVICE_TOPOLOGY:
            # Query for requests between services
            # This is a simplified query - in production, you'd have more specific labels
            source_config = SERVICE_CONFIG.get(source, {})
            target_config = SERVICE_CONFIG.get(target, {})

            source_job = source_config.get('job_patterns', [source])[0]
            target_job = target_config.get('job_patterns', [target])[0]

            # Simplified - just use mock data based on general traffic
            # In production, you'd have specific metrics for inter-service calls
            rpm_query = f'sum(rate(cc1c_requests_total{{job=~"{source_job}"}}[5m])) * 60'
            latency_query = f'avg(rate(cc1c_request_duration_seconds_sum{{job=~"{source_job}"}}[5m]) / rate(cc1c_request_duration_seconds_count{{job=~"{source_job}"}}[5m])) * 1000'

            rpm_result = await self.query(rpm_query)
            latency_result = await self.query(latency_query)

            rpm = self._extract_value(rpm_result)
            latency = self._extract_value(latency_result)

            if str(latency).lower() == 'nan':
                latency = 0.0

            connections.append(ServiceConnection(
                source=source,
                target=target,
                requests_per_minute=rpm,
                avg_latency_ms=latency,
            ))

        return connections

    async def get_historical_metrics(
        self,
        service: str,
        minutes: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get historical metrics for charts.

        Args:
            service: Service name
            minutes: Number of minutes of history to fetch

        Returns:
            List of data points with timestamp and metrics
        """
        config = SERVICE_CONFIG.get(service, {})
        namespace = config.get('namespace', 'cc1c')
        job_patterns = config.get('job_patterns', [service])
        job_filter = '|'.join(job_patterns)

        end = datetime.utcnow()
        start = end - timedelta(minutes=minutes)

        # Determine step based on time range
        if minutes <= 30:
            step = "30s"
        elif minutes <= 60:
            step = "1m"
        else:
            step = "2m"

        # Queries
        ops_query = f'sum(rate({namespace}_requests_total{{job=~"{job_filter}"}}[1m])) * 60'
        latency_query = f'histogram_quantile(0.95, sum(rate({namespace}_request_duration_seconds_bucket{{job=~"{job_filter}"}}[1m])) by (le)) * 1000'
        error_query = f'sum(rate({namespace}_requests_total{{job=~"{job_filter}",status=~"5.."}}[1m])) / sum(rate({namespace}_requests_total{{job=~"{job_filter}"}}[1m]))'

        # Execute range queries
        ops_result = await self.query_range(ops_query, start, end, step)
        latency_result = await self.query_range(latency_query, start, end, step)
        error_result = await self.query_range(error_query, start, end, step)

        # Combine results into time series
        data_points = []

        ops_data = ops_result.get('data', {}).get('result', [])
        latency_data = latency_result.get('data', {}).get('result', [])
        error_data = error_result.get('data', {}).get('result', [])

        # Extract values from first series (if exists)
        ops_values = ops_data[0].get('values', []) if ops_data else []
        latency_values = latency_data[0].get('values', []) if latency_data else []
        error_values = error_data[0].get('values', []) if error_data else []

        # Build combined data points
        # Use ops_values as the base timeline
        for i, (timestamp, ops_value) in enumerate(ops_values):
            point = {
                'timestamp': datetime.fromtimestamp(timestamp).isoformat(),
                'ops_per_minute': float(ops_value) if ops_value != 'NaN' else 0.0,
                'p95_latency_ms': 0.0,
                'error_rate': 0.0,
            }

            # Add latency if available for this timestamp
            if i < len(latency_values):
                lat_val = latency_values[i][1]
                point['p95_latency_ms'] = float(lat_val) if lat_val != 'NaN' else 0.0

            # Add error rate if available
            if i < len(error_values):
                err_val = error_values[i][1]
                point['error_rate'] = float(err_val) if err_val != 'NaN' else 0.0

            data_points.append(point)

        return data_points

    async def get_overall_health(self, services_metrics: List[ServiceMetrics]) -> str:
        """
        Determine overall system health based on all service metrics.

        Args:
            services_metrics: List of ServiceMetrics for all services

        Returns:
            'healthy', 'degraded', or 'critical'
        """
        if not services_metrics:
            return 'critical'

        critical_count = sum(1 for s in services_metrics if s.status == 'critical')
        degraded_count = sum(1 for s in services_metrics if s.status == 'degraded')

        if critical_count > 0:
            return 'critical'
        elif degraded_count > 0:
            return 'degraded'
        else:
            return 'healthy'


# Singleton instance
_prometheus_client: Optional[PrometheusClient] = None


def get_prometheus_client() -> PrometheusClient:
    """Get or create Prometheus client singleton."""
    global _prometheus_client
    if _prometheus_client is None:
        _prometheus_client = PrometheusClient()
    return _prometheus_client
