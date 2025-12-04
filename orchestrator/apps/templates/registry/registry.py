"""
Central registry for operation types.

Provides thread-safe singleton for operation type registration
and lookup. Serves as Single Source of Truth.
"""
import logging
from typing import Dict, List, Optional, Set, Tuple
from threading import Lock

from .types import OperationType, BackendType

logger = logging.getLogger(__name__)


class OperationTypeRegistry:
    """
    Central registry for all operation types.

    Thread-safe singleton that serves as Single Source of Truth
    for operation type definitions.

    Usage:
        registry = OperationTypeRegistry()
        registry.register(operation_type)

        # Get all types
        all_types = registry.get_all()

        # Get Django choices
        choices = registry.get_choices()

        # Validate type exists
        if registry.is_valid('lock_scheduled_jobs'):
            ...
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._operations: Dict[str, OperationType] = {}
        self._by_backend: Dict[BackendType, Set[str]] = {
            bt: set() for bt in BackendType
        }
        self._initialized = True
        logger.info("OperationTypeRegistry initialized")

    def register(self, operation: OperationType) -> None:
        """
        Register an operation type.

        Args:
            operation: OperationType to register

        Raises:
            ValueError: If operation with same ID already registered with different backend
        """
        if operation.id in self._operations:
            existing = self._operations[operation.id]
            if existing.backend != operation.backend:
                raise ValueError(
                    f"Operation '{operation.id}' already registered "
                    f"with backend '{existing.backend.value}', cannot register "
                    f"with backend '{operation.backend.value}'"
                )
            # Same operation, same backend - skip
            return

        self._operations[operation.id] = operation
        self._by_backend[operation.backend].add(operation.id)

        logger.debug(
            f"Registered operation '{operation.id}' for backend '{operation.backend.value}'"
        )

    def register_many(self, operations: List[OperationType]) -> None:
        """Register multiple operation types."""
        for op in operations:
            self.register(op)

    def get(self, operation_id: str) -> Optional[OperationType]:
        """Get operation type by ID."""
        return self._operations.get(operation_id)

    def get_all(self) -> List[OperationType]:
        """Get all registered operation types."""
        return list(self._operations.values())

    def get_by_backend(self, backend: BackendType) -> List[OperationType]:
        """Get all operations for specific backend."""
        return [
            self._operations[op_id]
            for op_id in self._by_backend.get(backend, set())
        ]

    def get_choices(self) -> List[Tuple[str, str]]:
        """Get Django model choices format."""
        return sorted([op.to_choice() for op in self._operations.values()])

    def get_ids(self) -> Set[str]:
        """Get all registered operation IDs."""
        return set(self._operations.keys())

    def is_valid(self, operation_id: str) -> bool:
        """Check if operation type is registered."""
        return operation_id in self._operations

    def validate(self, operation_id: str) -> None:
        """
        Validate operation type exists.

        Raises:
            ValueError: If operation type not registered
        """
        if not self.is_valid(operation_id):
            valid_types = ', '.join(sorted(self._operations.keys()))
            raise ValueError(
                f"Unknown operation type: '{operation_id}'. "
                f"Valid types: {valid_types}"
            )

    def get_for_template_sync(self) -> List[Dict]:
        """
        Get operation data for OperationTemplate synchronization.

        Returns:
            List of dicts suitable for OperationTemplate creation/update.
        """
        return [
            {
                'id': f"tpl-{op.id.replace('_', '-')}",
                'name': op.name,
                'description': op.description,
                'operation_type': op.id,
                'target_entity': op.target_entity.value,
                'template_data': op.to_template_data(),
                'is_active': True,
            }
            for op in self._operations.values()
        ]

    def clear(self) -> None:
        """Clear all registrations. USE ONLY IN TESTS."""
        self._operations.clear()
        for backend in self._by_backend:
            self._by_backend[backend].clear()
        logger.warning("OperationTypeRegistry cleared")


# Module-level singleton accessor
_registry: Optional[OperationTypeRegistry] = None


def get_registry() -> OperationTypeRegistry:
    """Get the global operation type registry."""
    global _registry
    if _registry is None:
        _registry = OperationTypeRegistry()
    return _registry
