"""Tests for database v2 endpoints (Internal API)."""
import uuid

from rest_framework import status

from ._internal_api_v2_base import InternalAPIV2BaseTestCase


class DatabaseEndpointsV2Tests(InternalAPIV2BaseTestCase):
    def test_get_database_cluster_info_missing_id(self):
        response = self.client.get("/api/v2/internal/get-database-cluster-info")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("database_id", response.data["error"])

    def test_get_database_cluster_info_not_found(self):
        response = self.client.get(
            f"/api/v2/internal/get-database-cluster-info?database_id={uuid.uuid4()}"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_get_database_cluster_info_unauthorized(self):
        client = self.get_unauthenticated_client()
        response = client.get(
            f"/api/v2/internal/get-database-cluster-info?database_id={uuid.uuid4()}"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_database_cluster_info_success(self):
        from apps.databases.models import Cluster
        from apps.databases.models import Database

        ras_cluster_uuid = uuid.uuid4()
        ras_infobase_id = uuid.uuid4()
        cluster = Cluster.objects.create(
            id=uuid.uuid4(),
            name="Cluster For DB Cluster Info",
            ras_server="localhost:1545",
            ras_cluster_uuid=ras_cluster_uuid,
            cluster_service_url="http://localhost:8188",
        )
        db = Database.objects.create(
            id="db-cluster-info-1",
            name="DB Cluster Info 1",
            host="localhost",
            odata_url="http://localhost/odata",
            username="admin",
            password="secret",
            ras_infobase_id=ras_infobase_id,
            cluster=cluster,
        )

        response = self.client.get(
            f"/api/v2/internal/get-database-cluster-info?database_id={db.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["cluster_info"]["database_id"], db.id)
        self.assertEqual(response.data["cluster_info"]["cluster_id"], str(ras_cluster_uuid))
        self.assertEqual(response.data["cluster_info"]["infobase_id"], str(ras_infobase_id))
        self.assertEqual(response.data["cluster_info"]["ras_server"], "localhost:1545")

    def test_get_database_cluster_info_fallback_ras_cluster_id(self):
        from apps.databases.models import Cluster
        from apps.databases.models import Database

        ras_cluster_id = uuid.uuid4()
        ras_infobase_id = uuid.uuid4()
        cluster = Cluster.objects.create(
            id=uuid.uuid4(),
            name="Cluster Without RAS UUID",
            ras_server="localhost:1545",
            ras_cluster_uuid=None,
            cluster_service_url="http://localhost:8188",
        )
        db = Database.objects.create(
            id="db-cluster-info-2",
            name="DB Cluster Info 2",
            host="localhost",
            odata_url="http://localhost/odata",
            username="admin",
            password="secret",
            ras_cluster_id=ras_cluster_id,
            ras_infobase_id=ras_infobase_id,
            cluster=cluster,
        )

        response = self.client.get(
            f"/api/v2/internal/get-database-cluster-info?database_id={db.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["cluster_info"]["cluster_id"], str(ras_cluster_id))
        self.assertEqual(response.data["cluster_info"]["infobase_id"], str(ras_infobase_id))

    def test_list_databases_for_health_check(self):
        response = self.client.get("/api/v2/internal/list-databases-for-health-check")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIn("databases", response.data)
        self.assertIn("count", response.data)
        self.assertIsInstance(response.data["databases"], list)
        self.assertIsInstance(response.data["count"], int)

    def test_list_databases_for_health_check_unauthorized(self):
        client = self.get_unauthenticated_client()
        response = client.get("/api/v2/internal/list-databases-for-health-check")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_database_health_missing_id(self):
        response = self.client.post(
            "/api/v2/internal/update-database-health",
            {"healthy": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("database_id", response.data["error"])

    def test_update_database_health_not_found(self):
        response = self.client.post(
            f"/api/v2/internal/update-database-health?database_id={uuid.uuid4()}",
            {"healthy": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_update_database_health_missing_healthy_field(self):
        response = self.client.post(
            f"/api/v2/internal/update-database-health?database_id={uuid.uuid4()}",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_update_database_health_unauthorized(self):
        client = self.get_unauthenticated_client()
        response = client.post(
            f"/api/v2/internal/update-database-health?database_id={uuid.uuid4()}",
            {"healthy": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

