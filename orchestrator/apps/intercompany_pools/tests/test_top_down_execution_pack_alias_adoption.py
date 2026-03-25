from __future__ import annotations

import io
import json
from datetime import date
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.intercompany_pools.binding_profiles_store import create_canonical_binding_profile
from apps.intercompany_pools.models import OrganizationPool, PoolWorkflowBinding
from apps.intercompany_pools.top_down_execution_pack_alias_adoption import (
    TOP_DOWN_EXECUTION_PACK_CODE,
    adopt_top_down_execution_pack_aliases_for_all_tenants,
)
from apps.intercompany_pools.workflow_binding_attachments_store import upsert_pool_workflow_binding_attachment
from apps.templates.workflow.decision_tables import create_decision_table_revision
from apps.templates.workflow.models import DecisionTable
from apps.tenancy.models import Tenant
from apps.intercompany_pools.top_down_execution_pack_alias_adoption import (
    build_top_down_realization_alias_policy,
    build_top_down_receipt_alias_policy,
)


def _build_policy() -> dict[str, object]:
    return {
        "version": "document_policy.v1",
        "chains": [
            {
                "chain_id": "sample",
                "documents": [
                    {
                        "document_id": "doc-1",
                        "entity_name": "Document_Sample",
                        "document_role": "base",
                        "invoice_mode": "optional",
                        "field_mapping": {
                            "Организация_Key": "legacy-org-guid",
                            "Контрагент_Key": "legacy-counterparty-guid",
                            "ДоговорКонтрагента_Key": "legacy-contract-guid",
                            "Номенклатура_Key": "master_data.item.packing-service.ref",
                        },
                        "table_parts_mapping": {
                            "Услуги": [
                                {
                                    "Контрагент_Key": "legacy-line-counterparty-guid",
                                    "ДоговорКонтрагента_Key": "legacy-line-contract-guid",
                                    "Номенклатура_Key": "master_data.item.packing-service.ref",
                                }
                            ]
                        },
                        "link_rules": {},
                    }
                ],
            }
        ],
    }


def _build_decision_policy(
    *,
    chain_id: str,
    organization_ref: str,
    counterparty_ref: str,
    contract_ref: str,
) -> dict[str, object]:
    return {
        "version": "document_policy.v1",
        "chains": [
            {
                "chain_id": chain_id,
                "documents": [
                    {
                        "document_id": "document",
                        "entity_name": "Document_Sample",
                        "document_role": "base",
                        "field_mapping": {
                            "Организация_Key": organization_ref,
                            "Контрагент_Key": counterparty_ref,
                            "ДоговорКонтрагента_Key": contract_ref,
                        },
                        "table_parts_mapping": {
                            "Услуги": [
                                {
                                    "Контрагент_Key": counterparty_ref,
                                    "ДоговорКонтрагента_Key": contract_ref,
                                }
                            ]
                        },
                        "link_rules": {},
                    }
                ],
            }
        ],
    }


def _build_decision_contract(
    *,
    decision_table_id: str,
    chain_id: str,
    organization_ref: str,
    counterparty_ref: str,
    contract_ref: str,
) -> dict[str, object]:
    return {
        "decision_table_id": decision_table_id,
        "decision_key": "document_policy",
        "name": decision_table_id,
        "inputs": [],
        "outputs": [
            {
                "name": "document_policy",
                "value_type": "json",
                "required": True,
            }
        ],
        "rules": [
            {
                "rule_id": f"{decision_table_id}-rule-1",
                "conditions": {},
                "outputs": {
                    "document_policy": _build_decision_policy(
                        chain_id=chain_id,
                        organization_ref=organization_ref,
                        counterparty_ref=counterparty_ref,
                        contract_ref=contract_ref,
                    )
                },
                "priority": 1,
            }
        ],
    }


