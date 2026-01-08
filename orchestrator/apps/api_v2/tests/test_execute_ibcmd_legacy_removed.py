import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from apps.databases.models import Database, DatabasePermission, PermissionLevel


def _grant_operation_permission(client: APIClient, user: User, codename: str) -> None:
    ct = ContentType.objects.get(app_label="operations", model="batchoperation")
    perm = Permission.objects.get(content_type=ct, codename=codename)
    user.user_permissions.add(perm)
    client.force_authenticate(user=User.objects.get(pk=user.pk))


def _allow_operate(user: User, database: Database, *, level: int = PermissionLevel.OPERATE) -> None:
    DatabasePermission.objects.create(user=user, database=database, level=level)


@pytest.fixture
def user():
    return User.objects.create_user(username="ibcmd_legacy_removed_user", password="pass")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def target_dbs():
    db1 = Database.objects.create(
        name="target_db_1",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
    )
    db2 = Database.objects.create(
        name="target_db_2",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
    )
    return [db1, db2]


@pytest.mark.django_db
def test_execute_ibcmd_endpoint_removed_returns_404(client):
    resp = client.post("/api/v2/operations/execute-ibcmd/", {}, format="json")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_execute_operation_rejects_legacy_ibcmd_operation_type(client, user, target_dbs):
    _grant_operation_permission(client, user, "execute_safe_operation")
    for db in target_dbs:
        _allow_operate(user, db)

    resp = client.post(
        "/api/v2/operations/execute/",
        {
            "operation_type": "ibcmd_backup",
            "database_ids": [db.id for db in target_dbs],
            "config": {},
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert "operation_type" in payload

