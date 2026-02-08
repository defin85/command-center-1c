import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
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


class OperationDefinition(models.Model):
    """Canonical execution definition shared by templates and action catalog exposures."""

    EXECUTOR_IBCMD_CLI = "ibcmd_cli"
    EXECUTOR_DESIGNER_CLI = "designer_cli"
    EXECUTOR_WORKFLOW = "workflow"

    EXECUTOR_KIND_CHOICES = [
        (EXECUTOR_IBCMD_CLI, "IBCMD CLI"),
        (EXECUTOR_DESIGNER_CLI, "Designer CLI"),
        (EXECUTOR_WORKFLOW, "Workflow"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_scope = models.CharField(max_length=80, default="global")
    executor_kind = models.CharField(max_length=32, choices=EXECUTOR_KIND_CHOICES)
    executor_payload = models.JSONField(default=dict)
    contract_version = models.PositiveIntegerField(default=1)
    fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "operation_definitions"
        ordering = ["tenant_scope", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_scope", "fingerprint"],
                name="op_def_scope_fingerprint_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant_scope", "status"], name="op_def_scope_status_idx"),
            models.Index(fields=["executor_kind", "status"], name="op_def_kind_status_idx"),
            models.Index(fields=["fingerprint"], name="op_def_fingerprint_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.tenant_scope}:{self.executor_kind}:{self.id}"


class OperationExposure(models.Model):
    """Surface-specific publication bound to canonical operation definition."""

    SURFACE_TEMPLATE = "template"
    SURFACE_ACTION_CATALOG = "action_catalog"

    SURFACE_CHOICES = [
        (SURFACE_TEMPLATE, "Template"),
        (SURFACE_ACTION_CATALOG, "Action Catalog"),
    ]

    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_INVALID = "invalid"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PUBLISHED, "Published"),
        (STATUS_INVALID, "Invalid"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    definition = models.ForeignKey(
        OperationDefinition,
        on_delete=models.CASCADE,
        related_name="exposures",
    )
    surface = models.CharField(max_length=32, choices=SURFACE_CHOICES)
    alias = models.CharField(max_length=128)
    tenant = models.ForeignKey(
        "tenancy.Tenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="operation_exposures",
    )
    label = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    capability = models.CharField(max_length=128, blank=True, default="")
    contexts = models.JSONField(default=list)
    display_order = models.IntegerField(default=0)
    capability_config = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "operation_exposures"
        ordering = ["surface", "display_order", "label"]
        constraints = [
            models.UniqueConstraint(
                fields=["surface", "alias"],
                condition=Q(tenant__isnull=True),
                name="op_exp_surface_alias_global_uniq",
            ),
            models.UniqueConstraint(
                fields=["surface", "alias", "tenant"],
                condition=Q(tenant__isnull=False),
                name="op_exp_surface_alias_tenant_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["surface", "status"], name="op_exp_surface_status_idx"),
            models.Index(fields=["tenant", "surface"], name="op_exp_tenant_surface_idx"),
            models.Index(fields=["capability", "status"], name="op_exp_cap_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.surface}:{self.alias}:{self.status}"


class OperationMigrationIssue(models.Model):
    """Backfill/migration diagnostics for unified operation catalog cutover."""

    SEVERITY_WARNING = "warning"
    SEVERITY_ERROR = "error"

    SEVERITY_CHOICES = [
        (SEVERITY_WARNING, "Warning"),
        (SEVERITY_ERROR, "Error"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_type = models.CharField(max_length=64)
    source_id = models.CharField(max_length=255)
    tenant = models.ForeignKey(
        "tenancy.Tenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operation_migration_issues",
    )
    exposure = models.ForeignKey(
        OperationExposure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="migration_issues",
    )
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default=SEVERITY_ERROR)
    code = models.CharField(max_length=64)
    message = models.TextField()
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "operation_migration_issues"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["severity", "created_at"], name="op_mig_sev_created_idx"),
            models.Index(fields=["source_type", "source_id"], name="op_mig_source_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.source_type}:{self.source_id}:{self.severity}"


class OperationTemplatePermission(models.Model):
    """
    User permission for a specific operation template.
    """
    from django.conf import settings as django_settings

    user = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='operation_template_permissions'
    )
    template = models.ForeignKey(
        OperationTemplate,
        on_delete=models.CASCADE,
        related_name='user_permissions'
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
        db_table = 'templates_operation_template_permissions'
        unique_together = ['user', 'template']
        indexes = [
            models.Index(fields=['user', 'template'], name='otp_user_tpl_idx'),
            models.Index(fields=['template', 'level'], name='otp_tpl_level_idx'),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.template.id} ({self.get_level_display()})"


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


class WorkflowTemplatePermission(models.Model):
    """
    User permission for a workflow template.
    Rights on the template apply to its executions (inheritance).
    """
    from django.conf import settings as django_settings

    user = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workflow_template_permissions'
    )
    workflow_template = models.ForeignKey(
        WorkflowTemplate,
        on_delete=models.CASCADE,
        related_name='user_permissions'
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
        db_table = 'templates_workflow_template_permissions'
        unique_together = ['user', 'workflow_template']
        indexes = [
            models.Index(fields=['user', 'workflow_template'], name='wtp_user_wf_idx'),
            models.Index(fields=['workflow_template', 'level'], name='wtp_wf_level_idx'),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.workflow_template.name} ({self.get_level_display()})"


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
