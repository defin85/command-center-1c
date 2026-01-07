import pytest
from django.contrib.auth.models import Group, User

from apps.artifacts.models import (
    Artifact,
    ArtifactAlias,
    ArtifactGroupPermission,
    ArtifactKind,
    ArtifactPermission,
    ArtifactVersion,
)
from apps.artifacts.rbac import ArtifactPermissionService
from apps.databases.models import PermissionLevel


@pytest.mark.django_db
def test_group_artifact_permission_inherits_to_versions_and_aliases():
    group = Group.objects.create(name="art_ops")
    user = User.objects.create_user(username="u", password="pass")
    user.groups.add(group)

    artifact = Artifact.objects.create(
        name="A",
        kind=ArtifactKind.EXTENSION,
        is_versioned=True,
    )
    version = ArtifactVersion.objects.create(
        artifact=artifact,
        version="v1",
        filename="a.cfe",
        storage_key="artifacts/a/v1/a.cfe",
        size=1,
        checksum="deadbeef",
        content_type="application/octet-stream",
    )
    alias = ArtifactAlias.objects.create(
        artifact=artifact,
        alias="current",
        version=version,
    )

    ArtifactGroupPermission.objects.create(
        group=group,
        artifact=artifact,
        level=PermissionLevel.OPERATE,
        notes="",
    )

    assert (
        ArtifactPermissionService.get_user_level_for_artifact(user, artifact)
        == PermissionLevel.OPERATE
    )
    assert (
        ArtifactPermissionService.get_user_level_for_artifact_version(user, version)
        == PermissionLevel.OPERATE
    )
    assert (
        ArtifactPermissionService.get_user_level_for_artifact_alias(user, alias)
        == PermissionLevel.OPERATE
    )


@pytest.mark.django_db
def test_user_artifact_permission_inherits_to_versions_and_aliases():
    user = User.objects.create_user(username="u", password="pass")

    artifact = Artifact.objects.create(
        name="A",
        kind=ArtifactKind.EXTENSION,
        is_versioned=True,
    )
    version = ArtifactVersion.objects.create(
        artifact=artifact,
        version="v1",
        filename="a.cfe",
        storage_key="artifacts/a/v1/a.cfe",
        size=1,
        checksum="deadbeef",
        content_type="application/octet-stream",
    )
    alias = ArtifactAlias.objects.create(
        artifact=artifact,
        alias="current",
        version=version,
    )

    ArtifactPermission.objects.create(
        user=user,
        artifact=artifact,
        level=PermissionLevel.OPERATE,
        notes="",
    )

    assert (
        ArtifactPermissionService.get_user_level_for_artifact(user, artifact)
        == PermissionLevel.OPERATE
    )
    assert (
        ArtifactPermissionService.get_user_level_for_artifact_version(user, version)
        == PermissionLevel.OPERATE
    )
    assert (
        ArtifactPermissionService.get_user_level_for_artifact_alias(user, alias)
        == PermissionLevel.OPERATE
    )


@pytest.mark.django_db
def test_filter_accessible_artifacts_versions_aliases():
    group = Group.objects.create(name="art_ops")
    user = User.objects.create_user(username="u", password="pass")
    user.groups.add(group)

    group_artifact = Artifact.objects.create(
        name="A",
        kind=ArtifactKind.EXTENSION,
        is_versioned=True,
    )
    user_artifact = Artifact.objects.create(
        name="B",
        kind=ArtifactKind.EXTENSION,
        is_versioned=True,
    )
    denied_artifact = Artifact.objects.create(
        name="C",
        kind=ArtifactKind.EXTENSION,
        is_versioned=True,
    )

    version_a = ArtifactVersion.objects.create(
        artifact=group_artifact,
        version="v1",
        filename="a.cfe",
        storage_key="artifacts/a/v1/a.cfe",
        size=1,
        checksum="deadbeef",
        content_type="application/octet-stream",
    )
    version_b = ArtifactVersion.objects.create(
        artifact=user_artifact,
        version="v1",
        filename="b.cfe",
        storage_key="artifacts/b/v1/b.cfe",
        size=1,
        checksum="deadbeef",
        content_type="application/octet-stream",
    )
    version_c = ArtifactVersion.objects.create(
        artifact=denied_artifact,
        version="v1",
        filename="c.cfe",
        storage_key="artifacts/c/v1/c.cfe",
        size=1,
        checksum="deadbeef",
        content_type="application/octet-stream",
    )
    alias_a = ArtifactAlias.objects.create(
        artifact=group_artifact,
        alias="current",
        version=version_a,
    )
    alias_b = ArtifactAlias.objects.create(
        artifact=user_artifact,
        alias="current",
        version=version_b,
    )
    alias_c = ArtifactAlias.objects.create(
        artifact=denied_artifact,
        alias="current",
        version=version_c,
    )

    ArtifactGroupPermission.objects.create(
        group=group,
        artifact=group_artifact,
        level=PermissionLevel.VIEW,
        notes="",
    )
    ArtifactPermission.objects.create(
        user=user,
        artifact=user_artifact,
        level=PermissionLevel.VIEW,
        notes="",
    )

    artifacts_qs = ArtifactPermissionService.filter_accessible_artifacts(
        user, Artifact.objects.all(), min_level=PermissionLevel.VIEW
    )
    assert artifacts_qs.filter(id=group_artifact.id).exists()
    assert artifacts_qs.filter(id=user_artifact.id).exists()
    assert artifacts_qs.filter(id=denied_artifact.id).exists() is False

    versions_qs = ArtifactPermissionService.filter_accessible_artifact_versions(
        user, ArtifactVersion.objects.all(), min_level=PermissionLevel.VIEW
    )
    assert versions_qs.filter(id=version_a.id).exists()
    assert versions_qs.filter(id=version_b.id).exists()
    assert versions_qs.filter(id=version_c.id).exists() is False

    aliases_qs = ArtifactPermissionService.filter_accessible_artifact_aliases(
        user, ArtifactAlias.objects.all(), min_level=PermissionLevel.VIEW
    )
    assert aliases_qs.filter(id=alias_a.id).exists()
    assert aliases_qs.filter(id=alias_b.id).exists()
    assert aliases_qs.filter(id=alias_c.id).exists() is False


@pytest.mark.django_db
def test_effective_level_is_max_of_user_and_group():
    group = Group.objects.create(name="art_ops")
    user = User.objects.create_user(username="u", password="pass")
    user.groups.add(group)

    artifact = Artifact.objects.create(
        name="A",
        kind=ArtifactKind.EXTENSION,
        is_versioned=True,
    )

    ArtifactGroupPermission.objects.create(
        group=group,
        artifact=artifact,
        level=PermissionLevel.OPERATE,
        notes="",
    )
    user_perm = ArtifactPermission.objects.create(
        user=user,
        artifact=artifact,
        level=PermissionLevel.VIEW,
        notes="",
    )

    assert (
        ArtifactPermissionService.get_user_level_for_artifact(user, artifact)
        == PermissionLevel.OPERATE
    )

    user_perm.level = PermissionLevel.MANAGE
    user_perm.save(update_fields=["level"])

    assert (
        ArtifactPermissionService.get_user_level_for_artifact(user, artifact)
        == PermissionLevel.MANAGE
    )
