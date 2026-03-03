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
import json
import logging
import time
from datetime import datetime

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

driver_catalog_editor_conflicts_total = Counter(
    'cc1c_orchestrator_driver_catalog_editor_conflicts_total',
    'Total driver catalog editor optimistic concurrency conflicts (ETag mismatch)',
    ['driver', 'action']
)

driver_catalog_editor_validation_failed_total = Counter(
    'cc1c_orchestrator_driver_catalog_editor_validation_failed_total',
    'Total driver catalog editor validation failures',
    ['driver', 'stage', 'kind']
)

driver_catalog_editor_errors_total = Counter(
    'cc1c_orchestrator_driver_catalog_editor_errors_total',
    'Total driver catalog editor errors (by reason code)',
    ['driver', 'action', 'code']
)

# =============================================================================
# Artifacts Purge Metrics
# =============================================================================

artifact_purge_jobs_total = Counter(
    'cc1c_orchestrator_artifact_purge_jobs_total',
    'Total artifact purge jobs (created/success/failed)',
    ['mode', 'status']
)

artifact_purge_deleted_objects_total = Counter(
    'cc1c_orchestrator_artifact_purge_deleted_objects_total',
    'Total objects deleted by artifact purge',
    ['mode']
)

artifact_purge_deleted_bytes_total = Counter(
    'cc1c_orchestrator_artifact_purge_deleted_bytes_total',
    'Total bytes deleted by artifact purge',
    ['mode']
)

artifact_purge_duration_seconds = Histogram(
    'cc1c_orchestrator_artifact_purge_duration_seconds',
    'Artifact purge duration in seconds',
    ['mode', 'status'],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600, 1800]
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
# Pools Variant A (command_log + outbox) SLI Metrics
# =============================================================================

pool_run_command_log_write_errors_total = Counter(
    'cc1c_orchestrator_pool_run_command_log_write_errors_total',
    'Total pool_run command_log write errors',
    ['error_type']
)

pool_run_command_outbox_lag_seconds = Gauge(
    'cc1c_orchestrator_pool_run_command_outbox_lag_seconds',
    'Current lag in seconds for oldest pending pool_run command outbox entry'
)

pool_run_command_outbox_retry_saturation_ratio = Gauge(
    'cc1c_orchestrator_pool_run_command_outbox_retry_saturation_ratio',
    'Ratio of pending pool_run outbox entries above retry saturation threshold'
)

pool_run_command_outbox_pending_total = Gauge(
    'cc1c_orchestrator_pool_run_command_outbox_pending_total',
    'Current total pending pool_run command outbox entries'
)

pool_run_command_outbox_retry_saturated_pending_total = Gauge(
    'cc1c_orchestrator_pool_run_command_outbox_retry_saturated_pending_total',
    'Current pending pool_run outbox entries above retry saturation threshold'
)

pool_run_command_outbox_retry_saturation_events_total = Counter(
    'cc1c_orchestrator_pool_run_command_outbox_retry_saturation_events_total',
    'Total observed pool_run outbox retry saturation events'
)

# =============================================================================
# Pool Master Data Sync SLI Metrics
# =============================================================================

pool_master_data_sync_outbox_lag_seconds = Gauge(
    "cc1c_orchestrator_pool_master_data_sync_outbox_lag_seconds",
    "Current lag in seconds for oldest pending/retrying pool master-data sync outbox entry",
)

pool_master_data_sync_outbox_pending_total = Gauge(
    "cc1c_orchestrator_pool_master_data_sync_outbox_pending_total",
    "Current pending pool master-data sync outbox entries",
)

pool_master_data_sync_outbox_retry_total = Gauge(
    "cc1c_orchestrator_pool_master_data_sync_outbox_retry_total",
    "Current retrying (failed) pool master-data sync outbox entries",
)

pool_master_data_sync_outbox_retry_saturated_total = Gauge(
    "cc1c_orchestrator_pool_master_data_sync_outbox_retry_saturated_total",
    "Current pool master-data sync outbox entries above retry saturation threshold",
)

pool_master_data_sync_outbox_retry_saturation_ratio = Gauge(
    "cc1c_orchestrator_pool_master_data_sync_outbox_retry_saturation_ratio",
    "Ratio of pool master-data sync outbox backlog above retry saturation threshold",
)

pool_master_data_sync_conflicts_pending_total = Gauge(
    "cc1c_orchestrator_pool_master_data_sync_conflicts_pending_total",
    "Current pending pool master-data sync conflicts",
)

