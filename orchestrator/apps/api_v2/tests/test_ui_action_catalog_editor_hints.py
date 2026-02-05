import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient


@pytest.fixture
def staff_user():
    user = User.objects.create_user(username="ui_action_catalog_hints_staff", password="pass")
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
    return User.objects.create_user(username="ui_action_catalog_hints_user", password="pass")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.mark.django_db
def test_action_catalog_editor_hints_staff_only(client):
    resp = client.get("/api/v2/ui/action-catalog/editor-hints/")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_action_catalog_editor_hints_contains_extensions_set_flags(staff_client):
    resp = staff_client.get("/api/v2/ui/action-catalog/editor-hints/")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["hints_version"] == 1
    caps = payload.get("capabilities")
    assert isinstance(caps, dict)
    assert "extensions.set_flags" in caps
    hints = caps["extensions.set_flags"]
    assert isinstance(hints, dict)
    fixed_schema = hints.get("fixed_schema")
    assert isinstance(fixed_schema, dict)
    assert fixed_schema.get("type") == "object"
    props = fixed_schema.get("properties")
    assert isinstance(props, dict)
    assert "apply_mask" in props

