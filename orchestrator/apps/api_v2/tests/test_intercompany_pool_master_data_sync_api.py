from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from apps.databases.models import Database
from apps.intercompany_pools.models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncCheckpoint,
    PoolMasterDataSyncCheckpointStatus,
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncConflictStatus,
    PoolMasterDataSyncOutbox,
    PoolMasterDataSyncOutboxStatus,
)
from apps.tenancy.models import Tenant, TenantMember


@pytest.fixture
def default_tenant() -> Tenant:
    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    return tenant


@pytest.fixture
def user(default_tenant: Tenant) -> User:
    user = User.objects.create_user(username=f"pool-mdm-sync-user-{uuid4().hex[:8]}", password="pass")
    membership, _ = TenantMember.objects.get_or_create(
        tenant=default_tenant,
        user=user,
        defaults={"role": TenantMember.ROLE_ADMIN},
    )
    if membership.role != TenantMember.ROLE_ADMIN:
        membership.role = TenantMember.ROLE_ADMIN
        membership.save(update_fields=["role"])
    return user


@pytest.fixture
def authenticated_client(user: User, default_tenant: Tenant) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_CC1C_TENANT_ID=str(default_tenant.id))
    return client


@pytest.fixture(autouse=True)
def _mock_conflict_action_sync_trigger():
    with patch(
        "apps.intercompany_pools.master_data_sync_conflict_actions.trigger_pool_master_data_outbound_sync_job",
        return_value=SimpleNamespace(
            started_workflow=True,
            skipped=False,
            skip_reason=None,
            sync_job=None,
            start_result=None,
        ),
    ):
        yield


def _create_database(*, tenant: Tenant, name: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=name,
        host="localhost",
        odata_url="http://localhost/odata/sync-status.odata",
        username="user",
        password="pass",
    )


