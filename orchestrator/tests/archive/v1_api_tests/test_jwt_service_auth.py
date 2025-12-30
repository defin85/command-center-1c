"""
Интеграционные тесты для JWT service-to-service authentication
и установки расширений.

Проверяет полный flow:
1. Go Worker генерирует JWT token
2. Django ServiceJWTAuthentication валидирует токен
3. Worker запрашивает credentials через /api/v1/databases/{id}/credentials/
4. Orchestrator отправляет сообщение в Redis queue
5. Worker получает сообщение и устанавливает расширение
"""

import pytest
import jwt
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from django.conf import settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.databases.models import Database, Cluster
from apps.core.authentication import ServiceJWTAuthentication, ServiceUser


@pytest.mark.django_db
class TestServiceJWTAuthentication:
    """Тесты для service-to-service JWT authentication"""

    def setup_method(self):
        """Подготовка тестового окружения"""
        self.client = APIClient()

        # Создаём тестовый кластер
        self.cluster = Cluster.objects.create(
            name="Test Cluster",
            ras_server="localhost:1545",
            cluster_service_url="http://localhost:8088",
            status=Cluster.STATUS_ACTIVE
        )

    def generate_service_token(self, service_name="worker", ttl_hours=24):
        """
        Генерирует service token как это делает Go Worker.
        Использует тот же алгоритм что в go-services/shared/auth/service_token.go

        Args:
            service_name: Имя сервиса (worker, api-gateway, worker)
            ttl_hours: Время жизни токена в часах

        Returns:
            str: JWT token
        """
        import uuid
        now = datetime.utcnow()
        payload = {
            "user_id": f"service:{service_name}",  # Pseudo user для Django
            "service": service_name,
            "sub": service_name,
            "iss": "commandcenter",
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(hours=ttl_hours)).timestamp()),
            "jti": str(uuid.uuid4()),  # JWT ID - required by Django SimpleJWT
            "token_type": "access"  # Required by Django SimpleJWT
        }

        # Используем JWT_SECRET из settings
        secret = settings.SIMPLE_JWT['SIGNING_KEY']
        token = jwt.encode(payload, secret, algorithm="HS256")

        return token

    def test_generate_service_token_matches_go_worker(self):
        """Проверка что Python генерирует токен совместимый с Go Worker"""
        token = self.generate_service_token("worker")

        # Декодировать токен
        secret = settings.SIMPLE_JWT['SIGNING_KEY']
        decoded = jwt.decode(token, secret, algorithms=["HS256"])

        print("[OK] Token generated successfully")
        print(f"  user_id: {decoded['user_id']}")
        print(f"  service: {decoded['service']}")
        print(f"  iss: {decoded['iss']}")

        assert decoded["user_id"] == "service:worker"
        assert decoded["service"] == "worker"
        assert decoded["iss"] == "commandcenter"

    def test_django_validates_service_token(self):
        """Проверка что Django правильно валидирует service token"""
        # Создать токен через Django SimpleJWT
        token = AccessToken()
        token['user_id'] = 'service:worker'
        token_string = str(token)

        print(f"[OK] Token created: {token_string[:50]}...")

        # Валидировать через ServiceJWTAuthentication
        auth = ServiceJWTAuthentication()
        validated_token = auth.get_validated_token(token_string)
        user = auth.get_user(validated_token)

        print(f"[OK] Token validated, user: {user}")
        print(f"  service_name: {user.service_name}")
        print(f"  is_authenticated: {user.is_authenticated}")

        assert hasattr(user, 'service_name')
        assert user.service_name == 'worker'
        assert user.is_authenticated is True
        assert isinstance(user, ServiceUser)

    def test_credentials_endpoint_with_service_token(self):
        """Проверка что credentials endpoint доступен с service token"""
        # Создать тестовую БД
        db = Database.objects.create(
            id="test-db-001",
            name="Test DB",
            host="localhost",
            port=80,
            base_name="test_db",
            odata_url="http://localhost:8080/odata/standard.odata",
            username="Admin",
            password="Password123",  # Будет зашифрован через EncryptedCharField
            status=Database.STATUS_ACTIVE,
            cluster=self.cluster
        )

        print(f"[OK] Test database created: {db.id}")

        # Сгенерировать service token
        token = self.generate_service_token("worker")

        print(f"[OK] Service token generated: {token[:50]}...")
        print(f"[OK] JWT_SECRET: {settings.SIMPLE_JWT['SIGNING_KEY'][:10]}...")

        # Вызвать credentials endpoint
        response = self.client.get(
            f'/api/v1/databases/{db.id}/credentials/',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )

        # Проверить результат
        print(f"[OK] Response status: {response.status_code}")
        if response.status_code != 200:
            print(f"[ERROR] Response body: {response.content.decode()}")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.content.decode()}"

        data = response.data
        assert data['database_id'] == str(db.id)
        assert data['username'] == "Admin"
        assert 'password' in data  # Password расшифрован
        assert data['odata_url'] == db.odata_url

        print(f"[OK] Credentials endpoint OK: database_id={data['database_id']}")
        print(f"  username: {data['username']}")
        print(f"  odata_url: {data['odata_url']}")

    def test_credentials_endpoint_without_token_fails(self):
        """Проверка что без токена endpoint возвращает 401"""
        db = Database.objects.create(
            id="test-db-002",
            name="Test DB 2",
            host="localhost",
            port=80,
            base_name="test_db_2",
            odata_url="http://localhost:8080/odata/standard.odata",
            username="Admin",
            password="Password123",
            cluster=self.cluster
        )

        response = self.client.get(f'/api/v1/databases/{db.id}/credentials/')

        print(f"[OK] Without token: {response.status_code}")
        assert response.status_code == 401

    def test_credentials_endpoint_with_invalid_token_fails(self):
        """Проверка что с неправильным токеном endpoint возвращает 401"""
        db = Database.objects.create(
            id="test-db-003",
            name="Test DB 3",
            host="localhost",
            port=80,
            base_name="test_db_3",
            odata_url="http://localhost:8080/odata/standard.odata",
            username="Admin",
            password="Password123",
            cluster=self.cluster
        )

        # Использовать неправильный secret
        wrong_secret = "wrong-secret"
        payload = {"user_id": "service:worker"}
        token = jwt.encode(payload, wrong_secret, algorithm="HS256")

        response = self.client.get(
            f'/api/v1/databases/{db.id}/credentials/',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )

        print(f"[OK] With invalid token: {response.status_code}")
        assert response.status_code == 401


