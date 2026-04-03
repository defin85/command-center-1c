from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.master_data_sync_conflicts import (
    MASTER_DATA_SYNC_CONFLICT_APPLY,
    MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
    MasterDataSyncConflictError,
)
from apps.intercompany_pools.master_data_sync_inbound_poller import (
    MasterDataSyncInboundChange,
    MasterDataSyncSelectChangesResult,
)
from apps.intercompany_pools.master_data_sync_execution import (
    LegacyInboundRouteDisabledError,
    MASTER_DATA_SYNC_INBOUND_CALLBACKS_NOT_CONFIGURED,
    MASTER_DATA_SYNC_INBOUND_CAPABILITY_DISABLED,
    MASTER_DATA_SYNC_INBOUND_DISABLED,
    MASTER_DATA_SYNC_OUTBOUND_CAPABILITY_DISABLED,
    MASTER_DATA_SYNC_OUTBOUND_DISABLED,
    MASTER_DATA_SYNC_RECONCILE_CAPABILITY_DISABLED,
    configure_pool_master_data_sync_inbound_callbacks,
    execute_pool_master_data_sync_dispatch_step,
    execute_pool_master_data_sync_finalize_step,
    execute_pool_master_data_sync_inbound_step,
    reset_pool_master_data_sync_inbound_callbacks,
    run_pool_master_data_sync_legacy_inbound_route,
    trigger_pool_master_data_inbound_sync_job,
    trigger_pool_master_data_outbound_sync_job,
    trigger_pool_master_data_reconcile_sync_job,
)
from apps.intercompany_pools.master_data_sync_runtime_settings import (
    POOL_MASTER_DATA_SYNC_DEFAULT_POLICY_RUNTIME_KEY,
    POOL_MASTER_DATA_SYNC_ENABLED_RUNTIME_KEY,
    POOL_MASTER_DATA_SYNC_INBOUND_ENABLED_RUNTIME_KEY,
    POOL_MASTER_DATA_SYNC_OUTBOUND_ENABLED_RUNTIME_KEY,
)
from apps.intercompany_pools.master_data_registry import (
    POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND,
    POOL_MASTER_DATA_CAPABILITY_SYNC_OUTBOUND,
    POOL_MASTER_DATA_CAPABILITY_SYNC_RECONCILE,
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
    inbound_enabled: bool = True,
    outbound_enabled: bool = True,
    default_policy: str = PoolMasterDataSyncPolicy.CC_MASTER,
) -> None:
    RuntimeSetting.objects.create(key=POOL_MASTER_DATA_SYNC_ENABLED_RUNTIME_KEY, value=enabled)
    RuntimeSetting.objects.create(
        key=POOL_MASTER_DATA_SYNC_INBOUND_ENABLED_RUNTIME_KEY,
        value=inbound_enabled,
    )
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
def test_trigger_outbound_sync_skips_when_registry_disables_outbound_capability() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-outbound-cap-{uuid4().hex[:6]}", name="Sync Exec Outbound Cap")
    database = _create_database(tenant=tenant, suffix="outbound-cap")
    _set_runtime(enabled=True, outbound_enabled=True)

    def _supports(*, entity_type: str, capability: str, include_bootstrap_helpers: bool = False) -> bool:
        if capability == POOL_MASTER_DATA_CAPABILITY_SYNC_OUTBOUND:
            return False
        return True

    with patch(
        "apps.intercompany_pools.master_data_sync_execution.supports_pool_master_data_capability",
        side_effect=_supports,
    ):
        result = trigger_pool_master_data_outbound_sync_job(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.ITEM,
            canonical_id="item-capability-off",
            origin_system="cc",
            origin_event_id="evt-capability-off",
        )

    assert result.skipped is True
    assert result.skip_reason == MASTER_DATA_SYNC_OUTBOUND_CAPABILITY_DISABLED
    assert PoolMasterDataSyncJob.objects.filter(tenant=tenant).count() == 0


@pytest.mark.django_db
def test_trigger_inbound_sync_creates_job_and_starts_workflow() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-inbound-{uuid4().hex[:6]}", name="Sync Exec Inbound")
    database = _create_database(tenant=tenant, suffix="inbound")
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )
    _set_runtime(enabled=True, inbound_enabled=True, outbound_enabled=True)

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
        result = trigger_pool_master_data_inbound_sync_job(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.ITEM,
            origin_system="ib",
            origin_event_id="evt-inbound-001",
        )

    assert result.skipped is False
    assert result.created_job is True
    assert result.started_workflow is True
    assert result.sync_job is not None
    assert result.sync_job.direction == PoolMasterDataSyncDirection.INBOUND
    assert result.sync_job.status == PoolMasterDataSyncJobStatus.RUNNING
    assert result.sync_job.workflow_execution_id is not None
    assert result.sync_job.operation_id is not None


