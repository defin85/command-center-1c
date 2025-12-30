"""
Prometheus client for fetching service mesh metrics.

Provides real-time and historical metrics for:
- API Gateway, Worker, Orchestrator services
- Request rates, latencies, error rates
- Active workers and queue depths
"""
import asyncio
import httpx
import logging
import math
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
        'thresholds': {
            'critical_error_rate': 0.20,
            'degraded_error_rate': 0.02,
            'critical_p95_ms': 30000,
            'degraded_p95_ms': 5000,
        },
    },
    'worker': {
        'display_name': 'Worker',
        'job_patterns': ['worker', 'go_worker'],
        'namespace': 'cc1c',
        'metrics_type': 'tasks',  # Use tasks_processed_total instead of requests_total
        # Worker processes long-running tasks (e.g., sync_cluster, install_extension).
        # Use wider p95 thresholds than HTTP services to avoid false "critical"
        # when the system is healthy but doing long work.
        'thresholds': {
            'critical_error_rate': 0.10,
            'degraded_error_rate': 0.01,
            'critical_p95_ms': 60_000,
            'degraded_p95_ms': 15_000,
        },
    },
    'orchestrator': {
        'display_name': 'Orchestrator',
        'job_patterns': ['orchestrator', 'django'],
        'namespace': 'cc1c_orchestrator',
    },
    'frontend': {
        'display_name': 'Frontend',
        'job_patterns': [],
        'namespace': 'frontend',
    },
    'postgresql': {
        'display_name': 'PostgreSQL',
        'job_patterns': ['postgresql', 'postgres_exporter', 'postgres'],
        'namespace': 'pg',  # postgres_exporter uses pg_* prefix
    },
    'redis': {
        'display_name': 'Redis',
        'job_patterns': ['redis', 'redis_exporter'],
        'namespace': 'redis',  # redis_exporter uses redis_* prefix
    },
    'minio': {
        'display_name': 'MinIO',
        'job_patterns': ['minio'],
        'namespace': 'minio',
    },
    'event-subscriber': {
        'display_name': 'Event Subscriber',
        'job_patterns': ['event_subscriber', 'event-subscriber', 'eventsubscriber'],
        'namespace': 'orchestrator',  # Part of Django orchestrator
    },
    'ras-server': {
        'display_name': 'RAS Server',
        'job_patterns': [],
        'namespace': 'external',
    },
}

