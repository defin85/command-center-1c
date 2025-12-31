"""
DRF Permission classes for database access control.
"""

from rest_framework.permissions import BasePermission

from apps.databases.models import PermissionLevel
from apps.databases.services import PermissionService


class HasDatabasePermission(BasePermission):
    """
    Object-level permission for Database model.

    Usage in ViewSet:
        permission_classes = [IsAuthenticated, HasDatabasePermission]
    """

    message = "You do not have permission to access this database."

    def has_object_permission(self, request, view, obj):
        # Action-based permission levels
        action_levels = {
            'list': PermissionLevel.VIEW,
            'retrieve': PermissionLevel.VIEW,
            'health_check': PermissionLevel.VIEW,
            'update': PermissionLevel.MANAGE,
            'partial_update': PermissionLevel.MANAGE,
            'destroy': PermissionLevel.ADMIN,
        }

        action = getattr(view, 'action', None)
        required_level = action_levels.get(action, PermissionLevel.VIEW)

        return PermissionService.has_permission(
            request.user,
            obj,
            required_level
        )


class HasClusterPermission(BasePermission):
    """Object-level permission for Cluster model."""

    message = "You do not have permission to access this cluster."

    def has_object_permission(self, request, view, obj):
        action_levels = {
            'list': PermissionLevel.VIEW,
            'retrieve': PermissionLevel.VIEW,
            'sync': PermissionLevel.OPERATE,
            'update': PermissionLevel.MANAGE,
            'partial_update': PermissionLevel.MANAGE,
            'destroy': PermissionLevel.ADMIN,
        }

        action = getattr(view, 'action', None)
        required_level = action_levels.get(action, PermissionLevel.VIEW)

        user_level = PermissionService.get_user_level_for_cluster(
            request.user,
            obj
        )

        return user_level is not None and user_level >= required_level


class CanExecuteOperation(BasePermission):
    """
    Permission for execute_operation endpoint.
    Requires OPERATE level on ALL target databases.
    """

    message = "You do not have permission to execute operations on one or more databases."

    def has_permission(self, request, view):
        database_ids = request.data.get('database_ids', [])

        if not database_ids:
            return True  # Will fail validation later

        all_allowed, denied = PermissionService.check_bulk_permission(
            request.user,
            [str(db_id) for db_id in database_ids],
            PermissionLevel.OPERATE
        )

        if not all_allowed:
            denied_str = ', '.join(denied[:5])
            self.message = f"Access denied for databases: {denied_str}"
            if len(denied) > 5:
                self.message += f" and {len(denied) - 5} more"

        return all_allowed
