from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .models import PoolBatch, PoolRun, PoolRunDirection
from .run_input_sanitizer import sanitize_run_input_for_runtime_contract


def build_runtime_run_input(
    *,
    run: PoolRun,
    run_input: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = sanitize_run_input_for_runtime_contract(
        run_input=dict(run_input) if isinstance(run_input, Mapping) else run.run_input
    )
    if run.direction != PoolRunDirection.TOP_DOWN:
        return payload

    if _parse_decimal(payload.get("starting_amount")) is not None:
        return payload

    source_batch = _resolve_source_batch_for_runtime(run=run, run_input=payload)
    if source_batch is None:
        return payload

    normalization_summary = (
        source_batch.normalization_summary
        if isinstance(source_batch.normalization_summary, Mapping)
        else {}
    )
    starting_amount = _parse_decimal(normalization_summary.get("total_amount_with_vat"))
    if starting_amount is None:
        return payload

    payload["starting_amount"] = _decimal_to_string(starting_amount)
    return payload


def _resolve_source_batch_for_runtime(*, run: PoolRun, run_input: dict[str, Any]) -> PoolBatch | None:
    batch_id = str(run_input.get("batch_id") or "").strip()
    queryset = PoolBatch.objects.only("id", "normalization_summary", "run_id")
    if batch_id:
        return queryset.filter(id=batch_id, tenant_id=run.tenant_id, pool_id=run.pool_id).first()
    if run.pk is None:
        return None
    return queryset.filter(run_id=run.id).first()


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _decimal_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.quantize(Decimal("0.01")), "f")
