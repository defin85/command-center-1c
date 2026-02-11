"""
RBAC permission backend bridging Django permissions and object-level scope.

This backend enforces:
1) Capability: user/group must have Django permission codename (ModelBackend).
2) Scope: for supported permissions, user must have required PermissionLevel
   on the target object (RBAC bindings).

Staff bypass:
- `is_staff` users are treated as full-access for both capability and scope.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

from django.contrib.auth.backends import ModelBackend

from apps.core import permission_codes as perms
from apps.core.rbac_permissions_map import OBJECT_PERMISSION_RULES

logger = logging.getLogger(__name__)

_RBAC_APP_LABELS = frozenset({"databases", "templates", "artifacts", "operations"})


class RBACPermissionBackend(ModelBackend):
    """
    Permission backend implementing user.has_perm(<perm>, obj) over RBAC bindings.
    """

    def has_perm(self, user_obj, perm, obj=None):  # noqa: D401
        if not user_obj or not getattr(user_obj, "is_authenticated", False):
            return False

        if getattr(user_obj, "is_staff", False):
            return True

        # Capability (global) must be granted via Django permissions.
        if not super().has_perm(user_obj, perm):
            return False

        # Non-object permissions: capability is enough.
        if obj is None:
            return True

        rule = OBJECT_PERMISSION_RULES.get(perm)
        if rule is None:
            app_label = perm.split(".", 1)[0] if "." in perm else ""
            if app_label in _RBAC_APP_LABELS:
                logger.warning(
                    "Unknown object-level permission mapping",
                    extra={"perm": perm, "obj_type": type(obj).__name__},
                )
                return False
            # Unknown object-level rule for non-RBAC apps -> do not add scope restriction.
            return True

        required_level = int(rule.required_level)

        # Resolve scope/level by domain object type.
        from apps.databases.models import Cluster, Database
        from apps.databases.services import PermissionService

        if isinstance(obj, Database):
            return PermissionService.has_permission(user_obj, obj, required_level)

        if isinstance(obj, Cluster):
            allow_database_permissions = perm == perms.PERM_DATABASES_VIEW_CLUSTER
            return PermissionService.has_cluster_permission(
                user_obj,
                obj,
                required_level,
                allow_database_permissions=allow_database_permissions,
            )

        from apps.templates.models import OperationExposure
        from apps.templates.rbac import TemplatePermissionService
        from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate

        if isinstance(obj, OperationExposure):
            if obj.surface != OperationExposure.SURFACE_TEMPLATE:
                return False
            return TemplatePermissionService.has_operation_template_access(
                user_obj,
                SimpleNamespace(id=str(obj.alias)),
                required_level,
            )

        if isinstance(obj, WorkflowTemplate):
            return TemplatePermissionService.has_workflow_template_access(
                user_obj, obj, required_level
            )

        if isinstance(obj, WorkflowExecution):
            level = TemplatePermissionService.get_user_level_for_workflow_execution(
                user_obj, obj
            )
            return level is not None and level >= required_level

        from apps.artifacts.models import Artifact, ArtifactAlias, ArtifactVersion
        from apps.artifacts.rbac import ArtifactPermissionService

        if isinstance(obj, Artifact):
            return ArtifactPermissionService.has_artifact_access(
                user_obj, obj, required_level
            )

        if isinstance(obj, ArtifactVersion):
            level = ArtifactPermissionService.get_user_level_for_artifact_version(
                user_obj, obj
            )
            return level is not None and level >= required_level

        if isinstance(obj, ArtifactAlias):
            level = ArtifactPermissionService.get_user_level_for_artifact_alias(
                user_obj, obj
            )
            return level is not None and level >= required_level

        return False

    def has_module_perms(self, user_obj, app_label):  # noqa: D401
        if not user_obj or not getattr(user_obj, "is_authenticated", False):
            return False
        if getattr(user_obj, "is_staff", False):
            return True
        return super().has_module_perms(user_obj, app_label)
