import pytest
from django.contrib.auth.models import Permission, User
from rest_framework.test import APIClient

from apps.core import permission_codes as perms
from apps.tenancy.models import Tenant, TenantMember, UserTenantPreference


def _permission_by_code(code: str) -> Permission:
    app_label, codename = code.split(".", 1)
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


@pytest.fixture
def staff_user():
    user = User.objects.create_user(username="shell_bootstrap_staff", password="pass", is_staff=True)
    user.user_permissions.add(_permission_by_code(perms.PERM_DATABASES_MANAGE_RBAC))
    user.user_permissions.add(_permission_by_code(perms.PERM_OPERATIONS_MANAGE_DRIVER_CATALOGS))
    user.user_permissions.add(_permission_by_code(perms.PERM_OPERATIONS_MANAGE_RUNTIME_CONTROLS))
    return user


@pytest.fixture
def staff_client(staff_user):
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


@pytest.mark.django_db
def test_system_bootstrap_returns_shell_context(staff_client, staff_user):
    tenant_a = Tenant.objects.create(slug="alpha", name="Alpha")
    tenant_b = Tenant.objects.create(slug="beta", name="Beta")
    TenantMember.objects.create(tenant=tenant_a, user=staff_user, role=TenantMember.ROLE_ADMIN)
    TenantMember.objects.create(tenant=tenant_b, user=staff_user, role=TenantMember.ROLE_MEMBER)
    preference, _ = UserTenantPreference.objects.get_or_create(user=staff_user)
    preference.active_tenant = tenant_b
    preference.save(update_fields=["active_tenant", "updated_at"])

    response = staff_client.get("/api/v2/system/bootstrap/", HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9")

    assert response.status_code == 200
    payload = response.json()
    assert payload["me"] == {
      "id": staff_user.id,
      "username": staff_user.username,
      "is_staff": True,
    }
    assert payload["tenant_context"]["active_tenant_id"] == str(tenant_b.id)
    tenant_slugs = {item["slug"] for item in payload["tenant_context"]["tenants"]}
    assert {"alpha", "beta"}.issubset(tenant_slugs)
    assert payload["capabilities"] == {
      "can_manage_rbac": True,
      "can_manage_driver_catalogs": True,
      "can_manage_runtime_controls": True,
    }
    assert payload["i18n"] == {
      "supported_locales": ["ru", "en"],
      "default_locale": "ru",
      "requested_locale": None,
      "effective_locale": "en",
    }
    assert payload["access"]["user"]["id"] == staff_user.id
    assert payload["access"]["clusters"] == []
    assert payload["access"]["databases"] == []
    assert response["Content-Language"] == "en"
    assert "X-CC1C-Locale" in response["Vary"]


@pytest.mark.django_db
def test_system_bootstrap_runtime_control_capability_is_permission_backed():
    user = User.objects.create_user(username="shell_bootstrap_runtime_view", password="pass", is_staff=True)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/v2/system/bootstrap/")

    assert response.status_code == 200
    assert response.json()["capabilities"] == {
        "can_manage_rbac": False,
        "can_manage_driver_catalogs": False,
        "can_manage_runtime_controls": False,
    }


@pytest.mark.django_db
def test_system_bootstrap_explicit_locale_header_overrides_browser_signal(staff_client):
    response = staff_client.get(
        "/api/v2/system/bootstrap/",
        HTTP_X_CC1C_LOCALE="en",
        HTTP_ACCEPT_LANGUAGE="ru-RU,ru;q=0.9",
    )

    assert response.status_code == 200
    assert response.json()["i18n"] == {
        "supported_locales": ["ru", "en"],
        "default_locale": "ru",
        "requested_locale": "en",
        "effective_locale": "en",
    }
    assert response["Content-Language"] == "en"


@pytest.mark.django_db
def test_system_bootstrap_unsupported_language_signal_falls_back_to_default_locale(staff_client):
    response = staff_client.get(
        "/api/v2/system/bootstrap/",
        HTTP_ACCEPT_LANGUAGE="de-DE,de;q=0.9",
    )

    assert response.status_code == 200
    assert response.json()["i18n"] == {
        "supported_locales": ["ru", "en"],
        "default_locale": "ru",
        "requested_locale": None,
        "effective_locale": "ru",
    }
    assert response["Content-Language"] == "ru"
