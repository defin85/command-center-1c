import io
import json

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.artifacts.models import Artifact, ArtifactAlias, ArtifactKind, ArtifactVersion
from apps.artifacts.storage import ArtifactStorageClient


@pytest.fixture
def user():
    return User.objects.create_user(username="driver_commands_user", password="pass")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.mark.django_db
def test_driver_commands_requires_driver_param(client):
    resp = client.get("/api/v2/operations/driver-commands/")
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "MISSING_DRIVER"


@pytest.mark.django_db
def test_driver_commands_cli_reads_from_artifacts_and_merges_overrides(client, monkeypatch):
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

    storage_map = {
        "test/base": json.dumps(base_catalog).encode("utf-8"),
        "test/overrides": json.dumps(overrides_catalog).encode("utf-8"),
    }

    def fake_get_object(_self, storage_key: str):
        return io.BytesIO(storage_map[storage_key])

    monkeypatch.setattr(ArtifactStorageClient, "get_object", fake_get_object)

    resp = client.get("/api/v2/operations/driver-commands/", {"driver": "cli"})
    assert resp.status_code == 200
    assert resp.headers.get("ETag")

    payload = resp.json()
    assert payload["driver"] == "cli"
    assert payload["base_version"] == "v-base"
    assert payload["overrides_version"] == "v-override"
    assert payload["catalog"]["catalog_version"] == 2
    assert payload["catalog"]["driver"] == "cli"
    assert isinstance(payload["catalog"]["commands_by_id"], dict)
    assert payload["catalog"]["commands_by_id"]["AccessToken"]["risk_level"] == "dangerous"
    assert payload["catalog"]["commands_by_id"]["AccessToken"]["argv"] == ["/AccessToken"]


@pytest.mark.django_db
def test_driver_commands_etag_allows_304(client, monkeypatch):
    base = Artifact.objects.create(
        name="driver_catalog.cli.base",
        kind=ArtifactKind.DRIVER_CATALOG,
        is_versioned=True,
        tags=["driver_catalog", "cli", "base"],
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
    ArtifactAlias.objects.create(artifact=base, alias="approved", version=base_version)

    base_catalog = {
        "catalog_version": 2,
        "driver": "cli",
        "platform_version": "8.3.27",
        "source": {"type": "legacy_cli_config"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {},
    }

    def fake_get_object(_self, storage_key: str):
        assert storage_key == "test/base"
        return io.BytesIO(json.dumps(base_catalog).encode("utf-8"))

    monkeypatch.setattr(ArtifactStorageClient, "get_object", fake_get_object)

    first = client.get("/api/v2/operations/driver-commands/", {"driver": "cli"})
    assert first.status_code == 200
    etag = first.headers["ETag"]

    second = client.get(
        "/api/v2/operations/driver-commands/",
        {"driver": "cli"},
        HTTP_IF_NONE_MATCH=etag,
    )
    assert second.status_code == 304
    assert second.headers.get("ETag") == etag


@pytest.mark.django_db
def test_driver_commands_ibcmd_reads_from_artifacts(client, monkeypatch):
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
        storage_key="test/base",
        size=1,
        checksum="base",
        content_type="application/json",
        metadata={},
    )
    overrides_version = ArtifactVersion.objects.create(
        artifact=overrides,
        version="v-override",
        filename="driver_catalog.ibcmd.overrides__v-override.json",
        storage_key="test/overrides",
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
        "source": {"type": "its_import", "doc_id": "TI000001193", "section_prefix": "4.10"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "server.config.init": {
                "label": "server config init",
                "description": "Init server config",
                "argv": ["server", "config", "init"],
                "scope": "global",
                "risk_level": "safe",
            }
        },
    }
    overrides_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "overrides": {
            "commands_by_id": {
                "server.config.init": {"disabled": True},
            }
        },
    }

    storage_map = {
        "test/base": json.dumps(base_catalog).encode("utf-8"),
        "test/overrides": json.dumps(overrides_catalog).encode("utf-8"),
    }

    def fake_get_object(_self, storage_key: str):
        return io.BytesIO(storage_map[storage_key])

    monkeypatch.setattr(ArtifactStorageClient, "get_object", fake_get_object)

    resp = client.get("/api/v2/operations/driver-commands/", {"driver": "ibcmd"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["driver"] == "ibcmd"
    assert payload["base_version"] == "v-base"
    assert payload["overrides_version"] == "v-override"
    assert payload["catalog"]["commands_by_id"]["server.config.init"]["disabled"] is True


@pytest.mark.django_db
def test_driver_commands_ibcmd_returns_empty_catalog(client):
    resp = client.get("/api/v2/operations/driver-commands/", {"driver": "ibcmd"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["driver"] == "ibcmd"
    assert payload["catalog"]["catalog_version"] == 2
    assert payload["catalog"]["driver"] == "ibcmd"
    assert payload["catalog"]["commands_by_id"] == {}
