import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.artifacts.models import Artifact, ArtifactKind, ArtifactPurgeState


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        username="admin_support_restore",
        password="pass",
        email="admin-support@example.com",
    )


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.mark.django_db
def test_users_list_filters_by_exact_id(admin_client):
    target = User.objects.create_user(username="selected-admin-user", password="pass")
    User.objects.create_user(username="other-admin-user", password="pass")

    response = admin_client.get("/api/v2/users/list/", {"id": target.id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["total"] == 1
    assert [item["id"] for item in payload["users"]] == [target.id]


@pytest.mark.django_db
def test_artifacts_list_filters_by_exact_artifact_id_for_deleted_catalog(admin_client, admin_user):
    target = Artifact.objects.create(
        name="restore-target",
        kind=ArtifactKind.OTHER,
        is_versioned=True,
        tags=["restore"],
        is_deleted=True,
        purge_state=ArtifactPurgeState.SCHEDULED,
        created_by=admin_user,
    )
    Artifact.objects.create(
        name="restore-other",
        kind=ArtifactKind.OTHER,
        is_versioned=True,
        tags=["other"],
        is_deleted=True,
        purge_state=ArtifactPurgeState.SCHEDULED,
        created_by=admin_user,
    )

    response = admin_client.get(
        "/api/v2/artifacts/",
        {
            "artifact_id": str(target.id),
            "include_deleted": "true",
            "only_deleted": "true",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert [item["id"] for item in payload["artifacts"]] == [str(target.id)]
