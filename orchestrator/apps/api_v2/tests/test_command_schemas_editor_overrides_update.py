import io
import json

import pytest

from apps.api_v2.views import driver_catalogs as driver_catalogs_view
from apps.artifacts.models import Artifact, ArtifactAlias, ArtifactKind, ArtifactVersion
from apps.artifacts.storage import ArtifactStorageClient
from apps.operations.models import AdminActionAuditLog

from ._command_schemas_editor_fixtures import client, staff_user  # noqa: F401


@pytest.mark.django_db
def test_command_schemas_overrides_update_and_rollback(client, monkeypatch):
    base = Artifact.objects.create(
        name="driver_catalog.cli.base",
        kind=ArtifactKind.DRIVER_CATALOG,
        is_versioned=True,
        tags=["driver_catalog", "cli", "base"],
    )
    overrides = Artifact.objects.create(
        name="driver_catalog.cli.overrides",
        kind=ArtifactKind.DRIVER_CATALOG,
        is_versioned=True,
        tags=["driver_catalog", "cli", "overrides"],
    )

    base_version = ArtifactVersion.objects.create(
        artifact=base,
        version="v-base",
        filename="driver_catalog.cli.base__v-base.json",
        storage_key="test/base",
        size=1,
        checksum="base",
        content_type="application/json",
        metadata={},
    )
    initial_overrides_version = ArtifactVersion.objects.create(
        artifact=overrides,
        version="v-override",
        filename="driver_catalog.cli.overrides__v-override.json",
        storage_key="test/overrides",
        size=1,
        checksum="overrides",
        content_type="application/json",
        metadata={},
    )
    ArtifactAlias.objects.create(artifact=base, alias="approved", version=base_version)
    ArtifactAlias.objects.create(artifact=overrides, alias="active", version=initial_overrides_version)

    base_catalog = {
        "catalog_version": 2,
        "driver": "cli",
        "platform_version": "8.3.27",
        "source": {"type": "legacy_cli_config"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "AccessToken": {
                "label": "AccessToken",
                "description": "Get token",
                "argv": ["/AccessToken"],
                "scope": "per_database",
                "risk_level": "safe",
            }
        },
    }
    initial_overrides_catalog = {
        "catalog_version": 2,
        "driver": "cli",
        "overrides": {"commands_by_id": {"AccessToken": {"risk_level": "safe"}}},
    }

    storage_data: dict[str, bytes] = {
        "test/base": json.dumps(base_catalog).encode("utf-8"),
        "test/overrides": json.dumps(initial_overrides_catalog).encode("utf-8"),
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

    invalidations: list[str] = []

    def fake_invalidate(driver: str) -> None:
        invalidations.append(str(driver))

    monkeypatch.setattr(driver_catalogs_view, "invalidate_driver_catalog_cache", fake_invalidate)

    editor_resp = client.get("/api/v2/settings/command-schemas/editor/", {"driver": "cli"})
    assert editor_resp.status_code == 200
    etag = editor_resp.headers["ETag"]

    new_overrides_catalog = {
        "catalog_version": 2,
        "driver": "cli",
        "overrides": {"commands_by_id": {"AccessToken": {"risk_level": "dangerous"}}},
    }

    update_resp = client.post(
        "/api/v2/settings/command-schemas/overrides/update/",
        data={
            "driver": "cli",
            "catalog": new_overrides_catalog,
            "reason": "test update",
            "expected_etag": etag,
        },
        format="json",
    )
    assert update_resp.status_code == 200
    update_payload = update_resp.json()
    assert update_payload["driver"] == "cli"
    assert update_payload["overrides_version"].startswith("ovr-")
    assert update_payload["etag"]

    assert ArtifactAlias.objects.get(artifact=overrides, alias="active").version.version == update_payload["overrides_version"]

    update_audit = AdminActionAuditLog.objects.filter(
        action="driver_catalog.overrides.update",
        outcome="success",
        target_id="cli",
    ).first()
    assert update_audit is not None
    assert update_audit.metadata.get("reason") == "test update"

    rollback_resp = client.post(
        "/api/v2/settings/command-schemas/overrides/rollback/",
        data={
            "driver": "cli",
            "version": "v-override",
            "reason": "test rollback",
            "expected_etag": update_payload["etag"],
        },
        format="json",
    )
    assert rollback_resp.status_code == 200
    rollback_payload = rollback_resp.json()
    assert rollback_payload["driver"] == "cli"
    assert rollback_payload["overrides_version"] == "v-override"

    rollback_audit = AdminActionAuditLog.objects.filter(
        action="driver_catalog.overrides.rollback",
        outcome="success",
        target_id="cli",
    ).first()
    assert rollback_audit is not None
    assert rollback_audit.metadata.get("reason") == "test rollback"

    assert invalidations == ["cli", "cli"]

    versions_resp = client.get(
        "/api/v2/settings/command-schemas/versions/",
        {"driver": "cli", "artifact": "overrides", "limit": 10, "offset": 0},
    )
    assert versions_resp.status_code == 200
    versions_payload = versions_resp.json()
    assert versions_payload["driver"] == "cli"
    assert versions_payload["artifact"] == "overrides"
    assert versions_payload["versions"][0]["version"] == update_payload["overrides_version"]
    assert versions_payload["versions"][0]["metadata"].get("reason") == "test update"

    audit_resp = client.get("/api/v2/settings/command-schemas/audit/", {"driver": "cli", "limit": 10, "offset": 0})
    assert audit_resp.status_code == 200
    audit_payload = audit_resp.json()
    assert audit_payload["count"] >= 2
    actions = {row["action"] for row in audit_payload["items"]}
    assert "driver_catalog.overrides.update" in actions
    assert "driver_catalog.overrides.rollback" in actions


@pytest.mark.django_db
def test_command_schemas_overrides_update_rejects_invalid_cli_effective(client, monkeypatch):
    base = Artifact.objects.create(
        name="driver_catalog.cli.base",
        kind=ArtifactKind.DRIVER_CATALOG,
        is_versioned=True,
        tags=["driver_catalog", "cli", "base"],
    )
    overrides = Artifact.objects.create(
        name="driver_catalog.cli.overrides",
        kind=ArtifactKind.DRIVER_CATALOG,
        is_versioned=True,
        tags=["driver_catalog", "cli", "overrides"],
    )

    base_version = ArtifactVersion.objects.create(
        artifact=base,
        version="v-base",
        filename="driver_catalog.cli.base__v-base.json",
        storage_key="test/base",
        size=1,
        checksum="base",
        content_type="application/json",
        metadata={},
    )
    initial_overrides_version = ArtifactVersion.objects.create(
        artifact=overrides,
        version="v-override",
        filename="driver_catalog.cli.overrides__v-override.json",
        storage_key="test/overrides",
        size=1,
        checksum="overrides",
        content_type="application/json",
        metadata={},
    )
    ArtifactAlias.objects.create(artifact=base, alias="approved", version=base_version)
    ArtifactAlias.objects.create(artifact=overrides, alias="active", version=initial_overrides_version)

    base_catalog = {
        "catalog_version": 2,
        "driver": "cli",
        "platform_version": "8.3.27",
        "source": {"type": "legacy_cli_config"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "AccessToken": {
                "label": "AccessToken",
                "description": "Get token",
                "argv": ["/AccessToken"],
                "scope": "per_database",
                "risk_level": "safe",
            }
        },
    }
    initial_overrides_catalog = {
        "catalog_version": 2,
        "driver": "cli",
        "overrides": {"commands_by_id": {}},
    }

    storage_data: dict[str, bytes] = {
        "test/base": json.dumps(base_catalog).encode("utf-8"),
        "test/overrides": json.dumps(initial_overrides_catalog).encode("utf-8"),
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

    editor_resp = client.get("/api/v2/settings/command-schemas/editor/", {"driver": "cli"})
    assert editor_resp.status_code == 200
    etag = editor_resp.headers["ETag"]

    invalid_overrides_catalog = {
        "catalog_version": 2,
        "driver": "cli",
        "overrides": {
            "commands_by_id": {
                "AccessToken": {"argv": ["/Other"]},
            }
        },
    }

    update_resp = client.post(
        "/api/v2/settings/command-schemas/overrides/update/",
        data={
            "driver": "cli",
            "catalog": invalid_overrides_catalog,
            "reason": "test invalid update",
            "expected_etag": etag,
        },
        format="json",
    )
    assert update_resp.status_code == 400
    payload = update_resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "INVALID_EFFECTIVE_CATALOG"
    assert any(item["code"] == "COMMAND_ID_MISMATCH" for item in payload["error"]["details"])

    assert ArtifactAlias.objects.get(artifact=overrides, alias="active").version_id == initial_overrides_version.id
    assert overrides.versions.count() == 1