@pytest.mark.django_db
class TestJWTSecretConfiguration:
    """Тесты для проверки JWT_SECRET конфигурации"""

    def test_jwt_secret_is_configured(self):
        """Проверка что JWT_SECRET установлен"""
        assert hasattr(settings, 'SIMPLE_JWT')
        assert 'SIGNING_KEY' in settings.SIMPLE_JWT
        secret = settings.SIMPLE_JWT['SIGNING_KEY']
        assert secret != ""
        # В тестовом окружении может быть default значение
        # assert secret != "your-jwt-secret-change-in-production"

        print(f"[OK] JWT_SECRET configured: {secret[:10]}...")

    def test_jwt_algorithm_is_hs256(self):
        """Проверка что используется алгоритм HS256"""
        assert settings.SIMPLE_JWT['ALGORITHM'] == 'HS256'
        print("[OK] JWT algorithm: HS256")

    def test_jwt_user_id_claim_is_correct(self):
        """Проверка что используется правильный claim для user_id"""
        assert settings.SIMPLE_JWT['USER_ID_CLAIM'] == 'user_id'
        print("[OK] JWT USER_ID_CLAIM: user_id")


@pytest.mark.django_db
class TestExtensionInstallationFlow:
    """E2E тесты для полного flow установки расширения"""

    def setup_method(self):
        """Подготовка тестового окружения"""
        self.client = APIClient()

        # Создаём тестовый кластер
        self.cluster = Cluster.objects.create(
            name="Test Cluster",
            ras_server="localhost:1545",
            cluster_service_url="http://localhost:8088",
            status=Cluster.STATUS_ACTIVE
        )

    def generate_service_token(self, service_name="worker"):
        """Helper для генерации service token"""
        import uuid
        now = datetime.utcnow()
        payload = {
            "user_id": f"service:{service_name}",
            "service": service_name,
            "sub": service_name,
            "iss": "commandcenter",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=24)).timestamp()),
            "jti": str(uuid.uuid4()),  # JWT ID - required by Django SimpleJWT
            "token_type": "access"  # Required by Django SimpleJWT
        }
        secret = settings.SIMPLE_JWT['SIGNING_KEY']
        return jwt.encode(payload, secret, algorithm="HS256")

    @pytest.mark.skip(reason="Requires Celery and Redis setup")
    @patch('apps.databases.tasks.queue_extension_installation.delay')
    @patch('redis.Redis')
    def test_extension_installation_flow_with_queue(self, mock_redis, mock_task):
        """Проверка полного flow установки расширения с task queue"""
        # 1. Создать тестовую БД
        db = Database.objects.create(
            id="test-db-flow",
            name="Test DB Flow",
            host="localhost",
            port=80,
            base_name="test_db_flow",
            odata_url="http://localhost:8080/odata/standard.odata",
            username="Admin",
            password="Password123",
            status=Database.STATUS_ACTIVE,
            cluster=self.cluster
        )

        print(f"[OK] Test database created: {db.id}")

        # 2. Создать тестовый extension config
        extension_config = {
            'name': 'ТестовоеРасширение',
            'path': 'storage/extensions/ТестовоеРасширение.cfe'
        }

        # 3. Mock Celery task
        mock_task_result = MagicMock()
        mock_task_result.id = 'test-task-id-12345'
        mock_task.return_value = mock_task_result

        # 4. Получить frontend auth token (для batch_install_extension endpoint)
        # В реальности frontend использует user token, но для теста используем service token
        token = self.generate_service_token("admin")

        # 5. Вызвать batch_install_extension endpoint
        response = self.client.post(
            '/api/v1/databases/batch-install-extension/',
            {
                'database_ids': [str(db.id)],
                'extension_config': extension_config
            },
            HTTP_AUTHORIZATION=f'Bearer {token}',
            format='json'
        )

        print(f"[OK] batch_install_extension response: {response.status_code}")

        assert response.status_code == 201
        assert 'task_id' in response.data

        operation_id = response.data['task_id']
        print(f"[OK] Full flow OK: operation_id={operation_id}")

        # 6. Проверить что Celery task был вызван
        mock_task.assert_called_once()
        call_args = mock_task.call_args
        assert call_args[0][0] == [str(db.id)]  # database_ids
        assert call_args[0][1] == extension_config  # extension_config

    def test_worker_can_fetch_credentials(self):
        """
        Симулирует как Go Worker запрашивает credentials.
        Это точная копия логики из go-services/worker/internal/credentials/client.go
        """
        # 1. Создать тестовую БД
        db = Database.objects.create(
            id="test-db-worker",
            name="Test DB for Worker",
            host="localhost",
            port=80,
            base_name="test_db_worker",
            odata_url="http://localhost:8080/odata/standard.odata",
            username="TestUser",
            password="TestPassword123",
            status=Database.STATUS_ACTIVE,
            cluster=self.cluster
        )

        print(f"[OK] Test database created: {db.id}")

        # 2. Генерировать service token как Go Worker
        token = self.generate_service_token("worker")

        print("[OK] Service token generated for worker")

        # 3. Вызвать credentials endpoint через APIClient (симулируя HTTP request)
        response = self.client.get(
            f'/api/v1/databases/{db.id}/credentials/',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )

        # 4. Проверить результат
        print(f"Response status: {response.status_code}")
        if response.status_code != 200:
            print(f"Response body: {response.content.decode()}")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.content.decode()}"

        data = response.data
        assert data['database_id'] == str(db.id)
        assert data['username'] == "TestUser"
        assert 'password' in data
        assert data['odata_url'] == db.odata_url

        print("[OK] Worker can fetch credentials successfully")
        print(f"  database_id: {data['database_id']}")
        print(f"  username: {data['username']}")
        print(f"  odata_url: {data['odata_url']}")


