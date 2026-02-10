from __future__ import annotations

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.databases.models import Database, DatabaseExtensionsSnapshot
from apps.mappings.models import TenantMappingSpec
from apps.operations.models import ExtensionsPlan
from apps.templates.models import ManualOperationTemplateBinding, OperationExposure
from apps.templates.operation_catalog_service import resolve_definition, resolve_exposure
from apps.tenancy.models import Tenant, TenantMember


def _jwt_login(client: APIClient, *, username: str, password: str) -> None:
    resp = client.post("/api/token/", {"username": username, "password": password}, format="json")
    assert resp.status_code == 200
    access = resp.json()["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")


def _grant_database_permission(user: User, codename: str) -> None:
    ct = ContentType.objects.get(app_label="databases", model="database")
    perm = Permission.objects.get(content_type=ct, codename=codename)
    user.user_permissions.add(perm)


def _create_database_with_snapshot(*, tenant: Tenant, name: str) -> Database:
    db = Database.objects.create(
        tenant=tenant,
        name=name,
        host="localhost",
        port=80,
        base_name=name,
        odata_url="http://localhost/odata",
        username="u",
        password="p",
    )
    DatabaseExtensionsSnapshot.objects.update_or_create(
        database=db,
        defaults={"snapshot": {"extensions": [{"name": "ExtA"}], "raw": {}, "parse_error": None}},
    )
    return db


def _create_manual_template(
    *,
    template_id: str,
    capability: str,
    command_id: str = "dummy_command",
    params: dict | None = None,
    target_binding: dict | None = None,
    additional_args: list[str] | None = None,
) -> OperationExposure:
    template_data: dict = {}
    if isinstance(target_binding, dict):
        template_data["target_binding"] = dict(target_binding)

    definition_payload: dict = {
        "kind": "ibcmd_cli",
        "driver": "ibcmd",
        "operation_type": "ibcmd_cli",
        "target_entity": "infobase",
        "command_id": command_id,
        "mode": "guided",
        "params": dict(params or {}),
        "template_data": template_data,
    }
    if isinstance(additional_args, list):
        definition_payload["additional_args"] = list(additional_args)

    definition, _ = resolve_definition(
        tenant_scope="global",
        executor_kind="ibcmd_cli",
        executor_payload=definition_payload,
        contract_version=1,
    )
    exposure, _ = resolve_exposure(
        definition=definition,
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias=template_id,
        tenant_id=None,
        label=template_id,
        description="",
        is_active=True,
        capability=capability,
        contexts=[],
        display_order=0,
        capability_config={},
        status=OperationExposure.STATUS_PUBLISHED,
    )
    return exposure


def _create_set_flags_template(*, template_id: str, command_id: str = "dummy_set_flags") -> OperationExposure:
    return _create_manual_template(
        template_id=template_id,
        capability="extensions.set_flags",
        command_id=command_id,
        params={
            "active": "$flags.active",
            "safe_mode": "$flags.safe_mode",
            "unsafe_action_protection": "$flags.unsafe_action_protection",
        },
        target_binding={"extension_name_param": "extension_name"},
    )


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def default_tenant():
    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    return tenant


@pytest.fixture
def staff_user(default_tenant):
    user = User.objects.create_user(username="staff", password="pass", is_staff=True)
    TenantMember.objects.get_or_create(
        tenant=default_tenant,
        user=user,
        defaults={"role": TenantMember.ROLE_ADMIN},
    )
    return user


@pytest.fixture
def user(default_tenant):
    usr = User.objects.create_user(username="user", password="pass")
    TenantMember.objects.get_or_create(
        tenant=default_tenant,
        user=usr,
        defaults={"role": TenantMember.ROLE_MEMBER},
    )
    return usr


