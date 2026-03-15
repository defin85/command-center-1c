from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.document_plan_artifact_contract import (
    DOCUMENT_PLAN_ARTIFACT_VERSION,
    POOL_DOCUMENT_PLAN_ARTIFACT_INVALID,
    compile_document_plan_artifact_v1,
    build_publication_payload_from_document_plan_artifact,
    validate_document_plan_artifact_v1,
)
from apps.intercompany_pools.document_policy_contract import DOCUMENT_POLICY_VERSION
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolEdgeVersion,
    PoolNodeVersion,
    PoolRun,
    PoolRunDirection,
    PoolRunMode,
)
from apps.tenancy.models import Tenant


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


def _build_document_policy(*, chain_id: str, document_id: str, entity_name: str) -> dict[str, object]:
    return {
        "version": DOCUMENT_POLICY_VERSION,
        "chains": [
            {
                "chain_id": chain_id,
                "documents": [
                    {
                        "document_id": document_id,
                        "entity_name": entity_name,
                        "document_role": "base",
                        "field_mapping": {"Amount": "allocation.amount"},
                        "table_parts_mapping": {},
                        "link_rules": {},
                        "invoice_mode": "optional",
                    }
                ],
            }
        ],
    }


def _build_compiled_slot_entry(
    *,
    slot_key: str,
    decision_table_id: str,
    decision_revision: int,
    document_policy: dict[str, object],
) -> dict[str, object]:
    return {
        "decision_table_id": decision_table_id,
        "decision_revision": decision_revision,
        "document_policy_source": (
            f"workflow_binding.decision_table:{decision_table_id}:v{decision_revision}"
        ),
        "document_policy": document_policy,
    }


