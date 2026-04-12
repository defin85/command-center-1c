from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from apps.databases.models import Cluster, Database
from apps.intercompany_pools.master_data_bootstrap_collection_execution import (
    execute_pool_master_data_bootstrap_collection_step,
)
from apps.intercompany_pools.master_data_bootstrap_collection_service import (
    _COLLECTION_FANOUT_BATCH_SIZE,
    _COLLECTION_OPERATION_ID,
    _COLLECTION_STAGE_RUNNER,
    _COLLECTION_WORKFLOW_EXECUTION_ID,
    mark_pool_master_data_bootstrap_collection_failed,
    run_pool_master_data_bootstrap_collection_stage_chunk,
)
from apps.intercompany_pools.master_data_bootstrap_collection_workflow_contract import (
    build_pool_master_data_bootstrap_collection_workflow_input_context,
)
from apps.intercompany_pools.master_data_bootstrap_collection_workflow_runtime import (
    start_pool_master_data_bootstrap_collection_execute_workflow,
    start_pool_master_data_bootstrap_collection_stage_workflow,
)
from apps.intercompany_pools.models import (
    PoolMasterDataBootstrapCollectionItem,
    PoolMasterDataBootstrapCollectionItemStatus,
    PoolMasterDataBootstrapCollectionMode,
    PoolMasterDataBootstrapCollectionRequest,
    PoolMasterDataBootstrapCollectionStatus,
    PoolMasterDataBootstrapCollectionTargetMode,
)
from apps.operations.services import EnqueueResult
from apps.templates.workflow.models import WorkflowExecution
from apps.tenancy.models import Tenant
import apps.intercompany_pools.master_data_bootstrap_collection_execution as bootstrap_collection_execution


def _create_cluster(*, tenant: Tenant, suffix: str) -> Cluster:
    return Cluster.objects.create(
        tenant=tenant,
        name=f"bootstrap-collection-cluster-{suffix}",
        ras_server=f"bootstrap-collection-{suffix}:1545",
        cluster_service_url=f"http://bootstrap-collection-{suffix}.local",
    )


def _create_database(*, tenant: Tenant, cluster: Cluster, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        cluster=cluster,
        name=f"bootstrap-collection-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/bootstrap-collection-{suffix}.odata",
        username="admin",
        password="secret",
    )


def _create_collection(
    *,
    suffix: str = "runtime",
    mode: str = PoolMasterDataBootstrapCollectionMode.EXECUTE,
    status: str = PoolMasterDataBootstrapCollectionStatus.EXECUTE_RUNNING,
    item_count: int = 1,
    item_status: str = PoolMasterDataBootstrapCollectionItemStatus.PENDING,
    item_metadata: dict | None = None,
    collection_metadata: dict | None = None,
) -> PoolMasterDataBootstrapCollectionRequest:
    tenant = Tenant.objects.create(
        slug=f"bootstrap-collection-{suffix}-{uuid4().hex[:6]}",
        name="Bootstrap Collection Runtime",
    )
    cluster = _create_cluster(tenant=tenant, suffix=suffix)
    databases = [
        _create_database(tenant=tenant, cluster=cluster, suffix=f"{suffix}-{index}")
        for index in range(item_count)
    ]
    collection = PoolMasterDataBootstrapCollectionRequest.objects.create(
        tenant=tenant,
        target_mode=PoolMasterDataBootstrapCollectionTargetMode.DATABASE_SET,
        mode=mode,
        database_ids=[str(database.id) for database in databases],
        entity_scope=["party", "item"],
        status=status,
        metadata=collection_metadata or {},
    )
    for database in databases:
        PoolMasterDataBootstrapCollectionItem.objects.create(
            collection=collection,
            database=database,
            status=item_status,
            metadata=item_metadata or {},
        )
    return collection


