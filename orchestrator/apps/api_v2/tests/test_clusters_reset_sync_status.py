import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.databases.models import Cluster


@pytest.fixture
def staff_user():
    user = User.objects.create_user(username="staff_reset", password="pass")
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    return user


@pytest.fixture
def normal_user():
    return User.objects.create_user(username="user_reset", password="pass")


@pytest.fixture
def staff_client(staff_user):
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


@pytest.fixture
def normal_client(normal_user):
    client = APIClient()
    client.force_authenticate(user=normal_user)
    return client


@pytest.fixture
def clusters():
    pending_1 = Cluster.objects.create(
        name="Pending 1",
        ras_server="localhost:1545",
        cluster_service_url="http://localhost:8188",
        last_sync_status="pending",
        last_sync_error="stuck",
    )
    pending_2 = Cluster.objects.create(
        name="Pending 2",
        ras_server="localhost:1545",
        cluster_service_url="http://localhost:8188",
        last_sync_status="pending",
        last_sync_error="stuck",
    )
    success = Cluster.objects.create(
        name="Success",
        ras_server="localhost:1545",
        cluster_service_url="http://localhost:8188",
        last_sync_status="success",
        last_sync_error="",
    )
    failed = Cluster.objects.create(
        name="Failed",
        ras_server="localhost:1545",
        cluster_service_url="http://localhost:8188",
        last_sync_status="failed",
        last_sync_error="err",
    )
    return {
        "pending": [pending_1, pending_2],
        "success": success,
        "failed": failed,
    }


@pytest.mark.django_db
def test_reset_sync_status_requires_staff(normal_client, clusters):
    resp = normal_client.post("/api/v2/clusters/reset-sync-status/", {}, format="json")
    assert resp.status_code in [401, 403]


@pytest.mark.django_db
def test_reset_sync_status_resets_all_pending(staff_client, clusters):
    resp = staff_client.post("/api/v2/clusters/reset-sync-status/", {}, format="json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["reset_count"] == 2
    assert len(data["clusters"]) == 2

    for c in clusters["pending"]:
        c.refresh_from_db()
        assert c.last_sync_status == "failed"
        assert c.last_sync_error == ""

    clusters["success"].refresh_from_db()
    assert clusters["success"].last_sync_status == "success"

    clusters["failed"].refresh_from_db()
    assert clusters["failed"].last_sync_status == "failed"


@pytest.mark.django_db
def test_reset_sync_status_specific_cluster(staff_client, clusters):
    target = clusters["pending"][0]
    resp = staff_client.post(f"/api/v2/clusters/reset-sync-status/?cluster_id={target.id}", {}, format="json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["reset_count"] == 1

    target.refresh_from_db()
    assert target.last_sync_status == "failed"

    other = clusters["pending"][1]
    other.refresh_from_db()
    assert other.last_sync_status == "pending"


@pytest.mark.django_db
def test_reset_sync_status_unknown_cluster_returns_404(staff_client, clusters):
    resp = staff_client.post("/api/v2/clusters/reset-sync-status/?cluster_id=00000000-0000-0000-0000-000000000000", {}, format="json")
    assert resp.status_code == 404

