from __future__ import annotations

from datetime import date
from uuid import uuid4
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from apps.databases.models import Database, InfobaseUserMapping
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolNodeVersion,
    PoolPublicationAttempt,
    PoolPublicationAttemptStatus,
    PoolRun,
    PoolRunDirection,
    PoolRunMode,
)
from apps.intercompany_pools.runs import build_pool_run_idempotency_key
from apps.intercompany_pools.workflow_runtime import (
    start_pool_run_retry_workflow_execution,
    start_pool_run_workflow_execution,
)
from apps.operations.services.operations_service.types import EnqueueResult
from apps.templates.workflow.models import WorkflowExecution
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
    PoolNodeVersion.objects.create(
        pool=pool,
        organization=organization,
        effective_from=period_start,
        is_root=True,
    )
    return database


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_persists_pinned_binding_snapshot() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)

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
        result = start_pool_run_workflow_execution(run=run)

    execution = WorkflowExecution.objects.get(id=result.execution_id)
    operation_bindings = execution.execution_plan.get("operation_bindings")
    assert isinstance(operation_bindings, list)
    assert len(operation_bindings) >= 4
    assert all(item.get("binding_mode") == "pinned_exposure" for item in operation_bindings)
    assert all(str(item.get("template_exposure_id") or "").strip() for item in operation_bindings)
    assert all(int(item.get("template_exposure_revision") or 0) >= 1 for item in operation_bindings)

    binding_entries = [
        item
        for item in execution.bindings
        if str(item.get("target_ref") or "").startswith("workflow.operation_ref.")
    ]
    assert len(binding_entries) == len(operation_bindings)
    assert all(item.get("binding_mode") == "pinned_exposure" for item in binding_entries)


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
        result = start_pool_run_workflow_execution(run=run, requested_by=actor)

    execution = WorkflowExecution.objects.get(id=result.execution_id)
    publication_auth = execution.input_context.get("publication_auth")
    assert publication_auth == {
        "strategy": "actor",
        "actor_username": actor.username,
        "source": "run_create",
    }


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
        result = start_pool_run_workflow_execution(run=run)

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
        result = start_pool_run_workflow_execution(run=run)

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
    _attach_pool_target_database(
        tenant=run.tenant,
        pool=run.pool,
        period_start=run.period_start,
    )
    actor = User.objects.create_user(
        username=f"workflow-missing-map-{uuid4().hex[:8]}",
        email=f"workflow-missing-map-{uuid4().hex[:8]}@example.test",
    )

    with pytest.raises(ValueError) as exc:
        start_pool_run_workflow_execution(run=run, requested_by=actor)

    error_text = str(exc.value)
    assert "ODATA_MAPPING_NOT_CONFIGURED" in error_text
    assert "/rbac" in error_text


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_uses_service_mapping_when_actor_not_provided() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
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
        result = start_pool_run_workflow_execution(run=run, requested_by=None)

    execution = WorkflowExecution.objects.get(id=result.execution_id)
    assert execution.input_context.get("publication_auth") == {
        "strategy": "service",
        "actor_username": "",
        "source": "run_create",
    }


@pytest.mark.django_db
def test_start_pool_run_workflow_execution_fail_closed_when_service_mapping_ambiguous() -> None:
    run = _create_pool_run(mode=PoolRunMode.SAFE)
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
        start_pool_run_workflow_execution(run=run, requested_by=None)

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
        result_1 = start_pool_run_workflow_execution(run=run_1)
        result_2 = start_pool_run_workflow_execution(run=run_2)

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
        first = start_pool_run_workflow_execution(run=run, requested_by=creator)

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
        retry = start_pool_run_retry_workflow_execution(
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
        first = start_pool_run_workflow_execution(run=run)

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
        retry = start_pool_run_retry_workflow_execution(
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
                        "payload": {"Amount": "100.00"},
                        "link_to": "sale-doc",
                    }
                ],
            }
        ]
    }
    assert pool_runtime_payload.get("documents_by_database") == {
        str(failed_database.id): [{"Amount": "100.00"}]
    }
