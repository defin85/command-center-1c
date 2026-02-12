import json
from dataclasses import dataclass

from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django import forms

from django_json_widget.widgets import JSONEditorWidget

from .models import (
    OperationExposure,
    WorkflowExecution,
    WorkflowStepResult,
    WorkflowTemplate,
    WorkflowTemplateGroupPermission,
    WorkflowTemplatePermission,
)


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


class SafeJSONEditorWidget(JSONEditorWidget):
    """JSONEditorWidget that handles None values gracefully."""

    def __init__(self, default_value=None, *args, **kwargs):
        self.default_value = default_value if default_value is not None else {}
        super().__init__(*args, **kwargs)

    def format_value(self, value):
        if value is None:
            value = self.default_value
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return super().format_value(value)


@dataclass(frozen=True)
class OperationExposureReference:
    id: str
    name: str
    operation_type: str
    target_entity: str


def _serialize_template_reference(exposure: OperationExposure) -> OperationExposureReference:
    payload = exposure.definition.executor_payload if isinstance(exposure.definition.executor_payload, dict) else {}
    operation_type = str(payload.get("operation_type") or exposure.definition.executor_kind or "").strip()
    target_entity = str(payload.get("target_entity") or "").strip()
    return OperationExposureReference(
        id=str(exposure.alias),
        name=str(exposure.label or exposure.alias),
        operation_type=operation_type,
        target_entity=target_entity,
    )


class WorkflowTemplateAdminForm(forms.ModelForm):
    """Custom form with JSON Editor for dag_structure and config."""

    class Meta:
        model = WorkflowTemplate
        fields = '__all__'
        widgets = {
            'dag_structure': SafeJSONEditorWidget(
                default_value={"nodes": [], "edges": []},
                options={
                    'mode': 'code',
                    'modes': ['code', 'tree', 'form', 'view'],
                },
                attrs={'style': 'height: 500px; width: 100%;'}
            ),
            'config': SafeJSONEditorWidget(
                default_value={},
                options={
                    'mode': 'code',
                    'modes': ['code', 'tree', 'form', 'view'],
                },
                attrs={'style': 'height: 200px; width: 100%;'}
            ),
        }


@admin.action(description="Validate selected workflows")
def validate_workflows(modeladmin, request, queryset):
    """
    Admin action to validate selected workflow templates.

    Runs DAG validation on each selected template and shows results via messages.
    """
    if not request.user.is_staff:
        messages.error(
            request,
            "Workflow validation is disabled in Django Admin. Use SPA (/workflows). Staff-only break-glass.",
        )
        return

    valid_count = 0
    invalid_count = 0
    errors = []

    for template in queryset:
        try:
            template.validate()
            template.save(update_fields=['is_valid'])
            valid_count += 1
        except ValueError as e:
            invalid_count += 1
            errors.append(f"{template.name}: {str(e)}")

    if valid_count > 0:
        messages.success(
            request,
            f"Successfully validated {valid_count} workflow(s)."
        )

    if invalid_count > 0:
        messages.error(
            request,
            f"Validation failed for {invalid_count} workflow(s)."
        )
        for error in errors[:5]:  # Show max 5 errors to avoid message overflow
            messages.warning(request, error)

        if len(errors) > 5:
            messages.info(request, f"... and {len(errors) - 5} more errors.")


