from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

from django.core.exceptions import ValidationError

from .batch_intake_parsers import parse_pool_schema_template_amount
from .kvo17_purchase_split_intake import (
    KVO17_PURCHASE_SPLIT_ALLOWED_KVO_OVERRIDES,
    KVO17_PURCHASE_SPLIT_DEFAULT_CURRENCY,
)


KVO17_GENERATED_PURCHASE_REQUEST_SCHEMA_VERSION = "kvo17_generated_purchase_request.v1"
KVO17_GENERATED_PURCHASE_MANIFEST_VERSION = "kvo17_generated_purchase_manifest.v1"
KVO17_GENERATED_PURCHASE_METADATA_KEY = "kvo17_generated_purchase"
KVO17_GENERATED_PURCHASE_SOURCE_TYPE = "kvo17_generated_purchase"
KVO17_GENERATED_PURCHASE_DEFAULT_VAT_RATE = "20%"
KVO17_GENERATED_PURCHASE_DEFAULT_INVOICE_PREFIX = "KVO17"
KVO17_GENERATED_PURCHASE_DEFAULT_RANGE_KEYS = ("small", "large")
KVO17_GENERATED_PURCHASE_POLICY_SLOT = "kvo17_generated_purchase_pair"
KVO17_GENERATED_PURCHASE_POLICY_SLOTS = (KVO17_GENERATED_PURCHASE_POLICY_SLOT,)


@dataclass(frozen=True)
class Kvo17GeneratedPurchaseCounterparty:
    ref: str
    name: str
    inn: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "ref": self.ref,
            "name": self.name,
            "inn": self.inn,
        }


@dataclass(frozen=True)
class Kvo17GeneratedPurchaseAmountRange:
    range_key: str
    min_amount: Decimal
    max_amount: Decimal
    kvo: str

    def as_dict(self) -> dict[str, str]:
        return {
            "range_key": self.range_key,
            "min_amount": str(self.min_amount),
            "max_amount": str(self.max_amount),
            "kvo": self.kvo,
        }


@dataclass(frozen=True)
class Kvo17GeneratedPurchaseRow:
    line_no: int
    counterparty_ref: str
    counterparty_name: str
    counterparty_inn: str
    range_key: str
    kvo: str
    amount: Decimal
    vat_rate: str
    vat_amount: Decimal
    currency: str
    source_document_number: str
    source_document_date: date
    row_id: str
    row_fingerprint: str
    idempotency_key: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "line_no": self.line_no,
            "counterparty_ref": self.counterparty_ref,
            "counterparty_name": self.counterparty_name,
            "counterparty_inn": self.counterparty_inn,
            "range_key": self.range_key,
            "kvo": self.kvo,
            "amount": str(self.amount),
            "vat_rate": self.vat_rate,
            "vat_amount": str(self.vat_amount),
            "currency": self.currency,
            "source_document_number": self.source_document_number,
            "source_document_date": self.source_document_date.isoformat(),
            "row_id": self.row_id,
            "row_fingerprint": self.row_fingerprint,
            "idempotency_key": self.idempotency_key,
        }

    def as_purchase_split_row(self) -> dict[str, Any]:
        return {
            "source_document_number": self.source_document_number,
            "source_document_date": self.source_document_date.isoformat(),
            "source_supplier_ref": self.counterparty_ref,
            "source_supplier_name": self.counterparty_name,
            "source_supplier_inn": self.counterparty_inn,
            "amount": str(self.amount),
            "vat_amount": str(self.vat_amount),
            "vat_rate": self.vat_rate,
            "currency": self.currency,
            "row_id": self.row_id,
            "source_kvo_override": self.kvo,
        }


