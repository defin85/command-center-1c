"""
REST API Serializers for Workflow Engine.

Provides serializers for:
- WorkflowTemplate (list/detail views)
- WorkflowExecution (list/detail views)
- WorkflowStepResult
- Execute/Cancel request/response
- Nested DAG structure serializers
"""

from typing import Any, Dict

from django.contrib.auth import get_user_model
from pydantic import ValidationError as PydanticValidationError
from rest_framework import serializers

from .models import (
    DAGStructure,
    WorkflowConfig,
    WorkflowExecution,
    WorkflowStepResult,
    WorkflowTemplate,
)
from .management_mode import (
    is_system_managed_workflow,
    resolve_workflow_management_mode,
    resolve_workflow_read_only_reason,
    resolve_workflow_visibility_surface,
)

User = get_user_model()


# ============================================================================
# Nested Serializers for DAG Structure
# ============================================================================


class NodeConfigSerializer(serializers.Serializer):
    """Serializer for NodeConfig Pydantic model."""

    timeout_seconds = serializers.IntegerField(
        default=300, min_value=1, max_value=3600,
        help_text="Node execution timeout (1-3600s)"
    )
    max_retries = serializers.IntegerField(
        default=0, min_value=0, max_value=5,
        help_text="Maximum retry attempts (0-5)"
    )
    parallel_limit = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=100,
        help_text="Max parallel executions (Parallel nodes only)"
    )
    expression = serializers.CharField(
        required=False, allow_null=True, allow_blank=True,
        help_text="Jinja2 boolean expression for Condition nodes"
    )


class ParallelConfigSerializer(serializers.Serializer):
    """Serializer for ParallelConfig Pydantic model."""

    parallel_nodes = serializers.ListField(
        child=serializers.CharField(),
        min_length=1, max_length=50,
        help_text="List of node IDs to execute in parallel"
    )
    wait_for = serializers.CharField(
        default="all",
        help_text="Wait condition: 'all', 'any', or number"
    )
    timeout_seconds = serializers.IntegerField(
        default=300, min_value=1, max_value=3600
    )


class LoopConfigSerializer(serializers.Serializer):
    """Serializer for LoopConfig Pydantic model."""

    mode = serializers.ChoiceField(
        choices=["count", "while", "foreach"],
        help_text="Loop mode"
    )
    count = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=1000
    )
    condition = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    items = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    loop_node_id = serializers.CharField(help_text="Node ID to loop")
    max_iterations = serializers.IntegerField(
        default=100, min_value=1, max_value=10000
    )


class SubWorkflowRefSerializer(serializers.Serializer):
    """Serializer for SubWorkflowRef Pydantic model."""

    binding_mode = serializers.ChoiceField(
        choices=["direct_runtime_id", "pinned_revision"],
        default="direct_runtime_id",
        help_text="Binding mode for subworkflow reference",
    )
    workflow_definition_key = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=False,
        help_text="Stable definition key for pinned subworkflow binding",
    )
    workflow_revision_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=False,
        help_text="Pinned workflow revision ID",
    )
    workflow_revision = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        help_text="Pinned workflow revision number",
    )

    def validate(self, attrs):
        if attrs.get("binding_mode") == "pinned_revision":
            if not attrs.get("workflow_definition_key"):
                raise serializers.ValidationError(
                    {"workflow_definition_key": "This field is required for pinned_revision mode."}
                )
            if not attrs.get("workflow_revision_id"):
                raise serializers.ValidationError(
                    {"workflow_revision_id": "This field is required for pinned_revision mode."}
                )
            if attrs.get("workflow_revision") is None:
                raise serializers.ValidationError(
                    {"workflow_revision": "This field is required for pinned_revision mode."}
                )
        return attrs


class SubWorkflowConfigSerializer(serializers.Serializer):
    """Serializer for SubWorkflowConfig Pydantic model."""

    subworkflow_id = serializers.CharField(help_text="Subworkflow template ID")
    subworkflow_ref = SubWorkflowRefSerializer(
        required=False,
        allow_null=True,
        help_text="Pinned binding metadata for analyst-authored subworkflow calls",
    )
    input_mapping = serializers.DictField(
        child=serializers.CharField(),
        required=False,
        default=dict
    )
    output_mapping = serializers.DictField(
        child=serializers.CharField(),
        required=False, default=dict
    )
    max_depth = serializers.IntegerField(
        default=10, min_value=1, max_value=20
    )


