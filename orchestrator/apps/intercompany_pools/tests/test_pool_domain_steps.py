from __future__ import annotations

from datetime import date
from decimal import Decimal
import json
from uuid import uuid4
from unittest.mock import patch

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.document_plan_artifact_contract import (
    DOCUMENT_PLAN_ARTIFACT_VERSION,
    POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY,
)
from apps.intercompany_pools.master_data_artifact_contract import (
    POOL_RUNTIME_MASTER_DATA_BINDING_ARTIFACT_CONTEXT_KEY,
)
from apps.intercompany_pools.document_policy_contract import (
    DOCUMENT_POLICY_METADATA_KEY,
    DOCUMENT_POLICY_RESOLUTION_SOURCE_EDGE,
    DOCUMENT_POLICY_RESOLUTION_SOURCE_POOL_DEFAULT,
    POOL_DOCUMENT_POLICY_CHAIN_INVALID,
    POOL_DOCUMENT_POLICY_MAPPING_INVALID,
)
from apps.intercompany_pools.master_data_feature_flags import MasterDataGateConfigInvalidError
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolEdgeVersion,
    PoolMasterContract,
    PoolNodeVersion,
    PoolMasterParty,
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
    period_start: date = date(2026, 1, 1),
    period_end: date | None = None,
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
        period_start=period_start,
        period_end=period_end,
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


def _build_document_policy(*, chain_id: str = "sale_chain") -> dict[str, object]:
    return {
        "version": "document_policy.v1",
        "chains": [
            {
                "chain_id": chain_id,
                "documents": [
                    {
                        "document_id": "sale",
                        "entity_name": "Document_Sales",
                        "document_role": "sale",
                        "field_mapping": {"Amount": "allocation.amount"},
                        "table_parts_mapping": {},
                        "link_rules": {},
                    },
                    {
                        "document_id": "invoice",
                        "entity_name": "Document_Invoice",
                        "document_role": "invoice",
                        "field_mapping": {"BaseDocument": "sale.ref"},
                        "table_parts_mapping": {},
                        "link_rules": {"depends_on": "sale"},
                        "link_to": "sale",
                        "invoice_mode": "required",
                    },
                ],
            }
        ],
    }


def _attach_active_topology(
    *,
    run: PoolRun,
    left_edge_metadata: dict[str, object] | None = None,
    right_edge_metadata: dict[str, object] | None = None,
    pool_metadata: dict[str, object] | None = None,
) -> dict[str, str]:
    if isinstance(pool_metadata, dict):
        run.pool.metadata = dict(pool_metadata)
        run.pool.save(update_fields=["metadata", "updated_at"])

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
        metadata=dict(left_edge_metadata) if isinstance(left_edge_metadata, dict) else {},
    )
    PoolEdgeVersion.objects.create(
        pool=run.pool,
        parent_node=root_node,
        child_node=right_node,
        weight=Decimal("0.4"),
        effective_from=run.period_start,
        metadata=dict(right_edge_metadata) if isinstance(right_edge_metadata, dict) else {},
    )
    return {
        "left_inn": left_org.inn,
        "right_inn": right_org.inn,
        "left_database_id": str(left_db.id),
        "right_database_id": str(right_db.id),
        "left_node_id": str(left_node.id),
        "right_node_id": str(right_node.id),
    }


