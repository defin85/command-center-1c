"""
Workflow Engine Node Handlers.

Provides handler architecture for different workflow node types:
- OperationHandler: Executes operation templates via TemplateRenderer
- ConditionHandler: Evaluates Jinja2 boolean expressions in sandbox
- ParallelHandler: Executes multiple nodes in parallel using Celery groups
- LoopHandler: Executes loop nodes (count/while/foreach modes)
- SubWorkflowHandler: Executes nested workflow templates with input/output mapping

Architecture:
- BaseNodeHandler: Abstract base class with result creation
- NodeExecutionResult: Structured result with mode tracking
- NodeExecutionMode: Enum for sync/async execution
- NodeHandlerFactory: Registry-based handler resolution

Week 8 Implementation Status:
- All handlers implemented with placeholder integration for Celery/WorkflowEngine
- Full error handling and logging
- Thread-safe singleton pattern for handler instances
"""

from .base import BaseNodeHandler, NodeExecutionMode, NodeExecutionResult
from .condition import ConditionHandler
from .factory import NodeHandlerFactory
from .loop import LoopHandler
from .operation import OperationHandler
from .parallel import ParallelHandler
from .subworkflow import SubWorkflowHandler

__all__ = [
    # Base classes
    'BaseNodeHandler',
    'NodeExecutionMode',
    'NodeExecutionResult',
    # Handlers
    'OperationHandler',
    'ConditionHandler',
    'ParallelHandler',
    'LoopHandler',
    'SubWorkflowHandler',
    # Factory
    'NodeHandlerFactory',
]