def _create_compile_fixture(*, slot_keys: list[str | None]) -> dict[str, object]:
    tenant = Tenant.objects.create(slug=f"doc-plan-{uuid4().hex[:8]}", name="Doc Plan")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Document Plan Pool",
    )
    root_org = Organization.objects.create(
        tenant=tenant,
        name="Root Org",
        inn=f"73{uuid4().hex[:10]}",
    )
    root_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=root_org,
        effective_from=date(2026, 1, 1),
        is_root=True,
    )
    run = PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        direction=PoolRunDirection.TOP_DOWN,
        mode=PoolRunMode.SAFE,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        run_input={"starting_amount": "100.00"},
    )

    node_models = {str(root_node.id): root_node}
    edge_models: dict[tuple[str, str], PoolEdgeVersion] = {}
    edge_allocations: list[dict[str, object]] = []
    database_ids: list[str] = []
    for index, slot_key in enumerate(slot_keys):
        database = Database.objects.create(
            tenant=tenant,
            name=f"target-db-{uuid4().hex[:8]}",
            host="localhost",
            odata_url="http://localhost/odata/standard.odata",
            username="admin",
            password="secret",
        )
        database_ids.append(str(database.id))
        child_org = Organization.objects.create(
            tenant=tenant,
            database=database,
            name=f"Child Org {index + 1}",
            inn=f"74{uuid4().hex[:10]}",
        )
        child_node = PoolNodeVersion.objects.create(
            pool=pool,
            organization=child_org,
            effective_from=date(2026, 1, 1),
        )
        node_models[str(child_node.id)] = child_node
        metadata = {}
        if slot_key is not None:
            metadata["document_policy_key"] = slot_key
        edge = PoolEdgeVersion.objects.create(
            pool=pool,
            parent_node=root_node,
            child_node=child_node,
            effective_from=date(2026, 1, 1),
            metadata=metadata,
        )
        edge_key = (str(root_node.id), str(child_node.id))
        edge_models[edge_key] = edge
        edge_allocations.append(
            {
                "parent_node_id": edge_key[0],
                "child_node_id": edge_key[1],
                "amount": "50.00",
            }
        )
    return {
        "run": run,
        "distribution_artifact": {
            "version": "distribution_artifact.v1",
            "topology_version_ref": "pool_topology:test",
            "edge_allocations": edge_allocations,
        },
        "topology": {
            "topology_version_ref": "pool_topology:test",
            "node_models": node_models,
            "edge_models": edge_models,
        },
        "database_ids": database_ids,
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


def test_build_publication_payload_from_document_plan_artifact_preserves_explicit_empty_string_literals() -> None:
    artifact = _build_artifact()
    artifact["targets"][0]["chains"][0]["documents"] = [
        {
            "document_id": "sale",
            "entity_name": "Document_РеализацияТоваровУслуг",
            "document_role": "sale",
            "field_mapping": {
                "АдресДоставки": "",
                "СуммаДокумента": "allocation.amount",
            },
            "table_parts_mapping": {
                "Услуги": [
                    {
                        "Содержание": "",
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

    assert sale_payload["АдресДоставки"] == ""
    assert sale_payload["Услуги"] == [{"Содержание": "", "Сумма": "100.00"}]


def test_build_publication_payload_from_document_plan_artifact_resolves_derived_decimal_values() -> None:
    artifact = _build_artifact()
    artifact["targets"][0]["chains"][0]["documents"] = [
        {
            "document_id": "sale",
            "entity_name": "Document_РеализацияТоваровУслуг",
            "document_role": "sale",
            "field_mapping": {
                "СуммаДокумента": "allocation.amount",
                "СуммаНДСДокумента": {
                    "$derive": {
                        "op": "div",
                        "args": ["allocation.amount", 6],
                        "scale": 2,
                    }
                },
            },
            "table_parts_mapping": {
                "Услуги": [
                    {
                        "Сумма": "allocation.amount",
                        "СуммаНДС": {
                            "$derive": {
                                "op": "div",
                                "args": ["allocation.amount", 6],
                                "scale": 2,
                            }
                        },
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

    assert sale_payload["СуммаДокумента"] == "100.00"
    assert sale_payload["СуммаНДСДокумента"] == "16.67"
    assert sale_payload["Услуги"] == [{"Сумма": "100.00", "СуммаНДС": "16.67"}]


@pytest.mark.django_db
def test_compile_document_plan_artifact_v1_resolves_slot_based_policy_per_edge() -> None:
    fixture = _create_compile_fixture(slot_keys=["sale", "purchase"])

    artifact = compile_document_plan_artifact_v1(
        run=fixture["run"],
        distribution_artifact=fixture["distribution_artifact"],
        topology=fixture["topology"],
        compiled_document_policy_slots={
            "sale": _build_compiled_slot_entry(
                slot_key="sale",
                decision_table_id="sale-slot",
                decision_revision=3,
                document_policy=_build_document_policy(
                    chain_id="sale_chain",
                    document_id="sale",
                    entity_name="Document_Sales",
                ),
            ),
            "purchase": _build_compiled_slot_entry(
                slot_key="purchase",
                decision_table_id="purchase-slot",
                decision_revision=4,
                document_policy=_build_document_policy(
                    chain_id="purchase_chain",
                    document_id="purchase",
                    entity_name="Document_Purchase",
                ),
            ),
        },
    )

    assert artifact is not None
    assert artifact["compile_summary"]["compiled_edges"] == 2
    assert {ref["source"] for ref in artifact["policy_refs"]} == {
        "workflow_binding.decision_table:sale-slot:v3",
        "workflow_binding.decision_table:purchase-slot:v4",
    }
    chains_by_database = {
        str(target["database_id"]): [chain["chain_id"] for chain in target["chains"]]
        for target in artifact["targets"]
    }
    assert chains_by_database == {
        fixture["database_ids"][0]: ["sale_chain"],
        fixture["database_ids"][1]: ["purchase_chain"],
    }


@pytest.mark.django_db
def test_compile_document_plan_artifact_v1_fails_closed_when_slot_selector_missing() -> None:
    fixture = _create_compile_fixture(slot_keys=[None])

    with pytest.raises(ValueError, match="POOL_DOCUMENT_POLICY_SLOT_SELECTOR_REQUIRED"):
        compile_document_plan_artifact_v1(
            run=fixture["run"],
            distribution_artifact=fixture["distribution_artifact"],
            topology=fixture["topology"],
            compiled_document_policy_slots={
                "sale": _build_compiled_slot_entry(
                    slot_key="sale",
                    decision_table_id="sale-slot",
                    decision_revision=1,
                    document_policy=_build_document_policy(
                        chain_id="sale_chain",
                        document_id="sale",
                        entity_name="Document_Sales",
                    ),
                )
            },
        )


@pytest.mark.django_db
def test_compile_document_plan_artifact_v1_fails_closed_when_slot_not_bound() -> None:
    fixture = _create_compile_fixture(slot_keys=["sale", "purchase"])

    with pytest.raises(ValueError, match="POOL_DOCUMENT_POLICY_SLOT_NOT_BOUND"):
        compile_document_plan_artifact_v1(
            run=fixture["run"],
            distribution_artifact=fixture["distribution_artifact"],
            topology=fixture["topology"],
            compiled_document_policy_slots={
                "sale": _build_compiled_slot_entry(
                    slot_key="sale",
                    decision_table_id="sale-slot",
                    decision_revision=1,
                    document_policy=_build_document_policy(
                        chain_id="sale_chain",
                        document_id="sale",
                        entity_name="Document_Sales",
                    ),
                )
            },
        )
