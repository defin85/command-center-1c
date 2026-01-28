import io
import json

import pytest

from apps.artifacts.models import Artifact, ArtifactAlias, ArtifactKind, ArtifactVersion
from apps.artifacts.storage import ArtifactStorageClient

from ._command_schemas_editor_fixtures import client, staff_user  # noqa: F401


@pytest.mark.django_db
def test_command_schemas_preview_diff_and_validate_support_draft_overrides(client, monkeypatch):
    base = Artifact.objects.create(
        name="driver_catalog.ibcmd.base",
        kind=ArtifactKind.DRIVER_CATALOG,
        is_versioned=True,
        tags=["driver_catalog", "ibcmd", "base"],
    )
    overrides = Artifact.objects.create(
        name="driver_catalog.ibcmd.overrides",
        kind=ArtifactKind.DRIVER_CATALOG,
        is_versioned=True,
        tags=["driver_catalog", "ibcmd", "overrides"],
    )

    base_version = ArtifactVersion.objects.create(
        artifact=base,
        version="v-base",
        filename="driver_catalog.ibcmd.base__v-base.json",
        storage_key="test/ib/base",
        size=1,
        checksum="base",
        content_type="application/json",
        metadata={},
    )
    overrides_version = ArtifactVersion.objects.create(
        artifact=overrides,
        version="v-override",
        filename="driver_catalog.ibcmd.overrides__v-override.json",
        storage_key="test/ib/overrides",
        size=1,
        checksum="overrides",
        content_type="application/json",
        metadata={},
    )
    ArtifactAlias.objects.create(artifact=base, alias="approved", version=base_version)
    ArtifactAlias.objects.create(artifact=overrides, alias="active", version=overrides_version)

    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "its_import", "doc_id": "TI000", "doc_url": "http://example"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "ibcmd.infobase.dump": {
                "label": "Dump",
                "description": "Dump",
                "argv": ["ibcmd", "infobase", "dump"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {
                    "remote": {"kind": "flag", "required": True, "expects_value": True, "flag": "--remote"},
                    "pid": {"kind": "flag", "required": False, "expects_value": True, "flag": "--pid"},
                },
            },
            "ibcmd.infobase.extension.list": {
                "label": "List extensions",
                "description": "List extensions",
                "argv": ["ibcmd", "infobase", "extension", "list"],
                "scope": "per_database",
                "risk_level": "safe",
                "params_by_name": {},
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {"commands_by_id": {}}}

    storage_data = {
        "test/ib/base": json.dumps(base_catalog).encode("utf-8"),
        "test/ib/overrides": json.dumps(overrides_catalog).encode("utf-8"),
    }

    def fake_get_object(_self, storage_key: str):
        return io.BytesIO(storage_data[storage_key])

    monkeypatch.setattr(ArtifactStorageClient, "get_object", fake_get_object)

    validate_dup_resp = client.post(
        "/api/v2/settings/command-schemas/validate/",
        data={
            "driver": "ibcmd",
            "catalog": {
                "catalog_version": 2,
                "driver": "ibcmd",
                "overrides": {
                    "commands_by_id": {
                        "ibcmd.infobase.dump": {"params_by_name": {"remote": {"flag": "--pid"}}},
                    }
                },
            },
        },
        format="json",
    )
    assert validate_dup_resp.status_code == 200
    validate_payload = validate_dup_resp.json()
    assert validate_payload["driver"] == "ibcmd"
    assert validate_payload["ok"] is False
    assert any(item["code"] == "DUPLICATE_FLAG" for item in validate_payload["issues"])

    validate_driver_schema_resp = client.post(
        "/api/v2/settings/command-schemas/validate/",
        data={
            "driver": "ibcmd",
            "catalog": {
                "catalog_version": 2,
                "driver": "ibcmd",
                "overrides": {
                    "driver_schema": {
                        "connection": {
                            "remote": {"kind": "flag", "required": False, "expects_value": True, "flag": "--pid"},
                            "pid": {"kind": "flag", "required": False, "expects_value": True, "flag": "--pid"},
                        }
                    },
                    "commands_by_id": {},
                },
            },
        },
        format="json",
    )
    assert validate_driver_schema_resp.status_code == 200
    validate_driver_schema_payload = validate_driver_schema_resp.json()
    assert validate_driver_schema_payload["ok"] is False
    assert any(
        item["code"] == "DUPLICATE_FLAG"
        and str(item.get("path") or "").startswith("driver_schema.connection")
        for item in validate_driver_schema_payload["issues"]
    )

    preview_resp = client.post(
        "/api/v2/settings/command-schemas/preview/",
        data={
            "driver": "ibcmd",
            "command_id": "ibcmd.infobase.dump",
            "mode": "guided",
            "params": {"remote": "http://host:1545", "pid": "123"},
            "additional_args": [],
            "catalog": {
                "catalog_version": 2,
                "driver": "ibcmd",
                "overrides": {
                    "commands_by_id": {
                        "ibcmd.infobase.dump": {"params_by_name": {"remote": {"flag": "--remote-url"}}},
                    }
                },
            },
        },
        format="json",
    )
    assert preview_resp.status_code == 200
    preview_payload = preview_resp.json()
    assert preview_payload["driver"] == "ibcmd"
    assert preview_payload["command_id"] == "ibcmd.infobase.dump"
    assert preview_payload["argv"] == [
        "ibcmd",
        "infobase",
        "dump",
        "--pid=123",
        "--remote-url=http://host:1545",
    ]

    preview_conn_resp = client.post(
        "/api/v2/settings/command-schemas/preview/",
        data={
            "driver": "ibcmd",
            "command_id": "ibcmd.infobase.extension.list",
            "mode": "guided",
            "connection": {"remote": "http://host:1545"},
            "params": {},
            "additional_args": [],
        },
        format="json",
    )
    assert preview_conn_resp.status_code == 200
    preview_conn_payload = preview_conn_resp.json()
    assert preview_conn_payload["command_id"] == "ibcmd.infobase.extension.list"
    assert preview_conn_payload["argv"] == [
        "ibcmd",
        "infobase",
        "extension",
        "list",
        "--remote=http://host:1545",
    ]

    preview_conflict_resp = client.post(
        "/api/v2/settings/command-schemas/preview/",
        data={
            "driver": "ibcmd",
            "command_id": "ibcmd.infobase.extension.list",
            "mode": "guided",
            "connection": {"remote": "http://host:1545"},
            "params": {},
            "additional_args": ["--remote=http://other:1545"],
        },
        format="json",
    )
    assert preview_conflict_resp.status_code == 400
    preview_conflict_payload = preview_conflict_resp.json()
    assert preview_conflict_payload["success"] is False
    assert preview_conflict_payload["error"]["code"] == "INVALID_PREVIEW"

    preview_pid_short_resp = client.post(
        "/api/v2/settings/command-schemas/preview/",
        data={
            "driver": "ibcmd",
            "command_id": "ibcmd.infobase.extension.list",
            "mode": "guided",
            "connection": {"remote": "http://host:1545"},
            "params": {},
            "additional_args": ["-p123"],
        },
        format="json",
    )
    assert preview_pid_short_resp.status_code == 400
    preview_pid_short_payload = preview_pid_short_resp.json()
    assert preview_pid_short_payload["success"] is False
    assert preview_pid_short_payload["error"]["code"] == "INVALID_PREVIEW"

    diff_resp = client.post(
        "/api/v2/settings/command-schemas/diff/",
        data={
            "driver": "ibcmd",
            "command_id": "ibcmd.infobase.dump",
            "catalog": {
                "catalog_version": 2,
                "driver": "ibcmd",
                "overrides": {
                    "commands_by_id": {
                        "ibcmd.infobase.dump": {"params_by_name": {"remote": {"flag": "--remote-url"}}},
                    }
                },
            },
        },
        format="json",
    )
    assert diff_resp.status_code == 200
    diff_payload = diff_resp.json()
    assert diff_payload["driver"] == "ibcmd"
    assert diff_payload["command_id"] == "ibcmd.infobase.dump"
    assert any(
        row["path"] == "commands_by_id.ibcmd.infobase.dump.params_by_name.remote.flag"
        and row["base"] == "--remote"
        and row["effective"] == "--remote-url"
        for row in diff_payload["changes"]
    )
