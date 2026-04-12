from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from apps.databases.models import Database, InfobaseUserMapping
from apps.intercompany_pools.master_data_dedupe import ingest_pool_master_data_source_record
from apps.intercompany_pools.master_data_sync_conflicts import (
    MASTER_DATA_SYNC_CONFLICT_DEDUPE_REVIEW_REQUIRED,
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
    MASTER_DATA_SYNC_INBOUND_CAPABILITY_DISABLED,
    MASTER_DATA_SYNC_INBOUND_DISABLED,
    MASTER_DATA_SYNC_OUTBOUND_CAPABILITY_DISABLED,
    MASTER_DATA_SYNC_DEDUPE_REVIEW_REQUIRED,
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
    PoolMasterContract,
    PoolMasterItem,
    PoolMasterParty,
    PoolMasterTaxProfile,
    PoolMasterDataSourceRecord,
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


def _create_service_mapping(*, database: Database, username: str = "svc-user", password: str = "svc-pass") -> None:
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username=username,
        ib_password=password,
        is_service=True,
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


def _create_pending_item_dedupe(*, tenant: Tenant, database_a: Database, database_b: Database) -> str:
    first = ingest_pool_master_data_source_record(
        tenant_id=str(tenant.id),
        entity_type=PoolMasterDataEntityType.ITEM,
        source_database=database_a,
        source_ref="item-a",
        source_canonical_id="item-a",
        canonical_payload={
            "name": "Item Base",
            "sku": "SKU-001",
            "unit": "pcs",
            "metadata": {},
        },
        origin_kind="bootstrap_import",
        origin_ref="job-a",
        origin_event_id="evt-item-a",
    )
    blocked = ingest_pool_master_data_source_record(
        tenant_id=str(tenant.id),
        entity_type=PoolMasterDataEntityType.ITEM,
        source_database=database_b,
        source_ref="item-b",
        source_canonical_id="item-b",
        canonical_payload={
            "name": "Item Conflicted",
            "sku": "SKU-001",
            "unit": "pcs",
            "metadata": {},
        },
        origin_kind="bootstrap_import",
        origin_ref="job-b",
        origin_event_id="evt-item-b",
    )
    assert blocked.blocked is True
    return str(first.canonical_id)


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
def test_trigger_outbound_sync_coalesces_only_existing_outbound_job() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-coalesce-out-{uuid4().hex[:6]}", name="Sync Exec Coalesce Out")
    database = _create_database(tenant=tenant, suffix="coalesce-out")
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )
    _set_runtime(enabled=True, outbound_enabled=True, inbound_enabled=True)
    existing_job = PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
        direction=PoolMasterDataSyncDirection.OUTBOUND,
        status=PoolMasterDataSyncJobStatus.RUNNING,
        workflow_execution_id=uuid4(),
        operation_id=uuid4(),
        metadata={"trigger_count": 1, "policy_source": "database_scope"},
    )

    result = trigger_pool_master_data_outbound_sync_job(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-coalesce-out",
        origin_system="cc",
        origin_event_id="evt-coalesce-out",
    )

    assert result.created_job is False
    assert result.started_workflow is True
    assert result.sync_job is not None
    assert result.sync_job.id == existing_job.id
    existing_job.refresh_from_db()
    assert existing_job.direction == PoolMasterDataSyncDirection.OUTBOUND
    assert existing_job.policy == PoolMasterDataSyncPolicy.BIDIRECTIONAL
    assert existing_job.metadata["trigger_count"] == 2
    assert existing_job.metadata["last_requested_policy"] == PoolMasterDataSyncPolicy.BIDIRECTIONAL


