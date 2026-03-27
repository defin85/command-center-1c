from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction

from apps.tenancy.models import Tenant

from .models import (
    Organization,
    OrganizationPool,
    PoolBatch,
    PoolBatchKind,
    PoolRun,
    PoolRunDirection,
    PoolRunMode,
    PoolSchemaTemplate,
)


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
    batch_id: str | None = None,
    start_organization_id: str | None = None,
) -> str:
    normalized_run_input = _canonicalize_run_input(
        run_input,
        batch_id=batch_id,
        start_organization_id=start_organization_id,
    )
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


def _canonicalize_run_input(
    run_input: dict[str, Any] | None,
    *,
    batch_id: str | None = None,
    start_organization_id: str | None = None,
) -> str:
    if batch_id is not None or start_organization_id is not None:
        normalized_batch_id = str(batch_id or "").strip()
        normalized_start_organization_id = str(start_organization_id or "").strip()
        if not normalized_batch_id or not normalized_start_organization_id:
            raise ValueError(
                "Batch-backed pool run idempotency requires both batch_id and start_organization_id."
            )
        return json.dumps(
            {
                "batch_id": normalized_batch_id,
                "start_organization_id": normalized_start_organization_id,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )

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
    source_batch: PoolBatch | None = None,
    start_organization: Organization | None = None,
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
    if source_batch is not None or start_organization is not None:
        if direction != PoolRunDirection.TOP_DOWN:
            raise ValueError("Batch-backed pool run idempotency is only supported for top_down direction.")
        if source_batch is None or start_organization is None:
            raise ValueError("Batch-backed pool run requires both source_batch and start_organization.")

    idempotency_key = build_pool_run_idempotency_key(
        pool_id=str(pool.id),
        period_start=period_start,
        period_end=period_end,
        direction=direction,
        workflow_binding_id=workflow_binding_id,
        workflow_binding_revision=workflow_binding_revision,
        binding_profile_revision_id=binding_profile_revision_id,
        run_input=run_input,
        batch_id=str(source_batch.id) if source_batch is not None else None,
        start_organization_id=str(start_organization.id) if start_organization is not None else None,
    )

    with transaction.atomic():
        locked_batch: PoolBatch | None = None
        if source_batch is not None and start_organization is not None:
            locked_batch = PoolBatch.objects.select_for_update().get(id=source_batch.id)
            if locked_batch.tenant_id != tenant.id:
                raise ValueError("Batch-backed pool run requires a batch from the same tenant.")
            if locked_batch.pool_id != pool.id:
                raise ValueError("Batch-backed pool run requires a batch from the selected pool.")
            if locked_batch.batch_kind != PoolBatchKind.RECEIPT:
                raise ValueError("Only receipt batches can launch batch-backed top_down runs.")
            if locked_batch.period_start != period_start or locked_batch.period_end != period_end:
                raise ValueError("Batch-backed pool run period must match the canonical batch period.")
            if locked_batch.start_organization_id and locked_batch.start_organization_id != start_organization.id:
                raise ValueError("Receipt batch already pinned to a different start organization.")
            existing_batch_run = (
                PoolRun.objects.select_for_update().filter(id=locked_batch.run_id).first()
                if locked_batch.run_id
                else None
            )
            if existing_batch_run is not None and existing_batch_run.idempotency_key != idempotency_key:
                raise ValueError("Receipt batch already linked to another pool run.")

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
            if locked_batch is not None:
                locked_batch.start_organization = start_organization
                locked_batch.run = run
                locked_batch.save(update_fields=["start_organization", "run", "updated_at"])
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

        if locked_batch is not None:
            batch_changed_fields: list[str] = []
            if locked_batch.start_organization_id != start_organization.id:
                locked_batch.start_organization = start_organization
                batch_changed_fields.append("start_organization")
            if locked_batch.run_id != run.id:
                locked_batch.run = run
                batch_changed_fields.append("run")
            if batch_changed_fields:
                locked_batch.save(update_fields=[*batch_changed_fields, "updated_at"])

        return PoolRunUpsertResult(run=run, created=False)
