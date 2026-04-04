from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from typing import Mapping
from uuid import UUID

from django.db import transaction

from apps.databases.models import Database

from .master_data_registry import POOL_MASTER_DATA_CAPABILITY_OUTBOX_FANOUT, supports_pool_master_data_capability
from .master_data_sync_execution import trigger_pool_master_data_outbound_sync_job
from .master_data_sync_origin import (
    MASTER_DATA_SYNC_ORIGIN_IB,
    normalize_master_data_sync_origin,
    should_skip_outbound_sync_for_origin,
)
from .master_data_sync_outbox import enqueue_master_data_sync_outbox_intent
from .models import PoolMasterContract
from .models import PoolMasterDataEntityType
from .models import PoolMasterGLAccount
from .models import PoolMasterItem
from .models import PoolMasterParty
from .models import PoolMasterTaxProfile


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CanonicalUpsertResult:
    entity: object
    created: bool
    changed: bool


class MasterDataCanonicalUpsertError(ValueError):
    def __init__(self, *, code: str, detail: str) -> None:
        self.code = str(code or "").strip() or "MASTER_DATA_CANONICAL_UPSERT_ERROR"
        self.detail = str(detail or "").strip() or "Canonical upsert failed."
        super().__init__(f"{self.code}: {self.detail}")


def assign_changed_fields(instance: object, payload: dict[str, Any]) -> bool:
    changed = False
    for field_name, value in payload.items():
        if getattr(instance, field_name) != value:
            setattr(instance, field_name, value)
            changed = True
    return changed


def enqueue_canonical_mutation_outbox_intents(
    *,
    tenant_id: str | UUID,
    entity_type: str,
    canonical_id: str,
    mutation_kind: str,
    payload: dict[str, Any],
    origin_event_id: str,
    origin_system: str = "cc",
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
        entity_type=entity_type,
        capability=POOL_MASTER_DATA_CAPABILITY_OUTBOX_FANOUT,
    ):
        return

    database_ids = list(
        Database.objects.filter(tenant_id=tenant_id).values_list("id", flat=True)
    )
    for database_id in database_ids:
        outbox_row = enqueue_master_data_sync_outbox_intent(
            tenant_id=str(tenant_id),
            database_id=str(database_id),
            entity_type=entity_type,
            canonical_id=canonical_id,
            mutation_kind=mutation_kind,
            payload=payload,
            origin_system=origin.origin_system,
            origin_event_id=origin.origin_event_id,
        )
        if outbox_row is None:
            continue
        _schedule_outbound_master_data_sync_job_trigger(
            tenant_id=str(tenant_id),
            database_id=str(database_id),
            entity_type=entity_type,
            canonical_id=canonical_id,
            origin_system=origin.origin_system,
            origin_event_id=origin.origin_event_id,
        )


def upsert_pool_master_data_party(
    *,
    tenant_id: str | UUID,
    canonical_id: str,
    name: str,
    full_name: str = "",
    inn: str = "",
    kpp: str = "",
    is_our_organization: bool = False,
    is_counterparty: bool = True,
    metadata: Mapping[str, Any] | None = None,
    existing: PoolMasterParty | None = None,
    origin_system: str = "cc",
    origin_event_id: str = "",
) -> CanonicalUpsertResult:
    tenant_id_token = str(tenant_id)
    canonical_id_token = str(canonical_id)
    payload = {
        "tenant_id": tenant_id_token,
        "canonical_id": canonical_id_token,
        "name": str(name),
        "full_name": str(full_name or ""),
        "inn": str(inn or ""),
        "kpp": str(kpp or ""),
        "is_our_organization": bool(is_our_organization),
        "is_counterparty": bool(is_counterparty),
        "metadata": dict(metadata or {}),
    }
    with transaction.atomic():
        party = existing
        if party is None:
            party = PoolMasterParty.objects.filter(
                tenant_id=tenant_id_token,
                canonical_id=canonical_id_token,
            ).first()
        created = party is None
        changed = True
        if created:
            party = PoolMasterParty.objects.create(**payload)
        else:
            changed = assign_changed_fields(party, payload)
            if changed:
                party.save()

        if changed:
            resolved_origin_event_id = str(origin_event_id or "").strip() or (
                f"party:{party.id}:{int(party.updated_at.timestamp())}"
            )
            enqueue_canonical_mutation_outbox_intents(
                tenant_id=tenant_id_token,
                entity_type=PoolMasterDataEntityType.PARTY,
                canonical_id=str(party.canonical_id),
                mutation_kind="party_upsert",
                payload={
                    "canonical_id": str(party.canonical_id),
                    "name": str(party.name or ""),
                    "full_name": str(party.full_name or ""),
                    "inn": str(party.inn or ""),
                    "kpp": str(party.kpp or ""),
                    "is_our_organization": bool(party.is_our_organization),
                    "is_counterparty": bool(party.is_counterparty),
                    "metadata": dict(party.metadata or {}),
                },
                origin_event_id=resolved_origin_event_id,
                origin_system=origin_system,
            )
    return CanonicalUpsertResult(entity=party, created=created, changed=changed)


