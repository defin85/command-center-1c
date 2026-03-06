from __future__ import annotations

from datetime import date
from uuid import uuid4
from unittest.mock import patch

import pytest

from apps.intercompany_pools.master_data_feature_flags import PoolMasterDataGateResolution
from apps.intercompany_pools.models import (
    PoolRunDirection,
    PoolRunMode,
    PoolSchemaTemplate,
    PoolSchemaTemplateFormat,
)
from apps.intercompany_pools.runtime_template_registry import sync_pool_runtime_template_registry
from apps.intercompany_pools.workflow_compiler import (
    PoolWorkflowCompiler,
    PoolWorkflowRunContext,
    compile_pool_execution_plan,
)
from apps.tenancy.models import Tenant
from apps.templates.models import OperationExposure


def _create_schema_template(*, tenant: Tenant, code: str = "pool-template") -> PoolSchemaTemplate:
    return PoolSchemaTemplate.objects.create(
        tenant=tenant,
        code=code,
        name="Pool Template",
        format=PoolSchemaTemplateFormat.JSON,
        schema={"columns": {"inn": "inn", "amount": "amount"}},
        metadata={"workflow_binding": "legacy-binding-hint"},
    )


def _create_context(
    *,
    pool_id: str | None = None,
    period_start: date = date(2026, 1, 1),
    period_end: date | None = date(2026, 1, 31),
    direction: str = PoolRunDirection.BOTTOM_UP,
    mode: str = PoolRunMode.SAFE,
    run_input: dict | None = None,
    document_plan_artifact: dict | None = None,
) -> PoolWorkflowRunContext:
    return PoolWorkflowRunContext(
        pool_id=pool_id or str(uuid4()),
        period_start=period_start,
        period_end=period_end,
        direction=direction,
        mode=mode,
        run_input=run_input if isinstance(run_input, dict) else {"source_payload": [{"inn": "770000000001", "amount": "10.00"}]},
        document_plan_artifact=document_plan_artifact if isinstance(document_plan_artifact, dict) else None,
    )


def _sync_runtime_templates() -> None:
    sync_pool_runtime_template_registry()


def _build_document_plan_artifact() -> dict[str, object]:
    return {
        "version": "document_plan_artifact.v1",
        "run_id": str(uuid4()),
        "distribution_artifact_ref": {
            "version": "distribution_artifact.v1",
            "topology_version_ref": "topology-v1",
        },
        "topology_version_ref": "topology-v1",
        "policy_refs": [
            {
                "edge_ref": {
                    "parent_node_id": "node-parent",
                    "child_node_id": "node-child",
                },
                "policy_version": "document_policy.v1",
                "source": "edge.metadata.document_policy",
            }
        ],
        "targets": [
            {
                "database_id": "db-001",
                "chains": [
                    {
                        "chain_id": "sale-chain",
                        "edge_ref": {
                            "parent_node_id": "node-parent",
                            "child_node_id": "node-child",
                        },
                        "policy_source": "edge.metadata.document_policy",
                        "policy_version": "document_policy.v1",
                        "allocation": {"amount": "100.00"},
                        "documents": [
                            {
                                "document_id": "sale-doc",
                                "entity_name": "Document_Sales",
                                "document_role": "base",
                                "field_mapping": {},
                                "table_parts_mapping": {},
                                "link_rules": {},
                                "invoice_mode": "optional",
                                "idempotency_key": "doc-sale-key",
                            },
                            {
                                "document_id": "invoice-doc",
                                "entity_name": "Document_Invoice",
                                "document_role": "invoice",
                                "field_mapping": {},
                                "table_parts_mapping": {},
                                "link_rules": {},
                                "invoice_mode": "required",
                                "idempotency_key": "doc-invoice-key",
                                "link_to": "sale-doc",
                            },
                        ],
                    }
                ],
            }
        ],
        "compile_summary": {
            "compiled_edges": 1,
            "targets_count": 1,
            "chains_count": 1,
            "documents_count": 2,
            "compiled_at": "2026-01-01T00:00:00+00:00",
        },
    }


