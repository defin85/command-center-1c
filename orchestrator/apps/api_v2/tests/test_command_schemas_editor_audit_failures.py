# ruff: noqa: F811
import pytest

from apps.api_v2.views import driver_catalogs as driver_catalogs_view
from apps.artifacts.models import Artifact, ArtifactAlias, ArtifactKind, ArtifactVersion
from apps.operations.models import AdminActionAuditLog

from ._command_schemas_editor_fixtures import client, staff_user  # noqa: F401


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