def upsert_pool_master_data_item(
    *,
    tenant_id: str | UUID,
    canonical_id: str,
    name: str,
    sku: str = "",
    unit: str = "",
    metadata: Mapping[str, Any] | None = None,
    existing: PoolMasterItem | None = None,
    origin_system: str = "cc",
    origin_event_id: str = "",
) -> CanonicalUpsertResult:
    tenant_id_token = str(tenant_id)
    canonical_id_token = str(canonical_id)
    payload = {
        "tenant_id": tenant_id_token,
        "canonical_id": canonical_id_token,
        "name": str(name),
        "sku": str(sku or ""),
        "unit": str(unit or ""),
        "metadata": dict(metadata or {}),
    }
    with transaction.atomic():
        item = existing
        if item is None:
            item = PoolMasterItem.objects.filter(
                tenant_id=tenant_id_token,
                canonical_id=canonical_id_token,
            ).first()
        created = item is None
        changed = True
        if created:
            item = PoolMasterItem.objects.create(**payload)
        else:
            changed = assign_changed_fields(item, payload)
            if changed:
                item.save()

        if changed:
            resolved_origin_event_id = str(origin_event_id or "").strip() or (
                f"item:{item.id}:{int(item.updated_at.timestamp())}"
            )
            enqueue_canonical_mutation_outbox_intents(
                tenant_id=tenant_id_token,
                entity_type=PoolMasterDataEntityType.ITEM,
                canonical_id=str(item.canonical_id),
                mutation_kind="item_upsert",
                payload={
                    "canonical_id": str(item.canonical_id),
                    "name": str(item.name or ""),
                    "sku": str(item.sku or ""),
                    "unit": str(item.unit or ""),
                    "metadata": dict(item.metadata or {}),
                },
                origin_event_id=resolved_origin_event_id,
                origin_system=origin_system,
            )
    return CanonicalUpsertResult(entity=item, created=created, changed=changed)


def upsert_pool_master_data_gl_account(
    *,
    tenant_id: str | UUID,
    canonical_id: str,
    code: str,
    name: str,
    chart_identity: str,
    config_name: str,
    config_version: str,
    metadata: Mapping[str, Any] | None = None,
    existing: PoolMasterGLAccount | None = None,
    origin_system: str = "cc",
    origin_event_id: str = "",
) -> CanonicalUpsertResult:
    tenant_id_token = str(tenant_id)
    canonical_id_token = str(canonical_id)
    payload = {
        "tenant_id": tenant_id_token,
        "canonical_id": canonical_id_token,
        "code": str(code or ""),
        "name": str(name or ""),
        "chart_identity": str(chart_identity or ""),
        "config_name": str(config_name or ""),
        "config_version": str(config_version or ""),
        "metadata": dict(metadata or {}),
    }
    with transaction.atomic():
        gl_account = existing
        if gl_account is None:
            gl_account = PoolMasterGLAccount.objects.filter(
                tenant_id=tenant_id_token,
                canonical_id=canonical_id_token,
            ).first()
        created = gl_account is None
        changed = True
        if created:
            gl_account = PoolMasterGLAccount.objects.create(**payload)
        else:
            changed = assign_changed_fields(gl_account, payload)
            if changed:
                gl_account.save()

        if changed:
            resolved_origin_event_id = str(origin_event_id or "").strip() or (
                f"gl_account:{gl_account.id}:{int(gl_account.updated_at.timestamp())}"
            )
            enqueue_canonical_mutation_outbox_intents(
                tenant_id=tenant_id_token,
                entity_type=PoolMasterDataEntityType.GL_ACCOUNT,
                canonical_id=str(gl_account.canonical_id),
                mutation_kind="gl_account_upsert",
                payload={
                    "canonical_id": str(gl_account.canonical_id),
                    "code": str(gl_account.code or ""),
                    "name": str(gl_account.name or ""),
                    "chart_identity": str(gl_account.chart_identity or ""),
                    "config_name": str(gl_account.config_name or ""),
                    "config_version": str(gl_account.config_version or ""),
                    "metadata": dict(gl_account.metadata or {}),
                },
                origin_event_id=resolved_origin_event_id,
                origin_system=origin_system,
            )
    return CanonicalUpsertResult(entity=gl_account, created=created, changed=changed)


