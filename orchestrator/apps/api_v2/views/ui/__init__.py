"""
UI metadata endpoints for API v2.

This package replaces the previous monolithic `views/ui.py` module.
"""

from __future__ import annotations

import importlib
from typing import Any

_BASE = __name__
_EXPORTS: dict[str, tuple[str, str]] = {
    "get_action_catalog": (f"{_BASE}.actions", "get_action_catalog"),
    "preview_execution_plan": (f"{_BASE}.preview", "preview_execution_plan"),
    "get_table_metadata": (f"{_BASE}.table_metadata", "get_table_metadata"),
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
