"""
Workflow Engine for CommandCenter1C.

This package implements DAG-based workflow orchestration.

Components:
    - models: WorkflowTemplate, WorkflowExecution, WorkflowStepResult
    - validator: DAGValidator (Kahn's algorithm for cycle detection)
    - executor: DAGExecutor (execute nodes in topological order)
    - handlers: NodeHandlers (Operation, Condition, Parallel, Loop, SubWorkflow)
    - engine: WorkflowEngine (main orchestrator)
    - context: ContextManager (data passing between steps)

See docs/architecture/UNIFIED_WORKFLOW_VISUALIZATION.md for design details.

NOTE: To avoid circular imports, engine/executor/context are not imported at module level.
Import them directly when needed:
    from apps.templates.workflow.context import ContextManager
    from apps.templates.workflow.executor import DAGExecutor
    from apps.templates.workflow.engine import WorkflowEngine, get_workflow_engine
"""

from .validator import (
    DAGValidator,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
    # Exceptions
    CycleDetectedError,
    DAGValidationError,
    InvalidEdgeError,
    InvalidNodeTypeError,
    UnreachableNodeError,
)

__version__ = "1.0.0"

__all__ = [
    # Validator (imported at module level)
    "DAGValidator",
    "ValidationIssue",
    "ValidationResult",
    "ValidationSeverity",
    # Exceptions
    "CycleDetectedError",
    "DAGValidationError",
    "InvalidEdgeError",
    "InvalidNodeTypeError",
    "UnreachableNodeError",
    # These are available via direct import (not at module level to avoid circular imports):
    # from apps.templates.workflow.context import ContextManager
    # from apps.templates.workflow.executor import DAGExecutor, DAGExecutionError
    # from apps.templates.workflow.engine import WorkflowEngine, WorkflowEngineError, get_workflow_engine
]


def get_context_manager():
    """Lazy import for ContextManager to avoid circular imports."""
    from .context import ContextManager
    return ContextManager


def get_executor():
    """Lazy import for DAGExecutor to avoid circular imports."""
    from .executor import DAGExecutor
    return DAGExecutor


def get_engine():
    """Lazy import for WorkflowEngine to avoid circular imports."""
    from .engine import WorkflowEngine
    return WorkflowEngine
