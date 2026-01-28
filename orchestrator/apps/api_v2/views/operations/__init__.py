"""
Operation endpoints for API v2.

This package replaces the previous monolithic `views/operations.py` module.
"""

from __future__ import annotations

import importlib
from typing import Any

_BASE = __name__
_EXPORTS: dict[str, tuple[str, str]] = {
    "get_operation_catalog": (f"{_BASE}.catalog", "get_operation_catalog"),
    "get_cli_command_catalog": (f"{_BASE}.cli_catalog", "get_cli_command_catalog"),
    "get_driver_commands": (f"{_BASE}.cli_catalog", "get_driver_commands"),
    "execute_operation": (f"{_BASE}.execute", "execute_operation"),
    "execute_ibcmd_cli_operation": (f"{_BASE}.execute_ibcmd_cli", "execute_ibcmd_cli_operation"),
    "cancel_operation": (f"{_BASE}.listing", "cancel_operation"),
    "get_operation": (f"{_BASE}.listing", "get_operation"),
    "list_operations": (f"{_BASE}.listing", "list_operations"),
    "create_driver_command_shortcut": (f"{_BASE}.shortcuts", "create_driver_command_shortcut"),
    "delete_driver_command_shortcut": (f"{_BASE}.shortcuts", "delete_driver_command_shortcut"),
    "list_driver_command_shortcuts": (f"{_BASE}.shortcuts", "list_driver_command_shortcuts"),
    "get_stream_status": (f"{_BASE}.streams_live", "get_stream_status"),
    "get_stream_ticket": (f"{_BASE}.streams_live", "get_stream_ticket"),
    "get_mux_stream_ticket": (f"{_BASE}.streams_mux", "get_mux_stream_ticket"),
    "get_stream_mux_status": (f"{_BASE}.streams_mux", "get_stream_mux_status"),
    "operation_stream_mux": (f"{_BASE}.streams_mux", "operation_stream_mux"),
    "subscribe_operation_streams": (f"{_BASE}.streams_mux", "subscribe_operation_streams"),
    "unsubscribe_operation_streams": (f"{_BASE}.streams_mux", "unsubscribe_operation_streams"),
    "operation_stream": (f"{_BASE}.streams_sse", "operation_stream"),
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
