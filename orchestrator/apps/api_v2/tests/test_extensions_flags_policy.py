# ruff: noqa: F811
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from apps.databases.models import Database, DatabaseExtensionsSnapshot, DatabasePermission, ExtensionFlagsPolicy, PermissionLevel
from apps.tenancy.models import Tenant, TenantMember


def _jwt_login(client: APIClient, *, username: str, password: str) -> None:
    resp = client.post("/api/token/", {"username": username, "password": password}, format="json")
    assert resp.status_code == 200
    access = resp.json()["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")


def _grant_permission(user: User, *, app_label: str, model: str, codename: str) -> None:
    ct = ContentType.objects.get(app_label=app_label, model=model)
    perm = Permission.objects.get(content_type=ct, codename=codename)
    user.user_permissions.add(perm)


@pytest.mark.django_db
def test_extensions_flags_policy_staff_requires_explicit_tenant_header_for_mutating():
    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    user = User.objects.create_user(username="staff_policy", password="pass", is_staff=True)
    TenantMember.objects.get_or_create(tenant=tenant, user=user, defaults={"role": TenantMember.ROLE_ADMIN})
    _grant_permission(user, app_label="databases", model="database", codename="manage_database")

    client = APIClient()
    _jwt_login(client, username=user.username, password="pass")

    resp = client.put(
        "/api/v2/extensions/flags-policy/ExtA/",
        {"active": True, "safe_mode": None, "unsafe_action_protection": False},
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "TENANT_CONTEXT_REQUIRED"


@pytest.mark.django_db
def test_extensions_flags_policy_staff_upsert_and_list():
    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    user = User.objects.create_user(username="staff_policy2", password="pass", is_staff=True)
    TenantMember.objects.get_or_create(tenant=tenant, user=user, defaults={"role": TenantMember.ROLE_ADMIN})
    _grant_permission(user, app_label="databases", model="database", codename="manage_database")
    _grant_permission(user, app_label="databases", model="database", codename="view_database")

    client = APIClient()
    _jwt_login(client, username=user.username, password="pass")

    upsert = client.put(
        "/api/v2/extensions/flags-policy/ExtA/",
        {"active": True, "safe_mode": None, "unsafe_action_protection": False, "reason": "test"},
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )
    assert upsert.status_code == 200
    data = upsert.json()
    assert data["extension_name"] == "ExtA"
    assert data["active"] is True
    assert data["safe_mode"] is None
    assert data["unsafe_action_protection"] is False

    lst = client.get("/api/v2/extensions/flags-policy/", HTTP_X_CC1C_TENANT_ID=str(tenant.id))
    assert lst.status_code == 200
    policies = lst.json()["policies"]
    assert any(p["extension_name"] == "ExtA" for p in policies)


@pytest.mark.django_db
def test_extensions_flags_policy_user_upsert_without_explicit_tenant_header():
    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    user = User.objects.create_user(username="u_policy", password="pass")
    TenantMember.objects.get_or_create(tenant=tenant, user=user, defaults={"role": TenantMember.ROLE_MEMBER})
    _grant_permission(user, app_label="databases", model="database", codename="manage_database")

    client = APIClient()
    _jwt_login(client, username=user.username, password="pass")

    resp = client.put(
        "/api/v2/extensions/flags-policy/ExtB/",
        {"active": None, "safe_mode": True, "unsafe_action_protection": None},
        format="json",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["extension_name"] == "ExtB"
    assert data["safe_mode"] is True


@pytest.mark.django_db
def test_extensions_flags_policy_adopt_from_database_snapshot():
    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    user = User.objects.create_user(username="staff_adopt", password="pass", is_staff=True)
    TenantMember.objects.get_or_create(tenant=tenant, user=user, defaults={"role": TenantMember.ROLE_ADMIN})
    _grant_permission(user, app_label="databases", model="database", codename="manage_database")

    db = Database.objects.create(
        tenant=tenant,
        name="db_adopt",
        host="localhost",
        port=80,
        base_name="db_adopt",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db,
        defaults={
            "snapshot": {
                "extensions": [
                    {"name": "ExtA", "is_active": True, "safe_mode": False, "unsafe_action_protection": True},
                ],
                "raw": {},
                "parse_error": None,
            }
        },
    )

    client = APIClient()
    _jwt_login(client, username=user.username, password="pass")

    resp = client.post(
        "/api/v2/extensions/flags-policy/adopt/",
        {"database_id": db.id, "extension_name": "ExtA", "reason": "seed"},
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["extension_name"] == "ExtA"
    assert data["active"] is True
    assert data["safe_mode"] is False
    assert data["unsafe_action_protection"] is True

    obj = ExtensionFlagsPolicy.objects.get(tenant_id=str(tenant.id), extension_name="ExtA")
    assert obj.active is True