@pytest.mark.django_db
def test_master_data_sync_status_aggregates_checkpoint_outbox_and_conflicts(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"sync-status-db-{uuid4().hex[:8]}")
    now = timezone.now()
    PoolMasterDataSyncCheckpoint.objects.create(
        tenant=default_tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.PARTY,
        status=PoolMasterDataSyncCheckpointStatus.ACTIVE,
        checkpoint_token="cp-100",
        last_applied_at=now - timedelta(minutes=5),
        metadata={"pending_checkpoint_token": "cp-101"},
    )
    PoolMasterDataSyncOutbox.objects.create(
        tenant=default_tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.PARTY,
        status=PoolMasterDataSyncOutboxStatus.PENDING,
        dedupe_key=f"pending-{uuid4().hex}",
        payload={},
        available_at=now - timedelta(minutes=2),
    )
    PoolMasterDataSyncOutbox.objects.create(
        tenant=default_tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.PARTY,
        status=PoolMasterDataSyncOutboxStatus.FAILED,
        dedupe_key=f"failed-{uuid4().hex}",
        payload={},
        available_at=now - timedelta(minutes=3),
    )
    PoolMasterDataSyncConflict.objects.create(
        tenant=default_tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.PARTY,
        status=PoolMasterDataSyncConflictStatus.PENDING,
        conflict_code="POLICY_VIOLATION",
        canonical_id="party-001",
    )
    PoolMasterDataSyncConflict.objects.create(
        tenant=default_tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.PARTY,
        status=PoolMasterDataSyncConflictStatus.RETRYING,
        conflict_code="POLICY_VIOLATION",
        canonical_id="party-001",
    )

    response = authenticated_client.get(
        f"/api/v2/pools/master-data/sync-status/?database_id={database.id}&entity_type=party"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    status_row = payload["statuses"][0]
    assert status_row["database_id"] == str(database.id)
    assert status_row["entity_type"] == "party"
    assert status_row["checkpoint_token"] == "cp-100"
    assert status_row["pending_checkpoint_token"] == "cp-101"
    assert status_row["pending_count"] == 1
    assert status_row["retry_count"] == 1
    assert status_row["conflict_pending_count"] == 1
    assert status_row["conflict_retrying_count"] == 1
    assert status_row["lag_seconds"] >= 120


@pytest.mark.django_db
def test_master_data_sync_conflict_action_endpoints_retry_reconcile_resolve(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    user: User,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"sync-conflict-db-{uuid4().hex[:8]}")
    conflict = PoolMasterDataSyncConflict.objects.create(
        tenant=default_tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        status=PoolMasterDataSyncConflictStatus.PENDING,
        conflict_code="POLICY_VIOLATION",
        canonical_id="item-001",
        origin_system="ib",
        origin_event_id="evt-001",
    )

    retry_response = authenticated_client.post(
        f"/api/v2/pools/master-data/sync-conflicts/{conflict.id}/retry/",
        {"note": "retry now", "metadata": {"source": "test"}},
        format="json",
    )
    assert retry_response.status_code == 200
    conflict.refresh_from_db()
    assert conflict.status == PoolMasterDataSyncConflictStatus.RETRYING
    assert conflict.metadata["operator_actions"][-1]["action"] == "retry"
    assert conflict.metadata["operator_actions"][-1]["actor_id"] == str(user.id)

    reconcile_response = authenticated_client.post(
        f"/api/v2/pools/master-data/sync-conflicts/{conflict.id}/reconcile/",
        {"note": "reconcile", "reconcile_payload": {"strategy": "prefer_cc"}},
        format="json",
    )
    assert reconcile_response.status_code == 200
    conflict.refresh_from_db()
    assert conflict.status == PoolMasterDataSyncConflictStatus.RETRYING
    assert conflict.metadata["last_reconcile_payload"]["strategy"] == "prefer_cc"
    assert conflict.metadata["operator_actions"][-1]["action"] == "reconcile"

    resolve_response = authenticated_client.post(
        f"/api/v2/pools/master-data/sync-conflicts/{conflict.id}/resolve/",
        {"resolution_code": "MANUAL_RECONCILE", "note": "resolved", "metadata": {"source": "test"}},
        format="json",
    )
    assert resolve_response.status_code == 200
    conflict.refresh_from_db()
    assert conflict.status == PoolMasterDataSyncConflictStatus.RESOLVED
    assert conflict.resolved_by_id == user.id
    assert conflict.resolved_at is not None
    assert conflict.metadata["operator_actions"][-1]["action"] == "resolve"
    assert conflict.metadata["operator_actions"][-1]["metadata"]["resolution_code"] == "MANUAL_RECONCILE"


@pytest.mark.django_db
def test_master_data_sync_conflicts_list_supports_filters(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"sync-conflict-list-db-{uuid4().hex[:8]}")
    PoolMasterDataSyncConflict.objects.create(
        tenant=default_tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        status=PoolMasterDataSyncConflictStatus.PENDING,
        conflict_code="POLICY_VIOLATION",
        canonical_id="item-001",
    )
    PoolMasterDataSyncConflict.objects.create(
        tenant=default_tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        status=PoolMasterDataSyncConflictStatus.RESOLVED,
        conflict_code="POLICY_VIOLATION",
        canonical_id="item-002",
    )

    response = authenticated_client.get(
        f"/api/v2/pools/master-data/sync-conflicts/?database_id={database.id}&entity_type=item&status=pending&limit=50"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert len(payload["conflicts"]) == 1
    assert payload["conflicts"][0]["status"] == "pending"


@pytest.mark.django_db
def test_master_data_sync_conflict_action_returns_not_found(authenticated_client: APIClient) -> None:
    response = authenticated_client.post(
        f"/api/v2/pools/master-data/sync-conflicts/{uuid4()}/retry/",
        {"note": "retry"},
        format="json",
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["code"] == "SYNC_CONFLICT_NOT_FOUND"


@pytest.mark.django_db
def test_master_data_sync_conflict_actions_require_staff_or_tenant_admin(
    default_tenant: Tenant,
) -> None:
    member_user = User.objects.create_user(username=f"pool-mdm-sync-member-{uuid4().hex[:8]}", password="pass")
    TenantMember.objects.update_or_create(
        tenant=default_tenant,
        user=member_user,
        defaults={"role": TenantMember.ROLE_MEMBER},
    )
    member_client = APIClient()
    member_client.force_authenticate(user=member_user)
    member_client.credentials(HTTP_X_CC1C_TENANT_ID=str(default_tenant.id))

    database = _create_database(tenant=default_tenant, name=f"sync-conflict-rbac-db-{uuid4().hex[:8]}")
    conflict = PoolMasterDataSyncConflict.objects.create(
        tenant=default_tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        status=PoolMasterDataSyncConflictStatus.PENDING,
        conflict_code="POLICY_VIOLATION",
        canonical_id="item-rbac-001",
    )

    response = member_client.post(
        f"/api/v2/pools/master-data/sync-conflicts/{conflict.id}/retry/",
        {"note": "retry"},
        format="json",
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["code"] == "FORBIDDEN"

    conflict.refresh_from_db()
    assert conflict.status == PoolMasterDataSyncConflictStatus.PENDING


@pytest.mark.django_db
def test_master_data_sync_conflict_action_is_tenant_scoped(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    other_tenant = Tenant.objects.create(slug=f"sync-conflict-other-{uuid4().hex[:8]}", name="Sync Conflict Other")
    other_database = _create_database(tenant=other_tenant, name=f"sync-conflict-other-db-{uuid4().hex[:8]}")
    conflict = PoolMasterDataSyncConflict.objects.create(
        tenant=other_tenant,
        database=other_database,
        entity_type=PoolMasterDataEntityType.ITEM,
        status=PoolMasterDataSyncConflictStatus.PENDING,
        conflict_code="POLICY_VIOLATION",
        canonical_id="item-cross-tenant-001",
    )

    response = authenticated_client.post(
        f"/api/v2/pools/master-data/sync-conflicts/{conflict.id}/retry/",
        {"note": "retry"},
        format="json",
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["code"] == "SYNC_CONFLICT_NOT_FOUND"

    conflict.refresh_from_db()
    assert conflict.status == PoolMasterDataSyncConflictStatus.PENDING
