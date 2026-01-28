"""
Workflow endpoints for API v2.

This package replaces the previous monolithic `views/workflows.py` module.
"""

from __future__ import annotations

from .common import _start_async_workflow_execution
from .crud import (
    clone_workflow,
    create_workflow,
    delete_workflow,
    update_workflow,
    validate_workflow,
)
from .executions import (
    cancel_execution,
    get_execution,
    get_execution_steps,
    list_executions,
)
from .template_catalog import get_template_schema, list_templates
from .templates import execute_workflow, get_workflow, list_workflows

__all__ = [
    "_start_async_workflow_execution",
    "cancel_execution",
    "clone_workflow",
    "create_workflow",
    "delete_workflow",
    "execute_workflow",
    "get_execution",
    "get_execution_steps",
    "get_template_schema",
    "get_workflow",
    "list_executions",
    "list_templates",
    "list_workflows",
    "update_workflow",
    "validate_workflow",
]
