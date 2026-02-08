from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.tenancy.models import Tenant


@pytest.fixture
def staff_client(db):
    user = User.objects.create_user(username="operation_catalog_staff", password="pass")
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_ui_action_catalog_legacy_write_path_is_disabled(staff_client):
    payload = {
        "value": {
            "catalog_version": 1,
            "extensions": {"actions": []},
        }
    }

    resp_global = staff_client.patch("/api/v2/settings/runtime/ui.action_catalog/", data=payload, format="json")
    assert resp_global.status_code == 409
    assert resp_global.json()["error"]["code"] == "LEGACY_WRITE_DISABLED"

    tenant = Tenant.objects.create(slug="tenant-cutover", name="Tenant Cutover")
    resp_override = staff_client.patch(
        "/api/v2/settings/runtime-overrides/ui.action_catalog/",
        data=payload,
        format="json",
        HTTP_X_CC1C_TENANT_ID=str(tenant.id),
    )
    assert resp_override.status_code == 409
    assert resp_override.json()["error"]["code"] == "LEGACY_WRITE_DISABLED"


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
