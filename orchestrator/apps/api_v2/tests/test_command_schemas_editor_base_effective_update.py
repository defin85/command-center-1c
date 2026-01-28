import io
import json

import pytest

from apps.api_v2.views import driver_catalogs as driver_catalogs_view
from apps.artifacts.models import Artifact, ArtifactAlias, ArtifactKind, ArtifactVersion
from apps.artifacts.storage import ArtifactStorageClient

from apps.operations.models import AdminActionAuditLog

from ._command_schemas_editor_fixtures import client, staff_user  # noqa: F401


@pytest.mark.django_db
def test_command_schemas_base_update_publishes_base_artifact_and_is_audited(client, monkeypatch):
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
        version="v-approved",
        filename="driver_catalog.cli.base__v-approved.json",
        storage_key="test/base",
        size=1,
        checksum="base",
        content_type="application/json",
        metadata={},
    )
    overrides_version = ArtifactVersion.objects.create(
        artifact=overrides,
        version="ovr-0",
        filename="driver_catalog.cli.overrides__ovr-0.json",
        storage_key="test/overrides",
        size=1,
        checksum="overrides",
        content_type="application/json",
        metadata={},
    )
    ArtifactAlias.objects.create(artifact=base, alias="approved", version=base_version)
    ArtifactAlias.objects.create(artifact=base, alias="latest", version=base_version)
    ArtifactAlias.objects.create(artifact=overrides, alias="active", version=overrides_version)

    base_catalog = {
        "catalog_version": 2,
        "driver": "cli",
        "platform_version": "8.3.27",
        "source": {"type": "its_import", "doc_id": "TI000", "doc_url": "http://example"},
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
    overrides_catalog = {
        "catalog_version": 2,
        "driver": "cli",
        "overrides": {"commands_by_id": {}},
    }

    storage_data: dict[str, bytes] = {
        "test/base": json.dumps(base_catalog).encode("utf-8"),
        "test/overrides": json.dumps(overrides_catalog).encode("utf-8"),
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

    new_latest_catalog = {
        "catalog_version": 2,
        "driver": "cli",
        "platform_version": "8.3.27",
        "source": {"type": "its_import", "doc_id": "TI000", "doc_url": "http://example"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "AccessToken": {
                "label": "AccessToken",
                "description": "Get token (updated)",
                "argv": ["/AccessToken"],
                "scope": "per_database",
                "risk_level": "safe",
            }
        },
    }

    resp = client.post(
        "/api/v2/settings/command-schemas/base/update/",
        data={"driver": "cli", "catalog": new_latest_catalog, "reason": "update base", "expected_etag": etag},
        format="json",
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["driver"] == "cli"
    assert payload["base_version"]
    assert payload["etag"] == resp.headers["ETag"]

    base.refresh_from_db()
    assert base.versions.count() == 2

    latest_alias = ArtifactAlias.objects.get(artifact=base, alias="latest")
    approved_alias = ArtifactAlias.objects.get(artifact=base, alias="approved")
    assert latest_alias.version.version == payload["base_version"]
    assert approved_alias.version.version == "v-approved"

    latest_version = base.versions.get(version=payload["base_version"])
    assert latest_version.metadata.get("reason") == "update base"

    audit = AdminActionAuditLog.objects.filter(
        action="driver_catalog.base.update",
        outcome="success",
        target_id="cli",
    ).first()
    assert audit is not None
    assert audit.metadata.get("reason") == "update base"

    assert invalidations == ["cli"]

    conflict_resp = client.post(
        "/api/v2/settings/command-schemas/base/update/",
        data={"driver": "cli", "catalog": new_latest_catalog, "reason": "conflict", "expected_etag": "bogus"},
        format="json",
    )
    assert conflict_resp.status_code == 409
    assert conflict_resp.headers.get("ETag")


@pytest.mark.django_db
def test_command_schemas_effective_update_resets_overrides_and_is_audited(client, monkeypatch):
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
    overrides_version = ArtifactVersion.objects.create(
        artifact=overrides,
        version="ovr-custom",
        filename="driver_catalog.cli.overrides__ovr-custom.json",
        storage_key="test/overrides",
        size=1,
        checksum="overrides",
        content_type="application/json",
        metadata={},
    )
    ArtifactAlias.objects.create(artifact=base, alias="approved", version=base_version)
    ArtifactAlias.objects.create(artifact=base, alias="latest", version=base_version)
    ArtifactAlias.objects.create(artifact=overrides, alias="active", version=overrides_version)

    base_catalog = {
        "catalog_version": 2,
        "driver": "cli",
        "platform_version": "8.3.27",
        "source": {"type": "its_import", "doc_id": "TI000", "doc_url": "http://example"},
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
    overrides_catalog = {
        "catalog_version": 2,
        "driver": "cli",
        "overrides": {"commands_by_id": {"AccessToken": {"risk_level": "dangerous"}}},
    }

    storage_data: dict[str, bytes] = {
        "test/base": json.dumps(base_catalog).encode("utf-8"),
        "test/overrides": json.dumps(overrides_catalog).encode("utf-8"),
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

    effective_catalog = {
        **base_catalog,
        "commands_by_id": {
            "AccessToken": {
                "label": "AccessToken",
                "description": "Get token",
                "argv": ["/AccessToken"],
                "scope": "per_database",
                "risk_level": "dangerous",
            }
        },
    }

    resp = client.post(
        "/api/v2/settings/command-schemas/effective/update/",
        data={"driver": "cli", "catalog": effective_catalog, "reason": "dangerous reset", "expected_etag": etag},
        format="json",
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["driver"] == "cli"
    assert payload["base_version"]
    assert payload["overrides_version"]
    assert payload["etag"] == resp.headers["ETag"]

    overrides_alias = ArtifactAlias.objects.get(artifact=overrides, alias="active")
    overrides_storage_key = overrides_alias.version.storage_key
    overrides_payload = json.loads(storage_data[overrides_storage_key].decode("utf-8"))
    assert overrides_payload["overrides"]["commands_by_id"] == {}

    audit = AdminActionAuditLog.objects.filter(
        action="driver_catalog.effective.update",
        outcome="success",
        target_id="cli",
    ).first()
    assert audit is not None
    assert audit.metadata.get("reason") == "dangerous reset"

    assert invalidations == ["cli"]
