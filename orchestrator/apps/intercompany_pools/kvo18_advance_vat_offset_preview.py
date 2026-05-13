from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .kvo18_advance_vat_offset_intake import (
    ADVANCE_INVOICE_KVO01_SLOT,
    ADVANCE_OFFSET_KVO18_SLOT,
    CASH_RECEIPT_ORDER_SLOT,
    DECLARATION_EVIDENCE_SLOT,
    KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION,
    Kvo18AdvanceVatOffsetBatchNormalizationResult,
    Kvo18AdvanceVatOffsetIntakeRow,
    build_kvo18_advance_vat_offset_policy_config,
)


KVO18_DUPLICATE_ROW_ID = "KVO18_DUPLICATE_ROW_ID"
KVO18_DUPLICATE_ROW_FINGERPRINT = "KVO18_DUPLICATE_ROW_FINGERPRINT"


@dataclass(frozen=True)
class Kvo18AdvanceVatOffsetPreview:
    policy_revision: str
    total_amount: str
    total_vat_amount: str
    currency: str
    row_count: int
    rows: list[dict[str, Any]]
    stages: dict[str, dict[str, Any]]
    technical_realization_policy: dict[str, Any]
    evidence_requirements: dict[str, Any]
    diagnostics: list[dict[str, Any]]
    content_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "policy_revision": self.policy_revision,
            "total_amount": self.total_amount,
            "total_vat_amount": self.total_vat_amount,
            "currency": self.currency,
            "row_count": self.row_count,
            "rows": list(self.rows),
            "stages": dict(self.stages),
            "technical_realization_policy": dict(self.technical_realization_policy),
            "evidence_requirements": dict(self.evidence_requirements),
            "diagnostics": list(self.diagnostics),
            "content_hash": self.content_hash,
        }


def build_kvo18_advance_vat_offset_preview(
    *,
    batch: Kvo18AdvanceVatOffsetBatchNormalizationResult,
) -> Kvo18AdvanceVatOffsetPreview:
    policy = build_kvo18_advance_vat_offset_policy_config()
    total_amount = sum((row.amount for row in batch.rows), Decimal("0.00"))
    total_vat_amount = sum((row.vat_amount for row in batch.rows), Decimal("0.00"))
    currency = batch.rows[0].currency if batch.rows else "RUB"
    return Kvo18AdvanceVatOffsetPreview(
        policy_revision=KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION,
        total_amount=str(total_amount.quantize(Decimal("0.01"))),
        total_vat_amount=str(total_vat_amount.quantize(Decimal("0.01"))),
        currency=currency,
        row_count=len(batch.rows),
        rows=[_preview_row(row=row) for row in batch.rows],
        stages=_build_stage_preview(),
        technical_realization_policy=dict(policy["technical_realization"]),
        evidence_requirements=dict(policy["declaration_evidence"]),
        diagnostics=_build_duplicate_diagnostics(rows=batch.rows),
        content_hash=batch.content_hash,
    )


def _preview_row(*, row: Kvo18AdvanceVatOffsetIntakeRow) -> dict[str, Any]:
    return {
        "line_no": row.line_no,
        "row_id": row.row_id,
        "row_fingerprint": row.row_fingerprint,
        "counterparty": {
            "ref": row.counterparty_ref,
            "name": row.counterparty_name,
        },
        "contract": {
            "ref": row.contract_ref,
            "name": row.contract_name,
        },
        "operation_date": row.operation_date.isoformat(),
        "amount": str(row.amount),
        "vat_rate": row.vat_rate,
        "vat_amount": str(row.vat_amount),
        "currency": row.currency,
        "source_reference": row.source_reference,
        "source_document_number": row.source_document_number,
        "lineage": {
            "cash_receipt_order": {"required": True, "state": "pending"},
            "advance_invoice_kvo01": {"required": True, "state": "blocked"},
            "advance_offset_kvo18": {"required": True, "state": "blocked"},
            "declaration_evidence": {"required": True, "state": "blocked"},
        },
    }


def _build_stage_preview() -> dict[str, dict[str, Any]]:
    return {
        CASH_RECEIPT_ORDER_SLOT: {
            "slot_key": CASH_RECEIPT_ORDER_SLOT,
            "label": "Создать ПКО",
            "state": "ready",
            "prerequisites": [],
            "produces": ["cash_receipt_order_ref"],
        },
        ADVANCE_INVOICE_KVO01_SLOT: {
            "slot_key": ADVANCE_INVOICE_KVO01_SLOT,
            "label": "Создать СФ на аванс",
            "state": "blocked",
            "prerequisites": [CASH_RECEIPT_ORDER_SLOT],
            "produces": ["advance_invoice_ref", "sales_book_kvo01_evidence"],
        },
        ADVANCE_OFFSET_KVO18_SLOT: {
            "slot_key": ADVANCE_OFFSET_KVO18_SLOT,
            "label": "Сформировать зачет (КВО 18)",
            "state": "blocked",
            "prerequisites": [ADVANCE_INVOICE_KVO01_SLOT, "operator_preview_confirmation"],
            "produces": [
                "technical_realization_ref",
                "technical_realization_final_state",
                "purchase_book_kvo18_evidence",
            ],
        },
        DECLARATION_EVIDENCE_SLOT: {
            "slot_key": DECLARATION_EVIDENCE_SLOT,
            "label": "Проверить декларацию",
            "state": "blocked",
            "prerequisites": [ADVANCE_OFFSET_KVO18_SLOT],
            "produces": ["declaration_projection_kvo01_kvo18"],
        },
    }


def _build_duplicate_diagnostics(
    *,
    rows: list[Kvo18AdvanceVatOffsetIntakeRow],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    diagnostics.extend(
        _duplicate_diagnostics_for_key(
            rows=rows,
            key_name="row_id",
            code=KVO18_DUPLICATE_ROW_ID,
            values=[row.row_id for row in rows],
        )
    )
    diagnostics.extend(
        _duplicate_diagnostics_for_key(
            rows=rows,
            key_name="row_fingerprint",
            code=KVO18_DUPLICATE_ROW_FINGERPRINT,
            values=[row.row_fingerprint for row in rows],
        )
    )
    return diagnostics


def _duplicate_diagnostics_for_key(
    *,
    rows: list[Kvo18AdvanceVatOffsetIntakeRow],
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
                "detail": f"Duplicate KVO18 advance VAT offset source {key_name}.",
            }
        )
    return diagnostics


__all__ = [
    "KVO18_DUPLICATE_ROW_FINGERPRINT",
    "KVO18_DUPLICATE_ROW_ID",
    "Kvo18AdvanceVatOffsetPreview",
    "build_kvo18_advance_vat_offset_preview",
]
