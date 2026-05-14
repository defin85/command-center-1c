from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Callable, Mapping

from django.core.exceptions import ValidationError

from .batch_intake_parsers import parse_pool_schema_template_amount, parse_pool_schema_template_rows
from .kvo18_advance_vat_offset_intake import (
    KVO18_ADVANCE_VAT_OFFSET_INTAKE_SCHEMA_VERSION,
    KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS,
    normalize_kvo18_advance_vat_offset_batch,
)
from .kvo18_advance_vat_offset_preview import build_kvo18_advance_vat_offset_preview
from .kvo18_advance_vat_offset_scheme import (
    KVO18_ADVANCE_VAT_OFFSET_SCHEME_CODE,
    KVO18_ADVANCE_VAT_OFFSET_SCHEMA_TEMPLATE_CODE,
)
from .kvo17_generated_purchase_document_plan import (
    KVO17_GENERATED_PURCHASE_DOCUMENT_PLAN_VERSION,
    compile_kvo17_generated_purchase_document_plan,
)
from .kvo17_generated_purchase_intake import (
    KVO17_GENERATED_PURCHASE_MANIFEST_VERSION,
    KVO17_GENERATED_PURCHASE_METADATA_KEY,
    KVO17_GENERATED_PURCHASE_POLICY_SLOTS,
    build_kvo17_generated_purchase_manifest,
    validate_kvo17_generated_purchase_manifest_reuse,
)
from .models import OrganizationPool, PoolBatchKind, PoolBatchSourceType, PoolMasterParty, PoolSchemaTemplate

KVO18_ADVANCE_VAT_OFFSET_METADATA_KEY = "kvo18_advance_vat_offset"


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
    if _is_kvo18_advance_vat_offset_template(template):
        return _normalize_kvo18_advance_vat_offset_schema_template_upload(
            pool=pool,
            batch_kind=batch_kind,
            source_type=source_type,
            period_start=period_start,
            period_end=period_end,
            template=template,
            json_payload=json_payload,
            raw_payload_ref=raw_payload_ref,
            source_reference=source_reference,
            source_metadata=source_metadata,
        )

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


def _normalize_kvo18_advance_vat_offset_schema_template_upload(
    *,
    pool: OrganizationPool,
    batch_kind: str,
    source_type: str,
    period_start: date,
    period_end: date | None,
    template: PoolSchemaTemplate,
    json_payload: Any | None,
    raw_payload_ref: str,
    source_reference: str,
    source_metadata: dict[str, Any],
) -> CanonicalPoolBatchNormalizationResult:
    kvo18_batch = normalize_kvo18_advance_vat_offset_batch(
        json_payload=json_payload,
        source_reference=source_reference,
        raw_payload_ref=raw_payload_ref,
        source_metadata=source_metadata,
    )
    preview = build_kvo18_advance_vat_offset_preview(batch=kvo18_batch)
    blocking_diagnostics = [
        diagnostic
        for diagnostic in preview.diagnostics
        if str(diagnostic.get("severity") or "").strip().lower() == "error"
    ]
    if blocking_diagnostics:
        details = "; ".join(
            str(diagnostic.get("detail") or diagnostic.get("code") or "")
            for diagnostic in blocking_diagnostics
        )
        raise ValidationError(details or "KVO18 advance VAT offset intake has blocking diagnostics.")

    lines = [
        CanonicalPoolBatchLine(
            line_no=row.line_no,
            organization_inn=row.counterparty_ref,
            amount_with_vat=row.amount,
            external_id=row.row_id,
            vat_amount=row.vat_amount,
        )
        for row in kvo18_batch.rows
    ]
    kvo18_preview = preview.as_dict()
    stage_intent = str(source_metadata.get("kvo18_stage_intent") or "").strip()
    kvo18_metadata = {
        "policy_revision": preview.policy_revision,
        "content_hash": kvo18_batch.content_hash,
        "document_policy_slots": list(KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS),
        "stage_intent": stage_intent,
        "stages": kvo18_preview["stages"],
        "technical_realization_policy": kvo18_preview["technical_realization_policy"],
        "evidence_requirements": kvo18_preview["evidence_requirements"],
        "rows": kvo18_preview["rows"],
        "diagnostics": kvo18_preview["diagnostics"],
    }
    normalized_source_metadata = dict(source_metadata)
    normalized_source_metadata[KVO18_ADVANCE_VAT_OFFSET_METADATA_KEY] = kvo18_metadata

    summary = kvo18_batch.normalization_summary()
    total_amount = summary["total_amount"]
    total_vat_amount = summary["total_vat_amount"]
    provenance = CanonicalPoolBatchProvenance(
        batch_kind=batch_kind,
        source_type=source_type,
        source_reference=source_reference,
        raw_payload_ref=raw_payload_ref,
        content_hash=kvo18_batch.content_hash,
        source_metadata=normalized_source_metadata,
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
            **summary,
            "total_amount_with_vat": total_amount,
            "total_vat_amount": total_vat_amount,
            "kvo18_policy_revision": preview.policy_revision,
        },
    )


