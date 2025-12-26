import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.artifacts.models import Artifact, ArtifactKind, ArtifactVersion
from apps.artifacts.storage import ArtifactStorageClient


@pytest.mark.django_db
def test_artifact_list_requires_staff(regular_client):
    resp = regular_client.get("/api/v2/artifacts/")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_create_artifact_duplicate_name(staff_client):
    payload = {"name": "CoreExt", "kind": ArtifactKind.EXTENSION, "is_versioned": True}
    resp = staff_client.post("/api/v2/artifacts/create/", payload, format="json")
    assert resp.status_code == 201

    dup_resp = staff_client.post("/api/v2/artifacts/create/", payload, format="json")
    assert dup_resp.status_code == 400
    assert dup_resp.json()["error"]["code"] == "DUPLICATE"


@pytest.mark.django_db
def test_upload_version_rejects_duplicate_filename(staff_client, monkeypatch):
    artifact_one = Artifact.objects.create(
        name="ExtOne",
        kind=ArtifactKind.EXTENSION,
        is_versioned=True,
    )
    artifact_two = Artifact.objects.create(
        name="ExtTwo",
        kind=ArtifactKind.EXTENSION,
        is_versioned=True,
    )

    monkeypatch.setattr(ArtifactStorageClient, "upload_object", lambda *args, **kwargs: None)

    file_one = SimpleUploadedFile(
        name="shared.cfe",
        content=b"file-one",
        content_type="application/octet-stream",
    )
    resp_one = staff_client.post(
        f"/api/v2/artifacts/{artifact_one.id}/versions/upload/",
        {"file": file_one},
        format="multipart",
    )
    assert resp_one.status_code == 201

    file_two = SimpleUploadedFile(
        name="shared.cfe",
        content=b"file-two",
        content_type="application/octet-stream",
    )
    resp_two = staff_client.post(
        f"/api/v2/artifacts/{artifact_two.id}/versions/upload/",
        {"file": file_two},
        format="multipart",
    )
    assert resp_two.status_code == 400
    assert resp_two.json()["error"]["code"] == "FILENAME_EXISTS"


@pytest.mark.django_db
def test_non_versioned_artifact_allows_single_version(staff_client, monkeypatch):
    artifact = Artifact.objects.create(
        name="OneShot",
        kind=ArtifactKind.EXTENSION,
        is_versioned=False,
    )

    monkeypatch.setattr(ArtifactStorageClient, "upload_object", lambda *args, **kwargs: None)

    first_file = SimpleUploadedFile(
        name="oneshot.cfe",
        content=b"first",
        content_type="application/octet-stream",
    )
    first_resp = staff_client.post(
        f"/api/v2/artifacts/{artifact.id}/versions/upload/",
        {"file": first_file},
        format="multipart",
    )
    assert first_resp.status_code == 201

    second_file = SimpleUploadedFile(
        name="oneshot-2.cfe",
        content=b"second",
        content_type="application/octet-stream",
    )
    second_resp = staff_client.post(
        f"/api/v2/artifacts/{artifact.id}/versions/upload/",
        {"file": second_file},
        format="multipart",
    )
    assert second_resp.status_code == 400
    assert second_resp.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_download_artifact_version(staff_client, monkeypatch):
    artifact = Artifact.objects.create(
        name="Downloadable",
        kind=ArtifactKind.EXTENSION,
        is_versioned=True,
    )
    version = ArtifactVersion.objects.create(
        artifact=artifact,
        version="v1",
        filename="download.cfe",
        storage_key="artifacts/test/download.cfe",
        size=4,
        checksum="deadbeef",
        content_type="application/octet-stream",
    )

    monkeypatch.setattr(
        ArtifactStorageClient,
        "get_object",
        lambda *args, **kwargs: io.BytesIO(b"DATA"),
    )

    resp = staff_client.get(
        f"/api/v2/artifacts/{artifact.id}/versions/{version.version}/download/"
    )
    assert resp.status_code == 200
    body = b"".join(resp.streaming_content)
    assert body == b"DATA"