@pytest.mark.django_db
def test_trigger_inbound_sync_skips_when_inbound_runtime_gate_is_disabled() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-inbound-skip-{uuid4().hex[:6]}", name="Sync Exec Inbound Skip")
    database = _create_database(tenant=tenant, suffix="inbound-skip")
    _set_runtime(enabled=True, inbound_enabled=False, outbound_enabled=True)

    result = trigger_pool_master_data_inbound_sync_job(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=PoolMasterDataEntityType.ITEM,
        origin_system="ib",
        origin_event_id="evt-inbound-skip-001",
    )

    assert result.skipped is True
    assert result.skip_reason == MASTER_DATA_SYNC_INBOUND_DISABLED
    assert PoolMasterDataSyncJob.objects.filter(tenant=tenant).count() == 0


@pytest.mark.django_db
def test_trigger_inbound_sync_skips_when_registry_disables_inbound_capability() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-inbound-cap-{uuid4().hex[:6]}", name="Sync Exec Inbound Cap")
    database = _create_database(tenant=tenant, suffix="inbound-cap")
    _set_runtime(enabled=True, inbound_enabled=True, outbound_enabled=True)

    def _supports(*, entity_type: str, capability: str, include_bootstrap_helpers: bool = False) -> bool:
        if capability == POOL_MASTER_DATA_CAPABILITY_SYNC_INBOUND:
            return False
        return True

    with patch(
        "apps.intercompany_pools.master_data_sync_execution.supports_pool_master_data_capability",
        side_effect=_supports,
    ):
        result = trigger_pool_master_data_inbound_sync_job(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.ITEM,
            origin_system="ib",
            origin_event_id="evt-inbound-capability-off",
        )

    assert result.skipped is True
    assert result.skip_reason == MASTER_DATA_SYNC_INBOUND_CAPABILITY_DISABLED
    assert PoolMasterDataSyncJob.objects.filter(tenant=tenant).count() == 0


@pytest.mark.django_db
def test_trigger_reconcile_sync_creates_bidirectional_job_and_starts_workflow() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-reconcile-{uuid4().hex[:6]}", name="Sync Exec Reconcile")
    database = _create_database(tenant=tenant, suffix="reconcile")
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )
    _set_runtime(enabled=True, inbound_enabled=True, outbound_enabled=True)

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
        result = trigger_pool_master_data_reconcile_sync_job(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.ITEM,
            reconcile_window_id="window-001",
            reconcile_window_deadline_at="2026-03-03T12:02:00Z",
        )

    assert result.skipped is False
    assert result.created_job is True
    assert result.started_workflow is True
    assert result.sync_job is not None
    assert result.sync_job.direction == PoolMasterDataSyncDirection.BIDIRECTIONAL
    metadata = dict(result.sync_job.metadata or {})
    assert metadata["last_trigger"]["mode"] == "reconcile_probe"
    assert metadata["last_trigger"]["reconcile_window_id"] == "window-001"
    assert metadata["last_trigger"]["reconcile_window_deadline_at"] == "2026-03-03T12:02:00Z"


@pytest.mark.django_db
def test_trigger_reconcile_sync_skips_when_registry_disables_reconcile_capability() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-reconcile-cap-{uuid4().hex[:6]}", name="Sync Exec Reconcile Cap")
    database = _create_database(tenant=tenant, suffix="reconcile-cap")
    _set_runtime(enabled=True, inbound_enabled=True, outbound_enabled=True)

    def _supports(*, entity_type: str, capability: str, include_bootstrap_helpers: bool = False) -> bool:
        if capability == POOL_MASTER_DATA_CAPABILITY_SYNC_RECONCILE:
            return False
        return True

    with patch(
        "apps.intercompany_pools.master_data_sync_execution.supports_pool_master_data_capability",
        side_effect=_supports,
    ):
        result = trigger_pool_master_data_reconcile_sync_job(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.ITEM,
            reconcile_window_id="window-off",
            reconcile_window_deadline_at="2026-03-03T12:02:00Z",
        )

    assert result.skipped is True
    assert result.skip_reason == MASTER_DATA_SYNC_RECONCILE_CAPABILITY_DISABLED
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


