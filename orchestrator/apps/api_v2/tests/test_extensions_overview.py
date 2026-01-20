import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from apps.databases.models import Database, DatabaseExtensionsSnapshot, DatabasePermission, PermissionLevel


def _grant_view_database(client: APIClient, user: User) -> None:
    ct = ContentType.objects.get(app_label="databases", model="database")
    perm = Permission.objects.get(content_type=ct, codename="view_database")
    user.user_permissions.add(perm)
    client.force_authenticate(user=User.objects.get(pk=user.pk))


@pytest.mark.django_db
def test_extensions_overview_respects_rbac_and_counts():
    user = User.objects.create_user(username="u", password="pass")
    client = APIClient()
    client.force_authenticate(user=user)
    _grant_view_database(client, user)

    db1 = Database.objects.create(
        name="db1",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
    )
    db2 = Database.objects.create(
        name="db2",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
    )
    db3 = Database.objects.create(
        name="db3-no-access",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
    )

    DatabasePermission.objects.create(user=user, database=db1, level=PermissionLevel.VIEW)
    DatabasePermission.objects.create(user=user, database=db2, level=PermissionLevel.VIEW)

    DatabaseExtensionsSnapshot.objects.update_or_create(
        database_id=db1.id,
        defaults={
            "snapshot": {
                "extensions": [{"name": "ExtA", "version": "1.0", "is_active": True}],
                "raw": {"stdout": "ok"},
                "parse_error": None,
            },
            "source_operation_id": "op-1",
        },
    )
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database_id=db2.id,
        defaults={
            "snapshot": {
                "extensions": [{"name": "ExtB", "version": "2.0", "is_active": False}],
                "raw": {"stdout": "ok"},
                "parse_error": None,
            },
            "source_operation_id": "op-2",
        },
    )
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database_id=db3.id,
        defaults={
            "snapshot": {
                "extensions": [{"name": "ExtA", "version": "1.0", "is_active": True}],
                "raw": {"stdout": "ok"},
                "parse_error": None,
            },
            "source_operation_id": "op-3",
        },
    )

    resp = client.get("/api/v2/extensions/overview/", {"search": "ExtA"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total_databases"] == 2  # db1 + db2 only
    assert payload["count"] == 1
    row = payload["extensions"][0]
    assert row["name"] == "ExtA"
    assert row["installed_count"] == 1
    assert row["active_count"] == 1
    assert row["inactive_count"] == 0
    assert row["missing_count"] == 1
    assert row["unknown_count"] == 0


@pytest.mark.django_db
def test_extensions_overview_drilldown_filters_by_status():
    user = User.objects.create_user(username="u2", password="pass")
    client = APIClient()
    client.force_authenticate(user=user)
    _grant_view_database(client, user)

    db1 = Database.objects.create(
        name="db1",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
    )
    db2 = Database.objects.create(
        name="db2",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
    )

    DatabasePermission.objects.create(user=user, database=db1, level=PermissionLevel.VIEW)
    DatabasePermission.objects.create(user=user, database=db2, level=PermissionLevel.VIEW)

    DatabaseExtensionsSnapshot.objects.update_or_create(
        database_id=db1.id,
        defaults={
            "snapshot": {
                "extensions": [{"name": "ExtA", "version": "1.0", "is_active": True}],
                "raw": {"stdout": "ok"},
                "parse_error": None,
            },
            "source_operation_id": "op-1",
        },
    )
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database_id=db2.id,
        defaults={
            "snapshot": {
                "extensions": [{"name": "ExtB", "version": "2.0", "is_active": False}],
                "raw": {"stdout": "ok"},
                "parse_error": None,
            },
            "source_operation_id": "op-2",
        },
    )

    resp_active = client.get("/api/v2/extensions/overview/databases/", {"name": "ExtA", "status": "active"})
    assert resp_active.status_code == 200
    payload_active = resp_active.json()
    assert payload_active["count"] == 1
    assert payload_active["databases"][0]["database_name"] == "db1"

    resp_missing = client.get("/api/v2/extensions/overview/databases/", {"name": "ExtA", "status": "missing"})
    assert resp_missing.status_code == 200
    payload_missing = resp_missing.json()
    assert payload_missing["count"] == 1
    assert payload_missing["databases"][0]["database_name"] == "db2"

