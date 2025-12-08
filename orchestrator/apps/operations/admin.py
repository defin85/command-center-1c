"""Django Admin for operations app."""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from .models import (
    Task,
    BatchOperation,
    CompensationAuditLog,
    FailedEvent,
    SchedulerJobRun,
    TaskExecutionLog,
)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Admin for Task model."""

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
        'task_id',
        'worker_id',
        'started_at',
        'completed_at',
        'duration_seconds',
        'created_at',
        'updated_at'
    ]

    def id_short(self, obj):
        """Short ID for display."""
        return str(obj.id)[:8]
    id_short.short_description = 'ID'

    def status_badge(self, obj):
        """Colored badge for status."""
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
    """Admin for BatchOperation model."""

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
        """Short ID for display."""
        return str(obj.id)[:8]
    id_short.short_description = 'ID'

    def status_badge(self, obj):
        """Colored badge for status."""
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


@admin.register(CompensationAuditLog)
class CompensationAuditLogAdmin(admin.ModelAdmin):
    """Admin for CompensationAuditLog model."""

    list_display = [
        'id',
        'operation_id',
        'compensation_name',
        'success_badge',
        'attempts',
        'duration_seconds',
        'executed_at'
    ]
    list_filter = ['success', 'executed_at', 'compensation_name']
    search_fields = ['operation_id', 'compensation_name', 'error_message']
    readonly_fields = [
        'id',
        'operation_id',
        'compensation_name',
        'success',
        'attempts',
        'duration_seconds',
        'error_message',
        'executed_at',
        'created_at'
    ]
    date_hierarchy = 'executed_at'

    def success_badge(self, obj):
        """Colored badge for success status."""
        if obj.success:
            return format_html(
                '<span style="color: green; font-weight: bold;">●</span> Success'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">●</span> Failed'
        )
    success_badge.short_description = 'Status'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(FailedEvent)
class FailedEventAdmin(admin.ModelAdmin):
    """Admin for FailedEvent model."""

    list_display = [
        'id',
        'event_type',
        'channel',
        'correlation_id',
        'status_badge',
        'retry_count',
        'created_at'
    ]
    list_filter = ['status', 'event_type', 'channel', 'created_at']
    search_fields = ['correlation_id', 'event_type', 'last_error']
    readonly_fields = [
        'id',
        'channel',
        'event_type',
        'correlation_id',
        'payload',
        'source_service',
        'original_timestamp',
        'status',
        'retry_count',
        'max_retries',
        'last_error',
        'replayed_at',
        'created_at',
        'updated_at'
    ]
    date_hierarchy = 'created_at'

    def status_badge(self, obj):
        """Colored badge for status."""
        colors = {
            'pending': 'orange',
            'replayed': 'green',
            'failed': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(SchedulerJobRun)
class SchedulerJobRunAdmin(admin.ModelAdmin):
    """
    Admin for SchedulerJobRun model.
    Read-only - records are created by Go workers.
    """

    list_display = [
        'id',
        'job_name',
        'worker_instance',
        'status_badge',
        'duration_display',
        'items_processed',
        'items_failed',
        'started_at'
    ]
    list_filter = ['job_name', 'status', 'started_at', 'worker_instance']
    search_fields = ['job_name', 'worker_instance', 'result_summary', 'error_message']
    readonly_fields = [
        'id',
        'job_name',
        'worker_instance',
        'status',
        'started_at',
        'finished_at',
        'duration_ms',
        'result_summary',
        'error_message',
        'error_traceback',
        'items_processed',
        'items_failed'
    ]
    date_hierarchy = 'started_at'

    def status_badge(self, obj):
        """Colored badge for status."""
        colors = {
            'running': 'blue',
            'success': 'green',
            'failed': 'red',
            'skipped': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def duration_display(self, obj):
        """Format duration for display."""
        if obj.duration_ms is None:
            return '-'
        if obj.duration_ms < 1000:
            return f"{obj.duration_ms}ms"
        return f"{obj.duration_ms / 1000:.2f}s"
    duration_display.short_description = 'Duration'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(TaskExecutionLog)
class TaskExecutionLogAdmin(admin.ModelAdmin):
    """
    Admin for TaskExecutionLog model.
    Read-only - records are created by Go workers.
    """

    list_display = [
        'id',
        'task_id_short',
        'task_type',
        'queue_name',
        'status_badge',
        'operation_link',
        'duration_display',
        'retry_count',
        'started_at'
    ]
    list_filter = ['task_type', 'status', 'started_at', 'queue_name']
    search_fields = ['task_id', 'task_type', 'worker_instance', 'error_message', 'error_type']
    readonly_fields = [
        'id',
        'task_id',
        'task_type',
        'queue_name',
        'worker_instance',
        'operation',
        'status',
        'started_at',
        'finished_at',
        'duration_ms',
        'input_summary',
        'result_summary',
        'error_message',
        'error_type',
        'retry_count'
    ]
    date_hierarchy = 'started_at'
    raw_id_fields = ['operation']

    def task_id_short(self, obj):
        """Short task ID for display."""
        return str(obj.task_id)[:8]
    task_id_short.short_description = 'Task ID'

    def status_badge(self, obj):
        """Colored badge for status."""
        colors = {
            'pending': 'gray',
            'running': 'blue',
            'success': 'green',
            'failed': 'red',
            'retrying': 'orange'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def duration_display(self, obj):
        """Format duration for display."""
        if obj.duration_ms is None:
            return '-'
        if obj.duration_ms < 1000:
            return f"{obj.duration_ms}ms"
        return f"{obj.duration_ms / 1000:.2f}s"
    duration_display.short_description = 'Duration'

    def operation_link(self, obj):
        """Link to related BatchOperation."""
        if obj.operation:
            url = reverse('admin:operations_batchoperation_change', args=[obj.operation.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                str(obj.operation.id)[:8]
            )
        return '-'
    operation_link.short_description = 'Operation'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
