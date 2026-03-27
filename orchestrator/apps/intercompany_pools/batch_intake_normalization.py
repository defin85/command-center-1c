from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Callable, Mapping

from django.core.exceptions import ValidationError

from .batch_intake_parsers import parse_pool_schema_template_amount, parse_pool_schema_template_rows
from .models import OrganizationPool, PoolBatchKind, PoolBatchSourceType, PoolSchemaTemplate


@dataclass(frozen=True)
class CanonicalPoolBatchLine:
    line_no: int
    organization_inn: str
    amount_with_vat: Decimal
    external_id: str = ""
    amount_without_vat: Decimal | None = None
    vat_amount: Decimal | None = None


@dataclass(frozen=True)
class CanonicalPoolBatchProvenance:
    batch_kind: str
    source_type: str
    source_reference: str
    raw_payload_ref: str
    content_hash: str
    source_metadata: dict[str, Any]
    schema_reference: dict[str, str] | None
    integration_reference: dict[str, str] | None


@dataclass(frozen=True)
class CanonicalPoolBatchNormalizationResult:
    pool_id: str
    period_start: date
    period_end: date | None
    provenance: CanonicalPoolBatchProvenance
    lines: list[CanonicalPoolBatchLine]
    normalization_summary: dict[str, Any]


PoolBatchIntakeAdapter = Callable[..., CanonicalPoolBatchNormalizationResult]

_POOL_BATCH_INTAKE_ADAPTERS: dict[str, PoolBatchIntakeAdapter] = {}


def register_pool_batch_intake_adapter(source_type: str, adapter: PoolBatchIntakeAdapter) -> None:
    _POOL_BATCH_INTAKE_ADAPTERS[str(source_type)] = adapter


def unregister_pool_batch_intake_adapter(source_type: str) -> None:
    _POOL_BATCH_INTAKE_ADAPTERS.pop(str(source_type), None)


def normalize_pool_batch_intake(
    *,
    pool: OrganizationPool,
    batch_kind: str,
    source_type: str,
    period_start: date | None,
    period_end: date | None = None,
    schema_template: PoolSchemaTemplate | None = None,
    integration_reference: str | None = None,
    json_payload: Any | None = None,
    xlsx_bytes: bytes | None = None,
    raw_payload_ref: str = "",
    source_reference: str = "",
    source_metadata: Mapping[str, Any] | None = None,
) -> CanonicalPoolBatchNormalizationResult:
    normalized_batch_kind = _normalize_batch_kind(batch_kind)
    normalized_source_type = _normalize_source_type(source_type)
    validated_period_start, validated_period_end = _validate_period(
        period_start=period_start,
        period_end=period_end,
    )

    adapter = _POOL_BATCH_INTAKE_ADAPTERS.get(normalized_source_type)
    if adapter is None:
        raise ValidationError(f"Unsupported pool batch intake source_type '{normalized_source_type}'.")

    return adapter(
        pool=pool,
        batch_kind=normalized_batch_kind,
        source_type=normalized_source_type,
        period_start=validated_period_start,
        period_end=validated_period_end,
        schema_template=schema_template,
        integration_reference=integration_reference,
        json_payload=json_payload,
        xlsx_bytes=xlsx_bytes,
        raw_payload_ref=str(raw_payload_ref or "").strip(),
        source_reference=str(source_reference or "").strip(),
        source_metadata=dict(source_metadata or {}),
    )


