from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolEdgeVersion,
    PoolNodeVersion,
    PoolRun,
    PoolRunDirection,
    PoolRunMode,
)
from apps.intercompany_pools.pool_domain_steps import execute_pool_runtime_step
from apps.intercompany_pools.runtime_distribution import DISTRIBUTION_ARTIFACT_VERSION
from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate, WorkflowType
from apps.tenancy.models import Tenant


def _create_pool_run(
    *,
    mode: str,
    direction: str = PoolRunDirection.BOTTOM_UP,
    run_input: dict[str, object] | None = None,
) -> PoolRun:
    tenant = Tenant.objects.create(
        slug=f"pool-domain-{uuid4().hex[:8]}",
        name="Pool Domain",
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Pool Domain",
    )
    payload: dict[str, object] = (
        dict(run_input)
        if isinstance(run_input, dict)
        else {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]}
    )
    run = PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        mode=mode,
        direction=direction,
        period_start=date(2026, 1, 1),
        run_input=payload,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save(update_fields=["status", "validated_at", "validation_summary", "diagnostics", "updated_at"])
    return run


def _attach_execution(*, run: PoolRun, input_context: dict[str, object]) -> WorkflowExecution:
    template = WorkflowTemplate.objects.create(
        name=f"pool-domain-{run.id.hex[:8]}",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {
                    "id": "pool_step",
                    "name": "Pool Step",
                    "type": "operation",
                    "template_id": "pool.prepare_input",
                }
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
    )
    execution = template.create_execution(
        input_context,
        tenant=run.tenant,
        execution_consumer="pools",
    )
    run.workflow_execution_id = execution.id
    run.workflow_status = execution.status
    run.execution_backend = "workflow_core"
    run.workflow_template_name = template.name
    run.save(
        update_fields=[
            "workflow_execution_id",
            "workflow_status",
            "execution_backend",
            "workflow_template_name",
            "updated_at",
        ]
    )
    return execution


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"pool-domain-db-{suffix}-{uuid4().hex[:8]}",
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="pool-user",
        password="pool-pass",
    )


def _attach_active_topology(*, run: PoolRun) -> dict[str, str]:
    root_org = Organization.objects.create(
        tenant=run.tenant,
        name=f"Root {uuid4().hex[:6]}",
        inn=f"73{uuid4().hex[:10]}",
    )
    left_db = _create_database(tenant=run.tenant, suffix="left")
    right_db = _create_database(tenant=run.tenant, suffix="right")
    left_org = Organization.objects.create(
        tenant=run.tenant,
        database=left_db,
        name=f"Left {uuid4().hex[:6]}",
        inn=f"74{uuid4().hex[:10]}",
    )
    right_org = Organization.objects.create(
        tenant=run.tenant,
        database=right_db,
        name=f"Right {uuid4().hex[:6]}",
        inn=f"75{uuid4().hex[:10]}",
    )

    root_node = PoolNodeVersion.objects.create(
        pool=run.pool,
        organization=root_org,
        effective_from=run.period_start,
        is_root=True,
    )
    left_node = PoolNodeVersion.objects.create(
        pool=run.pool,
        organization=left_org,
        effective_from=run.period_start,
    )
    right_node = PoolNodeVersion.objects.create(
        pool=run.pool,
        organization=right_org,
        effective_from=run.period_start,
    )
    PoolEdgeVersion.objects.create(
        pool=run.pool,
        parent_node=root_node,
        child_node=left_node,
        weight=Decimal("0.6"),
        effective_from=run.period_start,
    )
    PoolEdgeVersion.objects.create(
        pool=run.pool,
        parent_node=root_node,
        child_node=right_node,
        weight=Decimal("0.4"),
        effective_from=run.period_start,
    )
    return {
        "left_inn": left_org.inn,
        "right_inn": right_org.inn,
        "left_database_id": str(left_db.id),
        "right_database_id": str(right_db.id),
        "left_node_id": str(left_node.id),
        "right_node_id": str(right_node.id),
    }


