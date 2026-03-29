from __future__ import annotations

from datetime import date
from uuid import uuid4
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import connections, transaction

from apps.databases.models import Database, InfobaseUserMapping
from apps.intercompany_pools.binding_profiles_store import create_canonical_binding_profile
from apps.intercompany_pools.document_plan_artifact_contract import (
    POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_CONTEXT_KEY,
    POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_SLOTS_CONTEXT_KEY,
    POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY,
    POOL_RUNTIME_DOCUMENT_POLICY_SOURCE_CONTEXT_KEY,
)
from apps.intercompany_pools.document_policy_contract import DOCUMENT_POLICY_VERSION
from apps.intercompany_pools.master_data_artifact_contract import (
    MASTER_DATA_BINDING_ARTIFACT_VERSION,
    MASTER_DATA_GATE_MODE_RESOLVE_UPSERT,
    POOL_RUNTIME_MASTER_DATA_BINDING_ARTIFACT_CONTEXT_KEY,
)
from apps.intercompany_pools.runtime_projection_contract import (
    POOL_RUNTIME_PROJECTION_CONTEXT_KEY,
    POOL_RUNTIME_PROJECTION_VERSION,
)
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolBatch,
    PoolBatchKind,
    PoolBatchSourceType,
    PoolEdgeVersion,
    PoolNodeVersion,
    PoolPublicationAttempt,
    PoolPublicationAttemptStatus,
    PoolRun,
    PoolRunDirection,
    PoolRunMode,
    PoolSchemaTemplate,
    PoolSchemaTemplateFormat,
    PoolWorkflowBinding,
)
from apps.intercompany_pools.pool_domain_steps import execute_pool_runtime_step
from apps.intercompany_pools.runs import build_pool_run_idempotency_key
from apps.intercompany_pools.workflow_authoring_contract import PoolWorkflowBindingContract
from apps.intercompany_pools.workflow_binding_resolution import (
    ERROR_CODE_POOL_WORKFLOW_BINDING_NOT_FOUND,
    PoolWorkflowBindingResolutionError,
)
from apps.intercompany_pools.workflow_binding_attachments_store import (
    list_pool_workflow_binding_attachments,
    PoolWorkflowBindingStoreError,
    upsert_pool_workflow_binding_attachment,
)
from apps.intercompany_pools.workflow_runtime import (
    POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY,
    start_pool_run_retry_workflow_execution,
    start_pool_run_workflow_execution,
)
from apps.operations.services.operations_service.types import EnqueueResult
from apps.templates.workflow.decision_tables import create_decision_table_revision
from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate, WorkflowType
from apps.tenancy.models import Tenant


User = get_user_model()


def _create_pool_run(*, mode: str) -> PoolRun:
    tenant = Tenant.objects.create(
        slug=f"pool-runtime-{uuid4().hex[:8]}",
        name="Pool Runtime",
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Pool Runtime",
    )
    return PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        mode=mode,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        run_input={"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
    )


def _create_pool_run_for_pool(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    mode: str,
    period_start: date,
    period_end: date | None,
    run_input: dict[str, object],
    seed: int | None = None,
) -> PoolRun:
    idempotency_key = build_pool_run_idempotency_key(
        pool_id=str(pool.id),
        period_start=period_start,
        period_end=period_end,
        direction=PoolRunDirection.BOTTOM_UP,
        run_input=run_input,
    )
    return PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        mode=mode,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=period_start,
        period_end=period_end,
        run_input=run_input,
        idempotency_key=idempotency_key,
        seed=seed,
    )


def _attach_pool_target_database(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    period_start: date,
) -> Database:
    existing_root = (
        PoolNodeVersion.objects.select_related("organization")
        .filter(
            pool=pool,
            is_root=True,
            effective_from__lte=period_start,
        )
        .order_by("-effective_from")
        .first()
    )
    if existing_root is None:
        root_organization = Organization.objects.create(
            tenant=tenant,
            name=f"Root Org {uuid4().hex[:6]}",
            inn=f"72{uuid4().hex[:10]}",
        )
        existing_root = PoolNodeVersion.objects.create(
            pool=pool,
            organization=root_organization,
            effective_from=period_start,
            is_root=True,
        )

    existing_target = (
        PoolNodeVersion.objects.select_related("organization__database")
        .filter(
            pool=pool,
            is_root=False,
            organization__database__isnull=False,
            effective_from__lte=period_start,
        )
        .order_by("-effective_from")
        .first()
    )
    if existing_target is not None and existing_target.organization.database is not None:
        edge, _ = PoolEdgeVersion.objects.get_or_create(
            pool=pool,
            parent_node=existing_root,
            child_node=existing_target,
            effective_from=existing_target.effective_from,
        )
        edge_metadata = dict(edge.metadata) if isinstance(edge.metadata, dict) else {}
        if edge_metadata.get("document_policy_key") != "document_policy":
            edge_metadata["document_policy_key"] = "document_policy"
            edge.metadata = edge_metadata
            edge.save(update_fields=["metadata", "updated_at"])
        return existing_target.organization.database

    database = Database.objects.create(
        tenant=tenant,
        name=f"pool-runtime-db-{uuid4().hex[:8]}",
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="legacy-user",
        password="legacy-pass",
    )
    organization = Organization.objects.create(
        tenant=tenant,
        database=database,
        name=f"Org {uuid4().hex[:6]}",
        inn=f"73{uuid4().hex[:10]}",
    )
    target_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=organization,
        effective_from=period_start,
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=existing_root,
        child_node=target_node,
        effective_from=period_start,
        metadata={"document_policy_key": "document_policy"},
    )
    return database


