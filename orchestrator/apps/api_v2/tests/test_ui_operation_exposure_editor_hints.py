import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient


@pytest.fixture
def staff_user():
    user = User.objects.create_user(username="ui_operation_exposure_hints_staff", password="pass")
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    return user


@pytest.fixture
def staff_client(staff_user):
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


@pytest.fixture
def user():
    return User.objects.create_user(username="ui_operation_exposure_hints_user", password="pass")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.mark.django_db
def test_operation_exposure_editor_hints_requires_auth():
    resp = APIClient().get("/api/v2/ui/operation-exposures/editor-hints/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_operation_exposure_editor_hints_staff_only(client):
    resp = client.get("/api/v2/ui/operation-exposures/editor-hints/")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_operation_exposure_editor_hints_contains_extensions_set_flags(staff_client):
    resp = staff_client.get("/api/v2/ui/operation-exposures/editor-hints/")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["hints_version"] == 1
    caps = payload.get("capabilities")
    assert isinstance(caps, dict)
    assert "extensions.set_flags" in caps
    hints = caps["extensions.set_flags"]
    assert isinstance(hints, dict)
    assert "fixed_schema" not in hints
    assert "fixed_ui_schema" not in hints

    target_binding_schema = hints.get("target_binding_schema")
    assert isinstance(target_binding_schema, dict)
    assert target_binding_schema.get("type") == "object"
    assert "extension_name_param" in (target_binding_schema.get("properties") or {})

    help_payload = hints.get("help")
    assert isinstance(help_payload, dict)
    help_title = help_payload.get("title")
    help_description = help_payload.get("description")
    assert isinstance(help_title, str) and help_title
    assert isinstance(help_description, str) and "$flags." in help_description


@pytest.mark.django_db
def test_legacy_action_catalog_editor_hints_endpoint_is_removed(staff_client):
    resp = staff_client.get("/api/v2/ui/action-catalog/editor-hints/")
    assert resp.status_code == 404
