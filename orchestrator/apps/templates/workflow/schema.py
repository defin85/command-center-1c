"""
Pydantic schemas used by the Workflow Engine models.

These schemas are used for JSON validation via django-pydantic-field.
"""

import re
from typing import ClassVar, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class NodeConfig(BaseModel):
    """Configuration for a workflow node."""

    timeout_seconds: int = Field(
        default=300, ge=1, le=3600, description="Node execution timeout (1-3600s)"
    )
    max_retries: int = Field(
        default=0, ge=0, le=5, description="Maximum retry attempts (0-5)"
    )
    parallel_limit: Optional[int] = Field(
        default=None, ge=1, le=100, description="Max parallel executions (Parallel nodes only)"
    )
    expression: Optional[str] = Field(
        default=None, description="Jinja2 boolean expression for Condition nodes"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timeout_seconds": 300,
                "max_retries": 2,
                "parallel_limit": 10,
                "expression": "{{ node_1.output.success }}",
            }
        }
    )


class ParallelConfig(BaseModel):
    """Configuration for Parallel nodes."""

    parallel_nodes: List[str] = Field(..., min_length=1, max_length=50)
    wait_for: str = Field(default="all", pattern="^(all|any|\\d+)$")
    timeout_seconds: int = Field(default=300, ge=1, le=3600)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "parallel_nodes": ["node_1", "node_2", "node_3"],
                "wait_for": "all",
                "timeout_seconds": 300,
            }
        }
    )


class LoopConfig(BaseModel):
    """Configuration for Loop nodes."""

    mode: str = Field(..., pattern="^(count|while|foreach)$")
    count: Optional[int] = Field(default=None, ge=1, le=1000)
    condition: Optional[str] = Field(default=None)
    items: Optional[str] = Field(default=None)
    loop_node_id: str = Field(...)
    max_iterations: int = Field(default=100, ge=1, le=10000)

    @model_validator(mode="after")
    def validate_loop_mode(self) -> "LoopConfig":
        """Validate loop configuration based on mode."""
        if self.mode == "count" and self.count is None:
            raise ValueError("count is required for mode='count'")
        if self.mode == "while" and not self.condition:
            raise ValueError("condition is required for mode='while'")
        if self.mode == "foreach" and not self.items:
            raise ValueError("items is required for mode='foreach'")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mode": "count",
                "count": 10,
                "loop_node_id": "process_item",
                "max_iterations": 100,
            }
        }
    )


class SubWorkflowRef(BaseModel):
    """Pinned binding metadata for analyst-authored subworkflow calls."""

    binding_mode: str = Field(
        default="direct_runtime_id",
        pattern="^(direct_runtime_id|pinned_revision)$",
    )
    workflow_definition_key: Optional[str] = Field(default=None)
    workflow_revision_id: Optional[str] = Field(default=None)
    workflow_revision: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_binding_mode(self) -> "SubWorkflowRef":
        if self.binding_mode == "pinned_revision":
            if not self.workflow_definition_key:
                raise ValueError(
                    "workflow_definition_key is required for pinned_revision binding_mode"
                )
            if not self.workflow_revision_id:
                raise ValueError(
                    "workflow_revision_id is required for pinned_revision binding_mode"
                )
            if self.workflow_revision is None:
                raise ValueError("workflow_revision is required for pinned_revision binding_mode")
        return self


class SubWorkflowConfig(BaseModel):
    """Configuration for SubWorkflow nodes."""

    subworkflow_id: str = Field(...)
    subworkflow_ref: Optional[SubWorkflowRef] = Field(default=None)
    input_mapping: Dict[str, str] = Field(default_factory=dict)
    output_mapping: Dict[str, str] = Field(default_factory=dict)
    max_depth: int = Field(default=10, ge=1, le=20)

    @model_validator(mode="after")
    def validate_subworkflow_binding(self) -> "SubWorkflowConfig":
        if (
            self.subworkflow_ref
            and self.subworkflow_ref.binding_mode == "pinned_revision"
            and self.subworkflow_ref.workflow_revision_id != self.subworkflow_id
        ):
            raise ValueError("workflow_revision_id must match subworkflow_id for pinned_revision")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subworkflow_id": "sub_workflow_v1",
                "subworkflow_ref": {
                    "binding_mode": "pinned_revision",
                    "workflow_definition_key": "approval_gate",
                    "workflow_revision_id": "sub_workflow_v1",
                    "workflow_revision": 7,
                },
                "input_mapping": {"database.id": "target_db_id"},
                "output_mapping": {"result.status": "sub_status"},
                "max_depth": 10,
            }
        }
    )


