from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.ccpool_traceability import (
    inject_ccpool_traceability_comment,
    parse_ccpool_traceability_marker,
)
from apps.intercompany_pools.document_plan_artifact_contract import (
    DOCUMENT_PLAN_ARTIFACT_VERSION,
    POOL_DOCUMENT_PLAN_ARTIFACT_INVALID,
    build_publication_payload_from_document_plan_artifact,
    compile_document_plan_artifact_v1,
    validate_document_plan_artifact_v1,
    validate_compiled_document_policy_slots_snapshot,
)
from apps.intercompany_pools.document_policy_contract import (
    DOCUMENT_POLICY_METADATA_KEY,
    DOCUMENT_POLICY_VERSION,
)
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolBatch,
    PoolBatchKind,
    PoolBatchSourceType,
    PoolEdgeVersion,
    PoolMasterParty,
    PoolNodeVersion,
    PoolODataMetadataCatalogSnapshot,
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
                "slot_key": "document_policy",
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


def _build_document_policy(
    *,
    chain_id: str,
    document_id: str,
    entity_name: str,
    field_mapping: dict[str, object] | None = None,
) -> dict[str, object]:
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
                        "field_mapping": (
                            dict(field_mapping)
                            if isinstance(field_mapping, dict)
                            else {"Amount": "allocation.amount"}
                        ),
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


def _create_compile_fixture(
    *,
    slot_keys: list[str | None],
    batch_kind: str | None = None,
) -> dict[str, object]:
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
    batch = None
    if batch_kind is not None:
        batch = PoolBatch.objects.create(
            tenant=tenant,
            pool=pool,
            batch_kind=batch_kind,
            source_type=PoolBatchSourceType.MANUAL,
            start_organization=root_org,
            run=run,
            period_start=run.period_start,
            period_end=run.period_end,
            source_reference=f"batch-{uuid4().hex[:8]}",
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
        "root_org": root_org,
        "batch": batch,
    }


def test_validate_document_plan_artifact_v1_accepts_required_contract_fields() -> None:
    artifact = _build_artifact()

    validated = validate_document_plan_artifact_v1(artifact=artifact)

    assert validated["version"] == DOCUMENT_PLAN_ARTIFACT_VERSION
    assert validated["policy_refs"][0]["slot_key"] == "document_policy"
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

    assert sale_payload["Amount"] == pytest.approx(100.0)
    assert isinstance(sale_payload["Amount"], (int, float))
    assert sale_payload["Goods"] == [{"Qty": pytest.approx(100.0)}]
    assert isinstance(sale_payload["Goods"][0]["Qty"], (int, float))
    assert invoice_payload["Amount"] == pytest.approx(100.0)
    assert isinstance(invoice_payload["Amount"], (int, float))
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
    assert sale_payload["СуммаДокумента"] == pytest.approx(100.0)
    assert isinstance(sale_payload["СуммаДокумента"], (int, float))
    assert sale_payload["Услуги"] == [{"Количество": 1, "Цена": pytest.approx(100.0), "Сумма": pytest.approx(100.0)}]
    assert isinstance(sale_payload["Услуги"][0]["Цена"], (int, float))
    assert isinstance(sale_payload["Услуги"][0]["Сумма"], (int, float))


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
    assert sale_payload["Услуги"] == [{"Содержание": "", "Сумма": pytest.approx(100.0)}]
    assert isinstance(sale_payload["Услуги"][0]["Сумма"], (int, float))


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

    assert sale_payload["СуммаДокумента"] == pytest.approx(100.0)
    assert isinstance(sale_payload["СуммаДокумента"], (int, float))
    assert sale_payload["СуммаНДСДокумента"] == pytest.approx(16.67)
    assert isinstance(sale_payload["СуммаНДСДокумента"], (int, float))
    assert sale_payload["Услуги"] == [{"Сумма": pytest.approx(100.0), "СуммаНДС": pytest.approx(16.67)}]
    assert isinstance(sale_payload["Услуги"][0]["Сумма"], (int, float))
    assert isinstance(sale_payload["Услуги"][0]["СуммаНДС"], (int, float))