def _build_binding_profile_revision(
    *,
    sale_decision_table_id: str = "sale-policy",
    receipt_decision_table_id: str = "receipt-policy",
) -> dict[str, object]:
    return {
        "workflow": {
            "workflow_definition_key": "top-down-template",
            "workflow_revision_id": str(uuid4()),
            "workflow_revision": 3,
            "workflow_name": "top_down_execution_pack",
        },
        "decisions": [
            {
                "decision_table_id": sale_decision_table_id,
                "decision_key": "document_policy",
                "slot_key": "sale",
                "decision_revision": 1,
            },
            {
                "decision_table_id": receipt_decision_table_id,
                "decision_key": "document_policy",
                "slot_key": "receipt_internal",
                "decision_revision": 1,
            },
            {
                "decision_table_id": receipt_decision_table_id,
                "decision_key": "document_policy",
                "slot_key": "receipt_leaf",
                "decision_revision": 1,
            },
        ],
        "parameters": {},
        "role_mapping": {},
        "metadata": {},
    }


def _seed_top_down_execution_pack(
    *,
    tenant: Tenant,
    actor,
) -> dict[str, object]:
    suffix = uuid4().hex[:8]
    sale_decision_table_id = f"sale-policy-{suffix}"
    receipt_decision_table_id = f"receipt-policy-{suffix}"
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"{TOP_DOWN_EXECUTION_PACK_CODE}-{suffix}",
        name="Top Down Execution Pack",
    )

    sale_decision = create_decision_table_revision(
        contract=_build_decision_contract(
            decision_table_id=sale_decision_table_id,
            chain_id="sale_chain",
            organization_ref="legacy.sale.organization",
            counterparty_ref="legacy.sale.counterparty",
            contract_ref="legacy.sale.contract",
        ),
        created_by=actor,
    )
    receipt_decision = create_decision_table_revision(
        contract=_build_decision_contract(
            decision_table_id=receipt_decision_table_id,
            chain_id="receipt_chain",
            organization_ref="legacy.receipt.organization",
            counterparty_ref="legacy.receipt.counterparty",
            contract_ref="legacy.receipt.contract",
        ),
        created_by=actor,
    )

    created_profile = create_canonical_binding_profile(
        tenant=tenant,
        binding_profile={
            "code": TOP_DOWN_EXECUTION_PACK_CODE,
            "name": "Top Down Execution Pack",
            "revision": _build_binding_profile_revision(
                sale_decision_table_id=sale_decision_table_id,
                receipt_decision_table_id=receipt_decision_table_id,
            ),
        },
        actor_username=actor.username,
    )
    saved_binding, created = upsert_pool_workflow_binding_attachment(
        pool=pool,
        workflow_binding={
            "binding_profile_revision_id": created_profile["latest_revision"]["binding_profile_revision_id"],
            "selector": {"direction": "top_down", "mode": "safe", "tags": ["baseline"]},
            "effective_from": date(2026, 1, 1).isoformat(),
            "status": "active",
        },
        actor_username=actor.username,
    )

    assert created is True
    return {
        "tenant": tenant,
        "pool": pool,
        "sale_decision": sale_decision,
        "receipt_decision": receipt_decision,
        "binding_profile_id": created_profile["binding_profile_id"],
        "binding_profile_revision_id": created_profile["latest_revision"]["binding_profile_revision_id"],
        "binding": saved_binding,
    }


