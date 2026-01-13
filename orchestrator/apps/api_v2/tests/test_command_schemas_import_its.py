import pytest
from django.contrib.auth.models import Permission, User
from rest_framework.test import APIClient

from apps.artifacts.models import Artifact, ArtifactKind
from apps.artifacts.storage import ArtifactStorageClient

@pytest.fixture
def staff_user():
    user = User.objects.create_user(username="command_schemas_admin", password="pass")
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
def test_command_schemas_import_its_ibcmd_uploads_base_catalog_artifact(client, monkeypatch):
    monkeypatch.setattr(ArtifactStorageClient, "upload_object", lambda *args, **kwargs: None)

    resp = client.post(
        "/api/v2/settings/command-schemas/import-its/",
        data={
            "driver": "ibcmd",
            "its_payload": {"version": "8.3.27", "sections": []},
            "save": True,
            "reason": "test import",
        },
        format="json",
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["driver"] == "ibcmd"
    assert payload["catalog"]["catalog_version"] == 2

    base = Artifact.objects.get(name="driver_catalog.ibcmd.base", kind=ArtifactKind.DRIVER_CATALOG)
    assert base.versions.count() == 1
    assert base.aliases.filter(alias="latest").exists()
    assert base.aliases.filter(alias="approved").exists()

    overrides = Artifact.objects.get(name="driver_catalog.ibcmd.overrides", kind=ArtifactKind.DRIVER_CATALOG)
    assert overrides.versions.count() == 1
    assert overrides.aliases.filter(alias="active").exists()


@pytest.mark.django_db
def test_command_schemas_import_its_cli_uploads_base_catalog_artifact(client, monkeypatch):
    monkeypatch.setattr(ArtifactStorageClient, "upload_object", lambda *args, **kwargs: None)

    resp = client.post(
        "/api/v2/settings/command-schemas/import-its/",
        data={
            "driver": "cli",
            "its_payload": {
                "version": "8.3.27",
                "sections": [{"title": "any", "text": "/AccessToken\n\nGet token.\n"}],
            },
            "save": True,
            "reason": "test import",
        },
        format="json",
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["driver"] == "cli"

    base = Artifact.objects.get(name="driver_catalog.cli.base", kind=ArtifactKind.DRIVER_CATALOG)
    assert base.versions.count() == 1
    assert base.aliases.filter(alias="latest").exists()
    assert base.aliases.filter(alias="approved").exists()

    overrides = Artifact.objects.get(name="driver_catalog.cli.overrides", kind=ArtifactKind.DRIVER_CATALOG)
    assert overrides.versions.count() == 1
    assert overrides.aliases.filter(alias="active").exists()


@pytest.mark.django_db
def test_command_schemas_import_its_does_not_move_approved_when_already_set(client, monkeypatch):
    monkeypatch.setattr(ArtifactStorageClient, "upload_object", lambda *args, **kwargs: None)

    resp1 = client.post(
        "/api/v2/settings/command-schemas/import-its/",
        data={
            "driver": "cli",
            "its_payload": {
                "version": "8.3.27",
                "sections": [{"title": "any", "text": "/AccessToken\n\nGet token.\n"}],
            },
            "save": True,
            "reason": "initial import",
        },
        format="json",
    )
    assert resp1.status_code == 200

    base = Artifact.objects.get(name="driver_catalog.cli.base", kind=ArtifactKind.DRIVER_CATALOG)
    approved_v1 = base.aliases.select_related("version").get(alias="approved").version
    latest_v1 = base.aliases.select_related("version").get(alias="latest").version

    resp2 = client.post(
        "/api/v2/settings/command-schemas/import-its/",
        data={
            "driver": "cli",
            "its_payload": {
                "version": "8.3.28",
                "sections": [{"title": "any", "text": "/AccessToken\n\nGet token.\n"}],
            },
            "save": True,
            "reason": "second import",
        },
        format="json",
    )
    assert resp2.status_code == 200

    base.refresh_from_db()
    approved_v2 = base.aliases.select_related("version").get(alias="approved").version
    latest_v2 = base.aliases.select_related("version").get(alias="latest").version

    assert approved_v2.id == approved_v1.id
    assert latest_v2.id != latest_v1.id
