"""
Operation endpoints for API v2.

This package replaces the previous monolithic `views/operations.py` module.
"""

from __future__ import annotations

from .catalog import get_operation_catalog
from .cli_catalog import get_cli_command_catalog, get_driver_commands
from .execute import execute_operation
from .execute_ibcmd_cli import execute_ibcmd_cli_operation
from .listing import cancel_operation, get_operation, list_operations
from .shortcuts import (
    create_driver_command_shortcut,
    delete_driver_command_shortcut,
    list_driver_command_shortcuts,
)
from .streams_live import get_stream_status, get_stream_ticket
from .streams_mux import (
    get_mux_stream_ticket,
    get_stream_mux_status,
    operation_stream_mux,
    subscribe_operation_streams,
    unsubscribe_operation_streams,
)
from .streams_sse import operation_stream

__all__ = [
    "cancel_operation",
    "create_driver_command_shortcut",
    "delete_driver_command_shortcut",
    "execute_ibcmd_cli_operation",
    "execute_operation",
    "get_cli_command_catalog",
    "get_driver_commands",
    "get_mux_stream_ticket",
    "get_operation",
    "get_operation_catalog",
    "get_stream_mux_status",
    "get_stream_status",
    "get_stream_ticket",
    "list_driver_command_shortcuts",
    "list_operations",
    "operation_stream",
    "operation_stream_mux",
    "subscribe_operation_streams",
    "unsubscribe_operation_streams",
]
