import json

from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django import forms

from django_json_widget.widgets import JSONEditorWidget

from .models import OperationTemplate, WorkflowTemplate, WorkflowExecution, WorkflowStepResult


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


def get_operation_type_choices():
    """
    Get operation type choices from registry.

    Returns choices for Select widget. Handles cases when
    registry is empty or unavailable.
    """
    from apps.templates.registry import get_registry

    try:
        registry = get_registry()
        choices = registry.get_choices()
        if choices:
            return choices
        return [('', '--- No types registered ---')]
    except Exception:
        return [('', '--- Registry not available ---')]


class OperationTemplateAdminForm(forms.ModelForm):
    """Form with dynamic operation_type choices and JSON editor for template_data."""

    class Meta:
        model = OperationTemplate
        fields = '__all__'
        widgets = {
            'template_data': SafeJSONEditorWidget(
                default_value={},
                options={
                    'mode': 'code',
                    'modes': ['code', 'tree', 'form', 'view'],
                },
                attrs={'style': 'height: 400px; width: 100%;'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set dynamic choices from registry
        self.fields['operation_type'].widget = forms.Select(
            choices=get_operation_type_choices()
        )


@admin.action(description="Sync templates from registry")
def sync_from_registry(modeladmin, request, queryset):
    """
    Admin action to synchronize OperationTemplate with registry.

    Creates missing templates, updates existing ones.
    """
    from django.db import transaction
    from apps.templates.registry import get_registry

    registry = get_registry()

    if not registry.get_all():
        messages.error(request, "No operation types registered in registry.")
        return

    created = 0
    updated = 0
    unchanged = 0

    try:
        with transaction.atomic():
            templates_data = registry.get_for_template_sync()

            for data in templates_data:
                template_id = data['id']

                try:
                    template = OperationTemplate.objects.get(id=template_id)
                    # Check if update needed
                    needs_update = False
                    for key in ['name', 'description', 'operation_type', 'target_entity']:
                        if getattr(template, key) != data.get(key):
                            needs_update = True
                            break

                    if needs_update:
                        for key, value in data.items():
                            if key != 'id':
                                setattr(template, key, value)
                        template.save()
                        updated += 1
                    else:
                        unchanged += 1

                except OperationTemplate.DoesNotExist:
                    OperationTemplate.objects.create(**data)
                    created += 1

        if created > 0:
            messages.success(request, f"Created {created} new template(s).")
        if updated > 0:
            messages.info(request, f"Updated {updated} existing template(s).")
        if unchanged > 0 and created == 0 and updated == 0:
            messages.info(request, f"All {unchanged} templates are up to date.")

    except Exception as e:
        messages.error(request, f"Sync failed: {str(e)}")


@admin.register(OperationTemplate)
class OperationTemplateAdmin(admin.ModelAdmin):
    form = OperationTemplateAdminForm
    list_display = ['name', 'operation_type', 'target_entity', 'is_active', 'created_at']
    list_filter = ['operation_type', 'is_active', 'created_at']
    search_fields = ['name', 'target_entity']
    readonly_fields = ['id', 'created_at', 'updated_at']
    actions = [sync_from_registry]

    # Add button in changelist header
    change_list_template = 'admin/templates/operationtemplate/change_list.html'

    def get_urls(self):
        """Add custom URL for sync action."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'sync/',
                self.admin_site.admin_view(self.sync_view),
                name='templates_operationtemplate_sync'
            ),
        ]
        return custom_urls + urls

    def sync_view(self, request):
        """
        Handle sync request from the button in changelist.

        Performs the same logic as sync_from_registry action but without queryset.
        """
        from django.db import transaction
        from apps.templates.registry import get_registry

        registry = get_registry()

        if not registry.get_all():
            messages.error(request, "No operation types registered in registry.")
            return HttpResponseRedirect(
                reverse('admin:templates_operationtemplate_changelist')
            )

        created = 0
        updated = 0
        unchanged = 0

        try:
            with transaction.atomic():
                templates_data = registry.get_for_template_sync()

                for data in templates_data:
                    template_id = data['id']

                    try:
                        template = OperationTemplate.objects.get(id=template_id)
                        # Check if update needed
                        needs_update = False
                        for key in ['name', 'description', 'operation_type', 'target_entity']:
                            if getattr(template, key) != data.get(key):
                                needs_update = True
                                break

                        if needs_update:
                            for key, value in data.items():
                                if key != 'id':
                                    setattr(template, key, value)
                            template.save()
                            updated += 1
                        else:
                            unchanged += 1

                    except OperationTemplate.DoesNotExist:
                        OperationTemplate.objects.create(**data)
                        created += 1

            if created > 0:
                messages.success(request, f"Created {created} new template(s).")
            if updated > 0:
                messages.info(request, f"Updated {updated} existing template(s).")
            if unchanged > 0 and created == 0 and updated == 0:
                messages.info(request, f"All {unchanged} templates are up to date.")

        except Exception as e:
            messages.error(request, f"Sync failed: {str(e)}")

        return HttpResponseRedirect(
            reverse('admin:templates_operationtemplate_changelist')
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
class WorkflowTemplateAdmin(admin.ModelAdmin):
    form = WorkflowTemplateAdminForm
    list_display = ['name', 'workflow_type', 'is_valid', 'is_active', 'is_template', 'version_number', 'created_at']
    list_filter = ['workflow_type', 'is_valid', 'is_active', 'is_template', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'is_valid', 'created_at', 'updated_at']
    actions = [validate_workflows]

    # Custom change form template with Validate button and Operation Templates Reference
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

    def _get_operation_templates_queryset(self):
        """Get active operation templates for reference panel."""
        return OperationTemplate.objects.filter(
            is_active=True
        ).order_by('operation_type', 'name')

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """
        Override to add operation_templates to context for the reference panel.

        This provides a list of all active OperationTemplate instances
        that can be used when building the DAG structure.
        """
        extra_context = extra_context or {}
        extra_context['operation_templates'] = self._get_operation_templates_queryset()
        return super().changeform_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        """
        Override to add operation_templates to context for the add form.

        This ensures the reference panel is available when creating new workflows.
        """
        extra_context = extra_context or {}
        extra_context['operation_templates'] = self._get_operation_templates_queryset()
        return super().add_view(request, form_url, extra_context)


@admin.register(WorkflowExecution)
class WorkflowExecutionAdmin(admin.ModelAdmin):
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
class WorkflowStepResultAdmin(admin.ModelAdmin):
    list_display = ['node_name', 'node_type', 'status', 'workflow_execution', 'started_at', 'completed_at']
    list_filter = ['status', 'node_type']
    search_fields = ['node_id', 'node_name', 'workflow_execution__id']
    readonly_fields = [
        'id', 'workflow_execution', 'node_id', 'node_name', 'node_type',
        'status', 'input_data', 'output_data', 'error_message',
        'started_at', 'completed_at', 'span_id', 'trace_id'
    ]
