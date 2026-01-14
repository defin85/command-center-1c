import pytest
from django.contrib.auth.models import Permission, User
from rest_framework.test import APIClient

from apps.artifacts.models import (
    Artifact,
    ArtifactAlias,
    ArtifactKind,
    ArtifactPermission,
    ArtifactPurgeJob,
    ArtifactPurgeJobMode,
    ArtifactPurgeJobStatus,
    ArtifactPurgeState,
    ArtifactVersion,
)
from apps.databases.models import PermissionLevel
from apps.operations.models import BatchOperation


@pytest.fixture
def user():
    return User.objects.create_user(username="u_artifacts_purge", password="pass")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _grant_capability(user: User, codename: str) -> None:
    perm = Permission.objects.get(content_type__app_label="artifacts", codename=codename)
    user.user_permissions.add(perm)


def _grant_artifact_admin(user: User, artifact: Artifact) -> None:
    ArtifactPermission.objects.create(
        user=user,
        artifact=artifact,
        level=PermissionLevel.ADMIN,
    )


@pytest.mark.django_db
def test_purge_requires_soft_delete(client, user):
    artifact = Artifact.objects.create(
        name="purge-me",
        kind=ArtifactKind.OTHER,
        is_versioned=True,
        tags=["t"],
        created_by=user,
    )
    _grant_artifact_admin(user, artifact)
    _grant_capability(user, "manage_artifact")
    _grant_capability(user, "purge_artifact")

    resp = client.post(f"/api/v2/artifacts/{artifact.id}/purge/", {"reason": "x"}, format="json")
    assert resp.status_code == 400
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "PURGE_NOT_ALLOWED"


@pytest.mark.django_db
def test_purge_is_blocked_when_in_use(client, user):
    artifact = Artifact.objects.create(
        name="purge-blocked",
        kind=ArtifactKind.OTHER,
        is_versioned=True,
        tags=["t"],
        is_deleted=True,
        purge_state=ArtifactPurgeState.SCHEDULED,
        created_by=user,
    )
    _grant_artifact_admin(user, artifact)
    _grant_capability(user, "manage_artifact")
    _grant_capability(user, "purge_artifact")

    version = ArtifactVersion.objects.create(
        artifact=artifact,
        version="v1",
        filename="purge-blocked-v1.txt",
        storage_key=f"artifacts/{artifact.id}/v1/purge-blocked-v1.txt",
        size=10,
        checksum="abc",
        content_type="text/plain",
        metadata={},
        created_by=user,
    )
    ArtifactAlias.objects.create(artifact=artifact, alias="latest", version=version)

    BatchOperation.objects.create(
        id="op_purge_blocked",
        name="purge blocked",
        description="",
        operation_type=BatchOperation.TYPE_IBCMD_CLI,
        target_entity="X",
        payload={"file": f"artifact://artifacts/{artifact.id}/v1/purge-blocked-v1.txt"},
        config={},
        status=BatchOperation.STATUS_PENDING,
        created_by="tester",
    )

    resp = client.post(f"/api/v2/artifacts/{artifact.id}/purge/", {"reason": "x"}, format="json")
    assert resp.status_code == 409
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "ARTIFACT_IN_USE"


@pytest.mark.django_db
def test_purge_creates_job_and_sets_running_state(client, user):
    artifact = Artifact.objects.create(
        name="purge-ok",
        kind=ArtifactKind.OTHER,
        is_versioned=True,
        tags=["t"],
        is_deleted=True,
        purge_state=ArtifactPurgeState.SCHEDULED,
        created_by=user,
    )
    _grant_artifact_admin(user, artifact)
    _grant_capability(user, "manage_artifact")
    _grant_capability(user, "purge_artifact")

    ArtifactVersion.objects.create(
        artifact=artifact,
        version="v1",
        filename="purge-ok-v1.txt",
        storage_key=f"artifacts/{artifact.id}/v1/purge-ok-v1.txt",
        size=10,
        checksum="abc",
        content_type="text/plain",
        metadata={},
        created_by=user,
    )

    resp = client.post(
        f"/api/v2/artifacts/{artifact.id}/purge/",
        {"reason": "cleanup"},
        format="json",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"]

    artifact.refresh_from_db()
    assert artifact.purge_state == ArtifactPurgeState.RUNNING

    job = ArtifactPurgeJob.objects.get(id=data["job_id"])
    assert str(job.artifact_id) == str(artifact.id)
    assert job.mode == ArtifactPurgeJobMode.MANUAL
    assert job.status == ArtifactPurgeJobStatus.QUEUED