@dataclass(frozen=True)
class Kvo17GeneratedPurchaseManifest:
    period_start: date
    period_end: date
    counterparties: list[Kvo17GeneratedPurchaseCounterparty]
    amount_ranges: list[Kvo17GeneratedPurchaseAmountRange]
    seed: str
    currency: str
    vat_rate: str
    invoice_number_prefix: str
    request_hash: str
    content_hash: str
    rows: list[Kvo17GeneratedPurchaseRow]

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_schema_version": KVO17_GENERATED_PURCHASE_REQUEST_SCHEMA_VERSION,
            "manifest_version": KVO17_GENERATED_PURCHASE_MANIFEST_VERSION,
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
            },
            "seed": self.seed,
            "currency": self.currency,
            "vat_rate": self.vat_rate,
            "invoice_number_prefix": self.invoice_number_prefix,
            "request_hash": self.request_hash,
            "content_hash": self.content_hash,
            "counterparties": [item.as_dict() for item in self.counterparties],
            "amount_ranges": [item.as_dict() for item in self.amount_ranges],
            "rows": [row.as_dict() for row in self.rows],
            "summary": _json_safe(self.normalization_summary()),
        }

    def normalization_summary(self) -> dict[str, Any]:
        total_amount = sum((row.amount for row in self.rows), Decimal("0.00"))
        total_vat_amount = sum((row.vat_amount for row in self.rows), Decimal("0.00"))
        return {
            "selected_counterparties": len(self.counterparties),
            "processed_rows": len(self.rows),
            "normalized_rows": len(self.rows),
            "total_amount": total_amount.quantize(Decimal("0.01")),
            "total_vat_amount": total_vat_amount.quantize(Decimal("0.01")),
            "total_amount_with_vat": total_amount.quantize(Decimal("0.01")),
            "currency": self.currency,
            "seed": self.seed,
            "request_hash": self.request_hash,
            "content_hash": self.content_hash,
            "row_fingerprints": [row.row_fingerprint for row in self.rows],
        }

    def rows_by_counterparty(self) -> dict[str, list[Kvo17GeneratedPurchaseRow]]:
        grouped: dict[str, list[Kvo17GeneratedPurchaseRow]] = {}
        for row in self.rows:
            grouped.setdefault(row.counterparty_ref, []).append(row)
        return grouped


def build_kvo17_generated_purchase_request_schema() -> dict[str, Any]:
    return {
        "version": KVO17_GENERATED_PURCHASE_REQUEST_SCHEMA_VERSION,
        "manifest_version": KVO17_GENERATED_PURCHASE_MANIFEST_VERSION,
        "source_type": KVO17_GENERATED_PURCHASE_SOURCE_TYPE,
        "required_fields": [
            "period_start",
            "period_end",
            "counterparties",
            "amount_ranges",
            "seed",
        ],
        "optional_fields": [
            "currency",
            "vat_rate",
            "invoice_number_prefix",
        ],
        "counterparty_fields": [
            "counterparty_ref",
            "counterparty_name",
            "counterparty_inn",
        ],
        "amount_range_fields": [
            "range_key",
            "min_amount",
            "max_amount",
            "kvo",
        ],
        "validation": {
            "fail_closed": True,
            "period": {
                "requires_start_and_end": True,
                "inclusive_bounds": True,
            },
            "counterparties": {
                "min_count": 1,
                "identity_field": "counterparty_ref",
                "stale_ref_policy": "reject",
            },
            "amount_ranges": {
                "count": 2,
                "positive_bounds": True,
                "default_range_keys": list(KVO17_GENERATED_PURCHASE_DEFAULT_RANGE_KEYS),
            },
            "kvo": {
                "supported": list(KVO17_PURCHASE_SPLIT_ALLOWED_KVO_OVERRIDES),
                "ranges_must_use_distinct_kvo": True,
                "document_policy_slot": KVO17_GENERATED_PURCHASE_POLICY_SLOT,
            },
            "randomization": {
                "deterministic_from_seed": True,
                "no_implicit_reroll_after_preview": True,
            },
            "invoice_identity": {
                "shared_per_counterparty_pair": True,
                "distinct_runtime_row_identity": True,
            },
        },
        "manifest_fields": [
            "request_hash",
            "content_hash",
            "seed",
            "rows",
            "row_fingerprint",
            "idempotency_key",
        ],
    }


