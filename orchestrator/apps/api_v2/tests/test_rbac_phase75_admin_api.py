import pytest
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from apps.artifacts.models import Artifact, ArtifactKind
from apps.databases.models import Cluster, Database
from apps.templates.models import OperationTemplate


def _grant_group_permission(group: Group, app_label: str, model: str, codename: str) -> None:
    ct = ContentType.objects.get(app_label=app_label, model=model)
    perm = Permission.objects.get(content_type=ct, codename=codename)
    group.permissions.add(perm)


@pytest.fixture
def cluster():
    return Cluster.objects.create(
        name="Test Cluster",
        ras_server="localhost:1545",
        cluster_service_url="http://localhost:8188",
    )


@pytest.fixture
def database(cluster):
    return Database.objects.create(
        id="db-1",
        name="test_db",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
        cluster=cluster,
    )


@pytest.fixture
def rbac_admin_client():
    user = User.objects.create_user(username="rbac_admin", password="pass")
    group = Group.objects.create(name="rbac_admins")
    _grant_group_permission(group, "databases", "clusterpermission", "manage_rbac")
    user.groups.add(group)

    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def staff_client():
    user = User.objects.create_user(username="staff", password="pass")
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_list_roles_requires_manage_rbac(normal_client):
    resp = normal_client.get("/api/v2/rbac/list-roles/")
    assert resp.status_code in [401, 403]


