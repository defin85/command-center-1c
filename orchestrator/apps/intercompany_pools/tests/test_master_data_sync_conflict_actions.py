from __future__ import annotations

from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model

from apps.databases.models import Database
from apps.intercompany_pools.master_data_sync_conflict_actions import (
    MASTER_DATA_SYNC_CONFLICT_ACTION_RECONCILE,
    MASTER_DATA_SYNC_CONFLICT_ACTION_RESOLVE,
    MASTER_DATA_SYNC_CONFLICT_ACTION_RETRY,
    reconcile_master_data_sync_conflict,
    resolve_master_data_sync_conflict,
    retry_master_data_sync_conflict,
)
from apps.intercompany_pools.master_data_sync_conflicts import (
    MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
    enqueue_master_data_sync_conflict,
)
from apps.intercompany_pools.models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncConflictStatus,
)
from apps.tenancy.models import Tenant


User = get_user_model()


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"sync-conflict-actions-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


def _create_conflict(*, tenant: Tenant, database: Database, entity_type: str) -> PoolMasterDataSyncConflict:
    return enqueue_master_data_sync_conflict(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=entity_type,
        conflict_code=MASTER_DATA_SYNC_CONFLICT_POLICY_VIOLATION,
        canonical_id=f"{entity_type}-001",
        origin_system="ib",
        origin_event_id=f"evt-{entity_type}-001",
    )


@pytest.mark.django_db
def test_retry_conflict_moves_status_to_retrying_and_writes_audit() -> None:
    tenant = Tenant.objects.create(slug=f"sync-conflict-retry-{uuid4().hex[:6]}", name="Sync Conflict Retry")
    database = _create_database(tenant=tenant, suffix="retry")
    actor = User.objects.create_user(username=f"sync-conflict-retry-{uuid4().hex[:6]}", password="pass")
    conflict = _create_conflict(tenant=tenant, database=database, entity_type=PoolMasterDataEntityType.ITEM)

    updated = retry_master_data_sync_conflict(
        conflict_id=str(conflict.id),
        tenant_id=str(tenant.id),
        actor_id=str(actor.id),
        note="retry requested by operator",
    )

    updated.refresh_from_db()
    assert updated.status == PoolMasterDataSyncConflictStatus.RETRYING
    assert updated.resolved_at is None
    assert updated.resolved_by_id is None
    assert updated.metadata["operator_actions"][-1]["action"] == MASTER_DATA_SYNC_CONFLICT_ACTION_RETRY
    assert updated.metadata["operator_actions"][-1]["actor_id"] == str(actor.id)


@pytest.mark.django_db
def test_reconcile_conflict_persists_reconcile_payload_and_audit() -> None:
    tenant = Tenant.objects.create(slug=f"sync-conflict-reconcile-{uuid4().hex[:6]}", name="Sync Conflict Reconcile")
    database = _create_database(tenant=tenant, suffix="reconcile")
    actor = User.objects.create_user(username=f"sync-conflict-reconcile-{uuid4().hex[:6]}", password="pass")
    conflict = _create_conflict(tenant=tenant, database=database, entity_type=PoolMasterDataEntityType.CONTRACT)

    updated = reconcile_master_data_sync_conflict(
        conflict_id=str(conflict.id),
        tenant_id=str(tenant.id),
        actor_id=str(actor.id),
        reconcile_payload={"strategy": "prefer_cc", "scope": "binding"},
        note="operator reconcile requested",
    )

    updated.refresh_from_db()
    assert updated.status == PoolMasterDataSyncConflictStatus.RETRYING
    assert updated.metadata["last_reconcile_payload"]["strategy"] == "prefer_cc"
    assert updated.metadata["operator_actions"][-1]["action"] == MASTER_DATA_SYNC_CONFLICT_ACTION_RECONCILE
    assert updated.metadata["operator_actions"][-1]["metadata"]["scope"] == "binding"


