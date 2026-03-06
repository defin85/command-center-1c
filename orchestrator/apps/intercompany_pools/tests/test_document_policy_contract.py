from __future__ import annotations

import pytest

from apps.intercompany_pools.document_policy_contract import (
    DOCUMENT_POLICY_METADATA_KEY,
    DOCUMENT_POLICY_RESOLUTION_SOURCE_EDGE,
    DOCUMENT_POLICY_RESOLUTION_SOURCE_NONE,
    DOCUMENT_POLICY_RESOLUTION_SOURCE_POOL_DEFAULT,
    DOCUMENT_POLICY_VERSION,
    POOL_DOCUMENT_POLICY_CHAIN_INVALID,
    resolve_document_policy_from_pool_metadata,
    resolve_document_policy_from_edge_metadata,
    resolve_document_policy_with_precedence,
    POOL_DOCUMENT_POLICY_MAPPING_INVALID,
    POOL_DOCUMENT_POLICY_MISSING_REQUIRED_INVOICE,
    validate_document_policy_v1,
)


def _build_policy() -> dict[str, object]:
    return {
        "version": DOCUMENT_POLICY_VERSION,
        "chains": [
            {
                "chain_id": "sale_chain",
                "documents": [
                    {
                        "document_id": "sale",
                        "entity_name": "Document_Sales",
                        "document_role": "sale",
                        "field_mapping": {"Amount": "allocation.amount"},
                        "table_parts_mapping": {"Goods": [{"Qty": "allocation.qty"}]},
                        "link_rules": {},
                    },
                    {
                        "document_id": "invoice",
                        "entity_name": "Document_Invoice",
                        "document_role": "invoice",
                        "field_mapping": {"BaseDocument": "sale.ref"},
                        "table_parts_mapping": {},
                        "link_rules": {"depends_on": "sale"},
                        "link_to": "sale",
                        "invoice_mode": "required",
                    },
                ],
            }
        ],
    }


def test_validate_document_policy_v1_accepts_versioned_chain_contract() -> None:
    policy = _build_policy()
    policy["completeness_profiles"] = {
        "minimal_documents_full_payload": {
            "entities": {
                "Document_Sales": {
                    "required_fields": ["Amount"],
                    "required_table_parts": {
                        "Goods": {
                            "min_rows": 1,
                            "required_fields": ["Qty"],
                        }
                    },
                }
            }
        }
    }

    payload = validate_document_policy_v1(policy=policy)

    assert payload["version"] == DOCUMENT_POLICY_VERSION
    chain = payload["chains"][0]
    assert chain["chain_id"] == "sale_chain"
    assert chain["documents"][0]["invoice_mode"] == "optional"
    assert chain["documents"][1]["invoice_mode"] == "required"
    assert payload["completeness_profiles"]["minimal_documents_full_payload"]["entities"][
        "Document_Sales"
    ] == {
        "required_fields": ["Amount"],
        "required_table_parts": {
            "Goods": {
                "min_rows": 1,
                "required_fields": ["Qty"],
            }
        },
    }


def test_validate_document_policy_v1_rejects_invalid_invoice_mode() -> None:
    policy = _build_policy()
    policy["chains"][0]["documents"][1]["invoice_mode"] = "always"

    with pytest.raises(ValueError, match=POOL_DOCUMENT_POLICY_CHAIN_INVALID):
        validate_document_policy_v1(policy=policy)


def test_validate_document_policy_v1_rejects_duplicate_chain_id() -> None:
    policy = _build_policy()
    policy["chains"].append(
        {
            "chain_id": "sale_chain",
            "documents": [
                {
                    "document_id": "purchase",
                    "entity_name": "Document_Purchase",
                    "document_role": "purchase",
                }
            ],
        }
    )

    with pytest.raises(ValueError, match=POOL_DOCUMENT_POLICY_CHAIN_INVALID):
        validate_document_policy_v1(policy=policy)


def test_validate_document_policy_v1_rejects_non_object_mappings() -> None:
    policy = _build_policy()
    policy["chains"][0]["documents"][0]["field_mapping"] = []

    with pytest.raises(ValueError, match=POOL_DOCUMENT_POLICY_MAPPING_INVALID):
        validate_document_policy_v1(policy=policy)


