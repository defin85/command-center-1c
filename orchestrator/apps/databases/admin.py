"""Django Admin для databases app."""

import logging
from django.contrib import admin
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import path
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Q
from .models import (
    Cluster, Database, DatabaseGroup, StatusHistory,
    ClusterGroupPermission, ClusterPermission,
    DatabaseGroupPermission, DatabasePermission,
)
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


@admin.action(description='Check health')
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
        if result['healthy']:
            modeladmin.message_user(
                request,
                f"✅ {db.name}: Healthy (response time: {result.get('response_time', 0):.3f}s)"
            )
        else:
            modeladmin.message_user(
                request,
                f"❌ {db.name}: {result.get('error', 'Unknown error')}",
                level='ERROR'
            )


@admin.action(description='Check health')
def check_cluster_service_status_action(modeladmin, request, queryset):
    """
    Проверить доступность RAS сервера для выбранных кластеров.
    """
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


@admin.action(description='Sync infobases from cluster')
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
            '⚠️ Выберите хотя бы один кластер для синхронизации',
            level=messages.WARNING
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


@admin.action(description='Reset sync status (unlock stuck clusters)')
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
        if old_status == 'pending':
            cluster.last_sync_status = 'failed'
            cluster.last_sync_error = ''
            cluster.save(update_fields=['last_sync_status', 'last_sync_error'])
            reset_count += 1

            modeladmin.message_user(
                request,
                format_html(
                    '🔓 <strong>{}</strong>: {} → failed',
                    cluster.name,
                    old_status
                ),
                level=messages.SUCCESS
            )
            logger.info(f"Reset sync status for cluster {cluster.name}: {old_status} -> failed")
        else:
            modeladmin.message_user(
                request,
                format_html(
                    'ℹ️ <strong>{}</strong>: not pending (status: {})',
                    cluster.name
                    , old_status
                ),
                level=messages.INFO
            )

    if reset_count > 0:
        modeladmin.message_user(
            request,
            format_html(
                '✅ Reset {} cluster(s)',
                reset_count
            ),
            level=messages.SUCCESS
        )


