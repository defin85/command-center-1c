from django.contrib import admin

from .models import (
    Artifact,
    ArtifactAlias,
    ArtifactGroupPermission,
    ArtifactPermission,
    ArtifactUsage,
    ArtifactVersion,
)


@admin.register(Artifact)
class ArtifactAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "is_versioned", "created_at", "created_by")
    list_filter = ("kind", "is_versioned")
    search_fields = ("name",)


@admin.register(ArtifactVersion)
class ArtifactVersionAdmin(admin.ModelAdmin):
    list_display = ("artifact", "version", "filename", "size", "created_at", "created_by")
    list_filter = ("artifact",)
    search_fields = ("artifact__name", "version", "filename")


@admin.register(ArtifactAlias)
class ArtifactAliasAdmin(admin.ModelAdmin):
    list_display = ("artifact", "alias", "version", "updated_at")
    search_fields = ("artifact__name", "alias")


@admin.register(ArtifactUsage)
class ArtifactUsageAdmin(admin.ModelAdmin):
    list_display = ("artifact", "version", "operation", "workflow_execution", "database", "used_at")
    list_filter = ("artifact",)


@admin.register(ArtifactPermission)
class ArtifactPermissionAdmin(admin.ModelAdmin):
    list_display = ("user", "artifact", "level", "granted_by", "granted_at")
    list_filter = ("level", "artifact__kind")
    search_fields = ("user__username", "artifact__name")
    autocomplete_fields = ("user", "artifact")
    readonly_fields = ("granted_at",)


@admin.register(ArtifactGroupPermission)
class ArtifactGroupPermissionAdmin(admin.ModelAdmin):
    list_display = ("group", "artifact", "level", "granted_by", "granted_at")
    list_filter = ("level", "artifact__kind")
    search_fields = ("group__name", "artifact__name")
    autocomplete_fields = ("group", "artifact")
    readonly_fields = ("granted_at",)