@pytest.mark.django_db
def test_trigger_outbound_sync_does_not_reuse_active_inbound_job() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-cross-dir-{uuid4().hex[:6]}", name="Sync Exec Cross Dir")
    database = _create_database(tenant=tenant, suffix="cross-dir")
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )
    _set_runtime(enabled=True, outbound_enabled=True, inbound_enabled=True)
    existing_job = PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
        direction=PoolMasterDataSyncDirection.INBOUND,
        status=PoolMasterDataSyncJobStatus.RUNNING,
        workflow_execution_id=uuid4(),
        operation_id=uuid4(),
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
            entity_type=PoolMasterDataEntityType.ITEM,
            canonical_id="item-cross-dir",
            origin_system="cc",
            origin_event_id="evt-cross-dir",
        )

    assert result.created_job is True
    assert result.sync_job is not None
    assert result.sync_job.id != existing_job.id
    assert result.sync_job.direction == PoolMasterDataSyncDirection.OUTBOUND
    existing_job.refresh_from_db()
    assert existing_job.direction == PoolMasterDataSyncDirection.INBOUND
    assert PoolMasterDataSyncJob.objects.filter(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
    ).count() == 2


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
def test_trigger_outbound_sync_skips_when_dedupe_review_is_pending() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-dedupe-{uuid4().hex[:6]}", name="Sync Exec Dedupe")
    database_a = _create_database(tenant=tenant, suffix="dedupe-a")
    database_b = _create_database(tenant=tenant, suffix="dedupe-b")
    _set_runtime(enabled=True, outbound_enabled=True)
    canonical_id = _create_pending_item_dedupe(tenant=tenant, database_a=database_a, database_b=database_b)

    result = trigger_pool_master_data_outbound_sync_job(
        tenant_id=str(tenant.id),
        database_id=str(database_a.id),
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id=canonical_id,
        origin_system="cc",
        origin_event_id="evt-dedupe-blocked",
    )

    assert result.skipped is True
    assert result.skip_reason == MASTER_DATA_SYNC_DEDUPE_REVIEW_REQUIRED
    assert PoolMasterDataSyncJob.objects.filter(tenant=tenant).count() == 0
    conflict = PoolMasterDataSyncConflict.objects.get(
        tenant=tenant,
        database=database_a,
        entity_type=PoolMasterDataEntityType.ITEM,
    )
    assert conflict.conflict_code == MASTER_DATA_SYNC_CONFLICT_DEDUPE_REVIEW_REQUIRED


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
def test_trigger_reconcile_sync_does_not_reuse_active_outbound_job() -> None:
    tenant = Tenant.objects.create(
        slug=f"sync-exec-reconcile-cross-{uuid4().hex[:6]}",
        name="Sync Exec Reconcile Cross",
    )
    database = _create_database(tenant=tenant, suffix="reconcile-cross")
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )
    _set_runtime(enabled=True, inbound_enabled=True, outbound_enabled=True)
    existing_job = PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
        direction=PoolMasterDataSyncDirection.OUTBOUND,
        status=PoolMasterDataSyncJobStatus.RUNNING,
        workflow_execution_id=uuid4(),
        operation_id=uuid4(),
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
        result = trigger_pool_master_data_reconcile_sync_job(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.ITEM,
            reconcile_window_id="window-cross",
            reconcile_window_deadline_at="2026-03-03T12:02:00Z",
        )

    assert result.created_job is True
    assert result.sync_job is not None
    assert result.sync_job.id != existing_job.id
    assert result.sync_job.direction == PoolMasterDataSyncDirection.BIDIRECTIONAL
    existing_job.refresh_from_db()
    assert existing_job.direction == PoolMasterDataSyncDirection.OUTBOUND


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


