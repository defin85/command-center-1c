"""
Database endpoints for API v2.

This package replaces the previous monolithic `views/databases.py` module.
"""

from __future__ import annotations

from .bulk_status import bulk_health_check, set_status
from .core import (
    get_database,
    get_extensions_snapshot,
    health_check,
    list_databases,
    update_database_credentials,
)
from .dbms_users import (
    create_dbms_user,
    delete_dbms_user,
    list_dbms_users,
    reset_dbms_user_password,
    set_dbms_user_password,
    update_dbms_user,
)
from .infobase_users import (
    create_infobase_user,
    delete_infobase_user,
    list_infobase_users,
    reset_infobase_user_password,
    set_infobase_user_password,
    update_infobase_user,
)
from .streaming import database_stream, get_database_stream_ticket

__all__ = [
    "bulk_health_check",
    "create_dbms_user",
    "create_infobase_user",
    "database_stream",
    "delete_dbms_user",
    "delete_infobase_user",
    "get_database",
    "get_database_stream_ticket",
    "get_extensions_snapshot",
    "health_check",
    "list_databases",
    "list_dbms_users",
    "list_infobase_users",
    "reset_dbms_user_password",
    "reset_infobase_user_password",
    "set_dbms_user_password",
    "set_infobase_user_password",
    "set_status",
    "update_database_credentials",
    "update_dbms_user",
    "update_infobase_user",
]