def upsert_pool_master_data_tax_profile(
    *,
    tenant_id: str | UUID,
    canonical_id: str,
    vat_rate: Decimal,
    vat_included: bool,
    vat_code: str,
    metadata: Mapping[str, Any] | None = None,
    existing: PoolMasterTaxProfile | None = None,
    origin_system: str = "cc",
    origin_event_id: str = "",
) -> CanonicalUpsertResult:
    tenant_id_token = str(tenant_id)
    canonical_id_token = str(canonical_id)
    payload = {
        "tenant_id": tenant_id_token,
        "canonical_id": canonical_id_token,
        "vat_rate": vat_rate,
        "vat_included": bool(vat_included),
        "vat_code": str(vat_code or ""),
        "metadata": dict(metadata or {}),
    }
    with transaction.atomic():
        tax_profile = existing
        if tax_profile is None:
            tax_profile = PoolMasterTaxProfile.objects.filter(
                tenant_id=tenant_id_token,
                canonical_id=canonical_id_token,
            ).first()
        created = tax_profile is None
        changed = True
        if created:
            tax_profile = PoolMasterTaxProfile.objects.create(**payload)
        else:
            changed = assign_changed_fields(tax_profile, payload)
            if changed:
                tax_profile.save()

        if changed:
            resolved_origin_event_id = str(origin_event_id or "").strip() or (
                f"tax_profile:{tax_profile.id}:{int(tax_profile.updated_at.timestamp())}"
            )
            enqueue_canonical_mutation_outbox_intents(
                tenant_id=tenant_id_token,
                entity_type=PoolMasterDataEntityType.TAX_PROFILE,
                canonical_id=str(tax_profile.canonical_id),
                mutation_kind="tax_profile_upsert",
                payload={
                    "canonical_id": str(tax_profile.canonical_id),
                    "vat_rate": str(tax_profile.vat_rate),
                    "vat_included": bool(tax_profile.vat_included),
                    "vat_code": str(tax_profile.vat_code or ""),
                    "metadata": dict(tax_profile.metadata or {}),
                },
                origin_event_id=resolved_origin_event_id,
                origin_system=origin_system,
            )
    return CanonicalUpsertResult(entity=tax_profile, created=created, changed=changed)


def upsert_pool_master_data_contract(
    *,
    tenant_id: str | UUID,
    canonical_id: str,
    name: str,
    owner_counterparty: PoolMasterParty,
    number: str = "",
    date: object | None = None,
    metadata: Mapping[str, Any] | None = None,
    existing: PoolMasterContract | None = None,
    origin_system: str = "cc",
    origin_event_id: str = "",
) -> CanonicalUpsertResult:
    if not owner_counterparty.is_counterparty:
        raise MasterDataCanonicalUpsertError(
            code="MASTER_DATA_OWNER_COUNTERPARTY_ROLE_INVALID",
            detail="Owner counterparty must have counterparty role.",
        )

    tenant_id_token = str(tenant_id)
    canonical_id_token = str(canonical_id)
    payload = {
        "tenant_id": tenant_id_token,
        "canonical_id": canonical_id_token,
        "name": str(name),
        "owner_counterparty": owner_counterparty,
        "number": str(number or ""),
        "date": date,
        "metadata": dict(metadata or {}),
    }
    with transaction.atomic():
        contract = existing
        if contract is None:
            contract = PoolMasterContract.objects.filter(
                tenant_id=tenant_id_token,
                canonical_id=canonical_id_token,
                owner_counterparty=owner_counterparty,
            ).first()
        created = contract is None
        changed = True
        if created:
            contract = PoolMasterContract.objects.create(**payload)
        else:
            changed = assign_changed_fields(contract, payload)
            if changed:
                contract.save()

        if changed:
            resolved_origin_event_id = str(origin_event_id or "").strip() or (
                f"contract:{contract.id}:{int(contract.updated_at.timestamp())}"
            )
            enqueue_canonical_mutation_outbox_intents(
                tenant_id=tenant_id_token,
                entity_type=PoolMasterDataEntityType.CONTRACT,
                canonical_id=str(contract.canonical_id),
                mutation_kind="contract_upsert",
                payload={
                    "canonical_id": str(contract.canonical_id),
                    "name": str(contract.name or ""),
                    "owner_counterparty_id": str(contract.owner_counterparty_id),
                    "owner_counterparty_canonical_id": str(contract.owner_counterparty.canonical_id),
                    "number": str(contract.number or ""),
                    "date": contract.date.isoformat() if contract.date else "",
                    "metadata": dict(contract.metadata or {}),
                },
                origin_event_id=resolved_origin_event_id,
                origin_system=origin_system,
            )
    return CanonicalUpsertResult(entity=contract, created=created, changed=changed)


def _schedule_outbound_master_data_sync_job_trigger(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    canonical_id: str,
    origin_system: str,
    origin_event_id: str,
) -> None:
    def _trigger_after_commit() -> None:
        try:
            trigger_pool_master_data_outbound_sync_job(
                tenant_id=tenant_id,
                database_id=database_id,
                entity_type=entity_type,
                canonical_id=canonical_id,
                origin_system=origin_system,
                origin_event_id=origin_event_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Master-data outbound sync trigger failed",
                extra={
                    "tenant_id": tenant_id,
                    "database_id": database_id,
                    "entity_type": entity_type,
                    "canonical_id": canonical_id,
                    "origin_system": origin_system,
                    "origin_event_id": origin_event_id,
                    "error": str(exc),
                },
                exc_info=True,
            )

    transaction.on_commit(_trigger_after_commit)