def _build_document_policy_decision_payload(*, decision_table_id: str) -> dict[str, object]:
    return {
        "decision_table_id": decision_table_id,
        "decision_key": "document_policy",
        "name": "Runtime Test Document Policy",
        "inputs": [
            {"name": "direction", "value_type": "string", "required": True},
            {"name": "mode", "value_type": "string", "required": True},
        ],
        "outputs": [
            {"name": "document_policy", "value_type": "json", "required": True},
        ],
        "rules": [
            {
                "rule_id": "default",
                "priority": 0,
                "conditions": {},
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


def _create_runtime_workflow_template(
    *,
    direction: str,
) -> tuple[WorkflowTemplate, WorkflowTemplate]:
    distribution_alias = (
        "pool.distribution_calculation.top_down"
        if direction == PoolRunDirection.TOP_DOWN
        else "pool.distribution_calculation.bottom_up"
    )
    root = WorkflowTemplate.objects.create(
        name=f"runtime-workflow-{uuid4().hex[:8]}",
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
                    "id": "reconciliation",
                    "name": "Reconciliation",
                    "type": "operation",
                    "template_id": "pool.reconciliation_report",
                },
                {
                    "id": "approval_gate",
                    "name": "Approval Gate",
                    "type": "operation",
                    "template_id": "pool.approval_gate",
                },
                {
                    "id": "publication",
                    "name": "Publication",
                    "type": "operation",
                    "template_id": "pool.publication_odata",
                },
            ],
            "edges": [
                {"from": "prepare_input", "to": "distribution"},
                {"from": "distribution", "to": "reconciliation"},
                {"from": "reconciliation", "to": "approval_gate"},
                {"from": "approval_gate", "to": "publication", "condition": "{{approved_at}}"},
            ],
        },
        config={"timeout_seconds": 86400, "max_retries": 0},
        is_valid=True,
        is_active=True,
        version_number=1,
    )
    revision = root
    for version_number in (2, 3):
        revision = WorkflowTemplate.objects.create(
            name=root.name,
            description=root.description,
            workflow_type=root.workflow_type,
            dag_structure=root.dag_structure,
            config=root.config,
            is_valid=True,
            is_active=True,
            parent_version=revision,
            version_number=version_number,
        )
    return root, revision


def _ensure_runtime_test_workflow_binding(*, run: PoolRun) -> dict[str, object]:
    return _ensure_runtime_test_workflow_binding_attachment(run=run)


def _create_runtime_binding_profile_revision(
    *,
    run: PoolRun,
    workflow_revision_number: int,
    chain_id: str = "sale_chain",
) -> dict[str, object]:
    decision_payload = _build_document_policy_decision_payload(
        decision_table_id=f"runtime-doc-policy-profile-{uuid4().hex[:8]}"
    )
    decision_payload["rules"][0]["outputs"]["document_policy"]["chains"][0]["chain_id"] = chain_id
    decision = create_decision_table_revision(contract=decision_payload)
    workflow_root, workflow = _create_runtime_workflow_template(direction=run.direction)
    profile = create_canonical_binding_profile(
        tenant=run.tenant,
        binding_profile={
            "code": f"runtime-profile-{uuid4().hex[:8]}",
            "name": "Runtime Profile",
            "revision": {
                "workflow": {
                    "workflow_definition_key": str(workflow_root.id),
                    "workflow_revision_id": str(workflow.id),
                    "workflow_revision": workflow_revision_number,
                    "workflow_name": workflow.name,
                },
                "decisions": [
                    {
                        "decision_table_id": decision.decision_table_id,
                        "decision_key": decision.decision_key,
                        "slot_key": decision.decision_key,
                        "decision_revision": decision.version_number,
                    }
                ],
                "parameters": {"publication_variant": "full"},
                "role_mapping": {"initiator": "finance"},
                "metadata": {"source": "runtime-test"},
            },
        },
        actor_username="pool-runtime-test",
    )
    latest_revision = profile["latest_revision"]
    assert isinstance(latest_revision, dict)
    return latest_revision


def _ensure_runtime_test_workflow_binding_attachment(*, run: PoolRun) -> dict[str, object]:
    existing_bindings = list_pool_workflow_binding_attachments(pool=run.pool)
    if existing_bindings:
        return existing_bindings[0]

    _attach_pool_target_database(
        tenant=run.tenant,
        pool=run.pool,
        period_start=run.period_start,
    )
    profile_revision = _create_runtime_binding_profile_revision(
        run=run,
        workflow_revision_number=3,
    )
    binding, _ = upsert_pool_workflow_binding_attachment(
        pool=run.pool,
        workflow_binding={
            "binding_profile_revision_id": str(profile_revision["binding_profile_revision_id"]),
            "selector": {
                "direction": run.direction,
                "mode": run.mode,
                "tags": [],
            },
            "effective_from": run.period_start.isoformat(),
            "status": "active",
        },
        actor_username="pool-runtime-test",
    )
    return binding


def _create_runtime_legacy_workflow_binding_attachment(*, run: PoolRun) -> dict[str, object]:
    _attach_pool_target_database(
        tenant=run.tenant,
        pool=run.pool,
        period_start=run.period_start,
    )
    decision = create_decision_table_revision(
        contract=_build_document_policy_decision_payload(
            decision_table_id=f"runtime-doc-policy-legacy-{uuid4().hex[:8]}"
        )
    )
    workflow_root, workflow = _create_runtime_workflow_template(direction=run.direction)
    binding_id = str(uuid4())
    legacy_binding = PoolWorkflowBinding.objects.create(
        binding_id=binding_id,
        tenant=run.tenant,
        pool=run.pool,
        status="active",
        effective_from=run.period_start,
        effective_to=None,
        direction=run.direction,
        mode=run.mode,
        selector_tags=[],
        workflow_definition_key=str(workflow_root.id),
        workflow_revision_id=str(workflow.id),
        workflow_revision=workflow.version_number,
        workflow_name=workflow.name,
        decisions=[
            {
                "decision_table_id": decision.decision_table_id,
                "decision_key": decision.decision_key,
                "slot_key": decision.decision_key,
                "decision_revision": decision.version_number,
            }
        ],
        parameters={"publication_variant": "legacy"},
        role_mapping={"initiator": "finance"},
        revision=1,
        created_by="legacy-import",
        updated_by="legacy-import",
    )
    return {
        "binding_id": legacy_binding.binding_id,
        "pool_id": str(run.pool_id),
        "workflow": {
            "workflow_definition_key": legacy_binding.workflow_definition_key,
            "workflow_revision_id": legacy_binding.workflow_revision_id,
            "workflow_revision": legacy_binding.workflow_revision,
            "workflow_name": legacy_binding.workflow_name,
        },
        "decisions": list(legacy_binding.decisions),
        "parameters": dict(legacy_binding.parameters),
        "role_mapping": dict(legacy_binding.role_mapping),
        "selector": {
            "direction": legacy_binding.direction,
            "mode": legacy_binding.mode,
            "tags": list(legacy_binding.selector_tags),
        },
        "effective_from": legacy_binding.effective_from.isoformat(),
        "status": legacy_binding.status,
    }


def _ensure_service_mapping(*, database: Database) -> None:
    if InfobaseUserMapping.objects.filter(database=database, is_service=True).exists():
        return
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username=f"svc-{uuid4().hex[:8]}",
        ib_password="svc-pass",
        is_service=True,
    )


def _ensure_actor_mapping(*, database: Database, actor: User) -> None:
    if InfobaseUserMapping.objects.filter(database=database, user=actor, is_service=False).exists():
        return
    InfobaseUserMapping.objects.create(
        database=database,
        user=actor,
        ib_username=f"actor-{actor.username}-{uuid4().hex[:4]}",
        ib_password="actor-pass",
        is_service=False,
    )


