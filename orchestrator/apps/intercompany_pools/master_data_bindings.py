from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.databases.models import Database
from apps.tenancy.models import Tenant

from .models import (
    PoolMasterBindingSyncStatus,
    PoolMasterDataBinding,
    PoolMasterDataEntityType,
)
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


def upsert_pool_master_data_binding(
    *,
    tenant: Tenant,
    entity_type: str,
    canonical_id: str,
    database: Database,
    ib_ref_key: str,
    ib_catalog_kind: str = "",
    owner_counterparty_canonical_id: str = "",
    sync_status: str = PoolMasterBindingSyncStatus.UPSERTED,
    fingerprint: str = "",
    metadata: dict[str, Any] | None = None,
) -> PoolMasterDataBindingUpsertResult:
    normalized_entity_type = str(entity_type or "").strip()
    if normalized_entity_type not in set(PoolMasterDataEntityType.values):
        raise MasterDataResolveError(
            code=MASTER_DATA_ENTITY_NOT_FOUND,
            detail=f"Unsupported master-data entity_type '{entity_type}'",
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
    }

    updatable_fields = {
        "ib_ref_key": str(ib_ref_key or "").strip(),
        "sync_status": str(sync_status or "").strip(),
        "fingerprint": str(fingerprint or "").strip(),
        "metadata": dict(metadata or {}),
    }

    try:
        with transaction.atomic():
            candidates = _load_scope_candidates(scope=scope)
            if len(candidates) > 1:
                diagnostics = [
                    {"binding_id": str(candidate.id)}
                    for candidate in candidates
                ]
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
