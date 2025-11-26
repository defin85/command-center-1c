"""
Django Filter classes for Workflow API.

Provides FilterSet classes for:
- WorkflowTemplateFilter
- WorkflowExecutionFilter
"""

import django_filters
from django.db.models import QuerySet

from .models import WorkflowExecution, WorkflowTemplate


class WorkflowTemplateFilter(django_filters.FilterSet):
    """
    FilterSet for WorkflowTemplate model.

    Filters:
    - workflow_type: Exact match
    - is_active: Boolean
    - is_valid: Boolean
    - created_at_after: Date range start
    - created_at_before: Date range end
    - created_by: User ID
    - version_number: Exact match
    - name_contains: Case-insensitive substring match
    """

    workflow_type = django_filters.CharFilter(
        field_name='workflow_type',
        lookup_expr='exact',
        help_text='Filter by workflow type (exact match)',
    )

    is_active = django_filters.BooleanFilter(
        field_name='is_active',
        help_text='Filter by active status',
    )

    is_valid = django_filters.BooleanFilter(
        field_name='is_valid',
        help_text='Filter by validation status',
    )

    created_at_after = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte',
        help_text='Filter templates created after this datetime (ISO 8601)',
    )

    created_at_before = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte',
        help_text='Filter templates created before this datetime (ISO 8601)',
    )

    created_by = django_filters.NumberFilter(
        field_name='created_by__id',
        help_text='Filter by creator user ID',
    )

    version_number = django_filters.NumberFilter(
        field_name='version_number',
        help_text='Filter by version number',
    )

    name_contains = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
        help_text='Filter by name (case-insensitive substring)',
    )

    has_parent = django_filters.BooleanFilter(
        method='filter_has_parent',
        help_text='Filter templates that have/dont have parent version',
    )

    class Meta:
        model = WorkflowTemplate
        fields = [
            'workflow_type',
            'is_active',
            'is_valid',
            'created_at_after',
            'created_at_before',
            'created_by',
            'version_number',
            'name_contains',
            'has_parent',
        ]

    def filter_has_parent(self, queryset: QuerySet, name: str, value: bool) -> QuerySet:
        """Filter by whether template has a parent version."""
        if value:
            return queryset.filter(parent_version__isnull=False)
        return queryset.filter(parent_version__isnull=True)


class WorkflowExecutionFilter(django_filters.FilterSet):
    """
    FilterSet for WorkflowExecution model.

    Filters:
    - status: Exact match or multiple (comma-separated)
    - workflow_template: Template UUID
    - started_at_after: Date range start
    - started_at_before: Date range end
    - completed_at_after: Completion date range start
    - completed_at_before: Completion date range end
    - trace_id: OpenTelemetry trace ID
    - has_error: Boolean - filter executions with/without errors
    """

    status = django_filters.CharFilter(
        method='filter_status',
        help_text='Filter by status (comma-separated for multiple: pending,running)',
    )

    workflow_template = django_filters.UUIDFilter(
        field_name='workflow_template__id',
        help_text='Filter by workflow template UUID',
    )

    template_name = django_filters.CharFilter(
        field_name='workflow_template__name',
        lookup_expr='icontains',
        help_text='Filter by template name (case-insensitive substring)',
    )

    started_at_after = django_filters.DateTimeFilter(
        field_name='started_at',
        lookup_expr='gte',
        help_text='Filter executions started after this datetime (ISO 8601)',
    )

    started_at_before = django_filters.DateTimeFilter(
        field_name='started_at',
        lookup_expr='lte',
        help_text='Filter executions started before this datetime (ISO 8601)',
    )

    completed_at_after = django_filters.DateTimeFilter(
        field_name='completed_at',
        lookup_expr='gte',
        help_text='Filter executions completed after this datetime (ISO 8601)',
    )

    completed_at_before = django_filters.DateTimeFilter(
        field_name='completed_at',
        lookup_expr='lte',
        help_text='Filter executions completed before this datetime (ISO 8601)',
    )

    trace_id = django_filters.CharFilter(
        field_name='trace_id',
        lookup_expr='exact',
        help_text='Filter by OpenTelemetry trace ID',
    )

    has_error = django_filters.BooleanFilter(
        method='filter_has_error',
        help_text='Filter executions with/without errors',
    )

    is_running = django_filters.BooleanFilter(
        method='filter_is_running',
        help_text='Filter currently running executions',
    )

    is_terminal = django_filters.BooleanFilter(
        method='filter_is_terminal',
        help_text='Filter executions in terminal state (completed/failed/cancelled)',
    )

    class Meta:
        model = WorkflowExecution
        fields = [
            'status',
            'workflow_template',
            'template_name',
            'started_at_after',
            'started_at_before',
            'completed_at_after',
            'completed_at_before',
            'trace_id',
            'has_error',
            'is_running',
            'is_terminal',
        ]

    def filter_status(self, queryset: QuerySet, name: str, value: str) -> QuerySet:
        """Filter by status - supports comma-separated values."""
        if not value:
            return queryset

        # Split comma-separated values
        statuses = [s.strip() for s in value.split(',') if s.strip()]

        # Validate statuses
        valid_statuses = {
            WorkflowExecution.STATUS_PENDING,
            WorkflowExecution.STATUS_RUNNING,
            WorkflowExecution.STATUS_COMPLETED,
            WorkflowExecution.STATUS_FAILED,
            WorkflowExecution.STATUS_CANCELLED,
        }
        statuses = [s for s in statuses if s in valid_statuses]

        if not statuses:
            return queryset

        return queryset.filter(status__in=statuses)

    def filter_has_error(self, queryset: QuerySet, name: str, value: bool) -> QuerySet:
        """Filter by whether execution has an error."""
        if value:
            return queryset.exclude(error_message='').exclude(error_message__isnull=True)
        return queryset.filter(error_message='') | queryset.filter(error_message__isnull=True)

    def filter_is_running(self, queryset: QuerySet, name: str, value: bool) -> QuerySet:
        """Filter by whether execution is currently running."""
        if value:
            return queryset.filter(status__in=[
                WorkflowExecution.STATUS_PENDING,
                WorkflowExecution.STATUS_RUNNING,
            ])
        return queryset.exclude(status__in=[
            WorkflowExecution.STATUS_PENDING,
            WorkflowExecution.STATUS_RUNNING,
        ])

    def filter_is_terminal(self, queryset: QuerySet, name: str, value: bool) -> QuerySet:
        """Filter by whether execution is in terminal state."""
        terminal_statuses = [
            WorkflowExecution.STATUS_COMPLETED,
            WorkflowExecution.STATUS_FAILED,
            WorkflowExecution.STATUS_CANCELLED,
        ]
        if value:
            return queryset.filter(status__in=terminal_statuses)
        return queryset.exclude(status__in=terminal_statuses)