@pytest.mark.django_db
def test_compile_document_plan_artifact_persists_gl_account_token_context_into_publication_payload() -> None:
    fixture = _create_compile_fixture(slot_keys=["slot.gl-account"])
    database_id = fixture["database_ids"][0]
    database = Database.objects.get(id=database_id)
    PoolODataMetadataCatalogSnapshot.objects.create(
        tenant=fixture["run"].tenant,
        database=database,
        config_name="Accounting Enterprise",
        config_version="3.0.1",
        extensions_fingerprint="",
        metadata_hash="hash-gl-account",
        catalog_version="catalog-v1",
        payload={
            "documents": [
                {
                    "entity_name": "Document_Sales",
                    "display_name": "Sales",
                    "fields": [
                        {
                            "name": "DebitAccount",
                            "type": "StandardODATA.ChartOfAccounts_Хозрасчетный",
                            "nullable": False,
                        },
                    ],
                    "table_parts": [],
                }
            ]
        },
        is_current=True,
    )
    policy = _build_document_policy(
        chain_id="sale_chain",
        document_id="sale",
        entity_name="Document_Sales",
        field_mapping={"DebitAccount": "master_data.gl_account.10.01.ref"},
    )

    artifact = compile_document_plan_artifact_v1(
        run=fixture["run"],
        distribution_artifact=fixture["distribution_artifact"],
        topology=fixture["topology"],
        compiled_document_policy_slots={
            "slot.gl-account": _build_compiled_slot_entry(
                slot_key="slot.gl-account",
                decision_table_id="gl-account-policy",
                decision_revision=1,
                document_policy=policy,
            )
        },
    )

    assert artifact is not None
    compiled_document = artifact["targets"][0]["chains"][0]["documents"][0]
    assert compiled_document["master_data_token_context"] == {
        "field_mapping.DebitAccount": {
            "token": "master_data.gl_account.10.01.ref",
            "chart_identity": "ChartOfAccounts_Хозрасчетный",
        }
    }

    payload = build_publication_payload_from_document_plan_artifact(artifact=artifact)
    published_document = payload["pool_runtime"]["document_chains_by_database"][database_id][0]["documents"][0]
    assert published_document["master_data_token_context"] == compiled_document["master_data_token_context"]


def test_inject_ccpool_traceability_comment_preserves_existing_human_tail() -> None:
    traceability = {
        "pool_id": "11111111-1111-1111-1111-111111111111",
        "run_id": "22222222-2222-2222-2222-222222222222",
        "batch_id": "33333333-3333-3333-3333-333333333333",
        "organization_id": "44444444-4444-4444-4444-444444444444",
        "quarter": "2026Q1",
        "kind": "sale",
    }

    payload = inject_ccpool_traceability_comment(
        payload={
            "Comment": (
                "CCPOOL:v=1;pool=stale;run=-;batch=-;org=44444444-4444-4444-4444-444444444444;"
                "q=2025Q4;kind=receipt||Operator note"
            )
        },
        traceability=traceability,
    )

    assert payload["Comment"] == (
        "CCPOOL:v=1;pool=11111111-1111-1111-1111-111111111111;"
        "run=22222222-2222-2222-2222-222222222222;"
        "batch=33333333-3333-3333-3333-333333333333;"
        "org=44444444-4444-4444-4444-444444444444;q=2026Q1;kind=sale||Operator note"
    )


