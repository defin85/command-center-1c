from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from apps.databases.models import Cluster, Database
from apps.intercompany_pools.models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncDirection,
    PoolMasterDataSyncCheckpoint,
    PoolMasterDataSyncCheckpointStatus,
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncConflictStatus,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncJobStatus,
    PoolMasterDataSyncOutbox,
    PoolMasterDataSyncOutboxStatus,
    PoolMasterDataSyncPolicy,
)
from apps.operations.models import BatchOperation, WorkflowEnqueueOutbox
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
    trigger_result = SimpleNamespace(
        started_workflow=True,
        skipped=False,
        skip_reason=None,
        sync_job=None,
        start_result=None,
    )
    with patch(
        "apps.intercompany_pools.master_data_sync_conflict_actions.trigger_pool_master_data_outbound_sync_job",
        return_value=trigger_result,
    ), patch(
        "apps.intercompany_pools.master_data_sync_conflict_actions.trigger_pool_master_data_inbound_sync_job",
        return_value=trigger_result,
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


def _create_cluster(*, tenant: Tenant, name: str) -> Cluster:
    return Cluster.objects.create(
        tenant=tenant,
        name=name,
        ras_server=f"{name.lower().replace(' ', '-')}:1545",
        cluster_service_url=f"http://{name.lower().replace(' ', '-')}.local",
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
def test_master_data_sync_status_supports_scheduling_filters_and_queue_states(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"sync-status-filter-db-{uuid4().hex[:8]}")
    operation_id = uuid4()
    deadline_at = (timezone.now() + timedelta(minutes=10)).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    PoolMasterDataSyncJob.objects.create(
        tenant=default_tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
        direction=PoolMasterDataSyncDirection.BIDIRECTIONAL,
        status=PoolMasterDataSyncJobStatus.PENDING,
        operation_id=operation_id,
    )
    BatchOperation.objects.create(
        id=str(operation_id),
        name="Sync Workflow Root",
        operation_type="execute_workflow",
        target_entity="Workflow",
        status=BatchOperation.STATUS_PENDING,
        payload={},
        config={},
        total_tasks=0,
        created_by="test",
        metadata={
            "priority": "p1",
            "role": "reconcile",
            "server_affinity": "srv-a",
            "deadline_at": deadline_at,
        },
    )
    WorkflowEnqueueOutbox.objects.create(
        operation_id=str(operation_id),
        message_payload={
            "metadata": {
                "priority": "p1",
                "role": "reconcile",
                "server_affinity": "srv-a",
            }
        },
        status=WorkflowEnqueueOutbox.STATUS_PENDING,
        dispatch_attempts=2,
        next_retry_at=timezone.now() - timedelta(seconds=30),
    )

    response = authenticated_client.get(
        (
            "/api/v2/pools/master-data/sync-status/"
            f"?database_id={database.id}&entity_type=item&priority=p1&role=reconcile"
            "&server_affinity=srv-a&deadline_state=pending"
        )
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    status_row = payload["statuses"][0]
    assert status_row["priority"] == "p1"
    assert status_row["role"] == "reconcile"
    assert status_row["server_affinity"] == "srv-a"
    assert status_row["deadline_state"] == "pending"
    assert status_row["queue_states"]["retrying"] == 1
    assert status_row["queue_states"]["queued"] == 0
    assert status_row["queue_states"]["processing"] == 0
    assert status_row["queue_states"]["failed"] == 0
    assert status_row["queue_states"]["completed"] == 0

    mismatch_response = authenticated_client.get(
        f"/api/v2/pools/master-data/sync-status/?database_id={database.id}&entity_type=item&deadline_state=missed"
    )
    assert mismatch_response.status_code == 200
    assert mismatch_response.json()["count"] == 0


@pytest.mark.django_db
def test_master_data_sync_status_rejects_invalid_scheduling_filters(
    authenticated_client: APIClient,
) -> None:
    response = authenticated_client.get(
        "/api/v2/pools/master-data/sync-status/?priority=urgent&role=unknown"
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "VALIDATION_ERROR"
    assert "priority" in str(payload["errors"])
    assert "role" in str(payload["errors"])


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
def test_master_data_sync_launches_create_list_and_detail_preserve_snapshot(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    cluster = _create_cluster(tenant=default_tenant, name=f"Sync Launch Cluster {uuid4().hex[:6]}")
    database_a = _create_database(tenant=default_tenant, name=f"sync-launch-db-a-{uuid4().hex[:6]}")
    database_b = _create_database(tenant=default_tenant, name=f"sync-launch-db-b-{uuid4().hex[:6]}")
    database_a.cluster = cluster
    database_b.cluster = cluster
    database_a.save(update_fields=["cluster", "updated_at"])
    database_b.save(update_fields=["cluster", "updated_at"])

    with patch(
        "apps.intercompany_pools.master_data_sync_launch_workflow_runtime.start_pool_master_data_sync_launch_request_workflow",
        return_value=SimpleNamespace(enqueue_success=True),
    ):
        create_response = authenticated_client.post(
            "/api/v2/pools/master-data/sync-launches/",
            {
                "mode": "inbound",
                "target_mode": "cluster_all",
                "cluster_id": str(cluster.id),
                "entity_scope": ["item", "party"],
            },
            format="json",
        )

    assert create_response.status_code == 201
    launch_payload = create_response.json()["launch"]
    launch_id = launch_payload["id"]
    assert launch_payload["mode"] == "inbound"
    assert launch_payload["target_mode"] == "cluster_all"
    assert launch_payload["cluster_id"] == str(cluster.id)
    assert launch_payload["database_ids"] == [str(database_a.id), str(database_b.id)]
    assert launch_payload["entity_scope"] == ["item", "party"]
    assert launch_payload["status"] == "pending"

    database_c = _create_database(tenant=default_tenant, name=f"sync-launch-db-c-{uuid4().hex[:6]}")
    database_c.cluster = cluster
    database_c.save(update_fields=["cluster", "updated_at"])

    list_response = authenticated_client.get("/api/v2/pools/master-data/sync-launches/?limit=20&offset=0")
    assert list_response.status_code == 200
    assert list_response.json()["count"] >= 1
    listed = {item["id"]: item for item in list_response.json()["launches"]}
    assert launch_id in listed

    detail_response = authenticated_client.get(f"/api/v2/pools/master-data/sync-launches/{launch_id}/")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()["launch"]
    assert detail_payload["database_ids"] == [str(database_a.id), str(database_b.id)]
    assert str(database_c.id) not in detail_payload["database_ids"]
    assert detail_payload["aggregate_counters"]["total_items"] == 4
    assert len(detail_payload["items"]) == 4


@pytest.mark.django_db
def test_master_data_sync_target_refs_are_tenant_scoped_and_cluster_aware(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    cluster_a = _create_cluster(tenant=default_tenant, name=f"Sync Target Cluster A {uuid4().hex[:6]}")
    cluster_b = _create_cluster(tenant=default_tenant, name=f"Sync Target Cluster B {uuid4().hex[:6]}")
    database_a = _create_database(tenant=default_tenant, name=f"sync-target-db-a-{uuid4().hex[:6]}")
    database_b = _create_database(tenant=default_tenant, name=f"sync-target-db-b-{uuid4().hex[:6]}")
    database_a.cluster = cluster_a
    database_b.cluster = cluster_b
    database_a.save(update_fields=["cluster", "updated_at"])
    database_b.save(update_fields=["cluster", "updated_at"])

    other_tenant = Tenant.objects.create(slug=f"sync-target-other-{uuid4().hex[:8]}", name="Sync Target Other")
    other_cluster = _create_cluster(tenant=other_tenant, name=f"Sync Target Cluster Other {uuid4().hex[:6]}")
    other_database = _create_database(tenant=other_tenant, name=f"sync-target-db-other-{uuid4().hex[:6]}")
    other_database.cluster = other_cluster
    other_database.save(update_fields=["cluster", "updated_at"])

    clusters_response = authenticated_client.get("/api/v2/pools/master-data/sync-target-clusters/")
    assert clusters_response.status_code == 200
    cluster_ids = {row["id"] for row in clusters_response.json()["clusters"]}
    assert str(cluster_a.id) in cluster_ids
    assert str(cluster_b.id) in cluster_ids
    assert str(other_cluster.id) not in cluster_ids

    databases_response = authenticated_client.get(
        f"/api/v2/pools/master-data/sync-target-databases/?cluster_id={cluster_a.id}"
    )
    assert databases_response.status_code == 200
    database_ids = [row["id"] for row in databases_response.json()["databases"]]
    assert database_ids == [str(database_a.id)]
    assert str(database_b.id) not in database_ids
    assert str(other_database.id) not in database_ids


@pytest.mark.django_db
def test_master_data_sync_target_refs_allow_tenant_member_without_manage_rbac(
    default_tenant: Tenant,
) -> None:
    member_user = User.objects.create_user(username=f"pool-mdm-sync-target-{uuid4().hex[:8]}", password="pass")
    TenantMember.objects.update_or_create(
        tenant=default_tenant,
        user=member_user,
        defaults={"role": TenantMember.ROLE_MEMBER},
    )
    member_client = APIClient()
    member_client.force_authenticate(user=member_user)
    member_client.credentials(HTTP_X_CC1C_TENANT_ID=str(default_tenant.id))

    cluster = _create_cluster(tenant=default_tenant, name=f"Sync Target Member {uuid4().hex[:6]}")
    database = _create_database(tenant=default_tenant, name=f"sync-target-member-{uuid4().hex[:6]}")
    database.cluster = cluster
    database.save(update_fields=["cluster", "updated_at"])

    clusters_response = member_client.get("/api/v2/pools/master-data/sync-target-clusters/")
    databases_response = member_client.get(
        f"/api/v2/pools/master-data/sync-target-databases/?cluster_id={cluster.id}"
    )

    assert clusters_response.status_code == 200
    assert databases_response.status_code == 200
    assert any(row["id"] == str(cluster.id) for row in clusters_response.json()["clusters"])
    assert [row["id"] for row in databases_response.json()["databases"]] == [str(database.id)]


@pytest.mark.django_db
def test_master_data_sync_launch_create_rejects_empty_database_set(
    authenticated_client: APIClient,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/master-data/sync-launches/",
        {
            "mode": "outbound",
            "target_mode": "database_set",
            "database_ids": [],
            "entity_scope": ["item"],
        },
        format="json",
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "SYNC_LAUNCH_DATABASE_IDS_REQUIRED"


@pytest.mark.django_db
def test_master_data_sync_launch_create_requires_staff_or_tenant_admin(
    default_tenant: Tenant,
) -> None:
    member_user = User.objects.create_user(username=f"pool-mdm-sync-launch-member-{uuid4().hex[:8]}", password="pass")
    TenantMember.objects.update_or_create(
        tenant=default_tenant,
        user=member_user,
        defaults={"role": TenantMember.ROLE_MEMBER},
    )
    member_client = APIClient()
    member_client.force_authenticate(user=member_user)
    member_client.credentials(HTTP_X_CC1C_TENANT_ID=str(default_tenant.id))

    response = member_client.post(
        "/api/v2/pools/master-data/sync-launches/",
        {
            "mode": "inbound",
            "target_mode": "database_set",
            "database_ids": [str(uuid4())],
            "entity_scope": ["item"],
        },
        format="json",
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["code"] == "FORBIDDEN"


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
