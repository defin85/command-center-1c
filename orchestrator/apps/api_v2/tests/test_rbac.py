import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.databases.models import Cluster, Database


@pytest.fixture
def staff_user():
    user = User.objects.create_user(username="staff", password="pass")
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    return user


@pytest.fixture
def normal_user():
    return User.objects.create_user(username="user", password="pass")


@pytest.fixture
def authenticated_client(staff_user):
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


@pytest.fixture
def normal_client(normal_user):
    client = APIClient()
    client.force_authenticate(user=normal_user)
    return client


@pytest.fixture
def cluster():
    return Cluster.objects.create(
        name="Test Cluster",
        ras_server="localhost:1545",
        cluster_service_url="http://localhost:8188",
    )


@pytest.fixture
def database(cluster):
    return Database.objects.create(
        id="db-1",
        name="test_db",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
        cluster=cluster,
    )


@pytest.mark.django_db
def test_rbac_requires_staff(normal_client):
    resp = normal_client.get("/api/v2/rbac/list-cluster-permissions/")
    assert resp.status_code in [401, 403]


@pytest.mark.django_db
def test_grant_and_list_cluster_permission(authenticated_client, staff_user, normal_user, cluster):
    resp = authenticated_client.post(
        "/api/v2/rbac/grant-cluster-permission/",
        {"user_id": normal_user.id, "cluster_id": str(cluster.id), "level": "OPERATE", "notes": "n"},
        format="json",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] is True
    assert data["permission"]["user"]["id"] == normal_user.id
    assert data["permission"]["cluster"]["id"] == str(cluster.id)
    assert data["permission"]["level"] == "OPERATE"

    resp2 = authenticated_client.get("/api/v2/rbac/list-cluster-permissions/", {"user_id": normal_user.id})
    assert resp2.status_code == 200
    listed = resp2.json()
    assert listed["total"] >= 1
    assert any(p["cluster"]["id"] == str(cluster.id) for p in listed["permissions"])


@pytest.mark.django_db
def test_grant_and_revoke_database_permission(authenticated_client, normal_user, database):
    resp = authenticated_client.post(
        "/api/v2/rbac/grant-database-permission/",
        {"user_id": normal_user.id, "database_id": database.id, "level": "VIEW"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["permission"]["level"] == "VIEW"

    revoke = authenticated_client.post(
        "/api/v2/rbac/revoke-database-permission/",
        {"user_id": normal_user.id, "database_id": database.id},
        format="json",
    )
    assert revoke.status_code == 200
    assert revoke.json()["deleted"] is True


@pytest.mark.django_db
def test_effective_access_self_only_for_non_staff(normal_client, normal_user, cluster, database, authenticated_client):
    # As staff, grant cluster permission to normal_user.
    authenticated_client.post(
        "/api/v2/rbac/grant-cluster-permission/",
        {"user_id": normal_user.id, "cluster_id": str(cluster.id), "level": "VIEW"},
        format="json",
    )

    resp = normal_client.get("/api/v2/rbac/get-effective-access/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["id"] == normal_user.id

    # Non-staff cannot request other user's access
    other = User.objects.create_user(username="other", password="pass")
    resp_forbidden = normal_client.get("/api/v2/rbac/get-effective-access/", {"user_id": other.id})
    assert resp_forbidden.status_code == 403

