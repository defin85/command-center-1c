from __future__ import annotations

import pytest

from apps.intercompany_pools.master_data_sync_workflow_template import (
    POOL_MASTER_DATA_SYNC_WORKFLOW_TEMPLATE_NAME,
    build_pool_master_data_sync_workflow_dag_v1,
    ensure_pool_master_data_sync_workflow_template,
)
from apps.templates.workflow.models import WorkflowTemplate, WorkflowType


@pytest.mark.django_db
def test_ensure_sync_workflow_template_creates_system_template_when_missing() -> None:
    template = ensure_pool_master_data_sync_workflow_template()

    assert template.name == POOL_MASTER_DATA_SYNC_WORKFLOW_TEMPLATE_NAME
    assert template.workflow_type == WorkflowType.SEQUENTIAL
    assert template.is_valid is True
    assert template.is_active is True
    dag = build_pool_master_data_sync_workflow_dag_v1()
    node_ids = [node["id"] for node in dag["nodes"]]
    assert node_ids == ["sync_inbound", "sync_dispatch", "sync_finalize"]
    assert dag["edges"] == [
        {"from": "sync_inbound", "to": "sync_dispatch"},
        {"from": "sync_dispatch", "to": "sync_finalize"},
    ]


@pytest.mark.django_db
def test_ensure_sync_workflow_template_is_idempotent() -> None:
    first = ensure_pool_master_data_sync_workflow_template()
    second = ensure_pool_master_data_sync_workflow_template()

    assert first.id == second.id
    assert WorkflowTemplate.objects.filter(
        name=POOL_MASTER_DATA_SYNC_WORKFLOW_TEMPLATE_NAME
    ).count() == 1