def _start_runtime_workflow_execution(
    *,
    run: PoolRun,
    requested_by: User | None = None,
    workflow_binding: dict[str, object] | None = None,
):
    binding = workflow_binding or _ensure_runtime_test_workflow_binding(run=run)
    database = _attach_pool_target_database(
        tenant=run.tenant,
        pool=run.pool,
        period_start=run.period_start,
    )
    if requested_by is None:
        _ensure_service_mapping(database=database)
    else:
        _ensure_actor_mapping(database=database, actor=requested_by)
    return start_pool_run_workflow_execution(
        run=run,
        requested_by=requested_by,
        workflow_binding=binding,
    )


def _start_runtime_retry_workflow_execution(
    *,
    run: PoolRun,
    retry_request: dict[str, object],
    requested_by: User | None = None,
):
    database = _attach_pool_target_database(
        tenant=run.tenant,
        pool=run.pool,
        period_start=run.period_start,
    )
    if requested_by is None:
        _ensure_service_mapping(database=database)
    else:
        _ensure_actor_mapping(database=database, actor=requested_by)
    return start_pool_run_retry_workflow_execution(
        run=run,
        retry_request=retry_request,
        requested_by=requested_by,
    )


def _create_batch_backed_top_down_run(*, mode: str) -> PoolRun:
    tenant = Tenant.objects.create(
        slug=f"pool-runtime-batch-{uuid4().hex[:8]}",
        name="Pool Runtime Batch",
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-batch-{uuid4().hex[:6]}",
        name="Pool Runtime Batch",
    )
    start_organization = Organization.objects.create(
        tenant=tenant,
        name=f"Batch Start {uuid4().hex[:6]}",
        inn=f"73{uuid4().int % 10**10:010d}",
    )
    PoolNodeVersion.objects.create(
        pool=pool,
        organization=start_organization,
        effective_from=date(2026, 1, 1),
        is_root=True,
    )
    _attach_pool_target_database(
        tenant=tenant,
        pool=pool,
        period_start=date(2026, 1, 1),
    )
    batch = PoolBatch.objects.create(
        tenant=tenant,
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
        start_organization=start_organization,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        source_reference=f"receipt-{uuid4().hex[:8]}",
        normalization_summary={
            "processed_rows": 1,
            "normalized_rows": 1,
            "total_amount_with_vat": "125.50",
        },
    )
    run = PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        mode=mode,
        direction=PoolRunDirection.TOP_DOWN,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        run_input={
            "batch_id": str(batch.id),
            "start_organization_id": str(start_organization.id),
        },
        idempotency_key=build_pool_run_idempotency_key(
            pool_id=str(pool.id),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            direction=PoolRunDirection.TOP_DOWN,
            run_input={
                "batch_id": str(batch.id),
                "start_organization_id": str(start_organization.id),
            },
            batch_id=str(batch.id),
            start_organization_id=str(start_organization.id),
        ),
    )
    batch.run = run
    batch.save(update_fields=["run", "updated_at"])
    return run


def _build_document_plan_artifact_for_compile() -> dict[str, object]:
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
                "slot_key": "document_policy",
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


