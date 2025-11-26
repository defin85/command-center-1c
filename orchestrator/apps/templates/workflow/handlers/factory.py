"""
NodeHandlerFactory for Workflow Engine.

Registry-based factory for creating and managing node handlers.
"""

import logging
import threading
from typing import Dict

from .base import BaseNodeHandler
from .condition import ConditionHandler
from .loop import LoopHandler
from .operation import OperationHandler
from .parallel import ParallelHandler
from .subworkflow import SubWorkflowHandler

logger = logging.getLogger(__name__)


class NodeHandlerFactory:
    """
    Factory for creating node handlers.

    Uses registry pattern for handler resolution:
    - register(): Register handler class for node type
    - get_handler(): Get singleton handler instance

    Handlers are singletons (created once, reused).

    Auto-registration:
        - Handlers are registered at module load time
        - See bottom of this file for registrations
    """

    # Class-level registry
    _handlers: Dict[str, type] = {}
    _instances: Dict[str, BaseNodeHandler] = {}
    _lock = threading.Lock()

    @classmethod
    def register(cls, node_type: str, handler_class: type) -> None:
        """
        Register handler class for node type.

        Args:
            node_type: Node type identifier (operation, condition, etc.)
            handler_class: Handler class (must inherit BaseNodeHandler)

        Raises:
            TypeError: If handler_class is not a BaseNodeHandler subclass
        """
        if not issubclass(handler_class, BaseNodeHandler):
            raise TypeError(
                f"Handler class must inherit from BaseNodeHandler, got {handler_class}"
            )

        cls._handlers[node_type] = handler_class

        logger.debug(
            f"Registered handler for node type '{node_type}'",
            extra={'node_type': node_type, 'handler_class': handler_class.__name__}
        )

    @classmethod
    def get_handler(cls, node_type: str) -> BaseNodeHandler:
        """
        Get handler instance for node type.

        Creates singleton instance on first access with thread-safe double-checked locking.

        Args:
            node_type: Node type identifier

        Returns:
            BaseNodeHandler: Handler instance

        Raises:
            ValueError: If no handler registered for node type
        """
        # Check if handler is registered
        if node_type not in cls._handlers:
            raise ValueError(
                f"No handler registered for node type '{node_type}'. "
                f"Available types: {list(cls._handlers.keys())}"
            )

        # Double-checked locking pattern for thread-safe singleton creation
        if node_type not in cls._instances:  # Fast path (no lock)
            with cls._lock:  # Thread-safe
                if node_type not in cls._instances:  # Re-check inside lock
                    handler_class = cls._handlers[node_type]
                    cls._instances[node_type] = handler_class()

                    logger.debug(
                        f"Created handler instance for node type '{node_type}'",
                        extra={'node_type': node_type, 'handler_class': handler_class.__name__}
                    )

        return cls._instances[node_type]


# ============================================================================
# Auto-registration
# ============================================================================


# Register handlers at module load time
NodeHandlerFactory.register('operation', OperationHandler)
NodeHandlerFactory.register('condition', ConditionHandler)
NodeHandlerFactory.register('parallel', ParallelHandler)
NodeHandlerFactory.register('loop', LoopHandler)
NodeHandlerFactory.register('subworkflow', SubWorkflowHandler)

logger.info(
    "NodeHandlers module initialized",
    extra={
        'registered_handlers': list(NodeHandlerFactory._handlers.keys())
    }
)
