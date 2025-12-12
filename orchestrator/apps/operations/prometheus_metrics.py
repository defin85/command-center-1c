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
from prometheus_client import Counter, Histogram, Gauge

# Namespace: cc1c_orchestrator_

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
