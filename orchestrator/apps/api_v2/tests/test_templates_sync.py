import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.templates.models import OperationExposure
from apps.templates.operation_catalog_service import upsert_template_exposure
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
    registry.register(
        OperationType(
            id=op_id,
            name=name,
            description="desc",
            backend=BackendType.RAS,
            target_entity=TargetEntity.INFOBASE,
            is_async=True,
            category="admin",
            tags=["test"],
        )
    )


@pytest.mark.django_db
def test_sync_from_registry_requires_staff(normal_client, isolated_registry):
    register_test_operation(isolated_registry)
    resp = normal_client.post("/api/v2/templates/sync-from-registry/", {"dry_run": True}, format="json")
    assert resp.status_code in [401, 403]


@pytest.mark.django_db
def test_sync_from_registry_dry_run_and_apply(staff_client, isolated_registry):
    register_test_operation(isolated_registry)
    base_qs = OperationExposure.objects.filter(surface=OperationExposure.SURFACE_TEMPLATE, tenant__isnull=True)
    before_count = base_qs.count()

    resp = staff_client.post("/api/v2/templates/sync-from-registry/", {"dry_run": True}, format="json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 1
    assert data["updated"] == 0
    assert base_qs.count() == before_count

    resp2 = staff_client.post("/api/v2/templates/sync-from-registry/", {"dry_run": False}, format="json")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["created"] == 1
    assert base_qs.count() == before_count + 1

    resp3 = staff_client.post("/api/v2/templates/sync-from-registry/", {}, format="json")
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3["created"] == 0
    assert data3["updated"] == 0
    assert data3["unchanged"] == 1


@pytest.mark.django_db
def test_sync_from_registry_updates_existing_exposure(staff_client, isolated_registry):
    register_test_operation(isolated_registry, op_id="test_op_update", name="Registry Name")
    template_id = "tpl-test-op-update"

    upsert_template_exposure(
        template_id=template_id,
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
    assert data["created"] == 0
    assert data["updated"] == 1

    exposure = OperationExposure.objects.get(
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias=template_id,
        tenant__isnull=True,
    )
    assert exposure.label == "Registry Name"
    assert exposure.is_active is True


@pytest.mark.django_db
def test_sync_from_registry_rejects_invalid_runtime_contract(staff_client, isolated_registry, monkeypatch):
    register_test_operation(isolated_registry, op_id="test_valid_sync", name="Valid op")

    monkeypatch.setattr(
        isolated_registry,
        "get_for_template_sync",
        lambda: [
            {
                "id": "tpl-invalid-sync",
                "name": "Invalid sync template",
                "description": "invalid payload",
                "operation_type": "unknown_sync_operation",
                "target_entity": "infobase",
                "template_data": "not-an-object",
                "is_active": True,
            }
        ],
    )

    resp = staff_client.post("/api/v2/templates/sync-from-registry/", {}, format="json")
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    detail = payload["error"]["details"][0]
    assert detail["template_id"] == "tpl-invalid-sync"
    codes = {item["code"] for item in detail["errors"]}
    assert "UNSUPPORTED_OPERATION_TYPE" in codes
    assert "INVALID_TYPE" in codes

    assert not OperationExposure.objects.filter(
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias="tpl-invalid-sync",
        tenant__isnull=True,
    ).exists()


@pytest.mark.django_db
def test_list_templates_with_default_sort_returns_200(staff_client, isolated_registry):
    register_test_operation(isolated_registry, op_id="test_op_list", name="List Name")
    sync_resp = staff_client.post("/api/v2/templates/sync-from-registry/", {"dry_run": False}, format="json")
    assert sync_resp.status_code == 200

    resp = staff_client.get("/api/v2/operation-catalog/exposures/?surface=template&limit=50&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["exposures"][0]["alias"] == "tpl-test-op-list"
