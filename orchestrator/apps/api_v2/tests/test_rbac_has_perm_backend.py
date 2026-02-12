import pytest
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType

from apps.artifacts.models import Artifact, ArtifactKind, ArtifactVersion
from apps.databases.models import (
    Cluster,
    Database,
    DatabaseGroupPermission,
    PermissionLevel,
)
from apps.templates.models import (
    OperationDefinition,
    OperationExposure,
    OperationExposureGroupPermission,
    WorkflowTemplateGroupPermission,
)
from apps.templates.workflow.models import WorkflowTemplate


def _grant_group_permission(group: Group, app_label: str, model: str, codename: str) -> None:
    ct = ContentType.objects.get(app_label=app_label, model=model)
    perm = Permission.objects.get(content_type=ct, codename=codename)
    group.permissions.add(perm)


def _reload_user(user: User) -> User:
    # ModelBackend caches permissions on the user instance; reload to avoid stale caches.
    return User.objects.get(pk=user.pk)


def _create_template_exposure(template_id: str) -> OperationExposure:
    definition = OperationDefinition.objects.create(
        tenant_scope="global",
        executor_kind=OperationDefinition.EXECUTOR_IBCMD_CLI,
        executor_payload={
            "operation_type": "noop",
            "target_entity": "db",
            "template_data": {},
        },
        contract_version=1,
        fingerprint=f"fp-{template_id}",
        status=OperationDefinition.STATUS_ACTIVE,
    )
    return OperationExposure.objects.create(
        definition=definition,
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias=template_id,
        tenant=None,
        label=template_id,
        description="",
        is_active=True,
        capability="",
        contexts=[],
        display_order=0,
        capability_config={},
        status=OperationExposure.STATUS_PUBLISHED,
    )


@pytest.mark.django_db
def test_has_perm_database_requires_capability_and_scope():
    group = Group.objects.create(name="db_ops")
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

    DatabaseGroupPermission.objects.create(
        group=group,
        database=database,
        level=PermissionLevel.VIEW,
        notes="",
    )

    assert user.has_perm("databases.view_database", database) is False

    _grant_group_permission(group, "databases", "database", "view_database")
    user = _reload_user(user)
    assert user.has_perm("databases.view_database", database) is True

    _grant_group_permission(group, "databases", "database", "manage_database")
    user = _reload_user(user)
    assert user.has_perm("databases.manage_database", database) is False

    DatabaseGroupPermission.objects.filter(group=group, database=database).update(
        level=PermissionLevel.MANAGE
    )
    assert user.has_perm("databases.manage_database", database) is True


@pytest.mark.django_db
def test_has_perm_view_cluster_allows_database_permissions_when_enabled():
    group = Group.objects.create(name="cluster_viewers")
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

    DatabaseGroupPermission.objects.create(
        group=group,
        database=database,
        level=PermissionLevel.VIEW,
        notes="",
    )

    _grant_group_permission(group, "databases", "cluster", "view_cluster")
    user = _reload_user(user)
    assert user.has_perm("databases.view_cluster", cluster) is True


@pytest.mark.django_db
def test_has_perm_operation_template_requires_capability_and_scope():
    group = Group.objects.create(name="tpl_ops")
    user = User.objects.create_user(username="u", password="pass")
    user.groups.add(group)

    template_id = "tpl-1"
    exposure = _create_template_exposure(template_id)
    OperationExposureGroupPermission.objects.create(
        group=group,
        exposure=exposure,
        level=PermissionLevel.VIEW,
        notes="",
    )

    _grant_group_permission(group, "templates", "operationtemplate", "view_operationtemplate")
    user = _reload_user(user)
    assert user.has_perm("templates.view_operationtemplate", exposure) is True

    _grant_group_permission(group, "templates", "operationtemplate", "manage_operation_template")
    user = _reload_user(user)
    assert user.has_perm("templates.manage_operation_template", exposure) is False

    OperationExposureGroupPermission.objects.filter(group=group, exposure=exposure).update(
        level=PermissionLevel.MANAGE
    )
    assert user.has_perm("templates.manage_operation_template", exposure) is True


@pytest.mark.django_db
def test_has_perm_execute_workflow_template_requires_operate_level():
    group = Group.objects.create(name="wf_ops")
    user = User.objects.create_user(username="u", password="pass")
    user.groups.add(group)

    workflow = WorkflowTemplate.objects.create(
        name="WF",
        description="",
        workflow_type="sequential",
        dag_structure={
            "nodes": [
                {
                    "id": "start",
                    "name": "Start",
                    "type": "operation",
                    "template_id": "noop",
                    "config": {},
                }
            ],
            "edges": [],
        },
        config={},
        is_valid=True,
        is_active=True,
    )

    WorkflowTemplateGroupPermission.objects.create(
        group=group,
        workflow_template=workflow,
        level=PermissionLevel.VIEW,
        notes="",
    )

    _grant_group_permission(group, "templates", "workflowtemplate", "execute_workflow_template")
    user = _reload_user(user)
    assert user.has_perm("templates.execute_workflow_template", workflow) is False

    WorkflowTemplateGroupPermission.objects.filter(group=group, workflow_template=workflow).update(
        level=PermissionLevel.OPERATE
    )
    assert user.has_perm("templates.execute_workflow_template", workflow) is True


@pytest.mark.django_db
def test_has_perm_download_artifact_version_resolves_via_artifact_scope():
    group = Group.objects.create(name="art_viewers")
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

    from apps.artifacts.models import ArtifactGroupPermission

    ArtifactGroupPermission.objects.create(
        group=group,
        artifact=artifact,
        level=PermissionLevel.VIEW,
        notes="",
    )

    _grant_group_permission(group, "artifacts", "artifactversion", "download_artifact_version")
    user = _reload_user(user)
    assert user.has_perm("artifacts.download_artifact_version", version) is True


@pytest.mark.django_db
def test_has_perm_unknown_object_mapping_denies_for_rbac_apps():
    group = Group.objects.create(name="rbac_admins")
    user = User.objects.create_user(username="u", password="pass")
    user.groups.add(group)

    cluster = Cluster.objects.create(
        name="c",
        ras_server="localhost:1545",
        cluster_service_url="http://localhost:8188",
    )

    _grant_group_permission(group, "databases", "clusterpermission", "manage_rbac")
    user = _reload_user(user)

    assert user.has_perm("databases.manage_rbac") is True
    assert user.has_perm("databases.manage_rbac", cluster) is False
