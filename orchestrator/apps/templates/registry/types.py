"""
Operation type definitions for registry.

Defines dataclasses that serve as Single Source of Truth
for operation metadata.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class TargetEntity(str, Enum):
    """Target entity types for operations."""
    INFOBASE = 'infobase'
    CLUSTER = 'cluster'
    ENTITY = 'entity'  # OData entity


class BackendType(str, Enum):
    """Backend type identifiers."""
    ODATA = 'odata'
    RAS = 'ras'


@dataclass
class ParameterSchema:
    """Schema for operation parameter."""
    name: str
    type: str  # 'string', 'integer', 'boolean', 'uuid', 'json'
    required: bool = True
    description: str = ""
    default: Optional[Any] = None


@dataclass
class OperationType:
    """
    Complete specification of an operation type.

    This is the Single Source of Truth for operation metadata.
    """
    id: str                          # 'lock_scheduled_jobs'
    name: str                        # 'Lock Scheduled Jobs'
    description: str                 # Human-readable description
    backend: BackendType            # Backend that handles this operation
    target_entity: TargetEntity     # What entity type is affected

    required_parameters: List[ParameterSchema] = field(default_factory=list)
    optional_parameters: List[ParameterSchema] = field(default_factory=list)

    # Execution characteristics
    is_async: bool = False          # Executed asynchronously via Celery
    timeout_seconds: int = 300      # Default timeout
    max_retries: int = 3            # Default retry count

    # Categorization
    category: str = "general"       # 'data', 'admin', 'maintenance'
    tags: List[str] = field(default_factory=list)

    def to_choice(self) -> tuple:
        """Convert to Django choices format."""
        return (self.id, self.name)

    def to_template_data(self) -> Dict[str, Any]:
        """Convert to OperationTemplate.template_data format."""
        return {
            'required_parameters': [p.name for p in self.required_parameters],
            'optional_parameters': [p.name for p in self.optional_parameters],
            'parameter_schemas': {
                p.name: {'type': p.type, 'description': p.description, 'required': p.required}
                for p in self.required_parameters + self.optional_parameters
            },
            'backend': self.backend.value,
            'is_async': self.is_async,
            'timeout_seconds': self.timeout_seconds,
            'max_retries': self.max_retries,
            'category': self.category,
            'tags': self.tags,
        }
