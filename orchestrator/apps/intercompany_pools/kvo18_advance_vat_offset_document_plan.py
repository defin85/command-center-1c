from __future__ import annotations

import hashlib
import json
from typing import Any

from .document_plan_artifact_contract import validate_compiled_document_policy_slots_snapshot
from .kvo18_advance_vat_offset_intake import (
    ADVANCE_INVOICE_KVO01_SLOT,
    ADVANCE_OFFSET_KVO18_SLOT,
    CASH_RECEIPT_ORDER_SLOT,
    DECLARATION_EVIDENCE_SLOT,
    KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION,
    KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS,
)
from .kvo18_advance_vat_offset_preview import Kvo18AdvanceVatOffsetPreview
from .kvo18_advance_vat_offset_scheme import build_kvo18_advance_vat_offset_document_policy


KVO18_ADVANCE_VAT_OFFSET_DOCUMENT_PLAN_VERSION = "kvo18_advance_vat_offset_document_plan.v1"


def build_kvo18_advance_vat_offset_compiled_policy_slots() -> dict[str, dict[str, Any]]:
    slots = {
        slot_key: {
            "decision_table_id": f"kvo18_advance_vat_offset_{slot_key}_policy",
            "decision_revision": 1,
            "document_policy_source": (
                f"workflow_binding.decision_table:kvo18_advance_vat_offset_{slot_key}_policy:v1"
            ),
            "document_policy": build_kvo18_advance_vat_offset_document_policy(slot_key=slot_key),
        }
        for slot_key in KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS
    }
    return validate_compiled_document_policy_slots_snapshot(slots) or {}


def compile_kvo18_advance_vat_offset_document_plan(
    *,
    preview: Kvo18AdvanceVatOffsetPreview,
    compiled_policy_slots: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    policy_slots = validate_compiled_document_policy_slots_snapshot(
        compiled_policy_slots or build_kvo18_advance_vat_offset_compiled_policy_slots()
    )
    if policy_slots is None:
        raise ValueError("KVO18 advance VAT offset document plan requires compiled policy slots.")

    missing_slots = [
        slot_key
        for slot_key in KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS
        if slot_key not in policy_slots
    ]
    if missing_slots:
        raise ValueError(
            "KVO18 advance VAT offset document plan is missing policy slots: "
            + ", ".join(missing_slots)
        )

    stages = {
        slot_key: _compile_stage(
            slot_key=slot_key,
            preview=preview,
            policy_slot=policy_slots[slot_key],
        )
        for slot_key in KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS
    }
    return {
        "version": KVO18_ADVANCE_VAT_OFFSET_DOCUMENT_PLAN_VERSION,
        "policy_revision": preview.policy_revision,
        "content_hash": preview.content_hash,
        "totals": {
            "row_count": preview.row_count,
            "total_amount": preview.total_amount,
            "total_vat_amount": preview.total_vat_amount,
            "currency": preview.currency,
        },
        "idempotency": _build_idempotency_projection(preview=preview),
        "lineage": _build_lineage_projection(preview=preview, stages=stages),
        "policy_refs": [
            {
                "slot_key": slot_key,
                "decision_table_id": policy_slots[slot_key]["decision_table_id"],
                "decision_revision": policy_slots[slot_key]["decision_revision"],
                "policy_version": policy_slots[slot_key]["document_policy"]["version"],
                "source": policy_slots[slot_key]["document_policy_source"],
            }
            for slot_key in KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS
        ],
        "stages": stages,
        "partial_failure_policy": {
            "scope": "per_row_per_stage",
            "downstream_requires_prior_stage_evidence": True,
            "silent_partial_offset_allowed": False,
        },
        "compile_summary": {
            "slots_count": len(KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS),
            "stages_count": len(stages),
            "documents_count": sum(stage["documents_count"] for stage in stages.values()),
            "diagnostics_count": len(preview.diagnostics),
        },
    }


def _compile_stage(
    *,
    slot_key: str,
    preview: Kvo18AdvanceVatOffsetPreview,
    policy_slot: dict[str, Any],
) -> dict[str, Any]:
    policy = policy_slot["document_policy"]
    policy_metadata = dict(policy.get("metadata") or {})
    stage_preview = dict(preview.stages[slot_key])
    documents: list[dict[str, Any]] = []
    for chain in list(policy.get("chains") or []):
        for document in list(chain.get("documents") or []):
            documents.append(
                {
                    "chain_id": chain["chain_id"],
                    "document_id": document["document_id"],
                    "entity_name": document["entity_name"],
                    "document_role": document["document_role"],
                    "field_mapping": dict(document["field_mapping"]),
                    "table_parts_mapping": dict(document["table_parts_mapping"]),
                    "link_rules": dict(document["link_rules"]),
                    "invoice_mode": document["invoice_mode"],
                    "stage": stage_preview,
                    "technical_realization_policy": dict(
                        policy_metadata.get("technical_realization") or {}
                    ),
                    "declaration_evidence": dict(
                        policy_metadata.get("declaration_evidence") or {}
                    ),
                    "rows": [
                        {
                            "row_id": row["row_id"],
                            "row_fingerprint": row["row_fingerprint"],
                            "counterparty": dict(row["counterparty"]),
                            "contract": dict(row["contract"]),
                            "operation_date": row["operation_date"],
                            "amount": row["amount"],
                            "vat_rate": row["vat_rate"],
                            "vat_amount": row["vat_amount"],
                            "lineage": dict(row["lineage"]),
                        }
                        for row in preview.rows
                    ],
                }
            )
    return {
        "slot_key": slot_key,
        "action_label": stage_preview["label"],
        "state": stage_preview["state"],
        "prerequisites": list(stage_preview["prerequisites"]),
        "produces": list(stage_preview["produces"]),
        "decision_table_id": policy_slot["decision_table_id"],
        "decision_revision": policy_slot["decision_revision"],
        "document_policy_source": policy_slot["document_policy_source"],
        "documents_count": len(documents),
        "documents": documents,
    }


def _build_idempotency_projection(*, preview: Kvo18AdvanceVatOffsetPreview) -> dict[str, str]:
    payload = {
        "policy_revision": preview.policy_revision,
        "content_hash": preview.content_hash,
        "row_fingerprints": [row["row_fingerprint"] for row in preview.rows],
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "policy_revision": preview.policy_revision,
        "content_hash": preview.content_hash,
        "idempotency_key": f"kvo18-advance-vat-offset:{digest}",
        "lineage_revision_ref": f"kvo18-advance-vat-offset:{digest[:16]}",
    }


def _build_lineage_projection(
    *,
    preview: Kvo18AdvanceVatOffsetPreview,
    stages: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "policy_revision": KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION,
        "stage_order": list(KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS),
        "row_fingerprints": [row["row_fingerprint"] for row in preview.rows],
        "stage_evidence": {
            slot_key: {
                "produces": list(stage["produces"]),
                "prerequisites": list(stage["prerequisites"]),
                "documents": [
                    {
                        "document_id": document["document_id"],
                        "entity_name": document["entity_name"],
                        "document_role": document["document_role"],
                    }
                    for document in stage["documents"]
                ],
            }
            for slot_key, stage in stages.items()
        },
        "final_acceptance": {
            "sales_book_kvo01_required": True,
            "purchase_book_kvo18_required": True,
            "declaration_projection_required": True,
            "document_creation_alone_is_success": False,
        },
    }


__all__ = [
    "KVO18_ADVANCE_VAT_OFFSET_DOCUMENT_PLAN_VERSION",
    "build_kvo18_advance_vat_offset_compiled_policy_slots",
    "compile_kvo18_advance_vat_offset_document_plan",
]
