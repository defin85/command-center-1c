"""
Abstract base class for operation backends.

Defines the contract for all operation backend implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Set

from apps.templates.workflow.models import WorkflowExecution
from ..base import NodeExecutionMode, NodeExecutionResult


class AbstractOperationBackend(ABC):
    """
    Abstract base class for operation backends.

    Each backend implementation handles specific operation types and executes
    them using appropriate protocols (OData, RAS, etc.).

    Implementations:
        - ODataBackend: OData protocol for data operations
        - RASBackend: RAS protocol for cluster management operations
    """

    @abstractmethod
    def execute(
        self,
        template: Any,
        rendered_data: Dict[str, Any],
        target_databases: List[str],
        context: Dict[str, Any],
        execution: WorkflowExecution,
        mode: NodeExecutionMode = NodeExecutionMode.SYNC
    ) -> NodeExecutionResult:
        """
        Execute operation using this backend.

        Args:
            template: Resolved runtime template with operation metadata
            rendered_data: Rendered template data (parameters, etc.)
            target_databases: List of database UUIDs to execute on
            context: Execution context with variables
            execution: WorkflowExecution for tracking
            mode: Execution mode (SYNC waits, ASYNC returns immediately)

        Returns:
            NodeExecutionResult with operation outcome
        """
        pass

    @abstractmethod
    def supports_operation_type(self, operation_type: str) -> bool:
        """
        Check if this backend supports the given operation type.

        Args:
            operation_type: Operation type string (e.g., 'create', 'lock_scheduled_jobs')

        Returns:
            True if this backend can handle the operation type
        """
        pass

    @classmethod
    @abstractmethod
    def get_supported_types(cls) -> Set[str]:
        """
        Get set of all operation types supported by this backend.

        Returns:
            Set of operation type strings
        """
        pass
