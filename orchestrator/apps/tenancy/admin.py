from django.contrib import admin

from .models import Tenant, TenantMember, UserTenantPreference


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("id", "slug", "name", "created_at", "updated_at")
    search_fields = ("slug", "name")
    ordering = ("name",)


@admin.register(TenantMember)
class TenantMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "user", "role", "created_at")
    search_fields = ("tenant__slug", "tenant__name", "user__username", "user__email")
    list_filter = ("role", "tenant")


@admin.register(UserTenantPreference)
class UserTenantPreferenceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "active_tenant", "updated_at")
    search_fields = ("user__username", "user__email", "active_tenant__slug", "active_tenant__name")
    list_filter = ("active_tenant",)