def test_validate_document_policy_v1_rejects_invalid_completeness_profile_shape() -> None:
    policy = _build_policy()
    policy["completeness_profiles"] = {
        "minimal_documents_full_payload": {
            "entities": {
                "Document_Sales": {
                    "required_fields": "Amount",
                }
            }
        }
    }

    with pytest.raises(ValueError, match=POOL_DOCUMENT_POLICY_MAPPING_INVALID):
        validate_document_policy_v1(policy=policy)


def test_validate_document_policy_v1_rejects_required_invoice_without_invoice_document() -> None:
    policy = _build_policy()
    policy["chains"][0]["documents"] = [
        {
            "document_id": "sale",
            "entity_name": "Document_Sales",
            "document_role": "sale",
            "field_mapping": {"Amount": "allocation.amount"},
            "table_parts_mapping": {},
            "link_rules": {},
            "invoice_mode": "required",
        }
    ]

    with pytest.raises(ValueError, match=POOL_DOCUMENT_POLICY_MISSING_REQUIRED_INVOICE):
        validate_document_policy_v1(policy=policy)


def test_resolve_document_policy_from_edge_metadata_returns_none_when_missing() -> None:
    assert resolve_document_policy_from_edge_metadata(metadata={"other": 1}) is None


def test_resolve_document_policy_from_edge_metadata_validates_contract() -> None:
    policy = _build_policy()

    resolved = resolve_document_policy_from_edge_metadata(
        metadata={DOCUMENT_POLICY_METADATA_KEY: policy}
    )

    assert resolved is not None
    assert resolved["version"] == DOCUMENT_POLICY_VERSION


def test_resolve_document_policy_from_pool_metadata_returns_none_when_missing() -> None:
    assert resolve_document_policy_from_pool_metadata(metadata={"other": 1}) is None


def test_resolve_document_policy_with_precedence_prefers_edge_metadata() -> None:
    edge_policy = _build_policy()
    edge_policy["chains"][0]["chain_id"] = "edge_chain"
    pool_policy = _build_policy()
    pool_policy["chains"][0]["chain_id"] = "pool_default_chain"

    resolved, source = resolve_document_policy_with_precedence(
        edge_metadata={DOCUMENT_POLICY_METADATA_KEY: edge_policy},
        pool_metadata={DOCUMENT_POLICY_METADATA_KEY: pool_policy},
    )

    assert source == DOCUMENT_POLICY_RESOLUTION_SOURCE_EDGE
    assert resolved is not None
    assert resolved["chains"][0]["chain_id"] == "edge_chain"


def test_resolve_document_policy_with_precedence_falls_back_to_pool_default() -> None:
    pool_policy = _build_policy()
    pool_policy["chains"][0]["chain_id"] = "pool_default_chain"

    resolved, source = resolve_document_policy_with_precedence(
        edge_metadata={},
        pool_metadata={DOCUMENT_POLICY_METADATA_KEY: pool_policy},
    )

    assert source == DOCUMENT_POLICY_RESOLUTION_SOURCE_POOL_DEFAULT
    assert resolved is not None
    assert resolved["chains"][0]["chain_id"] == "pool_default_chain"


def test_resolve_document_policy_with_precedence_returns_none_when_policy_is_missing() -> None:
    resolved, source = resolve_document_policy_with_precedence(
        edge_metadata={},
        pool_metadata={},
    )

    assert resolved is None
    assert source == DOCUMENT_POLICY_RESOLUTION_SOURCE_NONE


def test_resolve_document_policy_with_precedence_rejects_invalid_edge_policy_without_fallback() -> None:
    edge_policy = _build_policy()
    edge_policy["chains"][0]["documents"][1]["invoice_mode"] = "always"
    pool_policy = _build_policy()

    with pytest.raises(ValueError, match=POOL_DOCUMENT_POLICY_CHAIN_INVALID):
        resolve_document_policy_with_precedence(
            edge_metadata={DOCUMENT_POLICY_METADATA_KEY: edge_policy},
            pool_metadata={DOCUMENT_POLICY_METADATA_KEY: pool_policy},
        )
