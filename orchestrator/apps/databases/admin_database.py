from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html

from .admin_common import StaffWriteAdminMixin, health_check_action, logger
from .models import Database


@admin.register(Database)
class DatabaseAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    """Admin для Database model."""

    list_display = [
        "name",
        "cluster",
        "status_badge",
        "host",
        "port",
        "last_check_badge",
        "consecutive_failures",
        "avg_response_time",
        "created_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["name", "host", "description"]
    readonly_fields = [
        "id",
        "last_check",
        "last_check_status",
        "consecutive_failures",
        "avg_response_time",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        ("Основная информация", {"fields": ("id", "name", "description", "status", "cluster")}),
        ("Подключение", {"fields": ("host", "port", "base_name", "odata_url", "username", "password")}),
        (
            "Health Check",
            {"fields": ("last_check", "last_check_status", "consecutive_failures", "avg_response_time")},
        ),
        ("Connection Pool", {"fields": ("max_connections", "connection_timeout")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    actions = [health_check_action, "sync_from_cluster_action"]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "sync-from-cluster/",
                self.admin_site.admin_view(self.sync_from_cluster_view),
                name="databases_database_sync_from_cluster",
            ),
        ]
        return custom_urls + urls

    def sync_from_cluster_action(self, request, queryset):
        if not request.user.is_staff:
            messages.error(
                request,
                "Database import/sync is disabled in Django Admin. Use SPA (/clusters → Discover / Sync). Staff-only break-glass.",
            )
            return redirect("admin:databases_database_changelist")
        return redirect("admin:databases_database_sync_from_cluster")

    sync_from_cluster_action.short_description = "Sync databases from 1C cluster"

    def sync_from_cluster_view(self, request):
        if not request.user.is_staff:
            messages.error(request, "Only staff can sync databases from cluster.")
            return redirect("admin:databases_database_changelist")

        if request.method == "GET":
            context = {
                **self.admin_site.each_context(request),
                "title": "Sync Databases from 1C Cluster",
                "opts": self.model._meta,
            }
            return render(request, "admin/databases/sync_from_cluster_form.html", context)

        step = request.POST.get("step", "1")
        if step == "1":
            return self._handle_step1_get_database_list(request)
        if step == "2":
            return self._handle_step2_import_databases(request)

        messages.error(request, f"Invalid step: {step}")
        return redirect("admin:databases_database_changelist")

    def _handle_step1_get_database_list(self, request):
        messages.error(request, "Sync from cluster via Django Admin is disabled. Use SPA (/clusters).")
        return redirect("admin:databases_database_changelist")

    def _handle_step2_import_databases(self, request):
        sync_data = request.session.get("cluster_sync_data")
        if not sync_data:
            messages.error(request, "Session expired. Please start over.")
            return redirect("admin:databases_database_sync_from_cluster")

        import_timestamp_str = sync_data.get("import_timestamp")
        if import_timestamp_str:
            from dateutil import parser

            import_timestamp = parser.parse(import_timestamp_str)
            age_minutes = (timezone.now() - import_timestamp).total_seconds() / 60
            if age_minutes > 30:
                del request.session["cluster_sync_data"]
                messages.error(request, "Session expired (30 min timeout). Please start over.")
                return redirect("admin:databases_database_sync_from_cluster")

        selected_uuids = request.POST.getlist("selected_infobases")
        if not selected_uuids:
            messages.warning(request, "No databases selected.")
            if "cluster_sync_data" in request.session:
                del request.session["cluster_sync_data"]
            return redirect("admin:databases_database_changelist")

        logger.info("Step 2: Importing %s selected databases", len(selected_uuids))

        try:
            all_infobases = sync_data["infobases"]
            selected_infobases = [ib for ib in all_infobases if ib["uuid"] in selected_uuids]

            created, updated, errors = self._import_infobases(
                selected_infobases,
                sync_data.get("server", "localhost:1545"),
            )

            if "cluster_sync_data" in request.session:
                del request.session["cluster_sync_data"]

            if created > 0:
                messages.success(request, f"Successfully created {created} database(s).")
            if updated > 0:
                messages.info(request, f"Updated {updated} existing database(s).")
            if errors > 0:
                messages.error(
                    request,
                    f"Failed to import {errors} database(s). Check logs for details.",
                )

            return redirect("admin:databases_database_changelist")

        except Exception as e:
            logger.error("Error importing databases: %s", e, exc_info=True)

            if "cluster_sync_data" in request.session:
                del request.session["cluster_sync_data"]

            messages.error(request, f"Failed to import databases: {str(e)}")
            return redirect("admin:databases_database_sync_from_cluster")

    def _import_infobases(self, infobases: list, server: str) -> tuple:
        created = 0
        updated = 0
        errors = 0

        ras_host = server.split(":")[0] if ":" in server else server

        for ib in infobases:
            try:
                odata_url = self._build_odata_url(ib, ras_host)

                db_server = ib.get("db_server", "")
                host = self._parse_host(db_server) if db_server else ras_host

                database, is_created = Database.objects.update_or_create(
                    id=ib["uuid"],
                    defaults={
                        "name": ib["name"],
                        "description": ib.get("description", ""),
                        "host": host,
                        "port": 80,
                        "base_name": ib["name"],
                        "odata_url": odata_url,
                        "username": "",
                        "password": "",
                        "status": Database.STATUS_INACTIVE,
                        "version": "",
                        "metadata": {
                            "dbms": ib.get("dbms", ""),
                            "db_server": db_server,
                            "db_name": ib.get("db_name", ""),
                            "db_user": ib.get("db_user", ""),
                            "security_level": ib.get("security_level", 0),
                            "connection_string": ib.get("connection_string", ""),
                            "locale": ib.get("locale", ""),
                            "imported_from_cluster": True,
                            "import_timestamp": timezone.now().isoformat(),
                            "ras_server": server,
                        },
                    },
                )

                if is_created:
                    created += 1
                    logger.info("Created database: %s (%s)", database.name, database.id)
                else:
                    updated += 1
                    logger.info("Updated database: %s (%s)", database.name, database.id)

            except Exception as e:
                errors += 1
                logger.error(
                    "Failed to import infobase '%s': %s",
                    ib.get("name", "Unknown"),
                    e,
                    exc_info=True,
                )

        return created, updated, errors

    def _parse_host(self, db_server: str) -> str:
        if not db_server:
            return ""
        return db_server.split("\\\\")[0]

    def _build_odata_url(self, ib: dict, default_host: str) -> str:
        name = ib.get("name", "")
        if not name:
            return ""

        db_server = ib.get("db_server", "")
        host = self._parse_host(db_server) if db_server else default_host
        return f"http://{host}/{name}/odata/standard.odata/"

    def status_badge(self, obj):
        colors = {"active": "green", "inactive": "gray", "error": "red", "maintenance": "orange"}
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def last_check_badge(self, obj):
        if not obj.last_check:
            return "-"

        if obj.last_check_status == "success":
            return format_html(
                '<span style="color: green;">✓</span> {}',
                obj.last_check.strftime("%Y-%m-%d %H:%M"),
            )
        return format_html(
            '<span style="color: red;">✗</span> {}',
            obj.last_check.strftime("%Y-%m-%d %H:%M"),
        )

    last_check_badge.short_description = "Last Check"