@pytest.mark.django_db
def test_compile_pool_execution_plan_is_deterministic() -> None:
    tenant = Tenant.objects.create(slug=f"pool-compiler-{uuid4().hex[:8]}", name="Pool Compiler")
    schema_template = _create_schema_template(tenant=tenant)
    context = _create_context()
    _sync_runtime_templates()

    plan_1 = compile_pool_execution_plan(schema_template=schema_template, run_context=context)
    plan_2 = compile_pool_execution_plan(schema_template=schema_template, run_context=context)

    assert plan_1.plan_key == plan_2.plan_key
    assert plan_1.template_version == plan_2.template_version
    assert plan_1.dag_structure == plan_2.dag_structure
    assert plan_1.workflow_template_name == plan_2.workflow_template_name


@pytest.mark.django_db
def test_compile_pool_execution_plan_reuses_definition_for_different_period_and_run_input() -> None:
    tenant = Tenant.objects.create(slug=f"pool-reuse-{uuid4().hex[:8]}", name="Pool Reuse")
    schema_template = _create_schema_template(tenant=tenant, code="reuse-template")
    _sync_runtime_templates()

    shared_pool_id = str(uuid4())
    plan_1 = compile_pool_execution_plan(
        schema_template=schema_template,
        run_context=_create_context(
            pool_id=shared_pool_id,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            run_input={"source_payload": [{"inn": "770000000001", "amount": "10.00"}]},
        ),
    )
    plan_2 = compile_pool_execution_plan(
        schema_template=schema_template,
        run_context=_create_context(
            pool_id=shared_pool_id,
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28),
            run_input={"source_payload": [{"inn": "770000000999", "amount": "999.00"}]},
        ),
    )

    assert plan_1.plan_key == plan_2.plan_key
    assert plan_1.workflow_template_name == plan_2.workflow_template_name
    assert plan_1.dag_structure == plan_2.dag_structure


@pytest.mark.django_db
def test_compile_pool_execution_plan_safe_mode_includes_approval_gate() -> None:
    tenant = Tenant.objects.create(slug=f"pool-safe-{uuid4().hex[:8]}", name="Pool Safe")
    schema_template = _create_schema_template(tenant=tenant, code="safe-template")
    context = _create_context(mode=PoolRunMode.SAFE)
    _sync_runtime_templates()

    with patch(
        "apps.intercompany_pools.workflow_compiler.resolve_pool_master_data_gate_flag",
        return_value=PoolMasterDataGateResolution(
            source="tenant_override",
            raw_value=False,
            value=False,
        ),
    ):
        plan = compile_pool_execution_plan(schema_template=schema_template, run_context=context)
    node_ids = [node["id"] for node in plan.dag_structure["nodes"]]

    assert "approval_gate" in node_ids
    assert node_ids == [
        "prepare_input",
        "distribution_calculation",
        "reconciliation_report",
        "approval_gate",
        "publication_odata",
    ]
    approval_edge = next(
        edge
        for edge in plan.dag_structure["edges"]
        if edge["from"] == "approval_gate" and edge["to"] == "publication_odata"
    )
    assert approval_edge["condition"] == "{{approved_at}}"


@pytest.mark.django_db
def test_compile_pool_execution_plan_unsafe_mode_skips_approval_gate() -> None:
    tenant = Tenant.objects.create(slug=f"pool-unsafe-{uuid4().hex[:8]}", name="Pool Unsafe")
    schema_template = _create_schema_template(tenant=tenant, code="unsafe-template")
    context = _create_context(mode=PoolRunMode.UNSAFE)
    _sync_runtime_templates()

    with patch(
        "apps.intercompany_pools.workflow_compiler.resolve_pool_master_data_gate_flag",
        return_value=PoolMasterDataGateResolution(
            source="tenant_override",
            raw_value=False,
            value=False,
        ),
    ):
        plan = compile_pool_execution_plan(schema_template=schema_template, run_context=context)
    node_ids = [node["id"] for node in plan.dag_structure["nodes"]]

    assert "approval_gate" not in node_ids
    assert node_ids == [
        "prepare_input",
        "distribution_calculation",
        "reconciliation_report",
        "publication_odata",
    ]
    assert all("condition" not in edge for edge in plan.dag_structure["edges"])


