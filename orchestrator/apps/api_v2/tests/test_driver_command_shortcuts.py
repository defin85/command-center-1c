import io
import json
import uuid

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.artifacts.models import Artifact, ArtifactAlias, ArtifactKind, ArtifactVersion
from apps.artifacts.storage import ArtifactStorageClient


def _seed_ibcmd_catalog(monkeypatch, *, base_catalog: dict, overrides_catalog: dict | None = None):
    suffix = uuid.uuid4().hex[:8]

    base = Artifact.objects.create(
        name="driver_catalog.ibcmd.base",
        kind=ArtifactKind.DRIVER_CATALOG,
        is_versioned=True,
        tags=["driver_catalog", "ibcmd", "base"],
    )
    base_version = ArtifactVersion.objects.create(
        artifact=base,
        version=f"v-base-{suffix}",
        filename=f"driver_catalog.ibcmd.base__v-base-{suffix}.json",
        storage_key=f"test/ibcmd/base/{suffix}",
        size=1,
        checksum=f"base-{suffix}",
        content_type="application/json",
        metadata={},
    )
    ArtifactAlias.objects.create(artifact=base, alias="approved", version=base_version)

    overrides_version = None
    storage_map = {
        base_version.storage_key: json.dumps(base_catalog).encode("utf-8"),
    }

    if overrides_catalog is not None:
        overrides = Artifact.objects.create(
            name="driver_catalog.ibcmd.overrides",
            kind=ArtifactKind.DRIVER_CATALOG,
            is_versioned=True,
            tags=["driver_catalog", "ibcmd", "overrides"],
        )
        overrides_version = ArtifactVersion.objects.create(
            artifact=overrides,
            version=f"v-override-{suffix}",
            filename=f"driver_catalog.ibcmd.overrides__v-override-{suffix}.json",
            storage_key=f"test/ibcmd/overrides/{suffix}",
            size=1,
            checksum=f"overrides-{suffix}",
            content_type="application/json",
            metadata={},
        )
        ArtifactAlias.objects.create(artifact=overrides, alias="active", version=overrides_version)
        storage_map[overrides_version.storage_key] = json.dumps(overrides_catalog).encode("utf-8")

    def fake_get_object(_self, storage_key: str):
        return io.BytesIO(storage_map[storage_key])

    monkeypatch.setattr(ArtifactStorageClient, "get_object", fake_get_object)
    return base_version, overrides_version


@pytest.mark.django_db
def test_driver_command_shortcuts_crud(monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {
            "server.config.init": {
                "label": "server config init",
                "argv": ["server", "config", "init"],
                "scope": "global",
                "risk_level": "safe",
                "params_by_name": {},
            },
        },
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    u = User.objects.create_user(username="u1", password="pass")
    c = APIClient()
    c.force_authenticate(user=u)

    list_resp = c.get("/api/v2/operations/list-command-shortcuts/", {"driver": "ibcmd"})
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] == 0

    create_resp = c.post(
        "/api/v2/operations/create-command-shortcut/",
        {"driver": "ibcmd", "command_id": "server.config.init", "title": "Init server config"},
        format="json",
    )
    assert create_resp.status_code == 201
    shortcut_id = create_resp.json()["id"]

    list_resp = c.get("/api/v2/operations/list-command-shortcuts/", {"driver": "ibcmd"})
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert payload["count"] == 1
    assert payload["items"][0]["id"] == shortcut_id

    delete_resp = c.post(
        "/api/v2/operations/delete-command-shortcut/",
        {"shortcut_id": shortcut_id},
        format="json",
    )
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] is True

    list_resp = c.get("/api/v2/operations/list-command-shortcuts/", {"driver": "ibcmd"})
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] == 0


@pytest.mark.django_db
def test_driver_command_shortcuts_unknown_command_returns_400(monkeypatch):
    base_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "platform_version": "8.3.27",
        "source": {"type": "test"},
        "generated_at": "2026-01-01T00:00:00Z",
        "commands_by_id": {},
    }
    overrides_catalog = {"catalog_version": 2, "driver": "ibcmd", "overrides": {}}
    _seed_ibcmd_catalog(monkeypatch, base_catalog=base_catalog, overrides_catalog=overrides_catalog)

    u = User.objects.create_user(username="u1", password="pass")
    c = APIClient()
    c.force_authenticate(user=u)

    create_resp = c.post(
        "/api/v2/operations/create-command-shortcut/",
        {"driver": "ibcmd", "command_id": "unknown.command", "title": "x"},
        format="json",
    )
    assert create_resp.status_code == 400
    payload = create_resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNKNOWN_COMMAND"
