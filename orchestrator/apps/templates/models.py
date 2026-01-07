from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

# Import workflow models to make them discoverable by Django migrations
from .workflow.models import (  # noqa: F401
    WorkflowType,
    WorkflowTemplate,
    WorkflowExecution,
    WorkflowStepResult,
)


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
