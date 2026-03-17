from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


POOL_WORKFLOW_BINDING_ATTACHMENT_CONTRACT_VERSION = "pool_workflow_binding.v2"


class PoolWorkflowBindingAttachmentStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"


class PoolWorkflowBindingAttachmentSelector(BaseModel):
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


class PoolWorkflowBindingAttachmentContract(BaseModel):
    contract_version: str = Field(default=POOL_WORKFLOW_BINDING_ATTACHMENT_CONTRACT_VERSION)
    binding_id: str = Field(..., min_length=1)
    pool_id: str = Field(..., min_length=1)
    binding_profile_revision_id: str = Field(..., min_length=1)
    selector: PoolWorkflowBindingAttachmentSelector = Field(default_factory=PoolWorkflowBindingAttachmentSelector)
    effective_from: date
    effective_to: date | None = None
    status: PoolWorkflowBindingAttachmentStatus = PoolWorkflowBindingAttachmentStatus.DRAFT

    @model_validator(mode="after")
    def validate_effective_range(self) -> "PoolWorkflowBindingAttachmentContract":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be greater than or equal to effective_from")
        return self


__all__ = [
    "POOL_WORKFLOW_BINDING_ATTACHMENT_CONTRACT_VERSION",
    "PoolWorkflowBindingAttachmentContract",
    "PoolWorkflowBindingAttachmentSelector",
    "PoolWorkflowBindingAttachmentStatus",
]
