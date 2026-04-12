from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from .master_data_dedupe import (
    MasterDataDedupeReviewRequiredError,
    require_pool_master_data_dedupe_resolved,
)
from .master_data_errors import MASTER_DATA_ENTITY_NOT_FOUND, MasterDataResolveError
from .master_data_registry import normalize_pool_master_data_entity_type
from .master_data_sync_conflicts import (
    MASTER_DATA_SYNC_CONFLICT_DEDUPE_REVIEW_REQUIRED,
    enqueue_master_data_sync_conflict,
)
from .master_data_sync_outbox import enqueue_master_data_sync_outbox_intent
from .models import (
    PoolMasterContract,
    PoolMasterDataEntityType,
    PoolMasterItem,
    PoolMasterParty,
    PoolMasterTaxProfile,
)


@dataclass(frozen=True)
class ManualOutboundSnapshotResult:
    candidates: int
    prepared: int
    blocked: int


def enqueue_manual_outbound_snapshot_for_scope(
    *,
    tenant_id: str | UUID,
    database_id: str | UUID,
    entity_type: str,
    origin_system: str,
    origin_event_id: str,
) -> ManualOutboundSnapshotResult:
    normalized_entity_type = normalize_pool_master_data_entity_type(entity_type)
    candidates = 0
    prepared = 0
    blocked = 0

    for entity in _iter_scope_entities(tenant_id=str(tenant_id), entity_type=normalized_entity_type):
        candidates += 1
        canonical_id = str(entity.canonical_id)
        try:
            require_pool_master_data_dedupe_resolved(
                tenant_id=str(tenant_id),
                entity_type=normalized_entity_type,
                canonical_id=canonical_id,
            )
        except MasterDataDedupeReviewRequiredError as exc:
            enqueue_master_data_sync_conflict(
                tenant_id=str(tenant_id),
                database_id=str(database_id),
                entity_type=normalized_entity_type,
                conflict_code=MASTER_DATA_SYNC_CONFLICT_DEDUPE_REVIEW_REQUIRED,
                canonical_id=canonical_id,
                origin_system=str(origin_system or ""),
                origin_event_id=str(origin_event_id or ""),
                diagnostics=exc.to_diagnostic(),
                metadata={
                    "runtime_gate": "dedupe_review_required",
                    "launch_seed": "manual_outbound_snapshot",
                },
            )
            blocked += 1
            continue

        mutation_kind, payload = _build_outbound_payload(entity_type=normalized_entity_type, entity=entity)
        outbox_row = enqueue_master_data_sync_outbox_intent(
            tenant_id=str(tenant_id),
            database_id=str(database_id),
            entity_type=normalized_entity_type,
            canonical_id=canonical_id,
            mutation_kind=mutation_kind,
            payload=payload,
            origin_system=str(origin_system or ""),
            origin_event_id=f"{origin_event_id}:{canonical_id}",
        )
        if outbox_row is not None:
            prepared += 1

    return ManualOutboundSnapshotResult(
        candidates=candidates,
        prepared=prepared,
        blocked=blocked,
    )


def _iter_scope_entities(*, tenant_id: str, entity_type: str):
    if entity_type == PoolMasterDataEntityType.PARTY:
        return PoolMasterParty.objects.filter(tenant_id=tenant_id).order_by("created_at", "id").iterator(chunk_size=200)
    if entity_type == PoolMasterDataEntityType.ITEM:
        return PoolMasterItem.objects.filter(tenant_id=tenant_id).order_by("created_at", "id").iterator(chunk_size=200)
    if entity_type == PoolMasterDataEntityType.TAX_PROFILE:
        return PoolMasterTaxProfile.objects.filter(tenant_id=tenant_id).order_by("created_at", "id").iterator(chunk_size=200)
    if entity_type == PoolMasterDataEntityType.CONTRACT:
        return (
            PoolMasterContract.objects.select_related("owner_counterparty")
            .filter(tenant_id=tenant_id)
            .order_by("created_at", "id")
            .iterator(chunk_size=200)
        )
    raise MasterDataResolveError(
        code=MASTER_DATA_ENTITY_NOT_FOUND,
        detail=f"Unsupported outbound snapshot entity_type '{entity_type}'",
        entity_type=entity_type,
        canonical_id="",
        target_database_id="",
    )


def _build_outbound_payload(*, entity_type: str, entity: Any) -> tuple[str, dict[str, Any]]:
    if entity_type == PoolMasterDataEntityType.PARTY:
        return (
            "party_upsert",
            {
                "canonical_id": str(entity.canonical_id),
                "name": str(entity.name or ""),
                "full_name": str(entity.full_name or ""),
                "inn": str(entity.inn or ""),
                "kpp": str(entity.kpp or ""),
                "is_our_organization": bool(entity.is_our_organization),
                "is_counterparty": bool(entity.is_counterparty),
                "metadata": dict(entity.metadata or {}),
            },
        )
    if entity_type == PoolMasterDataEntityType.ITEM:
        return (
            "item_upsert",
            {
                "canonical_id": str(entity.canonical_id),
                "name": str(entity.name or ""),
                "sku": str(entity.sku or ""),
                "unit": str(entity.unit or ""),
                "metadata": dict(entity.metadata or {}),
            },
        )
    if entity_type == PoolMasterDataEntityType.TAX_PROFILE:
        return (
            "tax_profile_upsert",
            {
                "canonical_id": str(entity.canonical_id),
                "vat_rate": str(entity.vat_rate),
                "vat_included": bool(entity.vat_included),
                "vat_code": str(entity.vat_code or ""),
                "metadata": dict(entity.metadata or {}),
            },
        )
    if entity_type == PoolMasterDataEntityType.CONTRACT:
        return (
            "contract_upsert",
            {
                "canonical_id": str(entity.canonical_id),
                "name": str(entity.name or ""),
                "owner_counterparty_id": str(entity.owner_counterparty_id),
                "owner_counterparty_canonical_id": str(entity.owner_counterparty.canonical_id),
                "number": str(entity.number or ""),
                "date": entity.date.isoformat() if entity.date else "",
                "metadata": dict(entity.metadata or {}),
            },
        )
    raise MasterDataResolveError(
        code=MASTER_DATA_ENTITY_NOT_FOUND,
        detail=f"Unsupported outbound snapshot entity_type '{entity_type}'",
        entity_type=entity_type,
        canonical_id="",
        target_database_id="",
    )


__all__ = [
    "ManualOutboundSnapshotResult",
    "enqueue_manual_outbound_snapshot_for_scope",
]
