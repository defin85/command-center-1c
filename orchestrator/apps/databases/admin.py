"""Django Admin для databases app."""

import logging
from django.contrib import admin
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import path
from django.utils.html import format_html
from django.utils import timezone
from django.conf import settings
from django.db.models import Count, Q
from .models import Cluster, Database, DatabaseGroup, ExtensionInstallation
from .services import DatabaseService, ClusterService
from .clients import ClusterServiceClient

logger = logging.getLogger(__name__)


@admin.action(description='Health check selected databases')
def health_check_action(modeladmin, request, queryset):
    """Action для health check баз из admin."""
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


@admin.action(description='Check Cluster Service status')
def check_cluster_service_status_action(modeladmin, request, queryset):
    """
    Проверить доступность cluster-service для выбранных кластеров.

    Каждый кластер имеет свой cluster_service_url (поле cluster_service_url).
    """
    import time

    if not queryset.exists():
        modeladmin.message_user(
            request,
            '⚠️ Выберите хотя бы один кластер для проверки',
            level=messages.WARNING
        )
        return

    # Check each selected cluster
    for cluster in queryset:
        service_url = cluster.cluster_service_url
        service_timeout = settings.INSTALLATION_SERVICE_TIMEOUT

        logger.info(f"Checking cluster-service for cluster {cluster.name}: {service_url}")

        try:
            start_time = time.time()

            # Create client with cluster's cluster_service_url
            with ClusterServiceClient(base_url=service_url) as client:
                is_healthy = client.health_check()

            elapsed_time = time.time() - start_time

            if is_healthy:
                modeladmin.message_user(
                    request,
                    format_html(
                        '✅ <strong>Cluster "{}" - Cluster Service: HEALTHY</strong><br>'
                        '📍 URL: {}<br>'
                        '⏱️ Response time: {}s<br>'
                        '⚙️ Timeout: {}s',
                        cluster.name,
                        service_url,
                        f'{elapsed_time:.3f}',
                        service_timeout
                    ),
                    level=messages.SUCCESS
                )
                logger.info(
                    f"Cluster service for cluster {cluster.name} is healthy "
                    f"(response time: {elapsed_time:.3f}s)"
                )
            else:
                modeladmin.message_user(
                    request,
                    format_html(
                        '❌ <strong>Cluster "{}" - Cluster Service: UNAVAILABLE</strong><br>'
                        '📍 URL: {}<br>'
                        '⏱️ Response time: {}s<br>'
                        '⚙️ Timeout: {}s<br>'
                        '💡 Check if the service is running on Windows Server with this cluster',
                        cluster.name,
                        service_url,
                        f'{elapsed_time:.3f}',
                        service_timeout
                    ),
                    level=messages.ERROR
                )
                logger.error(
                    f"Cluster service for cluster {cluster.name} is unavailable (URL: {service_url})"
                )

        except Exception as e:
            modeladmin.message_user(
                request,
                format_html(
                    '💥 <strong>Cluster "{}" - Cluster Service: ERROR</strong><br>'
                    '📍 URL: {}<br>'
                    '❌ Error: {}<br>'
                    '💡 Check network connectivity and service logs',
                    cluster.name,
                    service_url,
                    str(e)
                ),
                level=messages.ERROR
            )
            logger.error(
                f"Failed to check installation service for cluster {cluster.name}: {e}",
                exc_info=True
            )


