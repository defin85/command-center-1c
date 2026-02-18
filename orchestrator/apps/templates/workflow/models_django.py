"""
Django models for Workflow Engine.

Implements DAG-based workflow orchestration with:
- WorkflowTemplate: Stores DAG structure with Pydantic validation
- WorkflowExecution: Runtime instance with FSM state transitions
- WorkflowStepResult: Audit trail for each workflow step
"""

import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from django_fsm import FSMField, transition
from django_pydantic_field import SchemaField

from .schema import DAGStructure, WorkflowConfig

try:
    from opentelemetry import trace

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


User = get_user_model()


class WorkflowType(models.TextChoices):
    """Workflow type choices for WorkflowTemplate."""

    SEQUENTIAL = "sequential", "Sequential"
    CONDITIONAL = "conditional", "Conditional"
    PARALLEL = "parallel", "Parallel"
    COMPLEX = "complex", "Complex"


class WorkflowCategory(models.TextChoices):
    """Category choices for WorkflowTemplate (Operations Center)."""

    RAS = "ras", "RAS Operations"
    ODATA = "odata", "OData Operations"
    SYSTEM = "system", "System Operations"
    CUSTOM = "custom", "Custom Operations"


class WorkflowTemplate(models.Model):
    """
    Workflow template with DAG structure.

    Stores workflow definitions as versioned templates with Pydantic-validated
    DAG structures. Supports versioning for iterative development.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Workflow template name")
    description = models.TextField(blank=True, help_text="Workflow description")
    workflow_type = models.CharField(
        max_length=100,
        choices=WorkflowType.choices,
        default=WorkflowType.SEQUENTIAL,
        help_text="Workflow type: sequential, conditional, parallel, complex",
    )

    # DAG structure (Pydantic-validated)
    dag_structure = SchemaField(
        schema=DAGStructure, help_text="DAG structure with nodes and edges (Pydantic-validated)"
    )

    # Global workflow config (Pydantic-validated)
    config = SchemaField(
        schema=WorkflowConfig, default=dict, help_text="Workflow configuration (timeout, retries)"
    )

    # Validation & activation
    is_valid = models.BooleanField(
        default=False, help_text="DAG structure is valid (cycles checked)"
    )
    is_active = models.BooleanField(
        default=True, help_text="Template is active and can be executed"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_workflows"
    )

    # Versioning
    parent_version = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_versions",
        help_text="Parent template if this is a new version",
    )
    version_number = models.PositiveIntegerField(
        default=1, help_text="Version number (auto-incremented)"
    )

    # Operations Center fields (Phase 5.1)
    input_schema = models.JSONField(
        null=True,
        blank=True,
        help_text="JSON Schema for dynamic form generation in Operations Center",
    )
    is_template = models.BooleanField(
        default=False, help_text="Template available for Operations Center (quick actions)"
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Ant Design icon name (e.g., 'PlayCircleOutlined')",
    )
    category = models.CharField(
        max_length=50,
        choices=WorkflowCategory.choices,
        default=WorkflowCategory.CUSTOM,
        help_text="Category for grouping in Operations Center",
    )

    class Meta:
        db_table = "workflow_templates"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "is_valid"]),
            models.Index(fields=["created_by", "-created_at"]),
        ]
        permissions = (
            ("manage_workflow_template", "Can manage workflow templates"),
            ("execute_workflow_template", "Can execute workflow templates"),
        )
        constraints = [
            models.UniqueConstraint(
                fields=["name", "version_number"],
                name="unique_workflow_name_version",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} (v{self.version_number})"

    def validate(self) -> bool:
        """
        Validate workflow template DAG structure using DAGValidator.

        Checks:
        - Pydantic schema validation (automatic)
        - Node IDs are unique
        - Edge references valid nodes
        - No cycles (Kahn's algorithm)
        - No self-loops
        - Proper topology (start/end nodes exist)
        - Connectivity analysis
        - Component counting

        Returns:
            True if validation passed

        Raises:
            ValueError: If validation fails with aggregated error messages
        """
        try:
            from apps.templates.workflow.validator import DAGValidator

            # Parse and validate schemas (Pydantic)
            # Note: SchemaField returns Pydantic object, not dict
            dag = (
                self.dag_structure
                if isinstance(self.dag_structure, DAGStructure)
                else DAGStructure(**self.dag_structure)
            )
            _ = (
                self.config
                if isinstance(self.config, WorkflowConfig)
                else WorkflowConfig(**self.config)
            )

            # Use DAGValidator for comprehensive validation
            validator = DAGValidator(dag)
            result = validator.validate()

            if not result.is_valid:
                # Aggregate all error messages
                error_messages = [issue.message for issue in result.errors]
                raise ValueError(f"DAG validation failed: {'; '.join(error_messages)}")

            # Store topological order in metadata (if not already initialized)
            if not hasattr(self, "_validation_metadata"):
                self._validation_metadata = {}

            self._validation_metadata["topological_order"] = result.topological_order
            self._validation_metadata["validation_metadata"] = result.metadata

            # Store warnings for later inspection
            if result.warnings:
                self._validation_metadata["warnings"] = [
                    issue.message for issue in result.warnings
                ]

            self.is_valid = True
            return True

        except Exception as e:
            self.is_valid = False
            raise ValueError(f"Workflow validation failed: {str(e)}")

    def create_execution(
        self,
        input_context: Dict[str, Any],
        *,
        tenant: Any | None = None,
        execution_consumer: str = "legacy",
    ) -> "WorkflowExecution":
        """
        Create a new execution instance from this template.

        Args:
            input_context: Initial context data for the workflow.
            tenant: Tenant binding for execution (required for pools consumer).
            execution_consumer: Runtime consumer name (pools/extensions/operations/...).

        Returns:
            WorkflowExecution: New execution instance in 'pending' state.

        Raises:
            ValueError: If template is not valid or not active.
        """
        if not self.is_valid:
            raise ValueError("Cannot execute invalid workflow template")
        if not self.is_active:
            raise ValueError("Cannot execute inactive workflow template")

        consumer = str(execution_consumer or "legacy").strip() or "legacy"
        if consumer == "pools" and tenant is None:
            raise ValueError("tenant is required for pools workflow execution")

        execution = WorkflowExecution.objects.create(
            workflow_template=self,
            input_context=input_context,
            tenant=tenant,
            execution_consumer=consumer,
            # status uses default=STATUS_PENDING (FSM protected field)
        )
        return execution

    def clone_as_new_version(self, created_by: Optional[User] = None) -> "WorkflowTemplate":
        """
        Clone this template as a new version.

        Args:
            created_by: User creating the new version (optional).

        Returns:
            WorkflowTemplate: New template with incremented version_number.
        """
        # Find max version for this workflow name
        max_version = (
            WorkflowTemplate.objects.filter(name=self.name).aggregate(
                max_ver=models.Max("version_number")
            )["max_ver"]
            or 0
        )

        new_template = WorkflowTemplate.objects.create(
            name=self.name,
            description=self.description,
            workflow_type=self.workflow_type,
            dag_structure=self.dag_structure,
            config=self.config,
            is_valid=self.is_valid,
            is_active=True,
            created_by=created_by or self.created_by,
            parent_version=self,
            version_number=max_version + 1,
        )
        return new_template


class WorkflowExecution(models.Model):
    """
    Runtime instance of a workflow execution.

    Tracks execution state using Django FSM for state transitions.
    Stores execution context, results, and progress tracking.
    """

    # Status choices for FSM
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Template reference
    workflow_template = models.ForeignKey(
        WorkflowTemplate, on_delete=models.PROTECT, related_name="executions"
    )
    tenant = models.ForeignKey(
        "tenancy.Tenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_executions",
        help_text="Tenant context for execution isolation",
    )
    execution_consumer = models.CharField(
        max_length=64,
        default="legacy",
        help_text="Consumer that initiated execution (e.g. pools/extensions/operations)",
    )

    # Execution data
    input_context = models.JSONField(default=dict, help_text="Initial input data for the workflow")
    execution_plan = models.JSONField(
        default=dict,
        blank=True,
        help_text="Safe execution plan (masked; MUST NOT contain raw secret values)",
    )
    bindings = models.JSONField(
        default=list,
        blank=True,
        help_text="Binding provenance list (MUST NOT contain raw secret values)",
    )
    final_result = models.JSONField(null=True, blank=True, help_text="Final workflow output data")

    # State tracking (FSM)
    status = FSMField(
        default=STATUS_PENDING,
        choices=STATUS_CHOICES,
        protected=True,
        help_text="Current execution status (FSM-protected)",
    )

    # Progress tracking
    current_node_id = models.CharField(
        max_length=100, blank=True, help_text="Currently executing node ID"
    )
    completed_nodes = models.JSONField(default=list, help_text="List of completed node IDs")
    failed_nodes = models.JSONField(default=list, help_text="List of failed node IDs")
    node_statuses = models.JSONField(
        default=dict,
        help_text="Map of node_id -> status (pending/running/completed/failed/skipped)",
    )

    # Error tracking
    error_message = models.TextField(blank=True, help_text="Error message if failed")
    error_code = models.CharField(
        max_length=128,
        blank=True,
        db_index=True,
        help_text="Machine-readable error code if failed",
    )
    error_details = models.JSONField(
        null=True,
        blank=True,
        default=None,
        help_text="Structured diagnostics payload for failure analysis",
    )
    error_node_id = models.CharField(
        max_length=100, blank=True, help_text="Node ID where error occurred"
    )

    # OpenTelemetry tracing
    trace_id = models.CharField(max_length=32, blank=True, help_text="OpenTelemetry trace ID (hex)")

    # Timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "workflow_executions"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["status", "-started_at"]),
            models.Index(fields=["workflow_template", "status"]),
            models.Index(fields=["trace_id"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(execution_consumer="pools") | Q(tenant__isnull=False),
                name="workflow_exec_pools_tenant_required",
            )
        ]

    def __str__(self) -> str:
        return f"Execution {self.id} - {self.workflow_template.name} ({self.status})"

    @property
    def progress_percent(self) -> Decimal:
        """
        Calculate execution progress percentage.

        Returns:
            Decimal: Progress from 0.00 to 100.00.
        """
        # SchemaField returns Pydantic object, not dict
        dag = self.workflow_template.dag_structure
        total_nodes = len(dag.nodes) if isinstance(dag, DAGStructure) else len(dag.get("nodes", []))
        if total_nodes == 0:
            return Decimal("0.00")

        completed_count = len(self.completed_nodes)
        return Decimal(str((completed_count / total_nodes) * 100)).quantize(Decimal("0.01"))

    @property
    def duration(self) -> Optional[float]:
        """
        Calculate execution duration in seconds.

        Returns:
            float: Duration in seconds, or None if not started/completed.
        """
        if not self.started_at:
            return None
        end_time = self.completed_at or timezone.now()
        return (end_time - self.started_at).total_seconds()

    @transition(field=status, source=STATUS_PENDING, target=STATUS_RUNNING)
    def start(self) -> None:
        """
        Start workflow execution.

        NOTE: OpenTelemetry span should be created in WorkflowEngine.execute_workflow(),
        NOT in model transitions. The span should live for the entire workflow execution,
        not just during the transition.

        For now, we only set trace_id if provided externally via set_trace_id().
        """
        self.started_at = timezone.now()
        # trace_id will be set by WorkflowEngine (Week 12)

    @transition(field=status, source=STATUS_RUNNING, target=STATUS_COMPLETED)
    def complete(self, result: Dict[str, Any]) -> None:
        """
        Complete workflow execution.

        Args:
            result: Final workflow result data.

        NOTE: OpenTelemetry span will be closed by WorkflowEngine (Week 12).
        """
        self.final_result = result
        self.completed_at = timezone.now()

    @transition(field=status, source=STATUS_RUNNING, target=STATUS_FAILED)
    def fail(self, error: str, node_id: Optional[str] = None) -> None:
        """
        Mark workflow as failed.

        Args:
            error: Error message describing the failure.
            node_id: Optional node ID where the error occurred.

        NOTE: OpenTelemetry span will be closed by WorkflowEngine (Week 12).
        """
        self.error_message = error
        self.error_node_id = node_id or ""
        self.completed_at = timezone.now()

    @transition(field=status, source=[STATUS_PENDING, STATUS_RUNNING], target=STATUS_CANCELLED)
    def cancel(self) -> None:
        """
        Cancel workflow execution.

        NOTE: OpenTelemetry span will be closed by WorkflowEngine (Week 12).
        """
        self.completed_at = timezone.now()

    def set_trace_id(self, trace_id: str) -> None:
        """
        Set OpenTelemetry trace ID (called by WorkflowEngine).

        Args:
            trace_id: OpenTelemetry trace ID (32 hex characters).

        Raises:
            ValueError: If trace_id is not 32 hex characters.
        """
        if len(trace_id) != 32:
            raise ValueError("trace_id must be 32 hex characters")
        self.trace_id = trace_id

    def get_node_status(self, node_id: str) -> str:
        """
        Get current status of a specific node.

        Args:
            node_id: Node identifier.

        Returns:
            str: Node status (pending/running/completed/failed/skipped).
        """
        return self.node_statuses.get(node_id, "pending")

    def update_node_status(
        self, node_id: str, status: str, result: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update node status with race condition protection.

        Args:
            node_id: Node identifier.
            status: New status (pending/running/completed/failed/skipped).
            result: Optional result data for the node.

        Raises:
            ValueError: If status is not valid.

        NOTE: Uses SELECT FOR UPDATE to prevent concurrent update race conditions.
        """
        valid_statuses = {"pending", "running", "completed", "failed", "skipped"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

        with transaction.atomic():
            # Lock row to prevent concurrent updates
            execution = WorkflowExecution.objects.select_for_update().get(pk=self.pk)

            # Refresh JSONFields from DB (exclude FSMField to avoid protection error)
            execution.refresh_from_db(
                fields=["node_statuses", "completed_nodes", "failed_nodes", "current_node_id"]
            )

            # Initialize node_statuses if None
            if execution.node_statuses is None:
                execution.node_statuses = {}

            # Update node status with timestamp tracking
            if node_id not in execution.node_statuses:
                execution.node_statuses[node_id] = {
                    "status": status,
                    "started_at": timezone.now().isoformat(),
                }
            else:
                execution.node_statuses[node_id]["status"] = status

                # Calculate duration for terminal states
                if status in ["completed", "failed", "skipped"]:
                    started = execution.node_statuses[node_id].get("started_at")
                    if started:
                        started_dt = timezone.datetime.fromisoformat(started)
                        duration = (timezone.now() - started_dt).total_seconds()
                        execution.node_statuses[node_id]["duration"] = duration

            # Store result if provided
            if result:
                execution.node_statuses[node_id]["result"] = result

            # Update tracking lists (avoid duplicates)
            if status == "completed" and node_id not in execution.completed_nodes:
                execution.completed_nodes = execution.completed_nodes + [node_id]
            elif status == "failed" and node_id not in execution.failed_nodes:
                execution.failed_nodes = execution.failed_nodes + [node_id]

            # Update current node
            execution.current_node_id = node_id if status == "running" else ""

            # Save with explicit update_fields
            execution.save(
                update_fields=[
                    "node_statuses",
                    "completed_nodes",
                    "failed_nodes",
                    "current_node_id",
                ]
            )

            # Refresh self to reflect DB state (exclude FSMField)
            self.refresh_from_db(
                fields=["node_statuses", "completed_nodes", "failed_nodes", "current_node_id"]
            )


class WorkflowStepResult(models.Model):
    """
    Audit trail for individual workflow step execution.

    Records detailed results for each node execution including inputs,
    outputs, errors, and OpenTelemetry span context.
    """

    # Status choices
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_SKIPPED, "Skipped"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Execution reference
    workflow_execution = models.ForeignKey(
        WorkflowExecution, on_delete=models.CASCADE, related_name="step_results"
    )

    # Node identification
    node_id = models.CharField(max_length=100, help_text="Node ID from DAG structure")
    node_name = models.CharField(max_length=200, help_text="Human-readable node name")
    node_type = models.CharField(max_length=50, help_text="Node type (operation/condition/etc)")

    # Execution data
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    input_data = models.JSONField(default=dict, help_text="Input data for this node")
    output_data = models.JSONField(null=True, blank=True, help_text="Output data from this node")
    error_message = models.TextField(blank=True, help_text="Error message if failed")

    # Timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # OpenTelemetry tracing
    span_id = models.CharField(max_length=16, blank=True, help_text="OpenTelemetry span ID (hex)")
    trace_id = models.CharField(max_length=32, blank=True, help_text="OpenTelemetry trace ID (hex)")

    class Meta:
        db_table = "workflow_step_results"
        ordering = ["workflow_execution", "started_at"]
        indexes = [
            models.Index(fields=["workflow_execution", "node_id"]),
            models.Index(fields=["status", "-started_at"]),
            models.Index(fields=["trace_id", "span_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["workflow_execution", "node_id"],
                condition=Q(status__in=["completed", "failed", "skipped"]),
                name="unique_completed_step_per_execution",
            )
        ]

    def __str__(self) -> str:
        return f"Step {self.node_name} ({self.status})"

    @property
    def duration_seconds(self) -> Optional[float]:
        """
        Calculate step execution duration in seconds.

        Returns:
            float: Duration in seconds, or None if not started/completed.
        """
        if not self.started_at or not self.completed_at:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    def set_opentelemetry_context(self) -> None:
        """
        Extract and store OpenTelemetry trace/span context.

        Sets trace_id and span_id from current trace context.
        """
        if not OTEL_AVAILABLE:
            return

        try:
            current_span = trace.get_current_span()
            if current_span.is_recording():
                ctx = current_span.get_span_context()
                self.trace_id = format(ctx.trace_id, "032x")
                self.span_id = format(ctx.span_id, "016x")
        except Exception:
            # Silently fail if no active span
            pass


__all__ = [
    "WorkflowCategory",
    "WorkflowExecution",
    "WorkflowStepResult",
    "WorkflowTemplate",
    "WorkflowType",
]
