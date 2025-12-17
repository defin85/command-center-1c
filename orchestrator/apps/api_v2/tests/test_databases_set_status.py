import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.databases.models import Database


@pytest.fixture
def normal_client():
    user = User.objects.create_user(username="normal_user", password="pass")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def staff_client():
    user = User.objects.create_user(username="staff_user", password="pass")
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_set_database_status_requires_staff(normal_client):
    db = Database.objects.create(
        id="db-1",
        name="DB 1",
        host="localhost",
        port=80,
        base_name="db1",
        odata_url="http://localhost/db1/odata/standard.odata",
        username="user",
        password="secret",
        status=Database.STATUS_ACTIVE,
    )

    resp = normal_client.post(
        "/api/v2/databases/set-status/",
        {"database_ids": [db.id], "status": "maintenance"},
        format="json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_set_database_status_updates_status(staff_client):
    db = Database.objects.create(
        id="db-2",
        name="DB 2",
        host="localhost",
        port=80,
        base_name="db2",
        odata_url="http://localhost/db2/odata/standard.odata",
        username="user",
        password="secret",
        status=Database.STATUS_ACTIVE,
    )

    resp = staff_client.post(
        "/api/v2/databases/set-status/",
        {"database_ids": [db.id], "status": "maintenance", "reason": "planned"},
        format="json",
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["updated"] == 1
    assert payload["not_found"] == []
    assert payload["status"] == "maintenance"

    db.refresh_from_db()
    assert db.status == Database.STATUS_MAINTENANCE


@pytest.mark.django_db
def test_set_database_status_reports_not_found(staff_client):
    db = Database.objects.create(
        id="db-3",
        name="DB 3",
        host="localhost",
        port=80,
        base_name="db3",
        odata_url="http://localhost/db3/odata/standard.odata",
        username="user",
        password="secret",
        status=Database.STATUS_ACTIVE,
    )

    resp = staff_client.post(
        "/api/v2/databases/set-status/",
        {"database_ids": [db.id, "missing-db"], "status": "inactive"},
        format="json",
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["updated"] == 1
    assert payload["not_found"] == ["missing-db"]

