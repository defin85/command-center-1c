from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..models import Cluster, Database


class PermissionService:
    """
    Centralized permission checking for databases and clusters.

    Resolution order:
    1. Staff -> Full access (ADMIN level)
    2. DatabasePermission (direct) -> Use if exists
    3. ClusterPermission (inherited) -> Use if database has cluster
    4. No permission -> Deny (None)

    Final level = max(database_level, cluster_level)

    OPTIMIZED: Uses batch loading to avoid N+1 queries.
    """

    @classmethod
    def _get_group_permission_maps(
        cls,
        user,
        database_ids: List[str] = None,
        cluster_ids: List[str] = None,
    ) -> Tuple[Dict[str, int], Dict[str, int]]:
        """
        Load all group-based permissions for user in batch.

        Returns:
            (database_permissions, cluster_permissions) - dicts mapping ID to max level
        """
        from django.db.models import Max
        from ..models import ClusterGroupPermission, DatabaseGroupPermission

        db_permissions: Dict[str, int] = {}
        cluster_permissions: Dict[str, int] = {}

        if database_ids:
            db_perms = (
                DatabaseGroupPermission.objects.filter(
                    group__user=user,
                    database_id__in=database_ids,
                )
                .values("database_id")
                .annotate(level=Max("level"))
                .values_list("database_id", "level")
            )
            db_permissions = {str(db_id): level for db_id, level in db_perms if level is not None}

        if cluster_ids:
            cluster_perms = (
                ClusterGroupPermission.objects.filter(
                    group__user=user,
                    cluster_id__in=cluster_ids,
                )
                .values("cluster_id")
                .annotate(level=Max("level"))
                .values_list("cluster_id", "level")
            )
            cluster_permissions = {str(c_id): level for c_id, level in cluster_perms if level is not None}

        return db_permissions, cluster_permissions

    @classmethod
    def _get_user_permission_maps(
        cls,
        user,
        database_ids: List[str] = None,
        cluster_ids: List[str] = None,
    ) -> Tuple[Dict[str, int], Dict[str, int]]:
        """
        Load all permissions for user in batch.

        Returns:
            (database_permissions, cluster_permissions) - dicts mapping ID to level
        """
        from ..models import ClusterPermission, DatabasePermission

        db_permissions: Dict[str, int] = {}
        cluster_permissions: Dict[str, int] = {}

        # Load database permissions in one query
        if database_ids:
            db_perms = DatabasePermission.objects.filter(
                user=user,
                database_id__in=database_ids,
            ).values_list("database_id", "level")

            db_permissions = {str(db_id): level for db_id, level in db_perms}

        # Load cluster permissions in one query
        if cluster_ids:
            cluster_perms = ClusterPermission.objects.filter(
                user=user,
                cluster_id__in=cluster_ids,
            ).values_list("cluster_id", "level")

            cluster_permissions = {str(c_id): level for c_id, level in cluster_perms}

        return db_permissions, cluster_permissions

    @classmethod
    def get_user_levels_for_databases_bulk(
        cls,
        user,
        databases: List[Database],
    ) -> Dict[str, Optional[int]]:
        """
        Get permission levels for multiple databases in batch (2-3 queries total).

        Args:
            user: User instance
            databases: List of Database instances (must have cluster_id loaded)

        Returns:
            Dict mapping database_id (str) to permission level (int or None)
        """
        from ..models import PermissionLevel

        if user.is_staff:
            return {str(db.id): PermissionLevel.ADMIN for db in databases}

        # Collect IDs
        database_ids = [str(db.id) for db in databases]
        cluster_ids = list({str(db.cluster_id) for db in databases if db.cluster_id is not None})

        # Batch load permissions (2 queries)
        db_perms, cluster_perms = cls._get_user_permission_maps(user, database_ids, cluster_ids)

        # Batch load group permissions (2 queries)
        group_db_perms, group_cluster_perms = cls._get_group_permission_maps(user, database_ids, cluster_ids)

        # Calculate effective levels
        result: Dict[str, Optional[int]] = {}
        for db in databases:
            db_id = str(db.id)
            levels = []

            # Direct database permission
            if db_id in db_perms:
                levels.append(db_perms[db_id])

            # Group database permission
            if db_id in group_db_perms:
                levels.append(group_db_perms[db_id])

            # Inherited cluster permission
            if db.cluster_id:
                cluster_id = str(db.cluster_id)
                if cluster_id in cluster_perms:
                    levels.append(cluster_perms[cluster_id])
                if cluster_id in group_cluster_perms:
                    levels.append(group_cluster_perms[cluster_id])

            result[db_id] = max(levels) if levels else None

        return result

    @classmethod
    def get_user_level_for_database(
        cls,
        user,
        database: Database,
    ) -> Optional[int]:
        """
        Get effective permission level for user on database.

        Returns:
            Permission level (int) or None if no access
        """
        # For single database, use bulk method with list of one
        levels = cls.get_user_levels_for_databases_bulk(user, [database])
        return levels.get(str(database.id))

    @classmethod
    def get_user_level_for_cluster(
        cls,
        user,
        cluster: Cluster,
    ) -> Optional[int]:
        """Get permission level for user on cluster."""
        from django.db.models import Max
        from ..models import ClusterGroupPermission, ClusterPermission, PermissionLevel

        if user.is_staff:
            return PermissionLevel.ADMIN

        direct_level = (
            ClusterPermission.objects.filter(
                user=user,
                cluster=cluster,
            )
            .values_list("level", flat=True)
            .first()
        )

        group_level = (
            ClusterGroupPermission.objects.filter(
                group__user=user,
                cluster=cluster,
            )
            .aggregate(level=Max("level"))
            .get("level")
        )

        levels = [lvl for lvl in [direct_level, group_level] if lvl is not None]
        return max(levels) if levels else None

    @classmethod
    def has_cluster_permission(
        cls,
        user,
        cluster: Cluster,
        required_level: int,
        allow_database_permissions: bool = False,
    ) -> bool:
        from django.db.models import Max
        from ..models import (
            ClusterGroupPermission,
            ClusterPermission,
            DatabaseGroupPermission,
            DatabasePermission,
        )

        if user.is_staff:
            return True

        level = (
            ClusterPermission.objects.filter(
                user=user,
                cluster=cluster,
            )
            .values_list("level", flat=True)
            .first()
        )

        group_level = (
            ClusterGroupPermission.objects.filter(
                group__user=user,
                cluster=cluster,
            )
            .aggregate(level=Max("level"))
            .get("level")
        )

        effective_levels = [lvl for lvl in [level, group_level] if lvl is not None]
        effective_level = max(effective_levels) if effective_levels else None

        if effective_level is not None and effective_level >= required_level:
            return True

        if allow_database_permissions:
            if DatabasePermission.objects.filter(
                user=user,
                level__gte=required_level,
                database__cluster=cluster,
            ).exists():
                return True

            if DatabaseGroupPermission.objects.filter(
                group__user=user,
                level__gte=required_level,
                database__cluster=cluster,
            ).exists():
                return True

        return False

    @classmethod
    def has_permission(
        cls,
        user,
        database: Database,
        required_level: int,
    ) -> bool:
        """Check if user has required level on database."""
        user_level = cls.get_user_level_for_database(user, database)
        return user_level is not None and user_level >= required_level

    @classmethod
    def filter_accessible_databases(
        cls,
        user,
        queryset,
        min_level: int = None,
    ):
        """
        Filter queryset to only databases user can access.

        Usage:
            qs = Database.objects.all()
            qs = PermissionService.filter_accessible_databases(user, qs)
        """
        from django.db.models import Q
        from ..models import (
            ClusterGroupPermission,
            ClusterPermission,
            DatabaseGroupPermission,
            DatabasePermission,
            PermissionLevel,
        )

        if min_level is None:
            min_level = PermissionLevel.VIEW

        if user.is_staff:
            return queryset

        # Get database IDs with direct permission
        db_ids = DatabasePermission.objects.filter(
            user=user,
            level__gte=min_level,
        ).values_list("database_id", flat=True)

        # Group database permissions
        group_db_ids = DatabaseGroupPermission.objects.filter(
            group__user=user,
            level__gte=min_level,
        ).values_list("database_id", flat=True)

        # Get cluster IDs with permission
        cluster_ids = ClusterPermission.objects.filter(
            user=user,
            level__gte=min_level,
        ).values_list("cluster_id", flat=True)

        group_cluster_ids = ClusterGroupPermission.objects.filter(
            group__user=user,
            level__gte=min_level,
        ).values_list("cluster_id", flat=True)

        return queryset.filter(
            Q(id__in=db_ids) | Q(id__in=group_db_ids) | Q(cluster_id__in=cluster_ids) | Q(cluster_id__in=group_cluster_ids)
        )

    @classmethod
    def filter_accessible_clusters(
        cls,
        user,
        queryset,
        min_level: int = None,
    ):
        from django.db.models import Q
        from ..models import (
            ClusterGroupPermission,
            ClusterPermission,
            DatabaseGroupPermission,
            DatabasePermission,
            PermissionLevel,
        )

        if min_level is None:
            min_level = PermissionLevel.VIEW

        if user.is_staff:
            return queryset

        cluster_ids = ClusterPermission.objects.filter(
            user=user,
            level__gte=min_level,
        ).values_list("cluster_id", flat=True)

        group_cluster_ids = ClusterGroupPermission.objects.filter(
            group__user=user,
            level__gte=min_level,
        ).values_list("cluster_id", flat=True)

        db_cluster_ids = DatabasePermission.objects.filter(
            user=user,
            level__gte=min_level,
            database__cluster_id__isnull=False,
        ).values_list("database__cluster_id", flat=True)

        group_db_cluster_ids = DatabaseGroupPermission.objects.filter(
            group__user=user,
            level__gte=min_level,
            database__cluster_id__isnull=False,
        ).values_list("database__cluster_id", flat=True)

        return queryset.filter(
            Q(id__in=cluster_ids) | Q(id__in=group_cluster_ids) | Q(id__in=db_cluster_ids) | Q(id__in=group_db_cluster_ids)
        ).distinct()

    @classmethod
    def check_bulk_permission(
        cls,
        user,
        database_ids: List[str],
        required_level: int,
    ) -> Tuple[bool, List[str]]:
        """
        Check permission for multiple databases (OPTIMIZED - O(3) queries).

        Returns:
            (all_allowed: bool, denied_ids: List[str])
        """
        if user.is_staff:
            return True, []

        # Fetch databases with cluster info (1 query)
        databases = list(
            Database.objects.filter(
                id__in=database_ids,
            )
            .select_related("cluster")
            .only("id", "cluster_id")
        )

        # Batch check permissions (2 queries)
        levels = cls.get_user_levels_for_databases_bulk(user, databases)

        # Find denied
        denied = []
        found_ids = set()

        for db in databases:
            db_id = str(db.id)
            found_ids.add(db_id)

            level = levels.get(db_id)
            if level is None or level < required_level:
                denied.append(db_id)

        # Check for missing/invalid database IDs
        for db_id in database_ids:
            if str(db_id) not in found_ids:
                denied.append(str(db_id))

        return len(denied) == 0, denied