@pytest.mark.django_db
def test_adopt_top_down_execution_pack_aliases_command_rewrites_policies_and_repins_bindings() -> None:
    tenant = Tenant.objects.create(slug=f"top-down-{uuid4().hex[:8]}", name="Top Down")
    actor = get_user_model().objects.create_user(
        username=f"top-down-actor-{uuid4().hex[:8]}",
        password="testpass123",
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=TOP_DOWN_EXECUTION_PACK_CODE,
        name="Top Down Execution Pack",
    )

    sale_decision = create_decision_table_revision(
        contract=_build_decision_contract(
            decision_table_id="sale-policy",
            chain_id="sale_chain",
            organization_ref="legacy.sale.organization",
            counterparty_ref="legacy.sale.counterparty",
            contract_ref="legacy.sale.contract",
        ),
        created_by=actor,
    )
    receipt_decision = create_decision_table_revision(
        contract=_build_decision_contract(
            decision_table_id="receipt-policy",
            chain_id="receipt_chain",
            organization_ref="legacy.receipt.organization",
            counterparty_ref="legacy.receipt.counterparty",
            contract_ref="legacy.receipt.contract",
        ),
        created_by=actor,
    )

    created_profile = create_canonical_binding_profile(
        tenant=tenant,
        binding_profile={
            "code": TOP_DOWN_EXECUTION_PACK_CODE,
            "name": "Top Down Execution Pack",
            "revision": _build_binding_profile_revision(),
        },
        actor_username=actor.username,
    )
    binding_profile_id = created_profile["binding_profile_id"]
    binding_profile_revision_id = created_profile["latest_revision"]["binding_profile_revision_id"]

    saved_binding, created = upsert_pool_workflow_binding_attachment(
        pool=pool,
        workflow_binding={
            "binding_profile_revision_id": binding_profile_revision_id,
            "selector": {"direction": "top_down", "mode": "safe", "tags": ["baseline"]},
            "effective_from": date(2026, 1, 1).isoformat(),
            "status": "active",
        },
        actor_username=actor.username,
    )

    assert created is True
    assert saved_binding["binding_profile_revision_id"] == binding_profile_revision_id

    out = io.StringIO()
    call_command(
        "adopt_top_down_execution_pack_aliases",
        "--actor",
        actor.username,
        "--tenant-slug",
        tenant.slug,
        stdout=out,
    )
    output = json.loads(out.getvalue())

    assert output["binding_profile_code"] == TOP_DOWN_EXECUTION_PACK_CODE
    assert output["binding_profile_id"] == binding_profile_id
    assert output["profile_revision_reused"] is False
    assert output["updated_binding_ids"] == [saved_binding["binding_id"]]
    assert output["reused_binding_ids"] == []
    assert output["binding_profile_revision_number"] == 2
    assert output["realization_decision_revision"] == 2
    assert output["receipt_decision_revision"] == 2

    second_out = io.StringIO()
    call_command(
        "adopt_top_down_execution_pack_aliases",
        "--actor",
        actor.username,
        "--tenant-slug",
        tenant.slug,
        stdout=second_out,
    )
    second_output = json.loads(second_out.getvalue())
    assert second_output["profile_revision_reused"] is True
    assert second_output["updated_binding_ids"] == []
    assert second_output["reused_binding_ids"] == [saved_binding["binding_id"]]

    sale_latest = (
        DecisionTable.objects.filter(decision_table_id=sale_decision.decision_table_id)
        .order_by("-version_number")
        .first()
    )
    receipt_latest = (
        DecisionTable.objects.filter(decision_table_id=receipt_decision.decision_table_id)
        .order_by("-version_number")
        .first()
    )
    assert sale_latest is not None
    assert receipt_latest is not None
    assert sale_latest.version_number == 2
    assert receipt_latest.version_number == 2
    assert sale_latest.rules[0]["outputs"]["document_policy"]["chains"][0]["documents"][0]["field_mapping"][
        "Организация_Key"
    ] == "master_data.party.edge.parent.organization.ref"
    assert receipt_latest.rules[0]["outputs"]["document_policy"]["chains"][0]["documents"][0]["field_mapping"][
        "Организация_Key"
    ] == "master_data.party.edge.child.organization.ref"

    binding = PoolWorkflowBinding.objects.get(binding_id=saved_binding["binding_id"])
    assert binding.binding_profile_revision_id == output["binding_profile_revision_id"]
    assert binding.binding_profile_revision.revision_number == 2


