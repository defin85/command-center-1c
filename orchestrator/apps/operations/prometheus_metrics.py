"""
Prometheus metrics for Orchestrator.

Custom metrics for tracking operations, WebSocket connections, and Redis events.
These complement the default django-prometheus metrics (HTTP requests, DB queries, etc.).

Usage:
    from apps.operations.prometheus_metrics import (
        record_operation,
        record_batch_operation,
        record_redis_event_published,
    )

    # Record operation completion
    record_operation('sync_database', 'success', duration=2.5)

    # Record batch operation
    record_batch_operation('bulk_update', 'completed')

    # Record Redis event
    record_redis_event_published('operation_completed', 'cc1c:events')
"""
import logging
import time

import redis
from django.conf import settings
from prometheus_client import Counter, Histogram, Gauge, REGISTRY
from prometheus_client.core import GaugeMetricFamily

logger = logging.getLogger(__name__)

# Namespace: cc1c_orchestrator_

# =============================================================================
# HTTP Request Metrics
# =============================================================================

http_requests_total = Counter(
    'cc1c_orchestrator_requests_total',
    'Total HTTP requests',
    ['method', 'status']
)

http_request_duration = Histogram(
    'cc1c_orchestrator_request_duration_seconds',
    'HTTP request duration',
    ['method', 'status'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10]
)

active_workers = Gauge(
    'cc1c_orchestrator_active_workers',
    'Number of in-flight HTTP requests'
)

# =============================================================================
# Operations Metrics
# =============================================================================

operations_total = Counter(
    'cc1c_orchestrator_operations_total',
    'Total operations processed',
    ['operation_type', 'status']
)

operation_duration = Histogram(
    'cc1c_orchestrator_operation_duration_seconds',
    'Operation processing duration',
    ['operation_type'],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120]
)

# =============================================================================
# WebSocket Metrics
# =============================================================================

websocket_connections = Gauge(
    'cc1c_orchestrator_websocket_connections_active',
    'Number of active WebSocket connections'
)

# =============================================================================
# SSE Metrics
# =============================================================================

sse_connections = Gauge(
    'cc1c_orchestrator_sse_connections_active',
    'Number of active SSE connections',
    ['stream']
)

sse_tickets_total = Counter(
    'cc1c_orchestrator_sse_tickets_total',
    'Total SSE tickets issued',
    ['stream', 'status']
)

sse_stream_errors_total = Counter(
    'cc1c_orchestrator_sse_stream_errors_total',
    'Total SSE stream errors',
    ['stream', 'stage']
)

sse_stream_loop_duration = Histogram(
    'cc1c_orchestrator_sse_stream_loop_duration_seconds',
    'SSE loop iteration duration',
    ['stream'],
    buckets=[0.1, 0.25, 0.5, 1, 2, 5, 10]
)

# =============================================================================
# API v2 Metrics
# =============================================================================

api_v2_duration = Histogram(
    'cc1c_orchestrator_api_v2_duration_seconds',
    'API v2 endpoint duration',
    ['endpoint', 'status'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10]
)

api_v2_errors_total = Counter(
    'cc1c_orchestrator_api_v2_errors_total',
    'API v2 endpoint errors',
    ['endpoint', 'error']
)

# =============================================================================
# Driver Catalog / Schema-driven Commands Metrics
# =============================================================================

driver_commands_denied_total = Counter(
    'cc1c_orchestrator_driver_commands_denied_total',
    'Total schema-driven driver commands denied (RBAC filter)',
    ['driver', 'reason']
)

# =============================================================================
# Deprecation Metrics
# =============================================================================

deprecated_operations_total = Counter(
    'cc1c_orchestrator_deprecated_operations_total',
    'Total deprecated operations invoked via API',
    ['operation_type', 'endpoint']
)

# =============================================================================
# Redis Events Metrics
# =============================================================================

redis_events_published = Counter(
    'cc1c_orchestrator_redis_events_published_total',
    'Total Redis events published',
    ['event_type', 'channel']
)

