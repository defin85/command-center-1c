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
    ParallelConfig,
    SubWorkflowConfig,
    WorkflowConfig,
    WorkflowEdge,
    WorkflowNode,
)

__all__ = [
    "DAGStructure",
    "LoopConfig",
    "NodeConfig",
    "ParallelConfig",
    "SubWorkflowConfig",
    "WorkflowCategory",
    "WorkflowConfig",
    "WorkflowEdge",
    "WorkflowExecution",
    "WorkflowNode",
    "WorkflowStepResult",
    "WorkflowTemplate",
    "WorkflowType",
]