# Service mesh topology (connections between services)
SERVICE_TOPOLOGY = [
    # Level 0 → 1: Client → Gateway
    ('frontend', 'api-gateway'),

    # Level 1 → 2: Gateway → Orchestrator (ALL requests go through Orchestrator)
    ('api-gateway', 'orchestrator'),

    # Level 2: Orchestrator → Infrastructure
    ('orchestrator', 'postgresql'),
    ('orchestrator', 'redis'),
    ('orchestrator', 'minio'),

    # Level 2 → 3: Worker gets tasks from Redis
    ('redis', 'worker'),  # Worker pulls from Redis queue

    # Level 2.5: Event Subscriber listens to Redis Streams
    ('redis', 'event-subscriber'),  # Event Subscriber consumes Redis Streams
    ('event-subscriber', 'postgresql'),  # Event Subscriber writes to DB

    # Level 3: Worker → Execution Layer (direct RAS/CLI tools)
    ('worker', 'ras-server'),
    ('worker', 'minio'),

    # Note: All adapters communicate via Redis Streams (Event-Driven Architecture)
    # Results flow: Adapters → Redis Streams (events:*) → Worker/Event Subscriber → PostgreSQL
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
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        loop = asyncio.get_running_loop()
        if self._client_loop and self._client_loop.is_closed():
            self._client = None
            self._client_loop = None
        if (
            self._client is None
            or self._client.is_closed
            or self._client_loop is not loop
        ):
            if self._client and not self._client.is_closed:
                await self._client.aclose()
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=10.0,
            )
            self._client_loop = loop
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None
        self._client_loop = None

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

    def _has_result(self, result: Dict[str, Any]) -> bool:
        """Return True if Prometheus response has at least one result series."""
        try:
            return bool(result.get('data', {}).get('result', []))
        except Exception:
            return False

    async def _get_ras_server_status(self) -> str:
        """
        RAS Server is an external dependency.

        We treat Prometheus as the single source of truth and read a Blackbox Exporter probe:
        `probe_success{cc1c_service="ras-server"}`.
        """
        result = await self.query('max(probe_success{cc1c_service="ras-server"})')
        if result.get("status") == "error" or not self._has_result(result):
            return "critical"

        value = self._extract_value(result)
        return "healthy" if value >= 0.5 else "critical"

    def _determine_status(
        self,
        error_rate: float,
        p95_latency_ms: float,
        ops_per_minute: float,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> str:
        """
        Determine service health status based on metrics.

        Thresholds:
        - critical: error_rate > 10% OR p95 > 5000ms
        - degraded: error_rate > 1% OR p95 > 1000ms
        - healthy: otherwise
        """
        thresholds = thresholds or {}
        critical_error_rate = float(thresholds.get('critical_error_rate', 0.10))
        degraded_error_rate = float(thresholds.get('degraded_error_rate', 0.01))
        critical_p95_ms = float(thresholds.get('critical_p95_ms', 5000))
        degraded_p95_ms = float(thresholds.get('degraded_p95_ms', 1000))

        if error_rate > critical_error_rate or p95_latency_ms > critical_p95_ms:
            return 'critical'
        elif error_rate > degraded_error_rate or p95_latency_ms > degraded_p95_ms:
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

        if service == "event-subscriber":
            up_result, consumers_result = await self._execute_queries([
                'min(cc1c_orchestrator_event_subscriber_up{group="orchestrator-group"})',
                'max(cc1c_orchestrator_event_subscriber_consumers{group="orchestrator-group"})',
            ])
            if (
                up_result.get("status") == "error"
                or consumers_result.get("status") == "error"
                or not self._has_result(up_result)
            ):
                status = "critical"
            else:
                up_value = self._extract_value(up_result)
                consumers = self._extract_value(consumers_result)
                if up_value < 0.5:
                    status = "critical"
                elif consumers < 1:
                    status = "degraded"
                else:
                    status = "healthy"

            return ServiceMetrics(
                name=service,
                display_name=display_name,
                status=status,
                ops_per_minute=0.0,
                active_operations=0,
                p95_latency_ms=0.0,
                error_rate=0.0,
                last_updated=datetime.utcnow(),
            )

        if service in ("ras-server", "frontend"):
            service_label = "ras-server" if service == "ras-server" else "frontend"
            success_result, duration_result = await self._execute_queries([
                f'max(probe_success{{cc1c_service="{service_label}"}})',
                f'max(probe_duration_seconds{{cc1c_service="{service_label}"}}) * 1000',
            ])
            if success_result.get("status") == "error" or not self._has_result(success_result):
                status = "critical"
            else:
                status = "healthy" if self._extract_value(success_result) >= 0.5 else "critical"

            p95_latency_ms = self._extract_value(duration_result) if self._has_result(duration_result) else 0.0
            return ServiceMetrics(
                name=service,
                display_name=display_name,
                status=status,
                ops_per_minute=0.0,
                active_operations=0,
                p95_latency_ms=p95_latency_ms,
                error_rate=0.0,
                last_updated=datetime.utcnow(),
            )

        namespace = config.get('namespace', 'cc1c')
        job_patterns = config.get('job_patterns', [service])
        metrics_type = config.get('metrics_type', 'requests')  # 'requests' or 'tasks'

        # Build job filter for PromQL
        job_filter = '|'.join(job_patterns)

        up_query = f'max(up{{job=~"{job_filter}"}})'

        # Queries depend on metrics type (HTTP requests vs task processing)
        if metrics_type == 'tasks':
            # Worker uses tasks_processed_total and task_duration_seconds
            ops_query = f'sum(rate({namespace}_tasks_processed_total{{job=~"{job_filter}"}}[5m])) * 60'
            latency_query = f'histogram_quantile(0.95, sum(rate({namespace}_task_duration_seconds_bucket{{job=~"{job_filter}"}}[5m])) by (le)) * 1000'
            error_query = f'sum(rate({namespace}_tasks_processed_total{{job=~"{job_filter}",status="failed"}}[5m])) / sum(rate({namespace}_tasks_processed_total{{job=~"{job_filter}"}}[5m]))'
        else:
            # Default: HTTP request metrics
            ops_query = f'sum(rate({namespace}_requests_total{{job=~"{job_filter}"}}[5m])) * 60'
            latency_query = f'histogram_quantile(0.95, sum(rate({namespace}_request_duration_seconds_bucket{{job=~"{job_filter}"}}[5m])) by (le)) * 1000'
            error_query = f'sum(rate({namespace}_requests_total{{job=~"{job_filter}",status=~"5.."}}[5m])) / sum(rate({namespace}_requests_total{{job=~"{job_filter}"}}[5m]))'

        active_query = f'{namespace}_active_workers{{job=~"{job_filter}"}}'

        # Execute queries in parallel
        ops_result, latency_result, error_result, active_result, up_result = await self._execute_queries([
            ops_query, latency_query, error_query, active_query, up_query
        ])

        if any(r.get('status') == 'error' for r in [ops_result, latency_result, error_result, active_result, up_result]):
            return ServiceMetrics(
                name=service,
                display_name=display_name,
                status='degraded',
                ops_per_minute=0.0,
                active_operations=0,
                p95_latency_ms=0.0,
                error_rate=0.0,
                last_updated=datetime.utcnow(),
            )

        up_value = self._extract_value(up_result)
        if up_value < 0.5:
            return ServiceMetrics(
                name=service,
                display_name=display_name,
                status='critical',
                ops_per_minute=0.0,
                active_operations=0,
                p95_latency_ms=0.0,
                error_rate=0.0,
                last_updated=datetime.utcnow(),
            )

        # Extract values
        ops_per_minute = self._extract_value(ops_result)
        p95_latency_ms = self._extract_value(latency_result)
        error_rate = self._extract_value(error_result)
        active_operations = int(self._extract_value(active_result))

        # Handle NaN values
        if math.isnan(p95_latency_ms):
            p95_latency_ms = 0.0
        if math.isnan(error_rate):
            error_rate = 0.0

        # Determine status
        thresholds = config.get('thresholds')
        status = self._determine_status(error_rate, p95_latency_ms, ops_per_minute, thresholds)

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
        results = await asyncio.gather(
            *[self.get_service_metrics(service) for service in services],
            return_exceptions=True,
        )

        metrics = []
        for service, result in zip(services, results):
            if isinstance(result, Exception):
                logger.error(f"Error fetching metrics for {service}: {result}")
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
                continue

            metrics.append(result)

        return metrics

    async def get_service_connections(self) -> List[ServiceConnection]:
        """
        Get traffic metrics for service-to-service connections.

        Uses the SERVICE_TOPOLOGY to determine connections and
        queries for request rates between services.

        Optimized: executes all queries in parallel using asyncio.gather.

        Returns:
            List of ServiceConnection objects
        """
        # Step 1: Build all queries upfront
        queries = []
        topology_info = []  # Track (source, target) for each query pair

        for source, target in SERVICE_TOPOLOGY:
            source_config = SERVICE_CONFIG.get(source, {})
            job_patterns = source_config.get('job_patterns', [source])
            if not job_patterns:
                job_patterns = [source]
            source_job = job_patterns[0]

            rpm_query = f'sum(rate(cc1c_requests_total{{job=~"{source_job}"}}[5m])) * 60'
            latency_query = f'avg(rate(cc1c_request_duration_seconds_sum{{job=~"{source_job}"}}[5m]) / rate(cc1c_request_duration_seconds_count{{job=~"{source_job}"}}[5m])) * 1000'

            queries.extend([rpm_query, latency_query])
            topology_info.append((source, target))

        # Step 2: Execute ALL queries in parallel (single await)
        results = await self._execute_queries(queries)

        # Step 3: Build connections from results
        connections = []
        for i, (source, target) in enumerate(topology_info):
            rpm_result = results[i * 2]
            latency_result = results[i * 2 + 1]

            rpm = self._extract_value(rpm_result)
            latency = self._extract_value(latency_result)

            if math.isnan(latency):
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