class OperationRefSerializer(serializers.Serializer):
    """Serializer for OperationRef Pydantic model."""

    alias = serializers.CharField(
        min_length=1,
        max_length=200,
        help_text="OperationExposure alias for template surface",
    )
    binding_mode = serializers.ChoiceField(
        choices=["alias_latest", "pinned_exposure"],
        default="alias_latest",
        help_text="Binding mode",
    )
    template_exposure_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Pinned OperationExposure ID (required for pinned_exposure)",
    )
    template_exposure_revision = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        help_text="Pinned OperationExposure revision (required for pinned_exposure)",
    )

    def validate(self, attrs):
        """Validate pinned mode required fields."""
        mode = attrs.get("binding_mode")
        if mode == "pinned_exposure":
            if not attrs.get("template_exposure_id"):
                raise serializers.ValidationError(
                    {"template_exposure_id": "This field is required for pinned_exposure mode."}
                )
            if attrs.get("template_exposure_revision") is None:
                raise serializers.ValidationError(
                    {
                        "template_exposure_revision": (
                            "This field is required for pinned_exposure mode."
                        )
                    }
                )
        return attrs


class OperationIOSerializer(serializers.Serializer):
    """Serializer for OperationIO Pydantic model."""

    mode = serializers.ChoiceField(
        choices=["implicit_legacy", "explicit_strict"],
        default="implicit_legacy",
        help_text="Data-flow mode for operation node",
    )
    input_mapping = serializers.DictField(
        child=serializers.CharField(),
        required=False,
        default=dict,
        help_text="Input mapping: target_path -> source_path",
    )
    output_mapping = serializers.DictField(
        child=serializers.CharField(),
        required=False,
        default=dict,
        help_text="Output mapping: target_path -> source_path",
    )


class WorkflowNodeSerializer(serializers.Serializer):
    """Serializer for WorkflowNode Pydantic model."""

    id = serializers.CharField(
        min_length=1, max_length=100,
        help_text="Unique node identifier"
    )
    name = serializers.CharField(
        min_length=1, max_length=200,
        help_text="Human-readable name"
    )
    type = serializers.ChoiceField(
        choices=["operation", "condition", "parallel", "loop", "subworkflow"],
        help_text="Node type"
    )
    template_id = serializers.CharField(
        required=False, allow_null=True, allow_blank=True,
        help_text="Template ID for Operation nodes"
    )
    operation_ref = OperationRefSerializer(
        required=False,
        allow_null=True,
        help_text="OperationExposure binding for Operation nodes",
    )
    io = OperationIOSerializer(
        required=False,
        allow_null=True,
        help_text="Operation node data-flow contract",
    )
    config = NodeConfigSerializer(required=False, default=dict)
    parallel_config = ParallelConfigSerializer(required=False, allow_null=True)
    loop_config = LoopConfigSerializer(required=False, allow_null=True)
    subworkflow_config = SubWorkflowConfigSerializer(required=False, allow_null=True)


class WorkflowEdgeSerializer(serializers.Serializer):
    """Serializer for WorkflowEdge Pydantic model."""

    condition = serializers.CharField(
        required=False, allow_null=True, allow_blank=True,
        help_text="Jinja2 expression for conditional edges"
    )

    def get_fields(self):
        """Expose 'from'/'to' in schema while keeping Python-safe field names."""
        fields = super().get_fields()
        fields["from"] = serializers.CharField(help_text="Source node ID")
        fields["to"] = serializers.CharField(help_text="Destination node ID")
        return fields

    def to_representation(self, instance):
        """Handle both dict and Pydantic model."""
        if hasattr(instance, 'from_node'):
            # Pydantic model
            return {
                'from': instance.from_node,
                'to': instance.to_node,
                'condition': instance.condition,
            }
        elif isinstance(instance, dict):
            return {
                'from': instance.get('from') or instance.get('from_node'),
                'to': instance.get('to') or instance.get('to_node'),
                'condition': instance.get('condition'),
            }
        return super().to_representation(instance)

    def to_internal_value(self, data):
        """Convert incoming JSON to internal format."""
        return {
            'from': data.get('from') or data.get('from_node'),
            'to': data.get('to') or data.get('to_node'),
            'condition': data.get('condition'),
        }


