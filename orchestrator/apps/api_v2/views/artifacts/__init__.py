"""
Artifact endpoints for API v2.

This package replaces the previous monolithic `views/artifacts.py` module.
"""

from __future__ import annotations

from .crud import create_artifact, delete_artifact, list_artifacts, restore_artifact
from .purge import get_purge_job, purge_artifact
from .versions import (
    download_artifact_version,
    list_artifact_aliases,
    list_artifact_versions,
    upload_artifact_version,
    upsert_artifact_alias,
)

__all__ = [
    "create_artifact",
    "delete_artifact",
    "download_artifact_version",
    "get_purge_job",
    "list_artifact_aliases",
    "list_artifact_versions",
    "list_artifacts",
    "purge_artifact",
    "restore_artifact",
    "upload_artifact_version",
    "upsert_artifact_alias",
]
