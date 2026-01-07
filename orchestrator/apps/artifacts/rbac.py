from typing import Optional

from django.db.models import Max, Q

from apps.databases.models import PermissionLevel
from apps.artifacts.models import (
    Artifact,
    ArtifactAlias,
    ArtifactGroupPermission,
    ArtifactPermission,
    ArtifactVersion,
)


class ArtifactPermissionService:
    """
    Scope/level resolution for artifacts.

    This service does NOT check Django capabilities (user.has_perm).
    It only resolves "what objects this user can access" and at what PermissionLevel.

    Inheritance:
    - Artifact -> ArtifactVersion / ArtifactAlias
    """

    @classmethod
    def get_user_level_for_artifact(
        cls,
        user,
        artifact: Artifact,
    ) -> Optional[int]:
        if not user or not getattr(user, "is_authenticated", False):
            return None
        if getattr(user, "is_staff", False):
            return PermissionLevel.ADMIN

        user_level = ArtifactPermission.objects.filter(
            user=user,
            artifact=artifact,
        ).values_list("level", flat=True).first()

        group_level = (
            ArtifactGroupPermission.objects.filter(
                group__user=user,
                artifact=artifact,
            )
            .aggregate(level=Max("level"))
            .get("level")
        )
        levels = [lvl for lvl in [user_level, group_level] if lvl is not None]
        return max(levels) if levels else None

    @classmethod
    def get_user_level_for_artifact_version(
        cls,
        user,
        version: ArtifactVersion,
    ) -> Optional[int]:
        return cls.get_user_level_for_artifact(user, version.artifact)

    @classmethod
    def get_user_level_for_artifact_alias(
        cls,
        user,
        alias: ArtifactAlias,
    ) -> Optional[int]:
        return cls.get_user_level_for_artifact(user, alias.artifact)

    @classmethod
    def has_artifact_access(
        cls,
        user,
        artifact: Artifact,
        required_level: int,
    ) -> bool:
        level = cls.get_user_level_for_artifact(user, artifact)
        return level is not None and level >= required_level

    @classmethod
    def filter_accessible_artifacts(
        cls,
        user,
        queryset,
        min_level: int = None,
    ):
        if min_level is None:
            min_level = PermissionLevel.VIEW
        if not user or not getattr(user, "is_authenticated", False):
            return queryset.none()
        if getattr(user, "is_staff", False):
            return queryset

        user_artifact_ids = ArtifactPermission.objects.filter(
            user=user,
            level__gte=min_level,
        ).values_list("artifact_id", flat=True)
        group_artifact_ids = ArtifactGroupPermission.objects.filter(
            group__user=user,
            level__gte=min_level,
        ).values_list("artifact_id", flat=True)
        return queryset.filter(Q(id__in=user_artifact_ids) | Q(id__in=group_artifact_ids))

    @classmethod
    def filter_accessible_artifact_versions(
        cls,
        user,
        queryset,
        min_level: int = None,
    ):
        if min_level is None:
            min_level = PermissionLevel.VIEW
        if not user or not getattr(user, "is_authenticated", False):
            return queryset.none()
        if getattr(user, "is_staff", False):
            return queryset

        user_artifact_ids = ArtifactPermission.objects.filter(
            user=user,
            level__gte=min_level,
        ).values_list("artifact_id", flat=True)
        group_artifact_ids = ArtifactGroupPermission.objects.filter(
            group__user=user,
            level__gte=min_level,
        ).values_list("artifact_id", flat=True)
        return queryset.filter(
            Q(artifact_id__in=user_artifact_ids) | Q(artifact_id__in=group_artifact_ids)
        )

    @classmethod
    def filter_accessible_artifact_aliases(
        cls,
        user,
        queryset,
        min_level: int = None,
    ):
        if min_level is None:
            min_level = PermissionLevel.VIEW
        if not user or not getattr(user, "is_authenticated", False):
            return queryset.none()
        if getattr(user, "is_staff", False):
            return queryset

        user_artifact_ids = ArtifactPermission.objects.filter(
            user=user,
            level__gte=min_level,
        ).values_list("artifact_id", flat=True)
        group_artifact_ids = ArtifactGroupPermission.objects.filter(
            group__user=user,
            level__gte=min_level,
        ).values_list("artifact_id", flat=True)
        return queryset.filter(
            Q(artifact_id__in=user_artifact_ids) | Q(artifact_id__in=group_artifact_ids)
        )
