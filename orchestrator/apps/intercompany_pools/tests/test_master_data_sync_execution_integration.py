from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.databases.models import Database
from apps.intercompany_pools.master_data_sync_dispatcher import (
    MasterDataSyncTransportError,
    dispatch_pending_master_data_sync_outbox as real_dispatch_pending_master_data_sync_outbox,
)
from apps.intercompany_pools.master_data_sync_execution import (
    LegacyInboundRouteDisabledError,
    execute_pool_master_data_sync_dispatch_step,
    execute_pool_master_data_sync_finalize_step,
    run_pool_master_data_sync_legacy_inbound_route,
    trigger_pool_master_data_outbound_sync_job,
)
from apps.intercompany_pools.master_data_sync_outbox import (
    build_master_data_mutation_payload_fingerprint,
    enqueue_master_data_sync_outbox_intent,
)
from apps.intercompany_pools.models import (
    PoolMasterDataBinding,
    PoolMasterDataEntityType,
    PoolMasterDataSyncCheckpoint,
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncJobStatus,
    PoolMasterDataSyncOutbox,
    PoolMasterDataSyncOutboxStatus,
    PoolMasterDataSyncPolicy,
    PoolMasterDataSyncScope,
)
from apps.operations.services import EnqueueResult
from apps.runtime_settings.models import RuntimeSetting
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"sync-e2e-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


def _set_runtime_settings() -> None:
    RuntimeSetting.objects.create(key="pools.master_data.sync.enabled", value=True)
    RuntimeSetting.objects.create(key="pools.master_data.sync.inbound.enabled", value=True)
    RuntimeSetting.objects.create(key="pools.master_data.sync.outbound.enabled", value=True)
    RuntimeSetting.objects.create(key="pools.master_data.sync.default_policy", value="cc_master")
    RuntimeSetting.objects.create(key="pools.master_data.sync.dispatch_batch_size", value=100)
    RuntimeSetting.objects.create(key="pools.master_data.sync.max_retry_backoff_seconds", value=900)


def _build_input_context(*, sync_job: PoolMasterDataSyncJob) -> dict[str, str]:
    return {
        "contract_version": "pool_master_data_sync_workflow.v1",
        "sync_job_id": str(sync_job.id),
        "tenant_id": str(sync_job.tenant_id),
        "database_id": str(sync_job.database_id),
        "entity_type": str(sync_job.entity_type),
        "sync_policy": str(sync_job.policy),
        "sync_direction": str(sync_job.direction),
        "correlation_id": "corr-sync-e2e",
        "origin_system": "cc",
        "origin_event_id": "evt-sync-e2e",
    }


@pytest.mark.django_db
def test_outbound_sync_path_supports_retry_recovery_and_finalize() -> None:
    tenant = Tenant.objects.create(slug=f"sync-e2e-retry-{uuid4().hex[:6]}", name="Sync E2E Retry")
    database = _create_database(tenant=tenant, suffix="retry")
    _set_runtime_settings()
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )
    outbox_row = enqueue_master_data_sync_outbox_intent(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-retry-001",
        mutation_kind="item_upsert",
        payload={"canonical_id": "item-retry-001", "name": "Retry Item"},
        origin_system="cc",
        origin_event_id="evt-retry-001",
    )

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
        trigger_result = trigger_pool_master_data_outbound_sync_job(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.ITEM,
            canonical_id="item-retry-001",
            origin_system="cc",
            origin_event_id="evt-retry-001",
        )
    assert trigger_result.sync_job is not None
    sync_job = trigger_result.sync_job

    dispatch_attempt = {"count": 0}

    def _dispatch_with_retry(**kwargs):
        dispatch_attempt["count"] += 1

        def _transport_apply(_outbox):
            if dispatch_attempt["count"] == 1:
                raise MasterDataSyncTransportError(
                    code="IB_TRANSPORT_DOWN",
                    detail="temporary outage",
                )
            return {"status": "ok"}

        return real_dispatch_pending_master_data_sync_outbox(
            transport_apply=_transport_apply,
            **kwargs,
        )

    with patch(
        "apps.intercompany_pools.master_data_sync_execution.dispatch_pending_master_data_sync_outbox",
        side_effect=_dispatch_with_retry,
    ):
        first = execute_pool_master_data_sync_dispatch_step(input_context=_build_input_context(sync_job=sync_job))
        assert first["dispatch"]["failed"] == 1

        outbox_row.refresh_from_db()
        assert outbox_row.status == PoolMasterDataSyncOutboxStatus.FAILED
        assert outbox_row.last_error_code == "IB_TRANSPORT_DOWN"
        outbox_row.available_at = timezone.now() - timedelta(seconds=1)
        outbox_row.save(update_fields=["available_at", "updated_at"])

        second = execute_pool_master_data_sync_dispatch_step(input_context=_build_input_context(sync_job=sync_job))
        assert second["dispatch"]["sent"] == 1

    outbox_row.refresh_from_db()
    assert outbox_row.status == PoolMasterDataSyncOutboxStatus.SENT
    assert outbox_row.attempt_count == 2
    assert dispatch_attempt["count"] == 2

    finalize_output = execute_pool_master_data_sync_finalize_step(
        input_context=_build_input_context(sync_job=sync_job)
    )
    sync_job.refresh_from_db()
    assert finalize_output["status"] == PoolMasterDataSyncJobStatus.SUCCEEDED
    assert sync_job.status == PoolMasterDataSyncJobStatus.SUCCEEDED
    assert sync_job.attempt_count == 2


