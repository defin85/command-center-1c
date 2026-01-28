from __future__ import annotations

from .core import OperationsServiceCore
from .discovery import OperationsServiceDiscoveryMixin
from .extra import OperationsServiceExtraMixin
from .health import OperationsServiceHealthMixin
from .message import OperationsServiceMessageMixin
from .types import EnqueueResult
from .workflow import OperationsServiceWorkflowMixin


class OperationsService(
    OperationsServiceWorkflowMixin,
    OperationsServiceHealthMixin,
    OperationsServiceDiscoveryMixin,
    OperationsServiceExtraMixin,
    OperationsServiceMessageMixin,
    OperationsServiceCore,
):
    """
    Service for sending operations directly to Redis queue.

    Replaces Celery tasks for operation enqueueing with direct Redis LPUSH.
    Maintains Message Protocol v2.0 compatibility with Go Workers.
    """


__all__ = [
    "EnqueueResult",
    "OperationsService",
]