@pytest.mark.django_db(transaction=True)
def test_start_bootstrap_collection_stage_workflow_creates_execution_and_links_operation_ids() -> None:
    collection = _create_collection(
        suffix="start",
        mode=PoolMasterDataBootstrapCollectionMode.DRY_RUN,
        status=PoolMasterDataBootstrapCollectionStatus.DRY_RUN_RUNNING,
    )

    with patch(
        "apps.intercompany_pools.master_data_bootstrap_collection_workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id=str(uuid4()),
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        result = start_pool_master_data_bootstrap_collection_stage_workflow(
            collection=collection,
            stage=PoolMasterDataBootstrapCollectionMode.DRY_RUN,
            correlation_id="corr-bootstrap-collection-runtime-001",
            origin_system="tests",
            origin_event_id="evt-bootstrap-collection-runtime-001",
            actor_username="bootstrap-admin",
        )

    assert result.enqueue_success is True
    collection.refresh_from_db()
    metadata = collection.metadata
    assert metadata[_COLLECTION_WORKFLOW_EXECUTION_ID]
    assert metadata[_COLLECTION_OPERATION_ID]
    assert metadata[_COLLECTION_STAGE_RUNNER]["stage"] == PoolMasterDataBootstrapCollectionMode.DRY_RUN
    assert collection.status == PoolMasterDataBootstrapCollectionStatus.DRY_RUN_RUNNING

    execution = WorkflowExecution.objects.get(id=metadata[_COLLECTION_WORKFLOW_EXECUTION_ID])
    assert execution.execution_consumer == "pools"
    assert execution.input_context["collection_id"] == str(collection.id)
    assert execution.input_context["tenant_id"] == str(collection.tenant_id)
    assert execution.input_context["stage"] == PoolMasterDataBootstrapCollectionMode.DRY_RUN
    assert execution.input_context["actor_username"] == "bootstrap-admin"


@pytest.mark.django_db(transaction=True)
def test_start_bootstrap_collection_execute_wrapper_uses_execute_stage() -> None:
    collection = _create_collection(suffix="execute-wrapper")

    with patch(
        "apps.intercompany_pools.master_data_bootstrap_collection_workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id=str(uuid4()),
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        result = start_pool_master_data_bootstrap_collection_execute_workflow(
            collection=collection,
            correlation_id="corr-bootstrap-collection-runtime-002",
            origin_system="tests",
            origin_event_id="evt-bootstrap-collection-runtime-002",
            actor_username="bootstrap-admin",
        )

    assert result.stage == PoolMasterDataBootstrapCollectionMode.EXECUTE
    collection.refresh_from_db()
    assert collection.metadata[_COLLECTION_STAGE_RUNNER]["stage"] == PoolMasterDataBootstrapCollectionMode.EXECUTE


@pytest.mark.django_db
def test_mark_bootstrap_collection_failed_sets_failed_status_and_error() -> None:
    collection = _create_collection(suffix="step-failed")
    refreshed = mark_pool_master_data_bootstrap_collection_failed(
        collection_id=str(collection.id),
        error_code="BOOTSTRAP_COLLECTION_EXECUTE_FANOUT_FAILED",
        error_detail="Execute fan-out failed for the batch collection.",
    )

    assert refreshed is not None
    collection.refresh_from_db()
    assert collection.status == PoolMasterDataBootstrapCollectionStatus.FAILED
    assert collection.last_error_code == "BOOTSTRAP_COLLECTION_EXECUTE_FANOUT_FAILED"
    assert collection.last_error == "Execute fan-out failed for the batch collection."


@pytest.mark.django_db
def test_run_bootstrap_collection_stage_chunk_processes_only_configured_batch_size_for_dry_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = _create_collection(
        suffix="chunked",
        mode=PoolMasterDataBootstrapCollectionMode.DRY_RUN,
        status=PoolMasterDataBootstrapCollectionStatus.DRY_RUN_RUNNING,
        item_count=2,
        item_status=PoolMasterDataBootstrapCollectionItemStatus.PENDING,
        item_metadata={
            "preflight_result": {
                "ok": True,
                "source_kind": "ib_odata",
                "coverage": {"party": True},
                "credential_strategy": "service",
                "errors": [],
                "diagnostics": {},
            }
        },
        collection_metadata={_COLLECTION_FANOUT_BATCH_SIZE: 1, "chunk_size": 50},
    )

    def _dry_run_preview(*, database: Database, **_kwargs):
        return {
            "rows_total": 1,
            "chunks_total": 1,
            "entities": [{"entity_type": "party", "rows_total": 1, "chunks_total": 1}],
            "database_id": str(database.id),
        }

    monkeypatch.setattr(
        "apps.intercompany_pools.master_data_bootstrap_collection_service.run_pool_master_data_bootstrap_dry_run_preview",
        _dry_run_preview,
    )

    result = run_pool_master_data_bootstrap_collection_stage_chunk(
        collection_id=str(collection.id),
        stage=PoolMasterDataBootstrapCollectionMode.DRY_RUN,
    )

    assert result.processed_items == 1
    assert result.pending_items == 1
    assert result.should_continue is True
    collection.refresh_from_db()
    assert collection.status == PoolMasterDataBootstrapCollectionStatus.DRY_RUN_RUNNING
    items = list(collection.items.order_by("created_at"))
    assert [item.status for item in items].count(PoolMasterDataBootstrapCollectionItemStatus.COMPLETED) == 1
    assert [item.status for item in items].count(PoolMasterDataBootstrapCollectionItemStatus.PENDING) == 1


@pytest.mark.django_db
def test_execute_bootstrap_collection_step_calls_fail_closed_hook_when_stage_chunk_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = _create_collection(suffix="step-hook")
    input_context = build_pool_master_data_bootstrap_collection_workflow_input_context(
        collection_id=str(collection.id),
        tenant_id=str(collection.tenant_id),
        stage=PoolMasterDataBootstrapCollectionMode.EXECUTE,
        runner_token="execute-runner",
        correlation_id="corr-bootstrap-collection-step-001",
        origin_system="tests",
        origin_event_id="evt-bootstrap-collection-step-001",
        actor_username="bootstrap-admin",
    )

    class _FanoutError(RuntimeError):
        code = "BOOTSTRAP_COLLECTION_EXECUTE_FANOUT_FAILED"
        detail = "Execute fan-out failed for the batch collection."

    def _raise_fanout(*, collection_id: str, stage: str, runner_token: str) -> None:
        raise _FanoutError(f"boom:{collection_id}:{stage}:{runner_token}")

    monkeypatch.setattr(
        bootstrap_collection_execution,
        "run_pool_master_data_bootstrap_collection_stage_chunk",
        _raise_fanout,
    )
    fail_closed_calls: list[dict[str, str]] = []

    def _capture_fail_closed(*, collection_id: str, error_code: str, error_detail: str):
        fail_closed_calls.append(
            {
                "collection_id": collection_id,
                "error_code": error_code,
                "error_detail": error_detail,
            }
        )
        return None

    monkeypatch.setattr(
        bootstrap_collection_execution,
        "mark_pool_master_data_bootstrap_collection_failed",
        _capture_fail_closed,
    )

    with pytest.raises(_FanoutError):
        execute_pool_master_data_bootstrap_collection_step(input_context=input_context)

    assert fail_closed_calls == [
        {
            "collection_id": str(collection.id),
            "error_code": "BOOTSTRAP_COLLECTION_EXECUTE_FANOUT_FAILED",
            "error_detail": "Execute fan-out failed for the batch collection.",
        }
    ]


@pytest.mark.django_db
def test_execute_bootstrap_collection_step_requeues_followup_when_pending_items_remain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = _create_collection(
        suffix="followup",
        mode=PoolMasterDataBootstrapCollectionMode.DRY_RUN,
        status=PoolMasterDataBootstrapCollectionStatus.DRY_RUN_RUNNING,
    )
    input_context = build_pool_master_data_bootstrap_collection_workflow_input_context(
        collection_id=str(collection.id),
        tenant_id=str(collection.tenant_id),
        stage=PoolMasterDataBootstrapCollectionMode.DRY_RUN,
        runner_token="dry-runner",
        correlation_id="corr-bootstrap-collection-step-002",
        origin_system="tests",
        origin_event_id="evt-bootstrap-collection-step-002",
        actor_username="bootstrap-admin",
    )

    requeue_calls: list[dict[str, str]] = []

    def _result(*, collection_id: str, stage: str, runner_token: str):
        refreshed = PoolMasterDataBootstrapCollectionRequest.objects.get(id=collection_id)
        return type("ChunkResult", (), {
            "collection": refreshed,
            "stage": stage,
            "processed_items": 1,
            "pending_items": 1,
            "should_continue": True,
            "stale_runner": False,
        })()

    def _capture_requeue(*, collection, stage: str, **_kwargs):
        requeue_calls.append({"collection_id": str(collection.id), "stage": stage})
        return None

    monkeypatch.setattr(
        bootstrap_collection_execution,
        "run_pool_master_data_bootstrap_collection_stage_chunk",
        _result,
    )
    monkeypatch.setattr(
        bootstrap_collection_execution,
        "start_pool_master_data_bootstrap_collection_stage_workflow",
        _capture_requeue,
    )

    payload = execute_pool_master_data_bootstrap_collection_step(input_context=input_context)

    assert payload["stage"] == PoolMasterDataBootstrapCollectionMode.DRY_RUN
    assert payload["pending_items"] == 1
    assert requeue_calls == [
        {
            "collection_id": str(collection.id),
            "stage": PoolMasterDataBootstrapCollectionMode.DRY_RUN,
        }
    ]