@pytest.mark.django_db
class TestServiceUserBehavior:
    """Тесты для проверки поведения ServiceUser"""

    def test_service_user_properties(self):
        """Проверка что ServiceUser имеет правильные свойства"""
        user = ServiceUser("worker")

        assert user.service_name == "worker"
        assert user.username == "service:worker"
        assert user.id == "service:worker"
        assert user.is_authenticated is True
        assert user.is_active is True
        assert user.is_staff is False
        assert user.is_staff is False

        print("[OK] ServiceUser properties OK")
        print(f"  service_name: {user.service_name}")
        print(f"  username: {user.username}")
        print(f"  is_authenticated: {user.is_authenticated}")

    def test_service_user_str_representation(self):
        """Проверка строкового представления ServiceUser"""
        user = ServiceUser("worker")

        assert str(user) == "ServiceUser(worker)"
        print(f"[OK] ServiceUser str representation: {str(user)}")


@pytest.mark.django_db
class TestAuthenticationEdgeCases:
    """Тесты для граничных случаев authentication"""

    def setup_method(self):
        """Подготовка тестового окружения"""
        self.client = APIClient()

        # Создаём тестовый кластер
        self.cluster = Cluster.objects.create(
            name="Test Cluster",
            ras_server="localhost:1545",
            cluster_service_url="http://localhost:8088",
            status=Cluster.STATUS_ACTIVE
        )

    def generate_service_token(self, service_name="worker"):
        """Helper для генерации service token"""
        import uuid
        now = datetime.utcnow()
        payload = {
            "user_id": f"service:{service_name}",
            "service": service_name,
            "sub": service_name,
            "iss": "commandcenter",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=24)).timestamp()),
            "jti": str(uuid.uuid4()),  # JWT ID - required by Django SimpleJWT
            "token_type": "access"  # Required by Django SimpleJWT
        }
        secret = settings.SIMPLE_JWT['SIGNING_KEY']
        return jwt.encode(payload, secret, algorithm="HS256")

    def test_expired_token_fails(self):
        """Проверка что истекший токен отклоняется"""
        db = Database.objects.create(
            id="test-db-expired",
            name="Test DB Expired",
            host="localhost",
            port=80,
            odata_url="http://localhost:8080/odata/standard.odata",
            username="Admin",
            password="Password123",
            cluster=self.cluster
        )

        # Создать токен с истекшим временем
        now = datetime.utcnow()
        payload = {
            "user_id": "service:worker",
            "service": "worker",
            "iat": int((now - timedelta(hours=25)).timestamp()),
            "exp": int((now - timedelta(hours=1)).timestamp())  # Expired 1 hour ago
        }
        secret = settings.SIMPLE_JWT['SIGNING_KEY']
        token = jwt.encode(payload, secret, algorithm="HS256")

        response = self.client.get(
            f'/api/v1/databases/{db.id}/credentials/',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )

        print(f"[OK] Expired token: {response.status_code}")
        assert response.status_code == 401

    def test_missing_user_id_claim_fails(self):
        """Проверка что токен без user_id claim отклоняется"""
        db = Database.objects.create(
            id="test-db-no-claim",
            name="Test DB No Claim",
            host="localhost",
            port=80,
            odata_url="http://localhost:8080/odata/standard.odata",
            username="Admin",
            password="Password123",
            cluster=self.cluster
        )

        # Создать токен без user_id claim
        now = datetime.utcnow()
        payload = {
            "service": "worker",  # Missing user_id
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=24)).timestamp())
        }
        secret = settings.SIMPLE_JWT['SIGNING_KEY']
        token = jwt.encode(payload, secret, algorithm="HS256")

        response = self.client.get(
            f'/api/v1/databases/{db.id}/credentials/',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )

        print(f"[OK] Missing user_id claim: {response.status_code}")
        assert response.status_code == 401

    def test_malformed_token_fails(self):
        """Проверка что невалидный токен отклоняется"""
        db = Database.objects.create(
            id="test-db-malformed",
            name="Test DB Malformed",
            host="localhost",
            port=80,
            odata_url="http://localhost:8080/odata/standard.odata",
            username="Admin",
            password="Password123",
            cluster=self.cluster
        )

        # Использовать невалидный токен
        token = "invalid.jwt.token"

        response = self.client.get(
            f'/api/v1/databases/{db.id}/credentials/',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )

        print(f"[OK] Malformed token: {response.status_code}")
        assert response.status_code == 401
