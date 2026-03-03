from __future__ import annotations

from typing import Any

from django.db import IntegrityError

from apps.templates.workflow.models import WorkflowTemplate, WorkflowType


POOL_MASTER_DATA_SYNC_WORKFLOW_TEMPLATE_NAME = "Pools Master Data Sync Workflow"
POOL_MASTER_DATA_SYNC_WORKFLOW_TEMPLATE_DESCRIPTION = (
    "System-managed workflow template for pool master-data sync jobs."
)

POOL_MASTER_DATA_SYNC_WORKFLOW_DISPATCH_ALIAS = "pool.master_data_sync.dispatch"
POOL_MASTER_DATA_SYNC_WORKFLOW_INBOUND_ALIAS = "pool.master_data_sync.inbound"
POOL_MASTER_DATA_SYNC_WORKFLOW_FINALIZE_ALIAS = "pool.master_data_sync.finalize"


def build_pool_master_data_sync_workflow_dag_v1() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": "sync_inbound",
                "name": "Sync Inbound",
                "type": "operation",
                "template_id": POOL_MASTER_DATA_SYNC_WORKFLOW_INBOUND_ALIAS,
            },
            {
                "id": "sync_dispatch",
                "name": "Sync Dispatch",
                "type": "operation",
                "template_id": POOL_MASTER_DATA_SYNC_WORKFLOW_DISPATCH_ALIAS,
            },
            {
                "id": "sync_finalize",
                "name": "Sync Finalize",
                "type": "operation",
                "template_id": POOL_MASTER_DATA_SYNC_WORKFLOW_FINALIZE_ALIAS,
            },
        ],
        "edges": [
            {"from": "sync_inbound", "to": "sync_dispatch"},
            {"from": "sync_dispatch", "to": "sync_finalize"},
        ],
    }


def _normalize_dag(dag: Any) -> dict[str, Any]:
    if hasattr(dag, "model_dump"):
        dumped = dag.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {}
    if isinstance(dag, dict):
        return dict(dag)
    return {}


def ensure_pool_master_data_sync_workflow_template(
    *,
    created_by=None,
) -> WorkflowTemplate:
    target_dag = build_pool_master_data_sync_workflow_dag_v1()
    template = (
        WorkflowTemplate.objects.filter(name=POOL_MASTER_DATA_SYNC_WORKFLOW_TEMPLATE_NAME)
        .order_by("-version_number")
        .first()
    )
    if template is not None:
        if (
            template.workflow_type == WorkflowType.SEQUENTIAL
            and template.is_valid is True
            and template.is_active is True
            and _normalize_dag(template.dag_structure) == target_dag
        ):
            return template
        template.workflow_type = WorkflowType.SEQUENTIAL
        template.description = POOL_MASTER_DATA_SYNC_WORKFLOW_TEMPLATE_DESCRIPTION
        template.dag_structure = target_dag
        template.is_valid = True
        template.is_active = True
        template.save(
            update_fields=[
                "workflow_type",
                "description",
                "dag_structure",
                "is_valid",
                "is_active",
                "updated_at",
            ]
        )
        return template

    template = WorkflowTemplate(
        name=POOL_MASTER_DATA_SYNC_WORKFLOW_TEMPLATE_NAME,
        description=POOL_MASTER_DATA_SYNC_WORKFLOW_TEMPLATE_DESCRIPTION,
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure=target_dag,
        is_valid=True,
        is_active=True,
        created_by=created_by,
    )
    try:
        template.save()
    except IntegrityError:
        existing = (
            WorkflowTemplate.objects.filter(name=POOL_MASTER_DATA_SYNC_WORKFLOW_TEMPLATE_NAME)
            .order_by("-version_number")
            .first()
        )
        if existing is not None:
            return existing
        raise
    return template
