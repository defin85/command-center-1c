import pytest
from django.contrib.auth.models import User
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.databases.models import Database, DatabaseExtensionsSnapshot
from apps.operations.models import BatchOperation, CommandResultSnapshot
from apps.runtime_settings.models import RuntimeSetting, TenantRuntimeSettingOverride
from apps.tenancy.models import Tenant, TenantMember


def _jwt_login(client: APIClient, *, username: str, password: str) -> None:
    resp = client.post("/api/token/", {"username": username, "password": password}, format="json")
    assert resp.status_code == 200
    access = resp.json()["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def staff_user():
    user = User.objects.create_user(username="staff", password="pass", is_staff=True)
    default, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    TenantMember.objects.get_or_create(
        tenant=default,
        user=user,
        defaults={"role": TenantMember.ROLE_ADMIN},
    )
    return user


@pytest.fixture
def user():
    user = User.objects.create_user(username="user", password="pass")
    default, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    TenantMember.objects.get_or_create(
        tenant=default,
        user=user,
        defaults={"role": TenantMember.ROLE_MEMBER},
    )
    return user


@pytest.mark.django_db
def test_list_my_tenants_returns_default(client, user):
    _jwt_login(client, username=user.username, password="pass")
    resp = client.get("/api/v2/tenants/list-my-tenants/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenants"]
    assert any(t.get("slug") == "default" for t in data["tenants"])
    assert data["active_tenant_id"] is not None


@pytest.mark.django_db
def test_tenant_header_requires_membership(client, user):
    other = Tenant.objects.create(slug="t2", name="Tenant 2")
    _jwt_login(client, username=user.username, password="pass")
    resp = client.get("/api/v2/system/me/", HTTP_X_CC1C_TENANT_ID=str(other.id))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_list_databases_staff_can_see_cross_tenant_without_header(client, staff_user):
    default = Tenant.objects.get(slug="default")
    other = Tenant.objects.create(slug="t2", name="Tenant 2")
    TenantMember.objects.get_or_create(tenant=default, user=staff_user, defaults={"role": TenantMember.ROLE_ADMIN})

    db1 = Database.objects.create(
        tenant=default,
        name="db1",
        host="localhost",
        port=80,
        base_name="db1",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )
    db2 = Database.objects.create(
        tenant=other,
        name="db2",
        host="localhost",
        port=80,
        base_name="db2",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )

    _jwt_login(client, username=staff_user.username, password="pass")
    resp = client.get("/api/v2/databases/list-databases/")
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()["databases"]}
    assert str(db1.id) in ids
    assert str(db2.id) in ids


@pytest.mark.django_db
def test_list_databases_staff_with_tenant_header_is_filtered(client, staff_user):
    default = Tenant.objects.get(slug="default")
    other = Tenant.objects.create(slug="t2", name="Tenant 2")
    TenantMember.objects.get_or_create(tenant=default, user=staff_user, defaults={"role": TenantMember.ROLE_ADMIN})
    TenantMember.objects.get_or_create(tenant=other, user=staff_user, defaults={"role": TenantMember.ROLE_ADMIN})

    db1 = Database.objects.create(
        tenant=default,
        name="db1",
        host="localhost",
        port=80,
        base_name="db1",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )
    db2 = Database.objects.create(
        tenant=other,
        name="db2",
        host="localhost",
        port=80,
        base_name="db2",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )

    _jwt_login(client, username=staff_user.username, password="pass")
    resp = client.get("/api/v2/databases/list-databases/", HTTP_X_CC1C_TENANT_ID=str(other.id))
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()["databases"]}
    assert str(db1.id) not in ids
    assert str(db2.id) in ids


@pytest.mark.django_db
def test_runtime_effective_uses_tenant_override(client, staff_user):
    default = Tenant.objects.get(slug="default")
    _jwt_login(client, username=staff_user.username, password="pass")

    TenantRuntimeSettingOverride.objects.update_or_create(
        tenant=default,
        key="ui.action_catalog",
        defaults={"status": TenantRuntimeSettingOverride.STATUS_PUBLISHED, "value": {"catalog_version": 1, "extensions": {"actions": []}}},
    )

    resp = client.get("/api/v2/settings/runtime-effective/")
    assert resp.status_code == 200
    settings = resp.json()["settings"]
    entry = next((s for s in settings if s["key"] == "ui.action_catalog"), None)
    assert entry is not None
    assert entry["source"] == "tenant_override"