class DAGStructureSerializer(serializers.Serializer):
    """Serializer for DAGStructure Pydantic model."""

    nodes = WorkflowNodeSerializer(many=True, help_text="List of workflow nodes")
    edges = WorkflowEdgeSerializer(
        many=True, required=False, default=list,
        help_text="List of directed edges"
    )


class WorkflowConfigSerializer(serializers.Serializer):
    """Serializer for WorkflowConfig Pydantic model."""

    timeout_seconds = serializers.IntegerField(
        default=3600, min_value=60, max_value=86400,
        help_text="Total workflow timeout (60-86400s)"
    )
    max_retries = serializers.IntegerField(
        default=0, min_value=0, max_value=3,
        help_text="Workflow-level retry attempts"
    )


# ============================================================================
# WorkflowTemplate Serializers
# ============================================================================


class WorkflowTemplateListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for WorkflowTemplate list view.

    Excludes dag_structure for performance in list endpoints.
    """

    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True, allow_null=True
    )
    node_count = serializers.SerializerMethodField()
    execution_count = serializers.SerializerMethodField()
    category = serializers.CharField(read_only=True)
    is_system_managed = serializers.SerializerMethodField()
    management_mode = serializers.SerializerMethodField()
    visibility_surface = serializers.SerializerMethodField()
    read_only_reason = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowTemplate
        fields = [
            'id',
            'name',
            'description',
            'workflow_type',
            'category',
            'is_valid',
            'is_active',
            'is_system_managed',
            'management_mode',
            'visibility_surface',
            'read_only_reason',
            'version_number',
            'parent_version',
            'created_by',
            'created_by_username',
            'node_count',
            'execution_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'is_valid',
            'version_number',
            'created_at',
            'updated_at',
        ]

    def get_node_count(self, obj) -> int:
        """Return number of nodes in DAG."""
        dag = obj.dag_structure
        if isinstance(dag, DAGStructure):
            return len(dag.nodes)
        elif isinstance(dag, dict):
            return len(dag.get('nodes', []))
        return 0

    def get_execution_count(self, obj) -> int:
        """
        Return number of executions for this template.

        Uses annotated _execution_count from ViewSet queryset to avoid N+1 queries.
        Falls back to count() query if annotation is not present.
        """
        return getattr(obj, '_execution_count', obj.executions.count())

    def get_is_system_managed(self, obj) -> bool:
        return is_system_managed_workflow(obj)

    def get_management_mode(self, obj) -> str:
        return resolve_workflow_management_mode(obj)

    def get_visibility_surface(self, obj) -> str:
        return resolve_workflow_visibility_surface(obj)

    def get_read_only_reason(self, obj) -> str | None:
        return resolve_workflow_read_only_reason(obj)


class WorkflowTemplateDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for WorkflowTemplate detail view.

    Includes dag_structure and config.
    """

    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True, allow_null=True
    )
    dag_structure = DAGStructureSerializer()
    config = WorkflowConfigSerializer(required=False, default=dict)
    execution_count = serializers.SerializerMethodField()
    parent_version_name = serializers.CharField(
        source='parent_version.name', read_only=True, allow_null=True
    )
    category = serializers.CharField(read_only=True)
    is_system_managed = serializers.SerializerMethodField()
    management_mode = serializers.SerializerMethodField()
    visibility_surface = serializers.SerializerMethodField()
    read_only_reason = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowTemplate
        fields = [
            'id',
            'name',
            'description',
            'workflow_type',
            'category',
            'dag_structure',
            'config',
            'is_valid',
            'is_active',
            'is_system_managed',
            'management_mode',
            'visibility_surface',
            'read_only_reason',
            'version_number',
            'parent_version',
            'parent_version_name',
            'created_by',
            'created_by_username',
            'execution_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'is_valid',
            'version_number',
            'created_at',
            'updated_at',
        ]

    def get_execution_count(self, obj) -> int:
        """Return number of executions for this template."""
        return obj.executions.count()

    def get_is_system_managed(self, obj) -> bool:
        return is_system_managed_workflow(obj)

    def get_management_mode(self, obj) -> str:
        return resolve_workflow_management_mode(obj)

    def get_visibility_surface(self, obj) -> str:
        return resolve_workflow_visibility_surface(obj)

    def get_read_only_reason(self, obj) -> str | None:
        return resolve_workflow_read_only_reason(obj)

    def validate_dag_structure(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate DAG structure using Pydantic model."""
        try:
            # Validate through Pydantic
            DAGStructure(**value)
        except PydanticValidationError as exc:
            errors = [f"{err['loc']}: {err['msg']}" for err in exc.errors()]
            raise serializers.ValidationError(errors)
        return value

    def validate_config(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate workflow config using Pydantic model."""
        try:
            WorkflowConfig(**value)
        except PydanticValidationError as exc:
            errors = [f"{err['loc']}: {err['msg']}" for err in exc.errors()]
            raise serializers.ValidationError(errors)
        return value

    def create(self, validated_data):
        """Create workflow template with Pydantic-validated data."""
        # Convert dag_structure dict to Pydantic model for storage
        dag_data = validated_data.get('dag_structure', {})
        config_data = validated_data.get('config', {})

        # Let SchemaField handle the conversion
        validated_data['dag_structure'] = dag_data
        validated_data['config'] = config_data

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update workflow template with Pydantic-validated data."""
        dag_data = validated_data.get('dag_structure')
        config_data = validated_data.get('config')

        if dag_data is not None:
            validated_data['dag_structure'] = dag_data
            # Reset is_valid when DAG structure changes
            validated_data['is_valid'] = False

        if config_data is not None:
            validated_data['config'] = config_data

        return super().update(instance, validated_data)


# ============================================================================
# WorkflowStepResult Serializer
# ============================================================================


class WorkflowStepResultSerializer(serializers.ModelSerializer):
    """Serializer for WorkflowStepResult model."""

    duration_seconds = serializers.FloatField(read_only=True)

    class Meta:
        model = WorkflowStepResult
        fields = [
            'id',
            'node_id',
            'node_name',
            'node_type',
            'status',
            'input_data',
            'output_data',
            'error_message',
            'started_at',
            'completed_at',
            'duration_seconds',
            'trace_id',
            'span_id',
        ]
        read_only_fields = fields


# ============================================================================
# WorkflowExecution Serializers
# ============================================================================


class WorkflowExecutionListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for WorkflowExecution list view.

    Excludes step_results and detailed node_statuses for performance.
    """

    template_name = serializers.CharField(
        source='workflow_template.name', read_only=True
    )
    template_version = serializers.IntegerField(
        source='workflow_template.version_number', read_only=True
    )
    progress_percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )
    duration = serializers.FloatField(read_only=True)

    class Meta:
        model = WorkflowExecution
        fields = [
            'id',
            'workflow_template',
            'template_name',
            'template_version',
            'status',
            'progress_percent',
            'current_node_id',
            'error_message',
            'error_code',
            'error_node_id',
            'trace_id',
            'started_at',
            'completed_at',
            'duration',
        ]
        read_only_fields = fields


class WorkflowExecutionDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for WorkflowExecution detail view.

    Includes step_results and detailed node_statuses.
    """

    template_name = serializers.CharField(
        source='workflow_template.name', read_only=True
    )
    template_version = serializers.IntegerField(
        source='workflow_template.version_number', read_only=True
    )
    progress_percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )
    duration = serializers.FloatField(read_only=True)
    step_results = WorkflowStepResultSerializer(many=True, read_only=True)

    class Meta:
        model = WorkflowExecution
        fields = [
            'id',
            'workflow_template',
            'template_name',
            'template_version',
            'status',
            'input_context',
            'final_result',
            'current_node_id',
            'completed_nodes',
            'failed_nodes',
            'node_statuses',
            'progress_percent',
            'error_message',
            'error_code',
            'error_details',
            'error_node_id',
            'trace_id',
            'started_at',
            'completed_at',
            'duration',
            'step_results',
        ]
        read_only_fields = fields


# ============================================================================
# Request/Response Serializers
# ============================================================================


class WorkflowExecuteRequestSerializer(serializers.Serializer):
    """Serializer for workflow execute request."""

    input_context = serializers.DictField(
        required=False, default=dict,
        help_text="Initial context data for the workflow"
    )
    mode = serializers.ChoiceField(
        choices=['sync', 'async'],
        default='async',
        help_text="Execution mode: 'sync' (blocking) or 'async' (background)"
    )

    def validate_input_context(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input_context is JSON-serializable."""
        import json
        try:
            json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError(
                f"input_context must be JSON-serializable: {exc}"
            )
        return value


