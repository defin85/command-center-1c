from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Mapping

from django.core.exceptions import ValidationError

from .batch_intake_parsers import parse_pool_schema_template_amount


KVO18_ADVANCE_VAT_OFFSET_INTAKE_SCHEMA_VERSION = "kvo18_advance_vat_offset_intake.v1"
KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION = "kvo18_advance_vat_offset_policy.v1"
KVO18_ADVANCE_VAT_OFFSET_DEFAULT_CURRENCY = "RUB"

CASH_RECEIPT_ORDER_SLOT = "cash_receipt_order"
ADVANCE_INVOICE_KVO01_SLOT = "advance_invoice_kvo01"
ADVANCE_OFFSET_KVO18_SLOT = "advance_offset_kvo18"
DECLARATION_EVIDENCE_SLOT = "declaration_evidence"
KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS = (
    CASH_RECEIPT_ORDER_SLOT,
    ADVANCE_INVOICE_KVO01_SLOT,
    ADVANCE_OFFSET_KVO18_SLOT,
    DECLARATION_EVIDENCE_SLOT,
)

KVO18_ADVANCE_VAT_OFFSET_REQUIRED_INTAKE_FIELDS = (
    "counterparty_ref",
    "counterparty_name",
    "contract_ref",
    "contract_name",
    "operation_date",
    "amount",
    "vat_rate",
    "vat_amount",
    "currency",
    "row_id",
)
KVO18_ADVANCE_VAT_OFFSET_OPTIONAL_INTAKE_FIELDS = (
    "source_reference",
    "source_document_number",
)


@dataclass(frozen=True)
class Kvo18AdvanceVatOffsetIntakeRow:
    line_no: int
    counterparty_ref: str
    counterparty_name: str
    contract_ref: str
    contract_name: str
    operation_date: date
    amount: Decimal
    vat_rate: str
    vat_amount: Decimal
    currency: str
    row_id: str
    row_fingerprint: str
    source_reference: str = ""
    source_document_number: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "line_no": self.line_no,
            "counterparty_ref": self.counterparty_ref,
            "counterparty_name": self.counterparty_name,
            "contract_ref": self.contract_ref,
            "contract_name": self.contract_name,
            "operation_date": self.operation_date.isoformat(),
            "amount": str(self.amount),
            "vat_rate": self.vat_rate,
            "vat_amount": str(self.vat_amount),
            "currency": self.currency,
            "row_id": self.row_id,
            "row_fingerprint": self.row_fingerprint,
            "source_reference": self.source_reference,
            "source_document_number": self.source_document_number,
        }

    def provenance(self) -> dict[str, Any]:
        return {
            "counterparty_ref": self.counterparty_ref,
            "counterparty_name": self.counterparty_name,
            "contract_ref": self.contract_ref,
            "contract_name": self.contract_name,
            "operation_date": self.operation_date.isoformat(),
            "row_id": self.row_id,
            "row_fingerprint": self.row_fingerprint,
            "source_reference": self.source_reference,
            "source_document_number": self.source_document_number,
        }


@dataclass(frozen=True)
class Kvo18AdvanceVatOffsetBatchNormalizationResult:
    rows: list[Kvo18AdvanceVatOffsetIntakeRow]
    content_hash: str
    source_reference: str = ""
    raw_payload_ref: str = ""
    source_metadata: dict[str, Any] | None = None

    def provenance(self) -> dict[str, Any]:
        return {
            "source_reference": self.source_reference,
            "raw_payload_ref": self.raw_payload_ref,
            "content_hash": self.content_hash,
            "source_metadata": dict(self.source_metadata or {}),
            "rows": [row.provenance() for row in self.rows],
        }

    def normalization_summary(self) -> dict[str, Any]:
        total_amount = sum((row.amount for row in self.rows), Decimal("0.00"))
        total_vat_amount = sum((row.vat_amount for row in self.rows), Decimal("0.00"))
        currencies = sorted({row.currency for row in self.rows})
        return {
            "processed_rows": len(self.rows),
            "normalized_rows": len(self.rows),
            "total_amount": total_amount.quantize(Decimal("0.01")),
            "total_vat_amount": total_vat_amount.quantize(Decimal("0.01")),
            "currencies": currencies,
            "row_fingerprints": [row.row_fingerprint for row in self.rows],
        }


