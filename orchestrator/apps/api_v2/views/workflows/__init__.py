"""
Workflow endpoints for API v2.

This package replaces the previous monolithic `views/workflows.py` module.
"""

from __future__ import annotations

import importlib
from typing import Any

_BASE = __name__
_EXPORTS: dict[str, tuple[str, str]] = {
    "_start_async_workflow_execution": (f"{_BASE}.common", "_start_async_workflow_execution"),
    "clone_workflow": (f"{_BASE}.crud", "clone_workflow"),
    "create_workflow": (f"{_BASE}.crud", "create_workflow"),
    "delete_workflow": (f"{_BASE}.crud", "delete_workflow"),
    "update_workflow": (f"{_BASE}.crud", "update_workflow"),
    "validate_workflow": (f"{_BASE}.crud", "validate_workflow"),
    "cancel_execution": (f"{_BASE}.executions", "cancel_execution"),
    "get_execution": (f"{_BASE}.executions", "get_execution"),
    "get_execution_steps": (f"{_BASE}.executions", "get_execution_steps"),
    "list_executions": (f"{_BASE}.executions", "list_executions"),
    "get_template_schema": (f"{_BASE}.template_catalog", "get_template_schema"),
    "list_templates": (f"{_BASE}.template_catalog", "list_templates"),
    "execute_workflow": (f"{_BASE}.templates", "execute_workflow"),
    "get_workflow": (f"{_BASE}.templates", "get_workflow"),
    "list_workflows": (f"{_BASE}.templates", "list_workflows"),
}


def __getattr__(name: str) -> Any:
    mapping = _EXPORTS.get(name)
    if mapping is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_path, attr_name = mapping
    value = getattr(importlib.import_module(module_path), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(list(globals().keys()) + list(_EXPORTS.keys())))

__all__ = list(_EXPORTS.keys())