pool_master_data_sync_conflicts_retrying_total = Gauge(
    "cc1c_orchestrator_pool_master_data_sync_conflicts_retrying_total",
    "Current retrying pool master-data sync conflicts",
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

event_subscriber_claimed_total = Counter(
    'cc1c_orchestrator_event_subscriber_claimed_total',
    'Total pending messages claimed (reclaimed) by event subscriber',
    ['stream', 'group']
)

event_subscriber_duplicate_receipts_total = Counter(
    'cc1c_orchestrator_event_subscriber_duplicate_receipts_total',
    'Total duplicate receipt detections (message already processed)',
    ['stream', 'group']
)

event_subscriber_poison_total = Counter(
    'cc1c_orchestrator_event_subscriber_poison_total',
    'Total poison messages acknowledged by event subscriber',
    ['stream', 'group', 'reason']
)


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
# Pool Run Outbox Dispatcher Runtime Metrics
# =============================================================================

POOL_OUTBOX_DISPATCHER_HEARTBEAT_KEY = "cc1c:pool_run_command_outbox_dispatcher:heartbeat"
POOL_OUTBOX_DISPATCHER_HEARTBEAT_STALE_SECONDS = 45
POOL_OUTBOX_RETRY_SATURATION_THRESHOLD_ATTEMPTS = 5


class PoolOutboxDispatcherCollector:
    """Collect runtime liveness and backlog metrics for pool outbox dispatcher."""

    def __init__(self):
        self._cache_ttl = 5
        self._cache_at = 0.0
        self._cache = {
            "up": 0.0,
            "heartbeat_age_seconds": float(POOL_OUTBOX_DISPATCHER_HEARTBEAT_STALE_SECONDS),
            "pending_total": 0.0,
            "retry_saturated_pending_total": 0.0,
            "lag_seconds": 0.0,
            "last_cycle_claimed_total": 0.0,
            "last_cycle_dispatched_total": 0.0,
            "last_cycle_failed_total": 0.0,
        }

    def collect(self):
        data = self._get_data()

        up_metric = GaugeMetricFamily(
            "cc1c_orchestrator_pool_run_command_outbox_dispatcher_up",
            "Pool outbox dispatcher heartbeat health (1/0)",
        )
        heartbeat_age_metric = GaugeMetricFamily(
            "cc1c_orchestrator_pool_run_command_outbox_dispatcher_heartbeat_age_seconds",
            "Age of latest pool outbox dispatcher heartbeat in seconds",
        )
        pending_metric = GaugeMetricFamily(
            "cc1c_orchestrator_pool_run_command_outbox_dispatcher_pending_total",
            "Current pending pool_run outbox entries",
        )
        retry_saturated_metric = GaugeMetricFamily(
            "cc1c_orchestrator_pool_run_command_outbox_dispatcher_retry_saturated_pending_total",
            "Pending pool_run outbox entries with saturated retries",
        )
        lag_metric = GaugeMetricFamily(
            "cc1c_orchestrator_pool_run_command_outbox_dispatcher_lag_seconds",
            "Current lag (seconds) for oldest pending pool_run outbox entry",
        )
        claimed_metric = GaugeMetricFamily(
            "cc1c_orchestrator_pool_run_command_outbox_dispatcher_last_cycle_claimed_total",
            "Outbox entries claimed by dispatcher in latest cycle",
        )
        dispatched_metric = GaugeMetricFamily(
            "cc1c_orchestrator_pool_run_command_outbox_dispatcher_last_cycle_dispatched_total",
            "Outbox entries dispatched by dispatcher in latest cycle",
        )
        failed_metric = GaugeMetricFamily(
            "cc1c_orchestrator_pool_run_command_outbox_dispatcher_last_cycle_failed_total",
            "Outbox entries failed by dispatcher in latest cycle",
        )

        up_metric.add_metric([], float(data.get("up", 0.0)))
        heartbeat_age_metric.add_metric([], float(data.get("heartbeat_age_seconds", 0.0)))
        pending_metric.add_metric([], float(data.get("pending_total", 0.0)))
        retry_saturated_metric.add_metric(
            [],
            float(data.get("retry_saturated_pending_total", 0.0)),
        )
        lag_metric.add_metric([], float(data.get("lag_seconds", 0.0)))
        claimed_metric.add_metric([], float(data.get("last_cycle_claimed_total", 0.0)))
        dispatched_metric.add_metric([], float(data.get("last_cycle_dispatched_total", 0.0)))
        failed_metric.add_metric([], float(data.get("last_cycle_failed_total", 0.0)))

        yield up_metric
        yield heartbeat_age_metric
        yield pending_metric
        yield retry_saturated_metric
        yield lag_metric
        yield claimed_metric
        yield dispatched_metric
        yield failed_metric

    def _get_data(self):
        now = time.time()
        if now - self._cache_at < self._cache_ttl:
            return self._cache

        data = dict(self._cache)
        data.update(
            {
                "up": 0.0,
                "heartbeat_age_seconds": float(POOL_OUTBOX_DISPATCHER_HEARTBEAT_STALE_SECONDS),
                "last_cycle_claimed_total": 0.0,
                "last_cycle_dispatched_total": 0.0,
                "last_cycle_failed_total": 0.0,
            }
        )

        redis_password = getattr(settings, "REDIS_PASSWORD", None)
        client = redis.Redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT),
            password=redis_password if redis_password else None,
            decode_responses=True,
        )

        try:
            heartbeat_raw = client.get(POOL_OUTBOX_DISPATCHER_HEARTBEAT_KEY)
            if heartbeat_raw:
                try:
                    payload = json.loads(heartbeat_raw)
                except (TypeError, json.JSONDecodeError):
                    payload = None

                if isinstance(payload, dict):
                    heartbeat_ts = _parse_iso_datetime(payload.get("timestamp"))
                    heartbeat_age_seconds = float(
                        POOL_OUTBOX_DISPATCHER_HEARTBEAT_STALE_SECONDS
                    )
                    if heartbeat_ts is not None:
                        heartbeat_age_seconds = max(now - heartbeat_ts.timestamp(), 0.0)
                    data["heartbeat_age_seconds"] = heartbeat_age_seconds
                    data["up"] = 1.0 if heartbeat_age_seconds <= POOL_OUTBOX_DISPATCHER_HEARTBEAT_STALE_SECONDS else 0.0
                    data["last_cycle_claimed_total"] = float(payload.get("claimed") or 0.0)
                    data["last_cycle_dispatched_total"] = float(payload.get("dispatched") or 0.0)
                    data["last_cycle_failed_total"] = float(payload.get("failed") or 0.0)

            try:
                from apps.intercompany_pools.models import (
                    PoolRunCommandOutbox,
                    PoolRunCommandOutboxStatus,
                )

                pending_entries = PoolRunCommandOutbox.objects.filter(
                    status=PoolRunCommandOutboxStatus.PENDING
                )
                data["pending_total"] = float(pending_entries.count())
                data["retry_saturated_pending_total"] = float(
                    pending_entries.filter(
                        dispatch_attempts__gte=POOL_OUTBOX_RETRY_SATURATION_THRESHOLD_ATTEMPTS
                    ).count()
                )

                oldest_next_retry_at = (
                    pending_entries.order_by("next_retry_at")
                    .values_list("next_retry_at", flat=True)
                    .first()
                )
                if oldest_next_retry_at is not None:
                    data["lag_seconds"] = max(
                        (now - oldest_next_retry_at.timestamp()),
                        0.0,
                    )
                else:
                    data["lag_seconds"] = 0.0
            except Exception as exc:
                logger.debug("Failed to collect pool outbox backlog metrics: %s", exc)
        except Exception as exc:
            logger.debug("Failed to collect pool outbox dispatcher metrics: %s", exc)
        finally:
            try:
                client.close()
            except Exception:
                pass

        self._cache = data
        self._cache_at = now
        return data


