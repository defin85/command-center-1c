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
"""

__version__ = "1.0.0"
