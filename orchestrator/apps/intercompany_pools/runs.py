from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction

from apps.tenancy.models import Tenant

from .models import OrganizationPool, PoolRun, PoolRunDirection, PoolRunMode, PoolSchemaTemplate


@dataclass(frozen=True)
class PoolRunUpsertResult:
    run: PoolRun
    created: bool


def build_pool_run_idempotency_key(
    *,
    pool_id: str,
    period_start: date,
    period_end: date | None,
    direction: str,
    workflow_binding_id: str | None = None,
    workflow_binding_revision: int | None = None,
    binding_profile_revision_id: str | None = None,
    run_input: dict[str, Any] | None,
) -> str:
    normalized_run_input = _canonicalize_run_input(run_input)
    period_signature = period_start.isoformat()
    if period_end is not None:
        period_signature = f"{period_signature}:{period_end.isoformat()}"
    raw = "|".join(
        [
            str(pool_id),
            period_signature,
            str(direction),
            f"workflow_binding={str(workflow_binding_id or '').strip()}",
            f"workflow_binding_revision={workflow_binding_revision if workflow_binding_revision is not None else ''}",
            f"binding_profile_revision_id={str(binding_profile_revision_id or '').strip()}",
            normalized_run_input,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _canonicalize_run_input(run_input: dict[str, Any] | None) -> str:
    payload = run_input if isinstance(run_input, dict) else {}
    normalized = _normalize_for_idempotency(payload)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _normalize_for_idempotency(value: Any, *, key_hint: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _normalize_for_idempotency(nested_value, key_hint=str(key))
            for key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [_normalize_for_idempotency(item, key_hint=key_hint) for item in value]
    if _is_money_key(key_hint):
        normalized_money = _normalize_money_scalar(value)
        if normalized_money is not None:
            return normalized_money
    if isinstance(value, Decimal):
        return format(value, "f")
    return value


def _is_money_key(key_hint: str | None) -> bool:
    if not key_hint:
        return False
    normalized = key_hint.strip().lower()
    return normalized == "amount" or normalized.endswith("_amount")


def _normalize_money_scalar(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
    elif isinstance(value, (int, float, Decimal)):
        raw = str(value)
    else:
        return None
    try:
        decimal_value = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    quantized = decimal_value.quantize(Decimal("0.01"))
    return format(quantized, "f")


def upsert_pool_run(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    direction: str,
    period_start: date,
    period_end: date | None,
    workflow_binding_id: str | None = None,
    workflow_binding_revision: int | None = None,
    binding_profile_revision_id: str | None = None,
    run_input: dict[str, Any] | None,
    mode: str = PoolRunMode.SAFE,
    schema_template: PoolSchemaTemplate | None = None,
    seed: int | None = None,
    created_by=None,
    validation_summary: dict | None = None,
    diagnostics: list | None = None,
) -> PoolRunUpsertResult:
    if direction not in PoolRunDirection.values:
        raise ValueError(f"Unsupported direction '{direction}'")
    if mode not in PoolRunMode.values:
        raise ValueError(f"Unsupported mode '{mode}'")

    idempotency_key = build_pool_run_idempotency_key(
        pool_id=str(pool.id),
        period_start=period_start,
        period_end=period_end,
        direction=direction,
        workflow_binding_id=workflow_binding_id,
        workflow_binding_revision=workflow_binding_revision,
        binding_profile_revision_id=binding_profile_revision_id,
        run_input=run_input,
    )

    with transaction.atomic():
        run = (
            PoolRun.objects.select_for_update()
            .filter(tenant=tenant, idempotency_key=idempotency_key)
            .first()
        )
        if run is None:
            run = PoolRun.objects.create(
                tenant=tenant,
                pool=pool,
                schema_template=schema_template,
                mode=mode,
                direction=direction,
                period_start=period_start,
                period_end=period_end,
                run_input=run_input or {},
                idempotency_key=idempotency_key,
                seed=seed,
                created_by=created_by,
                validation_summary=validation_summary or {},
                diagnostics=diagnostics or [],
            )
            run.add_audit_event(
                event_type="run.created",
                actor=created_by,
                status_before=None,
                status_after=run.status,
                payload={
                    "idempotency_key": idempotency_key,
                    "direction": direction,
                    "mode": mode,
                    "pool_workflow_binding_id": str(workflow_binding_id or "").strip() or None,
                    "pool_workflow_binding_revision": workflow_binding_revision,
                    "binding_profile_revision_id": (
                        str(binding_profile_revision_id or "").strip() or None
                    ),
                },
            )
            return PoolRunUpsertResult(run=run, created=True)

        update_fields = {
            "pool": pool,
            "schema_template": schema_template,
            "mode": mode,
            "direction": direction,
            "period_start": period_start,
            "period_end": period_end,
            "run_input": run_input or {},
            "seed": seed,
        }
        if validation_summary is not None:
            update_fields["validation_summary"] = validation_summary
        if diagnostics is not None:
            update_fields["diagnostics"] = diagnostics

        changed_fields: list[str] = []
        for field_name, new_value in update_fields.items():
            if getattr(run, field_name) != new_value:
                setattr(run, field_name, new_value)
                changed_fields.append(field_name)
        if changed_fields:
            run.save(update_fields=[*changed_fields, "updated_at"])
            run.add_audit_event(
                event_type="run.upserted",
                actor=created_by,
                status_before=run.status,
                status_after=run.status,
                payload={
                    "updated_fields": changed_fields,
                    "idempotency_key": idempotency_key,
                    "pool_workflow_binding_id": str(workflow_binding_id or "").strip() or None,
                    "pool_workflow_binding_revision": workflow_binding_revision,
                    "binding_profile_revision_id": (
                        str(binding_profile_revision_id or "").strip() or None
                    ),
                },
            )

        return PoolRunUpsertResult(run=run, created=False)
