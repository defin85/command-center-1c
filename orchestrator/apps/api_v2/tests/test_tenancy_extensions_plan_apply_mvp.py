import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.databases.models import Database, DatabaseExtensionsSnapshot, DatabasePermission, ExtensionFlagsPolicy, PermissionLevel
from apps.operations.models import BatchOperation, CommandResultSnapshot
from apps.runtime_settings.models import RuntimeSetting, TenantRuntimeSettingOverride
from apps.templates.models import OperationExposure
from apps.templates.operation_catalog_service import resolve_definition, resolve_exposure
from apps.tenancy.models import Tenant, TenantMember


def _jwt_login(client: APIClient, *, username: str, password: str) -> None:
    resp = client.post("/api/token/", {"username": username, "password": password}, format="json")
    assert resp.status_code == 200
    access = resp.json()["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")


def _grant_view_database_permission(user: User) -> None:
    ct = ContentType.objects.get(app_label="databases", model="database")
    perm = Permission.objects.get(content_type=ct, codename="view_database")
    user.user_permissions.add(perm)


def _grant_manage_database_permission(user: User) -> None:
    ct = ContentType.objects.get(app_label="databases", model="database")
    perm = Permission.objects.get(content_type=ct, codename="manage_database")
    user.user_permissions.add(perm)


def _seed_action_catalog_exposures(*, tenant: Tenant, actions: list[dict], tenant_scoped: bool = False) -> None:
    tenant_scope = f"tenant:{tenant.id}" if tenant_scoped else "global"
    tenant_id = str(tenant.id) if tenant_scoped else None
    for index, action in enumerate(actions):
        executor = dict(action.get("executor") or {})
        capability = str(action.get("capability") or "").strip()
        fixed = executor.get("fixed")
        target_binding = executor.get("target_binding")
        capability_config: dict[str, object] = {}
        if isinstance(fixed, dict):
            fixed_payload = dict(fixed)
            apply_mask = fixed_payload.pop("apply_mask", None)
            if apply_mask is not None:
                capability_config["apply_mask"] = apply_mask
            if fixed_payload:
                capability_config["fixed"] = fixed_payload
        if isinstance(target_binding, dict):
            capability_config["target_binding"] = dict(target_binding)

        executor_payload = dict(executor)
        executor_payload.pop("target_binding", None)
        definition, _ = resolve_definition(
            tenant_scope=tenant_scope,
            executor_kind=str(executor_payload.get("kind") or "").strip(),
            executor_payload=executor_payload,
            contract_version=1,
        )
        resolve_exposure(
            definition=definition,
            surface=OperationExposure.SURFACE_ACTION_CATALOG,
            alias=str(action.get("id") or "").strip(),
            tenant_id=tenant_id,
            label=str(action.get("label") or action.get("id") or "").strip(),
            description=str(action.get("description") or ""),
            is_active=bool(action.get("is_active", True)),
            capability=capability,
            contexts=[str(v) for v in (action.get("contexts") or []) if isinstance(v, str)],
            display_order=index,
            capability_config=capability_config,
            status=OperationExposure.STATUS_PUBLISHED,
        )


def _mock_ibcmd_command_catalog(monkeypatch, commands: dict[str, list[str]]) -> None:
    def _fake_commands(_driver: str, _cache):
        return {
            command_id: {
                "params_by_name": {name: {"type": "string"} for name in params},
            }
            for command_id, params in commands.items()
        }

    monkeypatch.setattr("apps.templates.operation_catalog_service._commands_by_driver", _fake_commands)


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
def test_extensions_overview_staff_can_see_cross_tenant_without_header(client, staff_user):
    default = Tenant.objects.get(slug="default")
    other = Tenant.objects.create(slug="t2", name="Tenant 2")
    TenantMember.objects.get_or_create(tenant=default, user=staff_user, defaults={"role": TenantMember.ROLE_ADMIN})

    _grant_view_database_permission(staff_user)

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
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db1,
        defaults={"snapshot": {"extensions": [{"name": "ExtA", "purpose": "patch", "safe_mode": True}], "raw": {}, "parse_error": None}},
    )
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db2,
        defaults={"snapshot": {"extensions": [{"name": "ExtB", "purpose": "add-on", "safe_mode": False}], "raw": {}, "parse_error": None}},
    )

    _jwt_login(client, username=staff_user.username, password="pass")
    resp = client.get("/api/v2/extensions/overview/")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total_databases"] == 2
    names = {row["name"] for row in payload["extensions"]}
    assert names == {"ExtA", "ExtB"}


