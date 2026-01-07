import pytest
from django.contrib.auth.models import Group, User

from apps.databases.models import (
    Cluster,
    ClusterGroupPermission,
    Database,
    DatabaseGroupPermission,
    PermissionLevel,
)
from apps.databases.services import PermissionService


@pytest.mark.django_db
def test_group_cluster_permission_grants_database_access():
    group = Group.objects.create(name="ops")
    user = User.objects.create_user(username="u", password="pass")
    user.groups.add(group)

    cluster = Cluster.objects.create(
        name="c",
        ras_server="localhost:1545",
        cluster_service_url="http://localhost:8188",
    )
    database = Database.objects.create(
        id="db-1",
        name="db",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
        cluster=cluster,
    )

    ClusterGroupPermission.objects.create(
        group=group,
        cluster=cluster,
        level=PermissionLevel.OPERATE,
        notes="",
    )

    assert PermissionService.get_user_level_for_cluster(user, cluster) == PermissionLevel.OPERATE
    assert PermissionService.get_user_level_for_database(user, database) == PermissionLevel.OPERATE
    assert PermissionService.has_permission(user, database, PermissionLevel.OPERATE) is True

    allowed, denied = PermissionService.check_bulk_permission(
        user, [str(database.id)], PermissionLevel.OPERATE
    )
    assert allowed is True
    assert denied == []


@pytest.mark.django_db
def test_group_database_permission_wins_over_group_cluster_permission():
    group = Group.objects.create(name="ops")
    user = User.objects.create_user(username="u", password="pass")
    user.groups.add(group)

    cluster = Cluster.objects.create(
        name="c",
        ras_server="localhost:1545",
        cluster_service_url="http://localhost:8188",
    )
    database = Database.objects.create(
        id="db-1",
        name="db",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
        cluster=cluster,
    )

    ClusterGroupPermission.objects.create(
        group=group,
        cluster=cluster,
        level=PermissionLevel.VIEW,
        notes="",
    )
    DatabaseGroupPermission.objects.create(
        group=group,
        database=database,
        level=PermissionLevel.MANAGE,
        notes="",
    )

    assert PermissionService.get_user_level_for_database(user, database) == PermissionLevel.MANAGE