def _build_workflow_binding_payload(*, pool_id: str) -> dict[str, object]:
    return {
        "binding_id": str(uuid4()),
        "pool_id": pool_id,
        "workflow": {
            "workflow_definition_key": "services-publication",
            "workflow_revision_id": str(uuid4()),
            "workflow_revision": 3,
            "workflow_name": "services_publication",
        },
        "decisions": [
            {
                "decision_table_id": "decision-1",
                "decision_key": "invoice_mode",
                "decision_revision": 2,
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


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_requires_explicit_pool_workflow_binding() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    run.schema_template = PoolSchemaTemplate.objects.create(
        tenant=run.tenant,
        code=f"legacy-binding-{uuid4().hex[:8]}",
        name="Legacy Binding Template",
        format=PoolSchemaTemplateFormat.JSON,
        schema={},
        metadata={"workflow_binding": "legacy-binding-hint"},
    )
    run.save(update_fields=["schema_template", "updated_at"])

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-1",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        with pytest.raises(ValueError, match="POOL_WORKFLOW_BINDING_REQUIRED"):
            start_pool_run_workflow_execution(run=run)


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_persists_explicit_pool_workflow_binding() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    workflow_binding = _ensure_runtime_test_workflow_binding_attachment(run=run)

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-binding",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        result = _start_runtime_workflow_execution(run=run, workflow_binding=workflow_binding)

    execution = WorkflowExecution.objects.get(id=result.execution_id)
    persisted_binding = execution.input_context.get(POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY)
    runtime_projection = execution.input_context.get(POOL_RUNTIME_PROJECTION_CONTEXT_KEY)
    compiled_document_policy = execution.input_context.get(
        POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_CONTEXT_KEY
    )
    compiled_document_policy_slots = execution.input_context.get(
        POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_SLOTS_CONTEXT_KEY
    )

    assert persisted_binding["binding_id"] == workflow_binding["binding_id"]
    assert persisted_binding["binding_profile_revision_id"] == workflow_binding["binding_profile_revision_id"]
    assert persisted_binding["binding_profile_revision_number"] == workflow_binding["binding_profile_revision_number"]
    assert persisted_binding["revision"] == workflow_binding["revision"]
    assert persisted_binding["resolved_profile"]["workflow"]["workflow_revision"] == 3
    assert isinstance(runtime_projection, dict)
    assert isinstance(compiled_document_policy, dict)
    assert isinstance(compiled_document_policy_slots, dict)
    assert compiled_document_policy["version"] == DOCUMENT_POLICY_VERSION
    assert set(compiled_document_policy_slots) == {"document_policy"}
    assert compiled_document_policy_slots["document_policy"]["document_policy"] == compiled_document_policy
    assert (
        execution.input_context.get(POOL_RUNTIME_DOCUMENT_POLICY_SOURCE_CONTEXT_KEY)
        .startswith("workflow_binding.decision_table:")
    )
    assert runtime_projection["workflow_binding"]["binding_mode"] == "pool_workflow_binding"
    assert runtime_projection["workflow_binding"]["binding_id"] == workflow_binding["binding_id"]
    assert runtime_projection["workflow_binding"]["binding_profile_revision_id"] == (
        workflow_binding["binding_profile_revision_id"]
    )
    assert runtime_projection["workflow_binding"]["attachment_revision"] == workflow_binding["revision"]
    assert runtime_projection["workflow_binding"]["workflow_revision"] == 3
    assert runtime_projection["document_policy_projection"]["compiled_document_policy_slots"] == (
        compiled_document_policy_slots
    )
    assert runtime_projection["document_policy_projection"]["slot_coverage_summary"]["counts"]["resolved"] == 1

    binding_entry = next(
        item
        for item in execution.bindings
        if item.get("target_ref") == "workflow.binding"
    )
    assert binding_entry["source_ref"] == f"pool_workflow_binding:{workflow_binding['binding_id']}"
    assert binding_entry["binding_mode"] == "pool_workflow_binding"

    persisted_run = PoolRun.objects.get(id=run.id)
    assert persisted_run.workflow_binding_snapshot["binding_id"] == workflow_binding["binding_id"]
    assert persisted_run.workflow_binding_snapshot["binding_profile_revision_id"] == (
        workflow_binding["binding_profile_revision_id"]
    )
    assert persisted_run.workflow_binding_snapshot["revision"] == workflow_binding["revision"]
    assert persisted_run.workflow_binding_snapshot["resolved_profile"]["workflow"]["workflow_revision"] == 3
    assert "workflow" not in persisted_run.workflow_binding_snapshot
    assert "decisions" not in persisted_run.workflow_binding_snapshot
    assert persisted_run.runtime_projection_snapshot == runtime_projection


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_accepts_batch_backed_top_down_run_without_explicit_starting_amount() -> None:
    run = _create_batch_backed_top_down_run(mode=PoolRunMode.SAFE)
    workflow_binding = _ensure_runtime_test_workflow_binding_attachment(run=run)

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-batch-top-down",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        result = _start_runtime_workflow_execution(run=run, workflow_binding=workflow_binding)

    execution = WorkflowExecution.objects.get(id=result.execution_id)

    assert execution.input_context[POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY]["version"] == "document_plan_artifact.v1"
    assert execution.input_context[POOL_RUNTIME_PROJECTION_CONTEXT_KEY]["compile_summary"]["compiled_targets_count"] == 1


@pytest.mark.django_db(transaction=True)
def test_start_pool_run_workflow_execution_defers_enqueue_until_outer_commit() -> None:
    run = _create_batch_backed_top_down_run(mode=PoolRunMode.SAFE)
    workflow_binding = _ensure_runtime_test_workflow_binding_attachment(run=run)
    target_database = (
        PoolNodeVersion.objects.filter(
            pool=run.pool,
            effective_from=run.period_start,
            is_root=False,
            organization__database__isnull=False,
        )
        .values_list("organization__database", flat=True)
        .first()
    )
    assert target_database is not None
    _ensure_service_mapping(database=Database.objects.get(id=target_database))
    enqueue_atomic_flags: list[bool] = []

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        side_effect=lambda **kwargs: (
            enqueue_atomic_flags.append(connections["default"].in_atomic_block)
            or EnqueueResult(
                success=True,
                operation_id="workflow-op-deferred-top-down",
                status="queued",
                error=None,
                error_code=None,
            )
        ),
    ):
        with transaction.atomic():
            result = start_pool_run_workflow_execution(run=run, workflow_binding=workflow_binding)
            assert result.enqueue_status == "deferred"
            assert enqueue_atomic_flags == []

    refreshed_run = PoolRun.objects.get(id=run.id)
    assert enqueue_atomic_flags == [False]
    assert refreshed_run.workflow_status == "queued"


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_fails_closed_for_legacy_attachment_without_profile_refs() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    legacy_binding = _create_runtime_legacy_workflow_binding_attachment(run=run)

    with pytest.raises(PoolWorkflowBindingStoreError) as exc_info:
        _start_runtime_workflow_execution(run=run, workflow_binding=legacy_binding)

    assert str(exc_info.value) == (
        f"POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING: Workflow binding '{legacy_binding['binding_id']}' "
        "is missing binding_profile references."
    )

    persisted_record = PoolWorkflowBinding.objects.get(binding_id=str(legacy_binding["binding_id"]))
    assert persisted_record.binding_profile_id is None
    assert persisted_record.binding_profile_revision_id is None
    assert persisted_record.updated_by == "legacy-import"


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_reloads_binding_snapshot_from_attachment_store() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    stale_binding = _ensure_runtime_test_workflow_binding_attachment(run=run)
    updated_revision = _create_runtime_binding_profile_revision(
        run=run,
        workflow_revision_number=4,
        chain_id="canonical_lineage_chain",
    )
    updated_binding, _ = upsert_pool_workflow_binding_attachment(
        pool=run.pool,
        workflow_binding={
            "binding_id": str(stale_binding["binding_id"]),
            "revision": int(stale_binding["revision"]),
            "binding_profile_revision_id": str(updated_revision["binding_profile_revision_id"]),
            "selector": dict(stale_binding["selector"]),
            "effective_from": str(stale_binding["effective_from"]),
            "effective_to": stale_binding.get("effective_to"),
            "status": str(stale_binding["status"]),
        },
        actor_username="pool-runtime-test",
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-binding-canonical",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        result = _start_runtime_workflow_execution(run=run, workflow_binding=stale_binding)

    execution = WorkflowExecution.objects.get(id=result.execution_id)
    persisted_binding = execution.input_context.get(POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY)
    runtime_projection = execution.input_context.get(POOL_RUNTIME_PROJECTION_CONTEXT_KEY)
    compiled_document_policy = execution.input_context.get(
        POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_CONTEXT_KEY
    )

    assert persisted_binding["binding_id"] == stale_binding["binding_id"]
    assert persisted_binding["binding_profile_revision_id"] == updated_revision["binding_profile_revision_id"]
    assert persisted_binding["revision"] == updated_binding["revision"]
    assert persisted_binding["resolved_profile"]["workflow"]["workflow_revision"] == 4
    assert persisted_binding["binding_profile_revision_id"] != stale_binding["binding_profile_revision_id"]
    assert isinstance(compiled_document_policy, dict)
    assert compiled_document_policy["chains"][0]["chain_id"] == "canonical_lineage_chain"
    assert execution.input_context.get(POOL_RUNTIME_DOCUMENT_POLICY_SOURCE_CONTEXT_KEY).startswith(
        "workflow_binding.decision_table:"
    )
    assert runtime_projection["workflow_binding"]["binding_id"] == stale_binding["binding_id"]
    assert runtime_projection["workflow_binding"]["binding_profile_revision_id"] == (
        updated_revision["binding_profile_revision_id"]
    )
    assert runtime_projection["workflow_binding"]["attachment_revision"] == updated_binding["revision"]
    assert runtime_projection["workflow_binding"]["workflow_revision"] == 4
    assert runtime_projection["document_policy_projection"]["compiled_document_policy_slots"]

    persisted_run = PoolRun.objects.get(id=run.id)
    assert persisted_run.workflow_binding_snapshot["binding_id"] == stale_binding["binding_id"]
    assert persisted_run.workflow_binding_snapshot["binding_profile_revision_id"] == (
        updated_revision["binding_profile_revision_id"]
    )
    assert persisted_run.workflow_binding_snapshot["revision"] == updated_binding["revision"]
    assert persisted_run.workflow_binding_snapshot["resolved_profile"]["workflow"]["workflow_revision"] == 4
    assert "workflow" not in persisted_run.workflow_binding_snapshot
    assert "decisions" not in persisted_run.workflow_binding_snapshot
    assert persisted_run.runtime_projection_snapshot == runtime_projection


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_fails_closed_when_attachment_is_deleted() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    workflow_binding = _ensure_runtime_test_workflow_binding_attachment(run=run)
    PoolWorkflowBinding.objects.filter(pool=run.pool, binding_id=workflow_binding["binding_id"]).delete()

    with pytest.raises(PoolWorkflowBindingResolutionError) as exc_info:
        _start_runtime_workflow_execution(run=run, workflow_binding=workflow_binding)

    assert exc_info.value.code == ERROR_CODE_POOL_WORKFLOW_BINDING_NOT_FOUND
    assert exc_info.value.errors == [{"binding_id": workflow_binding["binding_id"]}]


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_uses_atomic_publication_nodes_when_document_plan_artifact_is_available() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    artifact = _build_document_plan_artifact_for_compile()

    with (
        patch(
            "apps.intercompany_pools.binding_preview.compile_document_plan_artifact_v1",
            return_value=artifact,
        ),
        patch(
            "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
            return_value=EnqueueResult(
                success=True,
                operation_id="workflow-op-atomic",
                status="queued",
                error=None,
                error_code=None,
            ),
        ),
    ):
        result = _start_runtime_workflow_execution(run=run)

    execution = WorkflowExecution.objects.get(id=result.execution_id)
    node_ids = [node.id for node in execution.workflow_template.dag_structure.nodes]
    atomic_publication_node_ids = [node_id for node_id in node_ids if node_id.startswith("publication_odata_")]
    runtime_projection = execution.input_context.get(POOL_RUNTIME_PROJECTION_CONTEXT_KEY)

    assert len(atomic_publication_node_ids) == 2
    assert "publication_odata" not in node_ids
    assert isinstance(runtime_projection, dict)
    assert runtime_projection["document_policy_projection"]["source_mode"] == "document_plan_artifact"
    assert runtime_projection["document_policy_projection"]["policy_refs"] == artifact["policy_refs"]
    assert runtime_projection["document_policy_projection"]["policy_refs_count"] == 1
    assert runtime_projection["document_policy_projection"]["targets_count"] == 1
    compiled_slots = runtime_projection["document_policy_projection"]["compiled_document_policy_slots"]
    assert set(compiled_slots) == {"document_policy"}
    assert compiled_slots["document_policy"]["document_policy"]["version"] == DOCUMENT_POLICY_VERSION
    assert compiled_slots["document_policy"]["document_policy_source"].startswith(
        "workflow_binding.decision_table:"
    )
    assert runtime_projection["document_policy_projection"]["slot_coverage_summary"]["counts"]["resolved"] == 1
    assert runtime_projection["artifacts"]["document_plan_artifact_version"] == "document_plan_artifact.v1"
    assert runtime_projection["artifacts"]["topology_version_ref"] == "topology-v1"
    assert runtime_projection["artifacts"]["distribution_artifact_ref"] == artifact["distribution_artifact_ref"]
    assert runtime_projection["compile_summary"]["compiled_targets_count"] == 1
    assert execution.input_context.get(POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY) == artifact

    operation_bindings = execution.execution_plan.get("operation_bindings")
    assert isinstance(operation_bindings, list)
    publication_binding_node_ids = sorted(
        str(item.get("node_id") or "")
        for item in operation_bindings
        if str(item.get("alias") or "") == "pool.publication_odata"
    )
    assert publication_binding_node_ids == sorted(atomic_publication_node_ids)
    publication_provenance_items = [
        item.get("provenance")
        for item in operation_bindings
        if str(item.get("alias") or "") == "pool.publication_odata"
    ]
    assert len(publication_provenance_items) == 2
    assert all(isinstance(item, dict) for item in publication_provenance_items)
    assert all(item.get("kind") == "pool_atomic_publication" for item in publication_provenance_items)
    assert all(item.get("action_kind") == "publish_odata" for item in publication_provenance_items)
    assert all(item.get("attempt_scope") == "run_execution" for item in publication_provenance_items)


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_reconciliation_uses_persisted_document_plan_artifact() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)
    database = _attach_pool_target_database(
        tenant=run.tenant,
        pool=run.pool,
        period_start=run.period_start,
    )
    target_node = (
        PoolNodeVersion.objects.select_related("organization")
        .filter(
            pool=run.pool,
            is_root=False,
            organization__database=database,
            effective_from__lte=run.period_start,
        )
        .order_by("-effective_from")
        .first()
    )
    assert target_node is not None
    run.run_input = {
        "source_payload": [
            {
                "inn": target_node.organization.inn,
                "amount": "100.00",
            }
        ]
    }
    run.save(update_fields=["run_input", "updated_at"])
    _ensure_service_mapping(database=database)
    invalid_edge_policy = {
        "version": DOCUMENT_POLICY_VERSION,
        "chains": [
            {
                "chain_id": "invalid-edge-chain",
                "documents": [
                    {
                        "document_id": "sale",
                        "entity_name": "Document_Sales",
                        "document_role": "base",
                        "field_mapping": {"Amount": "allocation.amount"},
                        "table_parts_mapping": {},
                        "link_rules": {},
                        "invoice_mode": "always",
                    }
                ],
            }
        ],
    }

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-persisted-artifact",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        result = _start_runtime_workflow_execution(run=run)

    execution = WorkflowExecution.objects.get(id=result.execution_id)
    persisted_artifact = execution.input_context.get(POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY)

    assert isinstance(persisted_artifact, dict)
    assert persisted_artifact["version"] == "document_plan_artifact.v1"
    assert any(
        str(ref.get("source") or "").startswith("workflow_binding.decision_table:")
        for ref in persisted_artifact.get("policy_refs", [])
        if isinstance(ref, dict)
    )
    assert execution.input_context.get("decisions", {}).get("document_policy", {}).get("version") == (
        DOCUMENT_POLICY_VERSION
    )
    edge = PoolEdgeVersion.objects.filter(pool=run.pool).first()
    assert edge is not None
    edge.metadata = {"document_policy": invalid_edge_policy}
    edge.save(update_fields=["metadata", "updated_at"])

    execute_pool_runtime_step(
        operation_type="pool.distribution_calculation.bottom_up",
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

    assert reconciliation_output["document_plan_artifact"] == persisted_artifact
    execution.refresh_from_db(fields=["input_context"])
    assert execution.input_context[POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY] == persisted_artifact


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_fails_closed_when_required_invoice_step_is_missing() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    invalid_artifact = _build_document_plan_artifact_for_compile()
    invalid_artifact["targets"][0]["chains"][0]["documents"] = [
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

    with (
        patch(
            "apps.intercompany_pools.binding_preview.compile_document_plan_artifact_v1",
            return_value=invalid_artifact,
        ),
        patch("apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution") as enqueue_mock,
    ):
        with pytest.raises(ValueError, match="POOL_RUNTIME_REQUIRED_INVOICE_STEP_MISSING"):
            _start_runtime_workflow_execution(run=run)

    enqueue_mock.assert_not_called()


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_sets_publication_auth_context() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    actor = User.objects.create_user(
        username=f"workflow-actor-{uuid4().hex[:8]}",
        email=f"workflow-actor-{uuid4().hex[:8]}@example.test",
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-auth",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        result = _start_runtime_workflow_execution(run=run, requested_by=actor)

    execution = WorkflowExecution.objects.get(id=result.execution_id)
    publication_auth = execution.input_context.get("publication_auth")
    assert publication_auth == {
        "strategy": "actor",
        "actor_username": actor.username,
        "source": "run_create",
    }


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_sets_master_data_refs_in_input_context() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-master-data-refs",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        result = _start_runtime_workflow_execution(run=run)

    execution = WorkflowExecution.objects.get(id=result.execution_id)
    snapshot_ref = str(execution.input_context.get("master_data_snapshot_ref") or "").strip()
    binding_ref = str(execution.input_context.get("master_data_binding_artifact_ref") or "").strip()
    assert snapshot_ref.startswith("master_data_snapshot.v1:")
    assert binding_ref.startswith("master_data_binding_artifact.v1:")


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_does_not_prefill_publication_payload_from_run_input() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)
    run.run_input = {
        "entity_name": "Document_IntercompanyPoolDistribution",
        "documents_by_database": {
            "db-initial-1": [{"Amount": "100.00"}],
            "db-initial-2": [{"Amount": "90.00"}],
        },
        "max_attempts": 2,
        "retry_interval_seconds": 5,
        "external_key_field": "ExternalRunKey",
    }
    run.save(update_fields=["run_input", "updated_at"])

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-publication-payload",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        result = _start_runtime_workflow_execution(run=run)

    execution = WorkflowExecution.objects.get(id=result.execution_id)
    assert "pool_runtime_publication_payload" not in execution.input_context


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_sanitizes_reserved_artifact_keys_from_run_input() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)
    run.run_input = {
        "entity_name": "Document_IntercompanyPoolDistribution",
        "source_payload": [{"inn": "730000000001", "amount": "100.00"}],
        "pool_runtime_distribution_artifact": {"version": "distribution_artifact.v1"},
        "distribution_artifact": {"version": "distribution_artifact.v1"},
        "document_plan_artifact": {"version": "document_plan_artifact.v1"},
        "pool_runtime_publication_payload": {
            "pool_runtime": {
                "entity_name": "Document_IntercompanyPoolDistribution",
                "documents_by_database": {"db-bypass": [{"Amount": "999.00"}]},
            }
        },
    }
    run.save(update_fields=["run_input", "updated_at"])

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-run-input-sanitize",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        result = _start_runtime_workflow_execution(run=run)

    execution = WorkflowExecution.objects.get(id=result.execution_id)
    run_input = execution.input_context.get("run_input")
    assert isinstance(run_input, dict)
    assert run_input.get("entity_name") == "Document_IntercompanyPoolDistribution"
    assert "source_payload" in run_input
    assert "pool_runtime_distribution_artifact" not in run_input
    assert "distribution_artifact" not in run_input
    assert "document_plan_artifact" not in run_input
    assert "pool_runtime_publication_payload" not in run_input


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_fail_closed_when_actor_mapping_missing() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    workflow_binding = _ensure_runtime_test_workflow_binding(run=run)
    actor = User.objects.create_user(
        username=f"workflow-missing-map-{uuid4().hex[:8]}",
        email=f"workflow-missing-map-{uuid4().hex[:8]}@example.test",
    )

    with pytest.raises(ValueError) as exc:
        start_pool_run_workflow_execution(run=run, requested_by=actor, workflow_binding=workflow_binding)

    error_text = str(exc.value)
    assert "ODATA_MAPPING_NOT_CONFIGURED" in error_text
    assert "/rbac" in error_text


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_uses_service_mapping_when_actor_not_provided() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    workflow_binding = _ensure_runtime_test_workflow_binding(run=run)
    database = _attach_pool_target_database(
        tenant=run.tenant,
        pool=run.pool,
        period_start=run.period_start,
    )
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username="odata_service_user",
        ib_password="odata_service_pwd",
        is_service=True,
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-service-auth",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        result = start_pool_run_workflow_execution(
            run=run,
            requested_by=None,
            workflow_binding=workflow_binding,
        )

    execution = WorkflowExecution.objects.get(id=result.execution_id)
    assert execution.input_context.get("publication_auth") == {
        "strategy": "service",
        "actor_username": "",
        "source": "run_create",
    }


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_fail_closed_when_service_mapping_ambiguous() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    workflow_binding = _ensure_runtime_test_workflow_binding(run=run)
    database = _attach_pool_target_database(
        tenant=run.tenant,
        pool=run.pool,
        period_start=run.period_start,
    )
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username="svc-user-1",
        ib_password="svc-pass-1",
        is_service=True,
    )
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username="svc-user-2",
        ib_password="svc-pass-2",
        is_service=True,
    )

    with pytest.raises(ValueError) as exc:
        start_pool_run_workflow_execution(run=run, requested_by=None, workflow_binding=workflow_binding)

    error_text = str(exc.value)
    assert "ODATA_MAPPING_AMBIGUOUS" in error_text
    assert "/rbac" in error_text


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_reuses_definition_for_same_pool_structure() -> None:
    tenant = Tenant.objects.create(slug=f"pool-runtime-reuse-{uuid4().hex[:8]}", name="Pool Runtime Reuse")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-{uuid4().hex[:6]}",
        name="Pool Runtime Reuse",
    )
    run_1 = _create_pool_run_for_pool(
        tenant=tenant,
        pool=pool,
        mode=PoolRunMode.SAFE,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        run_input={"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
        seed=101,
    )
    run_2 = _create_pool_run_for_pool(
        tenant=tenant,
        pool=pool,
        mode=PoolRunMode.SAFE,
        period_start=date(2026, 2, 1),
        period_end=date(2026, 2, 28),
        run_input={"source_payload": [{"inn": "730000000999", "amount": "999.00"}]},
        seed=202,
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-reuse",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        result_1 = _start_runtime_workflow_execution(run=run_1)
        result_2 = _start_runtime_workflow_execution(run=run_2)

    execution_1 = WorkflowExecution.objects.get(id=result_1.execution_id)
    execution_2 = WorkflowExecution.objects.get(id=result_2.execution_id)
    assert execution_1.workflow_template_id == execution_2.workflow_template_id

    definition_1 = execution_1.execution_plan.get("definition") if isinstance(execution_1.execution_plan, dict) else {}
    definition_2 = execution_2.execution_plan.get("definition") if isinstance(execution_2.execution_plan, dict) else {}
    assert isinstance(definition_1, dict)
    assert isinstance(definition_2, dict)
    assert definition_1.get("definition_key")
    assert definition_1.get("definition_key") == definition_2.get("definition_key")

    snapshot_1 = execution_1.execution_plan.get("execution_snapshot") if isinstance(execution_1.execution_plan, dict) else {}
    snapshot_2 = execution_2.execution_plan.get("execution_snapshot") if isinstance(execution_2.execution_plan, dict) else {}
    assert isinstance(snapshot_1, dict)
    assert isinstance(snapshot_2, dict)
    assert snapshot_1.get("period_start") == "2026-01-01"
    assert snapshot_2.get("period_start") == "2026-02-01"
    assert snapshot_1.get("run_input") != snapshot_2.get("run_input")


@pytest.mark.django_db
def test_retry_workflow_execution_keeps_operation_binding_snapshot() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)
    creator = User.objects.create_user(
        username=f"workflow-creator-{uuid4().hex[:8]}",
        email=f"workflow-creator-{uuid4().hex[:8]}@example.test",
    )
    retry_actor = User.objects.create_user(
        username=f"workflow-retry-{uuid4().hex[:8]}",
        email=f"workflow-retry-{uuid4().hex[:8]}@example.test",
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-initial",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        first = _start_runtime_workflow_execution(run=run, requested_by=creator)

    retry_payload = {
        "entity_name": "Document_IntercompanyPoolDistribution",
        "documents_by_database": {
            "db-retry-1": [{"Amount": "100.00"}],
        },
        "use_retry_subset_payload": True,
        "max_attempts": 1,
        "retry_interval_seconds": 0,
        "external_key_field": "ExternalRunKey",
    }
    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-retry",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        retry = _start_runtime_retry_workflow_execution(
            run=run,
            retry_request=retry_payload,
            requested_by=retry_actor,
        )

    assert first.execution_id != retry.execution_id

    first_execution = WorkflowExecution.objects.get(id=first.execution_id)
    execution = WorkflowExecution.objects.get(id=retry.execution_id)
    operation_bindings = execution.execution_plan.get("operation_bindings")
    assert isinstance(operation_bindings, list)
    assert len(operation_bindings) >= 4
    assert all(item.get("binding_mode") == "pinned_exposure" for item in operation_bindings)
    assert all(str(item.get("template_exposure_id") or "").strip() for item in operation_bindings)

    first_definition = first_execution.execution_plan.get("definition")
    assert isinstance(first_definition, dict)
    assert str(first_definition.get("definition_key") or "").strip()

    definition = execution.execution_plan.get("definition")
    assert isinstance(definition, dict)
    assert str(definition.get("definition_key") or "").strip()
    assert definition.get("definition_key") == first_definition.get("definition_key")
    assert definition.get("workflow_template_id") == str(execution.workflow_template_id)

    execution_snapshot = execution.execution_plan.get("execution_snapshot")
    assert isinstance(execution_snapshot, dict)
    lineage = execution_snapshot.get("lineage")
    assert isinstance(lineage, dict)
    assert lineage.get("attempt_kind") == "retry"
    assert int(lineage.get("attempt_number") or 0) >= 2
    assert str(lineage.get("parent_workflow_run_id") or "").strip()
    assert execution.input_context.get("pool_runtime_retry_settings") == {
        "use_retry_subset_payload": True,
    }
    retry_request = execution.input_context.get("retry_request")
    assert isinstance(retry_request, dict)
    assert retry_request.get("use_retry_subset_payload") is True

    publication_payload = execution.input_context.get("pool_runtime_publication_payload")
    assert isinstance(publication_payload, dict)
    pool_runtime_payload = publication_payload.get("pool_runtime")
    assert isinstance(pool_runtime_payload, dict)
    assert pool_runtime_payload.get("documents_by_database") == retry_payload.get("documents_by_database")

    first_publication_auth = first_execution.input_context.get("publication_auth")
    assert first_publication_auth == {
        "strategy": "actor",
        "actor_username": creator.username,
        "source": "run_create",
    }
    retry_publication_auth = execution.input_context.get("publication_auth")
    assert retry_publication_auth == {
        "strategy": "actor",
        "actor_username": retry_actor.username,
        "source": "retry_publication",
    }


@pytest.mark.django_db
def test_retry_workflow_execution_reuses_explicit_pool_workflow_binding() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
    workflow_binding = _ensure_runtime_test_workflow_binding(run=run)
    normalized_workflow_binding = PoolWorkflowBindingContract(**workflow_binding).model_dump(
        mode="json",
        exclude_none=True,
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-initial-binding",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        first = _start_runtime_workflow_execution(run=run, workflow_binding=workflow_binding)

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-retry-binding",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        retry = _start_runtime_retry_workflow_execution(
            run=run,
            retry_request={"documents_by_database": {}, "use_retry_subset_payload": False},
        )

    first_execution = WorkflowExecution.objects.get(id=first.execution_id)
    retry_execution = WorkflowExecution.objects.get(id=retry.execution_id)

    assert first_execution.input_context.get(POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY) == normalized_workflow_binding
    assert retry_execution.input_context.get(POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY) == normalized_workflow_binding
    assert retry_execution.input_context.get(POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_SLOTS_CONTEXT_KEY) == (
        first_execution.input_context.get(POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_SLOTS_CONTEXT_KEY)
    )
    assert retry_execution.input_context[POOL_RUNTIME_PROJECTION_CONTEXT_KEY]["workflow_binding"]["binding_id"] == (
        workflow_binding["binding_id"]
    )


@pytest.mark.django_db
def test_retry_workflow_execution_reuses_master_data_refs_and_binding_artifact() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-initial-master-data",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        first = _start_runtime_workflow_execution(run=run)

    first_execution = WorkflowExecution.objects.get(id=first.execution_id)
    first_execution.input_context = {
        **(first_execution.input_context or {}),
        "master_data_snapshot_ref": "master_data_snapshot.v1:lineage-fixed",
        "master_data_binding_artifact_ref": "master_data_binding_artifact.v1:lineage-fixed",
        POOL_RUNTIME_MASTER_DATA_BINDING_ARTIFACT_CONTEXT_KEY: {
            "version": MASTER_DATA_BINDING_ARTIFACT_VERSION,
            "run_id": str(run.id),
            "mode": MASTER_DATA_GATE_MODE_RESOLVE_UPSERT,
            "snapshot_ref": "master_data_snapshot.v1:lineage-fixed",
            "binding_artifact_ref": "master_data_binding_artifact.v1:lineage-fixed",
            "targets": [],
            "bindings": [],
            "diagnostics": [],
            "generated_at": "2026-01-01T00:00:00+00:00",
        },
    }
    first_execution.save(update_fields=["input_context"])

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-retry-master-data",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        retry = _start_runtime_retry_workflow_execution(
            run=run,
            retry_request={"documents_by_database": {}, "use_retry_subset_payload": False},
        )

    retry_execution = WorkflowExecution.objects.get(id=retry.execution_id)
    assert retry_execution.input_context.get("master_data_snapshot_ref") == "master_data_snapshot.v1:lineage-fixed"
    assert (
        retry_execution.input_context.get("master_data_binding_artifact_ref")
        == "master_data_binding_artifact.v1:lineage-fixed"
    )
    persisted_artifact = retry_execution.input_context.get(
        POOL_RUNTIME_MASTER_DATA_BINDING_ARTIFACT_CONTEXT_KEY
    )
    assert isinstance(persisted_artifact, dict)
    assert persisted_artifact.get("binding_artifact_ref") == "master_data_binding_artifact.v1:lineage-fixed"


