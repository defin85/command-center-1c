from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

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
    source_hash: str,
) -> str:
    normalized_hash = str(source_hash or "").strip().lower()
    period_signature = period_start.isoformat()
    if period_end is not None:
        period_signature = f"{period_signature}:{period_end.isoformat()}"
    raw = "|".join([str(pool_id), period_signature, str(direction), normalized_hash])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def upsert_pool_run(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    direction: str,
    period_start: date,
    period_end: date | None,
    source_hash: str,
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
        source_hash=source_hash,
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
                source_hash=source_hash,
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
            "source_hash": source_hash,
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
                payload={"updated_fields": changed_fields, "idempotency_key": idempotency_key},
            )

        return PoolRunUpsertResult(run=run, created=False)