@pytest.mark.django_db
def test_outbound_sync_path_preserves_dedupe_without_duplicate_side_effects() -> None:
    tenant = Tenant.objects.create(slug=f"sync-e2e-dedupe-{uuid4().hex[:6]}", name="Sync E2E Dedupe")
    database = _create_database(tenant=tenant, suffix="dedupe")
    _set_runtime_settings()
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )
    payload = {"canonical_id": "item-dedupe-001", "ib_ref_key": "ref-item-dedupe-001"}
    payload_fingerprint = build_master_data_mutation_payload_fingerprint(payload=payload)
    binding = PoolMasterDataBinding.objects.create(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-dedupe-001",
        database=database,
        ib_ref_key="ref-item-dedupe-001",
        sync_status="resolved",
        fingerprint=payload_fingerprint,
        metadata={},
    )
    enqueue_master_data_sync_outbox_intent(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-dedupe-001",
        mutation_kind="binding_upsert",
        payload=payload,
        origin_system="cc",
        origin_event_id="evt-dedupe-001",
    )

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
        trigger_result = trigger_pool_master_data_outbound_sync_job(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.ITEM,
            canonical_id="item-dedupe-001",
            origin_system="cc",
            origin_event_id="evt-dedupe-001",
        )
    assert trigger_result.sync_job is not None

    ib_apply_calls = {"count": 0}

    def _dispatch_with_ib_apply(**kwargs):
        def _ib_apply(_outbox):
            ib_apply_calls["count"] += 1
            return {"status": "applied"}

        return real_dispatch_pending_master_data_sync_outbox(
            ib_apply=_ib_apply,
            **kwargs,
        )

    with patch(
        "apps.intercompany_pools.master_data_sync_execution.dispatch_pending_master_data_sync_outbox",
        side_effect=_dispatch_with_ib_apply,
    ):
        result = execute_pool_master_data_sync_dispatch_step(
            input_context=_build_input_context(sync_job=trigger_result.sync_job)
        )

    assert result["dispatch"]["sent"] == 1
    assert ib_apply_calls["count"] == 0

    outbox_row = PoolMasterDataSyncOutbox.objects.get(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
    )
    assert outbox_row.status == PoolMasterDataSyncOutboxStatus.SENT
    binding.refresh_from_db()
    assert binding.metadata["sync_audit"][-1]["event"] == "idempotent_skip"


@pytest.mark.django_db
def test_legacy_inbound_route_is_fail_closed_with_machine_readable_code_and_no_side_effects() -> None:
    tenant = Tenant.objects.create(slug=f"sync-e2e-legacy-{uuid4().hex[:6]}", name="Sync E2E Legacy Disabled")
    database = _create_database(tenant=tenant, suffix="legacy-disabled")

    with pytest.raises(LegacyInboundRouteDisabledError) as exc_info:
        run_pool_master_data_sync_legacy_inbound_route(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.ITEM,
        )

    assert exc_info.value.code == "SYNC_LEGACY_INBOUND_ROUTE_DISABLED"
    assert "Use workflow runtime trigger" in exc_info.value.detail
    assert PoolMasterDataSyncJob.objects.filter(tenant=tenant, database=database).count() == 0
    assert PoolMasterDataSyncOutbox.objects.filter(tenant=tenant, database=database).count() == 0
    assert PoolMasterDataSyncCheckpoint.objects.filter(tenant=tenant, database=database).count() == 0
    assert PoolMasterDataSyncConflict.objects.filter(tenant=tenant, database=database).count() == 0
