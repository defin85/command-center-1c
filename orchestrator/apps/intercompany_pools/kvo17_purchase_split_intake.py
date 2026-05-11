from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Mapping

from django.core.exceptions import ValidationError

from .batch_intake_parsers import parse_pool_schema_template_amount


KVO17_PURCHASE_SPLIT_INTAKE_SCHEMA_VERSION = "kvo17_purchase_split_intake.v1"
KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION = "kvo17_purchase_split_classifier.v1"
KVO17_PURCHASE_SPLIT_DEFAULT_CURRENCY = "RUB"
KVO17_PURCHASE_SPLIT_ALLOWED_KVO_OVERRIDES = ("01", "17")
PURCHASE_KVO01_SLOT = "purchase_kvo01"
PURCHASE_KVO17_SLOT = "purchase_kvo17"
KVO17_PURCHASE_SPLIT_REQUIRED_INTAKE_FIELDS = (
    "source_document_number",
    "source_document_date",
    "source_supplier_ref",
    "source_supplier_name",
    "amount",
    "vat_amount",
    "vat_rate",
    "currency",
    "row_id",
)
KVO17_PURCHASE_SPLIT_OPTIONAL_INTAKE_FIELDS = (
    "source_supplier_inn",
    "source_kvo_override",
)


@dataclass(frozen=True)
class Kvo17PurchaseSplitIntakeRow:
    line_no: int
    source_document_number: str
    source_document_date: date
    source_supplier_ref: str
    source_supplier_name: str
    amount: Decimal
    vat_amount: Decimal
    vat_rate: str
    currency: str
    row_id: str
    row_fingerprint: str
    source_supplier_inn: str = ""
    source_kvo_override: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "line_no": self.line_no,
            "source_document_number": self.source_document_number,
            "source_document_date": self.source_document_date.isoformat(),
            "source_supplier_ref": self.source_supplier_ref,
            "source_supplier_name": self.source_supplier_name,
            "source_supplier_inn": self.source_supplier_inn,
            "amount": str(self.amount),
            "vat_amount": str(self.vat_amount),
            "vat_rate": self.vat_rate,
            "currency": self.currency,
            "row_id": self.row_id,
            "row_fingerprint": self.row_fingerprint,
            "source_kvo_override": self.source_kvo_override,
        }

    def provenance(self) -> dict[str, Any]:
        return {
            "source_document_number": self.source_document_number,
            "source_document_date": self.source_document_date.isoformat(),
            "source_supplier_ref": self.source_supplier_ref,
            "source_supplier_name": self.source_supplier_name,
            "source_supplier_inn": self.source_supplier_inn,
            "row_id": self.row_id,
            "row_fingerprint": self.row_fingerprint,
        }


@dataclass(frozen=True)
class Kvo17PurchaseSplitBatchNormalizationResult:
    source_document_number: str
    source_document_date: date
    source_supplier_ref: str
    source_supplier_name: str
    rows: list[Kvo17PurchaseSplitIntakeRow]
    content_hash: str
    source_reference: str = ""
    raw_payload_ref: str = ""
    source_metadata: dict[str, Any] | None = None

    def provenance(self) -> dict[str, Any]:
        return {
            "source_document_number": self.source_document_number,
            "source_document_date": self.source_document_date.isoformat(),
            "source_supplier_ref": self.source_supplier_ref,
            "source_supplier_name": self.source_supplier_name,
            "source_reference": self.source_reference,
            "raw_payload_ref": self.raw_payload_ref,
            "content_hash": self.content_hash,
            "source_metadata": dict(self.source_metadata or {}),
            "rows": [row.provenance() for row in self.rows],
        }

    def normalization_summary(self) -> dict[str, Any]:
        total_amount = sum((row.amount for row in self.rows), Decimal("0.00"))
        total_vat_amount = sum((row.vat_amount for row in self.rows), Decimal("0.00"))
        return {
            "processed_rows": len(self.rows),
            "normalized_rows": len(self.rows),
            "source_document_identity": {
                "number": self.source_document_number,
                "date": self.source_document_date.isoformat(),
            },
            "source_supplier_identity": {
                "ref": self.source_supplier_ref,
                "name": self.source_supplier_name,
            },
            "total_amount": total_amount.quantize(Decimal("0.01")),
            "total_vat_amount": total_vat_amount.quantize(Decimal("0.01")),
            "row_fingerprints": [row.row_fingerprint for row in self.rows],
        }