redis_events_received = Counter(
    'cc1c_orchestrator_redis_events_received_total',
    'Total Redis events received',
    ['event_type', 'channel']
)

# =============================================================================
# Batch Operations Metrics
# =============================================================================

batch_operations_total = Counter(
    'cc1c_orchestrator_batch_operations_total',
    'Total batch operations',
    ['operation_type', 'status']
)

# =============================================================================
# Queue Metrics
# =============================================================================

queue_depth = Gauge(
    'cc1c_orchestrator_queue_depth',
    'Number of operations in queue',
    ['queue_name']
)

# =============================================================================
# Admin/Operator Actions Metrics
# =============================================================================

admin_actions_total = Counter(
    'cc1c_orchestrator_admin_actions_total',
    'Total operator/admin actions executed via API',
    ['action', 'outcome']
)

# =============================================================================
# Event Subscriber (Redis Streams) Metrics
# =============================================================================

EVENT_SUBSCRIBER_GROUP = "orchestrator-group"
EVENT_SUBSCRIBER_STREAMS = [
    'events:worker:cluster-synced',
    'events:worker:clusters-discovered',
    'events:worker:completed',
    'events:worker:failed',
    'commands:worker:dlq',
    'commands:orchestrator:get-cluster-info',
    'commands:orchestrator:get-database-credentials',
]


class EventSubscriberCollector:
    """Collect Redis Streams consumer group stats for Prometheus."""

    def __init__(self):
        self._cache_ttl = 5
        self._cache_at = 0.0
        self._cache = {}

    def collect(self):
        data = self._get_data()

        up_metric = GaugeMetricFamily(
            'cc1c_orchestrator_event_subscriber_up',
            'Event subscriber consumer group exists for stream (1/0)',
            labels=['stream', 'group']
        )
        consumers_metric = GaugeMetricFamily(
            'cc1c_orchestrator_event_subscriber_consumers',
            'Event subscriber consumer count per stream/group',
            labels=['stream', 'group']
        )
        pending_metric = GaugeMetricFamily(
            'cc1c_orchestrator_event_subscriber_pending',
            'Event subscriber pending messages per stream/group',
            labels=['stream', 'group']
        )

        for stream, info in data.items():
            labels = [stream, EVENT_SUBSCRIBER_GROUP]
            up_metric.add_metric(labels, info.get('up', 0))
            consumers_metric.add_metric(labels, info.get('consumers', 0))
            pending_metric.add_metric(labels, info.get('pending', 0))

        yield up_metric
        yield consumers_metric
        yield pending_metric

    def _get_data(self):
        now = time.time()
        if now - self._cache_at < self._cache_ttl:
            return self._cache

        data = {stream: {'up': 0, 'consumers': 0, 'pending': 0} for stream in EVENT_SUBSCRIBER_STREAMS}

        redis_password = getattr(settings, 'REDIS_PASSWORD', None)
        client = redis.Redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT),
            password=redis_password if redis_password else None,
            decode_responses=True,
        )

        try:
            for stream in EVENT_SUBSCRIBER_STREAMS:
                try:
                    groups = client.xinfo_groups(stream)
                except Exception:
                    continue

                group_info = next(
                    (group for group in groups if group.get('name') == EVENT_SUBSCRIBER_GROUP),
                    None
                )
                if not group_info:
                    continue

                data[stream]['up'] = 1
                data[stream]['consumers'] = int(group_info.get('consumers', 0) or 0)
                data[stream]['pending'] = int(group_info.get('pending', 0) or 0)
        except Exception as exc:
            logger.debug("Failed to collect event subscriber metrics: %s", exc)
        finally:
            try:
                client.close()
            except Exception:
                pass

        self._cache = data
        self._cache_at = now
        return data


_EVENT_SUBSCRIBER_COLLECTOR_REGISTERED = False
if not _EVENT_SUBSCRIBER_COLLECTOR_REGISTERED:
    REGISTRY.register(EventSubscriberCollector())
    _EVENT_SUBSCRIBER_COLLECTOR_REGISTERED = True


