from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

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
    direction: str = PoolRunDirection.BOTTOM_UP,
    mode: str = PoolRunMode.SAFE,
) -> PoolWorkflowRunContext:
    return PoolWorkflowRunContext(
        pool_id=str(uuid4()),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        direction=direction,
        mode=mode,
        run_input={"source_payload": [{"inn": "770000000001", "amount": "10.00"}]},
    )


def _sync_runtime_templates() -> None:
    sync_pool_runtime_template_registry()


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
def test_compile_pool_execution_plan_safe_mode_includes_approval_gate() -> None:
    tenant = Tenant.objects.create(slug=f"pool-safe-{uuid4().hex[:8]}", name="Pool Safe")
    schema_template = _create_schema_template(tenant=tenant, code="safe-template")
    context = _create_context(mode=PoolRunMode.SAFE)
    _sync_runtime_templates()

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
