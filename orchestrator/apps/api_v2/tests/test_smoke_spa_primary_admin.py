from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.databases.models import Cluster
from apps.operations.models import BatchOperation
from apps.templates.models import OperationTemplate
from apps.templates.registry import get_registry
from apps.templates.registry.types import BackendType, OperationType, TargetEntity


@pytest.fixture
def staff_client():
    user = User.objects.create_user(username="staff_smoke", password="pass")
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_spa_primary_admin_smoke(staff_client, monkeypatch):
    user = User.objects.get(username="staff_smoke")
    cluster = Cluster.objects.create(
        name="Smoke Cluster",
        ras_server="localhost:1545",
        cluster_service_url="http://localhost:8188",
        last_sync_status="pending",
        last_sync_error="stuck",
    )

    me = staff_client.get("/api/v2/system/me/")
    assert me.status_code == 200
    assert me.json()["is_staff"] is True

    clusters = staff_client.get("/api/v2/clusters/list-clusters/")
    assert clusters.status_code == 200

    reset = staff_client.post(f"/api/v2/clusters/reset-sync-status/?cluster_id={cluster.id}", {}, format="json")
    assert reset.status_code == 200
    cluster.refresh_from_db()
    assert cluster.last_sync_status == "failed"
    assert cluster.last_sync_error == ""

    rbac = staff_client.get("/api/v2/rbac/list-cluster-permissions/")
    assert rbac.status_code == 200

    operation = BatchOperation.objects.create(
        id="smoke-operation-1",
        name="Smoke Operation",
        operation_type="lock_scheduled_jobs",
        target_entity="infobase",
        status=BatchOperation.STATUS_COMPLETED,
        created_by=user.username,
    )

    ops_list = staff_client.get("/api/v2/operations/list-operations/?limit=10")
    assert ops_list.status_code == 200

    ops_filter = staff_client.get(
        f"/api/v2/operations/list-operations/?workflow_execution_id=wf-1&node_id=node-1"
    )
    assert ops_filter.status_code == 200

    ops_id_filter = staff_client.get(
        f"/api/v2/operations/list-operations/?operation_id={str(operation.id).upper()}"
    )
    assert ops_id_filter.status_code == 200

    ops_get = staff_client.get(f"/api/v2/operations/get-operation/?operation_id={operation.id}")
    assert ops_get.status_code == 200
    assert ops_get.json()["operation"]["id"] == str(operation.id)

    with patch("apps.operations.services.timeline_service.TimelineService._fetch_timeline_from_redis") as mock_fetch:
        mock_fetch.return_value = ([
            {
                "timestamp": 1734567890123,
                "event": "operation.started",
                "service": "worker",
                "trace_id": "trace-1",
                "workflow_execution_id": "wf-1",
                "node_id": "node-1",
                "metadata": {},
            }
        ], 1, 0)
        timeline = staff_client.post("/api/v2/operations/get-operation-timeline/", {"operation_id": operation.id}, format="json")
        assert timeline.status_code == 200
        timeline_data = timeline.json()
        assert timeline_data["timeline"][0]["trace_id"] == "trace-1"

    registry = get_registry()
    previous = registry.get_all()
    registry.clear()
    try:
        OperationTemplate.objects.all().delete()
        registry.register(OperationType(
            id="smoke_op",
            name="Smoke Op",
            description="desc",
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
            is_async=True,
            category="admin",
            tags=["smoke"],
        ))

        sync_dry = staff_client.post("/api/v2/templates/sync-from-registry/", {"dry_run": True}, format="json")
        assert sync_dry.status_code == 200
        assert sync_dry.json()["created"] == 1
        assert OperationTemplate.objects.count() == 0

        sync_apply = staff_client.post("/api/v2/templates/sync-from-registry/", {"dry_run": False}, format="json")
        assert sync_apply.status_code == 200
        assert sync_apply.json()["created"] == 1
        assert OperationTemplate.objects.count() == 1
    finally:
        registry.clear()
        registry.register_many(previous)

    from apps.api_v2.views import dlq as dlq_view

    class FakeRedis:
        def __init__(self, items):
            self._items = items

        def xlen(self, _stream):
            return len(self._items)

        def xrevrange(self, _stream, max="+", min="-", count=50):  # noqa: A002
            return list(reversed(self._items))[:count]

    monkeypatch.setattr(dlq_view, "_get_redis_client", lambda: FakeRedis([
        (
            "1710000000000-0",
            {
                "original_message_id": "orig-1",
                "operation_id": "op-1",
                "error_code": "ENVELOPE_PARSE_ERROR",
                "error_message": "bad json",
                "worker_id": "w1",
                "failed_at": "2025-12-16T10:00:00Z",
            },
        ),
    ]))

    dlq = staff_client.get("/api/v2/dlq/list/?limit=10")
    assert dlq.status_code == 200
    data = dlq.json()
    assert data["total"] == 1
    assert data["count"] == 1
