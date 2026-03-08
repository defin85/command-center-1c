from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.templates.workflow.models import WorkflowTemplate


WORKFLOW_DEFINITION_CONTRACT_VERSION = "workflow_definition.v1"
DECISION_TABLE_CONTRACT_VERSION = "decision_table.v1"
WORKFLOW_COMPILE_BOUNDARY_CONTRACT_VERSION = "workflow_compile_boundary.v1"
WORKFLOW_CONSTRUCT_VISIBILITY_CONTRACT_VERSION = "workflow_construct_visibility.v1"


class WorkflowAuthoringNodeType(str, Enum):
    OPERATION_TASK = "operation_task"
    DECISION_GATE = "decision_gate"
    APPROVAL_GATE = "approval_gate"
    SUBWORKFLOW_CALL = "subworkflow_call"


class DecisionHitPolicy(str, Enum):
    FIRST_MATCH = "first_match"


class DecisionValidationMode(str, Enum):
    FAIL_CLOSED = "fail_closed"


class DecisionExecutionMode(str, Enum):
    COMPILE_TIME_ONLY = "compile_time_only"


class WorkflowDefinitionRef(BaseModel):
    contract_version: str = Field(default=WORKFLOW_DEFINITION_CONTRACT_VERSION)
    workflow_definition_key: str = Field(..., min_length=1)
    workflow_revision_id: str = Field(..., min_length=1)
    workflow_revision: int = Field(..., ge=1)
    workflow_name: str = Field(..., min_length=1)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "contract_version": WORKFLOW_DEFINITION_CONTRACT_VERSION,
                "workflow_definition_key": "f0a53276-1fd2-4c9b-bfab-40c8634f1234",
                "workflow_revision_id": "d9e2b5db-7116-4437-b13e-d7fc2647aa10",
                "workflow_revision": 3,
                "workflow_name": "services_publication",
            }
        }
    )


class DecisionField(BaseModel):
    name: str = Field(..., min_length=1)
    value_type: str = Field(..., min_length=1)
    required: bool = True

    @field_validator("name", "value_type")
    @classmethod
    def _normalize_non_empty(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("field values must not be empty")
        return normalized


class DecisionRule(BaseModel):
    rule_id: str = Field(..., min_length=1)
    conditions: dict[str, object] = Field(default_factory=dict)
    outputs: dict[str, object] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0)

    @field_validator("rule_id")
    @classmethod
    def _normalize_rule_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("rule_id must not be empty")
        return normalized


