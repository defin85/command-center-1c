import io
import json

import pytest
from django.contrib.auth.models import Permission, User
from rest_framework.test import APIClient

from apps.artifacts.models import Artifact, ArtifactAlias, ArtifactKind, ArtifactVersion
from apps.artifacts.storage import ArtifactStorageClient, ArtifactStorageError
from apps.runtime_settings.models import RuntimeSetting


@pytest.fixture
def staff_user():
    user = User.objects.create_user(username="driver_catalogs_overrides_admin", password="pass")
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    permission = Permission.objects.get(codename="manage_driver_catalogs", content_type__app_label="operations")
    user.user_permissions.add(permission)
    return user


@pytest.fixture
def client(staff_user):
    c = APIClient()
    c.force_authenticate(user=staff_user)
    return c


@pytest.mark.django_db
def test_command_schemas_overrides_update_for_ibcmd(client, monkeypatch):
    storage_data: dict[str, bytes] = {}

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
    initial_overrides_version = ArtifactVersion.objects.create(
        artifact=overrides,
        version="ovr-initial",
        filename="driver_catalog.ibcmd.overrides__ovr-initial.json",
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
                },
            },
        },
    }
    overrides_catalog_initial = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "overrides": {"commands_by_id": {}},
    }

    storage_data["test/base"] = json.dumps(base_catalog).encode("utf-8")
    storage_data["test/overrides"] = json.dumps(overrides_catalog_initial).encode("utf-8")

    editor_resp = client.get("/api/v2/settings/command-schemas/editor/", {"driver": "ibcmd"})
    assert editor_resp.status_code == 200
    etag = editor_resp.headers["ETag"]

    overrides_catalog = {
        "catalog_version": 2,
        "driver": "ibcmd",
        "overrides": {
            "commands_by_id": {
                "ibcmd.infobase.dump": {"disabled": True},
            }
        },
    }

    update_resp = client.post(
        "/api/v2/settings/command-schemas/overrides/update/",
        data={"driver": "ibcmd", "catalog": overrides_catalog, "reason": "test update", "expected_etag": etag},
        format="json",
    )
    assert update_resp.status_code == 200
    update_payload = update_resp.json()
    assert update_payload["driver"] == "ibcmd"
    assert update_payload["overrides_version"].startswith("ovr-")

    editor_after = client.get("/api/v2/settings/command-schemas/editor/", {"driver": "ibcmd"})
    assert editor_after.status_code == 200
    effective = editor_after.json()["catalogs"]["effective"]["catalog"]
    assert effective["commands_by_id"]["ibcmd.infobase.dump"]["disabled"] is True


@pytest.mark.django_db
def test_driver_catalogs_promote_changes_approved_alias(client, monkeypatch):
    monkeypatch.setattr(ArtifactStorageClient, "upload_object", lambda *args, **kwargs: None)

    base = Artifact.objects.create(
        name="driver_catalog.ibcmd.base",
        kind=ArtifactKind.DRIVER_CATALOG,
        is_versioned=True,
        tags=["driver_catalog", "ibcmd", "base"],
    )
    v1 = ArtifactVersion.objects.create(
        artifact=base,
        version="v1",
        filename="driver_catalog.ibcmd.base__v1.json",
        storage_key="test/v1",
        size=1,
        checksum="v1",
        content_type="application/json",
        metadata={},
    )
    v2 = ArtifactVersion.objects.create(
        artifact=base,
        version="v2",
        filename="driver_catalog.ibcmd.base__v2.json",
        storage_key="test/v2",
        size=1,
        checksum="v2",
        content_type="application/json",
        metadata={},
    )
    ArtifactAlias.objects.create(artifact=base, alias="approved", version=v1)

    resp = client.post(
        "/api/v2/settings/command-schemas/promote/",
        data={"driver": "ibcmd", "version": "v2", "alias": "approved", "reason": "test promote"},
        format="json",
    )
    assert resp.status_code == 200
    assert ArtifactAlias.objects.get(artifact=base, alias="approved").version_id == v2.id


@pytest.mark.django_db
def test_driver_commands_falls_back_to_lkg_when_storage_fails(client, monkeypatch):
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
        storage_key="missing/base",
        size=1,
        checksum="base",
        content_type="application/json",
        metadata={},
    )
    ArtifactAlias.objects.create(artifact=base, alias="approved", version=base_version)

    lkg_catalog = {
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
    RuntimeSetting.objects.update_or_create(
        key="operations.driver_catalog_lkg.cli",
        defaults={
            "value": {
                "driver": "cli",
                "base_version": "v-lkg",
                "base_version_id": "deadbeef-dead-beef-dead-beefdeadbeef",
                "overrides_version": None,
                "overrides_version_id": None,
                "saved_at": "2026-01-01T00:00:00Z",
                "catalog": lkg_catalog,
            }
        },
    )

    def fake_get_object(_self, storage_key: str):
        raise ArtifactStorageError(f"missing: {storage_key}")

    monkeypatch.setattr(ArtifactStorageClient, "get_object", fake_get_object)

    resp = client.get("/api/v2/operations/driver-commands/", {"driver": "cli"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["driver"] == "cli"
    assert payload["base_version"] == "v-lkg"
    assert payload["catalog"]["commands_by_id"]["AccessToken"]["argv"] == ["/AccessToken"]