def test_parse_ccpool_traceability_marker_returns_none_for_missing_pool() -> None:
    assert (
        parse_ccpool_traceability_marker(
            "CCPOOL:v=1;run=-;batch=-;org=44444444-4444-4444-4444-444444444444;q=2026Q1;kind=sale"
        )
        is None
    )


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
    assert {ref["slot_key"] for ref in artifact["policy_refs"]} == {"sale", "purchase"}
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
def test_compile_document_plan_artifact_v1_uses_run_period_start_for_document_date() -> None:
    fixture = _create_compile_fixture(slot_keys=["receipt"])

    artifact = compile_document_plan_artifact_v1(
        run=fixture["run"],
        distribution_artifact=fixture["distribution_artifact"],
        topology=fixture["topology"],
        compiled_document_policy_slots={
            "receipt": _build_compiled_slot_entry(
                slot_key="receipt",
                decision_table_id="receipt-slot",
                decision_revision=7,
                document_policy=_build_document_policy(
                    chain_id="receipt_chain",
                    document_id="receipt",
                    entity_name="Document_ПоступлениеТоваровУслуг",
                    field_mapping={
                        "Date": "2023-10-03T12:00:00",
                        "СуммаДокумента": "allocation.amount",
                    },
                ),
            )
        },
    )

    assert artifact is not None
    payload = build_publication_payload_from_document_plan_artifact(artifact=artifact)
    document_payload = payload["pool_runtime"]["document_chains_by_database"][fixture["database_ids"][0]][0][
        "documents"
    ][0]["payload"]

    assert document_payload["Date"] == "2026-01-01T00:00:00"
    assert document_payload["СуммаДокумента"] == pytest.approx(50.0)


@pytest.mark.django_db
def test_compile_document_plan_artifact_v1_embeds_ccpool_traceability_for_batch_backed_run() -> None:
    fixture = _create_compile_fixture(
        slot_keys=["sale"],
        batch_kind=PoolBatchKind.RECEIPT,
    )

    artifact = compile_document_plan_artifact_v1(
        run=fixture["run"],
        distribution_artifact=fixture["distribution_artifact"],
        topology=fixture["topology"],
        compiled_document_policy_slots={
            "sale": _build_compiled_slot_entry(
                slot_key="sale",
                decision_table_id="sale-slot",
                decision_revision=8,
                document_policy=_build_document_policy(
                    chain_id="sale_chain",
                    document_id="sale",
                    entity_name="Document_РеализацияТоваровУслуг",
                    field_mapping={
                        "Comment": "Operator note",
                        "СуммаДокумента": "allocation.amount",
                    },
                ),
            )
        },
    )

    assert artifact is not None
    document = artifact["targets"][0]["chains"][0]["documents"][0]
    assert document["traceability"] == {
        "pool_id": str(fixture["run"].pool_id),
        "run_id": str(fixture["run"].id),
        "batch_id": str(fixture["batch"].id),
        "organization_id": str(fixture["root_org"].id),
        "quarter": "2026Q1",
        "kind": "sale",
    }

    payload = build_publication_payload_from_document_plan_artifact(artifact=artifact)
    document_payload = payload["pool_runtime"]["document_chains_by_database"][fixture["database_ids"][0]][0][
        "documents"
    ][0]["payload"]

    assert document_payload["Comment"] == (
        f"CCPOOL:v=1;pool={fixture['run'].pool_id};run={fixture['run'].id};"
        f"batch={fixture['batch'].id};org={fixture['root_org'].id};q=2026Q1;kind=sale||Operator note"
    )


