from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from apps.databases.models import Database
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
from apps.intercompany_pools.workflow_bindings_store import upsert_canonical_pool_workflow_binding
from apps.templates.workflow.decision_tables import create_decision_table_revision
from apps.templates.workflow.models import WorkflowTemplate, WorkflowType
from apps.tenancy.models import Tenant


def _build_decision_payload(*, decision_table_id: str) -> dict[str, object]:
    return {
        "decision_table_id": decision_table_id,
        "decision_key": "document_policy",
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
                                "chain_id": "sale_chain",
                                "documents": [
                                    {
                                        "document_id": "sale",
                                        "entity_name": "Document_Sales",
                                        "document_role": "base",
                                        "field_mapping": {"Amount": "allocation.amount"},
                                        "table_parts_mapping": {},
                                        "link_rules": {},
                                        "invoice_mode": "required",
                                    },
                                    {
                                        "document_id": "invoice",
                                        "entity_name": "Document_Invoice",
                                        "document_role": "invoice",
                                        "field_mapping": {"BaseDocument": "sale.ref"},
                                        "table_parts_mapping": {},
                                        "link_rules": {"depends_on": "sale"},
                                        "link_to": "sale",
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


@pytest.mark.django_db
def test_build_pool_workflow_binding_preview_returns_compiled_projection_and_decision_lineage() -> None:
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
        name="Child Org",
        inn=f"74{uuid4().hex[:10]}",
    )
    root_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=root_org,
        effective_from=date(2026, 1, 1),
        is_root=True,
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
    )

    decision = create_decision_table_revision(contract=_build_decision_payload(decision_table_id="doc-policy"))
    workflow = _create_runtime_workflow_template(direction=PoolRunDirection.BOTTOM_UP)
    binding = {
        "binding_id": str(uuid4()),
        "pool_id": str(pool.id),
        "workflow": {
            "workflow_definition_key": str(workflow.id),
            "workflow_revision_id": str(workflow.id),
            "workflow_revision": workflow.version_number,
            "workflow_name": workflow.name,
        },
        "decisions": [
            {
                "decision_table_id": decision.decision_table_id,
                "decision_key": decision.decision_key,
                "decision_revision": decision.version_number,
            }
        ],
        "selector": {
            "direction": PoolRunDirection.BOTTOM_UP,
            "mode": PoolRunMode.SAFE,
            "tags": [],
        },
        "effective_from": "2026-01-01",
        "status": "active",
    }
    upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=binding,
        actor_username="binding-preview-test",
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
    assert preview["compiled_document_policy"]["version"] == DOCUMENT_POLICY_VERSION
    assert preview["runtime_projection"]["workflow_binding"]["binding_id"] == binding["binding_id"]
    assert preview["runtime_projection"]["document_policy_projection"]["policy_refs_count"] == 1
    assert preview["runtime_projection"]["decision_refs"] == [
        {
            "decision_table_id": decision.decision_table_id,
            "decision_key": decision.decision_key,
            "decision_revision": decision.version_number,
        }
    ]
