from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from .document_policy_contract import DOCUMENT_POLICY_METADATA_KEY
from apps.templates.workflow.authoring_contract import (
    DecisionField,
    DecisionRule,
    DecisionTableContract,
    DecisionTableRef,
    WorkflowDefinitionRef,
    build_workflow_definition_ref,
)


POOL_WORKFLOW_BINDING_CONTRACT_VERSION = "pool_workflow_binding.v1"
POOL_DOCUMENT_POLICY_SLOT_DUPLICATE = "POOL_DOCUMENT_POLICY_SLOT_DUPLICATE"


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


class PoolWorkflowBindingDecisionRef(BaseModel):
    decision_table_id: str = Field(..., min_length=1)
    decision_key: str = Field(..., min_length=1)
    decision_revision: int = Field(..., ge=1)
    slot_key: str | None = None

    @field_validator("decision_table_id", "decision_key")
    @classmethod
    def _normalize_required_string(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("decision ref values must not be empty")
        return normalized

    @field_validator("slot_key")
    @classmethod
    def _normalize_optional_slot_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def resolved_slot_key(self) -> str | None:
        if self.slot_key:
            return self.slot_key
        if self.decision_key == DOCUMENT_POLICY_METADATA_KEY:
            return DOCUMENT_POLICY_METADATA_KEY
        return None


class PoolWorkflowBindingContract(BaseModel):
    contract_version: str = Field(default=POOL_WORKFLOW_BINDING_CONTRACT_VERSION)
    binding_id: str = Field(..., min_length=1)
    pool_id: str = Field(..., min_length=1)
    workflow: WorkflowDefinitionRef
    decisions: list[PoolWorkflowBindingDecisionRef] = Field(default_factory=list)
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
            (
                decision.decision_table_id,
                decision.decision_key,
                decision.decision_revision,
                decision.slot_key or "",
            )
            for decision in self.decisions
        ]
        if len(decision_refs) != len(set(decision_refs)):
            raise ValueError("decision refs must be unique per decision_table_id/revision/slot_key")
        decision_keys = [
            str(decision.decision_key or "").strip()
            for decision in self.decisions
            if decision.decision_key != DOCUMENT_POLICY_METADATA_KEY
        ]
        if len(decision_keys) != len(set(decision_keys)):
            raise ValueError("decision_key values must be unique within non-slot binding decisions")
        slot_keys = [
            slot_key
            for decision in self.decisions
            if (slot_key := decision.resolved_slot_key())
        ]
        if len(slot_keys) != len(set(slot_keys)):
            raise ValueError(f"{POOL_DOCUMENT_POLICY_SLOT_DUPLICATE}: slot_key values must be unique within binding decisions")
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
            decision.model_dump(mode="json", exclude_none=True)
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
    "PoolWorkflowBindingDecisionRef",
    "POOL_DOCUMENT_POLICY_SLOT_DUPLICATE",
    "POOL_WORKFLOW_BINDING_CONTRACT_VERSION",
    "PoolWorkflowBindingContract",
    "PoolWorkflowBindingSelector",
    "PoolWorkflowBindingStatus",
    "WorkflowDefinitionRef",
    "build_pool_workflow_binding_lineage",
    "build_workflow_definition_ref",
]
