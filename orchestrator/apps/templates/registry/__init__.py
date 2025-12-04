"""
Operation Type Registry module.

Provides centralized registration and lookup of operation types
with full metadata support.

Usage:
    from apps.templates.registry import (
        get_registry,
        OperationType,
        BackendType,
        TargetEntity,
        ParameterSchema,
    )

    # Define operation type
    lock_jobs = OperationType(
        id='lock_scheduled_jobs',
        name='Lock Scheduled Jobs',
        description='Disable scheduled jobs',
        backend=BackendType.RAS,
        target_entity=TargetEntity.INFOBASE,
    )

    # Register
    registry = get_registry()
    registry.register(lock_jobs)

    # Use
    if registry.is_valid('lock_scheduled_jobs'):
        op = registry.get('lock_scheduled_jobs')
"""
from .types import (
    OperationType,
    BackendType,
    TargetEntity,
    ParameterSchema,
)
from .registry import (
    OperationTypeRegistry,
    get_registry,
)

__all__ = [
    # Types
    'OperationType',
    'BackendType',
    'TargetEntity',
    'ParameterSchema',
    # Registry
    'OperationTypeRegistry',
    'get_registry',
]
