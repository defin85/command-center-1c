from apps.operations.event_subscriber.runtime import logger

try:
    from apps.operations.prometheus_metrics import record_batch_operation
    from apps.operations.prometheus_metrics import record_redis_event_received
    from apps.operations.prometheus_metrics import record_event_subscriber_claimed
    from apps.operations.prometheus_metrics import record_event_subscriber_duplicate_receipt
    from apps.operations.prometheus_metrics import record_event_subscriber_poison

    _METRICS_AVAILABLE = True
except Exception:
    record_redis_event_received = None
    record_batch_operation = None
    record_event_subscriber_claimed = None
    record_event_subscriber_duplicate_receipt = None
    record_event_subscriber_poison = None
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


def record_claimed_metric(stream: str, group: str, count: int = 1) -> None:
    if _METRICS_AVAILABLE:
        try:
            record_event_subscriber_claimed(stream, group, count)
        except Exception as metric_err:
            logger.debug("Failed to record event subscriber claimed metric: %s", metric_err)


def record_duplicate_receipt_metric(stream: str, group: str, count: int = 1) -> None:
    if _METRICS_AVAILABLE:
        try:
            record_event_subscriber_duplicate_receipt(stream, group, count)
        except Exception as metric_err:
            logger.debug("Failed to record event subscriber duplicate receipt metric: %s", metric_err)


def record_poison_metric(stream: str, group: str, reason: str, count: int = 1) -> None:
    if _METRICS_AVAILABLE:
        try:
            record_event_subscriber_poison(stream, group, reason, count)
        except Exception as metric_err:
            logger.debug("Failed to record event subscriber poison metric: %s", metric_err)