@pytest.mark.django_db
def test_adopt_top_down_execution_pack_aliases_for_all_tenants_rewrites_each_matching_profile() -> None:
    actor = get_user_model().objects.create_user(
        username=f"top-down-global-actor-{uuid4().hex[:8]}",
        password="testpass123",
    )
    first = _seed_top_down_execution_pack(
        tenant=Tenant.objects.create(slug=f"top-down-a-{uuid4().hex[:8]}", name="Top Down A"),
        actor=actor,
    )
    second = _seed_top_down_execution_pack(
        tenant=Tenant.objects.create(slug=f"top-down-b-{uuid4().hex[:8]}", name="Top Down B"),
        actor=actor,
    )
    _ = create_canonical_binding_profile(
        tenant=Tenant.objects.create(slug=f"top-down-c-{uuid4().hex[:8]}", name="Top Down C"),
        binding_profile={
            "code": "other-execution-pack",
            "name": "Other Execution Pack",
            "revision": _build_binding_profile_revision(),
        },
        actor_username=actor.username,
    )

    results = adopt_top_down_execution_pack_aliases_for_all_tenants(actor_username=actor.username)

    assert [result["tenant_slug"] for result in results] == sorted(
        [first["tenant"].slug, second["tenant"].slug]
    )
    results_by_tenant = {result["tenant_slug"]: result for result in results}
    expected = {first["tenant"].slug: first, second["tenant"].slug: second}
    for tenant_slug, seeded in expected.items():
        result = results_by_tenant[tenant_slug]
        assert result["binding_profile_code"] == TOP_DOWN_EXECUTION_PACK_CODE
        assert result["binding_profile_id"] == seeded["binding_profile_id"]
        assert result["profile_revision_reused"] is False
        assert result["updated_binding_ids"] == [seeded["binding"]["binding_id"]]
        assert result["reused_binding_ids"] == []
        assert result["binding_profile_revision_number"] == 2

        binding = PoolWorkflowBinding.objects.get(binding_id=seeded["binding"]["binding_id"])
        assert binding.binding_profile_revision_id == result["binding_profile_revision_id"]
        assert binding.binding_profile_revision.revision_number == 2

    second_results = adopt_top_down_execution_pack_aliases_for_all_tenants(actor_username=actor.username)
    second_results_by_tenant = {result["tenant_slug"]: result for result in second_results}
    for tenant_slug, seeded in expected.items():
        result = second_results_by_tenant[tenant_slug]
        assert result["profile_revision_reused"] is True
        assert result["updated_binding_ids"] == []
        assert result["reused_binding_ids"] == [seeded["binding"]["binding_id"]]


def test_build_top_down_realization_alias_policy_rewrites_header_and_line_item_participants() -> None:
    policy = build_top_down_realization_alias_policy(
        policy=_build_policy(),
        contract_canonical_id="osnovnoy",
    )
    document = policy["chains"][0]["documents"][0]

    assert document["field_mapping"]["Организация_Key"] == "master_data.party.edge.parent.organization.ref"
    assert document["field_mapping"]["Контрагент_Key"] == "master_data.party.edge.child.counterparty.ref"
    assert document["field_mapping"]["ДоговорКонтрагента_Key"] == "master_data.contract.osnovnoy.edge.child.ref"
    assert document["field_mapping"]["Номенклатура_Key"] == "master_data.item.packing-service.ref"
    assert document["table_parts_mapping"]["Услуги"][0]["Контрагент_Key"] == (
        "master_data.party.edge.child.counterparty.ref"
    )
    assert document["table_parts_mapping"]["Услуги"][0]["ДоговорКонтрагента_Key"] == (
        "master_data.contract.osnovnoy.edge.child.ref"
    )


def test_build_top_down_receipt_alias_policy_rewrites_header_and_line_item_participants() -> None:
    policy = build_top_down_receipt_alias_policy(
        policy=_build_policy(),
        contract_canonical_id="osnovnoy",
    )
    document = policy["chains"][0]["documents"][0]

    assert document["field_mapping"]["Организация_Key"] == "master_data.party.edge.child.organization.ref"
    assert document["field_mapping"]["Контрагент_Key"] == "master_data.party.edge.parent.counterparty.ref"
    assert document["field_mapping"]["ДоговорКонтрагента_Key"] == "master_data.contract.osnovnoy.edge.parent.ref"
    assert document["field_mapping"]["Номенклатура_Key"] == "master_data.item.packing-service.ref"
    assert document["table_parts_mapping"]["Услуги"][0]["Контрагент_Key"] == (
        "master_data.party.edge.parent.counterparty.ref"
    )
    assert document["table_parts_mapping"]["Услуги"][0]["ДоговорКонтрагента_Key"] == (
        "master_data.contract.osnovnoy.edge.parent.ref"
    )