@dataclass(frozen=True)
class Kvo17PurchaseSplitClassification:
    branch: str
    kvo: str
    rule_id: str
    classifier_revision: str
    amount: Decimal
    currency: str
    threshold_amount: Decimal
    source_kvo_override: str | None = None

    def preview(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "kvo": self.kvo,
            "rule_id": self.rule_id,
            "classifier_revision": self.classifier_revision,
            "amount": str(self.amount),
            "currency": self.currency,
            "threshold_amount": str(self.threshold_amount),
            "source_kvo_override": self.source_kvo_override,
        }


def build_kvo17_purchase_split_intake_schema() -> dict[str, Any]:
    columns = {
        field_name: field_name
        for field_name in (
            *KVO17_PURCHASE_SPLIT_REQUIRED_INTAKE_FIELDS,
            *KVO17_PURCHASE_SPLIT_OPTIONAL_INTAKE_FIELDS,
        )
    }
    return {
        "version": KVO17_PURCHASE_SPLIT_INTAKE_SCHEMA_VERSION,
        "rows_path": "rows",
        "columns": columns,
        "required_fields": list(KVO17_PURCHASE_SPLIT_REQUIRED_INTAKE_FIELDS),
        "optional_fields": list(KVO17_PURCHASE_SPLIT_OPTIONAL_INTAKE_FIELDS),
        "validation": {
            "fail_closed": True,
            "currency": {
                "default": KVO17_PURCHASE_SPLIT_DEFAULT_CURRENCY,
                "allowed": [KVO17_PURCHASE_SPLIT_DEFAULT_CURRENCY],
            },
            "source_kvo_override": {
                "allowed": list(KVO17_PURCHASE_SPLIT_ALLOWED_KVO_OVERRIDES),
                "empty_is_none": True,
            },
            "row_identity": {
                "field": "row_id",
                "fingerprint_fields": [
                    "source_document_number",
                    "source_document_date",
                    "source_supplier_ref",
                    "row_id",
                    "amount",
                    "vat_amount",
                    "vat_rate",
                    "currency",
                ],
            },
        },
        "provenance": {
            "preserve_fields": [
                "source_document_number",
                "source_document_date",
                "source_supplier_ref",
                "source_supplier_name",
                "source_supplier_inn",
                "row_id",
                "row_fingerprint",
            ],
        },
    }


def build_kvo17_purchase_split_classifier_config() -> dict[str, Any]:
    return {
        "revision": KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION,
        "currency": KVO17_PURCHASE_SPLIT_DEFAULT_CURRENCY,
        "threshold_amount": "100.00",
        "branches": {
            "01": PURCHASE_KVO01_SLOT,
            "17": PURCHASE_KVO17_SLOT,
        },
        "override_policy": {
            "enabled": True,
            "allowed_kvo": list(KVO17_PURCHASE_SPLIT_ALLOWED_KVO_OVERRIDES),
            "tenant_override_surface": {
                "metadata_key": "classifier_override",
                "requires_revision": True,
                "audit_required": True,
            },
        },
        "rules": [
            {
                "rule_id": "source_override_kvo17",
                "priority": 0,
                "branch": PURCHASE_KVO17_SLOT,
                "kvo": "17",
                "when": {"source_kvo_override": "17"},
            },
            {
                "rule_id": "source_override_kvo01",
                "priority": 1,
                "branch": PURCHASE_KVO01_SLOT,
                "kvo": "01",
                "when": {"source_kvo_override": "01"},
            },
            {
                "rule_id": "amount_lte_100_rub",
                "priority": 10,
                "branch": PURCHASE_KVO17_SLOT,
                "kvo": "17",
                "when": {"currency": KVO17_PURCHASE_SPLIT_DEFAULT_CURRENCY, "amount_lte": "100.00"},
            },
            {
                "rule_id": "amount_gt_100_rub",
                "priority": 11,
                "branch": PURCHASE_KVO01_SLOT,
                "kvo": "01",
                "when": {"currency": KVO17_PURCHASE_SPLIT_DEFAULT_CURRENCY, "amount_gt": "100.00"},
            },
        ],
    }


