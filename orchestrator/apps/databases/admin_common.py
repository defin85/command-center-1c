import logging

from django.contrib import admin, messages
from django.utils.html import format_html

from .services import DatabaseService

logger = logging.getLogger(__name__)


class StaffWriteAdminMixin:
    """
    Make Django Admin effectively read-only for non-staff.

    Operators should use SPA (/api/v2/*); Django Admin is break-glass for staff.
    """

    def has_view_permission(self, request, obj=None):
        return True

    def has_add_permission(self, request):
        return bool(getattr(request.user, "is_staff", False))

    def has_change_permission(self, request, obj=None):
        if getattr(request.user, "is_staff", False):
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        return bool(getattr(request.user, "is_staff", False))


@admin.action(description="Check health")
def health_check_action(modeladmin, request, queryset):
    """Action для health check баз из admin."""
    if not request.user.is_staff:
        messages.error(
            request,
            "Health check is disabled in Django Admin. Use SPA (/databases). Staff-only break-glass.",
        )
        return

    for db in queryset:
        result = DatabaseService.health_check_database(db)
        if result["healthy"]:
            modeladmin.message_user(
                request,
                f"✅ {db.name}: Healthy (response time: {result.get('response_time', 0):.3f}s)",
            )
        else:
            modeladmin.message_user(
                request,
                f"❌ {db.name}: {result.get('error', 'Unknown error')}",
                level="ERROR",
            )


@admin.action(description="Check health")
def check_cluster_service_status_action(modeladmin, request, queryset):
    """Проверить доступность RAS сервера для выбранных кластеров."""
    if not request.user.is_staff:
        messages.error(
            request,
            "Cluster health check is disabled in Django Admin. Use SPA (/system-status). Staff-only break-glass.",
        )
        return

    modeladmin.message_user(
        request,
        "Cluster health checks are handled by Go Worker operations. Use SPA (/clusters).",
        level=messages.WARNING,
    )


@admin.action(description="Sync infobases from cluster")
def sync_infobases_action(modeladmin, request, queryset):
    """
    Синхронизировать инфобазы из выбранных кластеров.

    Для каждого кластера отправляет sync_cluster в Go Worker.
    """
    if not request.user.is_staff:
        messages.error(
            request,
            "Cluster sync is disabled in Django Admin. Use SPA (/clusters). Staff-only break-glass.",
        )
        return

    if not queryset.exists():
        modeladmin.message_user(
            request,
            "⚠️ Выберите хотя бы один кластер для синхронизации",
            level=messages.WARNING,
        )
        return

    for cluster in queryset:
        try:
            from apps.operations.services import OperationsService

            result = OperationsService.enqueue_cluster_sync(
                cluster_id=str(cluster.id),
                created_by=request.user.username or "admin",
            )

            if result.success:
                modeladmin.message_user(
                    request,
                    f"✅ Cluster {cluster.name}: Sync queued (operation_id={result.operation_id})",
                    level=messages.SUCCESS,
                )
            else:
                modeladmin.message_user(
                    request,
                    f"❌ Cluster {cluster.name}: Sync enqueue failed - {result.error}",
                    level=messages.ERROR,
                )

        except Exception as exc:
            modeladmin.message_user(
                request,
                f"❌ Cluster {cluster.name}: Sync enqueue failed - {exc}",
                level=messages.ERROR,
            )


@admin.action(description="Reset sync status (unlock stuck clusters)")
def reset_sync_status_action(modeladmin, request, queryset):
    """
    Сбросить статус синхронизации для выбранных кластеров.

    Используется когда кластер "застрял" в статусе 'pending'
    после неудачной синхронизации.
    """
    if not request.user.is_staff:
        messages.error(
            request,
            "Reset sync status is disabled in Django Admin. Use SPA (/clusters). Staff-only break-glass.",
        )
        return

    reset_count = 0

    for cluster in queryset:
        old_status = cluster.last_sync_status
        if old_status == "pending":
            cluster.last_sync_status = "failed"
            cluster.last_sync_error = ""
            cluster.save(update_fields=["last_sync_status", "last_sync_error"])
            reset_count += 1

            modeladmin.message_user(
                request,
                format_html("🔓 <strong>{}</strong>: {} → failed", cluster.name, old_status),
                level=messages.SUCCESS,
            )
            logger.info(
                "Reset sync status for cluster %s: %s -> failed", cluster.name, old_status
            )
        else:
            modeladmin.message_user(
                request,
                format_html("ℹ️ <strong>{}</strong>: not pending (status: {})", cluster.name, old_status),
                level=messages.INFO,
            )

    if reset_count > 0:
        modeladmin.message_user(
            request,
            format_html("✅ Reset {} cluster(s)", reset_count),
            level=messages.SUCCESS,
        )