class OperationRef(BaseModel):
    """Operation exposure binding for operation nodes."""

    alias: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="OperationExposure alias for template surface",
    )
    binding_mode: str = Field(
        default="alias_latest",
        pattern="^(alias_latest|pinned_exposure)$",
        description="Binding mode: alias_latest or pinned_exposure",
    )
    template_exposure_id: Optional[str] = Field(
        default=None,
        description="Pinned OperationExposure ID (required for pinned_exposure)",
    )
    template_exposure_revision: Optional[int] = Field(
        default=None,
        ge=1,
        description="Pinned OperationExposure revision (required for pinned_exposure)",
    )

    @field_validator("alias")
    @classmethod
    def validate_alias(cls, v: str) -> str:
        """Ensure alias is a non-empty trimmed string."""
        alias = v.strip()
        if not alias:
            raise ValueError("operation_ref.alias must not be empty")
        return alias

    @model_validator(mode="after")
    def validate_pinned_fields(self) -> "OperationRef":
        """Require exposure identity fields for pinned binding mode."""
        if self.binding_mode == "pinned_exposure":
            if not self.template_exposure_id:
                raise ValueError(
                    "template_exposure_id is required for pinned_exposure binding_mode"
                )
            if self.template_exposure_revision is None:
                raise ValueError(
                    "template_exposure_revision is required for pinned_exposure binding_mode"
                )
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "alias": "tpl-custom-load-extension",
                "binding_mode": "pinned_exposure",
                "template_exposure_id": "6b5a0b0f-6f4e-4a06-8f63-10c992bd0f8f",
                "template_exposure_revision": 12,
            }
        }
    )


class OperationIO(BaseModel):
    """Explicit data-flow contract for operation nodes."""

    mode: str = Field(
        default="implicit_legacy",
        pattern="^(implicit_legacy|explicit_strict)$",
        description="Data-flow mode: implicit_legacy or explicit_strict",
    )
    input_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="input mapping: target_path -> source_path",
    )
    output_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="output mapping: target_path -> source_path",
    )

    _PATH_SEGMENT_RE: ClassVar[re.Pattern[str]] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    _RESERVED_TARGET_ROOTS: ClassVar[set[str]] = {"nodes"}
    _RESERVED_TARGET_PREFIXES: ClassVar[tuple[str, ...]] = ("_", "node_")

    @classmethod
    def _normalize_mapping_path(cls, path: str, *, field_name: str) -> str:
        if not isinstance(path, str):
            raise ValueError(f"{field_name} must be a string path")

        normalized = path.strip()
        if not normalized:
            raise ValueError(f"{field_name} must not be empty")
        if normalized.startswith(".") or normalized.endswith(".") or ".." in normalized:
            raise ValueError(
                f"{field_name} must use dot-notation without empty segments: '{path}'"
            )

        segments = normalized.split(".")
        for segment in segments:
            if not cls._PATH_SEGMENT_RE.match(segment):
                raise ValueError(
                    f"{field_name} segment '{segment}' is invalid; use [A-Za-z_][A-Za-z0-9_]*"
                )
        return normalized

    @classmethod
    def _validate_mapping_object(
        cls,
        mapping: object,
        *,
        field_name: str,
    ) -> Dict[str, str]:
        if mapping is None:
            return {}
        if not isinstance(mapping, dict):
            raise ValueError(f"{field_name} must be an object with string path mappings")

        normalized_mapping: Dict[str, str] = {}
        for raw_target_path, raw_source_path in mapping.items():
            target_path = cls._normalize_mapping_path(
                raw_target_path,
                field_name=f"{field_name} target_path",
            )
            source_path = cls._normalize_mapping_path(
                raw_source_path,
                field_name=f"{field_name} source_path",
            )

            root_segment = target_path.split(".", 1)[0]
            if (
                root_segment in cls._RESERVED_TARGET_ROOTS
                or any(root_segment.startswith(prefix) for prefix in cls._RESERVED_TARGET_PREFIXES)
            ):
                raise ValueError(
                    f"{field_name} target_path '{target_path}' uses reserved root '{root_segment}'"
                )

            normalized_mapping[target_path] = source_path
        return normalized_mapping

    @field_validator("input_mapping", "output_mapping", mode="before")
    @classmethod
    def validate_mapping_types(cls, value: object, info) -> Dict[str, str]:
        return cls._validate_mapping_object(value, field_name=info.field_name)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mode": "explicit_strict",
                "input_mapping": {
                    "params.database_id": "workflow.input.database.id",
                    "params.extension_name": "node.prepare.output.extension_name",
                },
                "output_mapping": {
                    "workflow.state.install_result": "result",
                },
            }
        }
    )


