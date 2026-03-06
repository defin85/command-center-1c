from __future__ import annotations

import pytest

from apps.intercompany_pools.document_plan_artifact_contract import (
    DOCUMENT_PLAN_ARTIFACT_VERSION,
    POOL_DOCUMENT_PLAN_ARTIFACT_INVALID,
    build_publication_payload_from_document_plan_artifact,
    validate_document_plan_artifact_v1,
)


def _build_artifact() -> dict[str, object]:
    return {
        "version": DOCUMENT_PLAN_ARTIFACT_VERSION,
        "run_id": "run-123",
        "distribution_artifact_ref": {
            "version": "distribution_artifact.v1",
            "topology_version_ref": "pool_topology:abc123",
        },
        "topology_version_ref": "pool_topology:abc123",
        "policy_refs": [
            {
                "edge_ref": {
                    "parent_node_id": "parent-1",
                    "child_node_id": "child-1",
                },
                "policy_version": "document_policy.v1",
                "source": "edge",
            }
        ],
        "targets": [
            {
                "database_id": "db-1",
                "chains": [
                    {
                        "chain_id": "sale_chain",
                        "edge_ref": {
                            "parent_node_id": "parent-1",
                            "child_node_id": "child-1",
                        },
                        "policy_source": "edge",
                        "policy_version": "document_policy.v1",
                        "allocation": {"amount": "100.00"},
                        "documents": [
                            {
                                "document_id": "sale",
                                "entity_name": "Document_Sales",
                                "document_role": "sale",
                                "field_mapping": {"Amount": "allocation.amount"},
                                "table_parts_mapping": {},
                                "link_rules": {},
                                "invoice_mode": "optional",
                                "idempotency_key": "doc-plan:abcdef123456",
                            }
                        ],
                    }
                ],
            }
        ],
        "compile_summary": {
            "compiled_edges": 1,
            "targets_count": 1,
            "chains_count": 1,
            "documents_count": 1,
            "compiled_at": "2026-02-19T00:00:00+00:00",
        },
    }


def test_validate_document_plan_artifact_v1_accepts_required_contract_fields() -> None:
    artifact = _build_artifact()

    validated = validate_document_plan_artifact_v1(artifact=artifact)

    assert validated["version"] == DOCUMENT_PLAN_ARTIFACT_VERSION
    assert validated["policy_refs"][0]["policy_version"] == "document_policy.v1"


def test_validate_document_plan_artifact_v1_rejects_missing_required_top_level_field() -> None:
    artifact = _build_artifact()
    artifact.pop("compile_summary")

    with pytest.raises(ValueError, match=POOL_DOCUMENT_PLAN_ARTIFACT_INVALID):
        validate_document_plan_artifact_v1(artifact=artifact)


def test_validate_document_plan_artifact_v1_rejects_missing_document_idempotency_key() -> None:
    artifact = _build_artifact()
    artifact["targets"][0]["chains"][0]["documents"][0]["idempotency_key"] = ""

    with pytest.raises(ValueError, match=POOL_DOCUMENT_PLAN_ARTIFACT_INVALID):
        validate_document_plan_artifact_v1(artifact=artifact)


def test_validate_document_plan_artifact_v1_rejects_negative_compile_summary_counts() -> None:
    artifact = _build_artifact()
    artifact["compile_summary"]["documents_count"] = -1

    with pytest.raises(ValueError, match=POOL_DOCUMENT_PLAN_ARTIFACT_INVALID):
        validate_document_plan_artifact_v1(artifact=artifact)


def test_build_publication_payload_from_document_plan_artifact_ignores_raw_run_input_overrides() -> None:
    artifact = _build_artifact()

    payload = build_publication_payload_from_document_plan_artifact(
        artifact=artifact,
        run_input={
            "entity_name": "Document_Raw_Bypass",
            "documents_by_database": {"db-raw": [{"Amount": "999.00"}]},
            "max_attempts": 3,
            "retry_interval_seconds": 5,
            "external_key_field": "ExternalRunKey",
        },
    )

    assert payload["pool_runtime"]["entity_name"] == "Document_Sales"
    assert payload["pool_runtime"]["documents_by_database"] == {
        "db-1": [{"Amount": "100.00"}]
    }
    assert "db-raw" not in payload["pool_runtime"]["documents_by_database"]
    assert payload["pool_runtime"]["document_chains_by_database"]["db-1"][0]["documents"][0][
        "entity_name"
    ] == "Document_Sales"


def test_build_publication_payload_from_document_plan_artifact_materializes_mapping_and_link_refs() -> None:
    artifact = _build_artifact()
    artifact["targets"][0]["chains"][0]["documents"] = [
        {
            "document_id": "sale",
            "entity_name": "Document_Sales",
            "document_role": "sale",
            "field_mapping": {"Amount": "allocation.amount"},
            "table_parts_mapping": {"Goods": [{"Qty": "allocation.amount"}]},
            "link_rules": {},
            "invoice_mode": "optional",
            "idempotency_key": "doc-plan:sale",
        },
        {
            "document_id": "invoice",
            "entity_name": "Document_Invoice",
            "document_role": "invoice",
            "field_mapping": {"BaseDocument": "sale.ref", "Amount": "allocation.amount"},
            "table_parts_mapping": {},
            "link_rules": {"depends_on": "sale"},
            "invoice_mode": "required",
            "idempotency_key": "doc-plan:invoice",
            "link_to": "sale",
            "resolved_link_refs": {"sale": "sale-ref-123"},
        },
    ]
    artifact["compile_summary"]["documents_count"] = 2

    payload = build_publication_payload_from_document_plan_artifact(artifact=artifact)
    chain = payload["pool_runtime"]["document_chains_by_database"]["db-1"][0]
    sale_payload = chain["documents"][0]["payload"]
    invoice_payload = chain["documents"][1]["payload"]

    assert sale_payload["Amount"] == "100.00"
    assert sale_payload["Goods"] == [{"Qty": "100.00"}]
    assert invoice_payload["Amount"] == "100.00"
    assert invoice_payload["BaseDocument"] == "sale-ref-123"


def test_build_publication_payload_from_document_plan_artifact_does_not_inject_generic_amount() -> None:
    artifact = _build_artifact()
    artifact["targets"][0]["chains"][0]["documents"] = [
        {
            "document_id": "sale",
            "entity_name": "Document_РеализацияТоваровУслуг",
            "document_role": "sale",
            "field_mapping": {
                "ВидОперации": "Услуги",
                "СуммаДокумента": "allocation.amount",
            },
            "table_parts_mapping": {
                "Услуги": [
                    {
                        "Количество": 1,
                        "Цена": "allocation.amount",
                        "Сумма": "allocation.amount",
                    }
                ]
            },
            "link_rules": {},
            "invoice_mode": "optional",
            "idempotency_key": "doc-plan:sale",
        }
    ]

    payload = build_publication_payload_from_document_plan_artifact(artifact=artifact)
    sale_payload = payload["pool_runtime"]["document_chains_by_database"]["db-1"][0]["documents"][0][
        "payload"
    ]

    assert "Amount" not in sale_payload
    assert sale_payload["ВидОперации"] == "Услуги"
    assert sale_payload["СуммаДокумента"] == "100.00"
    assert sale_payload["Услуги"] == [{"Количество": 1, "Цена": "100.00", "Сумма": "100.00"}]
