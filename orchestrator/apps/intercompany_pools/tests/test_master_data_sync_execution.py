from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.master_data_sync_conflicts import (
    MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
    MasterDataSyncConflictError,
)
from apps.intercompany_pools.master_data_sync_execution import (
    MASTER_DATA_SYNC_OUTBOUND_DISABLED,
    execute_pool_master_data_sync_dispatch_step,
    execute_pool_master_data_sync_finalize_step,
    trigger_pool_master_data_outbound_sync_job,
)
from apps.intercompany_pools.master_data_sync_runtime_settings import (
    POOL_MASTER_DATA_SYNC_DEFAULT_POLICY_RUNTIME_KEY,
    POOL_MASTER_DATA_SYNC_ENABLED_RUNTIME_KEY,
    POOL_MASTER_DATA_SYNC_OUTBOUND_ENABLED_RUNTIME_KEY,
)
from apps.intercompany_pools.models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncDirection,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncJobStatus,
    PoolMasterDataSyncPolicy,
    PoolMasterDataSyncScope,
)
from apps.operations.services import EnqueueResult
from apps.runtime_settings.models import RuntimeSetting
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"sync-execution-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


def _set_runtime(
    *,
    enabled: bool = True,
    outbound_enabled: bool = True,
    default_policy: str = PoolMasterDataSyncPolicy.CC_MASTER,
) -> None:
    RuntimeSetting.objects.create(key=POOL_MASTER_DATA_SYNC_ENABLED_RUNTIME_KEY, value=enabled)
    RuntimeSetting.objects.create(
        key=POOL_MASTER_DATA_SYNC_OUTBOUND_ENABLED_RUNTIME_KEY,
        value=outbound_enabled,
    )
    RuntimeSetting.objects.create(
        key=POOL_MASTER_DATA_SYNC_DEFAULT_POLICY_RUNTIME_KEY,
        value=default_policy,
    )


@pytest.mark.django_db
def test_trigger_outbound_sync_creates_job_and_starts_workflow() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-trigger-{uuid4().hex[:6]}", name="Sync Exec Trigger")
    database = _create_database(tenant=tenant, suffix="trigger")
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )
    _set_runtime(enabled=True, outbound_enabled=True)

    def _enqueue(execution_id: str, workflow_config: dict | None = None) -> EnqueueResult:
        return EnqueueResult(
            success=True,
            operation_id=execution_id,
            status="queued",
            error=None,
            error_code=None,
        )

    with patch(
        "apps.intercompany_pools.master_data_sync_workflow_runtime.OperationsService.enqueue_workflow_execution",
        side_effect=_enqueue,
    ):
        result = trigger_pool_master_data_outbound_sync_job(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.ITEM,
            canonical_id="item-001",
            origin_system="cc",
            origin_event_id="evt-trigger-001",
        )

    assert result.skipped is False
    assert result.created_job is True
    assert result.started_workflow is True
    assert result.policy == PoolMasterDataSyncPolicy.BIDIRECTIONAL
    assert result.policy_source == "database_scope"
    assert result.sync_job is not None
    assert result.sync_job.status == PoolMasterDataSyncJobStatus.RUNNING
    assert result.sync_job.workflow_execution_id is not None
    assert result.sync_job.operation_id is not None


@pytest.mark.django_db
def test_trigger_outbound_sync_uses_runtime_default_policy_when_scope_missing() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-default-{uuid4().hex[:6]}", name="Sync Exec Default")
    database = _create_database(tenant=tenant, suffix="default")
    _set_runtime(
        enabled=True,
        outbound_enabled=True,
        default_policy=PoolMasterDataSyncPolicy.CC_MASTER,
    )

    with patch(
        "apps.intercompany_pools.master_data_sync_workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=True,
            operation_id=str(uuid4()),
            status="queued",
            error=None,
            error_code=None,
        ),
    ):
        result = trigger_pool_master_data_outbound_sync_job(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.PARTY,
            canonical_id="party-001",
            origin_system="cc",
            origin_event_id="evt-default-001",
        )

    assert result.skipped is False
    assert result.policy == PoolMasterDataSyncPolicy.CC_MASTER
    assert result.policy_source == "runtime_default"
    assert result.sync_job is not None
    assert result.sync_job.policy == PoolMasterDataSyncPolicy.CC_MASTER


