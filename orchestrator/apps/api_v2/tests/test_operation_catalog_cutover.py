from __future__ import annotations

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from apps.databases.models import PermissionLevel
from apps.runtime_settings.models import TenantRuntimeSettingOverride
from apps.tenancy.models import Tenant
from apps.templates.models import (
    OperationExposure,
    OperationExposurePermission,
    OperationMigrationIssue,
)
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
def test_legacy_ui_action_catalog_endpoint_returns_stable_decommission_contract(staff_client):
    resp = staff_client.get("/api/v2/ui/action-catalog/")
    assert resp.status_code == 404
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "NOT_FOUND"


@pytest.mark.django_db
def test_operation_catalog_list_rejects_action_catalog_surface(staff_client):
    resp = staff_client.get("/api/v2/operation-catalog/exposures/?surface=action_catalog")
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["message"] == "unknown surface"


@pytest.mark.django_db
def test_operation_catalog_upsert_rejects_non_template_surface(staff_client):
    resp = staff_client.post(
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
                "alias": "extensions.list",
                "name": "List extensions",
                "description": "",
                "is_active": True,
                "capability": "extensions.sync",
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
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["message"][0]["path"] == "exposure.surface"
    assert payload["error"]["message"][0]["message"] == "unknown surface"


@pytest.mark.django_db
def test_operation_catalog_validate_rejects_non_template_surface(staff_client):
    resp = staff_client.post(
        "/api/v2/operation-catalog/validate/",
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
                "alias": "extensions.list.validate",
                "name": "List extensions",
                "capability": "extensions.sync",
                "capability_config": {},
            },
        },
        format="json",
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["valid"] is False
    assert payload["errors"][0]["path"] == "exposure.surface"
    assert payload["errors"][0]["message"] == "only template surface is supported"


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
    OperationExposurePermission.objects.update_or_create(
        user=user,
        exposure=exposure,
        defaults={"level": PermissionLevel.VIEW, "notes": ""},
    )

    resp_template = template_manager_client.get("/api/v2/operation-catalog/exposures/?surface=template")
    assert resp_template.status_code == 200
    aliases = {row["alias"] for row in resp_template.json()["exposures"]}
    assert "tpl-perm-view" in aliases

    resp_default = template_manager_client.get("/api/v2/operation-catalog/exposures/")
    assert resp_default.status_code == 200
    aliases_default = {row["alias"] for row in resp_default.json()["exposures"]}
    assert "tpl-perm-view" in aliases_default

    resp_action = template_manager_client.get("/api/v2/operation-catalog/exposures/?surface=action_catalog")
    assert resp_action.status_code == 400


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
    OperationExposurePermission.objects.update_or_create(
        user=user,
        exposure=exposure,
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
    assert not OperationExposure.objects.filter(
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias="tpl-perm-manage",
        tenant__isnull=True,
    ).exists()


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