@pytest.mark.django_db
def test_compile_pool_execution_plan_includes_master_data_gate_when_feature_enabled() -> None:
    tenant = Tenant.objects.create(slug=f"pool-master-gate-{uuid4().hex[:8]}", name="Pool Master Gate")
    schema_template = _create_schema_template(tenant=tenant, code="master-gate-template")
    _sync_runtime_templates()

    with patch(
        "apps.intercompany_pools.workflow_compiler.resolve_pool_master_data_gate_flag",
        return_value=PoolMasterDataGateResolution(
            source="tenant_override",
            raw_value=True,
            value=True,
        ),
    ):
        plan = compile_pool_execution_plan(
            schema_template=schema_template,
            run_context=_create_context(mode=PoolRunMode.SAFE),
        )

    node_ids = [node["id"] for node in plan.dag_structure["nodes"]]
    assert node_ids == [
        "prepare_input",
        "distribution_calculation",
        "reconciliation_report",
        "approval_gate",
        "master_data_gate",
        "publication_odata",
    ]
    approval_edge = next(
        edge
        for edge in plan.dag_structure["edges"]
        if edge["from"] == "approval_gate" and edge["to"] == "master_data_gate"
    )
    assert approval_edge["condition"] == "{{approved_at}}"


@pytest.mark.django_db
def test_compile_pool_execution_plan_includes_master_data_gate_when_feature_flag_is_invalid() -> None:
    tenant = Tenant.objects.create(slug=f"pool-master-gate-invalid-{uuid4().hex[:8]}", name="Pool Master Gate Invalid")
    schema_template = _create_schema_template(tenant=tenant, code="master-gate-invalid-template")
    _sync_runtime_templates()

    with patch(
        "apps.intercompany_pools.workflow_compiler.resolve_pool_master_data_gate_flag",
        return_value=PoolMasterDataGateResolution(
            source="global",
            raw_value="definitely-not-bool",
            value=None,
        ),
    ):
        plan = compile_pool_execution_plan(
            schema_template=schema_template,
            run_context=_create_context(mode=PoolRunMode.SAFE),
        )

    node_ids = [node["id"] for node in plan.dag_structure["nodes"]]
    assert node_ids == [
        "prepare_input",
        "distribution_calculation",
        "reconciliation_report",
        "approval_gate",
        "master_data_gate",
        "publication_odata",
    ]


@pytest.mark.django_db
def test_compile_pool_execution_plan_uses_atomic_publication_nodes_from_document_plan_artifact() -> None:
    tenant = Tenant.objects.create(slug=f"pool-atomic-{uuid4().hex[:8]}", name="Pool Atomic")
    schema_template = _create_schema_template(tenant=tenant, code="atomic-template")
    _sync_runtime_templates()

    artifact = _build_document_plan_artifact()
    with patch(
        "apps.intercompany_pools.workflow_compiler.resolve_pool_master_data_gate_flag",
        return_value=PoolMasterDataGateResolution(
            source="tenant_override",
            raw_value=False,
            value=False,
        ),
    ):
        plan = compile_pool_execution_plan(
            schema_template=schema_template,
            run_context=_create_context(
                mode=PoolRunMode.SAFE,
                document_plan_artifact=artifact,
            ),
        )

    publication_steps = [step for step in plan.steps if step.operation_alias == "pool.publication_odata"]
    node_ids = [node["id"] for node in plan.dag_structure["nodes"]]

    assert len(publication_steps) == 2
    assert "publication_odata" not in node_ids
    assert all(step.node_id.startswith("publication_odata_") for step in publication_steps)
    assert all(step.node_id in node_ids for step in publication_steps)
    assert all(isinstance(step.provenance, dict) for step in publication_steps)
    assert all(step.provenance.get("kind") == "pool_atomic_publication" for step in publication_steps)
    assert all(step.provenance.get("action_kind") == "publish_odata" for step in publication_steps)
    assert all(step.provenance.get("attempt_scope") == "run_execution" for step in publication_steps)
    assert all("edge_ref" in step.provenance for step in publication_steps)

    first_publication_node_id = publication_steps[0].node_id
    approval_edge = next(
        edge
        for edge in plan.dag_structure["edges"]
        if edge["from"] == "approval_gate" and edge["to"] == first_publication_node_id
    )
    assert approval_edge["condition"] == "{{approved_at}}"