@pytest.mark.django_db
def test_compile_document_plan_artifact_v1_rewrites_topology_aliases_per_edge_and_preserves_static_tokens() -> None:
    fixture = _create_compile_fixture(slot_keys=["receipt_leaf", "receipt_leaf"])
    node_models = fixture["topology"]["node_models"]
    root_node = next(
        node
        for node in node_models.values()
        if isinstance(node, PoolNodeVersion) and node.is_root
    )
    child_nodes = sorted(
        (
            node
            for node in node_models.values()
            if isinstance(node, PoolNodeVersion) and not node.is_root
        ),
        key=lambda node: str(node.id),
    )

    root_party = PoolMasterParty.objects.create(
        tenant=fixture["run"].tenant,
        canonical_id="root-party",
        name="Root Party",
        is_our_organization=True,
        is_counterparty=True,
    )
    root_node.organization.master_party = root_party
    root_node.organization.save(update_fields=["master_party", "updated_at"])

    child_canonical_ids: list[str] = []
    for index, child_node in enumerate(child_nodes, start=1):
        canonical_id = f"child-party-{index}"
        child_canonical_ids.append(canonical_id)
        child_party = PoolMasterParty.objects.create(
            tenant=fixture["run"].tenant,
            canonical_id=canonical_id,
            name=f"Child Party {index}",
            is_our_organization=True,
            is_counterparty=True,
        )
        child_node.organization.master_party = child_party
        child_node.organization.save(update_fields=["master_party", "updated_at"])

    policy = _build_document_policy(
        chain_id="receipt_chain",
        document_id="receipt",
        entity_name="Document_ПоступлениеТоваровУслуг",
        field_mapping={
            "Организация_Key": "master_data.party.edge.child.organization.ref",
            "Контрагент_Key": "master_data.party.edge.parent.counterparty.ref",
            "ДоговорКонтрагента_Key": "master_data.contract.osnovnoy.edge.child.ref",
            "Номенклатура_Key": "master_data.item.packing-service.ref",
            "СтавкаНДС_Key": "master_data.tax_profile.vat20.ref",
        },
    )
    policy["chains"][0]["documents"][0]["table_parts_mapping"] = {
        "Услуги": [
            {
                "Номенклатура_Key": "master_data.item.packing-service.ref",
                "СтавкаНДС_Key": "master_data.tax_profile.vat20.ref",
            }
        ]
    }

    artifact = compile_document_plan_artifact_v1(
        run=fixture["run"],
        distribution_artifact=fixture["distribution_artifact"],
        topology=fixture["topology"],
        compiled_document_policy_slots={
            "receipt_leaf": _build_compiled_slot_entry(
                slot_key="receipt_leaf",
                decision_table_id="receipt-slot",
                decision_revision=9,
                document_policy=policy,
            )
        },
    )

    assert artifact is not None
    serialized_artifact = str(artifact)
    assert "master_data.party.edge." not in serialized_artifact
    assert ".edge.parent.ref" not in serialized_artifact
    assert ".edge.child.ref" not in serialized_artifact

    documents = [target["chains"][0]["documents"][0] for target in artifact["targets"]]
    assert {
        document["field_mapping"]["Организация_Key"]
        for document in documents
    } == {
        f"master_data.party.{canonical_id}.organization.ref"
        for canonical_id in child_canonical_ids
    }
    assert {
        document["field_mapping"]["ДоговорКонтрагента_Key"]
        for document in documents
    } == {
        f"master_data.contract.osnovnoy.{canonical_id}.ref"
        for canonical_id in child_canonical_ids
    }
    for document in documents:
        assert document["field_mapping"]["Контрагент_Key"] == "master_data.party.root-party.counterparty.ref"
        assert document["field_mapping"]["Номенклатура_Key"] == "master_data.item.packing-service.ref"
        assert document["field_mapping"]["СтавкаНДС_Key"] == "master_data.tax_profile.vat20.ref"
        assert document["table_parts_mapping"] == {
            "Услуги": [
                {
                    "Номенклатура_Key": "master_data.item.packing-service.ref",
                    "СтавкаНДС_Key": "master_data.tax_profile.vat20.ref",
                }
            ]
        }


@pytest.mark.django_db
def test_compile_document_plan_artifact_v1_fails_closed_on_malformed_topology_alias() -> None:
    fixture = _create_compile_fixture(slot_keys=["sale"])

    with pytest.raises(ValueError, match="POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID"):
        compile_document_plan_artifact_v1(
            run=fixture["run"],
            distribution_artifact=fixture["distribution_artifact"],
            topology=fixture["topology"],
            compiled_document_policy_slots={
                "sale": _build_compiled_slot_entry(
                    slot_key="sale",
                    decision_table_id="sale-slot",
                    decision_revision=5,
                    document_policy=_build_document_policy(
                        chain_id="sale_chain",
                        document_id="sale",
                        entity_name="Document_Sales",
                        field_mapping={
                            "Контрагент_Key": "master_data.party.edge.middle.counterparty.ref"
                        },
                    ),
                )
            },
        )


