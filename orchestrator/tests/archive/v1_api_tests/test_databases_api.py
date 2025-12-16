"""
Тесты для REST API databases app.

Проверяет исправления:
1. Serializers - удаление last_error, исправление полей DatabaseGroup
2. Services - исправление get_client(), health_check() result handling
3. Views - корректная обработка всех endpoint'ов
"""

import pytest
from unittest.mock import Mock, patch
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.databases.models import Database, DatabaseGroup


@pytest.fixture
def api_client():
    """API client для тестов."""
    return APIClient()


@pytest.fixture
def test_database(db):
    """Создает тестовую базу данных."""
    database = Database.objects.create(
        id='test_db_001',
        name='Test Database',
        description='Test database for API tests',
        host='localhost',
        port=8080,
        base_name='test_base',
        odata_url='http://localhost:8080/test_base/odata/standard.odata',
        username='test_user',
        password='test_password',
        status=Database.STATUS_ACTIVE,
        last_check_status=Database.HEALTH_UNKNOWN,
        health_check_enabled=True
    )
    return database


@pytest.fixture
def test_database_group(db, test_database):
    """Создает тестовую группу баз данных."""
    group = DatabaseGroup.objects.create(
        id='test_group_001',
        name='Test Group',
        description='Test group for API tests'
    )
    group.databases.add(test_database)
    return group


