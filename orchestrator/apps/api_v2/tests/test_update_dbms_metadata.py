# ruff: noqa: F811
import pytest

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from apps.databases.models import Database, PermissionLevel
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Tenant

from ._execute_ibcmd_cli_support import client, target_dbs, user  # noqa: F401
from . import _execute_ibcmd_cli_support as support


def _grant_manage_database_permission(client, user: User) -> None:
    ct = ContentType.objects.get(app_label="databases", model="database")
    perm = Permission.objects.get(content_type=ct, codename="manage_database")
    user.user_permissions.add(perm)
    client.force_authenticate(user=User.objects.get(pk=user.pk))


@pytest.mark.django_db
def test_update_dbms_metadata_requires_manage_permission(client, user, target_dbs):
    db = target_dbs[0]
    _grant_manage_database_permission(client, user)
    support._allow_operate(user, db, level=PermissionLevel.OPERATE)

    resp = client.post(
        "/api/v2/databases/update-dbms-metadata/",
        {"database_id": db.id, "dbms": "PostgreSQL"},
        format="json",
    )
    assert resp.status_code == 403
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_update_dbms_metadata_set_and_reset(client, user, target_dbs):
    db = target_dbs[0]
    _grant_manage_database_permission(client, user)
    support._allow_operate(user, db, level=PermissionLevel.MANAGE)

    resp = client.post(
        "/api/v2/databases/update-dbms-metadata/",
        {"database_id": db.id, "dbms": "PostgreSQL", "db_server": "db.local", "db_name": "name"},
        format="json",
    )
    assert resp.status_code == 200

    db_refreshed = Database.objects.get(id=db.id)
    assert db_refreshed.metadata.get("dbms") == "PostgreSQL"
    assert db_refreshed.metadata.get("db_server") == "db.local"
    assert db_refreshed.metadata.get("db_name") == "name"

    resp = client.post(
        "/api/v2/databases/update-dbms-metadata/",
        {"database_id": db.id, "reset": True},
        format="json",
    )
    assert resp.status_code == 200

    db_refreshed = Database.objects.get(id=db.id)
    assert "dbms" not in db_refreshed.metadata
    assert "db_server" not in db_refreshed.metadata
    assert "db_name" not in db_refreshed.metadata


@pytest.mark.django_db
def test_update_dbms_metadata_rejects_empty_values(client, user, target_dbs):
    db = target_dbs[0]
    _grant_manage_database_permission(client, user)
    support._allow_operate(user, db, level=PermissionLevel.MANAGE)

    resp = client.post(
        "/api/v2/databases/update-dbms-metadata/",
        {"database_id": db.id, "dbms": ""},
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "INVALID_PARAMETER"


@pytest.mark.django_db
def test_update_dbms_metadata_requires_some_fields_unless_reset(client, user, target_dbs):
    db = target_dbs[0]
    _grant_manage_database_permission(client, user)
    support._allow_operate(user, db, level=PermissionLevel.MANAGE)

    resp = client.post(
        "/api/v2/databases/update-dbms-metadata/",
        {"database_id": db.id},
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "MISSING_PARAMETER"


@pytest.mark.django_db
def test_update_dbms_metadata_is_tenant_scoped(client, user):
    _grant_manage_database_permission(client, user)

    other = Tenant.objects.create(slug="other", name="Other")
    with tenant_context(str(other.id)):
        db_other = Database.objects.create(
            name="tenant_other_db",
            host="localhost",
            port=80,
            odata_url="http://localhost/odata",
            username="odata",
            password="secret",
        )

    resp = client.post(
        "/api/v2/databases/update-dbms-metadata/",
        {"database_id": db_other.id, "dbms": "PostgreSQL"},
        format="json",
    )
    assert resp.status_code == 404
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "DATABASE_NOT_FOUND"
