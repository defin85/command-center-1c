from __future__ import annotations

from dataclasses import dataclass
from typing import Any


POOL_MASTER_DATA_REGISTRY_CONTRACT_VERSION = 1
POOL_MASTER_DATA_REGISTRY_CONTRACT = "pool_master_data_registry.v1"

POOL_MASTER_DATA_ENTRY_KIND_CANONICAL = "canonical"
POOL_MASTER_DATA_ENTRY_KIND_BOOTSTRAP_HELPER = "bootstrap_helper"

POOL_MASTER_DATA_CAPABILITY_DIRECT_BINDING = "direct_binding"
POOL_MASTER_DATA_CAPABILITY_TOKEN_EXPOSURE = "token_exposure"
POOL_MASTER_DATA_CAPABILITY_BOOTSTRAP_IMPORT = "bootstrap_import"
POOL_MASTER_DATA_CAPABILITY_OUTBOX_FANOUT = "outbox_fanout"
POOL_MASTER_DATA_CAPABILITY_SYNC_OUTBOUND = "sync_outbound"
POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND = "sync_inbound"
POOL_MASTER_DATA_CAPABILITY_SYNC_RECONCILE = "sync_reconcile"
POOL_MASTER_DATA_CAPABILITY_CROSS_INFOBASE_DEDUPE = "cross_infobase_dedupe"

POOL_MASTER_DATA_CAPABILITIES: tuple[str, ...] = (
    POOL_MASTER_DATA_CAPABILITY_DIRECT_BINDING,
    POOL_MASTER_DATA_CAPABILITY_TOKEN_EXPOSURE,
    POOL_MASTER_DATA_CAPABILITY_BOOTSTRAP_IMPORT,
    POOL_MASTER_DATA_CAPABILITY_OUTBOX_FANOUT,
    POOL_MASTER_DATA_CAPABILITY_SYNC_OUTBOUND,
    POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND,
    POOL_MASTER_DATA_CAPABILITY_SYNC_RECONCILE,
    POOL_MASTER_DATA_CAPABILITY_CROSS_INFOBASE_DEDUPE,
)

POOL_MASTER_DATA_TOKEN_QUALIFIER_KIND_NONE = "none"
POOL_MASTER_DATA_TOKEN_QUALIFIER_KIND_IB_CATALOG_KIND = "ib_catalog_kind"
POOL_MASTER_DATA_TOKEN_QUALIFIER_KIND_OWNER_COUNTERPARTY_CANONICAL_ID = "owner_counterparty_canonical_id"


@dataclass(frozen=True)
class PoolMasterDataRegistryTokenContract:
    enabled: bool
    qualifier_kind: str = POOL_MASTER_DATA_TOKEN_QUALIFIER_KIND_NONE
    qualifier_required: bool = False
    qualifier_options: tuple[str, ...] = ()


@dataclass(frozen=True)
class PoolMasterDataRegistryBootstrapContract:
    enabled: bool
    dependency_order: int | None = None


@dataclass(frozen=True)
class PoolMasterDataRegistryDedupeContract:
    enabled: bool
    rollout_eligible: bool = False
    identity_signals: tuple[str, ...] = ()
    normalization_rules: tuple[str, ...] = ()
    survivor_precedence: tuple[str, ...] = ()
    review_required_conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class PoolMasterDataRegistryEntry:
    entity_type: str
    label: str
    kind: str
    display_order: int
    binding_scope_fields: tuple[str, ...]
    capabilities: frozenset[str]
    token_contract: PoolMasterDataRegistryTokenContract
    bootstrap_contract: PoolMasterDataRegistryBootstrapContract
    dedupe_contract: PoolMasterDataRegistryDedupeContract
    runtime_consumers: tuple[str, ...]