def _normalize_kvo17_generated_purchase(
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
    del schema_template, integration_reference, xlsx_bytes
    if batch_kind != PoolBatchKind.RECEIPT:
        raise ValidationError("KVO17 generated purchase intake is available only for receipt batches.")
    if not isinstance(json_payload, Mapping):
        raise ValidationError("KVO17 generated purchase intake requires json_payload object.")
    if period_end is None:
        raise ValidationError("KVO17 generated purchase intake requires explicit period_end.")

    request_payload = dict(json_payload)
    request_payload.setdefault("period_start", period_start.isoformat())
    request_payload.setdefault("period_end", period_end.isoformat())
    available_counterparty_refs = set(
        PoolMasterParty.objects.filter(
            tenant=pool.tenant,
            is_counterparty=True,
        ).values_list("canonical_id", flat=True)
    )
    accepted_generated_metadata = source_metadata.get(KVO17_GENERATED_PURCHASE_METADATA_KEY)
    if accepted_generated_metadata is not None and not isinstance(accepted_generated_metadata, Mapping):
        raise ValidationError("KVO17 generated purchase accepted preview metadata must be an object.")
    accepted_manifest = (
        accepted_generated_metadata.get("accepted_manifest")
        if isinstance(accepted_generated_metadata, Mapping)
        else None
    )
    if accepted_manifest is not None and not isinstance(accepted_manifest, Mapping):
        raise ValidationError("KVO17 generated purchase accepted_manifest must be an object.")
    if accepted_manifest is not None:
        manifest = validate_kvo17_generated_purchase_manifest_reuse(
            request=request_payload,
            accepted_manifest=accepted_manifest,
            available_counterparty_refs=available_counterparty_refs,
        )
    else:
        manifest = build_kvo17_generated_purchase_manifest(
            request=request_payload,
            available_counterparty_refs=available_counterparty_refs,
        )
    document_plan = compile_kvo17_generated_purchase_document_plan(manifest=manifest)
    lines = [
        CanonicalPoolBatchLine(
            line_no=row.line_no,
            organization_inn=row.counterparty_ref,
            amount_with_vat=row.amount,
            external_id=row.row_id,
            vat_amount=row.vat_amount,
        )
        for row in manifest.rows
    ]
    generated_metadata = {
        "manifest_version": KVO17_GENERATED_PURCHASE_MANIFEST_VERSION,
        "document_plan_version": KVO17_GENERATED_PURCHASE_DOCUMENT_PLAN_VERSION,
        "content_hash": manifest.content_hash,
        "request_hash": manifest.request_hash,
        "document_policy_slots": list(KVO17_GENERATED_PURCHASE_POLICY_SLOTS),
        "manifest": manifest.as_dict(),
        "document_plan": document_plan,
        "diagnostics": [],
        "readback_policy": document_plan["collapse_readback_policy"],
        "accepted_preview": {
            "required": accepted_manifest is not None,
            "provided": isinstance(accepted_manifest, Mapping),
            "request_hash": manifest.request_hash,
            "content_hash": manifest.content_hash,
        },
    }
    normalized_source_metadata = dict(source_metadata)
    normalized_source_metadata[KVO17_GENERATED_PURCHASE_METADATA_KEY] = generated_metadata
    provenance = CanonicalPoolBatchProvenance(
        batch_kind=batch_kind,
        source_type=source_type,
        source_reference=source_reference,
        raw_payload_ref=raw_payload_ref,
        content_hash=manifest.content_hash,
        source_metadata=normalized_source_metadata,
        schema_reference=None,
        integration_reference=None,
    )
    summary = manifest.normalization_summary()
    return CanonicalPoolBatchNormalizationResult(
        pool_id=str(pool.id),
        period_start=period_start,
        period_end=period_end,
        provenance=provenance,
        lines=lines,
        normalization_summary={
            **summary,
            "kvo17_generated_manifest_version": KVO17_GENERATED_PURCHASE_MANIFEST_VERSION,
            "kvo17_generated_document_plan_version": KVO17_GENERATED_PURCHASE_DOCUMENT_PLAN_VERSION,
        },
    )


def _is_kvo18_advance_vat_offset_template(template: PoolSchemaTemplate) -> bool:
    metadata = template.metadata if isinstance(template.metadata, Mapping) else {}
    schema = template.schema if isinstance(template.schema, Mapping) else {}
    return (
        template.code == KVO18_ADVANCE_VAT_OFFSET_SCHEMA_TEMPLATE_CODE
        or metadata.get("scheme_code") == KVO18_ADVANCE_VAT_OFFSET_SCHEME_CODE
        or schema.get("version") == KVO18_ADVANCE_VAT_OFFSET_INTAKE_SCHEMA_VERSION
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
register_pool_batch_intake_adapter(
    PoolBatchSourceType.KVO17_GENERATED_PURCHASE,
    _normalize_kvo17_generated_purchase,
)


__all__ = [
    "CanonicalPoolBatchLine",
    "CanonicalPoolBatchNormalizationResult",
    "CanonicalPoolBatchProvenance",
    "normalize_pool_batch_intake",
    "register_pool_batch_intake_adapter",
    "unregister_pool_batch_intake_adapter",
]
