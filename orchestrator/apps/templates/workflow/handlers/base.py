"""
Base handler classes for Workflow Engine.

Provides abstract base class and common functionality for all node handlers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional
import logging

from django.utils import timezone

from apps.templates.workflow.models import WorkflowExecution, WorkflowNode, WorkflowStepResult

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================


class NodeExecutionMode(Enum):
    """
    Execution mode for workflow nodes.

    - SYNC: Wait for operation completion before proceeding
    - ASYNC: Return immediately with task_id (Celery integration - Week 9)
    """
    SYNC = "sync"
    ASYNC = "async"


@dataclass
class NodeExecutionResult:
    """
    Result of a node execution.

    Attributes:
        success: Whether execution succeeded
        output: Node output data (rendered template, boolean result, etc.)
        error: Error message if failed (None if success)
        mode: Execution mode used (sync/async)
        duration_seconds: Execution duration in seconds (None if async)
        operation_id: BatchOperation ID for operation nodes (Week 17)
        task_id: Celery task ID for async execution (Week 17)
        context_updates: Optional dot-path updates to merge into workflow context
    """
    success: bool
    output: Optional[Any]
    error: Optional[str]
    mode: NodeExecutionMode
    duration_seconds: Optional[float]
    operation_id: Optional[str] = None
    task_id: Optional[str] = None
    context_updates: Optional[Dict[str, Any]] = None


# ============================================================================
# Base Handler
# ============================================================================


class BaseNodeHandler(ABC):
    """
    Abstract base handler for workflow nodes.

    Defines the handler contract and provides common functionality
    for creating and updating WorkflowStepResult records.

    Subclasses must implement:
        - execute(): Node execution logic
    """

    # Sensitive keys to sanitize before storing
    SENSITIVE_KEYS = {'db_password', 'password', 'secret', 'token', 'api_key'}

    @abstractmethod
    def execute(
        self,
        node: WorkflowNode,
        context: Dict[str, Any],
        execution: WorkflowExecution,
        mode: NodeExecutionMode = NodeExecutionMode.SYNC
    ) -> NodeExecutionResult:
        """
        Execute workflow node.

        Args:
            node: WorkflowNode Pydantic schema from DAG
            context: Execution context with variables
            execution: WorkflowExecution instance for tracking
            mode: Execution mode (sync/async)

        Returns:
            NodeExecutionResult with success/output/error
        """
        pass

    def _sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove sensitive fields before storing.

        Args:
            data: Dictionary that may contain sensitive fields

        Returns:
            Dictionary with sensitive fields masked as '***'
        """
        if not data:
            return data
        return {
            k: ('***' if k.lower() in self.SENSITIVE_KEYS else v)
            for k, v in data.items()
        }

    def _create_step_result(
        self,
        execution: WorkflowExecution,
        node: WorkflowNode,
        input_data: Dict[str, Any]
    ) -> WorkflowStepResult:
        """
        Create WorkflowStepResult for audit trail.

        Args:
            execution: WorkflowExecution instance
            node: WorkflowNode Pydantic schema
            input_data: Input data for this step

        Returns:
            WorkflowStepResult: Created step result instance (status=running)
        """
        # Sanitize sensitive data before storing
        sanitized_input_data = self._sanitize_data(input_data)

        step_result = WorkflowStepResult.objects.create(
            workflow_execution=execution,
            node_id=node.id,
            node_name=node.name,
            node_type=node.type,
            status=WorkflowStepResult.STATUS_RUNNING,
            input_data=sanitized_input_data,
            started_at=timezone.now()
        )

        # Set OpenTelemetry context if available (Week 12)
        step_result.set_opentelemetry_context()
        step_result.save(update_fields=['trace_id', 'span_id'])

        logger.info(
            f"Created step result for node {node.id}",
            extra={
                'execution_id': str(execution.id),
                'node_id': node.id,
                'node_type': node.type,
                'step_result_id': str(step_result.id)
            }
        )

        return step_result

    def _update_step_result(
        self,
        step_result: WorkflowStepResult,
        result: NodeExecutionResult
    ) -> None:
        """
        Update WorkflowStepResult with execution result.

        Args:
            step_result: WorkflowStepResult instance to update
            result: NodeExecutionResult with execution outcome
        """
        step_result.status = (
            WorkflowStepResult.STATUS_COMPLETED if result.success
            else WorkflowStepResult.STATUS_FAILED
        )
        step_result.output_data = result.output
        step_result.error_message = result.error or ""
        step_result.completed_at = timezone.now()

        step_result.save(update_fields=[
            'status', 'output_data', 'error_message', 'completed_at'
        ])

        logger.info(
            f"Updated step result for node {step_result.node_id}",
            extra={
                'step_result_id': str(step_result.id),
                'status': step_result.status,
                'duration_seconds': step_result.duration_seconds,
                'success': result.success
            }
        )