def _entry(
    *,
    entity_type: str,
    label: str,
    kind: str,
    display_order: int,
    binding_scope_fields: tuple[str, ...],
    capabilities: tuple[str, ...],
    token_contract: PoolMasterDataRegistryTokenContract,
    bootstrap_contract: PoolMasterDataRegistryBootstrapContract,
    dedupe_contract: PoolMasterDataRegistryDedupeContract,
    runtime_consumers: tuple[str, ...],
) -> PoolMasterDataRegistryEntry:
    return PoolMasterDataRegistryEntry(
        entity_type=str(entity_type or "").strip().lower(),
        label=str(label or "").strip(),
        kind=str(kind or "").strip(),
        display_order=int(display_order),
        binding_scope_fields=tuple(str(field).strip() for field in binding_scope_fields),
        capabilities=frozenset(str(capability).strip() for capability in capabilities),
        token_contract=token_contract,
        bootstrap_contract=bootstrap_contract,
        dedupe_contract=dedupe_contract,
        runtime_consumers=tuple(str(item).strip() for item in runtime_consumers),
    )


_POOL_MASTER_DATA_REGISTRY_ENTRIES: tuple[PoolMasterDataRegistryEntry, ...] = (
    _entry(
        entity_type="party",
        label="Party",
        kind=POOL_MASTER_DATA_ENTRY_KIND_CANONICAL,
        display_order=10,
        binding_scope_fields=("canonical_id", "database_id", "ib_catalog_kind"),
        capabilities=(
            POOL_MASTER_DATA_CAPABILITY_DIRECT_BINDING,
            POOL_MASTER_DATA_CAPABILITY_TOKEN_EXPOSURE,
            POOL_MASTER_DATA_CAPABILITY_BOOTSTRAP_IMPORT,
            POOL_MASTER_DATA_CAPABILITY_OUTBOX_FANOUT,
            POOL_MASTER_DATA_CAPABILITY_SYNC_OUTBOUND,
            POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND,
            POOL_MASTER_DATA_CAPABILITY_SYNC_RECONCILE,
            POOL_MASTER_DATA_CAPABILITY_CROSS_INFOBASE_DEDUPE,
        ),
        token_contract=PoolMasterDataRegistryTokenContract(
            enabled=True,
            qualifier_kind=POOL_MASTER_DATA_TOKEN_QUALIFIER_KIND_IB_CATALOG_KIND,
            qualifier_required=True,
            qualifier_options=("organization", "counterparty"),
        ),
        bootstrap_contract=PoolMasterDataRegistryBootstrapContract(enabled=True, dependency_order=10),
        dedupe_contract=PoolMasterDataRegistryDedupeContract(
            enabled=True,
            rollout_eligible=True,
            identity_signals=("inn", "kpp", "name"),
            normalization_rules=("trim", "collapse_spaces", "name_slug", "digits_only:inn", "digits_only:kpp"),
            survivor_precedence=("existing_manual_canonical", "existing_cluster_canonical", "first_resolved_source"),
            review_required_conditions=(
                "missing_identity_signals",
                "name_conflict",
                "role_conflict",
                "multiple_active_clusters",
            ),
        ),
        runtime_consumers=("bindings", "bootstrap_import", "sync", "token_catalog", "token_parser"),
    ),
    _entry(
        entity_type="item",
        label="Item",
        kind=POOL_MASTER_DATA_ENTRY_KIND_CANONICAL,
        display_order=20,
        binding_scope_fields=("canonical_id", "database_id"),
        capabilities=(
            POOL_MASTER_DATA_CAPABILITY_DIRECT_BINDING,
            POOL_MASTER_DATA_CAPABILITY_TOKEN_EXPOSURE,
            POOL_MASTER_DATA_CAPABILITY_BOOTSTRAP_IMPORT,
            POOL_MASTER_DATA_CAPABILITY_OUTBOX_FANOUT,
            POOL_MASTER_DATA_CAPABILITY_SYNC_OUTBOUND,
            POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND,
            POOL_MASTER_DATA_CAPABILITY_SYNC_RECONCILE,
            POOL_MASTER_DATA_CAPABILITY_CROSS_INFOBASE_DEDUPE,
        ),
        token_contract=PoolMasterDataRegistryTokenContract(enabled=True),
        bootstrap_contract=PoolMasterDataRegistryBootstrapContract(enabled=True, dependency_order=20),
        dedupe_contract=PoolMasterDataRegistryDedupeContract(
            enabled=True,
            rollout_eligible=True,
            identity_signals=("sku", "unit", "name"),
            normalization_rules=("trim", "collapse_spaces", "name_slug", "upper:sku", "lower:unit"),
            survivor_precedence=("existing_manual_canonical", "existing_cluster_canonical", "first_resolved_source"),
            review_required_conditions=("missing_identity_signals", "unit_conflict", "name_conflict", "multiple_active_clusters"),
        ),
        runtime_consumers=("bindings", "bootstrap_import", "sync", "token_catalog", "token_parser"),
    ),
    _entry(
        entity_type="contract",
        label="Contract",
        kind=POOL_MASTER_DATA_ENTRY_KIND_CANONICAL,
        display_order=30,
        binding_scope_fields=("canonical_id", "database_id", "owner_counterparty_canonical_id"),
        capabilities=(
            POOL_MASTER_DATA_CAPABILITY_DIRECT_BINDING,
            POOL_MASTER_DATA_CAPABILITY_TOKEN_EXPOSURE,
            POOL_MASTER_DATA_CAPABILITY_BOOTSTRAP_IMPORT,
            POOL_MASTER_DATA_CAPABILITY_OUTBOX_FANOUT,
            POOL_MASTER_DATA_CAPABILITY_SYNC_OUTBOUND,
            POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND,
            POOL_MASTER_DATA_CAPABILITY_SYNC_RECONCILE,
            POOL_MASTER_DATA_CAPABILITY_CROSS_INFOBASE_DEDUPE,
        ),
        token_contract=PoolMasterDataRegistryTokenContract(
            enabled=True,
            qualifier_kind=POOL_MASTER_DATA_TOKEN_QUALIFIER_KIND_OWNER_COUNTERPARTY_CANONICAL_ID,
            qualifier_required=True,
        ),
        bootstrap_contract=PoolMasterDataRegistryBootstrapContract(enabled=True, dependency_order=40),
        dedupe_contract=PoolMasterDataRegistryDedupeContract(
            enabled=True,
            rollout_eligible=True,
            identity_signals=("owner_counterparty_canonical_id", "number", "date", "name"),
            normalization_rules=("trim", "collapse_spaces", "name_slug", "upper:number", "iso_date:date"),
            survivor_precedence=("existing_manual_canonical", "existing_cluster_canonical", "first_resolved_source"),
            review_required_conditions=(
                "owner_scope_conflict",
                "number_conflict",
                "date_conflict",
                "multiple_active_clusters",
            ),
        ),
        runtime_consumers=("bindings", "bootstrap_import", "sync", "token_catalog", "token_parser"),
    ),
    _entry(
        entity_type="tax_profile",
        label="Tax Profile",
        kind=POOL_MASTER_DATA_ENTRY_KIND_CANONICAL,
        display_order=40,
        binding_scope_fields=("canonical_id", "database_id"),
        capabilities=(
            POOL_MASTER_DATA_CAPABILITY_DIRECT_BINDING,
            POOL_MASTER_DATA_CAPABILITY_TOKEN_EXPOSURE,
            POOL_MASTER_DATA_CAPABILITY_BOOTSTRAP_IMPORT,
            POOL_MASTER_DATA_CAPABILITY_OUTBOX_FANOUT,
            POOL_MASTER_DATA_CAPABILITY_SYNC_OUTBOUND,
            POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND,
            POOL_MASTER_DATA_CAPABILITY_SYNC_RECONCILE,
            POOL_MASTER_DATA_CAPABILITY_CROSS_INFOBASE_DEDUPE,
        ),
        token_contract=PoolMasterDataRegistryTokenContract(enabled=True),
        bootstrap_contract=PoolMasterDataRegistryBootstrapContract(enabled=True, dependency_order=30),
        dedupe_contract=PoolMasterDataRegistryDedupeContract(
            enabled=True,
            rollout_eligible=True,
            identity_signals=("vat_code", "vat_rate", "vat_included"),
            normalization_rules=("trim", "upper:vat_code", "decimal:vat_rate", "bool:vat_included"),
            survivor_precedence=("existing_manual_canonical", "existing_cluster_canonical", "first_resolved_source"),
            review_required_conditions=("structural_conflict", "multiple_active_clusters"),
        ),
        runtime_consumers=("bindings", "bootstrap_import", "sync", "token_catalog", "token_parser"),
    ),
    _entry(
        entity_type="gl_account",
        label="GL Account",
        kind=POOL_MASTER_DATA_ENTRY_KIND_CANONICAL,
        display_order=45,
        binding_scope_fields=("canonical_id", "database_id", "chart_identity"),
        capabilities=(
            POOL_MASTER_DATA_CAPABILITY_DIRECT_BINDING,
            POOL_MASTER_DATA_CAPABILITY_TOKEN_EXPOSURE,
            POOL_MASTER_DATA_CAPABILITY_BOOTSTRAP_IMPORT,
            POOL_MASTER_DATA_CAPABILITY_CROSS_INFOBASE_DEDUPE,
        ),
        token_contract=PoolMasterDataRegistryTokenContract(enabled=True),
        bootstrap_contract=PoolMasterDataRegistryBootstrapContract(enabled=True, dependency_order=35),
        dedupe_contract=PoolMasterDataRegistryDedupeContract(
            enabled=True,
            rollout_eligible=True,
            identity_signals=("chart_identity", "code", "name"),
            normalization_rules=("trim", "collapse_spaces", "name_slug", "upper:code", "lower:chart_identity"),
            survivor_precedence=("existing_manual_canonical", "existing_cluster_canonical", "first_resolved_source"),
            review_required_conditions=("chart_conflict", "name_conflict", "multiple_active_clusters"),
        ),
        runtime_consumers=("bindings", "bootstrap_import", "token_catalog", "token_parser"),
    ),
    _entry(
        entity_type="gl_account_set",
        label="GL Account Set",
        kind=POOL_MASTER_DATA_ENTRY_KIND_CANONICAL,
        display_order=46,
        binding_scope_fields=(),
        capabilities=(),
        token_contract=PoolMasterDataRegistryTokenContract(enabled=False),
        bootstrap_contract=PoolMasterDataRegistryBootstrapContract(enabled=False, dependency_order=None),
        dedupe_contract=PoolMasterDataRegistryDedupeContract(enabled=False, rollout_eligible=False),
        runtime_consumers=("profile_store", "revision_catalog"),
    ),
    _entry(
        entity_type="binding",
        label="Binding",
        kind=POOL_MASTER_DATA_ENTRY_KIND_BOOTSTRAP_HELPER,
        display_order=60,
        binding_scope_fields=(),
        capabilities=(POOL_MASTER_DATA_CAPABILITY_BOOTSTRAP_IMPORT,),
        token_contract=PoolMasterDataRegistryTokenContract(enabled=False),
        bootstrap_contract=PoolMasterDataRegistryBootstrapContract(enabled=True, dependency_order=50),
        dedupe_contract=PoolMasterDataRegistryDedupeContract(enabled=False, rollout_eligible=False),
        runtime_consumers=("bootstrap_import",),
    ),
)