@pytest.mark.django_db
def test_inbound_step_fails_closed_when_callbacks_are_not_configured() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-inbound-nocb-{uuid4().hex[:6]}", name="Sync Inbound No Callback")
    database = _create_database(tenant=tenant, suffix="inbound-nocb")
    _set_runtime(enabled=True, inbound_enabled=True, outbound_enabled=True, default_policy=PoolMasterDataSyncPolicy.IB_MASTER)
    sync_job = PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.IB_MASTER,
        direction=PoolMasterDataSyncDirection.INBOUND,
        status=PoolMasterDataSyncJobStatus.RUNNING,
    )
    reset_pool_master_data_sync_inbound_callbacks()

    with pytest.raises(MasterDataSyncConflictError) as exc_info:
        execute_pool_master_data_sync_inbound_step(
            input_context={
                "contract_version": "pool_master_data_sync_workflow.v1",
                "sync_job_id": str(sync_job.id),
                "tenant_id": str(tenant.id),
                "database_id": str(database.id),
                "entity_type": PoolMasterDataEntityType.ITEM,
                "sync_policy": PoolMasterDataSyncPolicy.IB_MASTER,
                "sync_direction": PoolMasterDataSyncDirection.INBOUND,
                "correlation_id": "corr-inbound-nocb-001",
                "origin_system": "ib",
                "origin_event_id": "evt-inbound-nocb-001",
            }
        )

    assert exc_info.value.code == MASTER_DATA_SYNC_CONFLICT_APPLY
    assert exc_info.value.diagnostics["error_code"] == MASTER_DATA_SYNC_INBOUND_CALLBACKS_NOT_CONFIGURED


@pytest.mark.django_db(transaction=True)
def test_inbound_step_processes_batch_via_workflow_runtime_path() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-inbound-step-{uuid4().hex[:6]}", name="Sync Inbound Step")
    database = _create_database(tenant=tenant, suffix="inbound-step")
    _set_runtime(enabled=True, inbound_enabled=True, outbound_enabled=True, default_policy=PoolMasterDataSyncPolicy.IB_MASTER)
    sync_job = PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.IB_MASTER,
        direction=PoolMasterDataSyncDirection.INBOUND,
        status=PoolMasterDataSyncJobStatus.RUNNING,
    )
    inbound_change = MasterDataSyncInboundChange(
        origin_system="ib",
        origin_event_id="evt-inbound-step-001",
        canonical_id="item-inbound-step-001",
        entity_type=PoolMasterDataEntityType.ITEM,
        payload={"name": "Inbound Item"},
        payload_fingerprint="fp-inbound-step-001",
    )
    apply_calls: list[str] = []
    notify_calls: list[dict[str, str]] = []

    def _select_changes(*, checkpoint_token: str, **kwargs):
        return MasterDataSyncSelectChangesResult(
            changes=[inbound_change],
            source_checkpoint_token=checkpoint_token,
            next_checkpoint_token="cp-inbound-step-001",
        )

    def _apply_change(*, change: MasterDataSyncInboundChange, **kwargs):
        apply_calls.append(change.origin_event_id)

    def _notify_changes_received(*, checkpoint_token: str, next_checkpoint_token: str, **kwargs):
        notify_calls.append(
            {
                "checkpoint_token": checkpoint_token,
                "next_checkpoint_token": next_checkpoint_token,
            }
        )

    configure_pool_master_data_sync_inbound_callbacks(
        select_changes=_select_changes,
        apply_change=_apply_change,
        notify_changes_received=_notify_changes_received,
    )
    try:
        output = execute_pool_master_data_sync_inbound_step(
            input_context={
                "contract_version": "pool_master_data_sync_workflow.v1",
                "sync_job_id": str(sync_job.id),
                "tenant_id": str(tenant.id),
                "database_id": str(database.id),
                "entity_type": PoolMasterDataEntityType.ITEM,
                "sync_policy": PoolMasterDataSyncPolicy.IB_MASTER,
                "sync_direction": PoolMasterDataSyncDirection.INBOUND,
                "correlation_id": "corr-inbound-step-001",
                "origin_system": "ib",
                "origin_event_id": "evt-inbound-step-001",
            }
        )
    finally:
        reset_pool_master_data_sync_inbound_callbacks()

    assert output["inbound"]["applied"] == 1
    assert output["inbound"]["duplicates"] == 0
    assert output["inbound"]["ack_scheduled"] is True
    assert apply_calls == ["evt-inbound-step-001"]
    assert notify_calls == [
        {
            "checkpoint_token": "",
            "next_checkpoint_token": "cp-inbound-step-001",
        }
    ]


