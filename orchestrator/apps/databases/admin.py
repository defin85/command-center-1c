"""Django Admin для databases app."""

from django.contrib import admin
from django.utils.html import format_html
from .models import Database, DatabaseGroup
from .services import DatabaseService


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


@admin.register(Database)
class DatabaseAdmin(admin.ModelAdmin):
    """Admin для Database model."""

    list_display = [
        'name',
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
            'fields': ('id', 'name', 'description', 'status')
        }),
        ('Подключение', {
            'fields': ('host', 'port', 'base_name', 'odata_url', 'username', 'password')
        }),
        ('Health Check', {
            'fields': (
                'last_check',
                'last_check_status',
                'consecutive_failures',
                'last_error',
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

    actions = [health_check_action]

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
