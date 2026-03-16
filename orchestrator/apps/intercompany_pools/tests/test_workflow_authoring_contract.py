from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from apps.intercompany_pools.workflow_authoring_contract import (
    DecisionField,
    DecisionRule,
    DecisionTableContract,
    PoolWorkflowBindingContract,
    PoolWorkflowBindingDecisionRef,
    PoolWorkflowBindingSelector,
    PoolWorkflowBindingStatus,
    build_pool_workflow_binding_lineage,
    build_workflow_definition_ref,
)
from apps.templates.workflow.models import DAGStructure, WorkflowTemplate, WorkflowType


def _create_workflow_template(*, name: str, parent_version: WorkflowTemplate | None = None, version_number: int = 1) -> WorkflowTemplate:
    return WorkflowTemplate.objects.create(
        name=name,
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure=DAGStructure(
            nodes=[{"id": "start", "name": "Start", "type": "operation", "template_id": "noop"}],
            edges=[],
        ),
        config={},
        is_valid=True,
        is_active=True,
        parent_version=parent_version,
        version_number=version_number,
    )


@pytest.mark.django_db
def test_build_workflow_definition_ref_uses_root_template_as_definition_key() -> None:
    root = _create_workflow_template(name=f"wf-{uuid4().hex[:6]}", version_number=1)
    revision = _create_workflow_template(
        name=root.name,
        parent_version=root,
        version_number=2,
    )

    ref = build_workflow_definition_ref(workflow_template=revision)

    assert ref.workflow_definition_key == str(root.id)
    assert ref.workflow_revision_id == str(revision.id)
    assert ref.workflow_revision == 2
    assert ref.workflow_name == root.name


def test_decision_table_contract_requires_unique_rule_ids() -> None:
    with pytest.raises(ValueError, match="decision rule_id values must be unique"):
        DecisionTableContract(
            decision_table_id="decision-publication",
            decision_key="publication_variant",
            decision_revision=1,
            name="Publication Variant",
            inputs=[DecisionField(name="direction", value_type="string")],
            outputs=[DecisionField(name="chain_id", value_type="string")],
            rules=[
                DecisionRule(rule_id="rule-1", conditions={"direction": "top_down"}, outputs={"chain_id": "a"}),
                DecisionRule(rule_id="rule-1", conditions={"direction": "bottom_up"}, outputs={"chain_id": "b"}),
            ],
        )


@pytest.mark.django_db
def test_pool_workflow_binding_contract_builds_lineage_snapshot() -> None:
    workflow = _create_workflow_template(name=f"wf-{uuid4().hex[:6]}", version_number=1)
    binding = PoolWorkflowBindingContract(
        binding_id="binding-services-v1",
        pool_id=str(uuid4()),
        workflow=build_workflow_definition_ref(workflow_template=workflow),
        decisions=[
            PoolWorkflowBindingDecisionRef(
                decision_table_id="decision-publication",
                decision_key="document_policy",
                slot_key="sale",
                decision_revision=3,
            )
        ],
        role_mapping={"seller": "organization:stroygrupp"},
        selector=PoolWorkflowBindingSelector(direction="top_down", mode="safe", tags=["baseline"]),
        effective_from=date(2026, 1, 1),
        status=PoolWorkflowBindingStatus.ACTIVE,
    )

    lineage = build_pool_workflow_binding_lineage(binding=binding)

    assert lineage["binding_id"] == "binding-services-v1"
    assert lineage["workflow"]["workflow_definition_key"] == str(workflow.id)
    assert lineage["workflow"]["workflow_revision"] == 1
    assert lineage["decisions"] == [
        {
            "decision_table_id": "decision-publication",
            "decision_key": "document_policy",
            "slot_key": "sale",
            "decision_revision": 3,
        }
    ]
    assert lineage["selector"] == {"direction": "top_down", "mode": "safe", "tags": ["baseline"]}
    assert lineage["status"] == "active"


@pytest.mark.django_db
def test_pool_workflow_binding_contract_allows_reusing_document_policy_decision_key_across_slots() -> None:
    workflow = _create_workflow_template(name=f"wf-{uuid4().hex[:6]}", version_number=1)

    binding = PoolWorkflowBindingContract(
        binding_id="binding-services-v1",
        pool_id=str(uuid4()),
        workflow=build_workflow_definition_ref(workflow_template=workflow),
        decisions=[
            PoolWorkflowBindingDecisionRef(
                decision_table_id="decision-publication-a",
                decision_key="document_policy",
                slot_key="sale",
                decision_revision=3,
            ),
            PoolWorkflowBindingDecisionRef(
                decision_table_id="decision-publication-b",
                decision_key="document_policy",
                slot_key="purchase",
                decision_revision=4,
            ),
        ],
        effective_from=date(2026, 1, 1),
        status=PoolWorkflowBindingStatus.ACTIVE,
    )

    assert [decision.slot_key for decision in binding.decisions] == ["sale", "purchase"]


@pytest.mark.django_db
def test_pool_workflow_binding_contract_requires_slot_key_for_document_policy_decisions() -> None:
    workflow = _create_workflow_template(name=f"wf-{uuid4().hex[:6]}", version_number=1)

    with pytest.raises(ValueError, match="slot_key"):
        PoolWorkflowBindingContract(
            binding_id="binding-services-v1",
            pool_id=str(uuid4()),
            workflow=build_workflow_definition_ref(workflow_template=workflow),
            decisions=[
                PoolWorkflowBindingDecisionRef(
                    decision_table_id="decision-publication",
                    decision_key="document_policy",
                    decision_revision=3,
                )
            ],
            effective_from=date(2026, 1, 1),
            status=PoolWorkflowBindingStatus.ACTIVE,
        )


@pytest.mark.django_db
def test_pool_workflow_binding_contract_rejects_duplicate_slot_key() -> None:
    workflow = _create_workflow_template(name=f"wf-{uuid4().hex[:6]}", version_number=1)

    with pytest.raises(ValueError, match="POOL_DOCUMENT_POLICY_SLOT_DUPLICATE"):
        PoolWorkflowBindingContract(
            binding_id="binding-services-v1",
            pool_id=str(uuid4()),
            workflow=build_workflow_definition_ref(workflow_template=workflow),
            decisions=[
                PoolWorkflowBindingDecisionRef(
                    decision_table_id="decision-publication-a",
                    decision_key="document_policy",
                    slot_key="shared_slot",
                    decision_revision=3,
                ),
                PoolWorkflowBindingDecisionRef(
                    decision_table_id="decision-publication-b",
                    decision_key="document_policy",
                    slot_key="shared_slot",
                    decision_revision=4,
                ),
            ],
            effective_from=date(2026, 1, 1),
            status=PoolWorkflowBindingStatus.ACTIVE,
        )