@pytest.mark.django_db
def test_compile_pool_execution_plan_includes_master_data_gate_when_document_plan_contains_master_data_tokens() -> None:
    tenant = Tenant.objects.create(
        slug=f"pool-atomic-master-data-{uuid4().hex[:8]}",
        name="Pool Atomic Master Data",
    )
    schema_template = _create_schema_template(tenant=tenant, code="atomic-master-data-template")
    _sync_runtime_templates()

    artifact = _build_document_plan_artifact()
    artifact["targets"][0]["chains"][0]["documents"][0]["field_mapping"] = {
        "Контрагент_Key": "master_data.party.party-001.counterparty.ref",
    }

    with patch(
        "apps.intercompany_pools.workflow_compiler.resolve_pool_master_data_gate_flag",
        return_value=PoolMasterDataGateResolution(
            source="tenant_override",
            raw_value=False,
            value=False,
        ),
    ):
        plan = compile_pool_execution_plan(
            schema_template=schema_template,
            run_context=_create_context(
                mode=PoolRunMode.SAFE,
                document_plan_artifact=artifact,
            ),
        )

    node_ids = [node["id"] for node in plan.dag_structure["nodes"]]
    publication_node_ids = [
        node_id
        for node_id in node_ids
        if node_id.startswith("publication_odata__")
    ]
    assert node_ids[:5] == [
        "prepare_input",
        "distribution_calculation",
        "reconciliation_report",
        "approval_gate",
        "master_data_gate",
    ]
    assert len(publication_node_ids) == 2
    approval_edge = next(
        edge
        for edge in plan.dag_structure["edges"]
        if edge["from"] == "approval_gate" and edge["to"] == "master_data_gate"
    )
    assert approval_edge["condition"] == "{{approved_at}}"
    gate_edges = [
        edge
        for edge in plan.dag_structure["edges"]
        if edge["from"] == "master_data_gate"
    ]
    assert gate_edges == [{"from": "master_data_gate", "to": publication_node_ids[0]}]


@pytest.mark.django_db
def test_compile_pool_execution_plan_atomic_publication_node_ids_are_deterministic() -> None:
    tenant = Tenant.objects.create(slug=f"pool-atomic-deterministic-{uuid4().hex[:8]}", name="Pool Atomic Deterministic")
    schema_template = _create_schema_template(tenant=tenant, code="atomic-deterministic-template")
    _sync_runtime_templates()

    artifact = _build_document_plan_artifact()
    context = _create_context(mode=PoolRunMode.SAFE, document_plan_artifact=artifact)
    plan_1 = compile_pool_execution_plan(schema_template=schema_template, run_context=context)
    plan_2 = compile_pool_execution_plan(schema_template=schema_template, run_context=context)

    publication_ids_1 = [step.node_id for step in plan_1.steps if step.operation_alias == "pool.publication_odata"]
    publication_ids_2 = [step.node_id for step in plan_2.steps if step.operation_alias == "pool.publication_odata"]

    assert publication_ids_1 == publication_ids_2


@pytest.mark.django_db
def test_compile_pool_execution_plan_fails_closed_when_required_invoice_step_is_missing() -> None:
    tenant = Tenant.objects.create(slug=f"pool-atomic-invoice-{uuid4().hex[:8]}", name="Pool Atomic Invoice")
    schema_template = _create_schema_template(tenant=tenant, code="atomic-invoice-template")
    _sync_runtime_templates()

    artifact = _build_document_plan_artifact()
    artifact["targets"][0]["chains"][0]["documents"] = [
        {
            "document_id": "sale-doc",
            "entity_name": "Document_Sales",
            "document_role": "base",
            "field_mapping": {},
            "table_parts_mapping": {},
            "link_rules": {},
            "invoice_mode": "required",
            "idempotency_key": "doc-sale-key",
        }
    ]

    with pytest.raises(ValueError, match="POOL_RUNTIME_REQUIRED_INVOICE_STEP_MISSING"):
        compile_pool_execution_plan(
            schema_template=schema_template,
            run_context=_create_context(
                mode=PoolRunMode.SAFE,
                document_plan_artifact=artifact,
            ),
        )


