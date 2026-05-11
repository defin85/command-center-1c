from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from .kvo17_purchase_split_intake import (
    KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION,
    PURCHASE_KVO01_SLOT,
    PURCHASE_KVO17_SLOT,
    Kvo17PurchaseSplitBatchNormalizationResult,
    Kvo17PurchaseSplitClassification,
    Kvo17PurchaseSplitIntakeRow,
    classify_kvo17_purchase_split_row,
)


KVO17_DUPLICATE_ROW_ID = "KVO17_DUPLICATE_ROW_ID"
KVO17_DUPLICATE_ROW_FINGERPRINT = "KVO17_DUPLICATE_ROW_FINGERPRINT"


@dataclass(frozen=True)
class Kvo17PurchaseSplitPreview:
    classifier_revision: str
    source_document_identity: dict[str, str]
    source_supplier_provenance: dict[str, str]
    branches: dict[str, dict[str, Any]]
    diagnostics: list[dict[str, Any]]
    content_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "classifier_revision": self.classifier_revision,
            "source_document_identity": dict(self.source_document_identity),
            "source_supplier_provenance": dict(self.source_supplier_provenance),
            "branches": dict(self.branches),
            "diagnostics": list(self.diagnostics),
            "content_hash": self.content_hash,
        }


def build_kvo17_purchase_split_preview(
    *,
    batch: Kvo17PurchaseSplitBatchNormalizationResult,
    classifier_config: Mapping[str, Any] | None = None,
) -> Kvo17PurchaseSplitPreview:
    branch_rows: dict[str, list[dict[str, Any]]] = {
        PURCHASE_KVO01_SLOT: [],
        PURCHASE_KVO17_SLOT: [],
    }
    classifications: list[Kvo17PurchaseSplitClassification] = []
    for row in batch.rows:
        classification = classify_kvo17_purchase_split_row(
            row=row,
            config=classifier_config,
        )
        classifications.append(classification)
        branch_rows[classification.branch].append(
            _preview_row(
                row=row,
                classification=classification,
            )
        )

    branches = {
        PURCHASE_KVO01_SLOT: _build_branch_preview(
            slot_key=PURCHASE_KVO01_SLOT,
            kvo="01",
            rows=branch_rows[PURCHASE_KVO01_SLOT],
        ),
        PURCHASE_KVO17_SLOT: _build_branch_preview(
            slot_key=PURCHASE_KVO17_SLOT,
            kvo="17",
            rows=branch_rows[PURCHASE_KVO17_SLOT],
        ),
    }
    classifier_revision = (
        classifications[0].classifier_revision
        if classifications
        else KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION
    )
    return Kvo17PurchaseSplitPreview(
        classifier_revision=classifier_revision,
        source_document_identity={
            "number": batch.source_document_number,
            "date": batch.source_document_date.isoformat(),
        },
        source_supplier_provenance={
            "ref": batch.source_supplier_ref,
            "name": batch.source_supplier_name,
        },
        branches=branches,
        diagnostics=_build_duplicate_diagnostics(rows=batch.rows),
        content_hash=batch.content_hash,
    )


def _preview_row(
    *,
    row: Kvo17PurchaseSplitIntakeRow,
    classification: Kvo17PurchaseSplitClassification,
) -> dict[str, Any]:
    return {
        "line_no": row.line_no,
        "row_id": row.row_id,
        "row_fingerprint": row.row_fingerprint,
        "amount": str(row.amount),
        "vat_amount": str(row.vat_amount),
        "currency": row.currency,
        "source_provenance": row.provenance(),
        "classification": classification.preview(),
    }


def _build_branch_preview(
    *,
    slot_key: str,
    kvo: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    total_amount = sum((Decimal(row["amount"]) for row in rows), Decimal("0.00"))
    total_vat_amount = sum((Decimal(row["vat_amount"]) for row in rows), Decimal("0.00"))
    return {
        "slot_key": slot_key,
        "kvo": kvo,
        "row_count": len(rows),
        "total_amount": str(total_amount.quantize(Decimal("0.01"))),
        "total_vat_amount": str(total_vat_amount.quantize(Decimal("0.01"))),
        "rows": list(rows),
    }


def _build_duplicate_diagnostics(
    *,
    rows: list[Kvo17PurchaseSplitIntakeRow],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    diagnostics.extend(
        _duplicate_diagnostics_for_key(
            rows=rows,
            key_name="row_id",
            code=KVO17_DUPLICATE_ROW_ID,
            values=[row.row_id for row in rows],
        )
    )
    diagnostics.extend(
        _duplicate_diagnostics_for_key(
            rows=rows,
            key_name="row_fingerprint",
            code=KVO17_DUPLICATE_ROW_FINGERPRINT,
            values=[row.row_fingerprint for row in rows],
        )
    )
    return diagnostics


def _duplicate_diagnostics_for_key(
    *,
    rows: list[Kvo17PurchaseSplitIntakeRow],
    key_name: str,
    code: str,
    values: list[str],
) -> list[dict[str, Any]]:
    line_numbers_by_value: dict[str, list[int]] = {}
    for row, value in zip(rows, values, strict=True):
        line_numbers_by_value.setdefault(value, []).append(row.line_no)

    diagnostics: list[dict[str, Any]] = []
    for value, line_numbers in sorted(line_numbers_by_value.items()):
        if len(line_numbers) < 2:
            continue
        diagnostics.append(
            {
                "code": code,
                "severity": "error",
                "field": key_name,
                "value": value,
                "line_numbers": line_numbers,
                "detail": f"Duplicate KVO17 purchase split source {key_name}.",
            }
        )
    return diagnostics


__all__ = [
    "KVO17_DUPLICATE_ROW_FINGERPRINT",
    "KVO17_DUPLICATE_ROW_ID",
    "Kvo17PurchaseSplitPreview",
    "build_kvo17_purchase_split_preview",
]
