from __future__ import annotations

import json

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.databases.models import PermissionLevel
from apps.runtime_settings.models import TenantRuntimeSettingOverride
from apps.tenancy.models import Tenant
from apps.templates.models import OperationMigrationIssue, OperationTemplate, OperationTemplatePermission
from apps.templates.operation_catalog_service import upsert_template_exposure


@pytest.fixture
def staff_client(db):
    user = User.objects.create_user(username="operation_catalog_staff", password="pass")
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _grant_template_capability(user: User, codename: str) -> None:
    ct = ContentType.objects.get(app_label="templates", model="operationtemplate")
    perm = Permission.objects.get(content_type=ct, codename=codename)
    user.user_permissions.add(perm)


def _create_action_exposure(
    client: APIClient,
    *,
    alias: str,
    name: str,
    capability: str,
    status: str = "draft",
    command_id: str = "infobase.extension.list",
    definition_id: str | None = None,
) -> dict:
    payload: dict = {
        "exposure": {
            "surface": "action_catalog",
            "alias": alias,
            "name": name,
            "description": "",
            "is_active": True,
            "capability": capability,
            "contexts": ["database_card"],
            "display_order": 0,
            "capability_config": {},
            "status": status,
        }
    }
    if definition_id:
        payload["definition_id"] = definition_id
    else:
        payload["definition"] = {
            "tenant_scope": "global",
            "executor_kind": "ibcmd_cli",
            "executor_payload": {
                "kind": "ibcmd_cli",
                "driver": "ibcmd",
                "command_id": command_id,
                "params": {},
            },
            "contract_version": 1,
        }

    resp = client.post("/api/v2/operation-catalog/exposures/", data=payload, format="json")
    assert resp.status_code == 200
    return resp.json()


@pytest.fixture
def template_manager_client(db):
    user = User.objects.create_user(username="template_manager_non_staff", password="pass", is_staff=False)
    _grant_template_capability(user, "view_operationtemplate")
    _grant_template_capability(user, "manage_operation_template")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_ui_action_catalog_runtime_setting_is_removed(staff_client):
    payload = {
        "value": {
            "catalog_version": 1,
            "extensions": {"actions": []},
        }
    }

    resp_global = staff_client.patch("/api/v2/settings/runtime/ui.action_catalog/", data=payload, format="json")
    assert resp_global.status_code == 404
    assert resp_global.json()["error"]["code"] == "NOT_FOUND"

    tenant = Tenant.objects.create(slug="tenant-cutover", name="Tenant Cutover")
    resp_override = staff_client.patch(
        "/api/v2/settings/runtime-overrides/ui.action_catalog/",
        data=payload,
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )
    assert resp_override.status_code == 404
    assert resp_override.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.django_db
