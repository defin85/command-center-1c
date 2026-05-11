from __future__ import annotations

import hashlib
import json
from typing import Any

from .document_plan_artifact_contract import validate_compiled_document_policy_slots_snapshot
from .kvo17_purchase_split_intake import PURCHASE_KVO01_SLOT, PURCHASE_KVO17_SLOT
from .kvo17_purchase_split_preview import Kvo17PurchaseSplitPreview
from .kvo17_purchase_split_scheme import (
    KVO17_PURCHASE_SPLIT_POLICY_SLOTS,
    build_kvo17_purchase_split_document_policy,
)


KVO17_PURCHASE_SPLIT_DOCUMENT_PLAN_VERSION = "kvo17_purchase_split_document_plan.v1"


def build_kvo17_purchase_split_compiled_policy_slots() -> dict[str, dict[str, Any]]:
    slots = {
        slot_key: {
            "decision_table_id": f"kvo17_purchase_split_{slot_key}_policy",
            "decision_revision": 1,
            "document_policy_source": (
                f"workflow_binding.decision_table:kvo17_purchase_split_{slot_key}_policy:v1"
            ),
            "document_policy": build_kvo17_purchase_split_document_policy(slot_key=slot_key),
        }
        for slot_key in KVO17_PURCHASE_SPLIT_POLICY_SLOTS
    }
    return validate_compiled_document_policy_slots_snapshot(slots) or {}