@pytest.mark.django_db
def test_extensions_overview_staff_with_tenant_header_is_filtered(client, staff_user):
    default = Tenant.objects.get(slug="default")
    other = Tenant.objects.create(slug="t2", name="Tenant 2")
    TenantMember.objects.get_or_create(tenant=default, user=staff_user, defaults={"role": TenantMember.ROLE_ADMIN})
    TenantMember.objects.get_or_create(tenant=other, user=staff_user, defaults={"role": TenantMember.ROLE_ADMIN})

    _grant_view_database_permission(staff_user)

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
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db1,
        defaults={"snapshot": {"extensions": [{"name": "ExtA"}], "raw": {}, "parse_error": None}},
    )
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db2,
        defaults={"snapshot": {"extensions": [{"name": "ExtB"}], "raw": {}, "parse_error": None}},
    )

    _jwt_login(client, username=staff_user.username, password="pass")
    resp = client.get("/api/v2/extensions/overview/", HTTP_X_CC1C_TENANT_ID=str(other.id))
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total_databases"] == 1
    names = {row["name"] for row in payload["extensions"]}
    assert names == {"ExtB"}


@pytest.mark.django_db
def test_extensions_overview_user_is_tenant_scoped(client, user):
    default = Tenant.objects.get(slug="default")
    other = Tenant.objects.create(slug="t2", name="Tenant 2")
    TenantMember.objects.get_or_create(tenant=other, user=user, defaults={"role": TenantMember.ROLE_MEMBER})

    _grant_view_database_permission(user)

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
    DatabasePermission.objects.create(user=user, database=db1, level=PermissionLevel.VIEW)
    DatabasePermission.objects.create(user=user, database=db2, level=PermissionLevel.VIEW)

    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db1,
        defaults={"snapshot": {"extensions": [{"name": "ExtA"}], "raw": {}, "parse_error": None}},
    )
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db2,
        defaults={"snapshot": {"extensions": [{"name": "ExtB"}], "raw": {}, "parse_error": None}},
    )

    _jwt_login(client, username=user.username, password="pass")
    resp = client.get("/api/v2/extensions/overview/", HTTP_X_CC1C_TENANT_ID=str(other.id))
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total_databases"] == 1
    names = {row["name"] for row in payload["extensions"]}
    assert names == {"ExtB"}


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

    _seed_action_catalog_exposures(
        tenant=default,
        actions=[
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
            },
        ],
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

    _seed_action_catalog_exposures(
        tenant=default,
        actions=[
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
        ],
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
def test_extensions_plan_apply_set_flags_resolves_policy_and_sets_post_completion_sync(client, staff_user, monkeypatch):
    default = Tenant.objects.get(slug="default")
    _grant_view_database_permission(staff_user)
    _grant_manage_database_permission(staff_user)
    _jwt_login(client, username=staff_user.username, password="pass")

    _mock_ibcmd_command_catalog(
        monkeypatch,
        {
            "dummy_set_flags": ["extension_name", "active", "safe_mode", "unsafe_action_protection"],
        },
    )
    _seed_action_catalog_exposures(
        tenant=default,
        actions=[
            {
                "id": "SyncAction",
                "capability": "extensions.sync",
                "label": "Sync extensions",
                "contexts": ["bulk_page"],
                "executor": {
                    "kind": "ibcmd_cli",
                    "driver": "ibcmd",
                    "command_id": "dummy_sync_extensions",
                },
            },
            {
                "id": "SetFlagsAction",
                "capability": "extensions.set_flags",
                "label": "Set flags",
                "contexts": ["bulk_page"],
                "executor": {
                    "kind": "ibcmd_cli",
                    "driver": "ibcmd",
                    "command_id": "dummy_set_flags",
                    "params": {
                        "active": "$policy.active",
                        "safe_mode": "$policy.safe_mode",
                        "unsafe_action_protection": "$policy.unsafe_action_protection",
                    },
                    "target_binding": {"extension_name_param": "extension_name"},
                },
            },
        ],
    )

    db = Database.objects.create(
        tenant=default,
        name="db_set_flags",
        host="localhost",
        port=80,
        base_name="db_set_flags",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db,
        defaults={"snapshot": {"extensions": [{"name": "ExtA"}], "raw": {}, "parse_error": None}},
    )

    ExtensionFlagsPolicy.objects.create(
        tenant_id=str(default.id),
        extension_name="ExtA",
        active=True,
        safe_mode=None,
        unsafe_action_protection=None,
    )

    def _fake_preview(**kwargs):
        assert kwargs.get("command_id") == "dummy_set_flags"
        assert kwargs.get("params") == {
            "active": True,
            "safe_mode": None,
            "unsafe_action_protection": None,
            "extension_name": "ExtA",
        }
        assert kwargs.get("additional_args") == []
        return ({"execution_plan": {"plan_version": 1}, "bindings": []}, None, None)

    monkeypatch.setattr("apps.api_v2.views.extensions_plan_apply._preview_ibcmd_cli", _fake_preview)

    def _fake_execute(_request, validated_data, *, metadata_overrides=None, **_kwargs):
        assert validated_data.get("command_id") == "dummy_set_flags"
        assert metadata_overrides is not None
        assert metadata_overrides.get("action_capability") == "extensions.set_flags"
        assert metadata_overrides.get("post_completion_extensions_sync") is True
        assert metadata_overrides.get("post_completion_extensions_sync_executor", {}).get("command_id") == "dummy_sync_extensions"
        assert metadata_overrides.get("extension_name") == "ExtA"
        assert metadata_overrides.get("snapshot_kinds") is None
        return Response({"operation_id": "op-set-flags", "status": "queued"}, status=202)

    monkeypatch.setattr("apps.api_v2.views.extensions_plan_apply._execute_ibcmd_cli_validated", _fake_execute)

    plan_resp = client.post(
        "/api/v2/extensions/plan/",
        {"database_ids": [db.id], "capability": "extensions.set_flags", "extension_name": "ExtA"},
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(default.id),
    )
    assert plan_resp.status_code == 200
    plan_id = plan_resp.json()["plan_id"]

    apply_resp = client.post(
        "/api/v2/extensions/apply/",
        {"plan_id": plan_id, "strict": False},
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(default.id),
    )
    assert apply_resp.status_code == 202
    assert apply_resp.json()["operation_id"] == "op-set-flags"


@pytest.mark.django_db
def test_extensions_plan_set_flags_requires_action_id_when_ambiguous(client, staff_user):
    default = Tenant.objects.get(slug="default")
    _grant_view_database_permission(staff_user)
    _grant_manage_database_permission(staff_user)
    _jwt_login(client, username=staff_user.username, password="pass")

    db = Database.objects.create(
        tenant=default,
        name="db_set_flags_ambiguous",
        host="localhost",
        port=80,
        base_name="db_set_flags_ambiguous",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )

    _seed_action_catalog_exposures(
        tenant=default,
        actions=[
            {
                "id": "SetFlags1",
                "capability": "extensions.set_flags",
                "label": "Set flags 1",
                "contexts": ["bulk_page"],
                "executor": {
                    "kind": "ibcmd_cli",
                    "driver": "ibcmd",
                    "command_id": "dummy_set_flags",
                    "target_binding": {"extension_name_param": "extension_name"},
                },
            },
            {
                "id": "SetFlags2",
                "capability": "extensions.set_flags",
                "label": "Set flags 2",
                "contexts": ["bulk_page"],
                "executor": {
                    "kind": "ibcmd_cli",
                    "driver": "ibcmd",
                    "command_id": "dummy_set_flags",
                    "target_binding": {"extension_name_param": "extension_name"},
                },
            },
        ],
    )

    resp = client.post(
        "/api/v2/extensions/plan/",
        {"database_ids": [db.id], "capability": "extensions.set_flags", "extension_name": "ExtA"},
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(default.id),
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["error"]["code"] == "AMBIGUOUS_ACTION"
    assert "candidates" in payload["error"]


@pytest.mark.django_db
def test_extensions_plan_set_flags_uses_preset_apply_mask_when_request_missing(client, staff_user, monkeypatch):
    default = Tenant.objects.get(slug="default")
    _grant_view_database_permission(staff_user)
    _grant_manage_database_permission(staff_user)
    _jwt_login(client, username=staff_user.username, password="pass")

    _mock_ibcmd_command_catalog(
        monkeypatch,
        {
            "dummy_set_flags": ["extension_name", "active", "safe_mode", "unsafe_action_protection"],
        },
    )
    _seed_action_catalog_exposures(
        tenant=default,
        actions=[
            {
                "id": "SyncAction",
                "capability": "extensions.sync",
                "label": "Sync extensions",
                "contexts": ["bulk_page"],
                "executor": {
                    "kind": "ibcmd_cli",
                    "driver": "ibcmd",
                    "command_id": "dummy_sync_extensions",
                },
            },
            {
                "id": "SetFlagsActiveOnly",
                "capability": "extensions.set_flags",
                "label": "Set flags: active only",
                "contexts": ["bulk_page"],
                "executor": {
                    "kind": "ibcmd_cli",
                    "driver": "ibcmd",
                    "command_id": "dummy_set_flags",
                    "params": {
                        "active": "$policy.active",
                        "safe_mode": "$policy.safe_mode",
                        "unsafe_action_protection": "$policy.unsafe_action_protection",
                    },
                    "fixed": {
                        "apply_mask": {
                            "active": True,
                            "safe_mode": False,
                            "unsafe_action_protection": False,
                        }
                    },
                    "target_binding": {"extension_name_param": "extension_name"},
                },
            },
        ],
    )

    db = Database.objects.create(
        tenant=default,
        name="db_set_flags_preset_mask",
        host="localhost",
        port=80,
        base_name="db_set_flags_preset_mask",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db,
        defaults={"snapshot": {"extensions": [{"name": "ExtA"}], "raw": {}, "parse_error": None}},
    )

    ExtensionFlagsPolicy.objects.create(
        tenant_id=str(default.id),
        extension_name="ExtA",
        active=True,
        safe_mode=None,
        unsafe_action_protection=None,
    )

    def _fake_preview(**kwargs):
        assert kwargs.get("command_id") == "dummy_set_flags"
        assert kwargs.get("params") == {"active": True, "extension_name": "ExtA"}
        assert kwargs.get("additional_args") == []
        return ({"execution_plan": {"plan_version": 1}, "bindings": []}, None, None)

    monkeypatch.setattr("apps.api_v2.views.extensions_plan_apply._preview_ibcmd_cli", _fake_preview)

    def _fake_execute(_request, validated_data, *, metadata_overrides=None, **_kwargs):
        assert validated_data.get("command_id") == "dummy_set_flags"
        assert validated_data.get("params") == {"active": True, "extension_name": "ExtA"}
        assert metadata_overrides is not None
        assert metadata_overrides.get("action_capability") == "extensions.set_flags"
        return Response({"operation_id": "op-set-flags", "status": "queued"}, status=202)

    monkeypatch.setattr("apps.api_v2.views.extensions_plan_apply._execute_ibcmd_cli_validated", _fake_execute)

    plan_resp = client.post(
        "/api/v2/extensions/plan/",
        {
            "database_ids": [db.id],
            "action_id": "SetFlagsActiveOnly",
            "extension_name": "ExtA",
        },
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(default.id),
    )
    assert plan_resp.status_code == 200
    plan_id = plan_resp.json()["plan_id"]

    apply_resp = client.post(
        "/api/v2/extensions/apply/",
        {"plan_id": plan_id, "strict": False},
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(default.id),
    )
    assert apply_resp.status_code == 202
    assert apply_resp.json()["operation_id"] == "op-set-flags"


@pytest.mark.django_db
def test_extensions_plan_set_flags_rejects_apply_mask_all_false(client, staff_user):
    default = Tenant.objects.get(slug="default")
    _grant_view_database_permission(staff_user)
    _grant_manage_database_permission(staff_user)
    _jwt_login(client, username=staff_user.username, password="pass")

    db = Database.objects.create(
        tenant=default,
        name="db_set_flags_mask_all_false",
        host="localhost",
        port=80,
        base_name="db_set_flags_mask_all_false",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )

    _seed_action_catalog_exposures(
        tenant=default,
        actions=[
            {
                "id": "SetFlagsAction",
                "capability": "extensions.set_flags",
                "label": "Set flags",
                "contexts": ["bulk_page"],
                "executor": {
                    "kind": "ibcmd_cli",
                    "driver": "ibcmd",
                    "command_id": "dummy_set_flags",
                    "target_binding": {"extension_name_param": "extension_name"},
                },
            },
        ],
    )

    resp = client.post(
        "/api/v2/extensions/plan/",
        {
            "database_ids": [db.id],
            "capability": "extensions.set_flags",
            "extension_name": "ExtA",
            "apply_mask": {"active": False, "safe_mode": False, "unsafe_action_protection": False},
        },
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(default.id),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_extensions_plan_set_flags_selective_apply_fails_closed_when_additional_args_use_policy(client, staff_user, monkeypatch):
    default = Tenant.objects.get(slug="default")
    _grant_view_database_permission(staff_user)
    _grant_manage_database_permission(staff_user)
    _jwt_login(client, username=staff_user.username, password="pass")

    _mock_ibcmd_command_catalog(
        monkeypatch,
        {
            "dummy_set_flags": ["extension_name", "active", "safe_mode", "unsafe_action_protection"],
        },
    )
    _seed_action_catalog_exposures(
        tenant=default,
        actions=[
            {
                "id": "SetFlagsAction",
                "capability": "extensions.set_flags",
                "label": "Set flags",
                "contexts": ["bulk_page"],
                "executor": {
                    "kind": "ibcmd_cli",
                    "driver": "ibcmd",
                    "command_id": "dummy_set_flags",
                    "params": {
                        "active": "$policy.active",
                        "safe_mode": "$policy.safe_mode",
                        "unsafe_action_protection": "$policy.unsafe_action_protection",
                    },
                    "additional_args": ["--active", "$policy.active"],
                    "target_binding": {"extension_name_param": "extension_name"},
                },
            },
        ],
    )

    db = Database.objects.create(
        tenant=default,
        name="db_set_flags_selective_fail",
        host="localhost",
        port=80,
        base_name="db_set_flags_selective_fail",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db,
        defaults={"snapshot": {"extensions": [{"name": "ExtA"}], "raw": {}, "parse_error": None}},
    )
    ExtensionFlagsPolicy.objects.create(
        tenant_id=str(default.id),
        extension_name="ExtA",
        active=True,
        safe_mode=False,
        unsafe_action_protection=False,
    )

    monkeypatch.setattr(
        "apps.api_v2.views.extensions_plan_apply._preview_ibcmd_cli",
        lambda **_kwargs: ({"execution_plan": {"plan_version": 1}, "bindings": []}, None, None),
    )

    resp = client.post(
        "/api/v2/extensions/plan/",
        {
            "database_ids": [db.id],
            "capability": "extensions.set_flags",
            "extension_name": "ExtA",
            "apply_mask": {"active": True, "safe_mode": False, "unsafe_action_protection": False},
        },
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(default.id),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "CONFIGURATION_ERROR"


@pytest.mark.django_db
def test_extensions_plan_apply_set_flags_selective_apply_masks_params(client, staff_user, monkeypatch):
    default = Tenant.objects.get(slug="default")
    _grant_view_database_permission(staff_user)
    _grant_manage_database_permission(staff_user)
    _jwt_login(client, username=staff_user.username, password="pass")

    _mock_ibcmd_command_catalog(
        monkeypatch,
        {
            "dummy_set_flags": ["extension_name", "active", "safe_mode", "unsafe_action_protection"],
        },
    )
    _seed_action_catalog_exposures(
        tenant=default,
        actions=[
            {
                "id": "SyncAction",
                "capability": "extensions.sync",
                "label": "Sync extensions",
                "contexts": ["bulk_page"],
                "executor": {
                    "kind": "ibcmd_cli",
                    "driver": "ibcmd",
                    "command_id": "dummy_sync_extensions",
                },
            },
            {
                "id": "SetFlagsAction",
                "capability": "extensions.set_flags",
                "label": "Set flags",
                "contexts": ["bulk_page"],
                "executor": {
                    "kind": "ibcmd_cli",
                    "driver": "ibcmd",
                    "command_id": "dummy_set_flags",
                    "params": {
                        "active": "$policy.active",
                        "safe_mode": "$policy.safe_mode",
                        "unsafe_action_protection": "$policy.unsafe_action_protection",
                    },
                    "target_binding": {"extension_name_param": "extension_name"},
                },
            },
        ],
    )

    db = Database.objects.create(
        tenant=default,
        name="db_set_flags_selective_ok",
        host="localhost",
        port=80,
        base_name="db_set_flags_selective_ok",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db,
        defaults={"snapshot": {"extensions": [{"name": "ExtA"}], "raw": {}, "parse_error": None}},
    )
    ExtensionFlagsPolicy.objects.create(
        tenant_id=str(default.id),
        extension_name="ExtA",
        active=True,
        safe_mode=False,
        unsafe_action_protection=False,
    )

    def _fake_preview(**kwargs):
        assert kwargs.get("command_id") == "dummy_set_flags"
        assert kwargs.get("params") == {"extension_name": "ExtA", "active": True}
        assert kwargs.get("additional_args") == []
        return ({"execution_plan": {"plan_version": 1}, "bindings": []}, None, None)

    monkeypatch.setattr("apps.api_v2.views.extensions_plan_apply._preview_ibcmd_cli", _fake_preview)

    def _fake_execute(_request, validated_data, *, metadata_overrides=None, **_kwargs):
        assert validated_data.get("command_id") == "dummy_set_flags"
        assert validated_data.get("params") == {"extension_name": "ExtA", "active": True}
        assert metadata_overrides is not None
        assert metadata_overrides.get("action_capability") == "extensions.set_flags"
        assert metadata_overrides.get("post_completion_extensions_sync") is True
        return Response({"operation_id": "op-set-flags-selective", "status": "queued"}, status=202)

    monkeypatch.setattr("apps.api_v2.views.extensions_plan_apply._execute_ibcmd_cli_validated", _fake_execute)

    plan_resp = client.post(
        "/api/v2/extensions/plan/",
        {
            "database_ids": [db.id],
            "capability": "extensions.set_flags",
            "extension_name": "ExtA",
            "apply_mask": {"active": True, "safe_mode": False, "unsafe_action_protection": False},
        },
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(default.id),
    )
    assert plan_resp.status_code == 200
    plan_id = plan_resp.json()["plan_id"]

    apply_resp = client.post(
        "/api/v2/extensions/apply/",
        {"plan_id": plan_id, "strict": False},
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(default.id),
    )
    assert apply_resp.status_code == 202
    assert apply_resp.json()["operation_id"] == "op-set-flags-selective"


@pytest.mark.django_db
def test_extensions_plan_set_flags_requires_manage_database_permission(client, user):
    default = Tenant.objects.get(slug="default")
    _grant_view_database_permission(user)
    _jwt_login(client, username=user.username, password="pass")

    db = Database.objects.create(
        tenant=default,
        name="db_no_manage",
        host="localhost",
        port=80,
        base_name="db_no_manage",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db,
        defaults={"snapshot": {"extensions": [{"name": "ExtA"}], "raw": {}, "parse_error": None}},
    )

    resp = client.post(
        "/api/v2/extensions/plan/",
        {"database_ids": [db.id], "capability": "extensions.set_flags", "extension_name": "ExtA"},
        format="json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_extensions_plan_set_flags_staff_requires_explicit_tenant_header(client, staff_user):
    default = Tenant.objects.get(slug="default")
    _grant_view_database_permission(staff_user)
    _grant_manage_database_permission(staff_user)
    _jwt_login(client, username=staff_user.username, password="pass")

    db = Database.objects.create(
        tenant=default,
        name="db_no_tenant_header",
        host="localhost",
        port=80,
        base_name="db_no_tenant_header",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db,
        defaults={"snapshot": {"extensions": [{"name": "ExtA"}], "raw": {}, "parse_error": None}},
    )
    ExtensionFlagsPolicy.objects.create(
        tenant_id=str(default.id),
        extension_name="ExtA",
        active=True,
        safe_mode=None,
        unsafe_action_protection=None,
    )
    _seed_action_catalog_exposures(
        tenant=default,
        actions=[
            {
                "id": "SetFlagsAction",
                "capability": "extensions.set_flags",
                "label": "Set flags",
                "contexts": ["bulk_page"],
                "executor": {
                    "kind": "ibcmd_cli",
                    "driver": "ibcmd",
                    "command_id": "dummy_set_flags",
                    "target_binding": {"extension_name_param": "extension_name"},
                },
            },
        ],
    )

    resp = client.post(
        "/api/v2/extensions/plan/",
        {"database_ids": [db.id], "capability": "extensions.set_flags", "extension_name": "ExtA"},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "TENANT_CONTEXT_REQUIRED"


@pytest.mark.django_db
def test_extensions_apply_set_flags_fails_closed_without_extensions_sync_configured(client, staff_user, monkeypatch):
    default = Tenant.objects.get(slug="default")
    _grant_view_database_permission(staff_user)
    _grant_manage_database_permission(staff_user)
    _jwt_login(client, username=staff_user.username, password="pass")

    _mock_ibcmd_command_catalog(
        monkeypatch,
        {
            "dummy_set_flags": ["extension_name", "active", "safe_mode", "unsafe_action_protection"],
        },
    )
    _seed_action_catalog_exposures(
        tenant=default,
        actions=[
            {
                "id": "SetFlagsAction",
                "capability": "extensions.set_flags",
                "label": "Set flags",
                "contexts": ["bulk_page"],
                "executor": {
                    "kind": "ibcmd_cli",
                    "driver": "ibcmd",
                    "command_id": "dummy_set_flags",
                    "target_binding": {"extension_name_param": "extension_name"},
                },
            },
        ],
    )

    db = Database.objects.create(
        tenant=default,
        name="db_set_flags_no_sync",
        host="localhost",
        port=80,
        base_name="db_set_flags_no_sync",
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db,
        defaults={"snapshot": {"extensions": [{"name": "ExtA"}], "raw": {}, "parse_error": None}},
    )
    ExtensionFlagsPolicy.objects.create(
        tenant_id=str(default.id),
        extension_name="ExtA",
        active=True,
        safe_mode=None,
        unsafe_action_protection=None,
    )

    monkeypatch.setattr(
        "apps.api_v2.views.extensions_plan_apply._preview_ibcmd_cli",
        lambda **_kwargs: ({"execution_plan": {"plan_version": 1}, "bindings": []}, None, None),
    )

    plan_resp = client.post(
        "/api/v2/extensions/plan/",
        {"database_ids": [db.id], "capability": "extensions.set_flags", "extension_name": "ExtA"},
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(default.id),
    )
    assert plan_resp.status_code == 200
    plan_id = plan_resp.json()["plan_id"]

    apply_resp = client.post(
        "/api/v2/extensions/apply/",
        {"plan_id": plan_id, "strict": False},
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(default.id),
    )
    assert apply_resp.status_code == 400
    assert apply_resp.json()["error"]["code"] == "MISSING_ACTION"


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
