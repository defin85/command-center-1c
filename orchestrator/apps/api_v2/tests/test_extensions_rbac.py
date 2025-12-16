import pytest
import uuid
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.databases.models import Cluster, Database, DatabasePermission, PermissionLevel


@pytest.fixture
def user():
    return User.objects.create_user(username="u1", password="pass")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def cluster():
    return Cluster.objects.create(
        name="Test Cluster",
        ras_server="localhost:1545",
        cluster_service_url="http://localhost:8188",
    )


@pytest.fixture
def database(cluster):
    db_id = str(uuid.uuid4())
    return Database.objects.create(
        id=db_id,
        name=f"test_db_ext_{db_id[:8]}",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="odata",
        password="secret",
        cluster=cluster,
    )


@pytest.mark.django_db
def test_batch_install_requires_manage_permission(client, user, database):
    resp = client.post(
        "/api/v2/extensions/batch-install/",
        {"database_ids": [database.id], "extension_name": "ODataAutoConfig", "extension_path": "/tmp/x.cfe"},
        format="json",
    )
    assert resp.status_code == 403

    DatabasePermission.objects.create(user=user, database=database, level=PermissionLevel.MANAGE)

    resp2 = client.post(
        "/api/v2/extensions/batch-install/",
        {"database_ids": [database.id], "extension_name": "ODataAutoConfig", "extension_path": "/tmp/x.cfe"},
        format="json",
    )
    assert resp2.status_code == 200