@pytest.fixture
def preview_ok(monkeypatch):
    monkeypatch.setattr(
        "apps.api_v2.views.extensions_plan_apply._preview_ibcmd_cli",
        lambda **_kwargs: ({"execution_plan": {"plan_version": 1}, "bindings": []}, None, None),
    )


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
def test_service_user_without_membership_can_use_default_tenant(client, default_tenant):
    from apps.core.authentication import ServiceUser
    from apps.tenancy.authentication import _resolve_tenant_for_user

    svc = ServiceUser("svc")
    resolved = _resolve_tenant_for_user(svc, header_tenant_id=None)
    assert str(resolved.id) == str(default_tenant.id)


@pytest.mark.django_db
def test_extensions_apply_rejects_legacy_plan_contract(client, staff_user, default_tenant):
    _grant_database_permission(staff_user, "view_database")
    _jwt_login(client, username=staff_user.username, password="pass")

    plan = ExtensionsPlan.objects.create(
        tenant=default_tenant,
        database_ids=[],
        preconditions={},
        executor={
            "execution_source": "action_catalog",
            "action_id": "legacy.action",
            "capability": "extensions.sync",
        },
    )

    resp = client.post("/api/v2/extensions/apply/", {"plan_id": str(plan.id)}, format="json")
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["error"]["code"] == "PLAN_INVALID_LEGACY"


@pytest.mark.django_db
def test_extensions_plan_uses_preferred_binding_when_no_override(client, staff_user, default_tenant, preview_ok):
    _grant_database_permission(staff_user, "view_database")
    _jwt_login(client, username=staff_user.username, password="pass")
    db = _create_database_with_snapshot(tenant=default_tenant, name="db-sync-binding")

    exposure = _create_manual_template(template_id="tpl-sync-default", capability="extensions.sync")
    ManualOperationTemplateBinding.objects.create(
        tenant=default_tenant,
        manual_operation="extensions.sync",
        template_id=exposure.alias,
        updated_by=staff_user,
    )

    resp = client.post(
        "/api/v2/extensions/plan/",
        {"database_ids": [str(db.id)], "manual_operation": "extensions.sync"},
        format="json",
    )
    assert resp.status_code == 200
    plan = ExtensionsPlan.objects.get(id=resp.json()["plan_id"])
    assert plan.executor["template_id"] == "tpl-sync-default"


@pytest.mark.django_db
def test_extensions_plan_template_override_takes_precedence_over_binding(client, staff_user, default_tenant, preview_ok):
    _grant_database_permission(staff_user, "view_database")
    _jwt_login(client, username=staff_user.username, password="pass")
    db = _create_database_with_snapshot(tenant=default_tenant, name="db-sync-override")

    _create_manual_template(template_id="tpl-sync-binding", capability="extensions.sync")
    override = _create_manual_template(template_id="tpl-sync-override", capability="extensions.sync")
    ManualOperationTemplateBinding.objects.create(
        tenant=default_tenant,
        manual_operation="extensions.sync",
        template_id="tpl-sync-binding",
        updated_by=staff_user,
    )

    resp = client.post(
        "/api/v2/extensions/plan/",
        {
            "database_ids": [str(db.id)],
            "manual_operation": "extensions.sync",
            "template_id": override.alias,
        },
        format="json",
    )
    assert resp.status_code == 200
    plan = ExtensionsPlan.objects.get(id=resp.json()["plan_id"])
    assert plan.executor["template_id"] == "tpl-sync-override"


