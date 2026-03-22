from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools import binding_preview
from apps.intercompany_pools.binding_profiles_store import create_canonical_binding_profile
from apps.intercompany_pools.document_policy_contract import DOCUMENT_POLICY_VERSION
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolEdgeVersion,
    PoolNodeVersion,
    PoolRunDirection,
    PoolRunMode,
    PoolSchemaTemplate,
    PoolSchemaTemplateFormat,
)
from apps.intercompany_pools.binding_preview import build_pool_workflow_binding_preview
from apps.intercompany_pools.workflow_authoring_contract import (
    PoolWorkflowBindingContract,
    PoolWorkflowBindingDecisionRef,
    PoolWorkflowBindingSelector,
    PoolWorkflowBindingStatus,
    build_workflow_definition_ref,
)
from apps.intercompany_pools.workflow_binding_attachments_store import (
    upsert_pool_workflow_binding_attachment,
)
from apps.templates.workflow.decision_tables import create_decision_table_revision
from apps.templates.workflow.models import WorkflowTemplate, WorkflowType
from apps.tenancy.models import Tenant


def _build_decision_payload(
    *,
    decision_table_id: str,
    decision_key: str = "document_policy",
    chain_id: str = "sale_chain",
    base_document_id: str = "sale",
    base_entity_name: str = "Document_Sales",
    invoice_document_id: str = "invoice",
    invoice_entity_name: str = "Document_Invoice",
) -> dict[str, object]:
    return {
        "decision_table_id": decision_table_id,
        "decision_key": decision_key,
        "name": "Document Policy Decision",
        "inputs": [
            {"name": "direction", "value_type": "string", "required": True},
            {"name": "mode", "value_type": "string", "required": True},
        ],
        "outputs": [
            {"name": "document_policy", "value_type": "json", "required": True},
        ],
        "rules": [
            {
                "rule_id": "bottom-up-safe",
                "priority": 0,
                "conditions": {"direction": "bottom_up", "mode": "safe"},
                "outputs": {
                    "document_policy": {
                        "version": DOCUMENT_POLICY_VERSION,
                        "chains": [
                            {
                                "chain_id": chain_id,
                                "documents": [
                                    {
                                        "document_id": base_document_id,
                                        "entity_name": base_entity_name,
                                        "document_role": "base",
                                        "field_mapping": {"Amount": "allocation.amount"},
                                        "table_parts_mapping": {},
                                        "link_rules": {},
                                        "invoice_mode": "required",
                                    },
                                    {
                                        "document_id": invoice_document_id,
                                        "entity_name": invoice_entity_name,
                                        "document_role": "invoice",
                                        "field_mapping": {
                                            "BaseDocument": f"{base_document_id}.ref"
                                        },
                                        "table_parts_mapping": {},
                                        "link_rules": {"depends_on": base_document_id},
                                        "link_to": base_document_id,
                                    },
                                ],
                            }
                        ],
                    }
                },
            }
        ],
    }


def _create_runtime_workflow_template(*, direction: str) -> WorkflowTemplate:
    distribution_alias = (
        "pool.distribution_calculation.top_down"
        if direction == PoolRunDirection.TOP_DOWN
        else "pool.distribution_calculation.bottom_up"
    )
    return WorkflowTemplate.objects.create(
        name=f"binding-preview-workflow-{uuid4().hex[:8]}",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {
                    "id": "prepare_input",
                    "name": "Prepare Input",
                    "type": "operation",
                    "template_id": "pool.prepare_input",
                },
                {
                    "id": "distribution",
                    "name": "Distribution",
                    "type": "operation",
                    "template_id": distribution_alias,
                },
                {
                    "id": "publish",
                    "name": "Publish",
                    "type": "operation",
                    "template_id": "pool.publication_odata",
                },
            ],
            "edges": [
                {"from": "prepare_input", "to": "distribution"},
                {"from": "distribution", "to": "publish"},
            ],
        },
        config={"timeout_seconds": 86400, "max_retries": 0},
        is_valid=True,
        is_active=True,
    )