def build_kvo17_generated_purchase_manifest(
    *,
    request: Mapping[str, Any],
    available_counterparty_refs: set[str] | None = None,
) -> Kvo17GeneratedPurchaseManifest:
    if not isinstance(request, Mapping):
        raise ValidationError("KVO17 generated purchase request must be an object.")

    period_start = _required_date(request, "period_start")
    period_end = _required_date(request, "period_end")
    if period_end < period_start:
        raise ValidationError("KVO17 generated purchase period_end must be greater than or equal to period_start.")

    seed = _required_text(request, "seed")
    currency = str(request.get("currency") or KVO17_PURCHASE_SPLIT_DEFAULT_CURRENCY).strip().upper()
    if currency != KVO17_PURCHASE_SPLIT_DEFAULT_CURRENCY:
        raise ValidationError("KVO17 generated purchase supports only RUB currency in the first release.")
    vat_rate = _normalize_vat_rate(request.get("vat_rate") or KVO17_GENERATED_PURCHASE_DEFAULT_VAT_RATE)
    invoice_number_prefix = str(
        request.get("invoice_number_prefix") or KVO17_GENERATED_PURCHASE_DEFAULT_INVOICE_PREFIX
    ).strip()
    if not invoice_number_prefix:
        raise ValidationError("KVO17 generated purchase invoice_number_prefix must not be blank.")

    counterparties = _normalize_counterparties(request.get("counterparties"))
    _validate_counterparty_refs(
        counterparties=counterparties,
        available_counterparty_refs=available_counterparty_refs,
    )
    amount_ranges = _normalize_amount_ranges(request.get("amount_ranges"))

    canonical_request = _canonical_request_payload(
        period_start=period_start,
        period_end=period_end,
        seed=seed,
        currency=currency,
        vat_rate=vat_rate,
        invoice_number_prefix=invoice_number_prefix,
        counterparties=counterparties,
        amount_ranges=amount_ranges,
    )
    request_hash = _stable_hash(canonical_request)
    rows = _generate_rows(
        period_start=period_start,
        period_end=period_end,
        seed=seed,
        request_hash=request_hash,
        currency=currency,
        vat_rate=vat_rate,
        invoice_number_prefix=invoice_number_prefix,
        counterparties=counterparties,
        amount_ranges=amount_ranges,
    )
    content_hash = _stable_hash(
        {
            "manifest_version": KVO17_GENERATED_PURCHASE_MANIFEST_VERSION,
            "request_hash": request_hash,
            "rows": [row.as_dict() for row in rows],
        }
    )
    return Kvo17GeneratedPurchaseManifest(
        period_start=period_start,
        period_end=period_end,
        counterparties=counterparties,
        amount_ranges=amount_ranges,
        seed=seed,
        currency=currency,
        vat_rate=vat_rate,
        invoice_number_prefix=invoice_number_prefix,
        request_hash=request_hash,
        content_hash=content_hash,
        rows=rows,
    )


def validate_kvo17_generated_purchase_manifest_reuse(
    *,
    request: Mapping[str, Any],
    accepted_manifest: Mapping[str, Any],
    available_counterparty_refs: set[str] | None = None,
) -> Kvo17GeneratedPurchaseManifest:
    manifest = build_kvo17_generated_purchase_manifest(
        request=request,
        available_counterparty_refs=available_counterparty_refs,
    )
    accepted_request_hash = str(accepted_manifest.get("request_hash") or "").strip()
    accepted_content_hash = str(accepted_manifest.get("content_hash") or "").strip()
    if accepted_request_hash != manifest.request_hash or accepted_content_hash != manifest.content_hash:
        raise ValidationError("KVO17 generated purchase manifest is not reproducible from the accepted request.")
    return manifest