# =============================================================================
# Helper Functions
# =============================================================================

def record_operation(operation_type: str, status: str, duration: float) -> None:
    """
    Record an operation with its duration.

    Args:
        operation_type: Type of operation (e.g., 'sync_database', 'update_config')
        status: Status of operation ('success', 'failure', 'timeout')
        duration: Duration in seconds
    """
    operations_total.labels(operation_type=operation_type, status=status).inc()
    operation_duration.labels(operation_type=operation_type).observe(duration)


def record_batch_operation(operation_type: str, status: str) -> None:
    """
    Record a batch operation.

    Args:
        operation_type: Type of batch operation (e.g., 'bulk_update', 'bulk_delete')
        status: Status of operation ('pending', 'running', 'completed', 'failed')
    """
    batch_operations_total.labels(operation_type=operation_type, status=status).inc()


def record_redis_event_published(event_type: str, channel: str) -> None:
    """
    Record a Redis event published.

    Args:
        event_type: Type of event (e.g., 'operation_completed', 'status_changed')
        channel: Redis channel name
    """
    redis_events_published.labels(event_type=event_type, channel=channel).inc()


def record_redis_event_received(event_type: str, channel: str) -> None:
    """
    Record a Redis event received.

    Args:
        event_type: Type of event
        channel: Redis channel name
    """
    redis_events_received.labels(event_type=event_type, channel=channel).inc()


def set_websocket_connections(count: int) -> None:
    """
    Set the number of active WebSocket connections.

    Args:
        count: Current number of active connections
    """
    websocket_connections.set(count)


def set_queue_depth(queue_name: str, depth: int) -> None:
    """
    Set the queue depth for a specific queue.

    Args:
        queue_name: Name of the queue (e.g., 'cc1c:operations:v1')
        depth: Number of items in queue
    """
    queue_depth.labels(queue_name=queue_name).set(depth)


def record_admin_action(action: str, outcome: str) -> None:
    """
    Record an operator/admin action (SPA-primary flows).

    Args:
        action: Action identifier (e.g. 'dlq.retry')
        outcome: 'success' | 'error'
    """
    admin_actions_total.labels(action=action, outcome=outcome).inc()


def record_api_v2_duration(endpoint: str, status: str, duration: float) -> None:
    """Record API v2 endpoint duration."""
    api_v2_duration.labels(endpoint=endpoint, status=status).observe(duration)


def record_api_v2_error(endpoint: str, error: str) -> None:
    """Record API v2 endpoint error."""
    api_v2_errors_total.labels(endpoint=endpoint, error=error).inc()


def record_driver_command_denied(driver: str, reason: str) -> None:
    """Record RBAC deny for schema-driven driver command (by reason)."""
    driver_commands_denied_total.labels(driver=driver, reason=reason).inc()


def record_deprecated_operation(operation_type: str, endpoint: str) -> None:
    """Record deprecated operation usage (migration/deprecation telemetry)."""
    deprecated_operations_total.labels(operation_type=operation_type, endpoint=endpoint).inc()


def record_sse_ticket(stream: str, status: str) -> None:
    """Record SSE ticket issuance result."""
    sse_tickets_total.labels(stream=stream, status=status).inc()


def sse_connection_open(stream: str) -> None:
    """Increment active SSE connection gauge."""
    sse_connections.labels(stream=stream).inc()


def sse_connection_close(stream: str) -> None:
    """Decrement active SSE connection gauge."""
    sse_connections.labels(stream=stream).dec()


def record_sse_stream_error(stream: str, stage: str) -> None:
    """Record SSE stream error with stage label."""
    sse_stream_errors_total.labels(stream=stream, stage=stage).inc()


def record_sse_loop_duration(stream: str, duration: float) -> None:
    """Record SSE loop iteration duration."""
    sse_stream_loop_duration.labels(stream=stream).observe(duration)