def compile_kvo17_purchase_split_document_plan(
    *,
    preview: Kvo17PurchaseSplitPreview,
    compiled_policy_slots: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    policy_slots = validate_compiled_document_policy_slots_snapshot(
        compiled_policy_slots or build_kvo17_purchase_split_compiled_policy_slots()
    )
    if policy_slots is None:
        raise ValueError("KVO17 purchase split document plan requires compiled policy slots.")

    missing_slots = [
        slot_key
        for slot_key in KVO17_PURCHASE_SPLIT_POLICY_SLOTS
        if slot_key not in policy_slots
    ]
    if missing_slots:
        raise ValueError(
            "KVO17 purchase split document plan is missing policy slots: "
            + ", ".join(missing_slots)
        )

    branches = {
        PURCHASE_KVO01_SLOT: _compile_branch(
            slot_key=PURCHASE_KVO01_SLOT,
            preview=preview,
            policy_slot=policy_slots[PURCHASE_KVO01_SLOT],
        ),
        PURCHASE_KVO17_SLOT: _compile_branch(
            slot_key=PURCHASE_KVO17_SLOT,
            preview=preview,
            policy_slot=policy_slots[PURCHASE_KVO17_SLOT],
        ),
    }
    artifact = {
        "version": KVO17_PURCHASE_SPLIT_DOCUMENT_PLAN_VERSION,
        "classifier_revision": preview.classifier_revision,
        "source_document_identity": dict(preview.source_document_identity),
        "source_supplier_provenance": dict(preview.source_supplier_provenance),
        "content_hash": preview.content_hash,
        "idempotency": _build_idempotency_projection(preview=preview),
        "lineage": _build_lineage_projection(
            preview=preview,
            branches=branches,
        ),
        "policy_refs": [
            {
                "slot_key": slot_key,
                "decision_table_id": policy_slots[slot_key]["decision_table_id"],
                "decision_revision": policy_slots[slot_key]["decision_revision"],
                "policy_version": policy_slots[slot_key]["document_policy"]["version"],
                "source": policy_slots[slot_key]["document_policy_source"],
            }
            for slot_key in KVO17_PURCHASE_SPLIT_POLICY_SLOTS
        ],
        "branches": branches,
        "compile_summary": {
            "slots_count": len(KVO17_PURCHASE_SPLIT_POLICY_SLOTS),
            "branches_count": len(branches),
            "documents_count": sum(
                branch["documents_count"]
                for branch in branches.values()
            ),
            "diagnostics_count": len(preview.diagnostics),
        },
    }
    return artifact


def _compile_branch(
    *,
    slot_key: str,
    preview: Kvo17PurchaseSplitPreview,
    policy_slot: dict[str, Any],
) -> dict[str, Any]:
    branch_preview = preview.branches[slot_key]
    policy = policy_slot["document_policy"]
    policy_metadata = dict(policy.get("metadata") or {})
    branch_documents: list[dict[str, Any]] = []
    for chain in list(policy.get("chains") or []):
        for document in list(chain.get("documents") or []):
            branch_documents.append(
                {
                    "chain_id": chain["chain_id"],
                    "document_id": document["document_id"],
                    "entity_name": document["entity_name"],
                    "document_role": document["document_role"],
                    "field_mapping": dict(document["field_mapping"]),
                    "table_parts_mapping": dict(document["table_parts_mapping"]),
                    "link_rules": dict(document["link_rules"]),
                    "invoice_mode": document["invoice_mode"],
                    "source_document_identity": dict(preview.source_document_identity),
                    "source_supplier_provenance": dict(preview.source_supplier_provenance),
                    "technical_identity_workaround": dict(
                        policy_metadata.get("technical_identity_workaround") or {}
                    ),
                    "declaration_export": {
                        "source_document_identity": dict(preview.source_document_identity),
                        "source_supplier_provenance": dict(preview.source_supplier_provenance),
                        "supplier_role": "original_declaration_supplier",
                    },
                    "technical_posting_audit": {
                        "source": policy_slot["document_policy_source"],
                        "technical_identity_workaround": dict(
                            policy_metadata.get("technical_identity_workaround") or {}
                        ),
                        "original_supplier_remains_declaration_provenance": True,
                    },
                    "rows": [
                        {
                            "row_id": row["row_id"],
                            "row_fingerprint": row["row_fingerprint"],
                            "amount": row["amount"],
                            "vat_amount": row["vat_amount"],
                            "classification": dict(row["classification"]),
                        }
                        for row in list(branch_preview.get("rows") or [])
                    ],
                }
            )
    return {
        "slot_key": slot_key,
        "kvo": branch_preview["kvo"],
        "row_count": branch_preview["row_count"],
        "total_amount": branch_preview["total_amount"],
        "total_vat_amount": branch_preview["total_vat_amount"],
        "decision_table_id": policy_slot["decision_table_id"],
        "decision_revision": policy_slot["decision_revision"],
        "document_policy_source": policy_slot["document_policy_source"],
        "documents_count": len(branch_documents),
        "documents": branch_documents,
    }


def _build_idempotency_projection(
    *,
    preview: Kvo17PurchaseSplitPreview,
) -> dict[str, str]:
    source_document = dict(preview.source_document_identity)
    supplier = dict(preview.source_supplier_provenance)
    source_document_key = "|".join(
        (
            str(source_document.get("number") or ""),
            str(source_document.get("date") or ""),
            str(supplier.get("ref") or ""),
        )
    )
    payload = {
        "source_document_key": source_document_key,
        "classifier_revision": preview.classifier_revision,
        "content_hash": preview.content_hash,
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
        "source_document_key": source_document_key,
        "classifier_revision": preview.classifier_revision,
        "content_hash": preview.content_hash,
        "idempotency_key": f"kvo17-purchase-split:{digest}",
        "lineage_revision_ref": f"kvo17-purchase-split:{digest[:16]}",
    }


def _build_lineage_projection(
    *,
    preview: Kvo17PurchaseSplitPreview,
    branches: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    branch_lineage = []
    for slot_key in KVO17_PURCHASE_SPLIT_POLICY_SLOTS:
        branch = branches[slot_key]
        branch_lineage.append(
            {
                "slot_key": slot_key,
                "kvo": branch["kvo"],
                "row_count": branch["row_count"],
                "row_fingerprints": [
                    row["row_fingerprint"]
                    for document in branch["documents"]
                    for row in document["rows"]
                ],
            }
        )
    return {
        "declaration_export": {
            "source_document_identity": dict(preview.source_document_identity),
            "source_supplier_provenance": dict(preview.source_supplier_provenance),
            "supplier_role": "original_declaration_supplier",
        },
        "technical_posting_audit": {
            "technical_identity_workaround_visible": True,
            "silent_supplier_mutation_allowed": False,
            "original_supplier_remains_declaration_provenance": True,
            "policy_slots": list(KVO17_PURCHASE_SPLIT_POLICY_SLOTS),
        },
        "branches": branch_lineage,
    }


__all__ = [
    "KVO17_PURCHASE_SPLIT_DOCUMENT_PLAN_VERSION",
    "build_kvo17_purchase_split_compiled_policy_slots",
    "compile_kvo17_purchase_split_document_plan",
]
