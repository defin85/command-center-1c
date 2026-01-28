"""
Pydantic schemas used by the Workflow Engine models.

These schemas are used for JSON validation via django-pydantic-field.
"""

from typing import Dict, List, Optional

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


class SubWorkflowConfig(BaseModel):
    """Configuration for SubWorkflow nodes."""

    subworkflow_id: str = Field(...)
    input_mapping: Dict[str, str] = Field(default_factory=dict)
    output_mapping: Dict[str, str] = Field(default_factory=dict)
    max_depth: int = Field(default=10, ge=1, le=20)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subworkflow_id": "sub_workflow_v1",
                "input_mapping": {"database.id": "target_db_id"},
                "output_mapping": {"result.status": "sub_status"},
                "max_depth": 10,
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
    def validate_template_id(self) -> "WorkflowNode":
        """Validate template_id based on node type."""
        if self.type == "operation":
            if not self.template_id:
                raise ValueError(f"template_id is required for operation nodes (node: {self.id})")
        else:
            if self.template_id is not None:
                raise ValueError(
                    f"template_id must be None for {self.type} nodes (node: {self.id})"
                )
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
    "ParallelConfig",
    "SubWorkflowConfig",
    "WorkflowConfig",
    "WorkflowEdge",
    "WorkflowNode",
]