@pytest.mark.django_db(transaction=True)
def test_inbound_step_uses_live_odata_transport_baseline_then_delta_when_callbacks_are_missing() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-inbound-live-{uuid4().hex[:6]}", name="Sync Inbound Live OData")
    database = _create_database(tenant=tenant, suffix="inbound-nocb")
    _create_service_mapping(database=database)
    _set_runtime(enabled=True, inbound_enabled=True, outbound_enabled=True, default_policy=PoolMasterDataSyncPolicy.IB_MASTER)
    reset_pool_master_data_sync_inbound_callbacks()

    live_rows = [
        {
            "Ref_Key": "item-existing-001",
            "DataVersion": "AAAAAAAAAAE=",
            "Code": "00-000001",
            "Description": "Existing Item",
            "Артикул": "SKU-EXISTING-001",
            "ВидНоменклатуры_Key": "kind-001",
            "ЕдиницаИзмерения_Key": "unit-001",
            "НаименованиеПолное": "Existing Item Full",
            "Комментарий": "",
            "Услуга": False,
            "DeletionMark": False,
            "IsFolder": False,
        }
    ]
    client_inits: list[dict[str, object]] = []

    class _FakeODataClient:
        def __init__(self, **kwargs):
            client_inits.append(dict(kwargs))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_entities(self, entity_name, filter_query=None, select_fields=None, top=None, skip=None):
            _ = (filter_query, select_fields)
            assert entity_name == "Catalog_Номенклатура"
            start = int(skip or 0)
            size = int(top or len(live_rows))
            return [dict(row) for row in live_rows[start : start + size]]

    with patch(
        "apps.intercompany_pools.master_data_sync_live_odata_transport.ODataClient",
        _FakeODataClient,
    ):
        baseline_job = PoolMasterDataSyncJob.objects.create(
            tenant=tenant,
            database=database,
            entity_type=PoolMasterDataEntityType.ITEM,
            policy=PoolMasterDataSyncPolicy.IB_MASTER,
            direction=PoolMasterDataSyncDirection.INBOUND,
            status=PoolMasterDataSyncJobStatus.RUNNING,
        )
        baseline_output = execute_pool_master_data_sync_inbound_step(
            input_context={
                "contract_version": "pool_master_data_sync_workflow.v1",
                "sync_job_id": str(baseline_job.id),
                "tenant_id": str(tenant.id),
                "database_id": str(database.id),
                "entity_type": PoolMasterDataEntityType.ITEM,
                "sync_policy": PoolMasterDataSyncPolicy.IB_MASTER,
                "sync_direction": PoolMasterDataSyncDirection.INBOUND,
                "correlation_id": "corr-inbound-live-baseline-001",
                "origin_system": "ib",
                "origin_event_id": "evt-inbound-live-baseline-001",
            }
        )
        assert baseline_output["inbound"] == {
            "polled": 0,
            "applied": 0,
            "duplicates": 0,
            "ack_scheduled": True,
            "next_checkpoint_token": baseline_output["inbound"]["next_checkpoint_token"],
        }

        live_rows.append(
            {
                "Ref_Key": "item-new-001",
                "DataVersion": "AAAAAAAAAAI=",
                "Code": "00-000002",
                "Description": "New Live Item",
                "Артикул": "SKU-LIVE-001",
                "ВидНоменклатуры_Key": "kind-001",
                "ЕдиницаИзмерения_Key": "unit-001",
                "НаименованиеПолное": "New Live Item Full",
                "Комментарий": "live delta",
                "Услуга": False,
                "DeletionMark": False,
                "IsFolder": False,
            }
        )
        delta_job = PoolMasterDataSyncJob.objects.create(
            tenant=tenant,
            database=database,
            entity_type=PoolMasterDataEntityType.ITEM,
            policy=PoolMasterDataSyncPolicy.IB_MASTER,
            direction=PoolMasterDataSyncDirection.INBOUND,
            status=PoolMasterDataSyncJobStatus.RUNNING,
        )
        delta_output = execute_pool_master_data_sync_inbound_step(
            input_context={
                "contract_version": "pool_master_data_sync_workflow.v1",
                "sync_job_id": str(delta_job.id),
                "tenant_id": str(tenant.id),
                "database_id": str(database.id),
                "entity_type": PoolMasterDataEntityType.ITEM,
                "sync_policy": PoolMasterDataSyncPolicy.IB_MASTER,
                "sync_direction": PoolMasterDataSyncDirection.INBOUND,
                "correlation_id": "corr-inbound-live-delta-001",
                "origin_system": "ib",
                "origin_event_id": "evt-inbound-live-delta-001",
            }
        )

    assert delta_output["inbound"]["polled"] == 1
    assert delta_output["inbound"]["applied"] == 1
    imported_item = PoolMasterItem.objects.get(tenant=tenant, canonical_id="item:item-new-001")
    assert imported_item.name == "New Live Item"
    assert imported_item.sku == "SKU-LIVE-001"
    assert imported_item.metadata["ib_ref_keys"][str(database.id)] == "item-new-001"
    assert imported_item.metadata["item_kind_ref"] == "kind-001"

    checkpoint = PoolMasterDataSourceRecord.objects.filter(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.ITEM,
        source_database=database,
        source_ref="item-new-001",
    ).first()
    assert checkpoint is not None
    assert client_inits
    assert client_inits[0]["verify_tls"] is True


