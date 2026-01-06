"""
Helpers for initializing the operation registry.

In production, registry is populated via Django AppConfig.ready().
In tests, some suites intentionally call registry.clear(), which can leave
the global registry empty for other tests running in the same process.
"""

from __future__ import annotations

import logging

from .registry import get_registry

logger = logging.getLogger(__name__)


def ensure_registry_populated() -> None:
    """
    Ensure the global OperationTypeRegistry is populated with default operations.

    This is a safe, idempotent operation: registering the same operation with
    the same backend is skipped by the registry.
    """
    registry = get_registry()
    if registry.get_all():
        return

    try:
        from apps.templates.workflow.handlers.backends.cli import CLIBackend
        from apps.templates.workflow.handlers.backends.ibcmd import IBCMDBackend
        from apps.templates.workflow.handlers.backends.odata import ODataBackend
        from apps.templates.workflow.handlers.backends.ras import RASBackend

        RASBackend.register_operations()
        ODataBackend.register_operations()
        IBCMDBackend.register_operations()
        CLIBackend.register_operations()
    except Exception:
        logger.exception("Failed to populate operation registry")
