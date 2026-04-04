from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

import pytest

from apps.intercompany_pools.master_data_errors import MasterDataResolveError
from apps.intercompany_pools.master_data_gate import _extract_requirements_from_document, _parse_master_data_token
from apps.intercompany_pools.master_data_registry import (
    POOL_MASTER_DATA_TOKEN_QUALIFIER_KIND_IB_CATALOG_KIND,
    PoolMasterDataRegistryTokenContract,
    get_pool_master_data_registry_entry,
)


def test_parse_master_data_token_accepts_registry_defined_ib_catalog_qualifier_options() -> None:
    entry = get_pool_master_data_registry_entry("party")
    assert entry is not None
    patched_entry = replace(
        entry,
        token_contract=PoolMasterDataRegistryTokenContract(
            enabled=True,
            qualifier_kind=POOL_MASTER_DATA_TOKEN_QUALIFIER_KIND_IB_CATALOG_KIND,
            qualifier_required=True,
            qualifier_options=("vendor",),
        ),
    )

    with patch(
        "apps.intercompany_pools.master_data_gate.get_pool_master_data_registry_entry",
        return_value=patched_entry,
    ):
        requirement = _parse_master_data_token(
            token="master_data.party.party-001.vendor.ref",
            database_id="db-1",
        )

    assert requirement.entity_type == "party"
    assert requirement.canonical_id == "party-001"
    assert requirement.ib_catalog_kind == "vendor"


def test_parse_master_data_token_rejects_qualifier_outside_registry_options() -> None:
    entry = get_pool_master_data_registry_entry("party")
    assert entry is not None
    patched_entry = replace(
        entry,
        token_contract=PoolMasterDataRegistryTokenContract(
            enabled=True,
            qualifier_kind=POOL_MASTER_DATA_TOKEN_QUALIFIER_KIND_IB_CATALOG_KIND,
            qualifier_required=True,
            qualifier_options=("vendor",),
        ),
    )

    with patch(
        "apps.intercompany_pools.master_data_gate.get_pool_master_data_registry_entry",
        return_value=patched_entry,
    ):
        with pytest.raises(MasterDataResolveError, match="vendor"):
            _parse_master_data_token(
                token="master_data.party.party-001.organization.ref",
                database_id="db-1",
            )


def test_parse_master_data_token_keeps_dotted_canonical_id_for_qualifierless_registry_entries() -> None:
    requirement = _parse_master_data_token(
        token="master_data.item.10.01.ref",
        database_id="db-1",
    )

    assert requirement.entity_type == "item"
    assert requirement.canonical_id == "10.01"
    assert requirement.ib_catalog_kind == ""
    assert requirement.owner_counterparty_canonical_id == ""


def test_extract_requirements_from_document_uses_gl_account_chart_identity_context() -> None:
    requirements = _extract_requirements_from_document(
        document={
            "field_mapping": {
                "DebitAccount": "master_data.gl_account.10.01.ref",
            },
            "table_parts_mapping": {},
            "master_data_token_context": {
                "field_mapping.DebitAccount": {
                    "token": "master_data.gl_account.10.01.ref",
                    "chart_identity": "ChartOfAccounts_Main",
                }
            },
        },
        database_id="db-1",
    )

    assert len(requirements) == 1
    requirement = requirements[0]
    assert requirement.entity_type == "gl_account"
    assert requirement.canonical_id == "10.01"
    assert requirement.mapping_path == "field_mapping.DebitAccount"
    assert requirement.chart_identity == "ChartOfAccounts_Main"


def test_extract_requirements_from_document_rejects_gl_account_without_typed_context() -> None:
    with pytest.raises(MasterDataResolveError, match="typed metadata context"):
        _extract_requirements_from_document(
            document={
                "field_mapping": {
                    "DebitAccount": "master_data.gl_account.10.01.ref",
                },
                "table_parts_mapping": {},
            },
            database_id="db-1",
        )
