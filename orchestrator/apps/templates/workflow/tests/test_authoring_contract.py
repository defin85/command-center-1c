from __future__ import annotations

from uuid import uuid4

import pytest

from apps.templates.workflow.authoring_contract import (
    DecisionField,
    DecisionRule,
    DecisionTableContract,
    DecisionTableRef,
    WorkflowAuthoringNodeType,
    build_workflow_construct_visibility,
    build_workflow_compile_boundary,
    build_workflow_definition_ref,
)
from apps.templates.workflow.models import DAGStructure, WorkflowTemplate, WorkflowType


def _create_workflow_template(
    *,
    name: str,
    parent_version: WorkflowTemplate | None = None,
    version_number: int = 1,
) -> WorkflowTemplate:
    return WorkflowTemplate.objects.create(
        name=name,
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure=DAGStructure(
            nodes=[
                {"id": "start", "name": "Start", "type": "operation", "template_id": "noop"}
            ],
            edges=[],
        ),
        config={},
        is_valid=True,
        is_active=True,
        parent_version=parent_version,
        version_number=version_number,
    )


@pytest.mark.django_db
def test_build_workflow_compile_boundary_freezes_runtime_projection_contracts() -> None:
    root = _create_workflow_template(name=f"wf-{uuid4().hex[:6]}", version_number=1)
    revision = _create_workflow_template(
        name=root.name,
        parent_version=root,
        version_number=2,
    )

    boundary = build_workflow_compile_boundary(
        workflow_template=revision,
        decisions=[
            DecisionTableRef(
                decision_table_id="decision-publication",
                decision_key="publication_variant",
                decision_revision=3,
            )
        ],
    )

    assert boundary.workflow == build_workflow_definition_ref(workflow_template=revision)
    assert boundary.authoring_node_types == [
        WorkflowAuthoringNodeType.OPERATION_TASK,
        WorkflowAuthoringNodeType.DECISION_GATE,
        WorkflowAuthoringNodeType.APPROVAL_GATE,
        WorkflowAuthoringNodeType.SUBWORKFLOW_CALL,
    ]
    assert boundary.runtime_node_types == [
        "operation",
        "condition",
        "parallel",
        "loop",
        "subworkflow",
    ]
    assert boundary.internal_runtime_only_node_types == ["condition", "parallel", "loop"]
    assert boundary.runtime_projection_contracts == [
        "document_policy.v1",
        "document_plan_artifact.v1",
    ]
    assert boundary.decision_execution_mode == "compile_time_only"


def test_decision_table_contract_is_fail_closed_for_unknown_fields() -> None:
    with pytest.raises(ValueError, match="reference unknown input fields"):
        DecisionTableContract(
            decision_table_id="decision-publication",
            decision_key="publication_variant",
            decision_revision=1,
            name="Publication Variant",
            inputs=[DecisionField(name="direction", value_type="string")],
            outputs=[DecisionField(name="chain_id", value_type="string")],
            rules=[
                DecisionRule(
                    rule_id="rule-top-down",
                    conditions={"mode": "safe"},
                    outputs={"chain_id": "baseline"},
                    priority=10,
                )
            ],
        )


def test_decision_table_contract_defaults_to_deterministic_first_match() -> None:
    decision = DecisionTableContract(
        decision_table_id="decision-publication",
        decision_key="publication_variant",
        decision_revision=2,
        name="Publication Variant",
        inputs=[DecisionField(name="direction", value_type="string")],
        outputs=[DecisionField(name="chain_id", value_type="string")],
        rules=[
            DecisionRule(
                rule_id="rule-top-down",
                conditions={"direction": "top_down"},
                outputs={"chain_id": "baseline"},
                priority=10,
            )
        ],
    )

    assert decision.hit_policy == "first_match"
    assert decision.validation_mode == "fail_closed"


def test_workflow_construct_visibility_contract_separates_public_internal_and_compatibility() -> None:
    visibility = build_workflow_construct_visibility()

    assert visibility.contract_version == "workflow_construct_visibility.v1"
    assert visibility.public_constructs == [
        "operation_task",
        "decision_gate",
        "approval_gate",
        "subworkflow_call",
        "explicit_io",
        "pinned_template_binding",
        "pinned_subworkflow_binding",
        "decision_table",
    ]
    assert visibility.internal_runtime_only_constructs == [
        "condition",
        "parallel",
        "loop",
        "generated_runtime_projection",
        "compiled_document_policy",
        "document_plan_artifact",
    ]
    assert visibility.compatibility_constructs == [
        "template_id",
        "alias_latest_operation_binding",
        "workflow_executor_kind_template",
    ]
    assert set(visibility.public_constructs).isdisjoint(
        visibility.internal_runtime_only_constructs
    )