@admin.register(Cluster)
class ClusterAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    """Admin для Cluster model."""

    list_display = [
        'name',
        'ras_server',
        'status_badge',
        'health_badge',
        'infobase_count',
        'healthy_infobase_count',
        'last_sync',
        'last_sync_status',
        'created_at'
    ]
    list_filter = ['status', 'last_sync_status', 'created_at']
    search_fields = ['name', 'description', 'ras_server', 'ras_host', 'rmngr_host']
    readonly_fields = [
        'last_sync',
        'last_sync_status',
        'last_sync_error',
        'consecutive_failures',
        'last_health_check',
        'created_at',
        'updated_at',
        'infobase_count',
        'healthy_infobase_count',
        'ras_server',
    ]

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description', 'status')
        }),
        ('RAS Connection', {
            'fields': ('ras_host', 'ras_port', 'ras_server', 'ras_cluster_uuid', 'cluster_user', 'cluster_pwd'),
            'description': 'ras_cluster_uuid заполняется автоматически при первой синхронизации. '
                           'Укажите вручную если на RAS сервере несколько кластеров.'
        }),
        ('1C Server Ports', {
            'fields': ('rmngr_host', 'rmngr_port', 'ragent_host', 'ragent_port', 'rphost_port_from', 'rphost_port_to'),
            'description': 'RMNGR используется для пакетного запуска (Designer/IBCMD).'
        }),
        ('Cluster Service', {
            'fields': ('cluster_service_url',)
        }),
        ('Sync Status', {
            'fields': (
                'last_sync',
                'last_sync_status',
                'last_sync_error'
            )
        }),
        ('Health Check', {
            'fields': (
                'consecutive_failures',
                'last_health_check'
            )
        }),
        ('Statistics', {
            'fields': ('infobase_count', 'healthy_infobase_count')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    actions = [check_cluster_service_status_action, sync_infobases_action, reset_sync_status_action]

    def get_queryset(self, request):
        """Optimize queries with annotate to prevent N+1 queries."""
        qs = super().get_queryset(request)
        return qs.annotate(
            _infobase_count=Count('databases'),
            _healthy_infobase_count=Count(
                'databases',
                filter=Q(databases__last_check_status='ok', databases__status='active')
            )
        )

    def infobase_count(self, obj):
        """Use pre-computed count from annotate."""
        return obj._infobase_count
    infobase_count.admin_order_field = '_infobase_count'
    infobase_count.short_description = 'Infobases'

    def healthy_infobase_count(self, obj):
        """Use pre-computed count from annotate."""
        return obj._healthy_infobase_count
    healthy_infobase_count.admin_order_field = '_healthy_infobase_count'
    healthy_infobase_count.short_description = 'Healthy'

    def status_badge(self, obj):
        """Цветной badge для статуса."""
        colors = {
            'active': 'green',
            'inactive': 'gray',
            'error': 'red',
            'maintenance': 'orange'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def health_badge(self, obj):
        """Badge для health check статуса."""
        if not obj.last_health_check:
            return format_html(
                '<span style="color: {};">●</span> {}',
                'gray',
                'Never checked',
            )

        if obj.consecutive_failures == 0:
            color = 'green'
            text = '✓ Healthy'
        elif obj.consecutive_failures < 3:
            color = 'orange'
            text = f'⚠ {obj.consecutive_failures} failures'
        else:
            color = 'red'
            text = f'✗ {obj.consecutive_failures} failures'

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, text
        )
    health_badge.short_description = 'Health Check'


@admin.register(Database)
class DatabaseAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    """Admin для Database model."""

    list_display = [
        'name',
        'cluster',
        'status_badge',
        'host',
        'port',
        'last_check_badge',
        'consecutive_failures',
        'avg_response_time',
        'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'host', 'description']
    readonly_fields = [
        'id',
        'last_check',
        'last_check_status',
        'consecutive_failures',
        'avg_response_time',
        'created_at',
        'updated_at'
    ]

    fieldsets = (
        ('Основная информация', {
            'fields': ('id', 'name', 'description', 'status', 'cluster')
        }),
        ('Подключение', {
            'fields': ('host', 'port', 'base_name', 'odata_url', 'username', 'password')
        }),
        ('Health Check', {
            'fields': (
                'last_check',
                'last_check_status',
                'consecutive_failures',
                'avg_response_time'
            )
        }),
        ('Connection Pool', {
            'fields': ('max_connections', 'connection_timeout')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    actions = [
        health_check_action,
        'sync_from_cluster_action'
    ]

    def get_urls(self):
        """Add custom URL for sync from cluster."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'sync-from-cluster/',
                self.admin_site.admin_view(self.sync_from_cluster_view),
                name='databases_database_sync_from_cluster',
            ),
        ]
        return custom_urls + urls

    def sync_from_cluster_action(self, request, queryset):
        """
        Admin action to trigger sync from 1C cluster.

        Redirects to intermediate page with cluster connection form.
        """
        if not request.user.is_staff:
            messages.error(
                request,
                "Database import/sync is disabled in Django Admin. Use SPA (/clusters → Discover / Sync). Staff-only break-glass.",
            )
            return redirect('admin:databases_database_changelist')
        return redirect('admin:databases_database_sync_from_cluster')

    sync_from_cluster_action.short_description = 'Sync databases from 1C cluster'

    def sync_from_cluster_view(self, request):
        """
        Intermediate page for syncing databases from 1C cluster.

        Workflow:
        1. GET - show form with cluster connection parameters
        2. POST step=1 - enqueue worker sync, show database list
        3. POST step=2 - import selected databases

        This is a three-step process:
        - Step 1: User enters cluster connection details
        - Step 2: System retrieves database list, user selects which to import
        - Step 3: System imports selected databases
        """
        # Check permissions
        if not request.user.is_staff:
            messages.error(request, 'Only staff can sync databases from cluster.')
            return redirect('admin:databases_database_changelist')

        # Step 1: Show form for cluster connection parameters
        if request.method == 'GET':
            context = {
                **self.admin_site.each_context(request),
                'title': 'Sync Databases from 1C Cluster',
                'opts': self.model._meta,
            }
            return render(
                request,
                'admin/databases/sync_from_cluster_form.html',
                context
            )

        # POST request - determine step
        step = request.POST.get('step', '1')

        # Step 2: Get database list from cluster
        if step == '1':
            return self._handle_step1_get_database_list(request)

        # Step 3: Import selected databases
        elif step == '2':
            return self._handle_step2_import_databases(request)

        else:
            messages.error(request, f'Invalid step: {step}')
            return redirect('admin:databases_database_changelist')

    def _handle_step1_get_database_list(self, request):
        """Handle step 1: Disabled (RAS Adapter removed)."""
        messages.error(
            request,
            'Sync from cluster via Django Admin is disabled. Use SPA (/clusters).'
        )
        return redirect('admin:databases_database_changelist')

    def _handle_step2_import_databases(self, request):
        """Handle step 2: Import selected databases."""
        # Get sync data from session
        sync_data = request.session.get('cluster_sync_data')
        if not sync_data:
            messages.error(request, 'Session expired. Please start over.')
            return redirect('admin:databases_database_sync_from_cluster')

        # Check if session data is too old (30 minutes timeout)
        import_timestamp_str = sync_data.get('import_timestamp')
        if import_timestamp_str:
            from dateutil import parser
            import_timestamp = parser.parse(import_timestamp_str)
            age_minutes = (timezone.now() - import_timestamp).total_seconds() / 60
            if age_minutes > 30:
                # Clear stale session data
                del request.session['cluster_sync_data']
                messages.error(request, 'Session expired (30 min timeout). Please start over.')
                return redirect('admin:databases_database_sync_from_cluster')

        # Get selected database UUIDs
        selected_uuids = request.POST.getlist('selected_infobases')
        if not selected_uuids:
            messages.warning(request, 'No databases selected.')
            # Clear session data before redirect
            if 'cluster_sync_data' in request.session:
                del request.session['cluster_sync_data']
            return redirect('admin:databases_database_changelist')

        logger.info(f"Step 2: Importing {len(selected_uuids)} selected databases")

        try:
            # Filter selected infobases
            all_infobases = sync_data['infobases']
            selected_infobases = [
                ib for ib in all_infobases if ib['uuid'] in selected_uuids
            ]

            # Import databases
            created, updated, errors = self._import_infobases(
                selected_infobases,
                sync_data.get('server', 'localhost:1545')
            )

            # Clear session data after successful import
            if 'cluster_sync_data' in request.session:
                del request.session['cluster_sync_data']

            # Show results
            if created > 0:
                messages.success(
                    request,
                    f'Successfully created {created} database(s).'
                )
            if updated > 0:
                messages.info(
                    request,
                    f'Updated {updated} existing database(s).'
                )
            if errors > 0:
                messages.error(
                    request,
                    f'Failed to import {errors} database(s). Check logs for details.'
                )

            return redirect('admin:databases_database_changelist')

        except Exception as e:
            logger.error(f"Error importing databases: {e}", exc_info=True)

            # CLEANUP: Clear session data on error
            if 'cluster_sync_data' in request.session:
                del request.session['cluster_sync_data']

            messages.error(request, f'Failed to import databases: {str(e)}')
            return redirect('admin:databases_database_sync_from_cluster')

    def _import_infobases(self, infobases: list, server: str) -> tuple:
        """
        Import infobases into Database model.

        Args:
            infobases: List of infobase dictionaries from worker sync
            server: RAS server address (for building OData URLs)

        Returns:
            Tuple of (created_count, updated_count, error_count)
        """
        created = 0
        updated = 0
        errors = 0

        # Extract host from server (remove port)
        ras_host = server.split(':')[0] if ':' in server else server

        for ib in infobases:
            try:
                # Build OData URL
                odata_url = self._build_odata_url(ib, ras_host)

                # Parse host from db_server
                db_server = ib.get('db_server', '')
                host = self._parse_host(db_server) if db_server else ras_host

                # Create or update database
                database, is_created = Database.objects.update_or_create(
                    id=ib['uuid'],
                    defaults={
                        'name': ib['name'],
                        'description': ib.get('description', ''),
                        'host': host,
                        'port': 80,  # Default HTTP port (OData)
                        'base_name': ib['name'],
                        'odata_url': odata_url,
                        'username': '',  # Must be set manually
                        'password': '',  # Must be set manually
                        'status': Database.STATUS_INACTIVE,
                        'version': '',
                        'metadata': {
                            'dbms': ib.get('dbms', ''),
                            'db_server': db_server,
                            'db_name': ib.get('db_name', ''),
                            'db_user': ib.get('db_user', ''),
                            'security_level': ib.get('security_level', 0),
                            'connection_string': ib.get('connection_string', ''),
                            'locale': ib.get('locale', ''),
                            'imported_from_cluster': True,
                            'import_timestamp': timezone.now().isoformat(),
                            'ras_server': server,
                        }
                    }
                )

                if is_created:
                    created += 1
                    logger.info(f"Created database: {database.name} ({database.id})")
                else:
                    updated += 1
                    logger.info(f"Updated database: {database.name} ({database.id})")

            except Exception as e:
                errors += 1
                logger.error(
                    f"Failed to import infobase '{ib.get('name', 'Unknown')}': {e}",
                    exc_info=True
                )

        return created, updated, errors

    def _parse_host(self, db_server: str) -> str:
        """
        Extract host from db_server string.

        Examples:
            'sql-server\\SQLEXPRESS' -> 'sql-server'
            'localhost' -> 'localhost'
            'db.example.com\\instance' -> 'db.example.com'

        Args:
            db_server: Database server string from 1C

        Returns:
            Host part (without instance name)
        """
        if not db_server:
            return ''
        # Split by backslash (SQL Server instance separator)
        return db_server.split('\\')[0]

    def _build_odata_url(self, ib: dict, default_host: str) -> str:
        """
        Build OData URL for infobase.

        Args:
            ib: Infobase dictionary
            default_host: Default host if db_server is not available

        Returns:
            OData URL
        """
        name = ib.get('name', '')
        if not name:
            return ''

        # Try to get host from db_server
        db_server = ib.get('db_server', '')
        if db_server:
            host = self._parse_host(db_server)
        else:
            host = default_host

        # Build OData URL
        # Format: http://host/base_name/odata/standard.odata/
        return f"http://{host}/{name}/odata/standard.odata/"

    def status_badge(self, obj):
        """Цветной badge для статуса."""
        colors = {
            'active': 'green',
            'inactive': 'gray',
            'error': 'red',
            'maintenance': 'orange'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def last_check_badge(self, obj):
        """Badge для last check."""
        if not obj.last_check:
            return '-'

        if obj.last_check_status == 'success':
            return format_html(
                '<span style="color: green;">✓</span> {}',
                obj.last_check.strftime('%Y-%m-%d %H:%M')
            )
        else:
            return format_html(
                '<span style="color: red;">✗</span> {}',
                obj.last_check.strftime('%Y-%m-%d %H:%M')
            )
    last_check_badge.short_description = 'Last Check'


@admin.register(DatabaseGroup)
class DatabaseGroupAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    """Admin для DatabaseGroup model."""

    list_display = ['name', 'databases_count', 'created_at']
    search_fields = ['name', 'description']
    filter_horizontal = ['databases']

    def databases_count(self, obj):
        """Количество баз в группе."""
        return obj.databases.count()
    databases_count.short_description = 'Databases'


@admin.register(ClusterPermission)
class ClusterPermissionAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    """Admin для ClusterPermission model (RBAC)."""

    list_display = ['user', 'cluster', 'level', 'granted_by', 'granted_at']
    list_filter = ['level', 'cluster']
    search_fields = ['user__username', 'cluster__name']
    autocomplete_fields = ['user', 'cluster']
    readonly_fields = ['granted_at']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.granted_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DatabasePermission)
class DatabasePermissionAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    """Admin для DatabasePermission model (RBAC)."""

    list_display = ['user', 'database', 'level', 'granted_by', 'granted_at']
    list_filter = ['level', 'database__cluster']
    search_fields = ['user__username', 'database__name']
    autocomplete_fields = ['user', 'database']
    readonly_fields = ['granted_at']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.granted_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ClusterGroupPermission)
class ClusterGroupPermissionAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    """Admin for ClusterGroupPermission model (RBAC)."""

    list_display = ['group', 'cluster', 'level', 'granted_by', 'granted_at']
    list_filter = ['level', 'cluster']
    search_fields = ['group__name', 'cluster__name']
    autocomplete_fields = ['group', 'cluster']
    readonly_fields = ['granted_at']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.granted_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DatabaseGroupPermission)
class DatabaseGroupPermissionAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    """Admin for DatabaseGroupPermission model (RBAC)."""

    list_display = ['group', 'database', 'level', 'granted_by', 'granted_at']
    list_filter = ['level', 'database__cluster']
    search_fields = ['group__name', 'database__name']
    autocomplete_fields = ['group', 'database']
    readonly_fields = ['granted_at']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.granted_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(StatusHistory)
class StatusHistoryAdmin(admin.ModelAdmin):
    """Admin для StatusHistory model."""

    list_display = [
        'id',
        'content_type',
        'object_id',
        'old_status',
        'new_status',
        'changed_at'
    ]
    list_filter = [
        'content_type',
        'old_status',
        'new_status',
        'changed_at'
    ]
    search_fields = ['object_id', 'reason']
    readonly_fields = [
        'content_type',
        'object_id',
        'old_status',
        'new_status',
        'reason',
        'metadata',
        'changed_at'
    ]
    date_hierarchy = 'changed_at'

    def has_add_permission(self, request):
        """Запретить создание записей вручную."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Запретить удаление (только через retention policy task)."""
        return False