@pytest.mark.django_db
def test_extensions_plan_rejects_incompatible_template_override(client, staff_user, default_tenant, preview_ok):
    _grant_database_permission(staff_user, "view_database")
    _grant_database_permission(staff_user, "manage_database")
    _jwt_login(client, username=staff_user.username, password="pass")
    db = _create_database_with_snapshot(tenant=default_tenant, name="db-incompatible-override")

    _create_manual_template(template_id="tpl-sync-only", capability="extensions.sync")

    resp = client.post(
        "/api/v2/extensions/plan/",
        {
            "database_ids": [str(db.id)],
            "manual_operation": "extensions.set_flags",
            "template_id": "tpl-sync-only",
        },
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(default_tenant.id),
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["error"]["code"] == "CONFIGURATION_ERROR"
    assert "not compatible" in payload["error"]["message"]


@pytest.mark.django_db
def test_manual_operation_binding_endpoint_rejects_incompatible_template(client, staff_user, default_tenant):
    _grant_database_permission(staff_user, "manage_database")
    _jwt_login(client, username=staff_user.username, password="pass")
    _create_manual_template(template_id="tpl-sync-only", capability="extensions.sync")

    resp = client.put(
        "/api/v2/extensions/manual-operation-bindings/extensions.set_flags/",
        {"template_id": "tpl-sync-only"},
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(default_tenant.id),
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["error"]["code"] == "CONFIGURATION_ERROR"


@pytest.mark.django_db
def test_extensions_plan_returns_missing_binding_when_template_deleted(client, staff_user, default_tenant, preview_ok):
    _grant_database_permission(staff_user, "view_database")
    _jwt_login(client, username=staff_user.username, password="pass")
    db = _create_database_with_snapshot(tenant=default_tenant, name="db-stale-delete")

    exposure = _create_manual_template(template_id="tpl-sync-to-delete", capability="extensions.sync")
    ManualOperationTemplateBinding.objects.create(
        tenant=default_tenant,
        manual_operation="extensions.sync",
        template_id=exposure.alias,
        updated_by=staff_user,
    )
    OperationExposure.objects.filter(surface=OperationExposure.SURFACE_TEMPLATE, alias=exposure.alias).delete()

    resp = client.post(
        "/api/v2/extensions/plan/",
        {"database_ids": [str(db.id)], "manual_operation": "extensions.sync"},
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["error"]["code"] == "MISSING_TEMPLATE_BINDING"
    assert "missing template" in payload["error"]["message"]


@pytest.mark.django_db
def test_extensions_plan_returns_missing_binding_when_alias_becomes_stale(client, staff_user, default_tenant, preview_ok):
    _grant_database_permission(staff_user, "view_database")
    _jwt_login(client, username=staff_user.username, password="pass")
    db = _create_database_with_snapshot(tenant=default_tenant, name="db-stale-capability")

    exposure = _create_manual_template(template_id="tpl-sync-stale", capability="extensions.sync")
    ManualOperationTemplateBinding.objects.create(
        tenant=default_tenant,
        manual_operation="extensions.sync",
        template_id=exposure.alias,
        updated_by=staff_user,
    )
    exposure.capability = "extensions.set_flags"
    exposure.save(update_fields=["capability", "updated_at"])

    resp = client.post(
        "/api/v2/extensions/plan/",
        {"database_ids": [str(db.id)], "manual_operation": "extensions.sync"},
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["error"]["code"] == "MISSING_TEMPLATE_BINDING"
    assert "stale" in payload["error"]["message"]


@pytest.mark.django_db
def test_extensions_plan_pins_result_contract_and_mapping_spec_ref(client, staff_user, default_tenant, preview_ok):
    _grant_database_permission(staff_user, "view_database")
    _jwt_login(client, username=staff_user.username, password="pass")
    db = _create_database_with_snapshot(tenant=default_tenant, name="db-pin-mapping")

    _create_manual_template(template_id="tpl-sync-pinned", capability="extensions.sync")
    ManualOperationTemplateBinding.objects.create(
        tenant=default_tenant,
        manual_operation="extensions.sync",
        template_id="tpl-sync-pinned",
        updated_by=staff_user,
    )
    mapping = TenantMappingSpec.objects.create(
        tenant=default_tenant,
        entity_kind=TenantMappingSpec.ENTITY_EXTENSIONS_INVENTORY,
        status=TenantMappingSpec.STATUS_PUBLISHED,
        spec={"version": 1},
    )

    resp = client.post(
        "/api/v2/extensions/plan/",
        {"database_ids": [str(db.id)], "manual_operation": "extensions.sync"},
        format="json",
    )
    assert resp.status_code == 200
    plan = ExtensionsPlan.objects.get(id=resp.json()["plan_id"])

    assert plan.executor["result_contract"] == "extensions.inventory.v1"
    mapping_ref = plan.executor["mapping_spec_ref"]
    assert mapping_ref["mapping_spec_id"] == str(mapping.id)
    assert mapping_ref["entity_kind"] == TenantMappingSpec.ENTITY_EXTENSIONS_INVENTORY
    assert isinstance(mapping_ref["mapping_spec_version"], str) and mapping_ref["mapping_spec_version"]


@pytest.mark.django_db
def test_extensions_apply_uses_pinned_metadata_from_plan(client, staff_user, default_tenant, preview_ok, monkeypatch):
    _grant_database_permission(staff_user, "view_database")
    _jwt_login(client, username=staff_user.username, password="pass")
    db = _create_database_with_snapshot(tenant=default_tenant, name="db-apply-pinned")

    _create_manual_template(template_id="tpl-sync-apply", capability="extensions.sync")
    ManualOperationTemplateBinding.objects.create(
        tenant=default_tenant,
        manual_operation="extensions.sync",
        template_id="tpl-sync-apply",
        updated_by=staff_user,
    )
    mapping = TenantMappingSpec.objects.create(
        tenant=default_tenant,
        entity_kind=TenantMappingSpec.ENTITY_EXTENSIONS_INVENTORY,
        status=TenantMappingSpec.STATUS_PUBLISHED,
        spec={"version": 1},
    )

    plan_resp = client.post(
        "/api/v2/extensions/plan/",
        {"database_ids": [str(db.id)], "manual_operation": "extensions.sync"},
        format="json",
    )
    assert plan_resp.status_code == 200
    plan = ExtensionsPlan.objects.get(id=plan_resp.json()["plan_id"])
    pinned_ref = dict(plan.executor.get("mapping_spec_ref") or {})

    mapping.spec = {"version": 2}
    mapping.save(update_fields=["spec", "updated_at"])
    mapping.refresh_from_db()
    assert mapping.updated_at.isoformat() != pinned_ref.get("mapping_spec_version")

    def _fake_execute(_request, validated_data, *, metadata_overrides=None, **_kwargs):
        assert validated_data.get("command_id") == "dummy_command"
        assert metadata_overrides is not None
        assert metadata_overrides.get("manual_operation") == "extensions.sync"
        assert metadata_overrides.get("result_contract") == "extensions.inventory.v1"
        assert metadata_overrides.get("mapping_spec_ref") == pinned_ref
        assert metadata_overrides.get("snapshot_kinds") == ["extensions"]
        assert metadata_overrides.get("snapshot_source") == "extensions_plan_apply"
        return Response({"operation_id": "op-sync", "status": "queued"}, status=202)

    monkeypatch.setattr("apps.api_v2.views.extensions_plan_apply._execute_ibcmd_cli_validated", _fake_execute)

    apply_resp = client.post("/api/v2/extensions/apply/", {"plan_id": str(plan.id)}, format="json")
    assert apply_resp.status_code == 202
    assert apply_resp.json()["operation_id"] == "op-sync"


@pytest.mark.django_db
def test_extensions_plan_set_flags_requires_explicit_tenant_header_for_staff(client, staff_user, default_tenant, preview_ok):
    _grant_database_permission(staff_user, "view_database")
    _grant_database_permission(staff_user, "manage_database")
    _jwt_login(client, username=staff_user.username, password="pass")
    db = _create_database_with_snapshot(tenant=default_tenant, name="db-set-flags-tenant")

    _create_set_flags_template(template_id="tpl-set-flags")
    ManualOperationTemplateBinding.objects.create(
        tenant=default_tenant,
        manual_operation="extensions.set_flags",
        template_id="tpl-set-flags",
        updated_by=staff_user,
    )

    resp = client.post(
        "/api/v2/extensions/plan/",
        {
            "database_ids": [str(db.id)],
            "manual_operation": "extensions.set_flags",
            "extension_name": "ExtA",
            "flags_values": {"active": True, "safe_mode": False, "unsafe_action_protection": True},
            "apply_mask": {"active": True, "safe_mode": False, "unsafe_action_protection": False},
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["error"]["code"] == "TENANT_CONTEXT_REQUIRED"