class DecisionTableContract(BaseModel):
    contract_version: str = Field(default=DECISION_TABLE_CONTRACT_VERSION)
    decision_table_id: str = Field(..., min_length=1)
    decision_key: str = Field(..., min_length=1)
    decision_revision: int = Field(..., ge=1)
    name: str = Field(..., min_length=1)
    inputs: list[DecisionField] = Field(default_factory=list)
    outputs: list[DecisionField] = Field(default_factory=list)
    rules: list[DecisionRule] = Field(..., min_length=1)
    hit_policy: DecisionHitPolicy = DecisionHitPolicy.FIRST_MATCH
    validation_mode: DecisionValidationMode = DecisionValidationMode.FAIL_CLOSED

    @model_validator(mode="after")
    def validate_fail_closed_contract(self) -> "DecisionTableContract":
        input_names = [field.name for field in self.inputs]
        if len(input_names) != len(set(input_names)):
            raise ValueError("decision inputs must be unique")

        output_names = [field.name for field in self.outputs]
        if len(output_names) != len(set(output_names)):
            raise ValueError("decision outputs must be unique")

        rule_ids = [rule.rule_id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("decision rule_id values must be unique")

        priorities = [rule.priority for rule in self.rules]
        if len(priorities) != len(set(priorities)):
            raise ValueError("decision rule priorities must be unique")

        known_inputs = set(input_names)
        known_outputs = set(output_names)

        for rule in self.rules:
            unknown_inputs = sorted(set(rule.conditions) - known_inputs)
            if unknown_inputs:
                raise ValueError(
                    "decision rule conditions reference unknown input fields: "
                    + ", ".join(unknown_inputs)
                )

            unknown_outputs = sorted(set(rule.outputs) - known_outputs)
            if unknown_outputs:
                raise ValueError(
                    "decision rule outputs reference unknown output fields: "
                    + ", ".join(unknown_outputs)
                )

            if not rule.outputs:
                raise ValueError("decision rules must produce at least one output")

        return self


class DecisionTableRef(BaseModel):
    decision_table_id: str = Field(..., min_length=1)
    decision_key: str = Field(..., min_length=1)
    decision_revision: int = Field(..., ge=1)


class WorkflowCompileBoundaryContract(BaseModel):
    contract_version: str = Field(default=WORKFLOW_COMPILE_BOUNDARY_CONTRACT_VERSION)
    workflow: WorkflowDefinitionRef
    decisions: list[DecisionTableRef] = Field(default_factory=list)
    authoring_node_types: list[WorkflowAuthoringNodeType] = Field(
        default_factory=lambda: [
            WorkflowAuthoringNodeType.OPERATION_TASK,
            WorkflowAuthoringNodeType.DECISION_GATE,
            WorkflowAuthoringNodeType.APPROVAL_GATE,
            WorkflowAuthoringNodeType.SUBWORKFLOW_CALL,
        ]
    )
    runtime_node_types: list[str] = Field(
        default_factory=lambda: ["operation", "condition", "parallel", "loop", "subworkflow"]
    )
    internal_runtime_only_node_types: list[str] = Field(
        default_factory=lambda: ["condition", "parallel", "loop"]
    )
    runtime_projection_contracts: list[str] = Field(
        default_factory=lambda: ["document_policy.v1", "document_plan_artifact.v1"]
    )
    decision_execution_mode: DecisionExecutionMode = DecisionExecutionMode.COMPILE_TIME_ONLY
    compile_mode: str = Field(default="binding_compiled_projection")

    @model_validator(mode="after")
    def validate_boundary(self) -> "WorkflowCompileBoundaryContract":
        runtime_types = set(self.runtime_node_types)
        if not set(self.internal_runtime_only_node_types).issubset(runtime_types):
            raise ValueError("internal_runtime_only_node_types must be subset of runtime_node_types")
        if len(self.authoring_node_types) != len(set(self.authoring_node_types)):
            raise ValueError("authoring_node_types must be unique")
        if len(self.runtime_projection_contracts) != len(set(self.runtime_projection_contracts)):
            raise ValueError("runtime_projection_contracts must be unique")
        return self


class WorkflowConstructVisibilityContract(BaseModel):
    contract_version: str = Field(default=WORKFLOW_CONSTRUCT_VISIBILITY_CONTRACT_VERSION)
    public_constructs: list[str] = Field(
        default_factory=lambda: [
            "operation_task",
            "decision_gate",
            "approval_gate",
            "subworkflow_call",
            "explicit_io",
            "pinned_template_binding",
            "pinned_subworkflow_binding",
            "decision_table",
        ]
    )
    internal_runtime_only_constructs: list[str] = Field(
        default_factory=lambda: [
            "condition",
            "parallel",
            "loop",
            "generated_runtime_projection",
            "compiled_document_policy",
            "document_plan_artifact",
        ]
    )
    compatibility_constructs: list[str] = Field(
        default_factory=lambda: [
            "template_id",
            "alias_latest_operation_binding",
            "workflow_executor_kind_template",
        ]
    )

    @model_validator(mode="after")
    def validate_no_overlap(self) -> "WorkflowConstructVisibilityContract":
        all_groups = {
            "public_constructs": set(self.public_constructs),
            "internal_runtime_only_constructs": set(self.internal_runtime_only_constructs),
            "compatibility_constructs": set(self.compatibility_constructs),
        }
        for field_name, values in all_groups.items():
            original = getattr(self, field_name)
            if len(original) != len(values):
                raise ValueError(f"{field_name} must be unique")
        if all_groups["public_constructs"] & all_groups["internal_runtime_only_constructs"]:
            raise ValueError("public and internal constructs must not overlap")
        if all_groups["public_constructs"] & all_groups["compatibility_constructs"]:
            raise ValueError("public and compatibility constructs must not overlap")
        if all_groups["internal_runtime_only_constructs"] & all_groups["compatibility_constructs"]:
            raise ValueError("internal and compatibility constructs must not overlap")
        return self


def derive_workflow_definition_key(*, workflow_template: WorkflowTemplate) -> str:
    current = workflow_template
    visited: set[str] = set()

    while current.parent_version_id:
        current_id = str(current.id)
        if current_id in visited:
            break
        visited.add(current_id)
        parent = current.parent_version
        if parent is None:
            break
        current = parent

    return str(current.id)


def build_workflow_definition_ref(*, workflow_template: WorkflowTemplate) -> WorkflowDefinitionRef:
    return WorkflowDefinitionRef(
        workflow_definition_key=derive_workflow_definition_key(workflow_template=workflow_template),
        workflow_revision_id=str(workflow_template.id),
        workflow_revision=int(workflow_template.version_number),
        workflow_name=str(workflow_template.name),
    )


def build_workflow_compile_boundary(
    *,
    workflow_template: WorkflowTemplate,
    decisions: list[DecisionTableRef] | None = None,
) -> WorkflowCompileBoundaryContract:
    return WorkflowCompileBoundaryContract(
        workflow=build_workflow_definition_ref(workflow_template=workflow_template),
        decisions=list(decisions or []),
    )


def build_workflow_construct_visibility() -> WorkflowConstructVisibilityContract:
    return WorkflowConstructVisibilityContract()


__all__ = [
    "DECISION_TABLE_CONTRACT_VERSION",
    "WORKFLOW_COMPILE_BOUNDARY_CONTRACT_VERSION",
    "WORKFLOW_CONSTRUCT_VISIBILITY_CONTRACT_VERSION",
    "WORKFLOW_DEFINITION_CONTRACT_VERSION",
    "DecisionExecutionMode",
    "DecisionField",
    "DecisionHitPolicy",
    "DecisionRule",
    "DecisionTableContract",
    "DecisionTableRef",
    "DecisionValidationMode",
    "WorkflowAuthoringNodeType",
    "WorkflowCompileBoundaryContract",
    "WorkflowConstructVisibilityContract",
    "WorkflowDefinitionRef",
    "build_workflow_construct_visibility",
    "build_workflow_compile_boundary",
    "build_workflow_definition_ref",
    "derive_workflow_definition_key",
]