def _attach_interval_topology_with_rotating_targets(*, run: PoolRun) -> dict[str, str]:
    if run.period_end is None:
        raise AssertionError("run.period_end must be set for interval topology fixture")

    first_day = run.period_start
    second_day = run.period_end

    root_day_1 = Organization.objects.create(
        tenant=run.tenant,
        name=f"Root Day 1 {uuid4().hex[:6]}",
        inn=f"76{uuid4().hex[:10]}",
    )
    root_day_2 = Organization.objects.create(
        tenant=run.tenant,
        name=f"Root Day 2 {uuid4().hex[:6]}",
        inn=f"77{uuid4().hex[:10]}",
    )

    first_db = _create_database(tenant=run.tenant, suffix="interval-first")
    second_db = _create_database(tenant=run.tenant, suffix="interval-second")
    first_org = Organization.objects.create(
        tenant=run.tenant,
        database=first_db,
        name=f"First Target {uuid4().hex[:6]}",
        inn=f"78{uuid4().hex[:10]}",
    )
    second_org = Organization.objects.create(
        tenant=run.tenant,
        database=second_db,
        name=f"Second Target {uuid4().hex[:6]}",
        inn=f"79{uuid4().hex[:10]}",
    )

    root_node_day_1 = PoolNodeVersion.objects.create(
        pool=run.pool,
        organization=root_day_1,
        effective_from=first_day,
        effective_to=first_day,
        is_root=True,
    )
    first_target_node = PoolNodeVersion.objects.create(
        pool=run.pool,
        organization=first_org,
        effective_from=first_day,
        effective_to=first_day,
    )
    PoolEdgeVersion.objects.create(
        pool=run.pool,
        parent_node=root_node_day_1,
        child_node=first_target_node,
        effective_from=first_day,
        effective_to=first_day,
        weight=Decimal("1"),
    )

    root_node_day_2 = PoolNodeVersion.objects.create(
        pool=run.pool,
        organization=root_day_2,
        effective_from=second_day,
        is_root=True,
    )
    second_target_node = PoolNodeVersion.objects.create(
        pool=run.pool,
        organization=second_org,
        effective_from=second_day,
    )
    PoolEdgeVersion.objects.create(
        pool=run.pool,
        parent_node=root_node_day_2,
        child_node=second_target_node,
        effective_from=second_day,
        weight=Decimal("1"),
    )

    return {
        "first_target_inn": first_org.inn,
        "second_target_inn": second_org.inn,
        "first_database_id": str(first_db.id),
        "second_database_id": str(second_db.id),
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
def test_distribution_top_down_rejects_raw_run_input_bypass_keys_for_artifacts() -> None:
    run = _create_pool_run(
        mode=PoolRunMode.UNSAFE,
        direction=PoolRunDirection.TOP_DOWN,
        run_input={
            "starting_amount": "100.00",
            "entity_name": "Document_IntercompanyPoolDistribution",
            "documents_by_database": {"db-raw-override": [{"Amount": "999.00"}]},
            "distribution_artifact": {"version": "distribution_artifact.v1", "topology_version_ref": "raw"},
            "pool_runtime_distribution_artifact": {"version": "distribution_artifact.v1"},
            "document_plan_artifact": {"version": "document_plan_artifact.v1"},
            "pool_runtime_publication_payload": {
                "pool_runtime": {
                    "entity_name": "Document_IntercompanyPoolDistribution",
                    "documents_by_database": {"db-bypass": [{"Amount": "777.00"}]},
                }
            },
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

    artifact = output["distribution_artifact"]
    assert artifact["version"] == DISTRIBUTION_ARTIFACT_VERSION
    assert artifact["topology_version_ref"] != "raw"
    publication_payload = output["publication_payload"]["pool_runtime"]
    documents_by_database = publication_payload["documents_by_database"]
    assert set(documents_by_database.keys()) == {
        topology["left_database_id"],
        topology["right_database_id"],
    }
    assert "db-raw-override" not in documents_by_database
    assert "db-bypass" not in documents_by_database


@pytest.mark.django_db
def test_reconciliation_without_document_policy_keeps_legacy_create_run_path() -> None:
    run = _create_pool_run(
        mode=PoolRunMode.UNSAFE,
        direction=PoolRunDirection.TOP_DOWN,
        run_input={
            "starting_amount": "100.00",
            "entity_name": "Document_IntercompanyPoolDistribution",
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

    distribution_output = execute_pool_runtime_step(
        operation_type="pool.distribution_calculation.top_down",
        rendered_data={"pool_runtime": {"step_id": "distribution_calculation"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )
    reconciliation_output = execute_pool_runtime_step(
        operation_type="pool.reconciliation_report",
        rendered_data={"pool_runtime": {"step_id": "reconciliation_report"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )

    documents_by_database = reconciliation_output["publication_payload"]["pool_runtime"]["documents_by_database"]
    assert set(documents_by_database.keys()) == {
        topology["left_database_id"],
        topology["right_database_id"],
    }
    assert reconciliation_output["report"]["status"] == "ok"
    assert reconciliation_output["distribution_artifact"]["version"] == DISTRIBUTION_ARTIFACT_VERSION

    execution.refresh_from_db(fields=["input_context"])
    assert execution.input_context.get("pool_runtime_publication_payload") == distribution_output["publication_payload"]
    assert "document_plan_artifact" not in execution.input_context
    assert "pool_runtime_document_plan_artifact" not in execution.input_context


@pytest.mark.django_db
def test_reconciliation_compiles_document_plan_artifact_from_edge_policy() -> None:
    run = _create_pool_run(
        mode=PoolRunMode.UNSAFE,
        direction=PoolRunDirection.TOP_DOWN,
        run_input={
            "starting_amount": "100.00",
            "entity_name": "Document_Raw_Bypass",
            "documents_by_database": {"db-raw-bypass": [{"Amount": "999.00"}]},
            "max_attempts": 3,
            "retry_interval_seconds": 5,
            "external_key_field": "ExternalRunKey",
        },
    )
    edge_policy = _build_document_policy(chain_id="edge_chain")
    topology = _attach_active_topology(
        run=run,
        left_edge_metadata={DOCUMENT_POLICY_METADATA_KEY: edge_policy},
    )
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
    reconciliation_output = execute_pool_runtime_step(
        operation_type="pool.reconciliation_report",
        rendered_data={"pool_runtime": {"step_id": "reconciliation_report"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )

    artifact = reconciliation_output.get("document_plan_artifact")
    assert isinstance(artifact, dict)
    assert artifact["version"] == DOCUMENT_PLAN_ARTIFACT_VERSION
    assert artifact["run_id"] == str(run.id)
    assert artifact["distribution_artifact_ref"]["version"] == DISTRIBUTION_ARTIFACT_VERSION
    assert artifact["topology_version_ref"] == reconciliation_output["distribution_artifact"]["topology_version_ref"]
    assert any(
        ref.get("source") == DOCUMENT_POLICY_RESOLUTION_SOURCE_EDGE
        for ref in artifact["policy_refs"]
        if isinstance(ref, dict)
    )

    target_ids = {
        str(target.get("database_id") or "").strip()
        for target in artifact["targets"]
        if isinstance(target, dict)
    }
    assert topology["left_database_id"] in target_ids

    left_target = next(
        (
            target
            for target in artifact["targets"]
            if isinstance(target, dict) and target.get("database_id") == topology["left_database_id"]
        ),
        None,
    )
    assert isinstance(left_target, dict)
    documents = left_target["chains"][0]["documents"]
    assert documents[0]["idempotency_key"].startswith("doc-plan:")
    assert documents[0]["invoice_mode"] == "optional"
    assert documents[1]["invoice_mode"] == "required"

    publication_payload = reconciliation_output["publication_payload"]["pool_runtime"]
    assert publication_payload["entity_name"] == "Document_Sales"
    assert publication_payload["documents_by_database"] == {
        topology["left_database_id"]: [{"Amount": "60.00"}]
    }
    assert "db-raw-bypass" not in publication_payload["documents_by_database"]
    chains_by_database = publication_payload.get("document_chains_by_database")
    assert isinstance(chains_by_database, dict)
    assert topology["left_database_id"] in chains_by_database
    chain_documents = chains_by_database[topology["left_database_id"]][0]["documents"]
    assert [item.get("entity_name") for item in chain_documents] == [
        "Document_Sales",
        "Document_Invoice",
    ]

    execution.refresh_from_db(fields=["input_context"])
    assert (
        execution.input_context.get(POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY)
        == artifact
    )


@pytest.mark.django_db
def test_reconciliation_document_plan_uses_pool_default_policy_when_edge_policy_missing() -> None:
    run = _create_pool_run(
        mode=PoolRunMode.UNSAFE,
        direction=PoolRunDirection.TOP_DOWN,
        run_input={
            "starting_amount": "100.00",
            "entity_name": "Document_IntercompanyPoolDistribution",
        },
    )
    pool_default_policy = _build_document_policy(chain_id="pool_default_chain")
    topology = _attach_active_topology(
        run=run,
        pool_metadata={DOCUMENT_POLICY_METADATA_KEY: pool_default_policy},
    )
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
    reconciliation_output = execute_pool_runtime_step(
        operation_type="pool.reconciliation_report",
        rendered_data={"pool_runtime": {"step_id": "reconciliation_report"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )

    artifact = reconciliation_output.get("document_plan_artifact")
    assert isinstance(artifact, dict)

    sources = {
        str(ref.get("source") or "").strip()
        for ref in artifact["policy_refs"]
        if isinstance(ref, dict)
    }
    assert DOCUMENT_POLICY_RESOLUTION_SOURCE_POOL_DEFAULT in sources
    assert DOCUMENT_POLICY_RESOLUTION_SOURCE_EDGE not in sources

    target_ids = {
        str(target.get("database_id") or "").strip()
        for target in artifact["targets"]
        if isinstance(target, dict)
    }
    assert topology["left_database_id"] in target_ids
    assert topology["right_database_id"] in target_ids


@pytest.mark.django_db
def test_reconciliation_fail_closed_on_invalid_edge_document_policy() -> None:
    run = _create_pool_run(
        mode=PoolRunMode.UNSAFE,
        direction=PoolRunDirection.TOP_DOWN,
        run_input={
            "starting_amount": "100.00",
            "entity_name": "Document_IntercompanyPoolDistribution",
        },
    )
    invalid_policy = _build_document_policy()
    invalid_policy["chains"][0]["documents"][1]["invoice_mode"] = "always"
    _attach_active_topology(
        run=run,
        left_edge_metadata={DOCUMENT_POLICY_METADATA_KEY: invalid_policy},
    )
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

    with pytest.raises(ValueError, match=POOL_DOCUMENT_POLICY_CHAIN_INVALID):
        execute_pool_runtime_step(
            operation_type="pool.reconciliation_report",
            rendered_data={"pool_runtime": {"step_id": "reconciliation_report"}},
            context={"pool_run_id": str(run.id)},
            execution=execution,
        )


@pytest.mark.django_db
def test_reconciliation_fail_closed_on_missing_required_table_part_from_completeness_profile() -> None:
    run = _create_pool_run(
        mode=PoolRunMode.UNSAFE,
        direction=PoolRunDirection.TOP_DOWN,
        run_input={"starting_amount": "100.00"},
    )
    policy = _build_document_policy()
    policy["completeness_profiles"] = {
        "minimal_documents_full_payload": {
            "entities": {
                "Document_Sales": {
                    "required_fields": ["Amount"],
                    "required_table_parts": {
                        "Goods": {
                            "min_rows": 1,
                            "required_fields": ["Qty"],
                        }
                    },
                }
            }
        }
    }
    _attach_active_topology(
        run=run,
        left_edge_metadata={DOCUMENT_POLICY_METADATA_KEY: policy},
    )
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

    with pytest.raises(ValueError, match=POOL_DOCUMENT_POLICY_MAPPING_INVALID):
        execute_pool_runtime_step(
            operation_type="pool.reconciliation_report",
            rendered_data={"pool_runtime": {"step_id": "reconciliation_report"}},
            context={"pool_run_id": str(run.id)},
            execution=execution,
        )

    execution.refresh_from_db(fields=["input_context"])
    blockers = execution.input_context.get("pool_runtime_readiness_blockers")
    assert isinstance(blockers, list)
    assert blockers[0]["code"] == POOL_DOCUMENT_POLICY_MAPPING_INVALID
    assert blockers[0]["entity_name"] == "Document_Sales"
    assert blockers[0]["field_or_table_path"] == "Goods"

    execution.refresh_from_db(fields=["input_context"])
    assert POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY not in execution.input_context


@pytest.mark.django_db
def test_reconciliation_fail_closed_on_missing_required_header_field_from_completeness_profile() -> None:
    run = _create_pool_run(
        mode=PoolRunMode.UNSAFE,
        direction=PoolRunDirection.TOP_DOWN,
        run_input={"starting_amount": "100.00"},
    )
    policy = _build_document_policy()
    policy["chains"][0]["documents"][0]["field_mapping"] = {}
    policy["completeness_profiles"] = {
        "minimal_documents_full_payload": {
            "entities": {
                "Document_Sales": {
                    "required_fields": ["Amount"],
                    "required_table_parts": {},
                }
            }
        }
    }
    _attach_active_topology(
        run=run,
        left_edge_metadata={DOCUMENT_POLICY_METADATA_KEY: policy},
    )
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

    with pytest.raises(ValueError, match=POOL_DOCUMENT_POLICY_MAPPING_INVALID):
        execute_pool_runtime_step(
            operation_type="pool.reconciliation_report",
            rendered_data={"pool_runtime": {"step_id": "reconciliation_report"}},
            context={"pool_run_id": str(run.id)},
            execution=execution,
        )

    execution.refresh_from_db(fields=["input_context"])
    blockers = execution.input_context.get("pool_runtime_readiness_blockers")
    assert isinstance(blockers, list)
    assert blockers[0]["code"] == POOL_DOCUMENT_POLICY_MAPPING_INVALID
    assert blockers[0]["entity_name"] == "Document_Sales"
    assert blockers[0]["field_or_table_path"] == "Amount"

    execution.refresh_from_db(fields=["input_context"])
    assert POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY not in execution.input_context


@pytest.mark.django_db
def test_reconciliation_accepts_explicit_empty_string_for_required_header_field() -> None:
    run = _create_pool_run(
        mode=PoolRunMode.UNSAFE,
        direction=PoolRunDirection.TOP_DOWN,
        run_input={"starting_amount": "100.00"},
    )
    policy = _build_document_policy()
    policy["chains"][0]["documents"][0]["field_mapping"] = {
        "Amount": "allocation.amount",
        "DeliveryAddress": "",
    }
    policy["chains"][0]["documents"] = policy["chains"][0]["documents"][:1]
    policy["completeness_profiles"] = {
        "minimal_documents_full_payload": {
            "entities": {
                "Document_Sales": {
                    "required_fields": ["Amount", "DeliveryAddress"],
                    "required_table_parts": {},
                }
            }
        }
    }
    _attach_active_topology(
        run=run,
        left_edge_metadata={DOCUMENT_POLICY_METADATA_KEY: policy},
    )
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
    result = execute_pool_runtime_step(
        operation_type="pool.reconciliation_report",
        rendered_data={"pool_runtime": {"step_id": "reconciliation_report"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )

    assert result["document_plan_artifact"]["version"] == DOCUMENT_PLAN_ARTIFACT_VERSION
    execution.refresh_from_db(fields=["input_context"])
    assert execution.input_context[POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY]["version"] == (
        DOCUMENT_PLAN_ARTIFACT_VERSION
    )


@pytest.mark.django_db
def test_reconciliation_fail_closed_on_invalid_pool_default_document_policy() -> None:
    run = _create_pool_run(
        mode=PoolRunMode.UNSAFE,
        direction=PoolRunDirection.TOP_DOWN,
        run_input={
            "starting_amount": "100.00",
            "entity_name": "Document_IntercompanyPoolDistribution",
        },
    )
    invalid_pool_default_policy = _build_document_policy()
    invalid_pool_default_policy["chains"][0]["documents"][1]["invoice_mode"] = "always"
    _attach_active_topology(
        run=run,
        pool_metadata={DOCUMENT_POLICY_METADATA_KEY: invalid_pool_default_policy},
    )
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

    with pytest.raises(ValueError, match=POOL_DOCUMENT_POLICY_CHAIN_INVALID):
        execute_pool_runtime_step(
            operation_type="pool.reconciliation_report",
            rendered_data={"pool_runtime": {"step_id": "reconciliation_report"}},
            context={"pool_run_id": str(run.id)},
            execution=execution,
        )

    execution.refresh_from_db(fields=["input_context"])
    assert POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY not in execution.input_context


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
def test_distribution_top_down_aggregates_over_period_interval() -> None:
    run = _create_pool_run(
        mode=PoolRunMode.UNSAFE,
        direction=PoolRunDirection.TOP_DOWN,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 2),
        run_input={
            "starting_amount": "100.00",
            "entity_name": "Document_IntercompanyPoolDistribution",
        },
    )
    topology = _attach_interval_topology_with_rotating_targets(run=run)
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

    artifact = output["distribution_artifact"]
    assert artifact["coverage"]["is_full"] is True
    assert artifact["balance"]["is_balanced"] is True
    documents_by_database = output["publication_payload"]["pool_runtime"]["documents_by_database"]
    assert set(documents_by_database.keys()) == {
        topology["first_database_id"],
        topology["second_database_id"],
    }
    totals_by_database = {
        db_id: sum(Decimal(str(item.get("Amount"))) for item in docs)
        for db_id, docs in documents_by_database.items()
    }
    assert totals_by_database[topology["first_database_id"]] == Decimal("50.00")
    assert totals_by_database[topology["second_database_id"]] == Decimal("50.00")


@pytest.mark.django_db
def test_distribution_bottom_up_uses_row_dates_across_period_interval() -> None:
    run = _create_pool_run(
        mode=PoolRunMode.UNSAFE,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 2),
    )
    topology = _attach_interval_topology_with_rotating_targets(run=run)
    run.run_input = {
        "entity_name": "Document_IntercompanyPoolDistribution",
        "source_payload": [
            {"inn": topology["first_target_inn"], "amount": "40.00", "date": "2026-01-01"},
            {"inn": topology["second_target_inn"], "amount": "60.00", "date": "2026-01-02"},
        ],
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
    assert artifact["coverage"]["is_full"] is True
    assert artifact["balance"]["source_total"] == "100.00"
    assert artifact["balance"]["distributed_total"] == "100.00"
    assert artifact["balance"]["is_balanced"] is True
    documents_by_database = output["publication_payload"]["pool_runtime"]["documents_by_database"]
    assert set(documents_by_database.keys()) == {
        topology["first_database_id"],
        topology["second_database_id"],
    }
    totals_by_database = {
        db_id: sum(Decimal(str(item.get("Amount"))) for item in docs)
        for db_id, docs in documents_by_database.items()
    }
    assert totals_by_database[topology["first_database_id"]] == Decimal("40.00")
    assert totals_by_database[topology["second_database_id"]] == Decimal("60.00")


@pytest.mark.django_db
def test_retry_subset_payload_is_locked_when_flag_enabled() -> None:
    run = _create_pool_run(
        mode=PoolRunMode.UNSAFE,
        direction=PoolRunDirection.TOP_DOWN,
        run_input={
            "starting_amount": "100.00",
            "entity_name": "Document_IntercompanyPoolDistribution",
            "documents_by_database": {"db-raw-override": [{"Amount": "999.00"}]},
        },
    )
    topology = _attach_active_topology(run=run)
    locked_retry_payload = {
        "pool_runtime": {
            "entity_name": "Document_IntercompanyPoolDistribution",
            "documents_by_database": {
                topology["left_database_id"]: [{"Amount": "10.00"}],
            },
            "max_attempts": 1,
            "retry_interval_seconds": 0,
            "external_key_field": "ExternalRunKey",
        }
    }
    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "approval_state": "not_required",
            "publication_step_state": "queued",
            "approved_at": None,
            "pool_runtime_retry_settings": {"use_retry_subset_payload": True},
            "pool_runtime_publication_payload": locked_retry_payload,
        },
    )

    distribution_output = execute_pool_runtime_step(
        operation_type="pool.distribution_calculation.top_down",
        rendered_data={"pool_runtime": {"step_id": "distribution_calculation"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )
    assert distribution_output["publication_payload"] == locked_retry_payload

    reconciliation_output = execute_pool_runtime_step(
        operation_type="pool.reconciliation_report",
        rendered_data={"pool_runtime": {"step_id": "reconciliation_report"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )
    assert reconciliation_output["publication_payload"] == locked_retry_payload


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
def test_reconciliation_failure_does_not_store_reconciliation_output() -> None:
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
    distribution_output = execute_pool_runtime_step(
        operation_type="pool.distribution_calculation.top_down",
        rendered_data={"pool_runtime": {"step_id": "distribution_calculation"}},
        context={"pool_run_id": str(run.id)},
        execution=execution,
    )

    execution.refresh_from_db(fields=["input_context"])
    artifact = dict(execution.input_context.get("pool_runtime_distribution_artifact") or {})
    balance = dict(artifact.get("balance") or {})
    balance["is_balanced"] = False
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

    execution.refresh_from_db(fields=["input_context"])
    assert "pool_runtime_reconciliation" not in execution.input_context
    assert execution.input_context.get("pool_runtime_publication_payload") == distribution_output["publication_payload"]
    assert execution.input_context.get("publication_step_state") == "queued"


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
def test_master_data_gate_is_skipped_when_feature_is_disabled() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)
    database = _create_database(tenant=run.tenant, suffix="gate-skip")
    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "master_data_snapshot_ref": "master_data_snapshot.v1:test",
            "master_data_binding_artifact_ref": "master_data_binding_artifact.v1:test",
            "pool_runtime_publication_payload": {
                "pool_runtime": {
                    "document_chains_by_database": {
                        str(database.id): [
                            {
                                "chain_id": "sale-chain",
                                "documents": [
                                    {
                                        "document_id": "sale",
                                        "field_mapping": {},
                                        "table_parts_mapping": {},
                                    }
                                ],
                            }
                        ]
                    }
                }
            },
        },
    )

    with patch(
        "apps.intercompany_pools.pool_domain_steps.is_pool_master_data_gate_enabled",
        return_value=False,
    ):
        output = execute_pool_runtime_step(
            operation_type="pool.master_data_gate",
            rendered_data={"pool_runtime": {"step_id": "master_data_gate"}},
            context={"pool_run_id": str(run.id)},
            execution=execution,
        )

    assert output["step"] == "master_data_gate"
    assert output["summary"]["status"] == "skipped"

    execution.refresh_from_db(fields=["input_context"])
    gate_summary = execution.input_context.get("pool_runtime_master_data_gate")
    assert isinstance(gate_summary, dict)
    assert gate_summary.get("status") == "skipped"


@pytest.mark.django_db
def test_master_data_gate_executes_when_payload_contains_master_data_tokens_even_if_flag_is_disabled() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)
    database = _create_database(tenant=run.tenant, suffix="gate-force-resolve")
    PoolMasterParty.objects.create(
        tenant=run.tenant,
        canonical_id="party-001",
        name="Organization 001",
        is_our_organization=True,
        metadata={
            "ib_ref_keys": {
                str(database.id): {
                    "organization": "ref-organization-001",
                }
            }
        },
    )

    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "master_data_snapshot_ref": "master_data_snapshot.v1:test",
            "master_data_binding_artifact_ref": "master_data_binding_artifact.v1:test",
            "pool_runtime_publication_payload": {
                "pool_runtime": {
                    "document_chains_by_database": {
                        str(database.id): [
                            {
                                "chain_id": "sale-chain",
                                "documents": [
                                    {
                                        "document_id": "sale",
                                        "field_mapping": {
                                            "Организация": "master_data.party.party-001.organization.ref"
                                        },
                                        "table_parts_mapping": {},
                                    }
                                ],
                            }
                        ]
                    }
                }
            },
        },
    )

    with patch(
        "apps.intercompany_pools.pool_domain_steps.is_pool_master_data_gate_enabled",
        return_value=False,
    ):
        output = execute_pool_runtime_step(
            operation_type="pool.master_data_gate",
            rendered_data={"pool_runtime": {"step_id": "master_data_gate"}},
            context={"pool_run_id": str(run.id)},
            execution=execution,
        )

    assert output["step"] == "master_data_gate"
    assert output["summary"]["status"] == "completed"
    assert output["summary"]["bindings_count"] == 1

    execution.refresh_from_db(fields=["input_context"])
    gate_summary = execution.input_context.get("pool_runtime_master_data_gate")
    assert isinstance(gate_summary, dict)
    assert gate_summary.get("status") == "completed"
    publication_payload = execution.input_context["pool_runtime_publication_payload"]["pool_runtime"]
    resolved_master_data_refs = publication_payload["document_chains_by_database"][str(database.id)][0]["documents"][0][
        "resolved_master_data_refs"
    ]
    assert resolved_master_data_refs == {
        "master_data.party.party-001.organization.ref": "ref-organization-001",
    }


@pytest.mark.django_db
def test_master_data_gate_fails_closed_when_feature_flag_config_is_invalid() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)
    publication_payload = {
        "pool_runtime": {
            "document_chains_by_database": {},
        }
    }
    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "pool_runtime_publication_payload": publication_payload,
        },
    )

    with patch(
        "apps.intercompany_pools.pool_domain_steps.is_pool_master_data_gate_enabled",
        side_effect=MasterDataGateConfigInvalidError(
            source="global",
            raw_value="definitely-not-bool",
        ),
    ):
        with pytest.raises(ValueError, match="MASTER_DATA_GATE_CONFIG_INVALID") as exc_info:
            execute_pool_runtime_step(
                operation_type="pool.master_data_gate",
                rendered_data={"pool_runtime": {"step_id": "master_data_gate"}},
                context={"pool_run_id": str(run.id)},
                execution=execution,
            )

    diagnostic = json.loads(str(exc_info.value).split("diagnostic=", 1)[1])
    assert diagnostic["error_code"] == "MASTER_DATA_GATE_CONFIG_INVALID"
    assert diagnostic["runtime_key"] == "pools.master_data.gate_enabled"
    assert diagnostic["source"] == "global"

    execution.refresh_from_db(fields=["input_context"])
    gate_summary = execution.input_context.get("pool_runtime_master_data_gate")
    assert isinstance(gate_summary, dict)
    assert gate_summary.get("status") == "failed"
    assert gate_summary.get("error_code") == "MASTER_DATA_GATE_CONFIG_INVALID"
    assert execution.input_context.get("pool_runtime_publication_payload") == publication_payload


@pytest.mark.django_db
def test_master_data_gate_fails_closed_when_target_organization_binding_is_missing() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)
    topology = _attach_active_topology(run=run)

    left_org = Organization.objects.get(tenant=run.tenant, inn=topology["left_inn"])
    right_org = Organization.objects.get(tenant=run.tenant, inn=topology["right_inn"])

    left_party = PoolMasterParty.objects.create(
        tenant=run.tenant,
        canonical_id="party-left-org",
        name="Party Left Org",
        inn=left_org.inn,
        is_our_organization=True,
    )
    left_org.master_party = left_party
    left_org.save(update_fields=["master_party", "updated_at"])

    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
        },
    )

    with patch(
        "apps.intercompany_pools.pool_domain_steps.is_pool_master_data_gate_enabled",
        return_value=True,
    ):
        with pytest.raises(ValueError, match="MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING") as exc_info:
            execute_pool_runtime_step(
                operation_type="pool.master_data_gate",
                rendered_data={"pool_runtime": {"step_id": "master_data_gate"}},
                context={"pool_run_id": str(run.id)},
                execution=execution,
            )

    diagnostic = json.loads(str(exc_info.value).split("diagnostic=", 1)[1])
    assert diagnostic["error_code"] == "MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING"
    assert diagnostic["missing_count"] == 1
    assert diagnostic["missing_organization_bindings"][0]["organization_id"] == str(right_org.id)

    execution.refresh_from_db(fields=["input_context"])
    gate_summary = execution.input_context.get("pool_runtime_master_data_gate")
    assert isinstance(gate_summary, dict)
    assert gate_summary.get("status") == "failed"
    assert gate_summary.get("error_code") == "MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING"


@pytest.mark.django_db
def test_master_data_gate_resolves_party_token_and_persists_binding_artifact() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)
    database = _create_database(tenant=run.tenant, suffix="gate-resolve")
    PoolMasterParty.objects.create(
        tenant=run.tenant,
        canonical_id="party-001",
        name="Counterparty 001",
        is_counterparty=True,
        metadata={
            "ib_ref_keys": {
                str(database.id): {
                    "counterparty": "ref-counterparty-001",
                }
            }
        },
    )

    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "master_data_snapshot_ref": "master_data_snapshot.v1:test",
            "master_data_binding_artifact_ref": "master_data_binding_artifact.v1:test",
            "pool_runtime_publication_payload": {
                "pool_runtime": {
                    "document_chains_by_database": {
                        str(database.id): [
                            {
                                "chain_id": "sale-chain",
                                "documents": [
                                    {
                                        "document_id": "sale",
                                        "field_mapping": {
                                            "Контрагент": "master_data.party.party-001.counterparty.ref"
                                        },
                                        "table_parts_mapping": {},
                                    }
                                ],
                            }
                        ]
                    }
                }
            },
        },
    )

    with patch(
        "apps.intercompany_pools.pool_domain_steps.is_pool_master_data_gate_enabled",
        return_value=True,
    ):
        output = execute_pool_runtime_step(
            operation_type="pool.master_data_gate",
            rendered_data={"pool_runtime": {"step_id": "master_data_gate"}},
            context={"pool_run_id": str(run.id)},
            execution=execution,
        )

    assert output["step"] == "master_data_gate"
    assert output["summary"]["status"] == "completed"
    assert output["summary"]["bindings_count"] == 1

    execution.refresh_from_db(fields=["input_context"])
    publication_payload = execution.input_context.get("pool_runtime_publication_payload")
    assert isinstance(publication_payload, dict)
    pool_runtime_payload = publication_payload.get("pool_runtime")
    assert isinstance(pool_runtime_payload, dict)
    chains = pool_runtime_payload["document_chains_by_database"][str(database.id)]
    resolved_master_data_refs = chains[0]["documents"][0].get("resolved_master_data_refs")
    assert resolved_master_data_refs == {
        "master_data.party.party-001.counterparty.ref": "ref-counterparty-001"
    }

    binding_artifact = execution.input_context.get(POOL_RUNTIME_MASTER_DATA_BINDING_ARTIFACT_CONTEXT_KEY)
    assert isinstance(binding_artifact, dict)
    assert binding_artifact.get("binding_artifact_ref") == "master_data_binding_artifact.v1:test"
    assert binding_artifact.get("mode") == "resolve+upsert"


@pytest.mark.django_db
def test_master_data_gate_resolves_role_specific_party_bindings_for_single_party() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)
    database = _create_database(tenant=run.tenant, suffix="gate-role-specific-party")
    PoolMasterParty.objects.create(
        tenant=run.tenant,
        canonical_id="party-001",
        name="Universal Party 001",
        is_our_organization=True,
        is_counterparty=True,
        metadata={
            "ib_ref_keys": {
                str(database.id): {
                    "organization": "ref-organization-001",
                    "counterparty": "ref-counterparty-001",
                }
            }
        },
    )

    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "master_data_snapshot_ref": "master_data_snapshot.v1:test",
            "master_data_binding_artifact_ref": "master_data_binding_artifact.v1:test",
            "pool_runtime_publication_payload": {
                "pool_runtime": {
                    "document_chains_by_database": {
                        str(database.id): [
                            {
                                "chain_id": "sale-chain",
                                "documents": [
                                    {
                                        "document_id": "sale",
                                        "field_mapping": {
                                            "Организация": "master_data.party.party-001.organization.ref",
                                            "Контрагент": "master_data.party.party-001.counterparty.ref",
                                        },
                                        "table_parts_mapping": {},
                                    }
                                ],
                            }
                        ]
                    }
                }
            },
        },
    )

    with patch(
        "apps.intercompany_pools.pool_domain_steps.is_pool_master_data_gate_enabled",
        return_value=True,
    ):
        output = execute_pool_runtime_step(
            operation_type="pool.master_data_gate",
            rendered_data={"pool_runtime": {"step_id": "master_data_gate"}},
            context={"pool_run_id": str(run.id)},
            execution=execution,
        )

    assert output["summary"]["status"] == "completed"
    assert output["summary"]["bindings_count"] == 2
    execution.refresh_from_db(fields=["input_context"])
    publication_payload = execution.input_context["pool_runtime_publication_payload"]["pool_runtime"]
    resolved_master_data_refs = publication_payload["document_chains_by_database"][str(database.id)][0]["documents"][0][
        "resolved_master_data_refs"
    ]
    assert resolved_master_data_refs == {
        "master_data.party.party-001.organization.ref": "ref-organization-001",
        "master_data.party.party-001.counterparty.ref": "ref-counterparty-001",
    }


