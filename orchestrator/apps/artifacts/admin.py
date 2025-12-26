from django.contrib import admin

from .models import Artifact, ArtifactVersion, ArtifactAlias, ArtifactUsage


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
    list_display = ("artifact", "version", "operation", "database", "used_at")
    list_filter = ("artifact",)