def test_runtime_overrides_list_excludes_decommissioned_keys(staff_client):
    tenant = Tenant.objects.create(slug="tenant-runtime-overrides", name="Tenant Runtime Overrides")

    TenantRuntimeSettingOverride.objects.update_or_create(
        tenant=tenant,
        key="ui.operations.max_live_streams",
        defaults={
            "status": TenantRuntimeSettingOverride.STATUS_PUBLISHED,
            "value": 17,
        },
    )
    TenantRuntimeSettingOverride.objects.update_or_create(
        tenant=tenant,
        key="ui.action_catalog",
        defaults={
            "status": TenantRuntimeSettingOverride.STATUS_PUBLISHED,
            "value": {"catalog_version": 1, "extensions": {"actions": []}},
        },
    )

    resp = staff_client.get(
        "/api/v2/settings/runtime-overrides/",
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    payload = resp.json()
    keys = [row["key"] for row in payload]
    assert "ui.operations.max_live_streams" in keys
    assert "ui.action_catalog" not in keys


@pytest.mark.django_db
def test_operation_catalog_endpoints_upsert_list_publish_validate(staff_client):
    upsert_resp = staff_client.post(
        "/api/v2/operation-catalog/exposures/",
        data={
            "definition": {
                "tenant_scope": "global",
                "executor_kind": "ibcmd_cli",
                "executor_payload": {
                    "kind": "ibcmd_cli",
                    "driver": "ibcmd",
                    "command_id": "infobase.extension.list",
                    "params": {},
                },
                "contract_version": 1,
            },
            "exposure": {
                "surface": "action_catalog",
                "alias": "extensions.list.test",
                "name": "List extensions",
                "description": "",
                "is_active": True,
                "capability": "extensions.list",
                "contexts": ["database_card"],
                "display_order": 0,
                "capability_config": {},
                "status": "draft",
            },
        },
        format="json",
    )
    assert upsert_resp.status_code == 200
    upsert_payload = upsert_resp.json()
    exposure_id = upsert_payload["exposure"]["id"]
    definition_id = upsert_payload["definition"]["id"]

    list_resp = staff_client.get("/api/v2/operation-catalog/exposures/", data={"surface": "action_catalog"})
    assert list_resp.status_code == 200
    assert any(item["alias"] == "extensions.list.test" for item in list_resp.json()["exposures"])

    publish_resp = staff_client.post(f"/api/v2/operation-catalog/exposures/{exposure_id}/publish/", data={}, format="json")
    assert publish_resp.status_code == 200
    publish_payload = publish_resp.json()
    assert publish_payload["published"] is True
    assert publish_payload["exposure"]["status"] == "published"
    assert publish_payload["validation_errors"] == []

    defs_resp = staff_client.get("/api/v2/operation-catalog/definitions/")
    assert defs_resp.status_code == 200
    assert any(item["id"] == definition_id for item in defs_resp.json()["definitions"])

    def_detail_resp = staff_client.get(f"/api/v2/operation-catalog/definitions/{definition_id}/")
    assert def_detail_resp.status_code == 200
    assert def_detail_resp.json()["definition"]["id"] == definition_id

    validate_resp = staff_client.post(
        "/api/v2/operation-catalog/validate/",
        data={
            "definition": {
                "tenant_scope": "global",
                "executor_kind": "ibcmd_cli",
                "executor_payload": {
                    "kind": "ibcmd_cli",
                    "driver": "ibcmd",
                    "command_id": "infobase.extension.update",
                    "params": {},
                },
                "contract_version": 1,
            },
            "exposure": {
                "surface": "action_catalog",
                "alias": "extensions.set_flags.bad",
                "name": "Set flags",
                "capability": "extensions.set_flags",
                "capability_config": {},
            },
        },
        format="json",
    )
    assert validate_resp.status_code == 200
    validate_payload = validate_resp.json()
    assert validate_payload["valid"] is False
    assert validate_payload["errors"]


@pytest.mark.django_db
def test_operation_catalog_upsert_rejects_kind_driver_mismatch(staff_client):
    resp = staff_client.post(
        "/api/v2/operation-catalog/exposures/",
        data={
            "definition": {
                "tenant_scope": "global",
                "executor_kind": "ibcmd_cli",
                "executor_payload": {
                    "kind": "ibcmd_cli",
                    "driver": "cli",
                    "command_id": "infobase.extension.list",
                },
                "contract_version": 1,
            },
            "exposure": {
                "surface": "action_catalog",
                "alias": "extensions.list.mismatch",
                "name": "List extensions",
                "description": "",
                "is_active": True,
                "capability": "extensions.list",
                "contexts": ["database_card"],
                "display_order": 0,
                "capability_config": {},
                "status": "draft",
            },
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert any(item["code"] == "DRIVER_KIND_MISMATCH" for item in payload["error"]["message"])


@pytest.mark.django_db
def test_operation_catalog_dedup_ignores_redundant_driver(staff_client):
    first_resp = staff_client.post(
        "/api/v2/operation-catalog/exposures/",
        data={
            "definition": {
                "tenant_scope": "global",
                "executor_kind": "ibcmd_cli",
                "executor_payload": {
                    "kind": "ibcmd_cli",
                    "driver": "ibcmd",
                    "command_id": "infobase.extension.list",
                    "params": {},
                },
                "contract_version": 1,
            },
            "exposure": {
                "surface": "action_catalog",
                "alias": "extensions.list.with-driver",
                "name": "List with driver",
                "description": "",
                "is_active": True,
                "capability": "extensions.list",
                "contexts": ["database_card"],
                "display_order": 0,
                "capability_config": {},
                "status": "draft",
            },
        },
        format="json",
    )
    assert first_resp.status_code == 200
    first_definition_id = first_resp.json()["definition"]["id"]

    second_resp = staff_client.post(
        "/api/v2/operation-catalog/exposures/",
        data={
            "definition": {
                "tenant_scope": "global",
                "executor_kind": "ibcmd_cli",
                "executor_payload": {
                    "kind": "ibcmd_cli",
                    "command_id": "infobase.extension.list",
                    "params": {},
                },
                "contract_version": 1,
            },
            "exposure": {
                "surface": "action_catalog",
                "alias": "extensions.list.no-driver",
                "name": "List no driver",
                "description": "",
                "is_active": True,
                "capability": "extensions.list",
                "contexts": ["database_card"],
                "display_order": 1,
                "capability_config": {},
                "status": "draft",
            },
        },
        format="json",
    )
    assert second_resp.status_code == 200
    second_definition_id = second_resp.json()["definition"]["id"]
    assert second_definition_id == first_definition_id


@pytest.mark.django_db
def test_operation_catalog_template_surface_allows_non_staff_with_view_scope(template_manager_client):
    user = User.objects.get(username="template_manager_non_staff")
    exposure, _ = upsert_template_exposure(
        template_id="tpl-perm-view",
        name="Template view",
        description="",
        operation_type="designer_cli",
        target_entity="infobase",
        template_data={"kind": "designer_cli", "driver": "cli", "command_id": "infobase.extension.list"},
        is_active=True,
    )
    template = OperationTemplate.objects.get(id=exposure.alias)
    OperationTemplatePermission.objects.update_or_create(
        user=user,
        template=template,
        defaults={"level": PermissionLevel.VIEW, "notes": ""},
    )

    resp_template = template_manager_client.get("/api/v2/operation-catalog/exposures/?surface=template")
    assert resp_template.status_code == 200
    aliases = {row["alias"] for row in resp_template.json()["exposures"]}
    assert "tpl-perm-view" in aliases

    resp_action = template_manager_client.get("/api/v2/operation-catalog/exposures/?surface=action_catalog")
    assert resp_action.status_code == 403

    resp_unified = template_manager_client.get("/api/v2/operation-catalog/exposures/")
    assert resp_unified.status_code == 403

    resp_all = template_manager_client.get("/api/v2/operation-catalog/exposures/?surface=all")
    assert resp_all.status_code == 403


@pytest.mark.django_db
def test_operation_catalog_exposures_staff_unified_list_no_surface_and_all_alias(staff_client):
    upsert_template_exposure(
        template_id="tpl-unified",
        name="Template unified",
        description="",
        operation_type="designer_cli",
        target_entity="infobase",
        template_data={"kind": "designer_cli", "driver": "cli", "command_id": "infobase.extension.list"},
        is_active=True,
    )
    _create_action_exposure(
        staff_client,
        alias="extensions.unified",
        name="Unified action",
        capability="extensions.list",
    )

    resp_no_surface = staff_client.get("/api/v2/operation-catalog/exposures/")
    assert resp_no_surface.status_code == 200
    payload_no_surface = resp_no_surface.json()
    rows_no_surface = {(row["surface"], row["alias"]) for row in payload_no_surface["exposures"]}
    assert ("template", "tpl-unified") in rows_no_surface
    assert ("action_catalog", "extensions.unified") in rows_no_surface

    resp_all = staff_client.get("/api/v2/operation-catalog/exposures/?surface=all")
    assert resp_all.status_code == 200
    payload_all = resp_all.json()
    rows_all = {(row["surface"], row["alias"]) for row in payload_all["exposures"]}
    assert rows_all == rows_no_surface
    assert payload_all["total"] == payload_no_surface["total"]


@pytest.mark.django_db
def test_operation_catalog_exposures_include_definitions_side_loading_is_unique(staff_client):
    first = _create_action_exposure(
        staff_client,
        alias="extensions.def.one",
        name="Def one",
        capability="extensions.list",
    )
    definition_id = first["definition"]["id"]
    _create_action_exposure(
        staff_client,
        alias="extensions.def.two",
        name="Def two",
        capability="extensions.sync",
        definition_id=definition_id,
    )

    resp = staff_client.get(
        "/api/v2/operation-catalog/exposures/",
        data={"surface": "action_catalog", "include": "definitions", "limit": 50, "offset": 0},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 2
    assert payload["total"] == 2
    assert len(payload.get("definitions", [])) == 1
    assert payload["definitions"][0]["id"] == definition_id
    assert all("definition" not in row for row in payload["exposures"])


@pytest.mark.django_db
def test_operation_catalog_exposures_supports_search_filters_sort_and_pagination(staff_client):
    _create_action_exposure(
        staff_client,
        alias="extensions.alpha",
        name="Alpha Action",
        capability="extensions.list",
        status="published",
    )
    _create_action_exposure(
        staff_client,
        alias="extensions.zulu",
        name="Zulu Action",
        capability="extensions.sync",
        status="draft",
    )
    upsert_template_exposure(
        template_id="tpl-filtered",
        name="Template filtered",
        description="",
        operation_type="designer_cli",
        target_entity="infobase",
        template_data={"kind": "designer_cli", "driver": "cli", "command_id": "infobase.extension.list"},
        is_active=True,
    )

    sorted_resp = staff_client.get(
        "/api/v2/operation-catalog/exposures/",
        data={
            "surface": "action_catalog",
            "search": "Action",
            "sort": json.dumps({"key": "name", "order": "asc"}),
            "limit": 1,
            "offset": 0,
        },
    )
    assert sorted_resp.status_code == 200
    sorted_payload = sorted_resp.json()
    assert sorted_payload["count"] == 1
    assert sorted_payload["total"] == 2
    assert sorted_payload["exposures"][0]["name"] == "Alpha Action"

    filtered_resp = staff_client.get(
        "/api/v2/operation-catalog/exposures/",
        data={
            "surface": "action_catalog",
            "filters": json.dumps({"capability": {"op": "contains", "value": "sync"}}),
        },
    )
    assert filtered_resp.status_code == 200
    filtered_payload = filtered_resp.json()
    assert filtered_payload["total"] == 1
    assert filtered_payload["exposures"][0]["alias"] == "extensions.zulu"

    template_filtered_resp = staff_client.get(
        "/api/v2/operation-catalog/exposures/",
        data={
            "surface": "template",
            "filters": json.dumps({"operation_type": {"op": "contains", "value": "designer"}}),
        },
    )
    assert template_filtered_resp.status_code == 200
    template_payload = template_filtered_resp.json()
    aliases = {row["alias"] for row in template_payload["exposures"]}
    assert "tpl-filtered" in aliases


@pytest.mark.django_db
def test_operation_catalog_exposures_backward_compatible_without_new_params(staff_client):
    _create_action_exposure(
        staff_client,
        alias="extensions.compat",
        name="Compat action",
        capability="extensions.list",
    )

    resp = staff_client.get(
        "/api/v2/operation-catalog/exposures/",
        data={"surface": "action_catalog", "limit": 50, "offset": 0},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert "exposures" in payload
    assert "count" in payload
    assert "total" in payload
    assert "definitions" not in payload
    assert any(row["alias"] == "extensions.compat" for row in payload["exposures"])


@pytest.mark.django_db
def test_operation_catalog_template_surface_upsert_publish_and_delete_for_non_staff_manager(template_manager_client):
    user = User.objects.get(username="template_manager_non_staff")
    exposure, _ = upsert_template_exposure(
        template_id="tpl-perm-manage",
        name="Template manage",
        description="before",
        operation_type="designer_cli",
        target_entity="infobase",
        template_data={"kind": "designer_cli", "driver": "cli", "command_id": "infobase.extension.list"},
        is_active=True,
    )
    template = OperationTemplate.objects.get(id=exposure.alias)
    OperationTemplatePermission.objects.update_or_create(
        user=user,
        template=template,
        defaults={"level": PermissionLevel.MANAGE, "notes": ""},
    )

    upsert_resp = template_manager_client.post(
        "/api/v2/operation-catalog/exposures/",
        data={
            "definition": {
                "tenant_scope": "global",
                "executor_kind": "designer_cli",
                "executor_payload": {
                    "operation_type": "designer_cli",
                    "target_entity": "infobase",
                    "template_data": {
                        "kind": "designer_cli",
                        "driver": "cli",
                        "command_id": "infobase.extension.update",
                    },
                },
                "contract_version": 1,
            },
            "exposure": {
                "surface": "template",
                "alias": "tpl-perm-manage",
                "name": "Template manage updated",
                "description": "after",
                "is_active": True,
                "capability": "",
                "contexts": [],
                "display_order": 0,
                "capability_config": {},
                "status": "draft",
            },
        },
        format="json",
    )
    assert upsert_resp.status_code == 200
    exposure_id = upsert_resp.json()["exposure"]["id"]

    publish_resp = template_manager_client.post(
        f"/api/v2/operation-catalog/exposures/{exposure_id}/publish/",
        data={},
        format="json",
    )
    assert publish_resp.status_code == 200
    assert publish_resp.json()["published"] is True

    delete_resp = template_manager_client.delete(f"/api/v2/operation-catalog/exposures/{exposure_id}/")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] is True
    assert not OperationTemplate.objects.filter(id="tpl-perm-manage").exists()


@pytest.mark.django_db
def test_legacy_templates_crud_routes_are_removed(staff_client):
    assert staff_client.get("/api/v2/templates/list-templates/").status_code == 404
    assert staff_client.post("/api/v2/templates/create-template/", data={}, format="json").status_code == 404
    assert staff_client.post("/api/v2/templates/update-template/", data={}, format="json").status_code == 404
    assert staff_client.post("/api/v2/templates/delete-template/", data={}, format="json").status_code == 404


@pytest.mark.django_db
def test_operation_catalog_migration_issues_list_returns_unified_diagnostics(staff_client):
    tenant = Tenant.objects.create(slug="tenant-migration-issues", name="Tenant Migration Issues")
    issue = OperationMigrationIssue.objects.create(
        source_type="runtime_setting",
        source_id="ui.action_catalog",
        tenant=tenant,
        severity=OperationMigrationIssue.SEVERITY_ERROR,
        code="INVALID_BINDING",
        message="target_binding.extension_name_param is required",
        details={"path": "capability_config.target_binding.extension_name_param"},
    )

    resp = staff_client.get("/api/v2/operation-catalog/migration-issues/")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 1
    assert payload["total"] == 1
    row = payload["issues"][0]
    assert row["id"] == str(issue.id)
    assert row["source_type"] == "runtime_setting"
    assert row["source_id"] == "ui.action_catalog"
    assert row["tenant_id"] == str(tenant.id)
    assert row["severity"] == OperationMigrationIssue.SEVERITY_ERROR
    assert row["code"] == "INVALID_BINDING"
    assert row["details"]["path"] == "capability_config.target_binding.extension_name_param"


@pytest.mark.django_db
def test_operation_catalog_migration_issues_staff_only():
    user = User.objects.create_user(username="operation_catalog_non_staff", password="pass", is_staff=False)
    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.get("/api/v2/operation-catalog/migration-issues/")
    assert resp.status_code == 403
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "FORBIDDEN"
