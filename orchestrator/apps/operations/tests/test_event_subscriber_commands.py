"""Unit tests for command handlers (EventSubscriber)."""

import uuid
from unittest.mock import MagicMock, patch

from apps.databases.models import Database
from apps.operations.event_subscriber import EventSubscriber

from ._event_subscriber_test_base import EventSubscriberBaseTestCase


class EventSubscriberClusterInfoTest(EventSubscriberBaseTestCase):
    def setUp(self):
        from apps.databases.models import Cluster

        self.cluster = Cluster.objects.create(
            id=uuid.uuid4(),
            name="Test Cluster",
            ras_server="localhost:1545",
            ras_cluster_uuid=uuid.uuid4(),
            cluster_service_url="http://localhost:8188",
            status=Cluster.STATUS_ACTIVE,
        )

        self.database = Database.objects.create(
            id="db-with-cluster",
            name="Database With Cluster",
            host="localhost",
            port=80,
            odata_url="http://localhost/odata",
            username="admin",
            password="password",
            cluster=self.cluster,
            ras_infobase_id=uuid.uuid4(),
        )

        self.database_no_cluster = Database.objects.create(
            id="db-no-cluster",
            name="Database Without Cluster",
            host="localhost",
            port=80,
            odata_url="http://localhost/odata",
            username="admin",
            password="password",
        )

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_handle_get_cluster_info_success(self, mock_redis_class):
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        subscriber = EventSubscriber()

        data = {
            "correlation_id": "test-corr-123",
            "database_id": self.database.id,
            "timestamp": "2025-12-15T10:30:00Z",
        }
        subscriber.handle_get_cluster_info(data, "test-corr-123")

        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        self.assertEqual(call_args[0][0], "events:orchestrator:cluster-info-response")

        response = call_args[0][1]
        self.assertEqual(response["correlation_id"], "test-corr-123")
        self.assertEqual(response["database_id"], self.database.id)
        self.assertEqual(response["success"], "true")
        self.assertEqual(response["ras_server"], "localhost:1545")
        self.assertNotEqual(response["ras_cluster_uuid"], "")
        self.assertNotEqual(response["infobase_id"], "")
        self.assertEqual(response["error"], "")

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_handle_get_database_credentials_success(self, mock_redis_class):
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        subscriber = EventSubscriber()

        data = {
            "correlation_id": "test-creds-123",
            "database_id": self.database.id,
            "timestamp": "2025-12-16T10:30:00Z",
        }

        subscriber.handle_get_database_credentials(data, "test-creds-123")

        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        self.assertEqual(call_args[0][0], "events:orchestrator:database-credentials-response")

        response = call_args[0][1]
        self.assertEqual(response["correlation_id"], "test-creds-123")
        self.assertEqual(response["database_id"], self.database.id)
        self.assertEqual(response["success"], "true")
        self.assertEqual(response["error"], "")
        self.assertNotEqual(response["encrypted_data"], "")
        self.assertNotEqual(response["nonce"], "")
        self.assertNotEqual(response["expires_at"], "")
        self.assertNotEqual(response["encryption_version"], "")

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_handle_get_database_credentials_not_found(self, mock_redis_class):
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        subscriber = EventSubscriber()

        data = {
            "correlation_id": "test-creds-404",
            "database_id": "nonexistent-db",
            "timestamp": "2025-12-16T10:30:00Z",
        }

        subscriber.handle_get_database_credentials(data, "test-creds-404")

        mock_redis.xadd.assert_called_once()
        response = mock_redis.xadd.call_args[0][1]

        self.assertEqual(response["correlation_id"], "test-creds-404")
        self.assertEqual(response["database_id"], "nonexistent-db")
        self.assertEqual(response["success"], "false")
        self.assertIn("not found", response["error"])
        self.assertEqual(response["encrypted_data"], "")
        self.assertEqual(response["nonce"], "")
        self.assertEqual(response["expires_at"], "")
        self.assertEqual(response["encryption_version"], "")

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_handle_get_cluster_info_database_not_found(self, mock_redis_class):
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        subscriber = EventSubscriber()

        data = {
            "correlation_id": "test-corr-456",
            "database_id": "nonexistent-db",
            "timestamp": "2025-12-15T10:30:00Z",
        }
        subscriber.handle_get_cluster_info(data, "test-corr-456")

        mock_redis.xadd.assert_called_once()
        response = mock_redis.xadd.call_args[0][1]
        self.assertEqual(response["correlation_id"], "test-corr-456")
        self.assertEqual(response["database_id"], "nonexistent-db")
        self.assertEqual(response["success"], "false")
        self.assertIn("not found", response["error"])

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_handle_get_cluster_info_no_cluster(self, mock_redis_class):
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        subscriber = EventSubscriber()

        data = {
            "correlation_id": "test-corr-789",
            "database_id": self.database_no_cluster.id,
            "timestamp": "2025-12-15T10:30:00Z",
        }
        subscriber.handle_get_cluster_info(data, "test-corr-789")

        mock_redis.xadd.assert_called_once()
        response = mock_redis.xadd.call_args[0][1]
        self.assertEqual(response["correlation_id"], "test-corr-789")
        self.assertEqual(response["success"], "false")
        self.assertIn("no cluster", response["error"].lower())

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_handle_get_cluster_info_no_ras_cluster_uuid(self, mock_redis_class):
        from apps.databases.models import Cluster

        cluster_no_uuid = Cluster.objects.create(
            id=uuid.uuid4(),
            name="Cluster Without UUID",
            ras_server="localhost:1545",
            ras_cluster_uuid=None,
            cluster_service_url="http://localhost:8188",
        )
        database = Database.objects.create(
            id="db-no-ras-uuid",
            name="DB No RAS UUID",
            host="localhost",
            port=80,
            odata_url="http://localhost/odata",
            username="admin",
            password="password",
            cluster=cluster_no_uuid,
        )

        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        subscriber = EventSubscriber()

        data = {"correlation_id": "test-corr-no-uuid", "database_id": database.id}
        subscriber.handle_get_cluster_info(data, "test-corr-no-uuid")

        response = mock_redis.xadd.call_args[0][1]
        self.assertEqual(response["success"], "false")
        self.assertIn("ras_cluster_uuid", response["error"])

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_handle_get_cluster_info_no_infobase_id(self, mock_redis_class):
        from apps.databases.models import Cluster

        cluster = Cluster.objects.create(
            id=uuid.uuid4(),
            name="Cluster With UUID",
            ras_server="localhost:1545",
            ras_cluster_uuid=uuid.uuid4(),
            cluster_service_url="http://localhost:8188",
        )
        database = Database.objects.create(
            id="db-no-infobase-id",
            name="DB No Infobase ID",
            host="localhost",
            port=80,
            odata_url="http://localhost/odata",
            username="admin",
            password="password",
            cluster=cluster,
            ras_infobase_id=None,
        )

        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        subscriber = EventSubscriber()

        data = {"correlation_id": "test-corr-no-infobase", "database_id": database.id}
        subscriber.handle_get_cluster_info(data, "test-corr-no-infobase")

        response = mock_redis.xadd.call_args[0][1]
        self.assertEqual(response["success"], "false")
        self.assertIn("ras_infobase_id", response["error"])

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_handle_get_cluster_info_success_with_ids(self, mock_redis_class):
        from apps.databases.models import Cluster

        cluster_uuid = uuid.uuid4()
        infobase_uuid = uuid.uuid4()
        cluster = Cluster.objects.create(
            id=uuid.uuid4(),
            name="Cluster Success",
            ras_server="localhost:1545",
            ras_cluster_uuid=cluster_uuid,
            cluster_service_url="http://localhost:8188",
        )
        database = Database.objects.create(
            id="db-success",
            name="DB Success",
            host="localhost",
            port=80,
            odata_url="http://localhost/odata",
            username="admin",
            password="password",
            cluster=cluster,
            ras_infobase_id=infobase_uuid,
        )

        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        subscriber = EventSubscriber()

        data = {"correlation_id": "test-corr-success", "database_id": database.id}
        subscriber.handle_get_cluster_info(data, "test-corr-success")

        response = mock_redis.xadd.call_args[0][1]
        self.assertEqual(response["success"], "true")
        self.assertEqual(response["cluster_id"], str(cluster_uuid))
        self.assertEqual(response["ras_cluster_uuid"], str(cluster_uuid))
        self.assertEqual(response["infobase_id"], str(infobase_uuid))

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_process_message_routes_to_get_cluster_info(self, mock_redis_class):
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()
        subscriber.handle_get_cluster_info = MagicMock()

        data = {
            "correlation_id": "test-corr-routing",
            "database_id": "db-123",
            "timestamp": "2025-12-15T10:30:00Z",
        }

        subscriber.process_message("commands:orchestrator:get-cluster-info", "1234567890-0", data)
        subscriber.handle_get_cluster_info.assert_called_once()

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_process_message_routes_to_get_database_credentials(self, mock_redis_class):
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        subscriber = EventSubscriber()
        subscriber.handle_get_database_credentials = MagicMock()

        data = {
            "correlation_id": "test-creds-routing",
            "database_id": "db-123",
            "timestamp": "2025-12-16T10:30:00Z",
        }

        subscriber.process_message(
            "commands:orchestrator:get-database-credentials",
            "1234567890-0",
            data,
        )
        subscriber.handle_get_database_credentials.assert_called_once()

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_subscriber_streams_includes_get_cluster_info(self, mock_redis_class):
        subscriber = EventSubscriber()
        self.assertIn("commands:orchestrator:get-cluster-info", subscriber.streams)

    @patch("apps.operations.event_subscriber.subscriber.redis.Redis")
    def test_subscriber_streams_includes_get_database_credentials(self, mock_redis_class):
        subscriber = EventSubscriber()
        self.assertIn("commands:orchestrator:get-database-credentials", subscriber.streams)