class WorkflowNode(BaseModel):
    """Represents a single node in the workflow DAG."""

    id: str = Field(..., min_length=1, max_length=100, description="Unique node identifier")
    name: str = Field(..., min_length=1, max_length=200, description="Human-readable name")
    type: str = Field(
        ...,
        pattern="^(operation|condition|parallel|loop|subworkflow)$",
        description="Node type: operation, condition, parallel, loop, subworkflow",
    )
    template_id: Optional[str] = Field(default=None, description="Template ID for Operation nodes")
    operation_ref: Optional[OperationRef] = Field(
        default=None,
        description="OperationExposure binding for Operation nodes",
    )
    io: Optional[OperationIO] = Field(
        default=None,
        description="Operation node data-flow contract",
    )
    config: NodeConfig = Field(default_factory=NodeConfig, description="Node-specific config")

    # Node-type specific configurations
    parallel_config: Optional[ParallelConfig] = Field(
        default=None, description="Configuration for Parallel nodes"
    )
    loop_config: Optional[LoopConfig] = Field(
        default=None, description="Configuration for Loop nodes"
    )
    subworkflow_config: Optional[SubWorkflowConfig] = Field(
        default=None, description="Configuration for SubWorkflow nodes"
    )

    @field_validator("type")
    @classmethod
    def validate_node_type(cls, v: str) -> str:
        """Validate node type is supported."""
        allowed_types = {"operation", "condition", "parallel", "loop", "subworkflow"}
        if v not in allowed_types:
            raise ValueError(f"Node type must be one of {allowed_types}")
        return v

    @model_validator(mode="after")
    def validate_template_binding(self) -> "WorkflowNode":
        """
        Validate and normalize template binding fields based on node type.

        Deterministic migration rules for operation nodes:
        1) template_id only -> synthesize operation_ref(alias_latest)
        2) operation_ref only -> mirror alias into legacy template_id
        3) both present -> aliases must match
        """
        template_id = self.template_id.strip() if isinstance(self.template_id, str) else ""

        if self.type == "operation":
            if not template_id and not self.operation_ref:
                raise ValueError(
                    f"template_id or operation_ref is required for operation nodes (node: {self.id})"
                )
            if template_id and self.operation_ref is None:
                self.operation_ref = OperationRef(alias=template_id, binding_mode="alias_latest")
            elif not template_id and self.operation_ref:
                self.template_id = self.operation_ref.alias
            elif self.operation_ref and template_id and self.operation_ref.alias != template_id:
                raise ValueError(
                    "template_id must match operation_ref.alias "
                    f"for operation nodes (node: {self.id})"
                )
            if self.io is None:
                self.io = OperationIO()
        else:
            if self.template_id is not None:
                raise ValueError(
                    f"template_id must be None for {self.type} nodes (node: {self.id})"
                )
            if self.operation_ref is not None:
                raise ValueError(
                    f"operation_ref must be None for {self.type} nodes (node: {self.id})"
                )
            if self.io is not None:
                raise ValueError(f"io must be None for {self.type} nodes (node: {self.id})")
        return self

    # Note: validate_config removed - config validation now handled by validate_node_configs
    # for parallel/loop/subworkflow nodes (Week 8 refactoring)

    @model_validator(mode="after")
    def validate_expression(self) -> "WorkflowNode":
        """Validate expression for condition nodes."""
        if self.type == "condition":
            if not self.config.expression:
                raise ValueError(f"expression is required for condition nodes (node: {self.id})")
        return self

    @model_validator(mode="after")
    def validate_node_configs(self) -> "WorkflowNode":
        """Validate node-type specific configurations."""
        if self.type == "parallel":
            if self.parallel_config is None:
                raise ValueError(
                    f"parallel_config is required for parallel nodes (node: {self.id})"
                )
        elif self.parallel_config is not None:
            raise ValueError(
                f"parallel_config must be None for non-parallel nodes (node: {self.id})"
            )

        if self.type == "loop":
            if self.loop_config is None:
                raise ValueError(f"loop_config is required for loop nodes (node: {self.id})")
        elif self.loop_config is not None:
            raise ValueError(f"loop_config must be None for non-loop nodes (node: {self.id})")

        if self.type == "subworkflow":
            if self.subworkflow_config is None:
                raise ValueError(
                    f"subworkflow_config is required for subworkflow nodes (node: {self.id})"
                )
        elif self.subworkflow_config is not None:
            raise ValueError(
                f"subworkflow_config must be None for non-subworkflow nodes (node: {self.id})"
            )

        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "node_1",
                "name": "Block Users",
                "type": "operation",
                "template_id": "bulk_user_block_v1",
                "operation_ref": {
                    "alias": "bulk_user_block_v1",
                    "binding_mode": "alias_latest",
                },
                "io": {
                    "mode": "implicit_legacy",
                    "input_mapping": {},
                    "output_mapping": {},
                },
                "config": {"timeout_seconds": 300, "max_retries": 2},
            }
        }
    )


