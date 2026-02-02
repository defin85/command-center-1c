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
def test_update_ibcmd_connection_profile_requires_manage_permission(client, user, target_dbs):
    db = target_dbs[0]
    _grant_manage_database_permission(client, user)
    support._allow_operate(user, db, level=PermissionLevel.OPERATE)

    resp = client.post(
        "/api/v2/databases/update-ibcmd-connection-profile/",
        {"database_id": db.id, "remote": "ssh://host:1545"},
        format="json",
    )
    assert resp.status_code == 403
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_update_ibcmd_connection_profile_remote_set_and_reset(client, user, target_dbs):
    db = target_dbs[0]
    _grant_manage_database_permission(client, user)
    support._allow_operate(user, db, level=PermissionLevel.MANAGE)

    resp = client.post(
        "/api/v2/databases/update-ibcmd-connection-profile/",
        {"database_id": db.id, "remote": "ssh://host:1545"},
        format="json",
    )
    assert resp.status_code == 200

    refreshed = Database.objects.get(id=db.id)
    profile = refreshed.metadata.get("ibcmd_connection")
    assert isinstance(profile, dict)
    assert profile.get("remote") == "ssh://host:1545"

    resp = client.post(
        "/api/v2/databases/update-ibcmd-connection-profile/",
        {"database_id": db.id, "reset": True},
        format="json",
    )
    assert resp.status_code == 200

    refreshed = Database.objects.get(id=db.id)
    assert "ibcmd_connection" not in (refreshed.metadata or {})

@pytest.mark.django_db
def test_update_ibcmd_connection_profile_remote_rejects_non_ssh(client, user, target_dbs):
    db = target_dbs[0]
    _grant_manage_database_permission(client, user)
    support._allow_operate(user, db, level=PermissionLevel.MANAGE)

    resp = client.post(
        "/api/v2/databases/update-ibcmd-connection-profile/",
        {"database_id": db.id, "remote": "http://host:1545"},
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_update_ibcmd_connection_profile_allows_offline_raw_keys(client, user, target_dbs):
    db = target_dbs[0]
    _grant_manage_database_permission(client, user)
    support._allow_operate(user, db, level=PermissionLevel.MANAGE)

    resp = client.post(
        "/api/v2/databases/update-ibcmd-connection-profile/",
        {"database_id": db.id, "offline": {"config": "/tmp/config", "data": "/tmp/data", "extra_key": "value"}},
        format="json",
    )
    assert resp.status_code == 200
    refreshed = Database.objects.get(id=db.id)
    profile = refreshed.metadata.get("ibcmd_connection")
    assert isinstance(profile, dict)
    assert profile.get("offline", {}).get("config") == "/tmp/config"
    assert profile.get("offline", {}).get("data") == "/tmp/data"
    assert profile.get("offline", {}).get("extra_key") == "value"


@pytest.mark.django_db
def test_update_ibcmd_connection_profile_rejects_secrets(client, user, target_dbs):
    db = target_dbs[0]
    _grant_manage_database_permission(client, user)
    support._allow_operate(user, db, level=PermissionLevel.MANAGE)

    resp = client.post(
        "/api/v2/databases/update-ibcmd-connection-profile/",
        {
            "database_id": db.id,
            "offline": {"config": "/tmp/config", "data": "/tmp/data", "db_user": "u"},
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_update_ibcmd_connection_profile_allows_empty_profile(client, user, target_dbs):
    db = target_dbs[0]
    _grant_manage_database_permission(client, user)
    support._allow_operate(user, db, level=PermissionLevel.MANAGE)

    resp = client.post(
        "/api/v2/databases/update-ibcmd-connection-profile/",
        {"database_id": db.id},
        format="json",
    )
    assert resp.status_code == 200
    refreshed = Database.objects.get(id=db.id)
    profile = refreshed.metadata.get("ibcmd_connection")
    assert isinstance(profile, dict)
    assert profile == {}


@pytest.mark.django_db
def test_update_ibcmd_connection_profile_is_tenant_scoped(client, user):
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
        "/api/v2/databases/update-ibcmd-connection-profile/",
        {"database_id": db_other.id, "remote": "ssh://host:1545"},
        format="json",
    )
    assert resp.status_code == 404
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "DATABASE_NOT_FOUND"