def _generate_rows(
    *,
    period_start: date,
    period_end: date,
    seed: str,
    request_hash: str,
    currency: str,
    vat_rate: str,
    invoice_number_prefix: str,
    counterparties: list[Kvo17GeneratedPurchaseCounterparty],
    amount_ranges: list[Kvo17GeneratedPurchaseAmountRange],
) -> list[Kvo17GeneratedPurchaseRow]:
    rows: list[Kvo17GeneratedPurchaseRow] = []
    line_no = 1
    for counterparty_index, counterparty in enumerate(counterparties, start=1):
        invoice_date = _random_date(
            period_start=period_start,
            period_end=period_end,
            seed=seed,
            request_hash=request_hash,
            counterparty_ref=counterparty.ref,
        )
        invoice_number = _build_invoice_number(
            prefix=invoice_number_prefix,
            counterparty_index=counterparty_index,
            seed=seed,
            request_hash=request_hash,
            counterparty_ref=counterparty.ref,
        )
        for amount_range in amount_ranges:
            amount = _random_amount(
                amount_range=amount_range,
                seed=seed,
                request_hash=request_hash,
                counterparty_ref=counterparty.ref,
            )
            row_id = f"{counterparty.ref}:{amount_range.range_key}:{amount_range.kvo}"
            row_payload = {
                "line_no": line_no,
                "counterparty_ref": counterparty.ref,
                "range_key": amount_range.range_key,
                "kvo": amount_range.kvo,
                "amount": str(amount),
                "vat_rate": vat_rate,
                "vat_amount": str(_calculate_included_vat(amount=amount, vat_rate=vat_rate)),
                "currency": currency,
                "source_document_number": invoice_number,
                "source_document_date": invoice_date.isoformat(),
                "row_id": row_id,
                "seed": seed,
                "request_hash": request_hash,
            }
            row_fingerprint = _stable_hash(row_payload)
            rows.append(
                Kvo17GeneratedPurchaseRow(
                    line_no=line_no,
                    counterparty_ref=counterparty.ref,
                    counterparty_name=counterparty.name,
                    counterparty_inn=counterparty.inn,
                    range_key=amount_range.range_key,
                    kvo=amount_range.kvo,
                    amount=amount,
                    vat_rate=vat_rate,
                    vat_amount=_calculate_included_vat(amount=amount, vat_rate=vat_rate),
                    currency=currency,
                    source_document_number=invoice_number,
                    source_document_date=invoice_date,
                    row_id=row_id,
                    row_fingerprint=row_fingerprint,
                    idempotency_key=f"kvo17-generated-purchase:{row_fingerprint[:32]}",
                )
            )
            line_no += 1
    return rows


def _canonical_request_payload(
    *,
    period_start: date,
    period_end: date,
    seed: str,
    currency: str,
    vat_rate: str,
    invoice_number_prefix: str,
    counterparties: list[Kvo17GeneratedPurchaseCounterparty],
    amount_ranges: list[Kvo17GeneratedPurchaseAmountRange],
) -> dict[str, Any]:
    return {
        "request_schema_version": KVO17_GENERATED_PURCHASE_REQUEST_SCHEMA_VERSION,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "seed": seed,
        "currency": currency,
        "vat_rate": vat_rate,
        "invoice_number_prefix": invoice_number_prefix,
        "counterparties": [item.as_dict() for item in counterparties],
        "amount_ranges": [item.as_dict() for item in amount_ranges],
    }


def _normalize_counterparties(raw_value: Any) -> list[Kvo17GeneratedPurchaseCounterparty]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValidationError("KVO17 generated purchase requires at least one counterparty.")
    counterparties: list[Kvo17GeneratedPurchaseCounterparty] = []
    seen_refs: set[str] = set()
    for index, raw_counterparty in enumerate(raw_value, start=1):
        if not isinstance(raw_counterparty, Mapping):
            raise ValidationError(f"Counterparty {index}: expected object.")
        ref = _first_text(
            raw_counterparty,
            "counterparty_ref",
            "ref",
            "canonical_id",
            error_field=f"counterparties[{index}].counterparty_ref",
        )
        if ref in seen_refs:
            raise ValidationError(f"Counterparty {index}: duplicate counterparty_ref '{ref}'.")
        seen_refs.add(ref)
        name = _first_text(
            raw_counterparty,
            "counterparty_name",
            "name",
            error_field=f"counterparties[{index}].counterparty_name",
        )
        inn = str(
            raw_counterparty.get("counterparty_inn")
            or raw_counterparty.get("inn")
            or ""
        ).strip()
        counterparties.append(
            Kvo17GeneratedPurchaseCounterparty(
                ref=ref,
                name=name,
                inn=inn,
            )
        )
    return counterparties


