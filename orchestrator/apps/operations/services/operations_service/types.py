from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import redis as redis_pkg

logger = logging.getLogger(__name__)

# Import Prometheus metrics with availability flag
try:
    from ...prometheus_metrics import record_batch_operation

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    record_batch_operation = None


def _record_batch_metric(operation_type: str, status: str) -> None:
    """
    Helper function to record batch operation metric.

    Args:
        operation_type: Type of operation (e.g., 'sync_cluster')
        status: Status to record (e.g., 'queued', 'completed', 'failed')
    """
    if METRICS_AVAILABLE:
        try:
            record_batch_operation(operation_type, status)
        except Exception as metric_err:
            logger.debug(f"Failed to record batch operation metric: {metric_err}")


@dataclass
class EnqueueResult:
    """Result of enqueue operation."""

    success: bool
    operation_id: str
    status: str  # queued|duplicate|error
    error: Optional[str] = None
    error_code: Optional[str] = None
    metadata: dict = field(default_factory=dict)


def classify_enqueue_error_code(exc: BaseException) -> str:
    """
    Classify enqueue failure for API/UX decisions.

    NOTE: Keep this logic conservative: detect only Redis-native errors (including wrapped causes),
    avoid heuristics on exception messages.
    """
    stack: list[BaseException] = [exc]
    seen: set[int] = set()
    while stack and len(seen) < 32:
        current = stack.pop()
        current_id = id(current)
        if current_id in seen:
            continue
        seen.add(current_id)

        if isinstance(current, redis_pkg.exceptions.RedisError):
            return "REDIS_ERROR"

        cause = getattr(current, "__cause__", None)
        if isinstance(cause, BaseException):
            stack.append(cause)
        context = getattr(current, "__context__", None)
        if isinstance(context, BaseException):
            stack.append(context)

    return "ENQUEUE_FAILED"