@pytest.mark.django_db
def test_master_data_gate_fails_closed_when_canonical_entity_is_missing() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)
    database = _create_database(tenant=run.tenant, suffix="gate-missing-entity")
    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "master_data_snapshot_ref": "master_data_snapshot.v1:test",
            "master_data_binding_artifact_ref": "master_data_binding_artifact.v1:test",
            "pool_runtime_publication_payload": {
                "pool_runtime": {
                    "document_chains_by_database": {
                        str(database.id): [
                            {
                                "chain_id": "sale-chain",
                                "documents": [
                                    {
                                        "document_id": "sale",
                                        "field_mapping": {
                                            "Контрагент": "master_data.party.missing-party.counterparty.ref"
                                        },
                                        "table_parts_mapping": {},
                                    }
                                ],
                            }
                        ]
                    }
                }
            },
        },
    )

    with patch(
        "apps.intercompany_pools.pool_domain_steps.is_pool_master_data_gate_enabled",
        return_value=True,
    ):
        with pytest.raises(ValueError, match="MASTER_DATA_ENTITY_NOT_FOUND") as exc_info:
            execute_pool_runtime_step(
                operation_type="pool.master_data_gate",
                rendered_data={"pool_runtime": {"step_id": "master_data_gate"}},
                context={"pool_run_id": str(run.id)},
                execution=execution,
            )

    diagnostic = json.loads(str(exc_info.value).split("diagnostic=", 1)[1])
    assert diagnostic["error_code"] == "MASTER_DATA_ENTITY_NOT_FOUND"
    assert diagnostic["entity_type"] == "party"
    assert diagnostic["canonical_id"] == "missing-party"
    assert diagnostic["target_database_id"] == str(database.id)

    execution.refresh_from_db(fields=["input_context"])
    gate_summary = execution.input_context.get("pool_runtime_master_data_gate")
    assert isinstance(gate_summary, dict)
    assert gate_summary.get("status") == "failed"
    assert gate_summary.get("error_code") == "MASTER_DATA_ENTITY_NOT_FOUND"
    assert isinstance(gate_summary.get("diagnostic"), dict)