def _normalize_amount_ranges(raw_value: Any) -> list[Kvo17GeneratedPurchaseAmountRange]:
    if isinstance(raw_value, Mapping):
        raw_ranges = [
            {"range_key": key, **dict(value)}
            for key, value in raw_value.items()
            if isinstance(value, Mapping)
        ]
    else:
        raw_ranges = raw_value
    if not isinstance(raw_ranges, list) or len(raw_ranges) != 2:
        raise ValidationError("KVO17 generated purchase requires exactly two amount ranges.")

    ranges: list[Kvo17GeneratedPurchaseAmountRange] = []
    seen_keys: set[str] = set()
    seen_kvo: set[str] = set()
    for index, raw_range in enumerate(raw_ranges, start=1):
        if not isinstance(raw_range, Mapping):
            raise ValidationError(f"Amount range {index}: expected object.")
        range_key = str(
            raw_range.get("range_key")
            or raw_range.get("key")
            or (KVO17_GENERATED_PURCHASE_DEFAULT_RANGE_KEYS[index - 1] if index <= 2 else "")
        ).strip()
        if not range_key:
            raise ValidationError(f"Amount range {index}: range_key is required.")
        if range_key in seen_keys:
            raise ValidationError(f"Amount range {index}: duplicate range_key '{range_key}'.")
        seen_keys.add(range_key)

        min_amount = _required_amount(raw_range, key="min_amount", field_name=f"{range_key}.min_amount")
        max_amount = _required_amount(raw_range, key="max_amount", field_name=f"{range_key}.max_amount")
        if min_amount <= Decimal("0.00") or max_amount <= Decimal("0.00"):
            raise ValidationError(f"Amount range '{range_key}' must use positive bounds.")
        if max_amount < min_amount:
            raise ValidationError(f"Amount range '{range_key}' max_amount must be greater than or equal to min_amount.")

        kvo = str(raw_range.get("kvo") or raw_range.get("source_kvo_override") or "").strip()
        if kvo not in KVO17_PURCHASE_SPLIT_ALLOWED_KVO_OVERRIDES:
            raise ValidationError(
                f"Amount range '{range_key}' kvo must be one of: "
                + ", ".join(KVO17_PURCHASE_SPLIT_ALLOWED_KVO_OVERRIDES)
            )
        if kvo in seen_kvo:
            raise ValidationError("KVO17 generated purchase amount ranges must use distinct KVO values.")
        seen_kvo.add(kvo)
        ranges.append(
            Kvo17GeneratedPurchaseAmountRange(
                range_key=range_key,
                min_amount=min_amount,
                max_amount=max_amount,
                kvo=kvo,
            )
        )
    return ranges


def _validate_counterparty_refs(
    *,
    counterparties: list[Kvo17GeneratedPurchaseCounterparty],
    available_counterparty_refs: set[str] | None,
) -> None:
    if available_counterparty_refs is None:
        return
    stale_refs = sorted(
        item.ref
        for item in counterparties
        if item.ref not in available_counterparty_refs
    )
    if stale_refs:
        raise ValidationError(
            "KVO17 generated purchase contains stale counterparty refs: "
            + ", ".join(stale_refs)
        )


def _random_date(
    *,
    period_start: date,
    period_end: date,
    seed: str,
    request_hash: str,
    counterparty_ref: str,
) -> date:
    days_count = (period_end - period_start).days
    rng = _rng_for(seed, request_hash, "date", counterparty_ref)
    return period_start + timedelta(days=rng.randint(0, days_count))