@pytest.mark.django_db
def test_compile_pool_execution_plan_uses_direction_specific_distribution_alias() -> None:
    tenant = Tenant.objects.create(slug=f"pool-direction-{uuid4().hex[:8]}", name="Pool Direction")
    schema_template = _create_schema_template(tenant=tenant, code="direction-template")
    _sync_runtime_templates()

    top_down = compile_pool_execution_plan(
        schema_template=schema_template,
        run_context=_create_context(direction=PoolRunDirection.TOP_DOWN),
    )
    bottom_up = compile_pool_execution_plan(
        schema_template=schema_template,
        run_context=_create_context(direction=PoolRunDirection.BOTTOM_UP),
    )

    top_down_alias = next(
        node["template_id"]
        for node in top_down.dag_structure["nodes"]
        if node["id"] == "distribution_calculation"
    )
    bottom_up_alias = next(
        node["template_id"]
        for node in bottom_up.dag_structure["nodes"]
        if node["id"] == "distribution_calculation"
    )

    assert top_down_alias == "pool.distribution_calculation.top_down"
    assert bottom_up_alias == "pool.distribution_calculation.bottom_up"
    assert top_down_alias != bottom_up_alias
    assert top_down.plan_key != bottom_up.plan_key


@pytest.mark.django_db
def test_compile_pool_execution_plan_builds_new_definition_when_template_version_changes() -> None:
    tenant = Tenant.objects.create(slug=f"pool-template-version-{uuid4().hex[:8]}", name="Pool Template Version")
    schema_template = _create_schema_template(tenant=tenant, code="template-version")
    _sync_runtime_templates()

    shared_pool_id = str(uuid4())
    plan_before = compile_pool_execution_plan(
        schema_template=schema_template,
        run_context=_create_context(pool_id=shared_pool_id),
    )

    schema_template.schema = {
        "columns": {
            "inn": "inn",
            "amount": "amount",
            "kpp": "kpp",
        }
    }
    schema_template.save(update_fields=["schema"])

    plan_after = compile_pool_execution_plan(
        schema_template=schema_template,
        run_context=_create_context(pool_id=shared_pool_id),
    )

    assert plan_before.plan_key != plan_after.plan_key
    assert plan_before.workflow_template_name != plan_after.workflow_template_name


@pytest.mark.django_db
def test_compiled_plan_builds_valid_workflow_template() -> None:
    tenant = Tenant.objects.create(slug=f"pool-template-{uuid4().hex[:8]}", name="Pool Template")
    schema_template = _create_schema_template(tenant=tenant, code="workflow-template")
    context = _create_context()
    _sync_runtime_templates()

    compiler = PoolWorkflowCompiler()
    plan = compiler.compile(schema_template=schema_template, run_context=context)
    workflow_template = plan.build_workflow_template()

    assert workflow_template.name == plan.workflow_template_name
    assert workflow_template.workflow_type == "sequential"
    assert workflow_template.is_valid is True
    assert len(workflow_template.dag_structure.nodes) == len(plan.steps)
    assert workflow_template.config.timeout_seconds == 86400
    assert plan.workflow_binding_hint == "legacy-binding-hint"


@pytest.mark.django_db
def test_compile_pool_execution_plan_builds_pinned_operation_refs() -> None:
    tenant = Tenant.objects.create(slug=f"pool-pinned-{uuid4().hex[:8]}", name="Pool Pinned")
    schema_template = _create_schema_template(tenant=tenant, code="pinned-template")
    _sync_runtime_templates()

    plan = compile_pool_execution_plan(schema_template=schema_template, run_context=_create_context())
    for node in plan.dag_structure["nodes"]:
        operation_ref = node["operation_ref"]
        assert operation_ref["binding_mode"] == "pinned_exposure"
        assert operation_ref["template_exposure_id"]
        assert int(operation_ref["template_exposure_revision"]) >= 1


@pytest.mark.django_db
def test_compile_pool_execution_plan_fails_closed_when_required_alias_missing() -> None:
    tenant = Tenant.objects.create(slug=f"pool-missing-{uuid4().hex[:8]}", name="Pool Missing")
    schema_template = _create_schema_template(tenant=tenant, code="missing-template")
    _sync_runtime_templates()
    OperationExposure.objects.filter(
        surface=OperationExposure.SURFACE_TEMPLATE,
        tenant__isnull=True,
        alias="pool.prepare_input",
    ).delete()

    with pytest.raises(ValueError, match="POOL_RUNTIME_TEMPLATE_NOT_CONFIGURED"):
        compile_pool_execution_plan(schema_template=schema_template, run_context=_create_context())
