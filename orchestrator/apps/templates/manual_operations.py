"""Manual operation registry for templates-only execution flows."""

from __future__ import annotations

MANUAL_OPERATION_EXTENSIONS_SYNC = "extensions.sync"
MANUAL_OPERATION_EXTENSIONS_SET_FLAGS = "extensions.set_flags"

SUPPORTED_MANUAL_OPERATIONS = (
    MANUAL_OPERATION_EXTENSIONS_SYNC,
    MANUAL_OPERATION_EXTENSIONS_SET_FLAGS,
)


def is_supported_manual_operation(value: str) -> bool:
    normalized = str(value or "").strip()
    return normalized in SUPPORTED_MANUAL_OPERATIONS