def _create_preview_fixture(
    *,
    child_count: int = 1,
    slot_keys: list[str | None] | None = None,
) -> dict[str, object]:
    tenant = Tenant.objects.create(slug=f"binding-preview-{uuid4().hex[:8]}", name="Binding Preview")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Pool Binding Preview",
    )
    schema_template = PoolSchemaTemplate.objects.create(
        tenant=tenant,
        code=f"schema-{uuid4().hex[:6]}",
        name="Schema Template",
        format=PoolSchemaTemplateFormat.JSON,
        schema={"columns": {"inn": "inn", "amount": "amount"}},
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
    for index in range(child_count):
        target_database = Database.objects.create(
            tenant=tenant,
            name=f"preview-db-{uuid4().hex[:8]}",
            host="localhost",
            odata_url="http://localhost/odata/standard.odata",
            username="admin",
            password="secret",
        )
        child_org = Organization.objects.create(
            tenant=tenant,
            database=target_database,
            name=f"Child Org {index + 1}",
            inn=f"74{uuid4().hex[:10]}",
        )
        child_node = PoolNodeVersion.objects.create(
            pool=pool,
            organization=child_org,
            effective_from=date(2026, 1, 1),
        )
        PoolEdgeVersion.objects.create(
            pool=pool,
            parent_node=root_node,
            child_node=child_node,
            effective_from=date(2026, 1, 1),
            metadata=(
                {"document_policy_key": str(slot_keys[index]).strip()}
                if slot_keys is not None and index < len(slot_keys) and slot_keys[index]
                else {}
            ),
        )
    return {
        "tenant": tenant,
        "pool": pool,
        "schema_template": schema_template,
    }


def _attach_binding(
    *,
    pool: OrganizationPool,
    workflow: WorkflowTemplate,
    decisions: list[dict[str, object]],
    direction: str,
    mode: str,
) -> dict[str, object]:
    profile = create_canonical_binding_profile(
        tenant=pool.tenant,
        binding_profile={
            "code": f"binding-preview-{uuid4().hex[:8]}",
            "name": f"Binding Preview {workflow.name}",
            "revision": {
                "workflow": {
                    "workflow_definition_key": str(workflow.id),
                    "workflow_revision_id": str(workflow.id),
                    "workflow_revision": workflow.version_number,
                    "workflow_name": workflow.name,
                },
                "decisions": decisions,
                "parameters": {},
                "role_mapping": {},
                "metadata": {
                    "source": "test",
                },
            },
        },
        actor_username="binding-preview-test",
    )
    latest_revision = profile["latest_revision"]
    assert isinstance(latest_revision, dict)
    binding, _ = upsert_pool_workflow_binding_attachment(
        pool=pool,
        workflow_binding={
            "binding_profile_revision_id": str(latest_revision["binding_profile_revision_id"]),
            "selector": {
                "direction": direction,
                "mode": mode,
                "tags": [],
            },
            "effective_from": "2026-01-01",
            "status": "active",
        },
        actor_username="binding-preview-test",
    )
    return binding


@pytest.mark.django_db
def test_build_pool_workflow_binding_preview_returns_compiled_projection_and_decision_lineage() -> None:
    fixture = _create_preview_fixture(slot_keys=["document_policy"])
    tenant = fixture["tenant"]
    pool = fixture["pool"]
    schema_template = fixture["schema_template"]

    decision = create_decision_table_revision(contract=_build_decision_payload(decision_table_id="doc-policy"))
    workflow = _create_runtime_workflow_template(direction=PoolRunDirection.BOTTOM_UP)
    binding = _attach_binding(
        pool=pool,
        workflow=workflow,
        decisions=[
            {
                "decision_table_id": decision.decision_table_id,
                "decision_key": decision.decision_key,
                "slot_key": "document_policy",
                "decision_revision": decision.version_number,
            }
        ],
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )

    preview = build_pool_workflow_binding_preview(
        tenant=tenant,
        pool=pool,
        pool_workflow_binding_id=binding["binding_id"],
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        run_input={"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
        schema_template=schema_template,
    )

    assert preview["workflow_binding"]["binding_id"] == binding["binding_id"]
    assert "workflow" not in preview["workflow_binding"]
    assert "decisions" not in preview["workflow_binding"]
    assert preview["workflow_binding"]["resolved_profile"]["decisions"] == [
        {
            "decision_table_id": decision.decision_table_id,
            "decision_key": decision.decision_key,
            "slot_key": "document_policy",
            "decision_revision": decision.version_number,
        }
    ]
    assert preview["compiled_document_policy"]["version"] == DOCUMENT_POLICY_VERSION
    assert preview["compiled_document_policy_slots"] == {
        "document_policy": {
            "decision_table_id": decision.decision_table_id,
            "decision_revision": decision.version_number,
            "document_policy_source": (
                "workflow_binding.decision_table:"
                f"{decision.decision_table_id}:v{decision.version_number}"
            ),
            "document_policy": preview["compiled_document_policy"],
        }
    }
    assert preview["runtime_projection"]["workflow_binding"]["binding_id"] == binding["binding_id"]
    assert preview["runtime_projection"]["document_policy_projection"]["policy_refs_count"] == 1
    assert preview["runtime_projection"]["document_policy_projection"]["compiled_document_policy_slots"] == (
        preview["compiled_document_policy_slots"]
    )
    assert preview["runtime_projection"]["document_policy_projection"]["slot_coverage_summary"] == (
        preview["slot_coverage_summary"]
    )
    assert preview["runtime_projection"]["workflow_binding"]["decision_refs"] == [
        {
            "decision_table_id": decision.decision_table_id,
            "decision_key": decision.decision_key,
            "slot_key": "document_policy",
            "decision_revision": decision.version_number,
        }
    ]


@pytest.mark.django_db
def test_build_pool_workflow_binding_preview_materializes_slots_once_per_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _create_preview_fixture(child_count=2, slot_keys=["sale", "purchase"])
    tenant = fixture["tenant"]
    pool = fixture["pool"]
    schema_template = fixture["schema_template"]

    sale_decision = create_decision_table_revision(
        contract=_build_decision_payload(
            decision_table_id="sale-slot",
            chain_id="sale_chain",
            base_document_id="sale",
            base_entity_name="Document_Sales",
        )
    )
    purchase_decision = create_decision_table_revision(
        contract=_build_decision_payload(
            decision_table_id="purchase-slot",
            chain_id="purchase_chain",
            base_document_id="purchase",
            base_entity_name="Document_Purchase",
            invoice_document_id="receipt",
            invoice_entity_name="Document_Receipt",
        )
    )
    workflow = _create_runtime_workflow_template(direction=PoolRunDirection.BOTTOM_UP)
    binding = _attach_binding(
        pool=pool,
        workflow=workflow,
        decisions=[
            {
                "decision_table_id": sale_decision.decision_table_id,
                "decision_key": sale_decision.decision_key,
                "slot_key": "sale",
                "decision_revision": sale_decision.version_number,
            },
            {
                "decision_table_id": purchase_decision.decision_table_id,
                "decision_key": purchase_decision.decision_key,
                "slot_key": "purchase",
                "decision_revision": purchase_decision.version_number,
            },
        ],
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
    )

    original_evaluate = binding_preview.evaluate_decision_table
    evaluation_inputs: list[dict[str, object]] = []

    def _counting_evaluate(*, decision_table, inputs):
        evaluation_inputs.append(dict(inputs))
        return original_evaluate(decision_table=decision_table, inputs=inputs)

    monkeypatch.setattr(binding_preview, "evaluate_decision_table", _counting_evaluate)

    preview = build_pool_workflow_binding_preview(
        tenant=tenant,
        pool=pool,
        pool_workflow_binding_id=binding["binding_id"],
        direction=PoolRunDirection.BOTTOM_UP,
        mode=PoolRunMode.SAFE,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        run_input={"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
        schema_template=schema_template,
    )

    assert len(evaluation_inputs) == 2
    assert preview["compiled_document_policy"]["chains"][0]["chain_id"] == "sale_chain"
    assert set(preview["compiled_document_policy_slots"]) == {"sale", "purchase"}
    assert preview["compiled_document_policy_slots"]["sale"]["document_policy"]["chains"][0]["chain_id"] == "sale_chain"
    assert (
        preview["compiled_document_policy_slots"]["purchase"]["document_policy"]["chains"][0]["chain_id"]
        == "purchase_chain"
    )
    assert preview["slot_coverage_summary"]["total_edges"] == 2
    assert preview["slot_coverage_summary"]["counts"]["resolved"] == 2
    assert preview["slot_coverage_summary"]["counts"]["missing_slot"] == 0
    assert preview["slot_coverage_summary"]["items"][0]["coverage"]["code"] is None


@pytest.mark.django_db
def test_build_pool_workflow_binding_preview_fails_closed_on_duplicate_slot_key() -> None:
    fixture = _create_preview_fixture()
    pool = fixture["pool"]

    first_decision = create_decision_table_revision(
        contract=_build_decision_payload(
            decision_table_id="duplicate-a",
            chain_id="slot_a_chain",
        )
    )
    second_decision = create_decision_table_revision(
        contract=_build_decision_payload(
            decision_table_id="duplicate-b",
            chain_id="slot_b_chain",
        )
    )
    workflow = _create_runtime_workflow_template(direction=PoolRunDirection.BOTTOM_UP)
    binding = PoolWorkflowBindingContract.model_construct(
        contract_version="pool_workflow_binding.v1",
        binding_id=str(uuid4()),
        pool_id=str(pool.id),
        workflow=build_workflow_definition_ref(workflow_template=workflow),
        decisions=[
            PoolWorkflowBindingDecisionRef(
                decision_table_id=first_decision.decision_table_id,
                decision_key=first_decision.decision_key,
                slot_key="shared_slot",
                decision_revision=first_decision.version_number,
            ),
            PoolWorkflowBindingDecisionRef(
                decision_table_id=second_decision.decision_table_id,
                decision_key=second_decision.decision_key,
                slot_key="shared_slot",
                decision_revision=second_decision.version_number,
            ),
        ],
        parameters={},
        role_mapping={},
        selector=PoolWorkflowBindingSelector(
            direction=PoolRunDirection.BOTTOM_UP,
            mode=PoolRunMode.SAFE,
            tags=[],
        ),
        effective_from=date(2026, 1, 1),
        effective_to=None,
        status=PoolWorkflowBindingStatus.ACTIVE,
    )

    with pytest.raises(ValueError, match="POOL_DOCUMENT_POLICY_SLOT_DUPLICATE"):
        binding_preview.evaluate_binding_decisions(
            binding=binding,
            pool=pool,
            direction=PoolRunDirection.BOTTOM_UP,
            mode=PoolRunMode.SAFE,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            run_input={"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
        )
