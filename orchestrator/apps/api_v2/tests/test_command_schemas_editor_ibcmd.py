# ruff: noqa: F811
import io
import json

import pytest

from apps.api_v2.views import driver_catalogs as driver_catalogs_view
from apps.artifacts.models import Artifact, ArtifactAlias, ArtifactKind, ArtifactVersion
from apps.artifacts.storage import ArtifactStorageClient
from apps.operations.models import AdminActionAuditLog

from ._command_schemas_editor_fixtures import client, staff_user  # noqa: F401


@pytest.mark.django_db
def test_command_schemas_overrides_update_ibcmd_requires_base_and_is_audited(client, monkeypatch):
    storage_data: dict[str, bytes] = {}

    def fake_upload_object(_self, storage_key: str, data, size: int, content_type=None):
        _ = size
        _ = content_type
        storage_data[storage_key] = data.read()
        try:
            data.seek(0)
        except Exception:
            pass

    monkeypatch.setattr(ArtifactStorageClient, "upload_object", fake_upload_object)

    recorded: list[tuple[str, str, str]] = []

    def fake_record_error(driver: str, action: str, code: str) -> None:
        recorded.append((str(driver), str(action), str(code)))

    monkeypatch.setattr(driver_catalogs_view, "record_driver_catalog_editor_error", fake_record_error)

    resp = client.post(
        "/api/v2/settings/command-schemas/overrides/update/",
        data={
            "driver": "ibcmd",
            "catalog": {"catalog_version": 2, "driver": "ibcmd", "overrides": {"commands_by_id": {}}},
            "reason": "test missing base",
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "BASE_CATALOG_MISSING"

    audit = AdminActionAuditLog.objects.filter(
        action="driver_catalog.overrides.update",
        outcome="error",
        target_id="ibcmd",
    ).first()
    assert audit is not None
    assert audit.metadata.get("error") == "BASE_CATALOG_MISSING"
    assert audit.metadata.get("reason") == "test missing base"

    assert ("ibcmd", "overrides.update", "BASE_CATALOG_MISSING") in recorded


@pytest.mark.django_db
def test_command_schemas_overrides_update_rejects_invalid_ibcmd_driver_schema(client, monkeypatch):
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
        storage_key="test/ib/base2",
        size=1,
        checksum="base",
        content_type="application/json",
        metadata={},
    )
    initial_overrides_version = ArtifactVersion.objects.create(
        artifact=overrides,
        version="v-override",
        filename="driver_catalog.ibcmd.overrides__v-override.json",
        storage_key="test/ib/overrides2",
        size=1,
        checksum="overrides",
        content_type="application/json",
        metadata={},
    )
    ArtifactAlias.objects.create(artifact=base, alias="approved", version=base_version)
    ArtifactAlias.objects.create(artifact=base, alias="latest", version=base_version)
    ArtifactAlias.objects.create(artifact=overrides, alias="active", version=initial_overrides_version)

    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "server.config.init": {
                "label": "server config init",
                "description": "Init server config",
                "argv": ["server", "config", "init"],
                "scope": "global",
                "risk_level": "safe",
                "params_by_name": {},
            },
        },
    }
    initial_overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {"commands_by_id": {}}}

    storage_data: dict[str, bytes] = {
        "test/ib/base2": json.dumps(base_catalog).encode("utf-8"),
        "test/ib/overrides2": json.dumps(initial_overrides_catalog).encode("utf-8"),
    }

    def fake_upload_object(_self, storage_key: str, data, size: int, content_type=None):
        _ = size
        _ = content_type
        storage_data[storage_key] = data.read()
        try:
            data.seek(0)
        except Exception:
            pass

    def fake_get_object(_self, storage_key: str):
        return io.BytesIO(storage_data[storage_key])

    monkeypatch.setattr(ArtifactStorageClient, "upload_object", fake_upload_object)
    monkeypatch.setattr(ArtifactStorageClient, "get_object", fake_get_object)

    editor_resp = client.get("/api/v2/settings/command-schemas/editor/", {"driver": "ibcmd"})
    assert editor_resp.status_code == 200
    etag = editor_resp.headers["ETag"]

    invalid_overrides_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "overrides": {
            "driver_schema": {
                "connection": {
                    "remote": {"kind": "flag", "required": False, "expects_value": True, "flag": "--pid"},
                    "pid": {"kind": "flag", "required": False, "expects_value": True, "flag": "--pid"},
                },
            },
            "commands_by_id": {},
        },
    }

    update_resp = client.post(
        "/api/v2/settings/command-schemas/overrides/update/",
        data={
            "driver": "ibcmd",
            "catalog": invalid_overrides_catalog,
            "reason": "test invalid driver schema",
            "expected_etag": etag,
        },
        format="json",
    )
    assert update_resp.status_code == 400
    payload = update_resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "INVALID_EFFECTIVE_CATALOG"
    assert any(
        item.get("code") == "DUPLICATE_FLAG" and str(item.get("path") or "").startswith("driver_schema.connection")
        for item in payload["error"]["details"]
    )

    assert ArtifactAlias.objects.get(artifact=overrides, alias="active").version_id == initial_overrides_version.id
    assert overrides.versions.count() == 1
