import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.templates.registry import get_registry
from apps.templates.registry.types import BackendType, OperationType, TargetEntity


@pytest.fixture
def staff_user():
    user = User.objects.create_user(username="catalog_admin", password="pass")
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    return user


@pytest.fixture
def client(staff_user):
    c = APIClient()
    c.force_authenticate(user=staff_user)
    return c


@pytest.fixture
def isolated_registry():
    registry = get_registry()
    previous = registry.get_all()
    registry.clear()
    try:
        yield registry
    finally:
        registry.clear()
        registry.register_many(previous)


@pytest.mark.django_db
def test_operations_catalog_returns_items(client, isolated_registry):
    isolated_registry.register(OperationType(
        id="designer_cli",
        name="Designer CLI",
        description="Execute designer CLI command.",
        backend=BackendType.CLI,
        target_entity=TargetEntity.INFOBASE,
        is_async=True,
        category="admin",
        tags=[],
    ))

    resp = client.get("/api/v2/operations/catalog/")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == len(payload["items"])

    found = next((item for item in payload["items"] if item["id"] == "designer_cli"), None)
    assert found is not None
    assert found["kind"] == "operation"
    assert found["driver"] == "cli"
    assert found["has_ui_form"] is True
    assert found["deprecated"] is False
    assert "cli" in (found.get("tags") or [])


@pytest.mark.django_db
def test_operations_catalog_marks_ibcmd_as_ui_available(client, isolated_registry):
    isolated_registry.register(OperationType(
        id="ibcmd_backup",
        name="IBCMD Backup Infobase",
        description="Backup infobase using ibcmd.",
        backend=BackendType.IBCMD,
        target_entity=TargetEntity.INFOBASE,
        is_async=True,
        category="admin",
        tags=[],
    ))

    resp = client.get("/api/v2/operations/catalog/")
    assert resp.status_code == 200
    payload = resp.json()

    found = next((item for item in payload["items"] if item["id"] == "ibcmd_backup"), None)
    assert found is not None
    assert found["kind"] == "operation"
    assert found["driver"] == "ibcmd"
    assert found["has_ui_form"] is True
