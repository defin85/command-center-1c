"""
Django models for Workflow Engine.

This module is a compatibility facade:
- Pydantic schemas live in `apps.templates.workflow.schema`
- Django models live in `apps.templates.workflow.models_django`
"""

from .models_django import (  # noqa: F401
    WorkflowCategory,
    WorkflowExecution,
    WorkflowStepResult,
    WorkflowTemplate,
    WorkflowType,
)
from .schema import (  # noqa: F401
    DAGStructure,
    LoopConfig,
    NodeConfig,
    OperationIO,
    OperationRef,
    ParallelConfig,
    SubWorkflowConfig,
    SubWorkflowRef,
    WorkflowConfig,
    WorkflowEdge,
    WorkflowNode,
)

__all__ = [
    "DAGStructure",
    "LoopConfig",
    "NodeConfig",
    "OperationIO",
    "OperationRef",
    "ParallelConfig",
    "SubWorkflowConfig",
    "SubWorkflowRef",
    "WorkflowCategory",
    "WorkflowConfig",
    "WorkflowEdge",
    "WorkflowExecution",
    "WorkflowNode",
    "WorkflowStepResult",
    "WorkflowTemplate",
    "WorkflowType",
]
