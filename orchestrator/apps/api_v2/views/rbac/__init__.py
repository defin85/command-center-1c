"""
RBAC management endpoints (API v2).

This package replaces the previous monolithic `views/rbac.py` module.
"""

from __future__ import annotations

from .artifacts import (
    bulk_grant_artifact_group_permission,
    bulk_revoke_artifact_group_permission,
    grant_artifact_group_permission,
    grant_artifact_permission,
    list_artifact_group_permissions,
    list_artifact_permissions,
    revoke_artifact_group_permission,
    revoke_artifact_permission,
)
from .audit import list_admin_audit
from .effective_access import get_effective_access
from .group_permissions_clusters import (
    bulk_grant_cluster_group_permission,
    bulk_revoke_cluster_group_permission,
    grant_cluster_group_permission,
    list_cluster_group_permissions,
    revoke_cluster_group_permission,
)
from .group_permissions_databases import (
    bulk_grant_database_group_permission,
    bulk_revoke_database_group_permission,
    grant_database_group_permission,
    list_database_group_permissions,
    revoke_database_group_permission,
)
from .operation_templates import (
    bulk_grant_operation_template_group_permission,
    bulk_revoke_operation_template_group_permission,
    grant_operation_template_group_permission,
    grant_operation_template_permission,
    list_operation_template_group_permissions,
    list_operation_template_permissions,
    revoke_operation_template_group_permission,
    revoke_operation_template_permission,
)
from .permissions_clusters_databases import (
    grant_cluster_permission,
    grant_database_permission,
    list_cluster_permissions,
    list_database_permissions,
    revoke_cluster_permission,
    revoke_database_permission,
)
from .refs import (
    ref_artifacts,
    ref_clusters,
    ref_databases,
    ref_operation_templates,
    ref_workflow_templates,
)
from .roles import (
    create_role,
    delete_role,
    list_capabilities,
    list_roles,
    set_role_capabilities,
    update_role,
)
from .user_roles import get_user_roles, set_user_roles
from .users import list_users, list_users_with_roles
from .workflow_templates import (
    bulk_grant_workflow_template_group_permission,
    bulk_revoke_workflow_template_group_permission,
    grant_workflow_template_group_permission,
    grant_workflow_template_permission,
    list_workflow_template_group_permissions,
    list_workflow_template_permissions,
    revoke_workflow_template_group_permission,
    revoke_workflow_template_permission,
)

__all__ = [
    "bulk_grant_artifact_group_permission",
    "bulk_grant_cluster_group_permission",
    "bulk_grant_database_group_permission",
    "bulk_grant_operation_template_group_permission",
    "bulk_grant_workflow_template_group_permission",
    "bulk_revoke_artifact_group_permission",
    "bulk_revoke_cluster_group_permission",
    "bulk_revoke_database_group_permission",
    "bulk_revoke_operation_template_group_permission",
    "bulk_revoke_workflow_template_group_permission",
    "create_role",
    "delete_role",
    "get_effective_access",
    "get_user_roles",
    "grant_artifact_group_permission",
    "grant_artifact_permission",
    "grant_cluster_group_permission",
    "grant_cluster_permission",
    "grant_database_group_permission",
    "grant_database_permission",
    "grant_operation_template_group_permission",
    "grant_operation_template_permission",
    "grant_workflow_template_group_permission",
    "grant_workflow_template_permission",
    "list_admin_audit",
    "list_artifact_group_permissions",
    "list_artifact_permissions",
    "list_capabilities",
    "list_cluster_group_permissions",
    "list_cluster_permissions",
    "list_database_group_permissions",
    "list_database_permissions",
    "list_operation_template_group_permissions",
    "list_operation_template_permissions",
    "list_roles",
    "list_users",
    "list_users_with_roles",
    "list_workflow_template_group_permissions",
    "list_workflow_template_permissions",
    "ref_artifacts",
    "ref_clusters",
    "ref_databases",
    "ref_operation_templates",
    "ref_workflow_templates",
    "revoke_artifact_group_permission",
    "revoke_artifact_permission",
    "revoke_cluster_group_permission",
    "revoke_cluster_permission",
    "revoke_database_group_permission",
    "revoke_database_permission",
    "revoke_operation_template_group_permission",
    "revoke_operation_template_permission",
    "revoke_workflow_template_group_permission",
    "revoke_workflow_template_permission",
    "set_role_capabilities",
    "set_user_roles",
    "update_role",
]