@pytest.mark.django_db
def test_snapshots_list_and_get_are_tenant_scoped(client, staff_user):
    default = Tenant.objects.get(slug="default")
    _jwt_login(client, username=staff_user.username, password="pass")

    db = Database.objects.create(
        tenant=default,
        name="db_snap",
        host="localhost",
        port=80,
        base_name="db_snap",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )
    op = BatchOperation.objects.create(
        id="op1",
        name="op1",
        operation_type=BatchOperation.TYPE_QUERY,
        target_entity="Test",
        created_by="test",
    )
    snap = CommandResultSnapshot.objects.create(
        tenant=default,
        operation=op,
        database=db,
        driver="ibcmd",
        command_id="cmd1",
        raw_payload={"stdout": "x"},
        normalized_payload={"extensions": []},
        canonical_payload={"extensions": []},
        canonical_hash="0" * 64,
    )

    resp = client.get("/api/v2/snapshots/list/?command_id=cmd1")
    assert resp.status_code == 200
    assert resp.json()["count"] == 1
    assert resp.json()["snapshots"][0]["id"] == snap.id

    resp2 = client.get(f"/api/v2/snapshots/get/?snapshot_id={snap.id}")
    assert resp2.status_code == 200
    assert resp2.json()["id"] == snap.id


@pytest.mark.django_db
def test_mapping_preview_ok(client, staff_user):
    default = Tenant.objects.get(slug="default")
    _jwt_login(client, username=staff_user.username, password="pass")

    db = Database.objects.create(
        tenant=default,
        name="db_map",
        host="localhost",
        port=80,
        base_name="db_map",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )
    op = BatchOperation.objects.create(
        id="op2",
        name="op2",
        operation_type=BatchOperation.TYPE_QUERY,
        target_entity="Test",
        created_by="test",
    )
    snap = CommandResultSnapshot.objects.create(
        tenant=default,
        operation=op,
        database=db,
        driver="ibcmd",
        command_id="cmd2",
        raw_payload={},
        normalized_payload={"extensions": [{"name": "A", "version": "1"}]},
        canonical_payload={"extensions": [{"name": "A", "version": "1"}]},
        canonical_hash="1" * 64,
    )

    resp_upsert = client.patch(
        "/api/v2/mappings/upsert/",
        {"entity_kind": "extensions_inventory", "status": "published", "spec": {}},
        format="json",
    )
    assert resp_upsert.status_code == 200

    resp_preview = client.post(
        "/api/v2/mappings/preview/",
        {"entity_kind": "extensions_inventory", "snapshot_id": snap.id, "status": "published"},
        format="json",
    )
    assert resp_preview.status_code == 200
    data = resp_preview.json()
    assert data["ok"] is True
    assert data["canonical"]["extensions"][0]["name"] == "A"


@pytest.mark.django_db
def test_extensions_apply_detects_drift(client, staff_user, monkeypatch):
    default = Tenant.objects.get(slug="default")
    _jwt_login(client, username=staff_user.username, password="pass")

    RuntimeSetting.objects.update_or_create(
        key="ui.action_catalog",
        defaults={
            "value": {
                "catalog_version": 1,
                "extensions": {
                    "actions": [
                        {
                            "id": "ListAction",
                            "capability": "extensions.list",
                            "label": "List",
                            "contexts": ["bulk_page"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "dummy_list"},
                        },
                        {
                            "id": "SyncAction",
                            "capability": "extensions.sync",
                            "label": "Sync",
                            "contexts": ["bulk_page"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "dummy"},
                        }
                    ]
                },
            }
        },
    )

    monkeypatch.setattr(
        "apps.api_v2.views.extensions_plan_apply._preview_ibcmd_cli",
        lambda **_kwargs: ({"execution_plan": {"plan_version": 1}, "bindings": []}, None, None),
    )
    monkeypatch.setattr(
        "apps.api_v2.views.extensions_plan_apply._execute_ibcmd_cli_validated",
        lambda _request, _validated_data, **_kwargs: Response({"operation_id": "op-preflight", "status": "queued"}, status=202),
    )
    monkeypatch.setattr(
        "apps.api_v2.views.extensions_plan_apply.ResultWaiter.wait",
        lambda *_args, **_kwargs: {"success": True, "status": "completed", "results": []},
    )

    db = Database.objects.create(
        tenant=default,
        name="db_drift",
        host="localhost",
        port=80,
        base_name="db_drift",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db,
        defaults={"snapshot": {"extensions": [{"name": "A"}], "raw": {}, "parse_error": None}},
    )

    plan_resp = client.post("/api/v2/extensions/plan/", {"database_ids": [db.id]}, format="json")
    assert plan_resp.status_code == 200
    plan_id = plan_resp.json()["plan_id"]

    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db,
        defaults={"snapshot": {"extensions": [{"name": "B"}], "raw": {}, "parse_error": None}},
    )

    apply_resp = client.post("/api/v2/extensions/apply/", {"plan_id": plan_id}, format="json")
    assert apply_resp.status_code == 409


