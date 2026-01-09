import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.databases.models import Cluster
from apps.operations.models import BatchOperation
from apps.operations.services.operations_service import EnqueueResult


@pytest.fixture
def superuser():
    return User.objects.create_superuser(username="admin_sync", password="pass", email="admin_sync@example.com")


@pytest.fixture
def api_client(superuser):
    client = APIClient()
    client.force_authenticate(user=superuser)
    return client


@pytest.fixture
def cluster():
    return Cluster.objects.create(
        name="Test Cluster",
        ras_server="localhost:1545",
        cluster_service_url="http://localhost:8188",
    )


@pytest.mark.django_db
def test_sync_cluster_enqueue_error_returns_response_and_marks_operation_failed(monkeypatch, api_client, cluster):
    def fake_enqueue_cluster_sync(cluster_id: str, operation_id: str, created_by: str):
        return EnqueueResult(
            success=False,
            operation_id=operation_id,
            status="error",
            error="boom",
        )

    monkeypatch.setattr(
        "apps.operations.services.operations_service.OperationsService.enqueue_cluster_sync",
        fake_enqueue_cluster_sync,
    )

    resp = api_client.post(f"/api/v2/clusters/sync-cluster/?cluster_id={cluster.id}", {}, format="json")
    assert resp.status_code == 500

    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "ENQUEUE_FAILED"
    assert data["error"]["message"] == "boom"

    op = BatchOperation.objects.get(id=data["operation_id"])
    assert op.status == BatchOperation.STATUS_FAILED
    assert op.failed_tasks == 1


@pytest.mark.django_db
def test_sync_cluster_duplicate_returns_409_and_marks_operation_failed(monkeypatch, api_client, cluster):
    def fake_enqueue_cluster_sync(cluster_id: str, operation_id: str, created_by: str):
        return EnqueueResult(
            success=False,
            operation_id=operation_id,
            status="duplicate",
            error="already running",
        )

    monkeypatch.setattr(
        "apps.operations.services.operations_service.OperationsService.enqueue_cluster_sync",
        fake_enqueue_cluster_sync,
    )

    resp = api_client.post(f"/api/v2/clusters/sync-cluster/?cluster_id={cluster.id}", {}, format="json")
    assert resp.status_code == 409

    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "SYNC_IN_PROGRESS"

    op = BatchOperation.objects.get(id=data["operation_id"])
    assert op.status == BatchOperation.STATUS_FAILED
    assert op.failed_tasks == 1