@admin.action(description='Sync infobases from cluster')
def sync_infobases_action(modeladmin, request, queryset):
    """
    Синхронизировать инфобазы из выбранных кластеров.

    Для каждого кластера вызывает ClusterService.sync_infobases(),
    который получает список инфобаз через cluster-service и RAS.
    """
    if not queryset.exists():
        modeladmin.message_user(
            request,
            '⚠️ Выберите хотя бы один кластер для синхронизации',
            level=messages.WARNING
        )
        return

    total_created = 0
    total_updated = 0
    total_errors = 0

    for cluster in queryset:
        logger.info(f"Starting infobase sync for cluster: {cluster.name}")

        try:
            # Вызываем ClusterService.sync_infobases()
            result = ClusterService.sync_infobases(cluster)

            created = result.get('created', 0)
            updated = result.get('updated', 0)
            errors = result.get('errors', 0)

            total_created += created
            total_updated += updated
            total_errors += errors

            if errors == 0:
                modeladmin.message_user(
                    request,
                    format_html(
                        '✅ <strong>Cluster "{}"</strong><br>'
                        '📝 Created: {} infobases<br>'
                        '🔄 Updated: {} infobases<br>'
                        '⏱️ Sync time: {}',
                        cluster.name,
                        created,
                        updated,
                        cluster.last_sync.strftime('%Y-%m-%d %H:%M:%S') if cluster.last_sync else 'N/A'
                    ),
                    level=messages.SUCCESS
                )
                logger.info(
                    f"Successfully synced cluster {cluster.name}: "
                    f"created={created}, updated={updated}"
                )
            else:
                modeladmin.message_user(
                    request,
                    format_html(
                        '⚠️ <strong>Cluster "{}"</strong><br>'
                        '📝 Created: {} infobases<br>'
                        '🔄 Updated: {} infobases<br>'
                        '❌ Errors: {} infobases<br>'
                        '💡 Check logs for details',
                        cluster.name,
                        created,
                        updated,
                        errors
                    ),
                    level=messages.WARNING
                )
                logger.warning(
                    f"Cluster {cluster.name} sync completed with errors: "
                    f"created={created}, updated={updated}, errors={errors}"
                )

        except ValueError as e:
            # Cluster is locked or in invalid state
            total_errors += 1
            modeladmin.message_user(
                request,
                format_html(
                    '🔒 <strong>Cluster "{}"</strong><br>'
                    '❌ Error: {}<br>'
                    '💡 {}',
                    cluster.name,
                    str(e),
                    'Cluster may be locked by another sync process'
                ),
                level=messages.ERROR
            )
            logger.error(f"Cluster {cluster.name} sync failed (locked): {e}")

        except Exception as e:
            # Unexpected error
            total_errors += 1
            modeladmin.message_user(
                request,
                format_html(
                    '💥 <strong>Cluster "{}"</strong><br>'
                    '❌ Unexpected error: {}<br>'
                    '💡 Check cluster-service and RAS connectivity',
                    cluster.name,
                    str(e)
                ),
                level=messages.ERROR
            )
            logger.error(
                f"Unexpected error syncing cluster {cluster.name}: {e}",
                exc_info=True
            )

    # Final summary
    if queryset.count() > 1:
        modeladmin.message_user(
            request,
            format_html(
                '<strong>📊 Sync Summary</strong><br>'
                '✅ Total created: {} infobases<br>'
                '🔄 Total updated: {} infobases<br>'
                '❌ Total errors: {}',
                total_created,
                total_updated,
                total_errors
            ),
            level=messages.SUCCESS if total_errors == 0 else messages.WARNING
        )