def build_kvo18_advance_vat_offset_intake_schema() -> dict[str, Any]:
    columns = {
        field_name: field_name
        for field_name in (
            *KVO18_ADVANCE_VAT_OFFSET_REQUIRED_INTAKE_FIELDS,
            *KVO18_ADVANCE_VAT_OFFSET_OPTIONAL_INTAKE_FIELDS,
        )
    }
    return {
        "version": KVO18_ADVANCE_VAT_OFFSET_INTAKE_SCHEMA_VERSION,
        "rows_path": "rows",
        "columns": columns,
        "required_fields": list(KVO18_ADVANCE_VAT_OFFSET_REQUIRED_INTAKE_FIELDS),
        "optional_fields": list(KVO18_ADVANCE_VAT_OFFSET_OPTIONAL_INTAKE_FIELDS),
        "validation": {
            "fail_closed": True,
            "currency": {
                "default": KVO18_ADVANCE_VAT_OFFSET_DEFAULT_CURRENCY,
                "allowed": [KVO18_ADVANCE_VAT_OFFSET_DEFAULT_CURRENCY],
            },
            "row_identity": {
                "field": "row_id",
                "fingerprint_fields": [
                    "counterparty_ref",
                    "contract_ref",
                    "operation_date",
                    "row_id",
                    "amount",
                    "vat_rate",
                    "vat_amount",
                    "currency",
                ],
            },
        },
        "staged_states": [
            "ready_for_cash_receipt_order",
            "cash_receipt_order_created",
            "advance_invoice_kvo01_created",
            "offset_kvo18_formed",
            "declaration_evidence_verified",
        ],
        "provenance": {
            "preserve_fields": [
                "counterparty_ref",
                "counterparty_name",
                "contract_ref",
                "contract_name",
                "operation_date",
                "row_id",
                "row_fingerprint",
                "source_reference",
                "source_document_number",
            ],
        },
    }


def build_kvo18_advance_vat_offset_policy_config() -> dict[str, Any]:
    return {
        "revision": KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION,
        "amount_rule": {
            "type": "sum_normalized_advance_rows",
            "coverage": "per_row_and_total",
            "currency": KVO18_ADVANCE_VAT_OFFSET_DEFAULT_CURRENCY,
        },
        "technical_realization": {
            "required": True,
            "amount_rule": "total_advance_amount",
            "counterparty_contract_source": "normalized_advance_row",
            "document_state_after_offset": "unposted_after_purchase_book_evidence",
            "confirmation_gates": [
                "operator_preview_confirmed",
                "cash_receipt_order_evidence",
                "advance_invoice_kvo01_evidence",
            ],
            "audit_evidence_required": [
                "technical_realization_ref",
                "technical_realization_final_state",
                "purchase_book_kvo18_evidence",
            ],
        },
        "declaration_evidence": {
            "sales_book_kvo01_required": True,
            "purchase_book_kvo18_required": True,
            "document_creation_alone_is_success": False,
        },
    }


def normalize_kvo18_advance_vat_offset_intake_rows(
    *,
    rows: Any,
) -> list[Kvo18AdvanceVatOffsetIntakeRow]:
    if not isinstance(rows, list) or not rows:
        raise ValidationError("KVO18 advance VAT offset intake requires a non-empty rows list.")

    normalized_rows: list[Kvo18AdvanceVatOffsetIntakeRow] = []
    for line_no, raw_row in enumerate(rows, start=1):
        if not isinstance(raw_row, Mapping):
            raise ValidationError(f"Row {line_no}: intake row must be an object.")
        normalized_rows.append(
            normalize_kvo18_advance_vat_offset_intake_row(
                row=raw_row,
                line_no=line_no,
            )
        )
    return normalized_rows


