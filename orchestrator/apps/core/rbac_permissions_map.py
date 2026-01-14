"""
Object-level RBAC mapping for Django permissions.

This module defines how Django permission codes (capabilities) map to
required RBAC PermissionLevel on concrete domain objects.

Notes:
- Capabilities are standard Django permissions assigned to users/groups.
- Scope/levels are stored in RBAC bindings (PermissionLevel) and resolved
  by domain services (PermissionService / TemplatePermissionService / ArtifactPermissionService).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from apps.core import permission_codes as perms
from apps.databases.models import PermissionLevel


@dataclass(frozen=True)
class ObjectPermissionRule:
    required_level: int


OBJECT_PERMISSION_RULES: Final[dict[str, ObjectPermissionRule]] = {
    # Databases / Clusters
    perms.PERM_DATABASES_VIEW_CLUSTER: ObjectPermissionRule(PermissionLevel.VIEW),
    perms.PERM_DATABASES_OPERATE_CLUSTER: ObjectPermissionRule(PermissionLevel.OPERATE),
    perms.PERM_DATABASES_MANAGE_CLUSTER: ObjectPermissionRule(PermissionLevel.MANAGE),
    perms.PERM_DATABASES_ADMIN_CLUSTER: ObjectPermissionRule(PermissionLevel.ADMIN),

    perms.PERM_DATABASES_VIEW_DATABASE: ObjectPermissionRule(PermissionLevel.VIEW),
    perms.PERM_DATABASES_OPERATE_DATABASE: ObjectPermissionRule(PermissionLevel.OPERATE),
    perms.PERM_DATABASES_MANAGE_DATABASE: ObjectPermissionRule(PermissionLevel.MANAGE),
    perms.PERM_DATABASES_ADMIN_DATABASE: ObjectPermissionRule(PermissionLevel.ADMIN),

    # Templates / Workflows
    perms.PERM_TEMPLATES_VIEW_OPERATION_TEMPLATE: ObjectPermissionRule(PermissionLevel.VIEW),
    perms.PERM_TEMPLATES_MANAGE_OPERATION_TEMPLATE: ObjectPermissionRule(PermissionLevel.MANAGE),

    perms.PERM_TEMPLATES_VIEW_WORKFLOW_TEMPLATE: ObjectPermissionRule(PermissionLevel.VIEW),
    perms.PERM_TEMPLATES_MANAGE_WORKFLOW_TEMPLATE: ObjectPermissionRule(PermissionLevel.MANAGE),
    perms.PERM_TEMPLATES_EXECUTE_WORKFLOW_TEMPLATE: ObjectPermissionRule(PermissionLevel.OPERATE),

    # Artifacts
    perms.PERM_ARTIFACTS_VIEW_ARTIFACT: ObjectPermissionRule(PermissionLevel.VIEW),
    perms.PERM_ARTIFACTS_MANAGE_ARTIFACT: ObjectPermissionRule(PermissionLevel.MANAGE),
    perms.PERM_ARTIFACTS_PURGE_ARTIFACT: ObjectPermissionRule(PermissionLevel.ADMIN),

    # ArtifactVersion permissions resolve against Artifact scope (inheritance)
    perms.PERM_ARTIFACTS_VIEW_ARTIFACT_VERSION: ObjectPermissionRule(PermissionLevel.VIEW),
    perms.PERM_ARTIFACTS_UPLOAD_ARTIFACT_VERSION: ObjectPermissionRule(PermissionLevel.OPERATE),
    perms.PERM_ARTIFACTS_DOWNLOAD_ARTIFACT_VERSION: ObjectPermissionRule(PermissionLevel.VIEW),
}
