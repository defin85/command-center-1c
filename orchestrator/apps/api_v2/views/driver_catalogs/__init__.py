"""
Command schemas / driver catalogs management views (API v2).

This package replaces the previous monolithic `views/driver_catalogs.py` module.
"""

from __future__ import annotations

from .audit import list_command_schemas_audit
from .diff import diff_command_schemas
from .overrides import rollback_command_schema_overrides, update_command_schema_overrides
from .preview import preview_command_schemas
from .read import get_command_schemas_editor_view, list_command_schema_versions
from .validate import validate_command_schemas
from .write import (
    import_its_command_schemas,
    promote_command_schemas_base,
    update_command_schemas_base,
    update_command_schemas_effective,
)

from apps.operations.driver_catalog_artifacts import upload_overrides_catalog_version
from apps.operations.driver_catalog_effective import invalidate_driver_catalog_cache
from apps.operations.prometheus_metrics import record_driver_catalog_editor_error

__all__ = [
    "diff_command_schemas",
    "get_command_schemas_editor_view",
    "import_its_command_schemas",
    "invalidate_driver_catalog_cache",
    "list_command_schema_versions",
    "list_command_schemas_audit",
    "preview_command_schemas",
    "promote_command_schemas_base",
    "record_driver_catalog_editor_error",
    "rollback_command_schema_overrides",
    "upload_overrides_catalog_version",
    "update_command_schema_overrides",
    "update_command_schemas_base",
    "update_command_schemas_effective",
    "validate_command_schemas",
]
