"""Integration tests для DatabaseService и ODataOperationService."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase

from apps.databases.models import Database, DatabaseGroup
from apps.databases.services import DatabaseService, ODataOperationService


@pytest.mark.django_db
class TestDatabaseService:
    """Tests для DatabaseService."""

    def test_health_check_database_success(self):
        """Test успешного health check."""
        # Setup
        db = Database.objects.create(
            name='test_db',
            host='localhost',
            port=80,
            base_name='test',
            odata_url='http://localhost/test/odata/standard.odata',
            username='admin',
            password='secret'
        )

        # Mock ODataClient.health_check
        with patch('apps.databases.odata.ODataClient.health_check') as mock_health:
            mock_health.return_value = {
                'healthy': True,
                'response_time': 0.5,
                'status_code': 200
            }

            # Mock session_manager.get_client
            with patch('apps.databases.services.session_manager.get_client') as mock_get_client:
                mock_client = MagicMock()
                mock_client.health_check.return_value = {
                    'healthy': True,
                    'response_time': 0.5,
                    'status_code': 200
                }
                mock_get_client.return_value = mock_client

                # Execute
                result = DatabaseService.health_check_database(db)

                # Assert
                assert result['healthy'] is True
                assert 'response_time' in result

                # Check database updated
                db.refresh_from_db()
                assert db.last_check_status == 'success'
                assert db.consecutive_failures == 0

    def test_health_check_database_failure(self):
        """Test неудачного health check."""
        db = Database.objects.create(
            name='test_db',
            host='localhost',
            port=80,
            base_name='test',
            odata_url='http://localhost/test/odata/standard.odata',
            username='admin',
            password='secret'
        )

        # Mock connection error
        with patch('apps.databases.services.session_manager.get_client') as mock_get_client:
            mock_get_client.side_effect = Exception("Connection failed")

            # Execute
            result = DatabaseService.health_check_database(db)

            # Assert
            assert result['healthy'] is False
            assert 'error' in result

            # Check database updated
            db.refresh_from_db()
            assert db.last_check_status == 'failed'
            assert db.consecutive_failures == 1

    def test_health_check_group(self):
        """Test health check для группы баз."""
        # Setup
        db1 = Database.objects.create(
            name='db1',
            host='localhost',
            port=80,
            base_name='test1',
            odata_url='http://localhost/test1/odata/standard.odata',
            username='admin',
            password='secret'
        )
        db2 = Database.objects.create(
            name='db2',
            host='localhost',
            port=80,
            base_name='test2',
            odata_url='http://localhost/test2/odata/standard.odata',
            username='admin',
            password='secret'
        )

        group = DatabaseGroup.objects.create(name='test_group')
        group.databases.add(db1, db2)

        # Mock health checks
        with patch('apps.databases.services.session_manager.get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.health_check.return_value = {
                'healthy': True,
                'status_code': 200
            }
            mock_get_client.return_value = mock_client

            # Execute
            result = DatabaseService.health_check_group(group)

            # Assert
            assert result['total'] == 2
            assert result['healthy'] == 2
            assert result['unhealthy'] == 0
            assert len(result['results']) == 2

    def test_bulk_create_databases(self):
        """Test массового создания баз."""
        databases_data = [
            {
                'name': 'db1',
                'host': 'localhost',
                'port': 80,
                'base_name': 'test1',
                'odata_url': 'http://localhost/test1/odata/standard.odata',
                'username': 'admin',
                'password': 'secret'
            },
            {
                'name': 'db2',
                'host': 'localhost',
                'port': 80,
                'base_name': 'test2',
                'odata_url': 'http://localhost/test2/odata/standard.odata',
                'username': 'admin',
                'password': 'secret'
            }
        ]

        # Execute
        result = DatabaseService.bulk_create_databases(databases_data)

        # Assert
        assert result['created'] == 2
        assert result['failed'] == 0
        assert len(result['errors']) == 0
        assert Database.objects.count() == 2


@pytest.mark.django_db
class TestODataOperationService:
    """Tests для ODataOperationService."""

    def test_create_entity_success(self):
        """Test успешного создания сущности."""
        db = Database.objects.create(
            name='test_db',
            host='localhost',
            port=80,
            base_name='test',
            odata_url='http://localhost/test/odata/standard.odata',
            username='admin',
            password='secret'
        )

        # Mock ODataClient.create_entity
        with patch('apps.databases.services.session_manager.get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.create_entity.return_value = {
                'Ref_Key': '12345-67890',
                'Description': 'Test User',
                'Code': '000001'
            }
            mock_get_client.return_value = mock_client

            # Execute
            result = ODataOperationService.create_entity(
                database=db,
                entity_type='Catalog',
                entity_name='Пользователи',
                data={'Description': 'Test User', 'Code': '000001'}
            )

            # Assert
            assert result['success'] is True
            assert result['data']['Ref_Key'] == '12345-67890'
            assert result['error'] is None

            # Verify mock was called correctly
            mock_client.create_entity.assert_called_once_with(
                'Catalog_Пользователи',
                {'Description': 'Test User', 'Code': '000001'}
            )

    def test_create_entity_failure(self):
        """Test неудачного создания сущности."""
        db = Database.objects.create(
            name='test_db',
            host='localhost',
            port=80,
            base_name='test',
            odata_url='http://localhost/test/odata/standard.odata',
            username='admin',
            password='secret'
        )

        # Mock error
        with patch('apps.databases.services.session_manager.get_client') as mock_get_client:
            mock_get_client.side_effect = Exception("OData error")

            # Execute
            result = ODataOperationService.create_entity(
                database=db,
                entity_type='Catalog',
                entity_name='Пользователи',
                data={'Description': 'Test User'}
            )

            # Assert
            assert result['success'] is False
            assert result['data'] is None
            assert 'error' in result

    def test_get_entities_success(self):
        """Test успешного получения списка сущностей."""
        db = Database.objects.create(
            name='test_db',
            host='localhost',
            port=80,
            base_name='test',
            odata_url='http://localhost/test/odata/standard.odata',
            username='admin',
            password='secret'
        )

        # Mock ODataClient.get_entities
        with patch('apps.databases.services.session_manager.get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_entities.return_value = {
                'value': [
                    {'Ref_Key': '1', 'Description': 'User 1'},
                    {'Ref_Key': '2', 'Description': 'User 2'}
                ]
            }
            mock_get_client.return_value = mock_client

            # Execute
            result = ODataOperationService.get_entities(
                database=db,
                entity_type='Catalog',
                entity_name='Пользователи',
                filter_query="Description eq 'Test'"
            )

            # Assert
            assert result['success'] is True
            assert result['count'] == 2
            assert len(result['data']) == 2

            # Verify filter was passed
            mock_client.get_entities.assert_called_once_with(
                'Catalog_Пользователи',
                params={'$filter': "Description eq 'Test'"}
            )

    def test_get_entities_without_filter(self):
        """Test получения сущностей без фильтра."""
        db = Database.objects.create(
            name='test_db',
            host='localhost',
            port=80,
            base_name='test',
            odata_url='http://localhost/test/odata/standard.odata',
            username='admin',
            password='secret'
        )

        with patch('apps.databases.services.session_manager.get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_entities.return_value = {
                'value': []
            }
            mock_get_client.return_value = mock_client

            # Execute
            result = ODataOperationService.get_entities(
                database=db,
                entity_type='Catalog',
                entity_name='Пользователи'
            )

            # Assert
            assert result['success'] is True
            assert result['count'] == 0

            # Verify no filter was passed
            mock_client.get_entities.assert_called_once_with(
                'Catalog_Пользователи',
                params={}
            )
