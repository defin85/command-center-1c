"""
UI metadata endpoints for API v2.

This package replaces the previous monolithic `views/ui.py` module.
"""

from __future__ import annotations

from .actions import get_action_catalog
from .preview import preview_execution_plan
from .table_metadata import get_table_metadata

__all__ = [
    "get_action_catalog",
    "get_table_metadata",
    "preview_execution_plan",
]