@pytest.mark.django_db(transaction=True)
def test_inbound_step_uses_live_odata_transport_for_party_contract_and_tax_profile() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-inbound-live-md-{uuid4().hex[:6]}", name="Sync Inbound Live MD")
    database = _create_database(tenant=tenant, suffix="inbound-live-md")
    _create_service_mapping(database=database)
    _set_runtime(enabled=True, inbound_enabled=True, outbound_enabled=True, default_policy=PoolMasterDataSyncPolicy.IB_MASTER)
    reset_pool_master_data_sync_inbound_callbacks()

    live_counterparties: list[dict[str, object]] = []
    live_contracts: list[dict[str, object]] = []
    client_inits: list[dict[str, object]] = []

    class _FakeODataClient:
        def __init__(self, **kwargs):
            client_inits.append(dict(kwargs))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_entities(self, entity_name, filter_query=None, select_fields=None, top=None, skip=None):
            _ = (filter_query, select_fields)
            if entity_name == "Catalog_Контрагенты":
                rows = live_counterparties
            elif entity_name == "Catalog_ДоговорыКонтрагентов":
                rows = live_contracts
            else:
                raise AssertionError(f"unexpected entity lookup {entity_name}")
            start = int(skip or 0)
            size = int(top or len(rows) or 1)
            return [dict(row) for row in rows[start : start + size]]

    def _run_inbound(entity_type: str, suffix: str) -> dict[str, object]:
        sync_job = PoolMasterDataSyncJob.objects.create(
            tenant=tenant,
            database=database,
            entity_type=entity_type,
            policy=PoolMasterDataSyncPolicy.IB_MASTER,
            direction=PoolMasterDataSyncDirection.INBOUND,
            status=PoolMasterDataSyncJobStatus.RUNNING,
        )
        return execute_pool_master_data_sync_inbound_step(
            input_context={
                "contract_version": "pool_master_data_sync_workflow.v1",
                "sync_job_id": str(sync_job.id),
                "tenant_id": str(tenant.id),
                "database_id": str(database.id),
                "entity_type": entity_type,
                "sync_policy": PoolMasterDataSyncPolicy.IB_MASTER,
                "sync_direction": PoolMasterDataSyncDirection.INBOUND,
                "correlation_id": f"corr-{entity_type}-{suffix}",
                "origin_system": "ib",
                "origin_event_id": f"evt-{entity_type}-{suffix}",
            }
        )

    with patch(
        "apps.intercompany_pools.master_data_sync_live_odata_transport.ODataClient",
        _FakeODataClient,
    ):
        for entity_type in (
            PoolMasterDataEntityType.PARTY,
            PoolMasterDataEntityType.TAX_PROFILE,
            PoolMasterDataEntityType.CONTRACT,
        ):
            baseline_output = _run_inbound(entity_type, "baseline")
            assert baseline_output["inbound"]["polled"] == 0
            assert baseline_output["inbound"]["applied"] == 0

        live_counterparties.append(
            {
                "Ref_Key": "party-new-001",
                "DataVersion": "AAAAAAAB",
                "Code": "00001",
                "Description": "New Live Party",
                "НаименованиеПолное": "New Live Party LLC",
                "ИНН": "7701234567",
                "КПП": "770101001",
                "DeletionMark": False,
                "IsFolder": False,
            }
        )
        party_output = _run_inbound(PoolMasterDataEntityType.PARTY, "delta")
        assert party_output["inbound"]["polled"] == 1
        assert party_output["inbound"]["applied"] == 1

        live_contracts.append(
            {
                "Ref_Key": "contract-new-001",
                "DataVersion": "AAAAAAAC",
                "Description": "New Live Contract",
                "Owner_Key": "party-new-001",
                "Номер": "CTR-001",
                "Дата": "2026-04-13T00:00:00",
                "ВидДоговора": "СПокупателем",
                "СтавкаНДС": "НДС20",
                "СуммаВключаетНДС": True,
                "DeletionMark": False,
                "IsFolder": False,
            }
        )
        tax_output = _run_inbound(PoolMasterDataEntityType.TAX_PROFILE, "delta")
        contract_output = _run_inbound(PoolMasterDataEntityType.CONTRACT, "delta")

    assert tax_output["inbound"]["polled"] == 1
    assert tax_output["inbound"]["applied"] == 1
    assert contract_output["inbound"]["polled"] == 1
    assert contract_output["inbound"]["applied"] == 1

    party = PoolMasterParty.objects.get(tenant=tenant, canonical_id="party:party-new-001")
    assert party.name == "New Live Party"
    assert party.metadata["ib_ref_keys"][str(database.id)]["counterparty"] == "party-new-001"

    tax_profile = PoolMasterTaxProfile.objects.get(tenant=tenant, canonical_id="vat20")
    assert str(tax_profile.vat_rate) == "20.00"
    assert tax_profile.vat_code == "VAT20"
    assert tax_profile.metadata["ib_ref_keys"][str(database.id)] == "НДС20"

    contract = PoolMasterContract.objects.get(tenant=tenant, canonical_id="contract:contract-new-001")
    assert contract.name == "New Live Contract"
    assert contract.owner_counterparty_id == party.id
    assert contract.metadata["ib_ref_keys"][str(database.id)]["party:party-new-001"] == "contract-new-001"
    assert contract.metadata["vat_profile_canonical_id"] == "vat20"
    assert contract.metadata["vat_native_ref"] == "НДС20"

    assert PoolMasterDataSourceRecord.objects.filter(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.PARTY,
        source_database=database,
        source_ref="party-new-001",
    ).exists()
    assert PoolMasterDataSourceRecord.objects.filter(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.CONTRACT,
        source_database=database,
        source_ref="contract-new-001",
    ).exists()
    assert PoolMasterDataSourceRecord.objects.filter(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.TAX_PROFILE,
        source_database=database,
        source_ref="НДС20",
    ).exists()
    assert client_inits
    assert client_inits[0]["verify_tls"] is True


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
def test_inbound_step_uses_default_source_record_ingestion_when_apply_callback_is_not_overridden() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-inbound-default-{uuid4().hex[:6]}", name="Sync Inbound Default")
    database = _create_database(tenant=tenant, suffix="inbound-default")
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
        origin_event_id="evt-inbound-default-001",
        canonical_id="item-inbound-default-001",
        entity_type=PoolMasterDataEntityType.ITEM,
        payload={
            "name": "Inbound Item",
            "sku": "SKU-IN-001",
            "unit": "pcs",
            "source_ref": "Ref_Item_Inbound",
        },
        payload_fingerprint="fp-inbound-default-001",
    )
    notify_calls: list[dict[str, str]] = []

    def _select_changes(*, checkpoint_token: str, **kwargs):
        return MasterDataSyncSelectChangesResult(
            changes=[inbound_change],
            source_checkpoint_token=checkpoint_token,
            next_checkpoint_token="cp-inbound-default-001",
        )

    def _notify_changes_received(*, checkpoint_token: str, next_checkpoint_token: str, **kwargs):
        notify_calls.append(
            {
                "checkpoint_token": checkpoint_token,
                "next_checkpoint_token": next_checkpoint_token,
            }
        )

    configure_pool_master_data_sync_inbound_callbacks(
        select_changes=_select_changes,
        apply_change=None,
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
                "correlation_id": "corr-inbound-default-001",
                "origin_system": "ib",
                "origin_event_id": "evt-inbound-default-001",
            }
        )
    finally:
        reset_pool_master_data_sync_inbound_callbacks()

    assert output["inbound"]["applied"] == 1
    source_record = PoolMasterDataSourceRecord.objects.get(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.ITEM,
        source_database=database,
        source_ref="Ref_Item_Inbound",
    )
    assert source_record.origin_kind == "sync_inbound"
    assert source_record.origin_ref == str(sync_job.id)
    assert source_record.metadata["payload_fingerprint"] == "fp-inbound-default-001"
    assert source_record.metadata["dedupe_fingerprint"]
    item = PoolMasterItem.objects.get(tenant=tenant, canonical_id="item-inbound-default-001")
    assert item.name == "Inbound Item"
    assert item.sku == "SKU-IN-001"
    assert notify_calls == [
        {
            "checkpoint_token": "",
            "next_checkpoint_token": "cp-inbound-default-001",
        }
    ]


