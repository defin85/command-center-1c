import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.intercompany_pools.runtime_template_registry import (
    get_pool_runtime_template_aliases,
    sync_pool_runtime_template_registry,
)
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


@pytest.mark.django_db
def test_inspect_pool_runtime_registry_requires_staff(normal_client):
    resp = normal_client.get("/api/v2/templates/pool-runtime-registry/")
    assert resp.status_code == 403
    payload = resp.json()
    assert payload["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_inspect_pool_runtime_registry_returns_configured_entries(staff_client):
    sync_pool_runtime_template_registry()

    resp = staff_client.get("/api/v2/templates/pool-runtime-registry/")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["contract_version"] == "pool_runtime.v1"
    assert payload["count"] == len(get_pool_runtime_template_aliases())
    aliases = {row["alias"] for row in payload["entries"]}
    assert aliases == set(get_pool_runtime_template_aliases())
    assert all(row["status"] == "configured" for row in payload["entries"])
    assert all(row["system_managed"] is True for row in payload["entries"])
    assert all(row["domain"] == OperationExposure.DOMAIN_POOL_RUNTIME for row in payload["entries"])


@pytest.mark.django_db
def test_sync_from_registry_can_include_pool_runtime_aliases(staff_client, isolated_registry):
    expected_aliases = set(get_pool_runtime_template_aliases())
    assert not OperationExposure.objects.filter(
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias__in=expected_aliases,
        tenant__isnull=True,
    ).exists()

    resp = staff_client.post(
        "/api/v2/templates/sync-from-registry/",
        {"include_pool_runtime": True},
        format="json",
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["created"] == len(expected_aliases)
    assert payload["updated"] == 0
    assert payload["unchanged"] == 0

    rows = list(
        OperationExposure.objects.filter(
            surface=OperationExposure.SURFACE_TEMPLATE,
            alias__in=expected_aliases,
            tenant__isnull=True,
        )
    )
    assert len(rows) == len(expected_aliases)
    assert all(row.system_managed is True for row in rows)
    assert all(row.domain == OperationExposure.DOMAIN_POOL_RUNTIME for row in rows)


@pytest.mark.django_db
def test_sync_from_registry_skips_system_managed_pool_runtime_aliases(staff_client, isolated_registry, monkeypatch):
    sync_pool_runtime_template_registry()
    exposure_before = OperationExposure.objects.get(
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias="pool.prepare_input",
        tenant__isnull=True,
    )
    old_label = exposure_before.label
    old_revision = exposure_before.exposure_revision

    monkeypatch.setattr(
        isolated_registry,
        "get_for_template_sync",
        lambda: [
            {
                "id": "pool.prepare_input",
                "name": "Should Not Override",
                "description": "should not override",
                "operation_type": "pool.prepare_input",
                "target_entity": "pool_run",
                "template_data": {},
                "is_active": False,
            }
        ],
    )

    resp = staff_client.post("/api/v2/templates/sync-from-registry/", {}, format="json")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["created"] == 0
    assert payload["updated"] == 0
    assert payload["unchanged"] == 1

    exposure_after = OperationExposure.objects.get(
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias="pool.prepare_input",
        tenant__isnull=True,
    )
    assert exposure_after.label == old_label
    assert exposure_after.exposure_revision == old_revision
    assert exposure_after.system_managed is True
    assert exposure_after.domain == OperationExposure.DOMAIN_POOL_RUNTIME