@pytest.mark.django_db
def test_master_data_gate_fails_closed_when_contract_owner_ref_key_is_not_owner_scoped() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)
    database = _create_database(tenant=run.tenant, suffix="gate-contract-default")
    owner = PoolMasterParty.objects.create(
        tenant=run.tenant,
        canonical_id="party-a",
        name="Counterparty A",
        is_counterparty=True,
    )
    PoolMasterContract.objects.create(
        tenant=run.tenant,
        canonical_id="contract-001",
        name="Contract 001",
        owner_counterparty=owner,
        metadata={
            "ib_ref_keys": {
                str(database.id): {
                    "default": "ref-contract-default",
                }
            }
        },
    )

    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "master_data_snapshot_ref": "master_data_snapshot.v1:test",
            "master_data_binding_artifact_ref": "master_data_binding_artifact.v1:test",
            "pool_runtime_publication_payload": {
                "pool_runtime": {
                    "document_chains_by_database": {
                        str(database.id): [
                            {
                                "chain_id": "sale-chain",
                                "documents": [
                                    {
                                        "document_id": "sale",
                                        "field_mapping": {
                                            "Договор": "master_data.contract.contract-001.party-a.ref"
                                        },
                                        "table_parts_mapping": {},
                                    }
                                ],
                            }
                        ]
                    }
                }
            },
        },
    )

    with patch(
        "apps.intercompany_pools.pool_domain_steps.is_pool_master_data_gate_enabled",
        return_value=True,
    ):
        with pytest.raises(ValueError, match="MASTER_DATA_BINDING_CONFLICT") as exc_info:
            execute_pool_runtime_step(
                operation_type="pool.master_data_gate",
                rendered_data={"pool_runtime": {"step_id": "master_data_gate"}},
                context={"pool_run_id": str(run.id)},
                execution=execution,
            )

    diagnostic = json.loads(str(exc_info.value).split("diagnostic=", 1)[1])
    assert diagnostic["error_code"] == "MASTER_DATA_BINDING_CONFLICT"
    assert diagnostic["entity_type"] == "contract"
    assert diagnostic["canonical_id"] == "contract-001"
    assert diagnostic["target_database_id"] == str(database.id)


