import io
import json

import pytest
from django.contrib.auth.models import Permission, User
from rest_framework.test import APIClient

from apps.api_v2.views import driver_catalogs as driver_catalogs_view
from apps.artifacts.models import Artifact, ArtifactAlias, ArtifactKind, ArtifactVersion
from apps.artifacts.storage import ArtifactStorageClient
from apps.operations.models import AdminActionAuditLog


@pytest.fixture
def staff_user():
    user = User.objects.create_user(username="command_schemas_staff", password="pass")
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
def test_command_schemas_overrides_rollback_version_not_found_is_audited(client, monkeypatch):
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

    recorded: list[tuple[str, str, str]] = []

    def fake_record_error(driver: str, action: str, code: str) -> None:
        recorded.append((str(driver), str(action), str(code)))

    monkeypatch.setattr(driver_catalogs_view, "record_driver_catalog_editor_error", fake_record_error)

    resp = client.post(
        "/api/v2/settings/command-schemas/overrides/rollback/",
        data={
            "driver": "cli",
            "version": "missing-version",
            "reason": "test missing version",
        },
        format="json",
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "VERSION_NOT_FOUND"

    audit = AdminActionAuditLog.objects.filter(
        action="driver_catalog.overrides.rollback",
        outcome="error",
        target_id="cli",
    ).first()
    assert audit is not None
    assert audit.metadata.get("error") == "VERSION_NOT_FOUND"
    assert audit.metadata.get("reason") == "test missing version"

    assert ("cli", "overrides.rollback", "VERSION_NOT_FOUND") in recorded


@pytest.mark.django_db
def test_command_schemas_overrides_update_save_failed_is_audited(client, monkeypatch):
    def fake_upload_overrides(*args, **kwargs):
        _ = args
        _ = kwargs
        raise RuntimeError("storage down")

    monkeypatch.setattr(driver_catalogs_view, "upload_overrides_catalog_version", fake_upload_overrides)

    recorded: list[tuple[str, str, str]] = []

    def fake_record_error(driver: str, action: str, code: str) -> None:
        recorded.append((str(driver), str(action), str(code)))

    monkeypatch.setattr(driver_catalogs_view, "record_driver_catalog_editor_error", fake_record_error)

    resp = client.post(
        "/api/v2/settings/command-schemas/overrides/update/",
        data={
            "driver": "cli",
            "catalog": {"catalog_version": 2, "driver": "cli", "overrides": {"commands_by_id": {}}},
            "reason": "test save failed",
        },
        format="json",
    )
    assert resp.status_code == 500
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "SAVE_FAILED"

    audit = AdminActionAuditLog.objects.filter(
        action="driver_catalog.overrides.update",
        outcome="error",
        target_id="cli",
    ).first()
    assert audit is not None
    assert audit.metadata.get("error") == "SAVE_FAILED"
    assert audit.metadata.get("reason") == "test save failed"

    assert ("cli", "overrides.update", "SAVE_FAILED") in recorded