def validate_kvo17_purchase_split_classifier_config(*, config: Mapping[str, Any]) -> dict[str, Any]:
    revision = str(config.get("revision") or "").strip()
    if not revision:
        raise ValidationError("KVO17 split classifier config requires revision.")
    currency = str(config.get("currency") or "").strip().upper()
    if currency != KVO17_PURCHASE_SPLIT_DEFAULT_CURRENCY:
        raise ValidationError(
            f"KVO17 split classifier config supports only {KVO17_PURCHASE_SPLIT_DEFAULT_CURRENCY} currency."
        )
    threshold_amount = parse_pool_schema_template_amount(
        config.get("threshold_amount"),
        quantizer=Decimal("0.01"),
        field_name="threshold_amount",
    )
    if threshold_amount <= Decimal("0.00"):
        raise ValidationError("KVO17 split classifier threshold_amount must be positive.")

    branches = dict(config.get("branches") or {})
    if branches.get("01") != PURCHASE_KVO01_SLOT or branches.get("17") != PURCHASE_KVO17_SLOT:
        raise ValidationError("KVO17 split classifier branches must map KVO 01/17 to purchase slots.")

    override_policy = dict(config.get("override_policy") or {})
    allowed_overrides = [
        str(item).zfill(2)
        for item in list(override_policy.get("allowed_kvo") or [])
        if str(item).strip()
    ]
    if tuple(allowed_overrides) != KVO17_PURCHASE_SPLIT_ALLOWED_KVO_OVERRIDES:
        raise ValidationError("KVO17 split classifier override policy must allow only KVO 01 and 17.")
    if not bool(override_policy.get("enabled")):
        raise ValidationError("KVO17 split classifier override policy must be explicit and enabled.")

    rules = list(config.get("rules") or [])
    rule_ids = {str(rule.get("rule_id") or "").strip() for rule in rules if isinstance(rule, Mapping)}
    required_rule_ids = {
        "source_override_kvo17",
        "source_override_kvo01",
        "amount_lte_100_rub",
        "amount_gt_100_rub",
    }
    if rule_ids != required_rule_ids:
        raise ValidationError("KVO17 split classifier config must define the exact default rule set.")

    return {
        "revision": revision,
        "currency": currency,
        "threshold_amount": threshold_amount,
        "branches": {
            "01": PURCHASE_KVO01_SLOT,
            "17": PURCHASE_KVO17_SLOT,
        },
        "override_policy": override_policy,
        "rules": rules,
    }


