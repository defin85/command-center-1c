from __future__ import annotations

from typing import Any

from django.db import IntegrityError

from apps.templates.workflow.models import WorkflowTemplate, WorkflowType


POOL_FACTUAL_SYNC_WORKFLOW_TEMPLATE_NAME = "Pools Factual Sync Workflow"
POOL_FACTUAL_SYNC_WORKFLOW_TEMPLATE_DESCRIPTION = (
    "System-managed workflow template for pool factual read/reconcile jobs."
)
POOL_FACTUAL_SYNC_WORKFLOW_ALIAS = "pool.factual.sync_source_slice"


def build_pool_factual_sync_workflow_dag_v1() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": "factual_sync_source_slice",
                "name": "Factual Sync Source Slice",
                "type": "operation",
                "template_id": POOL_FACTUAL_SYNC_WORKFLOW_ALIAS,
            }
        ],
        "edges": [],
    }


def _normalize_dag(dag: Any) -> dict[str, Any]:
    if hasattr(dag, "model_dump"):
        dumped = dag.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {}
    if isinstance(dag, dict):
        return dict(dag)
    return {}


def ensure_pool_factual_sync_workflow_template(*, created_by=None) -> WorkflowTemplate:
    target_dag = build_pool_factual_sync_workflow_dag_v1()
    template = (
        WorkflowTemplate.objects.filter(name=POOL_FACTUAL_SYNC_WORKFLOW_TEMPLATE_NAME)
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
        template.description = POOL_FACTUAL_SYNC_WORKFLOW_TEMPLATE_DESCRIPTION
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
        name=POOL_FACTUAL_SYNC_WORKFLOW_TEMPLATE_NAME,
        description=POOL_FACTUAL_SYNC_WORKFLOW_TEMPLATE_DESCRIPTION,
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
            WorkflowTemplate.objects.filter(name=POOL_FACTUAL_SYNC_WORKFLOW_TEMPLATE_NAME)
            .order_by("-version_number")
            .first()
        )
        if existing is not None:
            return existing
        raise
    return template


__all__ = [
    "POOL_FACTUAL_SYNC_WORKFLOW_ALIAS",
    "POOL_FACTUAL_SYNC_WORKFLOW_TEMPLATE_DESCRIPTION",
    "POOL_FACTUAL_SYNC_WORKFLOW_TEMPLATE_NAME",
    "build_pool_factual_sync_workflow_dag_v1",
    "ensure_pool_factual_sync_workflow_template",
]