def normalize_kvo18_advance_vat_offset_batch(
    *,
    json_payload: Any,
    source_reference: str = "",
    raw_payload_ref: str = "",
    source_metadata: Mapping[str, Any] | None = None,
) -> Kvo18AdvanceVatOffsetBatchNormalizationResult:
    rows = normalize_kvo18_advance_vat_offset_intake_rows(
        rows=_extract_kvo18_advance_vat_offset_rows(json_payload),
    )
    canonical_rows = [row.as_dict() for row in rows]
    content_hash = hashlib.sha256(
        json.dumps(
            canonical_rows,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return Kvo18AdvanceVatOffsetBatchNormalizationResult(
        rows=rows,
        content_hash=content_hash,
        source_reference=str(source_reference or "").strip(),
        raw_payload_ref=str(raw_payload_ref or "").strip(),
        source_metadata=dict(source_metadata or {}),
    )


def normalize_kvo18_advance_vat_offset_intake_row(
    *,
    row: Mapping[str, Any],
    line_no: int,
) -> Kvo18AdvanceVatOffsetIntakeRow:
    counterparty_ref = _required_text(row, key="counterparty_ref", line_no=line_no)
    counterparty_name = _required_text(row, key="counterparty_name", line_no=line_no)
    contract_ref = _required_text(row, key="contract_ref", line_no=line_no)
    contract_name = _required_text(row, key="contract_name", line_no=line_no)
    operation_date = _required_date(row, key="operation_date", line_no=line_no)
    amount = _required_amount(row, key="amount", line_no=line_no)
    vat_rate = _required_text(row, key="vat_rate", line_no=line_no)
    vat_amount = _required_amount(row, key="vat_amount", line_no=line_no)
    currency = _required_text(row, key="currency", line_no=line_no).upper()
    if currency != KVO18_ADVANCE_VAT_OFFSET_DEFAULT_CURRENCY:
        raise ValidationError(
            f"Row {line_no}: unsupported currency '{currency}' for KVO18 advance VAT offset intake."
        )
    row_id = _required_text(row, key="row_id", line_no=line_no)
    source_reference = str(row.get("source_reference") or "").strip()
    source_document_number = str(row.get("source_document_number") or "").strip()
    fingerprint_payload = {
        "counterparty_ref": counterparty_ref,
        "contract_ref": contract_ref,
        "operation_date": operation_date.isoformat(),
        "row_id": row_id,
        "amount": str(amount),
        "vat_rate": vat_rate,
        "vat_amount": str(vat_amount),
        "currency": currency,
    }
    row_fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return Kvo18AdvanceVatOffsetIntakeRow(
        line_no=line_no,
        counterparty_ref=counterparty_ref,
        counterparty_name=counterparty_name,
        contract_ref=contract_ref,
        contract_name=contract_name,
        operation_date=operation_date,
        amount=amount,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        currency=currency,
        row_id=row_id,
        row_fingerprint=row_fingerprint,
        source_reference=source_reference,
        source_document_number=source_document_number,
    )


def _extract_kvo18_advance_vat_offset_rows(json_payload: Any) -> list[dict[str, Any]]:
    value = json_payload
    if isinstance(value, (str, bytes)):
        value = json.loads(value)
    rows = value.get("rows") if isinstance(value, Mapping) else value
    if not isinstance(rows, list):
        raise ValidationError("KVO18 advance VAT offset payload must be a list or an object with rows list.")
    parsed_rows: list[dict[str, Any]] = []
    for line_no, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            raise ValidationError(f"Row {line_no}: intake row must be an object.")
        parsed_rows.append(dict(row))
    return parsed_rows


def _required_text(row: Mapping[str, Any], *, key: str, line_no: int) -> str:
    value = str(row.get(key) or "").strip()
    if not value:
        raise ValidationError(f"Row {line_no}: missing required {key} value.")
    return value


def _required_date(row: Mapping[str, Any], *, key: str, line_no: int) -> date:
    raw = row.get(key)
    if isinstance(raw, date):
        return raw
    value = str(raw or "").strip()
    if not value:
        raise ValidationError(f"Row {line_no}: missing required {key} value.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"Row {line_no}: invalid {key} '{raw}'.") from exc


def _required_amount(row: Mapping[str, Any], *, key: str, line_no: int) -> Decimal:
    try:
        return parse_pool_schema_template_amount(
            row.get(key),
            quantizer=Decimal("0.01"),
            field_name=key,
        )
    except ValidationError as exc:
        detail = "; ".join(str(message) for message in exc.messages)
        raise ValidationError(f"Row {line_no}: {detail}") from exc


__all__ = [
    "ADVANCE_INVOICE_KVO01_SLOT",
    "ADVANCE_OFFSET_KVO18_SLOT",
    "CASH_RECEIPT_ORDER_SLOT",
    "DECLARATION_EVIDENCE_SLOT",
    "KVO18_ADVANCE_VAT_OFFSET_DEFAULT_CURRENCY",
    "KVO18_ADVANCE_VAT_OFFSET_INTAKE_SCHEMA_VERSION",
    "KVO18_ADVANCE_VAT_OFFSET_OPTIONAL_INTAKE_FIELDS",
    "KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION",
    "KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS",
    "KVO18_ADVANCE_VAT_OFFSET_REQUIRED_INTAKE_FIELDS",
    "Kvo18AdvanceVatOffsetBatchNormalizationResult",
    "Kvo18AdvanceVatOffsetIntakeRow",
    "build_kvo18_advance_vat_offset_intake_schema",
    "build_kvo18_advance_vat_offset_policy_config",
    "normalize_kvo18_advance_vat_offset_batch",
    "normalize_kvo18_advance_vat_offset_intake_row",
    "normalize_kvo18_advance_vat_offset_intake_rows",
]
