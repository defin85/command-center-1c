from __future__ import annotations

from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.master_data_sync_conflicts import (
    MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
    MasterDataSyncConflictError,
    enqueue_master_data_sync_conflict,
    raise_fail_closed_master_data_sync_conflict,
)
from apps.intercompany_pools.models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncConflictStatus,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"sync-conflict-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


@pytest.mark.django_db
def test_enqueue_conflict_creates_pending_queue_record() -> None:
    tenant = Tenant.objects.create(slug=f"sync-conflict-create-{uuid4().hex[:6]}", name="Sync Conflict Create")
    database = _create_database(tenant=tenant, suffix="create")

    conflict = enqueue_master_data_sync_conflict(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=PoolMasterDataEntityType.ITEM,
        conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
        canonical_id="item-001",
        origin_system="ib",
        origin_event_id="evt-001",
        diagnostics={"reason": "policy mismatch"},
        metadata={"scope": "inbound"},
    )

    assert conflict.status == PoolMasterDataSyncConflictStatus.PENDING
    assert conflict.conflict_code == MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION
    assert conflict.canonical_id == "item-001"
    assert conflict.origin_system == "ib"
    assert conflict.origin_event_id == "evt-001"
    assert conflict.metadata["repeat_count"] == 1
    assert "queue_key" in conflict.metadata


@pytest.mark.django_db
def test_enqueue_conflict_reuses_pending_record_and_increments_repeat_count() -> None:
    tenant = Tenant.objects.create(slug=f"sync-conflict-repeat-{uuid4().hex[:6]}", name="Sync Conflict Repeat")
    database = _create_database(tenant=tenant, suffix="repeat")

    first = enqueue_master_data_sync_conflict(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=PoolMasterDataEntityType.CONTRACT,
        conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
        canonical_id="contract-001",
        origin_system="ib",
        origin_event_id="evt-777",
    )
    second = enqueue_master_data_sync_conflict(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=PoolMasterDataEntityType.CONTRACT,
        conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
        canonical_id="contract-001",
        origin_system="ib",
        origin_event_id="evt-777",
        diagnostics={"reason": "still conflicting"},
    )

    assert first.id == second.id
    second.refresh_from_db()
    assert second.metadata["repeat_count"] == 2
    assert second.diagnostics["reason"] == "still conflicting"
    assert (
        PoolMasterDataSyncConflict.objects.filter(
            tenant=tenant,
            database=database,
            entity_type=PoolMasterDataEntityType.CONTRACT,
            conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_enqueue_conflict_rejects_unknown_code() -> None:
    tenant = Tenant.objects.create(slug=f"sync-conflict-unknown-{uuid4().hex[:6]}", name="Sync Conflict Unknown")
    database = _create_database(tenant=tenant, suffix="unknown")

    with pytest.raises(ValueError, match="Unsupported master-data sync conflict code"):
        enqueue_master_data_sync_conflict(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.PARTY,
            conflict_code="random_conflict",
        )


@pytest.mark.django_db
def test_raise_fail_closed_conflict_persists_queue_record_and_raises() -> None:
    tenant = Tenant.objects.create(slug=f"sync-conflict-raise-{uuid4().hex[:6]}", name="Sync Conflict Raise")
    database = _create_database(tenant=tenant, suffix="raise")

    with pytest.raises(MasterDataSyncConflictError) as exc_info:
        raise_fail_closed_master_data_sync_conflict(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.TAX_PROFILE,
            conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
            detail="bidirectional conflict requires operator reconcile",
            canonical_id="tax-001",
            origin_system="ib",
            origin_event_id="evt-tax-001",
            diagnostics={"hint": "manual reconcile"},
        )

    error = exc_info.value
    assert error.code == MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION
    assert "operator reconcile" in error.detail
    persisted = PoolMasterDataSyncConflict.objects.get(id=error.conflict_id)
    assert persisted.status == PoolMasterDataSyncConflictStatus.PENDING
    assert persisted.conflict_code == MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION
    assert persisted.diagnostics["hint"] == "manual reconcile"


@pytest.mark.django_db
def test_conflict_diagnostics_redact_sensitive_fields() -> None:
    tenant = Tenant.objects.create(slug=f"sync-conflict-redact-{uuid4().hex[:6]}", name="Sync Conflict Redact")
    database = _create_database(tenant=tenant, suffix="redact")

    conflict = enqueue_master_data_sync_conflict(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=PoolMasterDataEntityType.ITEM,
        conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
        diagnostics={
            "password": "top-secret",
            "context": "authorization=Bearer abc123 checkpoint_token=cp-001",
        },
        metadata={"api_key": "api-secret"},
    )

    assert conflict.diagnostics["password"] == "***"
    assert "authorization=***" in conflict.diagnostics["context"] or "authorization=Bearer ***" in conflict.diagnostics["context"]
    assert "checkpoint_token=cp-001" in conflict.diagnostics["context"]
    assert conflict.metadata["last_context"]["api_key"] == "***"