_POOL_MASTER_DATA_REGISTRY_LOOKUP = {
    entry.entity_type: entry for entry in _POOL_MASTER_DATA_REGISTRY_ENTRIES
}


def list_pool_master_data_registry_entries(
    *,
    include_bootstrap_helpers: bool = False,
    capability: str | None = None,
) -> tuple[PoolMasterDataRegistryEntry, ...]:
    items = []
    for entry in _POOL_MASTER_DATA_REGISTRY_ENTRIES:
        if entry.kind != POOL_MASTER_DATA_ENTRY_KIND_CANONICAL and not include_bootstrap_helpers:
            continue
        if capability and capability not in entry.capabilities:
            continue
        items.append(entry)
    return tuple(items)


def get_pool_master_data_registry_entry(
    entity_type: str,
    *,
    include_bootstrap_helpers: bool = False,
) -> PoolMasterDataRegistryEntry | None:
    normalized = str(entity_type or "").strip().lower()
    entry = _POOL_MASTER_DATA_REGISTRY_LOOKUP.get(normalized)
    if entry is None:
        return None
    if entry.kind != POOL_MASTER_DATA_ENTRY_KIND_CANONICAL and not include_bootstrap_helpers:
        return None
    return entry


def supports_pool_master_data_capability(
    *,
    entity_type: str,
    capability: str,
    include_bootstrap_helpers: bool = False,
) -> bool:
    entry = get_pool_master_data_registry_entry(
        entity_type,
        include_bootstrap_helpers=include_bootstrap_helpers,
    )
    if entry is None:
        return False
    return str(capability or "").strip() in entry.capabilities


