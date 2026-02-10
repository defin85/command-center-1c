from __future__ import annotations

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from apps.databases.models import Database, DatabaseExtensionsSnapshot, DatabasePermission, PermissionLevel


@pytest.fixture
def user():
    return User.objects.create_user(username="extensions_snapshot_user", password="pass")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _grant_view_database_permission(user: User) -> None:
    ct = ContentType.objects.get(app_label="databases", model="database")
    perm = Permission.objects.get(content_type=ct, codename="view_database")
    user.user_permissions.add(perm)


@pytest.mark.django_db
def test_get_extensions_snapshot_requires_permission_and_returns_empty(client, user):
    db = Database.objects.create(
        name="db",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
    )

    denied = client.get("/api/v2/databases/get-extensions-snapshot/", {"database_id": str(db.id)})
    assert denied.status_code == 403

    _grant_view_database_permission(user)
    DatabasePermission.objects.create(user=user, database=db, level=PermissionLevel.VIEW)
    client.force_authenticate(user=User.objects.get(pk=user.pk))

    resp = client.get("/api/v2/databases/get-extensions-snapshot/", {"database_id": str(db.id)})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["database_id"] == str(db.id)
    assert payload["snapshot"] == {}

    DatabaseExtensionsSnapshot.objects.update_or_create(
        database_id=db.id,
        defaults={"snapshot": {"stdout": "ok", "exit_code": 0}, "source_operation_id": "op-1"},
    )
    resp2 = client.get("/api/v2/databases/get-extensions-snapshot/", {"database_id": str(db.id)})
    assert resp2.status_code == 200
    snapshot = resp2.json()["snapshot"]
    assert snapshot["extensions"] == []
    assert snapshot["raw"] == {"stdout": "ok", "exit_code": 0}
    assert snapshot["parse_error"] is None


@pytest.mark.django_db
def test_get_extensions_snapshot_preserves_full_extensions_fields(client, user):
    db = Database.objects.create(
        name="db",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
    )

    _grant_view_database_permission(user)
    DatabasePermission.objects.create(user=user, database=db, level=PermissionLevel.VIEW)
    client.force_authenticate(user=User.objects.get(pk=user.pk))

    DatabaseExtensionsSnapshot.objects.update_or_create(
        database_id=db.id,
        defaults={
            "snapshot": {
                "raw": {"stdout": "ok", "exit_code": 0},
                "parse_error": None,
                "extensions": [
                    {
                        "name": "ExtA",
                        "purpose": "Accounting",
                        "is_active": True,
                        "safe_mode": False,
                        "unsafe_action_protection": True,
                    },
                    {
                        "name": "ExtB",
                        "purpose": "",
                        "is_active": False,
                        "safe_mode": True,
                        "unsafe_action_protection": False,
                    },
                ],
            },
            "source_operation_id": "op-2",
        },
    )

    resp = client.get("/api/v2/databases/get-extensions-snapshot/", {"database_id": str(db.id)})
    assert resp.status_code == 200
    snapshot = resp.json()["snapshot"]
    assert snapshot["parse_error"] is None
    assert snapshot["raw"] == {"stdout": "ok", "exit_code": 0}
    assert snapshot["extensions"] == [
        {
            "name": "ExtA",
            "purpose": "Accounting",
            "is_active": True,
            "safe_mode": False,
            "unsafe_action_protection": True,
        },
        {
            "name": "ExtB",
            "purpose": "",
            "is_active": False,
            "safe_mode": True,
            "unsafe_action_protection": False,
        },
    ]
