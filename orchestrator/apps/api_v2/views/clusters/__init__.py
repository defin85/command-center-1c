"""
Cluster endpoints for API v2.

This package replaces the previous monolithic `views/clusters.py` module.
"""

from __future__ import annotations

from .crud import (
    create_cluster,
    delete_cluster,
    reset_sync_status,
    update_cluster,
    update_cluster_credentials,
)
from .discovery import discover_clusters, get_cluster_databases
from .read import get_cluster, list_clusters, sync_cluster

__all__ = [
    "create_cluster",
    "delete_cluster",
    "discover_clusters",
    "get_cluster",
    "get_cluster_databases",
    "list_clusters",
    "reset_sync_status",
    "sync_cluster",
    "update_cluster",
    "update_cluster_credentials",
]
