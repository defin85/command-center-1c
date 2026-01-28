"""Django Admin для databases app."""

from django.contrib import admin

from .admin_common import StaffWriteAdminMixin
from .models import (
    ClusterGroupPermission,
    ClusterPermission,
    DatabaseGroup,
    DatabaseGroupPermission,
    DatabasePermission,
    StatusHistory,
)
from . import admin_cluster as _admin_cluster  # noqa: F401
from . import admin_database as _admin_database  # noqa: F401


@admin.register(DatabaseGroup)
class DatabaseGroupAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    """Admin для DatabaseGroup model."""

    list_display = ["name", "databases_count", "created_at"]
    search_fields = ["name", "description"]
    filter_horizontal = ["databases"]

    def databases_count(self, obj):
        return obj.databases.count()

    databases_count.short_description = "Databases"


@admin.register(ClusterPermission)
class ClusterPermissionAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    """Admin для ClusterPermission model (RBAC)."""

    list_display = ["user", "cluster", "level", "granted_by", "granted_at"]
    list_filter = ["level", "cluster"]
    search_fields = ["user__username", "cluster__name"]


@admin.register(DatabasePermission)
class DatabasePermissionAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    """Admin для DatabasePermission model (RBAC)."""

    list_display = ["user", "database", "level", "granted_by", "granted_at"]
    list_filter = ["level", "database"]
    search_fields = ["user__username", "database__name"]


@admin.register(ClusterGroupPermission)
class ClusterGroupPermissionAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    """Admin для ClusterGroupPermission model (RBAC)."""

    list_display = ["group", "cluster", "level", "granted_by", "granted_at"]
    list_filter = ["level", "cluster"]
    search_fields = ["group__name", "cluster__name"]


@admin.register(DatabaseGroupPermission)
class DatabaseGroupPermissionAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    """Admin для DatabaseGroupPermission model (RBAC)."""

    list_display = ["group", "database", "level", "granted_by", "granted_at"]
    list_filter = ["level", "database"]
    search_fields = ["group__name", "database__name"]


@admin.register(StatusHistory)
class StatusHistoryAdmin(admin.ModelAdmin):
    """Admin для StatusHistory model."""

    list_display = ["content_object", "old_status", "new_status", "changed_at"]
    list_filter = ["content_type", "new_status"]
    search_fields = ["object_id", "reason"]
    readonly_fields = ["changed_at"]