@pytest.mark.django_db(transaction=True)
def test_inbound_step_does_not_ack_when_local_apply_raises() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-inbound-apply-{uuid4().hex[:6]}", name="Sync Inbound Apply Fail")
    database = _create_database(tenant=tenant, suffix="inbound-apply")
    _set_runtime(enabled=True, inbound_enabled=True, outbound_enabled=True, default_policy=PoolMasterDataSyncPolicy.IB_MASTER)
    sync_job = PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.IB_MASTER,
        direction=PoolMasterDataSyncDirection.INBOUND,
        status=PoolMasterDataSyncJobStatus.RUNNING,
    )
    inbound_change = MasterDataSyncInboundChange(
        origin_system="ib",
        origin_event_id="evt-inbound-apply-001",
        canonical_id="item-inbound-apply-001",
        entity_type=PoolMasterDataEntityType.ITEM,
        payload={"name": "Inbound Apply Fail"},
        payload_fingerprint="fp-inbound-apply-001",
    )
    notify_calls: list[str] = []

    def _select_changes(*, checkpoint_token: str, **kwargs):
        return MasterDataSyncSelectChangesResult(
            changes=[inbound_change],
            source_checkpoint_token=checkpoint_token,
            next_checkpoint_token="cp-inbound-apply-001",
        )

    def _apply_change(**kwargs):
        raise RuntimeError("apply failed in local transaction")

    def _notify_changes_received(**kwargs):
        notify_calls.append("called")

    configure_pool_master_data_sync_inbound_callbacks(
        select_changes=_select_changes,
        apply_change=_apply_change,
        notify_changes_received=_notify_changes_received,
    )
    try:
        with pytest.raises(MasterDataSyncConflictError) as exc_info:
            execute_pool_master_data_sync_inbound_step(
                input_context={
                    "contract_version": "pool_master_data_sync_workflow.v1",
                    "sync_job_id": str(sync_job.id),
                    "tenant_id": str(tenant.id),
                    "database_id": str(database.id),
                    "entity_type": PoolMasterDataEntityType.ITEM,
                    "sync_policy": PoolMasterDataSyncPolicy.IB_MASTER,
                    "sync_direction": PoolMasterDataSyncDirection.INBOUND,
                    "correlation_id": "corr-inbound-apply-001",
                    "origin_system": "ib",
                    "origin_event_id": "evt-inbound-apply-001",
                }
            )
    finally:
        reset_pool_master_data_sync_inbound_callbacks()

    assert exc_info.value.code == MASTER_DATA_SYNC_CONFLICT_APPLY
    assert notify_calls == []


@pytest.mark.django_db
def test_dispatch_step_skips_outbox_for_inbound_only_job() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-dispatch-inbound-{uuid4().hex[:6]}", name="Sync Dispatch Inbound")
    database = _create_database(tenant=tenant, suffix="dispatch-inbound")
    _set_runtime(enabled=True, inbound_enabled=True, outbound_enabled=True, default_policy=PoolMasterDataSyncPolicy.IB_MASTER)
    sync_job = PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.IB_MASTER,
        direction=PoolMasterDataSyncDirection.INBOUND,
        status=PoolMasterDataSyncJobStatus.RUNNING,
    )

    with patch("apps.intercompany_pools.master_data_sync_execution.dispatch_pending_master_data_sync_outbox") as dispatch_mock:
        output = execute_pool_master_data_sync_dispatch_step(
            input_context={
                "contract_version": "pool_master_data_sync_workflow.v1",
                "sync_job_id": str(sync_job.id),
                "tenant_id": str(tenant.id),
                "database_id": str(database.id),
                "entity_type": PoolMasterDataEntityType.ITEM,
                "sync_policy": PoolMasterDataSyncPolicy.IB_MASTER,
                "sync_direction": PoolMasterDataSyncDirection.INBOUND,
                "correlation_id": "corr-dispatch-inbound-001",
                "origin_system": "ib",
                "origin_event_id": "evt-dispatch-inbound-001",
            }
        )

    dispatch_mock.assert_not_called()
    assert output["dispatch"] == {"claimed": 0, "sent": 0, "failed": 0, "skipped": True}


@pytest.mark.django_db
def test_legacy_inbound_route_is_disabled_fail_closed_without_side_effects() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-legacy-{uuid4().hex[:6]}", name="Sync Legacy Disabled")
    database = _create_database(tenant=tenant, suffix="legacy")

    with pytest.raises(LegacyInboundRouteDisabledError) as exc_info:
        run_pool_master_data_sync_legacy_inbound_route(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.ITEM,
        )

    assert exc_info.value.code == "SYNC_LEGACY_INBOUND_ROUTE_DISABLED"
    assert PoolMasterDataSyncJob.objects.filter(tenant=tenant).count() == 0