@pytest.mark.django_db(transaction=True)
def test_inbound_step_fail_closed_when_default_ingestion_requires_dedupe_review() -> None:
    tenant = Tenant.objects.create(slug=f"sync-exec-inbound-review-{uuid4().hex[:6]}", name="Sync Inbound Review")
    database_a = _create_database(tenant=tenant, suffix="inbound-review-a")
    database_b = _create_database(tenant=tenant, suffix="inbound-review-b")
    _set_runtime(enabled=True, inbound_enabled=True, outbound_enabled=True, default_policy=PoolMasterDataSyncPolicy.IB_MASTER)
    sync_job = PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=database_b,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.IB_MASTER,
        direction=PoolMasterDataSyncDirection.INBOUND,
        status=PoolMasterDataSyncJobStatus.RUNNING,
    )
    ingest_pool_master_data_source_record(
        tenant_id=str(tenant.id),
        entity_type=PoolMasterDataEntityType.ITEM,
        source_database=database_a,
        source_ref="item-a",
        source_canonical_id="item-a",
        canonical_payload={
            "name": "Item Base",
            "sku": "SKU-001",
            "unit": "pcs",
            "metadata": {},
        },
        origin_kind="bootstrap_import",
        origin_ref="job-a",
        origin_event_id="evt-item-a",
    )
    inbound_change = MasterDataSyncInboundChange(
        origin_system="ib",
        origin_event_id="evt-inbound-review-001",
        canonical_id="item-b",
        entity_type=PoolMasterDataEntityType.ITEM,
        payload={
            "name": "Item Conflicted",
            "sku": "SKU-001",
            "unit": "pcs",
            "source_ref": "item-b",
        },
        payload_fingerprint="fp-inbound-review-001",
    )
    notify_calls: list[str] = []

    def _select_changes(*, checkpoint_token: str, **kwargs):
        return MasterDataSyncSelectChangesResult(
            changes=[inbound_change],
            source_checkpoint_token=checkpoint_token,
            next_checkpoint_token="cp-inbound-review-001",
        )

    def _notify_changes_received(**kwargs):
        notify_calls.append("called")

    configure_pool_master_data_sync_inbound_callbacks(
        select_changes=_select_changes,
        apply_change=None,
        notify_changes_received=_notify_changes_received,
    )
    try:
        with pytest.raises(MasterDataSyncConflictError) as exc_info:
            execute_pool_master_data_sync_inbound_step(
                input_context={
                    "contract_version": "pool_master_data_sync_workflow.v1",
                    "sync_job_id": str(sync_job.id),
                    "tenant_id": str(tenant.id),
                    "database_id": str(database_b.id),
                    "entity_type": PoolMasterDataEntityType.ITEM,
                    "sync_policy": PoolMasterDataSyncPolicy.IB_MASTER,
                    "sync_direction": PoolMasterDataSyncDirection.INBOUND,
                    "correlation_id": "corr-inbound-review-001",
                    "origin_system": "ib",
                    "origin_event_id": "evt-inbound-review-001",
                }
            )
    finally:
        reset_pool_master_data_sync_inbound_callbacks()

    assert exc_info.value.code == MASTER_DATA_SYNC_CONFLICT_DEDUPE_REVIEW_REQUIRED
    assert notify_calls == []
    conflict = PoolMasterDataSyncConflict.objects.get(id=exc_info.value.conflict_id)
    assert conflict.conflict_code == MASTER_DATA_SYNC_CONFLICT_DEDUPE_REVIEW_REQUIRED
    assert conflict.diagnostics["dedupe_review_item_id"]


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