@pytest.mark.django_db
def test_prepare_input_updates_safe_context_states() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "approval_state": "preparing",
            "publication_step_state": "not_enqueued",
            "approved_at": None,
        },
    )

    output = execute_pool_runtime_step(
        operation_type="pool.prepare_input",
        rendered_data={"pool_runtime": {"step_id": "prepare_input"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )

    execution.refresh_from_db(fields=["input_context"])
    assert output["step"] == "prepare_input"
    assert output["approval_state"] == "preparing"
    assert output["publication_step_state"] == "not_enqueued"
    assert execution.input_context.get("approval_state") == "preparing"
    assert execution.input_context.get("publication_step_state") == "not_enqueued"


@pytest.mark.django_db
def test_approval_gate_sets_awaiting_approval_for_safe_unconfirmed_run() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "approval_state": "preparing",
            "publication_step_state": "not_enqueued",
            "approved_at": None,
        },
    )

    output = execute_pool_runtime_step(
        operation_type="pool.approval_gate",
        rendered_data={"pool_runtime": {"step_id": "approval_gate"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )

    execution.refresh_from_db(fields=["input_context"])
    assert output["step"] == "approval_gate"
    assert output["awaiting_approval"] is True
    assert execution.input_context.get("approval_state") == "awaiting_approval"
    assert execution.input_context.get("publication_step_state") == "not_enqueued"


@pytest.mark.django_db
def test_distribution_top_down_stores_artifact_and_calculated_publication_payload() -> None:
    run = _create_pool_run(
        mode=PoolRunMode.UNSAFE,
        direction=PoolRunDirection.TOP_DOWN,
        run_input={
            "starting_amount": "100.00",
            "entity_name": "Document_IntercompanyPoolDistribution",
            "documents_by_database": {"db-raw-override": [{"Amount": "999.00"}]},
            "max_attempts": 2,
            "retry_interval_seconds": 5,
            "external_key_field": "ExternalRunKey",
        },
    )
    topology = _attach_active_topology(run=run)
    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "approval_state": "not_required",
            "publication_step_state": "queued",
            "approved_at": None,
        },
    )

    output = execute_pool_runtime_step(
        operation_type="pool.distribution_calculation.top_down",
        rendered_data={"pool_runtime": {"step_id": "distribution_calculation"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )

    execution.refresh_from_db(fields=["input_context"])
    artifact = output["distribution_artifact"]
    assert artifact["version"] == DISTRIBUTION_ARTIFACT_VERSION
    assert artifact["coverage"]["is_full"] is True
    assert artifact["balance"]["is_balanced"] is True
    publication_payload = output["publication_payload"]["pool_runtime"]
    documents_by_database = publication_payload["documents_by_database"]
    assert set(documents_by_database.keys()) == {
        topology["left_database_id"],
        topology["right_database_id"],
    }
    assert "db-raw-override" not in documents_by_database
    distributed_total = sum(
        Decimal(str(doc.get("Amount")))
        for documents in documents_by_database.values()
        for doc in documents
    )
    assert distributed_total == Decimal("100.00")
    assert execution.input_context.get("pool_runtime_distribution_artifact", {}).get(
        "version"
    ) == DISTRIBUTION_ARTIFACT_VERSION
    assert execution.input_context.get("pool_runtime_publication_payload") == output["publication_payload"]


@pytest.mark.django_db
def test_distribution_bottom_up_converges_to_root_total() -> None:
    run = _create_pool_run(
        mode=PoolRunMode.UNSAFE,
        direction=PoolRunDirection.BOTTOM_UP,
    )
    topology = _attach_active_topology(run=run)
    run.run_input = {
        "source_payload": [
            {"inn": topology["left_inn"], "amount": "70.00"},
            {"inn": topology["right_inn"], "amount": "30.00"},
        ],
        "entity_name": "Document_IntercompanyPoolDistribution",
        "documents_by_database": {"db-raw-override": [{"Amount": "999.00"}]},
        "max_attempts": 3,
    }
    run.save(update_fields=["run_input", "updated_at"])
    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "approval_state": "not_required",
            "publication_step_state": "queued",
            "approved_at": None,
        },
    )

    output = execute_pool_runtime_step(
        operation_type="pool.distribution_calculation.bottom_up",
        rendered_data={"pool_runtime": {"step_id": "distribution_calculation"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )

    artifact = output["distribution_artifact"]
    assert artifact["version"] == DISTRIBUTION_ARTIFACT_VERSION
    assert artifact["balance"]["source_total"] == "100.00"
    assert artifact["balance"]["distributed_total"] == "100.00"
    assert artifact["balance"]["is_balanced"] is True
    assert artifact["coverage"]["is_full"] is True
    publication_payload = output["publication_payload"]["pool_runtime"]
    documents_by_database = publication_payload["documents_by_database"]
    assert set(documents_by_database.keys()) == {
        topology["left_database_id"],
        topology["right_database_id"],
    }
    assert "db-raw-override" not in documents_by_database


@pytest.mark.django_db
def test_reconciliation_fails_closed_on_balance_mismatch() -> None:
    run = _create_pool_run(
        mode=PoolRunMode.UNSAFE,
        direction=PoolRunDirection.TOP_DOWN,
        run_input={"starting_amount": "100.00"},
    )
    _attach_active_topology(run=run)
    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "approval_state": "not_required",
            "publication_step_state": "queued",
            "approved_at": None,
        },
    )
    execute_pool_runtime_step(
        operation_type="pool.distribution_calculation.top_down",
        rendered_data={"pool_runtime": {"step_id": "distribution_calculation"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )
    execution.refresh_from_db(fields=["input_context"])
    artifact = dict(execution.input_context.get("pool_runtime_distribution_artifact") or {})
    balance = dict(artifact.get("balance") or {})
    balance["is_balanced"] = False
    balance["source_total"] = "100.00"
    balance["distributed_total"] = "99.00"
    balance["delta"] = "1.00"
    artifact["balance"] = balance
    execution.input_context = {
        **execution.input_context,
        "pool_runtime_distribution_artifact": artifact,
    }
    execution.save(update_fields=["input_context"])

    with pytest.raises(ValueError, match="POOL_DISTRIBUTION_BALANCE_MISMATCH"):
        execute_pool_runtime_step(
            operation_type="pool.reconciliation_report",
            rendered_data={"pool_runtime": {"step_id": "reconciliation_report"}},
            context={"pool_run_id": str(run.id)},
            execution=execution,
        )


@pytest.mark.django_db
def test_reconciliation_fails_closed_on_coverage_gap() -> None:
    run = _create_pool_run(
        mode=PoolRunMode.UNSAFE,
        direction=PoolRunDirection.TOP_DOWN,
        run_input={"starting_amount": "100.00"},
    )
    topology = _attach_active_topology(run=run)
    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "approval_state": "not_required",
            "publication_step_state": "queued",
            "approved_at": None,
        },
    )
    execute_pool_runtime_step(
        operation_type="pool.distribution_calculation.top_down",
        rendered_data={"pool_runtime": {"step_id": "distribution_calculation"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )
    execution.refresh_from_db(fields=["input_context"])
    artifact = dict(execution.input_context.get("pool_runtime_distribution_artifact") or {})
    coverage = dict(artifact.get("coverage") or {})
    coverage["is_full"] = False
    coverage["missing_target_node_ids"] = [topology["left_node_id"]]
    artifact["coverage"] = coverage
    execution.input_context = {
        **execution.input_context,
        "pool_runtime_distribution_artifact": artifact,
    }
    execution.save(update_fields=["input_context"])

    with pytest.raises(ValueError, match="POOL_DISTRIBUTION_COVERAGE_GAP"):
        execute_pool_runtime_step(
            operation_type="pool.reconciliation_report",
            rendered_data={"pool_runtime": {"step_id": "reconciliation_report"}},
            context={"pool_run_id": str(run.id)},
            execution=execution,
        )


@pytest.mark.django_db
def test_reconciliation_fails_closed_on_invalid_distribution_artifact() -> None:
    run = _create_pool_run(
        mode=PoolRunMode.UNSAFE,
        direction=PoolRunDirection.TOP_DOWN,
        run_input={"starting_amount": "100.00"},
    )
    _attach_active_topology(run=run)
    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "approval_state": "not_required",
            "publication_step_state": "queued",
            "approved_at": None,
        },
    )
    execute_pool_runtime_step(
        operation_type="pool.distribution_calculation.top_down",
        rendered_data={"pool_runtime": {"step_id": "distribution_calculation"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )
    execution.refresh_from_db(fields=["input_context"])
    artifact = dict(execution.input_context.get("pool_runtime_distribution_artifact") or {})
    artifact.pop("coverage", None)
    execution.input_context = {
        **execution.input_context,
        "pool_runtime_distribution_artifact": artifact,
    }
    execution.save(update_fields=["input_context"])

    with pytest.raises(ValueError, match="POOL_DISTRIBUTION_ARTIFACT_INVALID"):
        execute_pool_runtime_step(
            operation_type="pool.reconciliation_report",
            rendered_data={"pool_runtime": {"step_id": "reconciliation_report"}},
            context={"pool_run_id": str(run.id)},
            execution=execution,
        )


@pytest.mark.django_db
def test_publication_step_is_fail_closed_for_safe_mode() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "approval_state": "awaiting_approval",
            "publication_step_state": "not_enqueued",
            "approved_at": None,
        },
    )

    with pytest.raises(ValueError, match="POOL_RUNTIME_PUBLICATION_PATH_DISABLED"):
        execute_pool_runtime_step(
            operation_type="pool.publication_odata",
            rendered_data={"pool_runtime": {"step_id": "publication_odata"}},
            context={"pool_run_id": str(run.id)},
            execution=execution,
        )

    execution.refresh_from_db(fields=["input_context"])
    assert execution.input_context.get("publication_step_state") == "not_enqueued"


@pytest.mark.django_db
def test_publication_step_is_fail_closed_for_unsafe_mode() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)
    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "approval_state": "not_required",
            "publication_step_state": "queued",
            "approved_at": None,
        },
    )

    with pytest.raises(ValueError, match="POOL_RUNTIME_PUBLICATION_PATH_DISABLED"):
        execute_pool_runtime_step(
            operation_type="pool.publication_odata",
            rendered_data={"pool_runtime": {"step_id": "publication_odata"}},
            context={"pool_run_id": str(run.id)},
            execution=execution,
        )

    execution.refresh_from_db(fields=["input_context"])
    assert execution.input_context.get("publication_step_state") == "queued"
