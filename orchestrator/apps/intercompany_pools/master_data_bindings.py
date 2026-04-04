from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.databases.models import Database
from apps.tenancy.models import Tenant

from .master_data_registry import (
    POOL_MASTER_DATA_CAPABILITY_DIRECT_BINDING,
    POOL_MASTER_DATA_CAPABILITY_OUTBOX_FANOUT,
    normalize_pool_master_data_entity_type,
    supports_pool_master_data_capability,
)
from .models import (
    PoolMasterBindingSyncStatus,
    PoolMasterDataBinding,
)
from .master_data_sync_origin import (
    MASTER_DATA_SYNC_ORIGIN_IB,
    normalize_master_data_sync_origin,
    should_skip_outbound_sync_for_origin,
)
from .master_data_sync_outbox import enqueue_master_data_sync_outbox_intent
from .master_data_errors import (
    MASTER_DATA_BINDING_AMBIGUOUS,
    MASTER_DATA_BINDING_CONFLICT,
    MASTER_DATA_ENTITY_NOT_FOUND,
    MasterDataResolveError,
)


@dataclass(frozen=True)
class PoolMasterDataBindingUpsertResult:
    binding: PoolMasterDataBinding
    created: bool
    changed: bool


def _load_scope_candidates(*, scope: dict[str, Any]) -> list[PoolMasterDataBinding]:
    return list(
        PoolMasterDataBinding.objects.select_for_update()
        .filter(**scope)
        .order_by("created_at", "id")[:2]
    )


def _build_binding_outbox_payload(*, binding: PoolMasterDataBinding) -> dict[str, Any]:
    return {
        "entity_type": str(binding.entity_type or "").strip(),
        "canonical_id": str(binding.canonical_id or "").strip(),
        "ib_ref_key": str(binding.ib_ref_key or "").strip(),
        "ib_catalog_kind": str(binding.ib_catalog_kind or "").strip(),
        "owner_counterparty_canonical_id": str(binding.owner_counterparty_canonical_id or "").strip(),
        "chart_identity": str(binding.chart_identity or "").strip(),
        "sync_status": str(binding.sync_status or "").strip(),
        "fingerprint": str(binding.fingerprint or "").strip(),
        "metadata": dict(binding.metadata or {}),
    }


def _enqueue_binding_outbox_intent(
    *,
    binding: PoolMasterDataBinding,
    origin_system: str,
    origin_event_id: str,
) -> None:
    origin = normalize_master_data_sync_origin(
        origin_system=origin_system,
        origin_event_id=origin_event_id,
    )
    if should_skip_outbound_sync_for_origin(
        origin_system=origin.origin_system,
        origin_event_id=origin.origin_event_id,
        target_system=MASTER_DATA_SYNC_ORIGIN_IB,
    ):
        return
    if not supports_pool_master_data_capability(
        entity_type=str(binding.entity_type),
        capability=POOL_MASTER_DATA_CAPABILITY_OUTBOX_FANOUT,
    ):
        return

    resolved_origin_event_id = origin.origin_event_id
    if not resolved_origin_event_id:
        resolved_origin_event_id = f"binding:{binding.id}:{int(binding.updated_at.timestamp())}"
    enqueue_master_data_sync_outbox_intent(
        tenant_id=str(binding.tenant_id),
        database_id=str(binding.database_id),
        entity_type=str(binding.entity_type),
        canonical_id=str(binding.canonical_id),
        mutation_kind="binding_upsert",
        payload=_build_binding_outbox_payload(binding=binding),
        origin_system=origin.origin_system,
        origin_event_id=resolved_origin_event_id,
    )