def normalize_pool_master_data_entity_type(entity_type: str) -> str:
    normalized = str(entity_type or "").strip().lower()
    entry = get_pool_master_data_registry_entry(normalized)
    if entry is None:
        raise ValueError(f"Unsupported master-data entity_type '{entity_type}'")
    return normalized


def normalize_pool_master_data_bootstrap_entity_type(entity_type: str) -> str:
    normalized = str(entity_type or "").strip().lower()
    entry = get_pool_master_data_registry_entry(
        normalized,
        include_bootstrap_helpers=True,
    )
    if entry is None or POOL_MASTER_DATA_CAPABILITY_BOOTSTRAP_IMPORT not in entry.capabilities:
        raise ValueError(f"Unsupported bootstrap entity_type '{entity_type}'")
    return normalized


def get_pool_master_data_entity_types(
    *,
    capability: str | None = None,
) -> tuple[str, ...]:
    return tuple(
        entry.entity_type
        for entry in list_pool_master_data_registry_entries(capability=capability)
    )


def get_pool_master_data_entity_types_for_capabilities(
    *capabilities: str,
) -> tuple[str, ...]:
    normalized = {str(capability or "").strip() for capability in capabilities if str(capability or "").strip()}
    return tuple(
        entry.entity_type
        for entry in list_pool_master_data_registry_entries()
        if not normalized or any(capability in entry.capabilities for capability in normalized)
    )


