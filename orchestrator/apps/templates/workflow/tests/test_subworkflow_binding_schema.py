from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.templates.workflow.models import WorkflowTemplate


@pytest.mark.django_db
def test_workflow_template_accepts_pinned_subworkflow_metadata(admin_user) -> None:
    template = WorkflowTemplate.objects.create(
        name="Pinned Subworkflow",
        workflow_type="sequential",
        dag_structure={
            "nodes": [
                {
                    "id": "approval",
                    "name": "Approval Gate",
                    "type": "subworkflow",
                    "subworkflow_config": {
                        "subworkflow_id": "rev-7",
                        "subworkflow_ref": {
                            "binding_mode": "pinned_revision",
                            "workflow_definition_key": "approval-gate",
                            "workflow_revision_id": "rev-7",
                            "workflow_revision": 7,
                        },
                        "input_mapping": {"workflow.request": "input.request"},
                        "output_mapping": {"workflow.approval": "result.approval"},
                    },
                }
            ],
            "edges": [],
        },
        created_by=admin_user,
    )

    config = template.dag_structure.nodes[0].subworkflow_config

    assert config is not None
    assert config.subworkflow_ref is not None
    assert config.subworkflow_ref.binding_mode == "pinned_revision"
    assert config.subworkflow_ref.workflow_revision == 7


@pytest.mark.django_db
def test_workflow_template_rejects_mismatched_pinned_subworkflow_revision(admin_user) -> None:
    with pytest.raises(ValidationError, match="workflow_revision_id must match subworkflow_id"):
        WorkflowTemplate.objects.create(
            name="Pinned Subworkflow Invalid",
            workflow_type="sequential",
            dag_structure={
                "nodes": [
                    {
                        "id": "approval",
                        "name": "Approval Gate",
                        "type": "subworkflow",
                        "subworkflow_config": {
                            "subworkflow_id": "rev-7",
                            "subworkflow_ref": {
                                "binding_mode": "pinned_revision",
                                "workflow_definition_key": "approval-gate",
                                "workflow_revision_id": "rev-8",
                                "workflow_revision": 7,
                            },
                        },
                    }
                ],
                "edges": [],
            },
            created_by=admin_user,
        )