class WorkflowExecuteResponseSerializer(serializers.Serializer):
    """Serializer for workflow execute response."""

    execution_id = serializers.UUIDField(help_text="Execution instance ID")
    status = serializers.CharField(help_text="Current execution status")
    mode = serializers.CharField(help_text="Execution mode used")
    message = serializers.CharField(
        required=False, allow_blank=True,
        help_text="Additional information"
    )

    # Sync mode only fields
    final_result = serializers.DictField(
        required=False, allow_null=True,
        help_text="Final result (sync mode only)"
    )
    duration = serializers.FloatField(
        required=False, allow_null=True,
        help_text="Execution duration in seconds (sync mode only)"
    )
    error_message = serializers.CharField(
        required=False, allow_blank=True,
        help_text="Error message if failed"
    )


class WorkflowCancelResponseSerializer(serializers.Serializer):
    """Serializer for workflow cancel response."""

    execution_id = serializers.UUIDField(help_text="Execution instance ID")
    cancelled = serializers.BooleanField(help_text="Whether cancellation succeeded")
    status = serializers.CharField(help_text="Current execution status")
    message = serializers.CharField(
        required=False, allow_blank=True,
        help_text="Additional information"
    )


class WorkflowValidateResponseSerializer(serializers.Serializer):
    """Serializer for workflow validate response."""

    valid = serializers.BooleanField(help_text="Whether template is valid")
    errors = serializers.ListField(
        child=serializers.CharField(),
        required=False, default=list,
        help_text="Validation error messages"
    )
    warnings = serializers.ListField(
        child=serializers.CharField(),
        required=False, default=list,
        help_text="Validation warning messages"
    )
    metadata = serializers.DictField(
        required=False, default=dict,
        help_text="Additional validation metadata"
    )


class WorkflowCloneRequestSerializer(serializers.Serializer):
    """Serializer for workflow clone request."""

    name = serializers.CharField(
        required=False, allow_blank=True, max_length=200,
        help_text="New name for cloned template (optional)"
    )


class WorkflowCloneResponseSerializer(serializers.Serializer):
    """Serializer for workflow clone response."""

    id = serializers.UUIDField(help_text="New template ID")
    name = serializers.CharField(help_text="Template name")
    version_number = serializers.IntegerField(help_text="Version number")
    message = serializers.CharField(help_text="Success message")


class WorkflowStatusResponseSerializer(serializers.Serializer):
    """Lightweight serializer for polling execution status."""

    execution_id = serializers.UUIDField()
    status = serializers.CharField()
    progress_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    current_node_id = serializers.CharField(allow_blank=True)
    completed_nodes = serializers.ListField(child=serializers.CharField())
    failed_nodes = serializers.ListField(child=serializers.CharField())
    started_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    duration = serializers.FloatField(allow_null=True)

    # Only for terminal states
    final_result = serializers.DictField(required=False, allow_null=True)
    error_message = serializers.CharField(required=False, allow_blank=True)
    error_node_id = serializers.CharField(required=False, allow_blank=True)