def get_pool_master_data_bootstrap_entity_types() -> tuple[str, ...]:
    entries = list(
        list_pool_master_data_registry_entries(
            include_bootstrap_helpers=True,
            capability=POOL_MASTER_DATA_CAPABILITY_BOOTSTRAP_IMPORT,
        )
    )
    entries.sort(
        key=lambda entry: (
            entry.bootstrap_contract.dependency_order
            if entry.bootstrap_contract.dependency_order is not None
            else 10_000,
            entry.display_order,
        )
    )
    return tuple(entry.entity_type for entry in entries)


def serialize_pool_master_data_registry_entry(
    entry: PoolMasterDataRegistryEntry,
) -> dict[str, Any]:
    return {
        "entity_type": entry.entity_type,
        "label": entry.label,
        "kind": entry.kind,
        "display_order": entry.display_order,
        "binding_scope_fields": list(entry.binding_scope_fields),
        "capabilities": {
            capability: capability in entry.capabilities
            for capability in POOL_MASTER_DATA_CAPABILITIES
        },
        "token_contract": {
            "enabled": bool(entry.token_contract.enabled),
            "qualifier_kind": entry.token_contract.qualifier_kind,
            "qualifier_required": bool(entry.token_contract.qualifier_required),
            "qualifier_options": list(entry.token_contract.qualifier_options),
        },
        "bootstrap_contract": {
            "enabled": bool(entry.bootstrap_contract.enabled),
            "dependency_order": entry.bootstrap_contract.dependency_order,
        },
        "dedupe_contract": {
            "enabled": bool(entry.dedupe_contract.enabled),
            "rollout_eligible": bool(entry.dedupe_contract.rollout_eligible),
            "identity_signals": list(entry.dedupe_contract.identity_signals),
            "normalization_rules": list(entry.dedupe_contract.normalization_rules),
            "survivor_precedence": list(entry.dedupe_contract.survivor_precedence),
            "review_required_conditions": list(entry.dedupe_contract.review_required_conditions),
        },
        "runtime_consumers": list(entry.runtime_consumers),
    }


def inspect_pool_master_data_registry() -> dict[str, Any]:
    entries = [
        serialize_pool_master_data_registry_entry(entry)
        for entry in list_pool_master_data_registry_entries(include_bootstrap_helpers=True)
    ]
    return {
        "contract_version": POOL_MASTER_DATA_REGISTRY_CONTRACT,
        "entries": entries,
        "count": len(entries),
    }