@pytest.mark.django_db
def test_resolve_conflict_sets_resolved_fields_and_audit() -> None:
    tenant = Tenant.objects.create(slug=f"sync-conflict-resolve-{uuid4().hex[:6]}", name="Sync Conflict Resolve")
    database = _create_database(tenant=tenant, suffix="resolve")
    actor = User.objects.create_user(username=f"sync-conflict-resolve-{uuid4().hex[:6]}", password="pass")
    conflict = _create_conflict(tenant=tenant, database=database, entity_type=PoolMasterDataEntityType.PARTY)

    updated = resolve_master_data_sync_conflict(
        conflict_id=str(conflict.id),
        tenant_id=str(tenant.id),
        actor_id=str(actor.id),
        resolution_code="MANUAL_RECONCILE",
        note="operator resolved manually",
        metadata={"source": "ui"},
    )

    updated.refresh_from_db()
    assert updated.status == PoolMasterDataSyncConflictStatus.RESOLVED
    assert updated.resolved_at is not None
    assert updated.resolved_by_id == actor.id
    assert updated.metadata["operator_actions"][-1]["action"] == MASTER_DATA_SYNC_CONFLICT_ACTION_RESOLVE
    assert updated.metadata["operator_actions"][-1]["metadata"]["resolution_code"] == "MANUAL_RECONCILE"
    assert updated.metadata["operator_actions"][-1]["metadata"]["source"] == "ui"


@pytest.mark.django_db
def test_operator_actions_reject_modification_of_resolved_conflict() -> None:
    tenant = Tenant.objects.create(slug=f"sync-conflict-closed-{uuid4().hex[:6]}", name="Sync Conflict Closed")
    database = _create_database(tenant=tenant, suffix="closed")
    actor = User.objects.create_user(username=f"sync-conflict-closed-{uuid4().hex[:6]}", password="pass")
    conflict = _create_conflict(tenant=tenant, database=database, entity_type=PoolMasterDataEntityType.TAX_PROFILE)
    conflict.status = PoolMasterDataSyncConflictStatus.RESOLVED
    conflict.save(update_fields=["status", "updated_at"])

    with pytest.raises(ValueError, match="Cannot retry resolved"):
        retry_master_data_sync_conflict(
            conflict_id=str(conflict.id),
            tenant_id=str(tenant.id),
            actor_id=str(actor.id),
        )
    with pytest.raises(ValueError, match="Cannot reconcile resolved"):
        reconcile_master_data_sync_conflict(
            conflict_id=str(conflict.id),
            tenant_id=str(tenant.id),
            actor_id=str(actor.id),
            reconcile_payload={"strategy": "prefer_ib"},
        )
    with pytest.raises(ValueError, match="already resolved"):
        resolve_master_data_sync_conflict(
            conflict_id=str(conflict.id),
            tenant_id=str(tenant.id),
            actor_id=str(actor.id),
            resolution_code="MANUAL",
        )


@pytest.mark.django_db
def test_operator_actions_are_scoped_by_tenant() -> None:
    tenant = Tenant.objects.create(slug=f"sync-conflict-tenant-a-{uuid4().hex[:6]}", name="Sync Conflict Tenant A")
    other_tenant = Tenant.objects.create(slug=f"sync-conflict-tenant-b-{uuid4().hex[:6]}", name="Sync Conflict Tenant B")
    database = _create_database(tenant=tenant, suffix="tenant-a")
    actor = User.objects.create_user(username=f"sync-conflict-tenant-{uuid4().hex[:6]}", password="pass")
    conflict = _create_conflict(tenant=tenant, database=database, entity_type=PoolMasterDataEntityType.ITEM)

    with pytest.raises(PoolMasterDataSyncConflict.DoesNotExist):
        retry_master_data_sync_conflict(
            conflict_id=str(conflict.id),
            tenant_id=str(other_tenant.id),
            actor_id=str(actor.id),
        )

    conflict.refresh_from_db()
    assert conflict.status == PoolMasterDataSyncConflictStatus.PENDING
