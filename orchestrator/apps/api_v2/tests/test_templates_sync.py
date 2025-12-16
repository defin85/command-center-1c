import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.templates.models import OperationTemplate
from apps.templates.registry import get_registry
from apps.templates.registry.types import BackendType, OperationType, TargetEntity


@pytest.fixture
def staff_user():
    user = User.objects.create_user(username="staff_templates", password="pass")
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    return user


@pytest.fixture
def normal_user():
    return User.objects.create_user(username="user_templates", password="pass")


@pytest.fixture
def staff_client(staff_user):
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


@pytest.fixture
def normal_client(normal_user):
    client = APIClient()
    client.force_authenticate(user=normal_user)
    return client


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


def register_test_operation(registry, op_id: str = "test_op", name: str = "Test Op"):
    registry.register(OperationType(
        id=op_id,
        name=name,
        description="desc",
        backend=BackendType.RAS,
        target_entity=TargetEntity.INFOBASE,
        is_async=True,
        category="admin",
        tags=["test"],
    ))


@pytest.mark.django_db
def test_sync_from_registry_requires_staff(normal_client, isolated_registry):
    register_test_operation(isolated_registry)
    resp = normal_client.post("/api/v2/templates/sync-from-registry/", {"dry_run": True}, format="json")
    assert resp.status_code in [401, 403]


@pytest.mark.django_db
def test_sync_from_registry_dry_run_and_apply(staff_client, isolated_registry):
    register_test_operation(isolated_registry)

    resp = staff_client.post("/api/v2/templates/sync-from-registry/", {"dry_run": True}, format="json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 1
    assert data["updated"] == 0
    assert OperationTemplate.objects.count() == 0

    resp2 = staff_client.post("/api/v2/templates/sync-from-registry/", {"dry_run": False}, format="json")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["created"] == 1
    assert OperationTemplate.objects.count() == 1

    resp3 = staff_client.post("/api/v2/templates/sync-from-registry/", {}, format="json")
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3["created"] == 0
    assert data3["updated"] == 0
    assert data3["unchanged"] == 1


@pytest.mark.django_db
def test_sync_from_registry_updates_existing_template(staff_client, isolated_registry):
    register_test_operation(isolated_registry, op_id="test_op_update", name="Registry Name")
    template_id = "tpl-test-op-update"
    OperationTemplate.objects.create(
        id=template_id,
        name="Old Name",
        description="old",
        operation_type="test_op_update",
        target_entity="infobase",
        template_data={},
        is_active=False,
    )

    resp = staff_client.post("/api/v2/templates/sync-from-registry/", {}, format="json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] == 1

    tpl = OperationTemplate.objects.get(id=template_id)
    assert tpl.name == "Registry Name"
    assert tpl.is_active is True