@pytest.mark.django_db
def test_compile_document_plan_artifact_v1_fails_closed_when_slot_selector_missing() -> None:
    fixture = _create_compile_fixture(slot_keys=[None])

    with pytest.raises(ValueError, match="POOL_DOCUMENT_POLICY_SLOT_SELECTOR_MISSING"):
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
def test_validate_compiled_document_policy_slots_snapshot_uses_output_invalid_code() -> None:
    with pytest.raises(ValueError, match="POOL_DOCUMENT_POLICY_SLOT_OUTPUT_INVALID"):
        validate_compiled_document_policy_slots_snapshot(
            {
                "sale": {
                    "decision_table_id": "sale-slot",
                    "decision_revision": 1,
                    "document_policy": "broken",
                    "document_policy_source": "workflow_binding.decision_table:sale-slot:v1",
                }
            }
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


@pytest.mark.django_db
def test_compile_document_plan_artifact_v1_rejects_legacy_edge_policy_without_slot_resolution() -> None:
    fixture = _create_compile_fixture(slot_keys=[None])
    edge_model = next(iter(fixture["topology"]["edge_models"].values()))
    edge_model.metadata = {
        DOCUMENT_POLICY_METADATA_KEY: _build_document_policy(
            chain_id="legacy_edge_chain",
            document_id="sale",
            entity_name="Document_Sales",
        )
    }

    with pytest.raises(ValueError, match="POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED"):
        compile_document_plan_artifact_v1(
            run=fixture["run"],
            distribution_artifact=fixture["distribution_artifact"],
            topology=fixture["topology"],
        )


@pytest.mark.django_db
def test_compile_document_plan_artifact_v1_rejects_legacy_pool_default_without_slot_resolution() -> None:
    fixture = _create_compile_fixture(slot_keys=[None])
    fixture["run"].pool.metadata = {
        DOCUMENT_POLICY_METADATA_KEY: _build_document_policy(
            chain_id="legacy_pool_chain",
            document_id="sale",
            entity_name="Document_Sales",
        )
    }

    with pytest.raises(ValueError, match="POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED"):
        compile_document_plan_artifact_v1(
            run=fixture["run"],
            distribution_artifact=fixture["distribution_artifact"],
            topology=fixture["topology"],
        )


@pytest.mark.django_db
def test_compile_document_plan_artifact_v1_rejects_legacy_edge_policy_even_with_slot_resolution() -> None:
    fixture = _create_compile_fixture(slot_keys=["sale"])
    edge_model = next(iter(fixture["topology"]["edge_models"].values()))
    edge_model.metadata = {
        "document_policy_key": "sale",
        DOCUMENT_POLICY_METADATA_KEY: _build_document_policy(
            chain_id="legacy_edge_chain",
            document_id="sale",
            entity_name="Document_Sales",
        ),
    }

    with pytest.raises(ValueError, match="POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED"):
        compile_document_plan_artifact_v1(
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
                )
            },
        )


@pytest.mark.django_db
def test_compile_document_plan_artifact_v1_rejects_legacy_pool_default_even_with_slot_resolution() -> None:
    fixture = _create_compile_fixture(slot_keys=["sale"])
    fixture["run"].pool.metadata = {
        DOCUMENT_POLICY_METADATA_KEY: _build_document_policy(
            chain_id="legacy_pool_chain",
            document_id="sale",
            entity_name="Document_Sales",
        )
    }

    with pytest.raises(ValueError, match="POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED"):
        compile_document_plan_artifact_v1(
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
                )
            },
        )