def _parse_iso_datetime(value):
    if not value:
        return None
    try:
        normalized = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except (TypeError, ValueError):
        return None


_POOL_OUTBOX_DISPATCHER_COLLECTOR_REGISTERED = False
if not _POOL_OUTBOX_DISPATCHER_COLLECTOR_REGISTERED:
    REGISTRY.register(PoolOutboxDispatcherCollector())
    _POOL_OUTBOX_DISPATCHER_COLLECTOR_REGISTERED = True


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


def record_event_subscriber_claimed(stream: str, group: str, count: int = 1) -> None:
    event_subscriber_claimed_total.labels(stream=stream, group=group).inc(count)


def record_event_subscriber_duplicate_receipt(stream: str, group: str, count: int = 1) -> None:
    event_subscriber_duplicate_receipts_total.labels(stream=stream, group=group).inc(count)


def record_event_subscriber_poison(stream: str, group: str, reason: str, count: int = 1) -> None:
    event_subscriber_poison_total.labels(stream=stream, group=group, reason=reason).inc(count)


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


def record_pool_run_command_log_write_error(error_type: str) -> None:
    """Record command_log write error for Variant A rollback trigger SLI."""
    normalized_error_type = str(error_type or "unknown").strip()[:64] or "unknown"
    pool_run_command_log_write_errors_total.labels(error_type=normalized_error_type).inc()


def set_pool_run_command_outbox_lag_seconds(lag_seconds: float) -> None:
    """Set current outbox lag in seconds for Variant A rollback trigger SLI."""
    safe_lag = max(0.0, float(lag_seconds or 0.0))
    pool_run_command_outbox_lag_seconds.set(safe_lag)


