# ruff: noqa: F811
import io
import json

import pytest

from apps.artifacts.models import Artifact, ArtifactAlias, ArtifactKind, ArtifactVersion
from apps.artifacts.storage import ArtifactStorageClient

from ._command_schemas_editor_fixtures import client, staff_user  # noqa: F401


@pytest.mark.django_db
def test_command_schemas_editor_view_returns_versions_and_etag(client, monkeypatch):
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
        version="v-override",
        filename="driver_catalog.cli.overrides__v-override.json",
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
    overrides_catalog = {
        "catalog_version": 2,
        "driver": "cli",
        "overrides": {
            "commands_by_id": {
                "AccessToken": {"risk_level": "dangerous"},
            }
        },
    }

    storage_data = {
        "test/base": json.dumps(base_catalog).encode("utf-8"),
        "test/overrides": json.dumps(overrides_catalog).encode("utf-8"),
    }

    def fake_get_object(_self, storage_key: str):
        return io.BytesIO(storage_data[storage_key])

    monkeypatch.setattr(ArtifactStorageClient, "get_object", fake_get_object)

    resp = client.get("/api/v2/settings/command-schemas/editor/", {"driver": "cli"})
    assert resp.status_code == 200
    assert resp.headers.get("ETag")

    payload = resp.json()
    assert payload["driver"] == "cli"
    assert payload["etag"] == resp.headers["ETag"]
    assert payload["base"]["approved_version"] == "v-base"
    assert payload["overrides"]["active_version"] == "v-override"
    assert payload["catalogs"]["effective"]["catalog"]["commands_by_id"]["AccessToken"]["risk_level"] == "dangerous"

    resp_304 = client.get(
        "/api/v2/settings/command-schemas/editor/",
        {"driver": "cli"},
        HTTP_IF_NONE_MATCH=resp.headers["ETag"],
    )
    assert resp_304.status_code == 304