def _normalize_schema_template_upload(
    *,
    pool: OrganizationPool,
    batch_kind: str,
    source_type: str,
    period_start: date,
    period_end: date | None,
    schema_template: PoolSchemaTemplate | None,
    integration_reference: str | None,
    json_payload: Any | None,
    xlsx_bytes: bytes | None,
    raw_payload_ref: str,
    source_reference: str,
    source_metadata: dict[str, Any],
) -> CanonicalPoolBatchNormalizationResult:
    del integration_reference

    template = _validate_schema_template(pool=pool, schema_template=schema_template)
    rows = parse_pool_schema_template_rows(
        template=template,
        json_payload=json_payload,
        xlsx_bytes=xlsx_bytes,
    )
    organization_key = _resolve_required_column(
        template.schema,
        target="organization_inn",
        aliases=("inn",),
    )
    amount_key = _resolve_required_column(
        template.schema,
        target="amount_with_vat",
        aliases=("amount",),
    )
    external_id_key = _resolve_optional_column(template.schema, target="external_id")
    amount_without_vat_key = _resolve_optional_column(template.schema, target="amount_without_vat")
    vat_amount_key = _resolve_optional_column(template.schema, target="vat_amount")

    quantizer = Decimal("0.01")
    lines: list[CanonicalPoolBatchLine] = []
    total_amount_with_vat = Decimal("0.00")
    for line_no, row in enumerate(rows, start=1):
        organization_inn = str(row.get(organization_key) or "").strip()
        if not organization_inn:
            raise ValidationError(f"Row {line_no}: missing required organization_inn value.")
        amount_with_vat = parse_pool_schema_template_amount(
            row.get(amount_key),
            quantizer=quantizer,
            field_name="amount_with_vat",
        )
        amount_without_vat = _parse_optional_amount(
            row=row,
            key=amount_without_vat_key,
            quantizer=quantizer,
            field_name="amount_without_vat",
        )
        vat_amount = _parse_optional_amount(
            row=row,
            key=vat_amount_key,
            quantizer=quantizer,
            field_name="vat_amount",
        )
        line = CanonicalPoolBatchLine(
            line_no=line_no,
            organization_inn=organization_inn,
            amount_with_vat=amount_with_vat,
            external_id=str(row.get(external_id_key) or "").strip() if external_id_key else "",
            amount_without_vat=amount_without_vat,
            vat_amount=vat_amount,
        )
        lines.append(line)
        total_amount_with_vat += amount_with_vat

    serialized_rows = json.dumps(rows, sort_keys=True, ensure_ascii=True, separators=(",", ":"), default=str)
    provenance = CanonicalPoolBatchProvenance(
        batch_kind=batch_kind,
        source_type=source_type,
        source_reference=source_reference,
        raw_payload_ref=raw_payload_ref,
        content_hash=hashlib.sha256(serialized_rows.encode("utf-8")).hexdigest(),
        source_metadata=dict(source_metadata),
        schema_reference={
            "template_id": str(template.id),
            "template_code": template.code,
        },
        integration_reference=None,
    )
    return CanonicalPoolBatchNormalizationResult(
        pool_id=str(pool.id),
        period_start=period_start,
        period_end=period_end,
        provenance=provenance,
        lines=lines,
        normalization_summary={
            "processed_rows": len(rows),
            "normalized_rows": len(lines),
            "total_amount_with_vat": total_amount_with_vat.quantize(quantizer),
        },
    )


def _normalize_batch_kind(batch_kind: str) -> str:
    normalized = str(batch_kind or "").strip()
    if normalized not in set(PoolBatchKind.values):
        raise ValidationError(f"Unsupported pool batch kind '{normalized}'.")
    return normalized


def _normalize_source_type(source_type: str) -> str:
    normalized = str(source_type or "").strip()
    if normalized not in set(PoolBatchSourceType.values):
        raise ValidationError(f"Unsupported pool batch source_type '{normalized}'.")
    return normalized


def _validate_period(*, period_start: date | None, period_end: date | None) -> tuple[date, date | None]:
    if period_start is None:
        raise ValidationError("Batch intake requires explicit period_start.")
    if period_end is not None and period_end < period_start:
        raise ValidationError("Batch intake period_end must be greater than or equal to period_start.")
    return period_start, period_end


def _validate_schema_template(
    *,
    pool: OrganizationPool,
    schema_template: PoolSchemaTemplate | None,
) -> PoolSchemaTemplate:
    if schema_template is None:
        raise ValidationError("Schema template upload intake requires schema_template.")
    if schema_template.tenant_id != pool.tenant_id:
        raise ValidationError("Schema template tenant must match pool tenant.")
    if not schema_template.is_public:
        raise ValidationError("Schema template upload intake accepts only public templates.")
    if not schema_template.is_active:
        raise ValidationError("Schema template upload intake template is inactive.")
    return schema_template


def _resolve_required_column(schema: Mapping[str, Any], *, target: str, aliases: tuple[str, ...] = ()) -> str:
    key = _resolve_optional_column(schema, target=target, aliases=aliases)
    if key is None:
        raise ValidationError(f"Schema template is missing required '{target}' mapping.")
    return key


def _resolve_optional_column(
    schema: Mapping[str, Any],
    *,
    target: str,
    aliases: tuple[str, ...] = (),
) -> str | None:
    raw_columns = schema.get("columns") if isinstance(schema, Mapping) else None
    if not isinstance(raw_columns, Mapping):
        return None
    for key in (target, *aliases):
        candidate = str(raw_columns.get(key) or "").strip()
        if candidate:
            return candidate
    return None


def _parse_optional_amount(
    *,
    row: Mapping[str, Any],
    key: str | None,
    quantizer: Decimal,
    field_name: str,
) -> Decimal | None:
    if not key:
        return None
    raw_value = row.get(key)
    if raw_value in (None, ""):
        return None
    return parse_pool_schema_template_amount(raw_value, quantizer=quantizer, field_name=field_name)


register_pool_batch_intake_adapter(
    PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
    _normalize_schema_template_upload,
)


__all__ = [
    "CanonicalPoolBatchLine",
    "CanonicalPoolBatchNormalizationResult",
    "CanonicalPoolBatchProvenance",
    "normalize_pool_batch_intake",
    "register_pool_batch_intake_adapter",
    "unregister_pool_batch_intake_adapter",
]
