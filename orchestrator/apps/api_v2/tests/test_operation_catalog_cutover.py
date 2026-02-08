from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.runtime_settings.models import TenantRuntimeSettingOverride
from apps.tenancy.models import Tenant
from apps.templates.models import OperationMigrationIssue


@pytest.fixture
def staff_client(db):
    user = User.objects.create_user(username="operation_catalog_staff", password="pass")
    user.is_staff = True
    user.save(update_fields=["is_staff"])
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
