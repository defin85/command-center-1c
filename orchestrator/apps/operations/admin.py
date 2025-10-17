"""Django Admin для operations app."""

from django.contrib import admin
from django.utils.html import format_html
from .models import Task, BatchOperation


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Admin для Task model."""

    list_display = [
        'id_short',
        'batch_operation',
        'database',
        'status_badge',
        'retry_count',
        'duration_seconds',
        'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['id', 'batch_operation__name', 'database__name']
    readonly_fields = [
        'id',
        'celery_task_id',
        'worker_id',
        'started_at',
        'completed_at',
        'duration_seconds',
        'created_at',
        'updated_at'
    ]

    def id_short(self, obj):
        """Короткий ID для display."""
        return str(obj.id)[:8]
    id_short.short_description = 'ID'

    def status_badge(self, obj):
        """Цветной badge для статуса."""
        colors = {
            'pending': 'gray',
            'queued': 'blue',
            'processing': 'orange',
            'completed': 'green',
            'failed': 'red',
            'retry': 'purple'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(BatchOperation)
class BatchOperationAdmin(admin.ModelAdmin):
    """Admin для BatchOperation model."""

    list_display = [
        'id_short',
        'name',
        'status_badge',
        'progress_bar',
        'total_tasks',
        'completed_tasks',
        'failed_tasks',
        'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = [
        'id',
        'progress',
        'total_tasks',
        'completed_tasks',
        'failed_tasks',
        'started_at',
        'completed_at',
        'created_at',
        'updated_at'
    ]
    filter_horizontal = ['target_databases']

    def id_short(self, obj):
        """Короткий ID для display."""
        return str(obj.id)[:8]
    id_short.short_description = 'ID'

    def status_badge(self, obj):
        """Цветной badge для статуса."""
        colors = {
            'pending': 'gray',
            'processing': 'orange',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def progress_bar(self, obj):
        """HTML progress bar."""
        return format_html(
            '<progress value="{}" max="100" style="width: 100px;"></progress> {}%',
            obj.progress,
            obj.progress
        )
    progress_bar.short_description = 'Progress'