@pytest.mark.django_db
def test_retry_workflow_execution_uses_persisted_document_plan_and_skips_successful_document_steps() -> None:
    run = _create_pool_run(mode=PoolRunMode.UNSAFE)
    failed_database = Database.objects.create(
        tenant=run.tenant,
        name=f"pool-runtime-retry-db-{uuid4().hex[:8]}",
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="legacy-user",
        password="legacy-pass",
    )
    skipped_database = Database.objects.create(
        tenant=run.tenant,
        name=f"pool-runtime-retry-db-{uuid4().hex[:8]}",
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="legacy-user",
        password="legacy-pass",
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-initial",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        first = _start_runtime_workflow_execution(run=run)

    first_execution = WorkflowExecution.objects.get(id=first.execution_id)
    first_execution.input_context = {
        **(first_execution.input_context or {}),
        "pool_runtime_document_plan_artifact": {
            "version": "document_plan_artifact.v1",
            "run_id": str(run.id),
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
                    "database_id": str(failed_database.id),
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
                },
                {
                    "database_id": str(skipped_database.id),
                    "chains": [
                        {
                            "chain_id": "sale-chain-skipped",
                            "edge_ref": {
                                "parent_node_id": "node-parent",
                                "child_node_id": "node-child-skipped",
                            },
                            "policy_source": "edge.metadata.document_policy",
                            "policy_version": "document_policy.v1",
                            "allocation": {"amount": "50.00"},
                            "documents": [
                                {
                                    "document_id": "sale-doc-skipped",
                                    "entity_name": "Document_Sales",
                                    "document_role": "base",
                                    "field_mapping": {},
                                    "table_parts_mapping": {},
                                    "link_rules": {},
                                    "invoice_mode": "optional",
                                    "idempotency_key": "doc-sale-skip-key",
                                }
                            ],
                        }
                    ],
                },
            ],
            "compile_summary": {
                "compiled_edges": 1,
                "targets_count": 2,
                "chains_count": 2,
                "documents_count": 3,
                "compiled_at": "2026-01-01T00:00:00+00:00",
            },
        },
    }
    first_execution.save(update_fields=["input_context"])

    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=run.tenant,
        target_database=failed_database,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.FAILED,
        entity_name="Document_Sales",
        documents_count=2,
        posted=False,
        request_summary={
            "documents_count": 2,
            "document_idempotency_keys": ["doc-sale-key", "doc-invoice-key"],
        },
        response_summary={
            "posted": False,
            "successful_document_idempotency_keys": ["doc-sale-key"],
            "successful_document_refs": {"doc-sale-key": "sale-doc-ref"},
            "failed_document_idempotency_key": "doc-invoice-key",
        },
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id="workflow-op-retry",
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        retry = _start_runtime_retry_workflow_execution(
            run=run,
            retry_request={
                "target_database_ids": [str(failed_database.id)],
                "use_retry_subset_payload": True,
                "max_attempts": 1,
                "retry_interval_seconds": 0,
                "external_key_field": "ExternalRunKey",
            },
        )

    execution = WorkflowExecution.objects.get(id=retry.execution_id)
    publication_payload = execution.input_context.get("pool_runtime_publication_payload")
    assert isinstance(publication_payload, dict)
    pool_runtime_payload = publication_payload.get("pool_runtime")
    assert isinstance(pool_runtime_payload, dict)
    document_chains_by_database = pool_runtime_payload.get("document_chains_by_database")
    assert document_chains_by_database == {
        str(failed_database.id): [
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
                        "document_id": "invoice-doc",
                        "entity_name": "Document_Invoice",
                        "document_role": "invoice",
                        "idempotency_key": "doc-invoice-key",
                        "invoice_mode": "required",
                        "field_mapping": {},
                        "table_parts_mapping": {},
                        "link_rules": {},
                        "payload": {},
                        "link_to": "sale-doc",
                        "resolved_link_refs": {"sale-doc": "sale-doc-ref"},
                    }
                ],
            }
        ]
    }
    assert pool_runtime_payload.get("documents_by_database") == {
        str(failed_database.id): [{"Amount": "100.00"}]
    }

    node_ids = [node.id for node in execution.workflow_template.dag_structure.nodes]
    atomic_publication_node_ids = [
        node_id for node_id in node_ids if node_id.startswith("publication_odata_")
    ]
    assert "publication_odata" not in node_ids
    assert len(atomic_publication_node_ids) == 1

    operation_bindings = execution.execution_plan.get("operation_bindings")
    assert isinstance(operation_bindings, list)
    publication_bindings = [
        item
        for item in operation_bindings
        if str(item.get("alias") or "") == "pool.publication_odata"
    ]
    assert len(publication_bindings) == 1

    publication_provenance = publication_bindings[0].get("provenance")
    assert isinstance(publication_provenance, dict)
    assert publication_provenance.get("database_id") == str(failed_database.id)
    assert publication_provenance.get("chain_id") == "sale-chain"
    assert publication_provenance.get("document_id") == "invoice-doc"
    assert publication_provenance.get("document_role") == "invoice"
