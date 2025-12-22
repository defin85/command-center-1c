import uuid
import pytest

from apps.databases.models import Cluster, Database
from apps.databases.services import ClusterService


@pytest.mark.django_db
def test_import_infobases_preserves_existing_status():
    cluster = Cluster.objects.create(
        id="00000000-0000-0000-0000-000000000001",
        name="C1",
        ras_server="localhost:1545",
        cluster_service_url="http://localhost:8188",
        status=Cluster.STATUS_ACTIVE,
    )

    db = Database.objects.create(
        id="ib-1",
        name="IB 1",
        host="localhost",
        port=80,
        base_name="IB 1",
        odata_url="http://localhost/IB 1/odata/standard.odata/",
        username="user",
        password="secret",
        cluster=cluster,
        status=Database.STATUS_MAINTENANCE,
    )

    ClusterService.import_infobases_from_dict(
        cluster,
        [
            {
                "uuid": db.id,
                "name": "IB 1",
                "dbms": "PostgreSQL",
                "db_server": "localhost",
                "db_name": "ib1",
                "locale": "ru_RU",
                "sessions_deny": False,
                "scheduled_jobs_deny": False,
            }
        ],
    )

    db.refresh_from_db()
    assert db.status == Database.STATUS_MAINTENANCE
    assert db.cluster_id == cluster.id


@pytest.mark.django_db
def test_import_infobases_sets_ras_metadata():
    cluster_uuid = uuid.uuid4()
    infobase_uuid = uuid.uuid4()
    cluster = Cluster.objects.create(
        id=uuid.uuid4(),
        name="C2",
        ras_server="localhost:1545",
        ras_cluster_uuid=cluster_uuid,
        cluster_service_url="http://localhost:8188",
        status=Cluster.STATUS_ACTIVE,
    )

    ClusterService.import_infobases_from_dict(
        cluster,
        [
            {
                "uuid": str(infobase_uuid),
                "name": "IB 2",
                "dbms": "PostgreSQL",
                "db_server": "localhost",
                "db_name": "ib2",
                "locale": "ru_RU",
                "sessions_deny": False,
                "scheduled_jobs_deny": False,
                "denied_from": "2025-01-01T00:00:00Z",
                "denied_to": "2025-01-02T00:00:00Z",
                "denied_message": "Maintenance",
                "permission_code": "ALLOW",
                "denied_parameter": "param",
            }
        ],
    )

    db = Database.objects.get(id=str(infobase_uuid))
    assert db.ras_cluster_id == cluster_uuid
    assert db.ras_infobase_id == infobase_uuid
    assert db.metadata["denied_from"] == "2025-01-01T00:00:00Z"
    assert db.metadata["denied_to"] == "2025-01-02T00:00:00Z"
    assert db.metadata["denied_message"] == "Maintenance"
    assert db.metadata["permission_code"] == "ALLOW"
    assert db.metadata["denied_parameter"] == "param"


@pytest.mark.django_db
def test_import_infobases_skips_restrictions_when_info_unavailable():
    cluster = Cluster.objects.create(
        id="00000000-0000-0000-0000-000000000002",
        name="C3",
        ras_server="localhost:1545",
        cluster_service_url="http://localhost:8188",
        status=Cluster.STATUS_ACTIVE,
    )

    db = Database.objects.create(
        id="ib-2",
        name="IB 2",
        host="localhost",
        port=80,
        base_name="IB 2",
        odata_url="http://localhost/IB 2/odata/standard.odata/",
        username="user",
        password="secret",
        cluster=cluster,
        metadata={
            "sessions_deny": True,
            "scheduled_jobs_deny": True,
            "denied_from": "2025-01-01T00:00:00Z",
            "denied_to": "2025-01-02T00:00:00Z",
            "denied_message": "Maintenance",
            "permission_code": "ALLOW",
            "denied_parameter": "param",
            "dbms": "PostgreSQL",
        },
    )

    ClusterService.import_infobases_from_dict(
        cluster,
        [
            {
                "uuid": db.id,
                "name": "IB 2",
                "info_available": False,
                "info_error": "access denied",
            }
        ],
    )

    db.refresh_from_db()
    assert db.metadata.get("dbms") == "PostgreSQL"
    assert db.metadata.get("info_available") is False
    assert db.metadata.get("info_error") == "access denied"
    assert "sessions_deny" not in db.metadata
    assert "scheduled_jobs_deny" not in db.metadata
    assert "denied_from" not in db.metadata
    assert "denied_to" not in db.metadata
    assert "denied_message" not in db.metadata
    assert "permission_code" not in db.metadata
    assert "denied_parameter" not in db.metadata