@pytest.mark.django_db
def test_master_data_gate_fails_closed_when_contract_owner_does_not_match_token() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)
    database = _create_database(tenant=run.tenant, suffix="gate-contract-owner-mismatch")
    owner_a = PoolMasterParty.objects.create(
        tenant=run.tenant,
        canonical_id="party-a",
        name="Counterparty A",
        is_counterparty=True,
    )
    PoolMasterParty.objects.create(
        tenant=run.tenant,
        canonical_id="party-b",
        name="Counterparty B",
        is_counterparty=True,
    )
    PoolMasterContract.objects.create(
        tenant=run.tenant,
        canonical_id="contract-001",
        name="Contract 001",
        owner_counterparty=owner_a,
        metadata={
            "ib_ref_keys": {
                str(database.id): {
                    "party-a": "ref-contract-a",
                }
            }
        },
    )

    execution = _attach_execution(
        run=run,
        input_context={
            "pool_run_id": str(run.id),
            "master_data_snapshot_ref": "master_data_snapshot.v1:test",
            "master_data_binding_artifact_ref": "master_data_binding_artifact.v1:test",
            "pool_runtime_publication_payload": {
                "pool_runtime": {
                    "document_chains_by_database": {
                        str(database.id): [
                            {
                                "chain_id": "sale-chain",
                                "documents": [
                                    {
                                        "document_id": "sale",
                                        "field_mapping": {
                                            "Договор": "master_data.contract.contract-001.party-b.ref"
                                        },
                                        "table_parts_mapping": {},
                                    }
                                ],
                            }
                        ]
                    }
                }
            },
        },
    )

    with patch(
        "apps.intercompany_pools.pool_domain_steps.is_pool_master_data_gate_enabled",
        return_value=True,
    ):
        with pytest.raises(ValueError, match="MASTER_DATA_ENTITY_NOT_FOUND") as exc_info:
            execute_pool_runtime_step(
                operation_type="pool.master_data_gate",
                rendered_data={"pool_runtime": {"step_id": "master_data_gate"}},
                context={"pool_run_id": str(run.id)},
                execution=execution,
            )

    diagnostic = json.loads(str(exc_info.value).split("diagnostic=", 1)[1])
    assert diagnostic["error_code"] == "MASTER_DATA_ENTITY_NOT_FOUND"
    assert diagnostic["entity_type"] == "contract"
    assert diagnostic["canonical_id"] == "contract-001"
    assert diagnostic["target_database_id"] == str(database.id)


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