class WorkflowEdge(BaseModel):
    """Represents a directed edge in the workflow DAG."""

    from_node: str = Field(..., alias="from", description="Source node ID")
    to_node: str = Field(..., alias="to", description="Destination node ID")
    condition: Optional[str] = Field(
        default=None, description="Jinja2 expression for conditional edges"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "from": "node_1",
                "to": "node_2",
                "condition": "{{ node_1.output.success }}",
            }
        },
    )


class DAGStructure(BaseModel):
    """Complete DAG structure with nodes and edges."""

    nodes: List[WorkflowNode] = Field(..., min_length=1, description="List of workflow nodes")
    edges: List[WorkflowEdge] = Field(default_factory=list, description="List of directed edges")

    @field_validator("nodes")
    @classmethod
    def validate_unique_node_ids(cls, v: List[WorkflowNode]) -> List[WorkflowNode]:
        """Ensure all node IDs are unique."""
        node_ids = [node.id for node in v]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Node IDs must be unique within the workflow")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nodes": [
                    {"id": "start", "name": "Start", "type": "operation", "template_id": "init"},
                    {"id": "end", "name": "End", "type": "operation", "template_id": "cleanup"},
                ],
                "edges": [{"from": "start", "to": "end"}],
            }
        }
    )


class WorkflowConfig(BaseModel):
    """Global workflow configuration."""

    timeout_seconds: int = Field(
        default=3600, ge=60, le=86400, description="Total workflow timeout (60-86400s)"
    )
    max_retries: int = Field(default=0, ge=0, le=3, description="Workflow-level retry attempts")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timeout_seconds": 3600,
                "max_retries": 1,
            }
        }
    )


__all__ = [
    "DAGStructure",
    "LoopConfig",
    "NodeConfig",
    "OperationRef",
    "ParallelConfig",
    "SubWorkflowConfig",
    "SubWorkflowRef",
    "WorkflowConfig",
    "WorkflowEdge",
    "WorkflowNode",
]
