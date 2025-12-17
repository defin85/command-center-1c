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

