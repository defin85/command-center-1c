from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

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
