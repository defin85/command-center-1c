from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from apps.databases.models import Cluster, Database
from apps.intercompany_pools.master_data_sync_conflicts import MasterDataSyncConflictError
from apps.intercompany_pools.master_data_sync_execution import PoolMasterDataSyncTriggerResult
from apps.intercompany_pools.master_data_sync_launch_service import (
    create_pool_master_data_sync_launch_request,
    run_pool_master_data_sync_launch_request_fanout,
)
from apps.intercompany_pools.master_data_sync_launch_workflow_runtime import (
    start_pool_master_data_sync_launch_request_workflow,
)
from apps.intercompany_pools.models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncDirection,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncJobStatus,
    PoolMasterDataSyncLaunchItemStatus,
    PoolMasterDataSyncLaunchMode,
    PoolMasterDataSyncLaunchRequest,
    PoolMasterDataSyncLaunchStatus,
    PoolMasterDataSyncPolicy,
)
from apps.operations.services import EnqueueResult
from apps.templates.workflow.models import WorkflowExecution
from apps.tenancy.models import Tenant


def _create_cluster(*, tenant: Tenant, suffix: str) -> Cluster:
    return Cluster.objects.create(
        tenant=tenant,
        name=f"sync-launch-cluster-{suffix}",
        ras_server=f"sync-launch-{suffix}:1545",
        cluster_service_url=f"http://sync-launch-{suffix}.local",
    )


def _create_database(*, tenant: Tenant, cluster: Cluster | None, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        cluster=cluster,
        name=f"sync-launch-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/sync-launch-{suffix}.odata",
        username="admin",
        password="secret",
    )


def _create_sync_job(
    *,
    tenant: Tenant,
    database: Database,
    entity_type: str,
    status: str = PoolMasterDataSyncJobStatus.RUNNING,
    direction: str = PoolMasterDataSyncDirection.INBOUND,
) -> PoolMasterDataSyncJob:
    return PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=database,
        entity_type=entity_type,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
        direction=direction,
        status=status,
    )


def _create_launch_request(
    *,
    tenant: Tenant,
    database_ids: list[str],
    entity_scope: list[str],
) -> PoolMasterDataSyncLaunchRequest:
    return PoolMasterDataSyncLaunchRequest.objects.create(
        tenant=tenant,
        mode=PoolMasterDataSyncLaunchMode.INBOUND,
        target_mode="database_set",
        database_ids=database_ids,
        entity_scope=entity_scope,
        status=PoolMasterDataSyncLaunchStatus.PENDING,
        metadata={},
    )