@pytest.fixture
def normal_client():
    user = User.objects.create_user(username="user", password="pass")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_list_roles_staff_ok(staff_client):
    resp = staff_client.get("/api/v2/rbac/list-roles/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_roles_capabilities_and_audit(rbac_admin_client):
    create = rbac_admin_client.post(
        "/api/v2/rbac/create-role/",
        {"name": "ops", "reason": "TICKET-1"},
        format="json",
    )
    assert create.status_code == 200
    role_id = create.json()["id"]

    caps = rbac_admin_client.get("/api/v2/rbac/list-capabilities/")
    assert caps.status_code == 200
    codes = {c["code"] for c in caps.json()["capabilities"]}
    assert "databases.manage_rbac" in codes

    set_caps = rbac_admin_client.post(
        "/api/v2/rbac/set-role-capabilities/",
        {"group_id": role_id, "permission_codes": ["databases.manage_rbac"], "mode": "replace", "reason": "TICKET-2"},
        format="json",
    )
    assert set_caps.status_code == 200
    assert "databases.manage_rbac" in set_caps.json()["permission_codes"]

    target = User.objects.create_user(username="u1", password="pass")
    set_roles = rbac_admin_client.post(
        "/api/v2/rbac/set-user-roles/",
        {"user_id": target.id, "group_ids": [role_id], "mode": "replace", "reason": "TICKET-3"},
        format="json",
    )
    assert set_roles.status_code == 200
    roles = set_roles.json()["roles"]
    assert any(r["id"] == role_id for r in roles)

    audit = rbac_admin_client.get("/api/v2/rbac/list-admin-audit/", {"action": "rbac.create_role"})
    assert audit.status_code == 200
    assert audit.json()["total"] >= 1


@pytest.mark.django_db
def test_group_bindings_clusters_and_databases(rbac_admin_client, cluster, database):
    group = Group.objects.create(name="db_ops")

    grant_cluster = rbac_admin_client.post(
        "/api/v2/rbac/grant-cluster-group-permission/",
        {"group_id": group.id, "cluster_id": str(cluster.id), "level": "VIEW", "reason": "TICKET-1"},
        format="json",
    )
    assert grant_cluster.status_code == 200
    assert grant_cluster.json()["permission"]["level"] == "VIEW"

    listed = rbac_admin_client.get("/api/v2/rbac/list-cluster-group-permissions/", {"group_id": group.id})
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    revoke_cluster = rbac_admin_client.post(
        "/api/v2/rbac/revoke-cluster-group-permission/",
        {"group_id": group.id, "cluster_id": str(cluster.id), "reason": "TICKET-2"},
        format="json",
    )
    assert revoke_cluster.status_code == 200
    assert revoke_cluster.json()["deleted"] is True

    grant_db = rbac_admin_client.post(
        "/api/v2/rbac/grant-database-group-permission/",
        {"group_id": group.id, "database_id": database.id, "level": "OPERATE", "reason": "TICKET-3"},
        format="json",
    )
    assert grant_db.status_code == 200
    assert grant_db.json()["permission"]["level"] == "OPERATE"

    revoke_db = rbac_admin_client.post(
        "/api/v2/rbac/revoke-database-group-permission/",
        {"group_id": group.id, "database_id": database.id, "reason": "TICKET-4"},
        format="json",
    )
    assert revoke_db.status_code == 200
    assert revoke_db.json()["deleted"] is True


@pytest.mark.django_db
def test_template_and_artifact_bindings_user(rbac_admin_client):
    user = User.objects.create_user(username="u_tpl", password="pass")
    template = OperationTemplate.objects.create(
        id="tpl-1",
        name="Template 1",
        description="",
        operation_type="noop",
        target_entity="database",
        template_data={},
        is_active=True,
    )

    grant_tpl = rbac_admin_client.post(
        "/api/v2/rbac/grant-operation-template-permission/",
        {"user_id": user.id, "template_id": template.id, "level": "VIEW", "reason": "TICKET-1"},
        format="json",
    )
    assert grant_tpl.status_code == 200
    assert grant_tpl.json()["permission"]["level"] == "VIEW"

    revoke_tpl = rbac_admin_client.post(
        "/api/v2/rbac/revoke-operation-template-permission/",
        {"user_id": user.id, "template_id": template.id, "reason": "TICKET-2"},
        format="json",
    )
    assert revoke_tpl.status_code == 200
    assert revoke_tpl.json()["deleted"] is True

    artifact = Artifact.objects.create(
        name="A1",
        kind=ArtifactKind.OTHER,
        is_versioned=True,
        created_by=user,
    )
    grant_art = rbac_admin_client.post(
        "/api/v2/rbac/grant-artifact-permission/",
        {"user_id": user.id, "artifact_id": str(artifact.id), "level": "MANAGE", "reason": "TICKET-3"},
        format="json",
    )
    assert grant_art.status_code == 200
    assert grant_art.json()["permission"]["level"] == "MANAGE"


@pytest.mark.django_db
def test_direct_bindings_clusters_and_databases_require_reason(rbac_admin_client, cluster, database):
    target = User.objects.create_user(username="u_direct", password="pass")

    grant_cluster = rbac_admin_client.post(
        "/api/v2/rbac/grant-cluster-permission/",
        {"user_id": target.id, "cluster_id": str(cluster.id), "level": "VIEW", "reason": "TICKET-1"},
        format="json",
    )
    assert grant_cluster.status_code == 200
    assert grant_cluster.json()["permission"]["level"] == "VIEW"

    revoke_cluster = rbac_admin_client.post(
        "/api/v2/rbac/revoke-cluster-permission/",
        {"user_id": target.id, "cluster_id": str(cluster.id), "reason": "TICKET-2"},
        format="json",
    )
    assert revoke_cluster.status_code == 200
    assert revoke_cluster.json()["deleted"] is True

    grant_db = rbac_admin_client.post(
        "/api/v2/rbac/grant-database-permission/",
        {"user_id": target.id, "database_id": database.id, "level": "OPERATE", "reason": "TICKET-3"},
        format="json",
    )
    assert grant_db.status_code == 200
    assert grant_db.json()["permission"]["level"] == "OPERATE"

    revoke_db = rbac_admin_client.post(
        "/api/v2/rbac/revoke-database-permission/",
        {"user_id": target.id, "database_id": database.id, "reason": "TICKET-4"},
        format="json",
    )
    assert revoke_db.status_code == 200
    assert revoke_db.json()["deleted"] is True


@pytest.mark.django_db
def test_list_users_with_roles(rbac_admin_client):
    role1 = Group.objects.create(name="role_a")
    role2 = Group.objects.create(name="role_b")

    u1 = User.objects.create_user(username="u_roles_1", password="pass")
    u2 = User.objects.create_user(username="u_roles_2", password="pass")
    u1.groups.add(role2, role1)
    u2.groups.add(role1)

    resp = rbac_admin_client.get("/api/v2/rbac/list-users-with-roles/", {"search": "u_roles_", "limit": 10, "offset": 0})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 2
    assert payload["total"] >= 2

    users = payload["users"]
    assert users[0]["username"] == "u_roles_1"
    assert users[1]["username"] == "u_roles_2"

    u1_roles = users[0]["roles"]
    assert [r["name"] for r in u1_roles] == ["role_a", "role_b"]

    filtered = rbac_admin_client.get("/api/v2/rbac/list-users-with-roles/", {"role_id": role2.id, "limit": 10, "offset": 0})
    assert filtered.status_code == 200
    filtered_users = filtered.json()["users"]
    assert len(filtered_users) == 1
    assert filtered_users[0]["username"] == "u_roles_1"


@pytest.mark.django_db
def test_bulk_group_permissions_clusters_and_databases(rbac_admin_client, cluster, database):
    group = Group.objects.create(name="bulk_ops")

    bulk_grant_cluster = rbac_admin_client.post(
        "/api/v2/rbac/bulk-grant-cluster-group-permission/",
        {"group_id": group.id, "cluster_ids": [str(cluster.id), str(cluster.id)], "level": "VIEW", "reason": "TICKET-1"},
        format="json",
    )
    assert bulk_grant_cluster.status_code == 200
    assert bulk_grant_cluster.json()["created"] == 1
    assert bulk_grant_cluster.json()["total"] == 1

    bulk_grant_cluster_again = rbac_admin_client.post(
        "/api/v2/rbac/bulk-grant-cluster-group-permission/",
        {"group_id": group.id, "cluster_ids": [str(cluster.id)], "level": "VIEW", "reason": "TICKET-2"},
        format="json",
    )
    assert bulk_grant_cluster_again.status_code == 200
    assert bulk_grant_cluster_again.json()["skipped"] == 1

    bulk_revoke_cluster = rbac_admin_client.post(
        "/api/v2/rbac/bulk-revoke-cluster-group-permission/",
        {"group_id": group.id, "cluster_ids": [str(cluster.id)], "reason": "TICKET-3"},
        format="json",
    )
    assert bulk_revoke_cluster.status_code == 200
    assert bulk_revoke_cluster.json()["deleted"] == 1
    assert bulk_revoke_cluster.json()["total"] == 1

    bulk_grant_db = rbac_admin_client.post(
        "/api/v2/rbac/bulk-grant-database-group-permission/",
        {"group_id": group.id, "database_ids": [database.id], "level": "OPERATE", "reason": "TICKET-4"},
        format="json",
    )
    assert bulk_grant_db.status_code == 200
    assert bulk_grant_db.json()["created"] == 1

    bulk_revoke_db = rbac_admin_client.post(
        "/api/v2/rbac/bulk-revoke-database-group-permission/",
        {"group_id": group.id, "database_ids": [database.id], "reason": "TICKET-5"},
        format="json",
    )
    assert bulk_revoke_db.status_code == 200
    assert bulk_revoke_db.json()["deleted"] == 1


@pytest.mark.django_db
def test_guardrail_last_rbac_admin(rbac_admin_client):
    admin_group = Group.objects.get(name="rbac_admins")
    admin_user = User.objects.get(username="rbac_admin")

    set_caps = rbac_admin_client.post(
        "/api/v2/rbac/set-role-capabilities/",
        {"group_id": admin_group.id, "permission_codes": [], "mode": "replace", "reason": "TICKET-1"},
        format="json",
    )
    assert set_caps.status_code == 409
    assert set_caps.json()["error"]["code"] == "LAST_RBAC_ADMIN"

    set_roles = rbac_admin_client.post(
        "/api/v2/rbac/set-user-roles/",
        {"user_id": admin_user.id, "group_ids": [admin_group.id], "mode": "remove", "reason": "TICKET-2"},
        format="json",
    )
    assert set_roles.status_code == 409
    assert set_roles.json()["error"]["code"] == "LAST_RBAC_ADMIN"


@pytest.mark.django_db
def test_effective_access_database_pagination(rbac_admin_client, cluster, database):
    Database.objects.create(
        id="db-2",
        name="test_db_2",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
        cluster=cluster,
    )
    Database.objects.create(
        id="db-3",
        name="test_db_3",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
        cluster=cluster,
    )

    admin_user = User.objects.get(username="rbac_admin")
    grant_cluster = rbac_admin_client.post(
        "/api/v2/rbac/grant-cluster-permission/",
        {"user_id": admin_user.id, "cluster_id": str(cluster.id), "level": "VIEW", "reason": "TICKET-1"},
        format="json",
    )
    assert grant_cluster.status_code == 200

    effective = rbac_admin_client.get(
        "/api/v2/rbac/get-effective-access/",
        {"include_clusters": False, "include_databases": True, "limit": 1, "offset": 0},
    )
    assert effective.status_code == 200
    payload = effective.json()
    assert payload["databases_count"] == 1
    assert payload["databases_total"] == 3
    assert len(payload["databases"]) == 1
    assert payload["databases"][0]["source"] == "cluster"
    assert payload["databases"][0]["via_cluster_id"] == str(cluster.id)
    assert any(
        src["source"] == "cluster" and src["level"] == "VIEW" and src["via_cluster_id"] == str(cluster.id)
        for src in payload["databases"][0]["sources"]
    )


@pytest.mark.django_db
def test_effective_access_sources_all_categories(rbac_admin_client, cluster, database):
    user = User.objects.create_user(username="effective_target", password="pass")
    role = Group.objects.create(name="effective_role")
    user.groups.add(role)

    grant_db_direct = rbac_admin_client.post(
        "/api/v2/rbac/grant-database-permission/",
        {"user_id": user.id, "database_id": database.id, "level": "VIEW", "reason": "TICKET-1"},
        format="json",
    )
    assert grant_db_direct.status_code == 200

    grant_db_group = rbac_admin_client.post(
        "/api/v2/rbac/grant-database-group-permission/",
        {"group_id": role.id, "database_id": database.id, "level": "OPERATE", "reason": "TICKET-2"},
        format="json",
    )
    assert grant_db_group.status_code == 200

    grant_cluster = rbac_admin_client.post(
        "/api/v2/rbac/grant-cluster-permission/",
        {"user_id": user.id, "cluster_id": str(cluster.id), "level": "ADMIN", "reason": "TICKET-3"},
        format="json",
    )
    assert grant_cluster.status_code == 200

    effective = rbac_admin_client.get(
        "/api/v2/rbac/get-effective-access/",
        {"user_id": user.id, "include_clusters": False, "include_databases": True},
    )
    assert effective.status_code == 200
    payload = effective.json()
    assert len(payload["databases"]) == 1

    row = payload["databases"][0]
    assert row["database"]["id"] == database.id
    assert row["level"] == "ADMIN"
    assert row["source"] == "cluster"
    assert row["via_cluster_id"] == str(cluster.id)

    sources = row["sources"]
    assert any(src["source"] == "direct" and src["level"] == "VIEW" for src in sources)
    assert any(src["source"] == "group" and src["level"] == "OPERATE" for src in sources)
    assert any(
        src["source"] == "cluster" and src["level"] == "ADMIN" and src["via_cluster_id"] == str(cluster.id)
        for src in sources
    )
