"""
Database endpoints for API v2.

This package replaces the previous monolithic `views/databases.py` module.
"""

from __future__ import annotations

import importlib
from typing import Any

_BASE = __name__
_EXPORTS: dict[str, tuple[str, str]] = {
    "bulk_health_check": (f"{_BASE}.bulk_status", "bulk_health_check"),
    "set_status": (f"{_BASE}.bulk_status", "set_status"),
    "get_database": (f"{_BASE}.core", "get_database"),
    "get_extensions_snapshot": (f"{_BASE}.core", "get_extensions_snapshot"),
    "get_metadata_management": (f"{_BASE}.metadata_management", "get_metadata_management"),
    "health_check": (f"{_BASE}.core", "health_check"),
    "list_databases": (f"{_BASE}.core", "list_databases"),
    "refresh_metadata_snapshot": (f"{_BASE}.metadata_management", "refresh_metadata_snapshot"),
    "reverify_configuration_profile": (f"{_BASE}.metadata_management", "reverify_configuration_profile"),
    "update_database_credentials": (f"{_BASE}.core", "update_database_credentials"),
    "update_dbms_metadata": (f"{_BASE}.dbms_metadata", "update_dbms_metadata"),
    "update_ibcmd_connection_profile": (f"{_BASE}.ibcmd_connection_profile", "update_ibcmd_connection_profile"),
    "create_dbms_user": (f"{_BASE}.dbms_users", "create_dbms_user"),
    "delete_dbms_user": (f"{_BASE}.dbms_users", "delete_dbms_user"),
    "list_dbms_users": (f"{_BASE}.dbms_users", "list_dbms_users"),
    "reset_dbms_user_password": (f"{_BASE}.dbms_users", "reset_dbms_user_password"),
    "set_dbms_user_password": (f"{_BASE}.dbms_users", "set_dbms_user_password"),
    "update_dbms_user": (f"{_BASE}.dbms_users", "update_dbms_user"),
    "create_infobase_user": (f"{_BASE}.infobase_users", "create_infobase_user"),
    "delete_infobase_user": (f"{_BASE}.infobase_users", "delete_infobase_user"),
    "list_infobase_users": (f"{_BASE}.infobase_users", "list_infobase_users"),
    "reset_infobase_user_password": (f"{_BASE}.infobase_users", "reset_infobase_user_password"),
    "set_infobase_user_password": (f"{_BASE}.infobase_users", "set_infobase_user_password"),
    "update_infobase_user": (f"{_BASE}.infobase_users", "update_infobase_user"),
    "database_stream": (f"{_BASE}.streaming", "database_stream"),
    "get_database_stream_ticket": (f"{_BASE}.streaming", "get_database_stream_ticket"),
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