@pytest.mark.django_db
def test_trigger_outbound_sync_skips_when_outbound_runtime_gate_is_disabled() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-skip-{uuid4().hex[:6]}", name="Sync Exec Skip")
    database = _create_database(tenant=tenant, suffix="skip")
    _set_runtime(enabled=True, outbound_enabled=False)

    result = trigger_pool_master_data_outbound_sync_job(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-skip-001",
        origin_system="cc",
        origin_event_id="evt-skip-001",
    )

    assert result.skipped is True
    assert result.skip_reason == MASTER_DATA_SYNC_OUTBOUND_DISABLED
    assert PoolMasterDataSyncJob.objects.filter(tenant=tenant).count() == 0


@pytest.mark.django_db
def test_dispatch_step_fails_closed_with_policy_violation_conflict() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-conflict-{uuid4().hex[:6]}", name="Sync Exec Conflict")
    database = _create_database(tenant=tenant, suffix="conflict")
    _set_runtime(enabled=True, outbound_enabled=True, default_policy=PoolMasterDataSyncPolicy.CC_MASTER)
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.IB_MASTER,
    )
    sync_job = PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.IB_MASTER,
        direction=PoolMasterDataSyncDirection.OUTBOUND,
        status=PoolMasterDataSyncJobStatus.RUNNING,
    )

    with pytest.raises(MasterDataSyncConflictError) as exc_info:
        execute_pool_master_data_sync_dispatch_step(
            input_context={
                "contract_version": "pool_master_data_sync_workflow.v1",
                "sync_job_id": str(sync_job.id),
                "tenant_id": str(tenant.id),
                "database_id": str(database.id),
                "entity_type": PoolMasterDataEntityType.ITEM,
                "sync_policy": PoolMasterDataSyncPolicy.IB_MASTER,
                "sync_direction": PoolMasterDataSyncDirection.OUTBOUND,
                "correlation_id": "corr-dispatch-001",
                "origin_system": "cc",
                "origin_event_id": "evt-dispatch-001",
            }
        )

    assert exc_info.value.code == MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION
    conflict = PoolMasterDataSyncConflict.objects.get(id=exc_info.value.conflict_id)
    assert conflict.conflict_code == MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION
    assert conflict.entity_type == PoolMasterDataEntityType.ITEM


@pytest.mark.django_db
def test_finalize_step_marks_job_succeeded() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-finalize-{uuid4().hex[:6]}", name="Sync Exec Finalize")
    database = _create_database(tenant=tenant, suffix="finalize")
    sync_job = PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.CONTRACT,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
        direction=PoolMasterDataSyncDirection.OUTBOUND,
        status=PoolMasterDataSyncJobStatus.RUNNING,
    )

    output = execute_pool_master_data_sync_finalize_step(
        input_context={
            "contract_version": "pool_master_data_sync_workflow.v1",
            "sync_job_id": str(sync_job.id),
            "tenant_id": str(tenant.id),
            "database_id": str(database.id),
            "entity_type": PoolMasterDataEntityType.CONTRACT,
            "sync_policy": PoolMasterDataSyncPolicy.BIDIRECTIONAL,
            "sync_direction": PoolMasterDataSyncDirection.OUTBOUND,
            "correlation_id": "corr-finalize-001",
            "origin_system": "cc",
            "origin_event_id": "evt-finalize-001",
        }
    )

    sync_job.refresh_from_db()
    assert output["status"] == PoolMasterDataSyncJobStatus.SUCCEEDED
    assert sync_job.status == PoolMasterDataSyncJobStatus.SUCCEEDED
    assert sync_job.finished_at is not None