@pytest.mark.django_db
def test_extensions_apply_success_enqueues_sync(client, staff_user, monkeypatch):
    default = Tenant.objects.get(slug="default")
    _jwt_login(client, username=staff_user.username, password="pass")

    RuntimeSetting.objects.update_or_create(
        key="ui.action_catalog",
        defaults={
            "value": {
                "catalog_version": 1,
                "extensions": {
                    "actions": [
                        {
                            "id": "ListAction",
                            "capability": "extensions.list",
                            "label": "List",
                            "contexts": ["bulk_page"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "dummy_list"},
                        },
                        {
                            "id": "SyncAction",
                            "capability": "extensions.sync",
                            "label": "Sync",
                            "contexts": ["bulk_page"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "dummy_sync"},
                        },
                    ]
                },
            }
        },
    )

    monkeypatch.setattr(
        "apps.api_v2.views.extensions_plan_apply._preview_ibcmd_cli",
        lambda **_kwargs: ({"execution_plan": {"plan_version": 1}, "bindings": []}, None, None),
    )

    def _fake_execute(_request, validated_data, *, metadata_overrides=None, **_kwargs):
        cmd = str(validated_data.get("command_id") or "")
        if cmd == "dummy_list":
            assert metadata_overrides is not None
            assert metadata_overrides.get("snapshot_kinds") == ["extensions"]
            assert metadata_overrides.get("action_capability") == "extensions.list"
            return Response({"operation_id": "op-preflight", "status": "queued"}, status=202)
        if cmd == "dummy_sync":
            assert metadata_overrides is not None
            assert metadata_overrides.get("snapshot_kinds") == ["extensions"]
            assert metadata_overrides.get("action_capability") == "extensions.sync"
            return Response({"operation_id": "op-sync", "status": "queued"}, status=202)
        return Response({"success": False, "error": {"code": "UNKNOWN_COMMAND", "message": cmd}}, status=400)

    monkeypatch.setattr("apps.api_v2.views.extensions_plan_apply._execute_ibcmd_cli_validated", _fake_execute)
    monkeypatch.setattr(
        "apps.api_v2.views.extensions_plan_apply.ResultWaiter.wait",
        lambda *_args, **_kwargs: {"success": True, "status": "completed", "results": []},
    )

    db = Database.objects.create(
        tenant=default,
        name="db_ok",
        host="localhost",
        port=80,
        base_name="db_ok",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db,
        defaults={"snapshot": {"extensions": [{"name": "A"}], "raw": {}, "parse_error": None}},
    )

    plan_resp = client.post("/api/v2/extensions/plan/", {"database_ids": [db.id]}, format="json")
    assert plan_resp.status_code == 200
    plan_id = plan_resp.json()["plan_id"]

    apply_resp = client.post("/api/v2/extensions/apply/", {"plan_id": plan_id}, format="json")
    assert apply_resp.status_code == 202
    assert apply_resp.json()["operation_id"] == "op-sync"


@pytest.mark.django_db
def test_tenant_preference_is_used_when_header_missing(client):
    default, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    other = Tenant.objects.create(slug="t2", name="Tenant 2")

    u = User.objects.create_user(username="pref_user", password="pass", is_staff=True)
    TenantMember.objects.get_or_create(tenant=default, user=u, defaults={"role": TenantMember.ROLE_MEMBER})
    TenantMember.objects.get_or_create(tenant=other, user=u, defaults={"role": TenantMember.ROLE_MEMBER})

    TenantRuntimeSettingOverride.objects.update_or_create(
        tenant=other,
        key="ui.action_catalog",
        defaults={"status": TenantRuntimeSettingOverride.STATUS_PUBLISHED, "value": {"catalog_version": 99, "extensions": {"actions": []}}},
    )

    _jwt_login(client, username=u.username, password="pass")
    resp = client.post("/api/v2/tenants/set-active/", {"tenant_id": str(other.id)}, format="json")
    assert resp.status_code == 200

    resp2 = client.get("/api/v2/system/me/")
    assert resp2.status_code == 200

    resp3 = client.get("/api/v2/settings/runtime-effective/")
    assert resp3.status_code == 200
    settings = resp3.json()["settings"]
    entry = next((s for s in settings if s["key"] == "ui.action_catalog"), None)
    assert entry is not None
    assert entry["source"] == "tenant_override"


@pytest.mark.django_db
def test_service_user_without_membership_can_use_default_tenant(client):
    # Service JWT auth is covered by v1 archive tests, but we still want to ensure
    # tenant resolver permits service users without membership and selects default tenant.
    from apps.core.authentication import ServiceUser
    from apps.tenancy.authentication import _resolve_tenant_for_user

    default, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    svc = ServiceUser("svc")
    resolved = _resolve_tenant_for_user(svc, header_tenant_id=None)
    assert str(resolved.id) == str(default.id)
