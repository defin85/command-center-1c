from django.db import models
from django.utils import timezone

# Import workflow models to make them discoverable by Django migrations
from .workflow.models import (  # noqa: F401
    WorkflowTemplate,
    WorkflowExecution,
    WorkflowStepResult,
)


class OperationTemplate(models.Model):
    """Template for creating operations."""

    id = models.CharField(max_length=64, primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    operation_type = models.CharField(max_length=20)
    target_entity = models.CharField(max_length=255)
    template_data = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'operation_templates'
        ordering = ['name']

    def __str__(self):
        return self.name