def set_pool_run_command_outbox_retry_saturation(
    ratio: float,
    *,
    saturated_pending: int,
    total_pending: int,
) -> None:
    """Set current retry saturation metrics for Variant A rollback trigger SLI."""
    safe_total_pending = max(0, int(total_pending or 0))
    safe_saturated_pending = max(0, int(saturated_pending or 0))
    normalized_ratio = 0.0
    if safe_total_pending > 0:
        normalized_ratio = max(0.0, min(1.0, float(ratio or 0.0)))

    pool_run_command_outbox_pending_total.set(safe_total_pending)
    pool_run_command_outbox_retry_saturated_pending_total.set(safe_saturated_pending)
    pool_run_command_outbox_retry_saturation_ratio.set(normalized_ratio)

    if safe_saturated_pending > 0:
        pool_run_command_outbox_retry_saturation_events_total.inc()


def set_pool_master_data_sync_backlog_metrics(
    *,
    lag_seconds: float,
    pending_total: int,
    retry_total: int,
    saturated_total: int,
) -> None:
    """Set current pool master-data sync backlog SLI metrics."""
    safe_lag = max(0.0, float(lag_seconds or 0.0))
    safe_pending_total = max(0, int(pending_total or 0))
    safe_retry_total = max(0, int(retry_total or 0))
    safe_saturated_total = max(0, int(saturated_total or 0))
    backlog_total = safe_pending_total + safe_retry_total
    ratio = 0.0
    if backlog_total > 0:
        ratio = max(0.0, min(1.0, float(safe_saturated_total / backlog_total)))

    pool_master_data_sync_outbox_lag_seconds.set(safe_lag)
    pool_master_data_sync_outbox_pending_total.set(safe_pending_total)
    pool_master_data_sync_outbox_retry_total.set(safe_retry_total)
    pool_master_data_sync_outbox_retry_saturated_total.set(safe_saturated_total)
    pool_master_data_sync_outbox_retry_saturation_ratio.set(ratio)


def set_pool_master_data_sync_conflict_metrics(
    *,
    pending_total: int,
    retrying_total: int,
) -> None:
    """Set current pool master-data sync conflict queue metrics."""
    pool_master_data_sync_conflicts_pending_total.set(max(0, int(pending_total or 0)))
    pool_master_data_sync_conflicts_retrying_total.set(max(0, int(retrying_total or 0)))


def record_api_v2_duration(endpoint: str, status: str, duration: float) -> None:
    """Record API v2 endpoint duration."""
    api_v2_duration.labels(endpoint=endpoint, status=status).observe(duration)


def record_api_v2_error(endpoint: str, error: str) -> None:
    """Record API v2 endpoint error."""
    api_v2_errors_total.labels(endpoint=endpoint, error=error).inc()


def record_driver_command_denied(driver: str, reason: str) -> None:
    """Record RBAC deny for schema-driven driver command (by reason)."""
    driver_commands_denied_total.labels(driver=driver, reason=reason).inc()


def record_driver_catalog_editor_conflict(driver: str, action: str) -> None:
    """Record optimistic concurrency conflicts in driver catalog editor flows."""
    driver_catalog_editor_conflicts_total.labels(driver=driver, action=action).inc()


def record_driver_catalog_editor_validation_failed(driver: str, stage: str, kind: str) -> None:
    """Record validation failures in driver catalog editor flows."""
    driver_catalog_editor_validation_failed_total.labels(driver=driver, stage=stage, kind=kind).inc()


def record_driver_catalog_editor_error(driver: str, action: str, code: str) -> None:
    """Record an error response in driver catalog editor flows (by code)."""
    driver_catalog_editor_errors_total.labels(driver=driver, action=action, code=code).inc()


def record_artifact_purge_job_created(mode: str) -> None:
    """Record artifact purge job creation (manual/ttl)."""
    artifact_purge_jobs_total.labels(mode=mode, status="created").inc()


def record_artifact_purge_job_completed(
    mode: str,
    status: str,
    *,
    deleted_objects: int = 0,
    deleted_bytes: int = 0,
    duration_seconds: float = 0.0,
) -> None:
    """Record artifact purge job completion + counters."""
    artifact_purge_jobs_total.labels(mode=mode, status=status).inc()

    if deleted_objects:
        artifact_purge_deleted_objects_total.labels(mode=mode).inc(deleted_objects)
    if deleted_bytes:
        artifact_purge_deleted_bytes_total.labels(mode=mode).inc(deleted_bytes)
    if duration_seconds and duration_seconds > 0:
        artifact_purge_duration_seconds.labels(mode=mode, status=status).observe(duration_seconds)


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