@pytest.mark.django_db
class TestDatabaseListAPI:
    """Тесты для GET /api/v1/databases/"""

    def test_list_databases_success(self, api_client, test_database):
        """Тест: Получение списка баз данных."""
        url = reverse('database-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data or isinstance(response.data, list)

        # Проверяем структуру данных
        if 'results' in response.data:
            databases = response.data['results']
        else:
            databases = response.data

        assert len(databases) >= 1

        # Проверяем поля в ответе
        db_data = databases[0]
        assert 'id' in db_data
        assert 'name' in db_data
        assert 'status' in db_data
        assert 'status_display' in db_data
        assert 'is_healthy' in db_data
        assert 'last_check_status' in db_data

        # Проверяем что password не возвращается
        assert 'password' not in db_data

        # Проверяем что last_error ОТСУТСТВУЕТ (было удалено)
        assert 'last_error' not in db_data

    def test_list_databases_filter_by_status(self, api_client, test_database):
        """Тест: Фильтрация баз по статусу."""
        url = reverse('database-list')
        response = api_client.get(url, {'status': Database.STATUS_ACTIVE})

        assert response.status_code == status.HTTP_200_OK

        if 'results' in response.data:
            databases = response.data['results']
        else:
            databases = response.data

        # Все базы должны иметь статус active
        for db in databases:
            assert db['status'] == Database.STATUS_ACTIVE

    def test_list_databases_search(self, api_client, test_database):
        """Тест: Поиск баз по имени."""
        url = reverse('database-list')
        response = api_client.get(url, {'search': 'Test'})

        assert response.status_code == status.HTTP_200_OK

        if 'results' in response.data:
            databases = response.data['results']
        else:
            databases = response.data

        assert len(databases) >= 1
        assert 'Test' in databases[0]['name']

    def test_list_databases_empty(self, api_client, db):
        """Тест: Пустой список баз."""
        # Удаляем все базы
        Database.objects.all().delete()

        url = reverse('database-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK

        if 'results' in response.data:
            databases = response.data['results']
        else:
            databases = response.data

        assert len(databases) == 0


@pytest.mark.django_db
class TestDatabaseDetailAPI:
    """Тесты для GET /api/v1/databases/{id}/"""

    def test_get_database_success(self, api_client, test_database):
        """Тест: Получение деталей базы данных."""
        url = reverse('database-detail', kwargs={'pk': test_database.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK

        # Проверяем все поля
        assert response.data['id'] == test_database.id
        assert response.data['name'] == test_database.name
        assert response.data['host'] == test_database.host
        assert response.data['port'] == test_database.port
        assert response.data['status'] == test_database.status
        assert response.data['status_display'] == test_database.get_status_display()
        assert 'is_healthy' in response.data

        # Проверяем что password не возвращается
        assert 'password' not in response.data

        # Проверяем что last_error ОТСУТСТВУЕТ
        assert 'last_error' not in response.data

    def test_get_database_not_found(self, api_client, db):
        """Тест: Запрос несуществующей базы (должен быть 404)."""
        url = reverse('database-detail', kwargs={'pk': 'nonexistent_db'})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestDatabaseHealthCheckAPI:
    """Тесты для POST /api/v1/databases/{id}/health-check/"""

    @patch('apps.databases.services.session_manager.get_client')
    def test_health_check_success(self, mock_get_client, api_client, test_database):
        """Тест: Успешный health check."""
        # Mock OData client
        mock_client = Mock()
        mock_client.health_check.return_value = True  # Исправлено: health_check возвращает bool
        mock_get_client.return_value = mock_client

        url = reverse('database-health-check', kwargs={'pk': test_database.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK

        # Проверяем структуру ответа
        assert 'database_id' in response.data
        assert 'database_name' in response.data
        assert 'healthy' in response.data
        assert 'response_time' in response.data
        assert 'status_code' in response.data

        # Проверяем значения
        assert response.data['database_id'] == test_database.id
        assert response.data['database_name'] == test_database.name
        assert response.data['healthy'] is True
        assert response.data['status_code'] == 200

        # Проверяем что база обновилась
        test_database.refresh_from_db()
        assert test_database.last_check is not None
        assert test_database.last_check_status == Database.HEALTH_OK
        assert test_database.consecutive_failures == 0

    @patch('apps.databases.services.session_manager.get_client')
    def test_health_check_failure(self, mock_get_client, api_client, test_database):
        """Тест: Health check с ошибкой."""
        # Mock OData client с ошибкой
        from apps.databases.odata import ODataError

        mock_client = Mock()
        mock_client.health_check.side_effect = ODataError("Connection failed")
        mock_get_client.return_value = mock_client

        url = reverse('database-health-check', kwargs={'pk': test_database.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK

        # Проверяем что здоровье false
        assert response.data['healthy'] is False
        assert response.data['error'] is not None
        assert 'Connection failed' in response.data['error']

        # Проверяем что база отмечена как down
        test_database.refresh_from_db()
        assert test_database.last_check_status == Database.HEALTH_DOWN
        assert test_database.consecutive_failures == 1

    def test_health_check_database_not_found(self, api_client, db):
        """Тест: Health check для несуществующей базы (404)."""
        url = reverse('database-health-check', kwargs={'pk': 'nonexistent_db'})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestDatabaseGroupAPI:
    """Тесты для API групп баз данных."""

    def test_list_groups(self, api_client, test_database_group):
        """Тест: Получение списка групп."""
        url = reverse('databasegroup-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK

        if 'results' in response.data:
            groups = response.data['results']
        else:
            groups = response.data

        assert len(groups) >= 1

        # Проверяем поля
        group_data = groups[0]
        assert 'id' in group_data
        assert 'name' in group_data
        assert 'database_count' in group_data
        assert 'healthy_count' in group_data
        assert 'databases' in group_data

        # Проверяем что last_error ОТСУТСТВУЕТ
        assert 'last_error' not in group_data

    def test_get_group_detail(self, api_client, test_database_group, test_database):
        """Тест: Получение деталей группы."""
        url = reverse('databasegroup-detail', kwargs={'pk': test_database_group.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK

        assert response.data['id'] == test_database_group.id
        assert response.data['name'] == test_database_group.name
        assert response.data['database_count'] == 1

        # Проверяем вложенные базы
        assert len(response.data['databases']) == 1
        assert response.data['databases'][0]['id'] == test_database.id

    @patch('apps.databases.services.session_manager.get_client')
    def test_group_health_check(self, mock_get_client, api_client, test_database_group):
        """Тест: Health check для группы баз."""
        # Mock OData client
        mock_client = Mock()
        mock_client.health_check.return_value = True
        mock_get_client.return_value = mock_client

        url = reverse('databasegroup-health-check', kwargs={'pk': test_database_group.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK

        # Проверяем структуру ответа
        assert 'group_name' in response.data
        assert 'total' in response.data
        assert 'healthy' in response.data
        assert 'unhealthy' in response.data
        assert 'results' in response.data

        assert response.data['group_name'] == test_database_group.name
        assert response.data['total'] == 1
        assert len(response.data['results']) == 1


@pytest.mark.django_db
class TestDatabaseCRUD:
    """Тесты для CRUD операций с базами."""

    def test_create_database(self, api_client, db):
        """Тест: Создание новой базы через API."""
        url = reverse('database-list')
        data = {
            'name': 'New Test Database',
            'description': 'Created via API',
            'host': 'localhost',
            'port': 8080,
            'base_name': 'new_base',
            'odata_url': 'http://localhost:8080/new_base/odata/standard.odata',
            'username': 'new_user',
            'password': 'new_password',
            'status': Database.STATUS_ACTIVE
        }

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert 'id' in response.data
        assert response.data['name'] == data['name']

        # Проверяем что password не возвращается
        assert 'password' not in response.data

        # Проверяем что база создана в БД
        created_id = response.data['id']
        db_obj = Database.objects.get(id=created_id)
        assert db_obj.name == data['name']

    def test_update_database(self, api_client, test_database):
        """Тест: Обновление базы через API."""
        url = reverse('database-detail', kwargs={'pk': test_database.id})
        data = {
            'name': 'Updated Test Database',
            'description': 'Updated description'
        }

        response = api_client.patch(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == data['name']
        assert response.data['description'] == data['description']

        # Проверяем обновление в БД
        test_database.refresh_from_db()
        assert test_database.name == data['name']

    def test_delete_database(self, api_client, test_database):
        """Тест: Удаление базы через API."""
        url = reverse('database-detail', kwargs={'pk': test_database.id})

        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Проверяем что база удалена
        assert not Database.objects.filter(id=test_database.id).exists()


@pytest.mark.django_db
class TestBulkHealthCheck:
    """Тесты для bulk health check."""

    @patch('apps.databases.services.session_manager.get_client')
    def test_bulk_health_check_all(self, mock_get_client, api_client, test_database, db):
        """Тест: Bulk health check для всех баз."""
        # Создаем еще одну тестовую базу
        Database.objects.create(
            id='test_db_002',
            name='Test Database 2',
            host='localhost',
            port=8080,
            base_name='test_base_2',
            odata_url='http://localhost:8080/test_base_2/odata/standard.odata',
            username='test_user',
            password='test_password',
            status=Database.STATUS_ACTIVE
        )

        # Mock OData client
        mock_client = Mock()
        mock_client.health_check.return_value = True
        mock_get_client.return_value = mock_client

        url = reverse('database-bulk-health-check')
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK

        # Проверяем результаты
        assert response.data['total'] == 2
        assert response.data['healthy'] == 2
        assert response.data['unhealthy'] == 0
        assert len(response.data['results']) == 2

    @patch('apps.databases.services.session_manager.get_client')
    def test_bulk_health_check_filtered(self, mock_get_client, api_client, test_database, db):
        """Тест: Bulk health check с фильтром по статусу."""
        # Создаем базу с другим статусом
        Database.objects.create(
            id='test_db_003',
            name='Inactive Database',
            host='localhost',
            port=8080,
            base_name='test_base_3',
            odata_url='http://localhost:8080/test_base_3/odata/standard.odata',
            username='test_user',
            password='test_password',
            status=Database.STATUS_INACTIVE
        )

        # Mock OData client
        mock_client = Mock()
        mock_client.health_check.return_value = True
        mock_get_client.return_value = mock_client

        url = reverse('database-bulk-health-check')
        # Query параметры передаются в URL, а не в теле запроса
        response = api_client.post(f"{url}?status={Database.STATUS_ACTIVE}")

        assert response.status_code == status.HTTP_200_OK

        # Должна проверяться только одна active база
        assert response.data['total'] == 1


@pytest.mark.django_db
class TestSerializerFields:
    """Тесты для проверки правильности полей в сериализаторах."""

    def test_database_serializer_fields(self, api_client, test_database):
        """Тест: Проверка всех полей DatabaseSerializer."""
        url = reverse('database-detail', kwargs={'pk': test_database.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK

        # Обязательные поля
        required_fields = [
            'id', 'name', 'description', 'host', 'port', 'base_name',
            'odata_url', 'username', 'status', 'status_display',
            'version', 'last_check', 'last_check_status',
            'consecutive_failures', 'avg_response_time',
            'max_connections', 'connection_timeout',
            'health_check_enabled', 'is_healthy',
            'created_at', 'updated_at'
        ]

        for field in required_fields:
            assert field in response.data, f"Field '{field}' missing in response"

        # Поля, которых НЕ должно быть
        forbidden_fields = ['password', 'last_error']

        for field in forbidden_fields:
            assert field not in response.data, f"Field '{field}' should not be in response"

    def test_database_group_serializer_fields(self, api_client, test_database_group):
        """Тест: Проверка всех полей DatabaseGroupSerializer."""
        url = reverse('databasegroup-detail', kwargs={'pk': test_database_group.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK

        # Обязательные поля
        required_fields = [
            'id', 'name', 'description', 'databases',
            'database_count', 'healthy_count', 'metadata',
            'created_at', 'updated_at'
        ]

        for field in required_fields:
            assert field in response.data, f"Field '{field}' missing in response"

        # Поля, которых НЕ должно быть
        forbidden_fields = ['last_error']

        for field in forbidden_fields:
            assert field not in response.data, f"Field '{field}' should not be in response"