@pytest.mark.django_db(transaction=True)
def test_start_sync_launch_workflow_creates_execution_and_links_operation_ids() -> None:
    tenant = Tenant.objects.create(slug=f"sync-launch-runtime-{uuid4().hex[:6]}", name="Sync Launch Runtime")
    cluster = _create_cluster(tenant=tenant, suffix="start")
    database = _create_database(tenant=tenant, cluster=cluster, suffix="start")
    launch_request = _create_launch_request(
        tenant=tenant,
        database_ids=[str(database.id)],
        entity_scope=[PoolMasterDataEntityType.ITEM],
    )

    with patch(
        "apps.intercompany_pools.master_data_sync_launch_workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id=str(uuid4()),
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        result = start_pool_master_data_sync_launch_request_workflow(
            launch_request=launch_request,
            correlation_id="corr-sync-launch-runtime-001",
            origin_system="tests",
            origin_event_id="evt-sync-launch-runtime-001",
            actor_username="launch-admin",
        )

    assert result.enqueue_success is True
    launch_request.refresh_from_db()
    assert launch_request.status == PoolMasterDataSyncLaunchStatus.RUNNING
    assert launch_request.workflow_execution_id is not None
    assert launch_request.operation_id is not None
    execution = WorkflowExecution.objects.get(id=launch_request.workflow_execution_id)
    assert execution.execution_consumer == "pools"
    assert execution.input_context["launch_request_id"] == str(launch_request.id)
    assert execution.input_context["actor_username"] == "launch-admin"


@pytest.mark.django_db
def test_run_sync_launch_fanout_records_scheduled_coalesced_skipped_and_failed_outcomes() -> None:
    tenant = Tenant.objects.create(slug=f"sync-launch-fanout-{uuid4().hex[:6]}", name="Sync Launch Fanout")
    cluster = _create_cluster(tenant=tenant, suffix="fanout")
    database_a = _create_database(tenant=tenant, cluster=cluster, suffix="a")
    database_b = _create_database(tenant=tenant, cluster=cluster, suffix="b")
    launch_request = _create_launch_request(
        tenant=tenant,
        database_ids=[str(database_a.id), str(database_b.id)],
        entity_scope=[PoolMasterDataEntityType.ITEM, PoolMasterDataEntityType.PARTY],
    )
    item_a = launch_request.items.create(database=database_a, entity_type=PoolMasterDataEntityType.ITEM)
    party_a = launch_request.items.create(database=database_a, entity_type=PoolMasterDataEntityType.PARTY)
    item_b = launch_request.items.create(database=database_b, entity_type=PoolMasterDataEntityType.ITEM)
    party_b = launch_request.items.create(database=database_b, entity_type=PoolMasterDataEntityType.PARTY)

    scheduled_job = _create_sync_job(
        tenant=tenant,
        database=database_a,
        entity_type=PoolMasterDataEntityType.ITEM,
        status=PoolMasterDataSyncJobStatus.RUNNING,
    )
    coalesced_job = _create_sync_job(
        tenant=tenant,
        database=database_a,
        entity_type=PoolMasterDataEntityType.PARTY,
        status=PoolMasterDataSyncJobStatus.RUNNING,
    )
    failed_job = _create_sync_job(
        tenant=tenant,
        database=database_b,
        entity_type=PoolMasterDataEntityType.PARTY,
        status=PoolMasterDataSyncJobStatus.FAILED,
    )
    failed_job.last_error_code = "SERVER_AFFINITY_UNRESOLVED"
    failed_job.last_error = "Server affinity is unresolved."
    failed_job.save(update_fields=["last_error_code", "last_error", "updated_at"])

    def _trigger(**kwargs) -> PoolMasterDataSyncTriggerResult:
        database_id = str(kwargs["database_id"])
        entity_type = str(kwargs["entity_type"])
        if database_id == str(database_a.id) and entity_type == PoolMasterDataEntityType.ITEM:
            return PoolMasterDataSyncTriggerResult(
                sync_job=scheduled_job,
                created_job=True,
                started_workflow=True,
                skipped=False,
                skip_reason=None,
                policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
                policy_source="database_scope",
                start_result=SimpleNamespace(
                    enqueue_status="queued",
                    enqueue_error=None,
                    sync_job=scheduled_job,
                ),
            )
        if database_id == str(database_a.id) and entity_type == PoolMasterDataEntityType.PARTY:
            return PoolMasterDataSyncTriggerResult(
                sync_job=coalesced_job,
                created_job=False,
                started_workflow=True,
                skipped=False,
                skip_reason=None,
                policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
                policy_source="database_scope",
                start_result=SimpleNamespace(
                    enqueue_status="queued",
                    enqueue_error=None,
                    sync_job=coalesced_job,
                ),
            )
        if database_id == str(database_b.id) and entity_type == PoolMasterDataEntityType.ITEM:
            return PoolMasterDataSyncTriggerResult(
                sync_job=None,
                created_job=False,
                started_workflow=False,
                skipped=True,
                skip_reason="MASTER_DATA_SYNC_DISABLED",
                policy=None,
                policy_source=None,
                start_result=None,
            )
        raise MasterDataSyncConflictError(
            code="POLICY_VIOLATION",
            detail="Inbound sync is forbidden by effective policy.",
            conflict_id=str(uuid4()),
            entity_type=PoolMasterDataEntityType.PARTY,
            canonical_id="",
            diagnostics={"policy": "cc_master"},
        )

    with patch(
        "apps.intercompany_pools.master_data_sync_launch_service.trigger_pool_master_data_inbound_sync_job",
        side_effect=_trigger,
    ):
        refreshed = run_pool_master_data_sync_launch_request_fanout(
            launch_request_id=str(launch_request.id)
        )

    assert refreshed.status == PoolMasterDataSyncLaunchStatus.COMPLETED
    item_a.refresh_from_db()
    party_a.refresh_from_db()
    item_b.refresh_from_db()
    party_b.refresh_from_db()
    assert item_a.status == PoolMasterDataSyncLaunchItemStatus.SCHEDULED
    assert item_a.child_job_id == scheduled_job.id
    assert party_a.status == PoolMasterDataSyncLaunchItemStatus.COALESCED
    assert party_a.child_job_id == coalesced_job.id
    assert item_b.status == PoolMasterDataSyncLaunchItemStatus.SKIPPED
    assert item_b.reason_code == "MASTER_DATA_SYNC_DISABLED"
    assert party_b.status == PoolMasterDataSyncLaunchItemStatus.FAILED
    assert party_b.reason_code == "POLICY_VIOLATION"

    counters = refreshed.metadata["aggregate_counters"]
    assert counters["scheduled"] == 1
    assert counters["coalesced"] == 1
    assert counters["skipped"] == 1
    assert counters["failed"] == 1


@pytest.mark.django_db
def test_create_sync_launch_request_preserves_immutable_target_snapshot() -> None:
    tenant = Tenant.objects.create(slug=f"sync-launch-snapshot-{uuid4().hex[:6]}", name="Sync Launch Snapshot")
    cluster = _create_cluster(tenant=tenant, suffix="snapshot")
    database_a = _create_database(tenant=tenant, cluster=cluster, suffix="snapshot-a")
    database_b = _create_database(tenant=tenant, cluster=cluster, suffix="snapshot-b")

    with patch(
        "apps.intercompany_pools.master_data_sync_launch_workflow_runtime.start_pool_master_data_sync_launch_request_workflow",
        return_value=SimpleNamespace(enqueue_success=True),
    ):
        launch_request = create_pool_master_data_sync_launch_request(
            tenant=tenant,
            mode=PoolMasterDataSyncLaunchMode.INBOUND,
            target_mode="cluster_all",
            cluster_id=str(cluster.id),
            database_ids=[],
            entity_scope=[PoolMasterDataEntityType.ITEM],
            actor_id="1",
            actor_username="snapshot-admin",
        )

    assert launch_request.database_ids == [str(database_a.id), str(database_b.id)]

    database_c = _create_database(tenant=tenant, cluster=cluster, suffix="snapshot-c")
    refreshed = PoolMasterDataSyncLaunchRequest.objects.get(id=launch_request.id)
    assert refreshed.database_ids == [str(database_a.id), str(database_b.id)]
    assert str(database_c.id) not in refreshed.database_ids


@pytest.mark.django_db
def test_run_sync_launch_fanout_processes_items_in_configured_chunks() -> None:
    tenant = Tenant.objects.create(slug=f"sync-launch-chunks-{uuid4().hex[:6]}", name="Sync Launch Chunks")
    cluster = _create_cluster(tenant=tenant, suffix="chunks")
    databases = [
        _create_database(tenant=tenant, cluster=cluster, suffix=f"chunks-{index}")
        for index in range(5)
    ]

    with patch(
        "apps.intercompany_pools.master_data_sync_launch_workflow_runtime.start_pool_master_data_sync_launch_request_workflow",
        return_value=SimpleNamespace(enqueue_success=True),
    ):
        launch_request = create_pool_master_data_sync_launch_request(
            tenant=tenant,
            mode=PoolMasterDataSyncLaunchMode.INBOUND,
            target_mode="database_set",
            cluster_id=None,
            database_ids=[str(database.id) for database in databases],
            entity_scope=[PoolMasterDataEntityType.ITEM],
            actor_id="1",
            actor_username="chunk-admin",
        )

    def _trigger(**kwargs) -> PoolMasterDataSyncTriggerResult:
        database = Database.objects.get(id=kwargs["database_id"])
        child_job = _create_sync_job(
            tenant=tenant,
            database=database,
            entity_type=PoolMasterDataEntityType.ITEM,
            status=PoolMasterDataSyncJobStatus.RUNNING,
        )
        return PoolMasterDataSyncTriggerResult(
            sync_job=child_job,
            created_job=True,
            started_workflow=True,
            skipped=False,
            skip_reason=None,
            policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
            policy_source="database_scope",
            start_result=SimpleNamespace(
                enqueue_status="queued",
                enqueue_error=None,
                sync_job=child_job,
            ),
        )

    with patch(
        "apps.intercompany_pools.master_data_sync_launch_service.SYNC_LAUNCH_FANOUT_CHUNK_SIZE",
        2,
    ), patch(
        "apps.intercompany_pools.master_data_sync_launch_service.trigger_pool_master_data_inbound_sync_job",
        side_effect=_trigger,
    ):
        refreshed = run_pool_master_data_sync_launch_request_fanout(
            launch_request_id=str(launch_request.id)
        )

    assert refreshed.status == PoolMasterDataSyncLaunchStatus.COMPLETED
    chunk_events = [
        entry
        for entry in refreshed.metadata["audit_trail"]
        if entry.get("action") == "fanout_chunk_completed"
    ]
    assert len(chunk_events) == 3
    assert [entry["metadata"]["chunk_size"] for entry in chunk_events] == [2, 2, 1]
    assert [entry["metadata"]["processed_items"] for entry in chunk_events] == [2, 4, 5]
    assert all(entry["metadata"]["configured_chunk_size"] == 2 for entry in chunk_events)
