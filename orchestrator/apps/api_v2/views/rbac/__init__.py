"""
RBAC management endpoints (API v2).

This package replaces the previous monolithic `views/rbac.py` module.
"""

from __future__ import annotations

import importlib
from typing import Any

_BASE = __name__
_EXPORTS: dict[str, tuple[str, str]] = {
    "bulk_grant_artifact_group_permission": (f"{_BASE}.artifacts", "bulk_grant_artifact_group_permission"),
    "bulk_revoke_artifact_group_permission": (f"{_BASE}.artifacts", "bulk_revoke_artifact_group_permission"),
    "grant_artifact_group_permission": (f"{_BASE}.artifacts", "grant_artifact_group_permission"),
    "grant_artifact_permission": (f"{_BASE}.artifacts", "grant_artifact_permission"),
    "list_artifact_group_permissions": (f"{_BASE}.artifacts", "list_artifact_group_permissions"),
    "list_artifact_permissions": (f"{_BASE}.artifacts", "list_artifact_permissions"),
    "revoke_artifact_group_permission": (f"{_BASE}.artifacts", "revoke_artifact_group_permission"),
    "revoke_artifact_permission": (f"{_BASE}.artifacts", "revoke_artifact_permission"),
    "list_admin_audit": (f"{_BASE}.audit", "list_admin_audit"),
    "get_effective_access": (f"{_BASE}.effective_access", "get_effective_access"),
    "bulk_grant_cluster_group_permission": (f"{_BASE}.group_permissions_clusters", "bulk_grant_cluster_group_permission"),
    "bulk_revoke_cluster_group_permission": (f"{_BASE}.group_permissions_clusters", "bulk_revoke_cluster_group_permission"),
    "grant_cluster_group_permission": (f"{_BASE}.group_permissions_clusters", "grant_cluster_group_permission"),
    "list_cluster_group_permissions": (f"{_BASE}.group_permissions_clusters", "list_cluster_group_permissions"),
    "revoke_cluster_group_permission": (f"{_BASE}.group_permissions_clusters", "revoke_cluster_group_permission"),
    "bulk_grant_database_group_permission": (f"{_BASE}.group_permissions_databases", "bulk_grant_database_group_permission"),
    "bulk_revoke_database_group_permission": (f"{_BASE}.group_permissions_databases", "bulk_revoke_database_group_permission"),
    "grant_database_group_permission": (f"{_BASE}.group_permissions_databases", "grant_database_group_permission"),
    "list_database_group_permissions": (f"{_BASE}.group_permissions_databases", "list_database_group_permissions"),
    "revoke_database_group_permission": (f"{_BASE}.group_permissions_databases", "revoke_database_group_permission"),
    "bulk_grant_operation_template_group_permission": (
        f"{_BASE}.operation_templates",
        "bulk_grant_operation_template_group_permission",
    ),
    "bulk_revoke_operation_template_group_permission": (
        f"{_BASE}.operation_templates",
        "bulk_revoke_operation_template_group_permission",
    ),
    "grant_operation_template_group_permission": (f"{_BASE}.operation_templates", "grant_operation_template_group_permission"),
    "grant_operation_template_permission": (f"{_BASE}.operation_templates", "grant_operation_template_permission"),
    "list_operation_template_group_permissions": (f"{_BASE}.operation_templates", "list_operation_template_group_permissions"),
    "list_operation_template_permissions": (f"{_BASE}.operation_templates", "list_operation_template_permissions"),
    "revoke_operation_template_group_permission": (f"{_BASE}.operation_templates", "revoke_operation_template_group_permission"),
    "revoke_operation_template_permission": (f"{_BASE}.operation_templates", "revoke_operation_template_permission"),
    "grant_cluster_permission": (f"{_BASE}.permissions_clusters_databases", "grant_cluster_permission"),
    "grant_database_permission": (f"{_BASE}.permissions_clusters_databases", "grant_database_permission"),
    "list_cluster_permissions": (f"{_BASE}.permissions_clusters_databases", "list_cluster_permissions"),
    "list_database_permissions": (f"{_BASE}.permissions_clusters_databases", "list_database_permissions"),
    "revoke_cluster_permission": (f"{_BASE}.permissions_clusters_databases", "revoke_cluster_permission"),
    "revoke_database_permission": (f"{_BASE}.permissions_clusters_databases", "revoke_database_permission"),
    "ref_artifacts": (f"{_BASE}.refs", "ref_artifacts"),
    "ref_clusters": (f"{_BASE}.refs", "ref_clusters"),
    "ref_databases": (f"{_BASE}.refs", "ref_databases"),
    "ref_operation_templates": (f"{_BASE}.refs", "ref_operation_templates"),
    "ref_workflow_templates": (f"{_BASE}.refs", "ref_workflow_templates"),
    "create_role": (f"{_BASE}.roles", "create_role"),
    "delete_role": (f"{_BASE}.roles", "delete_role"),
    "list_capabilities": (f"{_BASE}.roles", "list_capabilities"),
    "list_roles": (f"{_BASE}.roles", "list_roles"),
    "set_role_capabilities": (f"{_BASE}.roles", "set_role_capabilities"),
    "update_role": (f"{_BASE}.roles", "update_role"),
    "get_user_roles": (f"{_BASE}.user_roles", "get_user_roles"),
    "set_user_roles": (f"{_BASE}.user_roles", "set_user_roles"),
    "list_users": (f"{_BASE}.users", "list_users"),
    "list_users_with_roles": (f"{_BASE}.users", "list_users_with_roles"),
    "bulk_grant_workflow_template_group_permission": (
        f"{_BASE}.workflow_templates",
        "bulk_grant_workflow_template_group_permission",
    ),
    "bulk_revoke_workflow_template_group_permission": (
        f"{_BASE}.workflow_templates",
        "bulk_revoke_workflow_template_group_permission",
    ),
    "grant_workflow_template_group_permission": (f"{_BASE}.workflow_templates", "grant_workflow_template_group_permission"),
    "grant_workflow_template_permission": (f"{_BASE}.workflow_templates", "grant_workflow_template_permission"),
    "list_workflow_template_group_permissions": (f"{_BASE}.workflow_templates", "list_workflow_template_group_permissions"),
    "list_workflow_template_permissions": (f"{_BASE}.workflow_templates", "list_workflow_template_permissions"),
    "revoke_workflow_template_group_permission": (f"{_BASE}.workflow_templates", "revoke_workflow_template_group_permission"),
    "revoke_workflow_template_permission": (f"{_BASE}.workflow_templates", "revoke_workflow_template_permission"),
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
