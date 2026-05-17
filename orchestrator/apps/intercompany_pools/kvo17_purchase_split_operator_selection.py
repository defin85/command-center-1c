from __future__ import annotations

from typing import Any, Mapping

from .kvo17_purchase_split_intake import (
    KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION,
)
from .kvo17_generated_purchase_intake import (
    KVO17_GENERATED_PURCHASE_MANIFEST_VERSION,
    KVO17_GENERATED_PURCHASE_REQUEST_SCHEMA_VERSION,
    KVO17_GENERATED_PURCHASE_SOURCE_TYPE,
)
from .kvo17_purchase_split_scheme import (
    KVO17_GENERATED_PURCHASE_PAIR_SLOT,
    KVO17_PURCHASE_SPLIT_BINDING_PROFILE_CODE,
    KVO17_PURCHASE_SPLIT_BINDING_POLICY_SLOTS,
    KVO17_PURCHASE_SPLIT_SCHEME_CODE,
    KVO17_PURCHASE_SPLIT_SCHEMA_TEMPLATE_CODE,
    build_kvo17_purchase_split_scheme_metadata,
)
from .models import OrganizationPool
from .workflow_binding_attachments_store import list_pool_workflow_binding_attachments


def list_kvo17_purchase_split_operator_schemes(
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
    if str(resolved_profile.get("code") or "").strip() != KVO17_PURCHASE_SPLIT_BINDING_PROFILE_CODE:
        return None

    decisions = list(resolved_profile.get("decisions") or [])
    slot_keys = [
        str(decision.get("slot_key") or "").strip()
        for decision in decisions
        if isinstance(decision, Mapping)
    ]
    if slot_keys != list(KVO17_PURCHASE_SPLIT_BINDING_POLICY_SLOTS):
        return None

    parameters = dict(resolved_profile.get("parameters") or {})
    if str(parameters.get("classifier_revision") or "").strip() != KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION:
        return None

    topology_summary = dict(resolved_profile.get("topology_template_compatibility") or {})
    if not bool(topology_summary.get("topology_aware_ready")):
        return None

    scheme_metadata = build_kvo17_purchase_split_scheme_metadata()
    return {
        "scheme_code": KVO17_PURCHASE_SPLIT_SCHEME_CODE,
        "schema_template_code": KVO17_PURCHASE_SPLIT_SCHEMA_TEMPLATE_CODE,
        "binding_id": binding["binding_id"],
        "binding_profile_revision_id": binding["binding_profile_revision_id"],
        "binding_profile_revision_number": binding["binding_profile_revision_number"],
        "classifier_revision": KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION,
        "document_policy_slots": list(KVO17_PURCHASE_SPLIT_BINDING_POLICY_SLOTS),
        "source_requirements": dict(scheme_metadata["required_source_provenance"]),
        "preview_capabilities": {
            "branch_totals": True,
            "duplicate_source_diagnostics": True,
            "source_document_identity": True,
            "source_supplier_provenance": True,
        },
        "generated_purchase_mode": _build_generated_purchase_mode(parameters=parameters),
    }


def _build_generated_purchase_mode(*, parameters: Mapping[str, Any]) -> dict[str, Any]:
    supported = bool(parameters.get("generated_purchase_supported"))
    source_type = str(parameters.get("generated_purchase_source_type") or "").strip()
    available = supported and source_type == KVO17_GENERATED_PURCHASE_SOURCE_TYPE
    return {
        "available": available,
        "source_type": KVO17_GENERATED_PURCHASE_SOURCE_TYPE,
        "request_schema_version": KVO17_GENERATED_PURCHASE_REQUEST_SCHEMA_VERSION,
        "manifest_version": KVO17_GENERATED_PURCHASE_MANIFEST_VERSION,
        "document_policy_slots": [KVO17_GENERATED_PURCHASE_PAIR_SLOT],
        "publication_policy_slot": KVO17_GENERATED_PURCHASE_PAIR_SLOT,
        "blocking_diagnostics": []
        if available
        else [
            {
                "code": "KVO17_GENERATED_PURCHASE_CAPABILITY_MISSING",
                "severity": "error",
                "detail": "Selected KVO17 binding does not declare generated purchase support.",
            }
        ],
    }


__all__ = ["list_kvo17_purchase_split_operator_schemes"]