def classify_kvo17_purchase_split_row(
    *,
    row: Kvo17PurchaseSplitIntakeRow,
    config: Mapping[str, Any] | None = None,
) -> Kvo17PurchaseSplitClassification:
    normalized_config = validate_kvo17_purchase_split_classifier_config(
        config=config or build_kvo17_purchase_split_classifier_config()
    )
    threshold_amount = normalized_config["threshold_amount"]
    if row.currency != normalized_config["currency"]:
        raise ValidationError(
            f"Row {row.line_no}: unsupported currency '{row.currency}' for classifier "
            f"{normalized_config['revision']}."
        )
    if row.amount < Decimal("0.00"):
        raise ValidationError(f"Row {row.line_no}: negative amount is ambiguous for KVO17 split classifier.")

    if row.source_kvo_override:
        if row.source_kvo_override == "17":
            return Kvo17PurchaseSplitClassification(
                branch=PURCHASE_KVO17_SLOT,
                kvo="17",
                rule_id="source_override_kvo17",
                classifier_revision=normalized_config["revision"],
                amount=row.amount,
                currency=row.currency,
                threshold_amount=threshold_amount,
                source_kvo_override=row.source_kvo_override,
            )
        if row.source_kvo_override == "01":
            return Kvo17PurchaseSplitClassification(
                branch=PURCHASE_KVO01_SLOT,
                kvo="01",
                rule_id="source_override_kvo01",
                classifier_revision=normalized_config["revision"],
                amount=row.amount,
                currency=row.currency,
                threshold_amount=threshold_amount,
                source_kvo_override=row.source_kvo_override,
            )
        raise ValidationError(
            f"Row {row.line_no}: unsupported source_kvo_override '{row.source_kvo_override}'."
        )

    if row.amount <= threshold_amount:
        return Kvo17PurchaseSplitClassification(
            branch=PURCHASE_KVO17_SLOT,
            kvo="17",
            rule_id="amount_lte_100_rub",
            classifier_revision=normalized_config["revision"],
            amount=row.amount,
            currency=row.currency,
            threshold_amount=threshold_amount,
        )
    return Kvo17PurchaseSplitClassification(
        branch=PURCHASE_KVO01_SLOT,
        kvo="01",
        rule_id="amount_gt_100_rub",
        classifier_revision=normalized_config["revision"],
        amount=row.amount,
        currency=row.currency,
        threshold_amount=threshold_amount,
    )


def normalize_kvo17_purchase_split_intake_rows(
    *,
    rows: Any,
) -> list[Kvo17PurchaseSplitIntakeRow]:
    if not isinstance(rows, list) or not rows:
        raise ValidationError("KVO17 purchase split intake requires a non-empty rows list.")

    normalized_rows: list[Kvo17PurchaseSplitIntakeRow] = []
    for line_no, raw_row in enumerate(rows, start=1):
        if not isinstance(raw_row, Mapping):
            raise ValidationError(f"Row {line_no}: intake row must be an object.")
        normalized_rows.append(
            normalize_kvo17_purchase_split_intake_row(
                row=raw_row,
                line_no=line_no,
            )
        )
    return normalized_rows