def upsert_pool_master_data_binding(
    *,
    tenant: Tenant,
    entity_type: str,
    canonical_id: str,
    database: Database,
    ib_ref_key: str,
    existing_binding: PoolMasterDataBinding | None = None,
    ib_catalog_kind: str = "",
    owner_counterparty_canonical_id: str = "",
    chart_identity: str = "",
    sync_status: str = PoolMasterBindingSyncStatus.UPSERTED,
    fingerprint: str = "",
    metadata: dict[str, Any] | None = None,
    origin_system: str = "cc",
    origin_event_id: str = "",
) -> PoolMasterDataBindingUpsertResult:
    normalized_entity_type = str(entity_type or "").strip()
    try:
        normalized_entity_type = normalize_pool_master_data_entity_type(normalized_entity_type)
    except ValueError:
        raise MasterDataResolveError(
            code=MASTER_DATA_ENTITY_NOT_FOUND,
            detail=f"Unsupported master-data entity_type '{entity_type}'",
            entity_type=normalized_entity_type,
            canonical_id=str(canonical_id or "").strip(),
            target_database_id=str(database.id),
        )
    if not supports_pool_master_data_capability(
        entity_type=normalized_entity_type,
        capability=POOL_MASTER_DATA_CAPABILITY_DIRECT_BINDING,
    ):
        raise MasterDataResolveError(
            code=MASTER_DATA_ENTITY_NOT_FOUND,
            detail=f"Master-data entity_type '{entity_type}' does not support direct bindings.",
            entity_type=normalized_entity_type,
            canonical_id=str(canonical_id or "").strip(),
            target_database_id=str(database.id),
        )

    scope = {
        "tenant": tenant,
        "entity_type": normalized_entity_type,
        "canonical_id": str(canonical_id or "").strip(),
        "database": database,
        "ib_catalog_kind": str(ib_catalog_kind or "").strip(),
        "owner_counterparty_canonical_id": str(owner_counterparty_canonical_id or "").strip(),
        "chart_identity": str(chart_identity or "").strip(),
    }

    updatable_fields = {
        "ib_ref_key": str(ib_ref_key or "").strip(),
        "sync_status": str(sync_status or "").strip(),
        "fingerprint": str(fingerprint or "").strip(),
        "metadata": dict(metadata or {}),
    }

    try:
        with transaction.atomic():
            binding = None
            if existing_binding is not None:
                binding = (
                    PoolMasterDataBinding.objects.select_for_update()
                    .filter(id=existing_binding.id, tenant=tenant)
                    .first()
                )
                if binding is None:
                    raise MasterDataResolveError(
                        code=MASTER_DATA_BINDING_CONFLICT,
                        detail="Binding not found for edit operation.",
                        entity_type=normalized_entity_type,
                        canonical_id=str(canonical_id or "").strip(),
                        target_database_id=str(database.id),
                    )
                candidates = [
                    candidate
                    for candidate in _load_scope_candidates(scope=scope)
                    if str(candidate.id) != str(binding.id)
                ]
                if candidates:
                    diagnostics = [{"binding_id": str(candidate.id)} for candidate in candidates]
                    raise MasterDataResolveError(
                        code=MASTER_DATA_BINDING_AMBIGUOUS,
                        detail=(
                            "Ambiguous master-data binding scope: multiple bindings "
                            "match the same canonical tuple."
                        ),
                        entity_type=normalized_entity_type,
                        canonical_id=str(canonical_id or "").strip(),
                        target_database_id=str(database.id),
                        errors=diagnostics,
                    )
                changed_fields: list[str] = []
                for field_name, new_value in {**scope, **updatable_fields}.items():
                    if getattr(binding, field_name) != new_value:
                        setattr(binding, field_name, new_value)
                        changed_fields.append(field_name)
                if changed_fields:
                    binding.last_synced_at = timezone.now()
                    binding.save(update_fields=[*changed_fields, "last_synced_at", "updated_at"])
                    _enqueue_binding_outbox_intent(
                        binding=binding,
                        origin_system=origin_system,
                        origin_event_id=origin_event_id,
                    )
                    return PoolMasterDataBindingUpsertResult(binding=binding, created=False, changed=True)
                return PoolMasterDataBindingUpsertResult(binding=binding, created=False, changed=False)

            candidates = _load_scope_candidates(scope=scope)
            if len(candidates) > 1:
                diagnostics = [{"binding_id": str(candidate.id)} for candidate in candidates]
                raise MasterDataResolveError(
                    code=MASTER_DATA_BINDING_AMBIGUOUS,
                    detail=(
                        "Ambiguous master-data binding scope: multiple bindings "
                        "match the same canonical tuple."
                    ),
                    entity_type=normalized_entity_type,
                    canonical_id=str(canonical_id or "").strip(),
                    target_database_id=str(database.id),
                    errors=diagnostics,
                )

            binding = candidates[0] if candidates else None
            if binding is None:
                created_binding = PoolMasterDataBinding.objects.create(
                    **scope,
                    **updatable_fields,
                    last_synced_at=timezone.now(),
                )
                _enqueue_binding_outbox_intent(
                    binding=created_binding,
                    origin_system=origin_system,
                    origin_event_id=origin_event_id,
                )
                return PoolMasterDataBindingUpsertResult(
                    binding=created_binding,
                    created=True,
                    changed=True,
                )

            changed_fields: list[str] = []
            for field_name, new_value in updatable_fields.items():
                if getattr(binding, field_name) != new_value:
                    setattr(binding, field_name, new_value)
                    changed_fields.append(field_name)

            if changed_fields:
                binding.last_synced_at = timezone.now()
                binding.save(update_fields=[*changed_fields, "last_synced_at", "updated_at"])
                _enqueue_binding_outbox_intent(
                    binding=binding,
                    origin_system=origin_system,
                    origin_event_id=origin_event_id,
                )
                return PoolMasterDataBindingUpsertResult(binding=binding, created=False, changed=True)

            return PoolMasterDataBindingUpsertResult(binding=binding, created=False, changed=False)
    except ValidationError as exc:
        raise MasterDataResolveError(
            code=MASTER_DATA_BINDING_CONFLICT,
            detail=str(exc),
            entity_type=normalized_entity_type,
            canonical_id=str(canonical_id or "").strip(),
            target_database_id=str(database.id),
            errors=[{"detail": str(exc)}],
        ) from exc
    except IntegrityError as exc:
        raise MasterDataResolveError(
            code=MASTER_DATA_BINDING_CONFLICT,
            detail=str(exc),
            entity_type=normalized_entity_type,
            canonical_id=str(canonical_id or "").strip(),
            target_database_id=str(database.id),
            errors=[{"detail": str(exc)}],
        ) from exc
