from apps.operations.event_subscriber.runtime import logger

try:
    from apps.operations.prometheus_metrics import record_batch_operation
    from apps.operations.prometheus_metrics import record_redis_event_received

    _METRICS_AVAILABLE = True
except Exception:
    record_redis_event_received = None
    record_batch_operation = None
    _METRICS_AVAILABLE = False


def record_event_metric(event_type: str, channel: str) -> None:
    if _METRICS_AVAILABLE:
        try:
            record_redis_event_received(event_type, channel)
        except Exception as metric_err:
            logger.debug("Failed to record redis event received metric: %s", metric_err)


def record_batch_metric(operation_type: str, status: str) -> None:
    if _METRICS_AVAILABLE:
        try:
            record_batch_operation(operation_type, status)
        except Exception as metric_err:
            logger.debug("Failed to record batch operation metric: %s", metric_err)