def normalize_kvo17_purchase_split_batch(
    *,
    json_payload: Any,
    source_reference: str = "",
    raw_payload_ref: str = "",
    source_metadata: Mapping[str, Any] | None = None,
) -> Kvo17PurchaseSplitBatchNormalizationResult:
    rows = normalize_kvo17_purchase_split_intake_rows(
        rows=_extract_kvo17_purchase_split_rows(json_payload),
    )
    first = rows[0]
    for row in rows[1:]:
        if (
            row.source_document_number != first.source_document_number
            or row.source_document_date != first.source_document_date
        ):
            raise ValidationError(
                "KVO17 purchase split batch must contain exactly one source document identity."
            )
        if (
            row.source_supplier_ref != first.source_supplier_ref
            or row.source_supplier_name != first.source_supplier_name
        ):
            raise ValidationError(
                "KVO17 purchase split batch must contain exactly one source supplier identity."
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
    return Kvo17PurchaseSplitBatchNormalizationResult(
        source_document_number=first.source_document_number,
        source_document_date=first.source_document_date,
        source_supplier_ref=first.source_supplier_ref,
        source_supplier_name=first.source_supplier_name,
        rows=rows,
        content_hash=content_hash,
        source_reference=str(source_reference or "").strip(),
        raw_payload_ref=str(raw_payload_ref or "").strip(),
        source_metadata=dict(source_metadata or {}),
    )


def normalize_kvo17_purchase_split_intake_row(
    *,
    row: Mapping[str, Any],
    line_no: int,
) -> Kvo17PurchaseSplitIntakeRow:
    source_document_number = _required_text(
        row,
        key="source_document_number",
        line_no=line_no,
    )
    source_document_date = _required_date(
        row,
        key="source_document_date",
        line_no=line_no,
    )
    source_supplier_ref = _required_text(
        row,
        key="source_supplier_ref",
        line_no=line_no,
    )
    source_supplier_name = _required_text(
        row,
        key="source_supplier_name",
        line_no=line_no,
    )
    amount = _required_amount(row, key="amount", line_no=line_no)
    vat_amount = _required_amount(row, key="vat_amount", line_no=line_no)
    vat_rate = _required_text(row, key="vat_rate", line_no=line_no)
    currency = _required_text(row, key="currency", line_no=line_no).upper()
    if currency != KVO17_PURCHASE_SPLIT_DEFAULT_CURRENCY:
        raise ValidationError(
            f"Row {line_no}: unsupported currency '{currency}' for KVO17 purchase split intake."
        )
    row_id = _required_text(row, key="row_id", line_no=line_no)
    source_kvo_override = _optional_kvo_override(row.get("source_kvo_override"), line_no=line_no)
    source_supplier_inn = str(row.get("source_supplier_inn") or "").strip()
    fingerprint_payload = {
        "source_document_number": source_document_number,
        "source_document_date": source_document_date.isoformat(),
        "source_supplier_ref": source_supplier_ref,
        "row_id": row_id,
        "amount": str(amount),
        "vat_amount": str(vat_amount),
        "vat_rate": vat_rate,
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

    return Kvo17PurchaseSplitIntakeRow(
        line_no=line_no,
        source_document_number=source_document_number,
        source_document_date=source_document_date,
        source_supplier_ref=source_supplier_ref,
        source_supplier_name=source_supplier_name,
        source_supplier_inn=source_supplier_inn,
        amount=amount,
        vat_amount=vat_amount,
        vat_rate=vat_rate,
        currency=currency,
        row_id=row_id,
        row_fingerprint=row_fingerprint,
        source_kvo_override=source_kvo_override,
    )


def _extract_kvo17_purchase_split_rows(json_payload: Any) -> list[dict[str, Any]]:
    value = json_payload
    if isinstance(value, (str, bytes)):
        value = json.loads(value)
    rows = value.get("rows") if isinstance(value, Mapping) else value
    if not isinstance(rows, list):
        raise ValidationError("KVO17 purchase split payload must be a list or an object with rows list.")
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


def _optional_kvo_override(raw: Any, *, line_no: int) -> str | None:
    value = str(raw or "").strip()
    if not value:
        return None
    normalized = value.zfill(2)
    if normalized not in KVO17_PURCHASE_SPLIT_ALLOWED_KVO_OVERRIDES:
        allowed = ", ".join(KVO17_PURCHASE_SPLIT_ALLOWED_KVO_OVERRIDES)
        raise ValidationError(
            f"Row {line_no}: unsupported source_kvo_override '{raw}', expected one of: {allowed}."
        )
    return normalized


__all__ = [
    "KVO17_PURCHASE_SPLIT_ALLOWED_KVO_OVERRIDES",
    "KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION",
    "KVO17_PURCHASE_SPLIT_DEFAULT_CURRENCY",
    "KVO17_PURCHASE_SPLIT_INTAKE_SCHEMA_VERSION",
    "KVO17_PURCHASE_SPLIT_OPTIONAL_INTAKE_FIELDS",
    "KVO17_PURCHASE_SPLIT_REQUIRED_INTAKE_FIELDS",
    "Kvo17PurchaseSplitBatchNormalizationResult",
    "Kvo17PurchaseSplitClassification",
    "Kvo17PurchaseSplitIntakeRow",
    "build_kvo17_purchase_split_intake_schema",
    "build_kvo17_purchase_split_classifier_config",
    "classify_kvo17_purchase_split_row",
    "normalize_kvo17_purchase_split_batch",
    "normalize_kvo17_purchase_split_intake_row",
    "normalize_kvo17_purchase_split_intake_rows",
    "validate_kvo17_purchase_split_classifier_config",
]
