from __future__ import annotations

from typing import Any, Mapping

from .kvo18_advance_vat_offset_intake import (
    KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION,
    KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS,
)
from .kvo18_advance_vat_offset_scheme import (
    KVO18_ADVANCE_VAT_OFFSET_BINDING_PROFILE_CODE,
    KVO18_ADVANCE_VAT_OFFSET_SCHEME_CODE,
    KVO18_ADVANCE_VAT_OFFSET_SCHEMA_TEMPLATE_CODE,
    build_kvo18_advance_vat_offset_scheme_metadata,
)
from .models import OrganizationPool
from .workflow_binding_attachments_store import list_pool_workflow_binding_attachments


def list_kvo18_advance_vat_offset_operator_schemes(
    *,
    pool: OrganizationPool,
) -> list[dict[str, Any]]:
    schemes: list[dict[str, Any]] = []
    for binding in list_pool_workflow_binding_attachments(pool=pool):
        read_model = _build_operator_scheme_read_model(binding=binding)
        if read_model is not None:
            schemes.append(read_model)
    return schemes


def _build_operator_scheme_read_model(
    *,
    binding: Mapping[str, Any],
) -> dict[str, Any] | None:
    if str(binding.get("status") or "").strip() != "active":
        return None
    resolved_profile = binding.get("resolved_profile")
    if not isinstance(resolved_profile, Mapping):
        return None
    if str(resolved_profile.get("code") or "").strip() != KVO18_ADVANCE_VAT_OFFSET_BINDING_PROFILE_CODE:
        return None

    decisions = list(resolved_profile.get("decisions") or [])
    slot_keys = [
        str(decision.get("slot_key") or "").strip()
        for decision in decisions
        if isinstance(decision, Mapping)
    ]
    if slot_keys != list(KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS):
        return None

    parameters = dict(resolved_profile.get("parameters") or {})
    if str(parameters.get("policy_revision") or "").strip() != KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION:
        return None

    topology_summary = dict(resolved_profile.get("topology_template_compatibility") or {})
    if not bool(topology_summary.get("topology_aware_ready")):
        return None

    scheme_metadata = build_kvo18_advance_vat_offset_scheme_metadata()
    return {
        "scheme_code": KVO18_ADVANCE_VAT_OFFSET_SCHEME_CODE,
        "schema_template_code": KVO18_ADVANCE_VAT_OFFSET_SCHEMA_TEMPLATE_CODE,
        "binding_id": binding["binding_id"],
        "binding_profile_revision_id": binding["binding_profile_revision_id"],
        "binding_profile_revision_number": binding["binding_profile_revision_number"],
        "policy_revision": KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION,
        "document_policy_slots": list(KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS),
        "source_requirements": dict(scheme_metadata["required_source_provenance"]),
        "staged_controls": list(scheme_metadata["staged_controls"]),
        "preview_capabilities": {
            "stage_blockers": True,
            "technical_realization_policy": True,
            "book_evidence": True,
            "declaration_readiness": True,
        },
    }


__all__ = ["list_kvo18_advance_vat_offset_operator_schemes"]
