from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from apps.templates.workflow.authoring_contract import (
    DecisionField,
    DecisionRule,
    DecisionTableContract,
    DecisionTableRef,
    WorkflowDefinitionRef,
    build_workflow_definition_ref,
)


POOL_WORKFLOW_BINDING_CONTRACT_VERSION = "pool_workflow_binding.v1"


class PoolWorkflowBindingStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"


class PoolWorkflowBindingSelector(BaseModel):
    direction: str | None = None
    mode: str | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("direction", "mode")
    @classmethod
    def _normalize_optional_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class PoolWorkflowBindingContract(BaseModel):
    contract_version: str = Field(default=POOL_WORKFLOW_BINDING_CONTRACT_VERSION)
    binding_id: str = Field(..., min_length=1)
    pool_id: str = Field(..., min_length=1)
    workflow: WorkflowDefinitionRef
    decisions: list[DecisionTableRef] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    role_mapping: dict[str, str] = Field(default_factory=dict)
    selector: PoolWorkflowBindingSelector = Field(default_factory=PoolWorkflowBindingSelector)
    effective_from: date
    effective_to: date | None = None
    status: PoolWorkflowBindingStatus = PoolWorkflowBindingStatus.DRAFT

    @model_validator(mode="after")
    def validate_effective_range_and_decisions(self) -> "PoolWorkflowBindingContract":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be greater than or equal to effective_from")
        decision_refs = [
            (decision.decision_table_id, decision.decision_revision) for decision in self.decisions
        ]
        if len(decision_refs) != len(set(decision_refs)):
            raise ValueError("decision refs must be unique per decision_table_id/revision")
        for role, target in self.role_mapping.items():
            if not str(role or "").strip():
                raise ValueError("role_mapping keys must not be empty")
            if not str(target or "").strip():
                raise ValueError("role_mapping values must not be empty")
        return self


def build_pool_workflow_binding_lineage(
    *, binding: PoolWorkflowBindingContract
) -> dict[str, Any]:
    return {
        "binding_id": binding.binding_id,
        "pool_id": binding.pool_id,
        "status": binding.status.value,
        "workflow": {
            "workflow_definition_key": binding.workflow.workflow_definition_key,
            "workflow_revision_id": binding.workflow.workflow_revision_id,
            "workflow_revision": binding.workflow.workflow_revision,
            "workflow_name": binding.workflow.workflow_name,
        },
        "decisions": [
            {
                "decision_table_id": decision.decision_table_id,
                "decision_key": decision.decision_key,
                "decision_revision": decision.decision_revision,
            }
            for decision in binding.decisions
        ],
        "selector": binding.selector.model_dump(),
        "effective_from": binding.effective_from.isoformat(),
        "effective_to": binding.effective_to.isoformat() if binding.effective_to else None,
    }


__all__ = [
    "DecisionField",
    "DecisionRule",
    "DecisionTableContract",
    "DecisionTableRef",
    "POOL_WORKFLOW_BINDING_CONTRACT_VERSION",
    "PoolWorkflowBindingContract",
    "PoolWorkflowBindingSelector",
    "PoolWorkflowBindingStatus",
    "WorkflowDefinitionRef",
    "build_pool_workflow_binding_lineage",
    "build_workflow_definition_ref",
]
