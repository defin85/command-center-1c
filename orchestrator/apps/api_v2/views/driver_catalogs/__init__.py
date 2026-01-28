"""
Command schemas / driver catalogs management views (API v2).

This package replaces the previous monolithic `views/driver_catalogs.py` module.
"""

from __future__ import annotations

import importlib
from typing import Any

_BASE = __name__
_EXPORTS: dict[str, tuple[str, str]] = {
    "list_command_schemas_audit": (f"{_BASE}.audit", "list_command_schemas_audit"),
    "diff_command_schemas": (f"{_BASE}.diff", "diff_command_schemas"),
    "rollback_command_schema_overrides": (f"{_BASE}.overrides", "rollback_command_schema_overrides"),
    "update_command_schema_overrides": (f"{_BASE}.overrides", "update_command_schema_overrides"),
    "preview_command_schemas": (f"{_BASE}.preview", "preview_command_schemas"),
    "get_command_schemas_editor_view": (f"{_BASE}.read", "get_command_schemas_editor_view"),
    "list_command_schema_versions": (f"{_BASE}.read", "list_command_schema_versions"),
    "validate_command_schemas": (f"{_BASE}.validate", "validate_command_schemas"),
    "import_its_command_schemas": (f"{_BASE}.write", "import_its_command_schemas"),
    "promote_command_schemas_base": (f"{_BASE}.write", "promote_command_schemas_base"),
    "update_command_schemas_base": (f"{_BASE}.write", "update_command_schemas_base"),
    "update_command_schemas_effective": (f"{_BASE}.write", "update_command_schemas_effective"),
    "upload_overrides_catalog_version": ("apps.operations.driver_catalog_artifacts", "upload_overrides_catalog_version"),
    "invalidate_driver_catalog_cache": ("apps.operations.driver_catalog_effective", "invalidate_driver_catalog_cache"),
    "record_driver_catalog_editor_error": ("apps.operations.prometheus_metrics", "record_driver_catalog_editor_error"),
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
