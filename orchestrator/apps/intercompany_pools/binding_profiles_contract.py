from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from apps.templates.workflow.authoring_contract import WorkflowDefinitionRef

from .document_policy_contract import DOCUMENT_POLICY_METADATA_KEY
from .workflow_authoring_contract import (
    POOL_DOCUMENT_POLICY_SLOT_DUPLICATE,
    PoolWorkflowBindingDecisionRef,
)


BINDING_PROFILE_CONTRACT_VERSION = "binding_profile.v1"
BINDING_PROFILE_REVISION_CONTRACT_VERSION = "binding_profile_revision.v1"
_PROFILE_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class BindingProfileStatus(str, Enum):
    ACTIVE = "active"
    DEACTIVATED = "deactivated"


class BindingProfileRevisionContract(BaseModel):
    contract_version: str = Field(default=BINDING_PROFILE_REVISION_CONTRACT_VERSION)
    workflow: WorkflowDefinitionRef
    decisions: list[PoolWorkflowBindingDecisionRef] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    role_mapping: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_revision_payload(self) -> "BindingProfileRevisionContract":
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

        slot_keys = [slot_key for decision in self.decisions if (slot_key := decision.resolved_slot_key())]
        if len(slot_keys) != len(set(slot_keys)):
            raise ValueError(f"{POOL_DOCUMENT_POLICY_SLOT_DUPLICATE}: slot_key values must be unique within binding decisions")

        for role, target in self.role_mapping.items():
            if not str(role or "").strip():
                raise ValueError("role_mapping keys must not be empty")
            if not str(target or "").strip():
                raise ValueError("role_mapping values must not be empty")

        return self


class BindingProfileCreateContract(BaseModel):
    contract_version: str = Field(default=BINDING_PROFILE_CONTRACT_VERSION)
    code: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str = ""
    revision: BindingProfileRevisionContract

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("code must not be empty")
        if not _PROFILE_CODE_PATTERN.fullmatch(normalized):
            raise ValueError("code must contain only letters, numbers, hyphen, or underscore")
        return normalized

    @field_validator("name", "description")
    @classmethod
    def _normalize_text(cls, value: str) -> str:
        return value.strip()


__all__ = [
    "BINDING_PROFILE_CONTRACT_VERSION",
    "BINDING_PROFILE_REVISION_CONTRACT_VERSION",
    "BindingProfileCreateContract",
    "BindingProfileRevisionContract",
    "BindingProfileStatus",
]