@admin.register(WorkflowTemplate)
class WorkflowTemplateAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    form = WorkflowTemplateAdminForm
    list_display = ['name', 'workflow_type', 'is_valid', 'is_active', 'is_template', 'version_number', 'created_at']
    list_filter = ['workflow_type', 'is_valid', 'is_active', 'is_template', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'is_valid', 'created_at', 'updated_at']
    actions = [validate_workflows]

    # Custom change form template with Validate button and exposure reference panel
    change_form_template = 'admin/templates/workflowtemplate/change_form.html'

    fieldsets = (
        ('Основное', {
            'fields': ('id', 'name', 'description', 'workflow_type')
        }),
        ('DAG Structure', {
            'fields': ('dag_structure',),
            'description': 'JSON структура: {"nodes": [...], "edges": [...]}'
        }),
        ('Конфигурация', {
            'fields': ('config',),
            'classes': ('collapse',)
        }),
        ('Валидация', {
            'fields': ('is_valid',),
            'classes': ('collapse',)
        }),
        ('Статус', {
            'fields': ('is_active', 'version_number', 'parent_version')
        }),
        ('Operations Center', {
            'fields': ('is_template', 'icon', 'input_schema'),
            'description': 'Настройки для отображения в Operations Center (New Operation Wizard)'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_urls(self):
        """Add custom URL for validate action."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/validate/',
                self.admin_site.admin_view(self.validate_view),
                name='templates_workflowtemplate_validate'
            ),
        ]
        return custom_urls + urls

    def validate_view(self, request, object_id):
        """
        Handle validation request for a single workflow template.

        GET/POST: Validates the workflow and redirects back to change page.
        """
        if not request.user.is_staff:
            messages.error(
                request,
                "Workflow validation is disabled in Django Admin. Use SPA (/workflows). Staff-only break-glass.",
            )
            return HttpResponseRedirect(
                reverse('admin:templates_workflowtemplate_changelist')
            )

        try:
            obj = self.get_object(request, object_id)
            if obj is None:
                messages.error(request, "Workflow template not found.")
                return HttpResponseRedirect(
                    reverse('admin:templates_workflowtemplate_changelist')
                )

            try:
                obj.validate()
                obj.save(update_fields=['is_valid'])
                messages.success(
                    request,
                    format_html(
                        'DAG validation <strong>passed</strong> for "{}". '
                        'Workflow is ready for execution.',
                        obj.name
                    )
                )

                # Show warnings if any
                if hasattr(obj, '_validation_metadata') and 'warnings' in obj._validation_metadata:
                    for warning in obj._validation_metadata['warnings']:
                        messages.warning(request, f"Warning: {warning}")

            except ValueError as e:
                messages.error(
                    request,
                    format_html(
                        'DAG validation <strong>failed</strong> for "{}": {}',
                        obj.name,
                        str(e)
                    )
                )
                obj.is_valid = False
                obj.save(update_fields=['is_valid'])

        except Exception as e:
            messages.error(request, f"Unexpected error during validation: {str(e)}")

        return HttpResponseRedirect(
            reverse('admin:templates_workflowtemplate_change', args=[object_id])
        )

    def _get_operation_exposure_references(self):
        """Get active+published template exposures for reference panel."""
        exposures = (
            OperationExposure.objects.select_related("definition")
            .filter(
                surface=OperationExposure.SURFACE_TEMPLATE,
                tenant__isnull=True,
                is_active=True,
                status=OperationExposure.STATUS_PUBLISHED,
            )
            .only("alias", "label", "definition__executor_payload", "definition__executor_kind")
        )
        items = [_serialize_template_reference(row) for row in exposures]
        items.sort(key=lambda item: (item.operation_type, item.name, item.id))
        return items

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """
        Override to add operation_templates to context for the reference panel.

        This provides a list of all active+published template exposures
        that can be used when building the DAG structure.
        """
        extra_context = extra_context or {}
        extra_context['operation_templates'] = self._get_operation_exposure_references()
        return super().changeform_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        """
        Override to add operation_templates to context for the add form.

        This ensures the reference panel is available when creating new workflows.
        """
        extra_context = extra_context or {}
        extra_context['operation_templates'] = self._get_operation_exposure_references()
        return super().add_view(request, form_url, extra_context)


@admin.register(WorkflowExecution)
class WorkflowExecutionAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    list_display = ['id_short', 'workflow_template', 'status', 'progress_percent', 'started_at', 'completed_at']
    list_filter = ['status', 'started_at', 'completed_at']
    search_fields = ['id', 'workflow_template__name']
    readonly_fields = [
        'id', 'workflow_template', 'input_context', 'status',
        'current_node_id', 'completed_nodes', 'failed_nodes', 'node_statuses',
        'final_result', 'error_message', 'error_node_id',
        'trace_id', 'started_at', 'completed_at'
    ]

    def id_short(self, obj):
        return str(obj.id)[:8] if obj.id else '-'
    id_short.short_description = 'ID'

    def progress_percent(self, obj):
        return f"{obj.progress_percent}%"
    progress_percent.short_description = 'Progress'


@admin.register(WorkflowStepResult)
class WorkflowStepResultAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    list_display = ['node_name', 'node_type', 'status', 'workflow_execution', 'started_at', 'completed_at']
    list_filter = ['status', 'node_type']
    search_fields = ['node_id', 'node_name', 'workflow_execution__id']
    readonly_fields = [
        'id', 'workflow_execution', 'node_id', 'node_name', 'node_type',
        'status', 'input_data', 'output_data', 'error_message',
        'started_at', 'completed_at', 'span_id', 'trace_id'
    ]


@admin.register(WorkflowTemplatePermission)
class WorkflowTemplatePermissionAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    """Admin for WorkflowTemplatePermission model (RBAC)."""

    list_display = ['user', 'workflow_template', 'level', 'granted_by', 'granted_at']
    list_filter = ['level', 'workflow_template__workflow_type']
    search_fields = ['user__username', 'workflow_template__name']
    autocomplete_fields = ['user', 'workflow_template']
    readonly_fields = ['granted_at']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.granted_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(WorkflowTemplateGroupPermission)
class WorkflowTemplateGroupPermissionAdmin(StaffWriteAdminMixin, admin.ModelAdmin):
    """Admin for WorkflowTemplateGroupPermission model (RBAC)."""

    list_display = ['group', 'workflow_template', 'level', 'granted_by', 'granted_at']
    list_filter = ['level', 'workflow_template__workflow_type']
    search_fields = ['group__name', 'workflow_template__name']
    autocomplete_fields = ['group', 'workflow_template']
    readonly_fields = ['granted_at']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.granted_by = request.user
        super().save_model(request, obj, form, change)