def _random_amount(
    *,
    amount_range: Kvo17GeneratedPurchaseAmountRange,
    seed: str,
    request_hash: str,
    counterparty_ref: str,
) -> Decimal:
    min_cents = _amount_to_cents(amount_range.min_amount)
    max_cents = _amount_to_cents(amount_range.max_amount)
    rng = _rng_for(seed, request_hash, "amount", counterparty_ref, amount_range.range_key)
    return (Decimal(rng.randint(min_cents, max_cents)) / Decimal("100")).quantize(Decimal("0.01"))


def _build_invoice_number(
    *,
    prefix: str,
    counterparty_index: int,
    seed: str,
    request_hash: str,
    counterparty_ref: str,
) -> str:
    digest = _stable_hash(
        {
            "seed": seed,
            "request_hash": request_hash,
            "counterparty_ref": counterparty_ref,
            "counterparty_index": counterparty_index,
        }
    )
    return f"{prefix}-{counterparty_index:04d}-{digest[:8].upper()}"


def _calculate_included_vat(*, amount: Decimal, vat_rate: str) -> Decimal:
    rate = _vat_rate_to_decimal(vat_rate)
    if rate == Decimal("0.00"):
        return Decimal("0.00")
    return (amount * rate / (Decimal("100.00") + rate)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def _normalize_vat_rate(raw_value: Any) -> str:
    text = str(raw_value or "").strip().replace(",", ".")
    if text.endswith("%"):
        numeric = text[:-1].strip()
    else:
        numeric = text
    try:
        value = Decimal(numeric).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"Invalid KVO17 generated purchase vat_rate '{raw_value}'.") from exc
    if value < Decimal("0.00") or value > Decimal("100.00"):
        raise ValidationError("KVO17 generated purchase vat_rate must be in range 0..100.")
    if value == value.to_integral():
        return f"{int(value)}%"
    return f"{value.normalize()}%"


def _vat_rate_to_decimal(vat_rate: str) -> Decimal:
    return Decimal(str(vat_rate).strip().rstrip("%"))


def _amount_to_cents(amount: Decimal) -> int:
    return int((amount * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))


def _rng_for(*parts: str) -> random.Random:
    digest = _stable_hash({"parts": [str(part) for part in parts]})
    return random.Random(int(digest[:16], 16))


def _stable_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValidationError(f"KVO17 generated purchase requires {key}.")
    return value


def _first_text(
    payload: Mapping[str, Any],
    *keys: str,
    error_field: str,
) -> str:
    for key in keys:
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    raise ValidationError(f"KVO17 generated purchase requires {error_field}.")


def _required_date(payload: Mapping[str, Any], key: str) -> date:
    raw_value = payload.get(key)
    if isinstance(raw_value, date) and not isinstance(raw_value, datetime):
        return raw_value
    value = str(raw_value or "").strip()
    if not value:
        raise ValidationError(f"KVO17 generated purchase requires {key}.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"Invalid KVO17 generated purchase {key} '{raw_value}'.") from exc


def _required_amount(payload: Mapping[str, Any], *, key: str, field_name: str) -> Decimal:
    return parse_pool_schema_template_amount(
        payload.get(key),
        quantizer=Decimal("0.01"),
        field_name=field_name,
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


__all__ = [
    "KVO17_GENERATED_PURCHASE_DEFAULT_RANGE_KEYS",
    "KVO17_GENERATED_PURCHASE_MANIFEST_VERSION",
    "KVO17_GENERATED_PURCHASE_METADATA_KEY",
    "KVO17_GENERATED_PURCHASE_POLICY_SLOT",
    "KVO17_GENERATED_PURCHASE_POLICY_SLOTS",
    "KVO17_GENERATED_PURCHASE_REQUEST_SCHEMA_VERSION",
    "KVO17_GENERATED_PURCHASE_SOURCE_TYPE",
    "Kvo17GeneratedPurchaseAmountRange",
    "Kvo17GeneratedPurchaseCounterparty",
    "Kvo17GeneratedPurchaseManifest",
    "Kvo17GeneratedPurchaseRow",
    "build_kvo17_generated_purchase_manifest",
    "build_kvo17_generated_purchase_request_schema",
    "validate_kvo17_generated_purchase_manifest_reuse",
]
