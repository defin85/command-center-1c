from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html

from .admin_common import (
    StaffWriteAdminMixin,
    check_cluster_service_status_action,
    reset_sync_status_action,
    sync_infobases_action,
)
from .models import Cluster


@admin.register(Cluster)
class ClusterAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    """Admin для Cluster model."""

    list_display = [
        "name",
        "ras_server",
        "status_badge",
        "health_badge",
        "infobase_count",
        "healthy_infobase_count",
        "last_sync",
        "last_sync_status",
        "created_at",
    ]
    list_filter = ["status", "last_sync_status", "created_at"]
    search_fields = ["name", "description", "ras_server", "ras_host", "rmngr_host"]
    readonly_fields = [
        "last_sync",
        "last_sync_status",
        "last_sync_error",
        "consecutive_failures",
        "last_health_check",
        "created_at",
        "updated_at",
        "infobase_count",
        "healthy_infobase_count",
        "ras_server",
    ]

    fieldsets = (
        ("Основная информация", {"fields": ("name", "description", "status")}),
        (
            "RAS Connection",
            {
                "fields": (
                    "ras_host",
                    "ras_port",
                    "ras_server",
                    "ras_cluster_uuid",
                    "cluster_user",
                    "cluster_pwd",
                ),
                "description": "ras_cluster_uuid заполняется автоматически при первой синхронизации. "
                "Укажите вручную если на RAS сервере несколько кластеров.",
            },
        ),
        (
            "1C Server Ports",
            {
                "fields": (
                    "rmngr_host",
                    "rmngr_port",
                    "ragent_host",
                    "ragent_port",
                    "rphost_port_from",
                    "rphost_port_to",
                ),
                "description": "RMNGR используется для пакетного запуска (Designer/IBCMD).",
            },
        ),
        ("Cluster Service", {"fields": ("cluster_service_url",)}),
        ("Sync Status", {"fields": ("last_sync", "last_sync_status", "last_sync_error")}),
        ("Health Check", {"fields": ("consecutive_failures", "last_health_check")}),
        ("Statistics", {"fields": ("infobase_count", "healthy_infobase_count")}),
        ("Metadata", {"fields": ("metadata",), "classes": ("collapse",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    actions = [
        check_cluster_service_status_action,
        sync_infobases_action,
        reset_sync_status_action,
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _infobase_count=Count("databases"),
            _healthy_infobase_count=Count(
                "databases",
                filter=Q(databases__last_check_status="ok", databases__status="active"),
            ),
        )

    def infobase_count(self, obj):
        return obj._infobase_count

    infobase_count.admin_order_field = "_infobase_count"
    infobase_count.short_description = "Infobases"

    def healthy_infobase_count(self, obj):
        return obj._healthy_infobase_count

    healthy_infobase_count.admin_order_field = "_healthy_infobase_count"
    healthy_infobase_count.short_description = "Healthy"

    def status_badge(self, obj):
        colors = {
            "active": "green",
            "inactive": "gray",
            "error": "red",
            "maintenance": "orange",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def health_badge(self, obj):
        if not obj.last_health_check:
            return format_html('<span style="color: {};">●</span> {}', "gray", "Never checked")

        if obj.consecutive_failures == 0:
            color = "green"
            text = "✓ Healthy"
        elif obj.consecutive_failures < 3:
            color = "orange"
            text = f"⚠ {obj.consecutive_failures} failures"
        else:
            color = "red"
            text = f"✗ {obj.consecutive_failures} failures"

        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, text)

    health_badge.short_description = "Health Check"

