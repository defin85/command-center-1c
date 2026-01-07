from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import Group
from django.utils import timezone

# Import workflow models to make them discoverable by Django migrations
from .workflow.models import (  # noqa: F401
    WorkflowType,
    WorkflowTemplate,
    WorkflowExecution,
    WorkflowStepResult,
)
from apps.databases.models import PermissionLevel


def validate_operation_type(value):
    """
    Validate operation_type against registry.

    Called during model validation (clean) and form validation.
    Gracefully handles empty registry during migrations.
    """
    from apps.templates.registry import get_registry

    registry = get_registry()

    # Registry may be empty during migrations or initial setup
    if not registry.get_all():
        return

    if not registry.is_valid(value):
        valid_types = ', '.join(sorted(registry.get_ids()))
        raise ValidationError(
            f"Unknown operation type: '{value}'. Valid types: {valid_types}"
        )


class OperationTemplate(models.Model):
    """Template for creating operations."""

    id = models.CharField(max_length=64, primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    operation_type = models.CharField(
        max_length=32,
        validators=[validate_operation_type],
    )
    target_entity = models.CharField(max_length=255)
    template_data = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'operation_templates'
        ordering = ['name']
        permissions = (
            ("manage_operation_template", "Can manage operation templates"),
        )

    def __str__(self):
        return self.name


class OperationTemplateGroupPermission(models.Model):
    """
    Group permission for a specific operation template.
    """
    from django.conf import settings as django_settings

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='operation_template_permissions'
    )
    template = models.ForeignKey(
        OperationTemplate,
        on_delete=models.CASCADE,
        related_name='group_permissions'
    )
    level = models.IntegerField(
        choices=PermissionLevel.choices,
        default=PermissionLevel.VIEW
    )

    # Audit fields
    granted_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'templates_operation_template_group_permissions'
        unique_together = ['group', 'template']
        indexes = [
            models.Index(fields=['group', 'template'], name='otgp_group_tpl_idx'),
            models.Index(fields=['template', 'level'], name='otgp_tpl_level_idx'),
        ]

    def __str__(self) -> str:
        return f"{self.group.name} -> {self.template.id} ({self.get_level_display()})"


class WorkflowTemplateGroupPermission(models.Model):
    """
    Group permission for a workflow template.
    Rights on the template apply to its executions (inheritance).
    """
    from django.conf import settings as django_settings

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='workflow_template_permissions'
    )
    workflow_template = models.ForeignKey(
        WorkflowTemplate,
        on_delete=models.CASCADE,
        related_name='group_permissions'
    )
    level = models.IntegerField(
        choices=PermissionLevel.choices,
        default=PermissionLevel.VIEW
    )

    # Audit fields
    granted_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'templates_workflow_template_group_permissions'
        unique_together = ['group', 'workflow_template']
        indexes = [
            models.Index(fields=['group', 'workflow_template'], name='wtgp_group_wf_idx'),
            models.Index(fields=['workflow_template', 'level'], name='wtgp_wf_level_idx'),
        ]

    def __str__(self) -> str:
        return f"{self.group.name} -> {self.workflow_template.name} ({self.get_level_display()})"
