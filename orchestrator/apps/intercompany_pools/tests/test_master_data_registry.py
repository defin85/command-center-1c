from __future__ import annotations

from apps.intercompany_pools.master_data_registry import (
    POOL_MASTER_DATA_CAPABILITY_BOOTSTRAP_IMPORT,
    POOL_MASTER_DATA_CAPABILITY_DIRECT_BINDING,
    POOL_MASTER_DATA_CAPABILITY_OUTBOX_FANOUT,
    POOL_MASTER_DATA_CAPABILITY_TOKEN_EXPOSURE,
    POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND,
    POOL_MASTER_DATA_CAPABILITY_SYNC_OUTBOUND,
    POOL_MASTER_DATA_CAPABILITY_SYNC_RECONCILE,
    inspect_pool_master_data_registry,
    get_pool_master_data_bootstrap_entity_types,
    get_pool_master_data_entity_types,
    get_pool_master_data_entity_types_for_capabilities,
    get_pool_master_data_registry_entry,
    normalize_pool_master_data_bootstrap_entity_type,
    normalize_pool_master_data_entity_type,
    supports_pool_master_data_capability,
)
from apps.intercompany_pools.models import (
    PoolMasterDataBootstrapImportEntityType,
    PoolMasterDataEntityType,
)


def test_registry_matches_current_enum_compatibility_wrappers() -> None:
    assert get_pool_master_data_entity_types() == tuple(PoolMasterDataEntityType.values)
    assert get_pool_master_data_bootstrap_entity_types() == tuple(PoolMasterDataBootstrapImportEntityType.values)


def test_registry_marks_binding_as_bootstrap_only_helper() -> None:
    entry = get_pool_master_data_registry_entry("binding", include_bootstrap_helpers=True)

    assert entry is not None
    assert entry.kind == "bootstrap_helper"
    assert supports_pool_master_data_capability(
        entity_type="binding",
        capability=POOL_MASTER_DATA_CAPABILITY_BOOTSTRAP_IMPORT,
        include_bootstrap_helpers=True,
    ) is True
    assert supports_pool_master_data_capability(
        entity_type="binding",
        capability=POOL_MASTER_DATA_CAPABILITY_DIRECT_BINDING,
        include_bootstrap_helpers=True,
    ) is False
    assert supports_pool_master_data_capability(
        entity_type="binding",
        capability=POOL_MASTER_DATA_CAPABILITY_TOKEN_EXPOSURE,
        include_bootstrap_helpers=True,
    ) is False
    assert supports_pool_master_data_capability(
        entity_type="binding",
        capability=POOL_MASTER_DATA_CAPABILITY_OUTBOX_FANOUT,
        include_bootstrap_helpers=True,
    ) is False


def test_registry_exposes_sync_capabilities_for_current_canonical_types() -> None:
    assert get_pool_master_data_entity_types_for_capabilities(
        POOL_MASTER_DATA_CAPABILITY_SYNC_OUTBOUND,
        POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND,
        POOL_MASTER_DATA_CAPABILITY_SYNC_RECONCILE,
    ) == (
        PoolMasterDataEntityType.PARTY,
        PoolMasterDataEntityType.ITEM,
        PoolMasterDataEntityType.CONTRACT,
        PoolMasterDataEntityType.TAX_PROFILE,
    )


def test_registry_normalizers_fail_closed_for_unknown_entities() -> None:
    try:
        normalize_pool_master_data_entity_type("unknown")
    except ValueError as exc:
        assert "Unsupported master-data entity_type" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown canonical entity type")

    try:
        normalize_pool_master_data_bootstrap_entity_type("unknown")
    except ValueError as exc:
        assert "Unsupported bootstrap entity_type" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown bootstrap entity type")


def test_registry_inspect_payload_contains_capability_matrix() -> None:
    payload = inspect_pool_master_data_registry()

    assert payload["contract_version"] == "pool_master_data_registry.v1"
    assert payload["count"] == 7
    assert len(payload["entries"]) == 7
    binding_entry = next(item for item in payload["entries"] if item["entity_type"] == "binding")
    assert binding_entry["capabilities"]["bootstrap_import"] is True
    assert binding_entry["capabilities"]["token_exposure"] is False
    party_entry = next(item for item in payload["entries"] if item["entity_type"] == "party")
    assert party_entry["token_contract"]["qualifier_kind"] == "ib_catalog_kind"
    assert party_entry["token_contract"]["qualifier_options"] == ["organization", "counterparty"]
    gl_account_entry = next(item for item in payload["entries"] if item["entity_type"] == "gl_account")
    assert gl_account_entry["binding_scope_fields"] == ["canonical_id", "database_id", "chart_identity"]
    assert gl_account_entry["capabilities"]["direct_binding"] is True
    assert gl_account_entry["capabilities"]["token_exposure"] is True
    assert gl_account_entry["capabilities"]["bootstrap_import"] is True
    assert gl_account_entry["capabilities"]["outbox_fanout"] is False
    assert gl_account_entry["capabilities"]["sync_outbound"] is False
    gl_account_set_entry = next(item for item in payload["entries"] if item["entity_type"] == "gl_account_set")
    assert gl_account_set_entry["binding_scope_fields"] == []
    assert gl_account_set_entry["capabilities"]["direct_binding"] is False
    assert gl_account_set_entry["capabilities"]["bootstrap_import"] is False