@admin.register(Cluster)
class ClusterAdmin(admin.ModelAdmin):
    """Admin для Cluster model."""

    list_display = [
        'name',
        'ras_server',
        'status_badge',
        'infobase_count',
        'healthy_infobase_count',
        'last_sync',
        'last_sync_status',
        'created_at'
    ]
    list_filter = ['status', 'last_sync_status', 'created_at']
    search_fields = ['name', 'description', 'ras_server']
    readonly_fields = [
        'last_sync',
        'last_sync_status',
        'last_sync_error',
        'created_at',
        'updated_at',
        'infobase_count',
        'healthy_infobase_count'
    ]

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description', 'status')
        }),
        ('RAS Connection', {
            'fields': ('ras_server', 'cluster_user', 'cluster_pwd')
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

    actions = [check_cluster_service_status_action, sync_infobases_action]

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


@admin.register(Database)
class DatabaseAdmin(admin.ModelAdmin):
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
        return redirect('admin:databases_database_sync_from_cluster')

    sync_from_cluster_action.short_description = 'Sync databases from 1C cluster'

    def sync_from_cluster_view(self, request):
        """
        Intermediate page for syncing databases from 1C cluster.

        Workflow:
        1. GET - show form with cluster connection parameters
        2. POST step=1 - call cluster-service, show database list
        3. POST step=2 - import selected databases

        This is a three-step process:
        - Step 1: User enters cluster connection details
        - Step 2: System retrieves database list, user selects which to import
        - Step 3: System imports selected databases
        """
        # Check permissions
        if not request.user.is_superuser:
            messages.error(request, 'Only superusers can sync databases from cluster.')
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
        """Handle step 1: Get database list from cluster-service."""
        # Get form parameters
        server = request.POST.get('server', 'localhost:1545')
        cluster_user = request.POST.get('cluster_user', '') or None
        cluster_pwd = request.POST.get('cluster_pwd', '') or None
        detailed = request.POST.get('detailed') == 'on'

        logger.info(
            f"Step 1: Getting database list from cluster (server={server}, "
            f"detailed={detailed}, user={cluster_user or 'None'})"
        )

        try:
            # Call cluster-service
            with ClusterServiceClient() as client:
                # Check health first
                if not client.health_check():
                    messages.error(
                        request,
                        'Cluster-service is not available. '
                        'Please ensure the service is running.'
                    )
                    return redirect('admin:databases_database_sync_from_cluster')

                # Get infobases
                result = client.get_infobases(
                    server=server,
                    cluster_user=cluster_user,
                    cluster_pwd=cluster_pwd,
                    detailed=detailed
                )

            # Store result in session for step 2 with timestamp
            request.session['cluster_sync_data'] = {
                'cluster_id': result['cluster_id'],
                'cluster_name': result['cluster_name'],
                'total_count': result['total_count'],
                'infobases': result['infobases'],
                'duration_ms': result.get('duration_ms', 0),
                'server': server,
                'import_timestamp': timezone.now().isoformat(),
            }

            # Show database selection page
            context = {
                **self.admin_site.each_context(request),
                'title': 'Select Databases to Import',
                'opts': self.model._meta,
                'cluster_id': result['cluster_id'],
                'cluster_name': result['cluster_name'],
                'total_count': result['total_count'],
                'infobases': result['infobases'],
                'duration_ms': result.get('duration_ms', 0),
            }

            return render(
                request,
                'admin/databases/sync_from_cluster_select.html',
                context
            )

        except Exception as e:
            logger.error(f"Error getting database list: {e}", exc_info=True)

            # CLEANUP: Clear session data on error
            if 'cluster_sync_data' in request.session:
                del request.session['cluster_sync_data']

            messages.error(
                request,
                f'Failed to retrieve database list: {str(e)}'
            )
            return redirect('admin:databases_database_sync_from_cluster')

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
            infobases: List of infobase dictionaries from cluster-service
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
class DatabaseGroupAdmin(admin.ModelAdmin):
    """Admin для DatabaseGroup model."""

    list_display = ['name', 'databases_count', 'created_at']
    search_fields = ['name', 'description']
    filter_horizontal = ['databases']

    def databases_count(self, obj):
        """Количество баз в группе."""
        return obj.databases.count()
    databases_count.short_description = 'Databases'


@admin.register(ExtensionInstallation)
class ExtensionInstallationAdmin(admin.ModelAdmin):
    """Admin для ExtensionInstallation model."""

    list_display = [
        'id',
        'database',
        'extension_name',
        'status_badge',
        'retry_count',
        'duration_seconds',
        'started_at',
        'completed_at'
    ]
    list_filter = ['status', 'extension_name', 'started_at']
    search_fields = ['database__name', 'extension_name', 'error_message']
    readonly_fields = [
        'id',
        'started_at',
        'completed_at',
        'duration_seconds',
        'retry_count'
    ]

    fieldsets = (
        ('Основная информация', {
            'fields': ('id', 'database', 'extension_name', 'status')
        }),
        ('Время выполнения', {
            'fields': ('started_at', 'completed_at', 'duration_seconds', 'retry_count')
        }),
        ('Результат', {
            'fields': ('error_message', 'metadata')
        }),
    )

    def status_badge(self, obj):
        """Цветной badge для статуса."""
        colors = {
            'pending': 'gray',
            'in_progress': 'blue',
            'completed': 'green',
            'failed': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
