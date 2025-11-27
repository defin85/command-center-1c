#!/usr/bin/env python
"""
Comprehensive test suite for Sprint 1.2 completion.
Tests all implemented features: Models, OData Client, REST API, Mock Server integration.
"""

import os
import sys
import django
import requests
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
sys.path.insert(0, '/app')
django.setup()

from apps.databases.models import Database, DatabaseGroup
from apps.operations.models import BatchOperation, Task
from apps.templates.models import OperationTemplate
from apps.databases.odata.client import ODataClient
from apps.databases.services import DatabaseService


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_header(text):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{text:^60}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")


def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_info(text):
    print(f"{Colors.YELLOW}ℹ {text}{Colors.END}")


# ==================== TESTS ====================

def test_1_database_models():
    """Test Database models are working correctly."""
    print_header("TEST 1: Database Models")

    try:
        # Clear existing data
        Database.objects.all().delete()
        DatabaseGroup.objects.all().delete()

        # Create test database
        db = Database.objects.create(
            id='test_db_001',
            name='Тестовая база Москва',
            description='Тестовая база данных для проверки',
            host='localhost',
            port=8081,
            base_name='moscow_001',
            odata_url='http://localhost:8081/odata/standard.odata',
            username='Администратор',
            password='test123',  # Will be encrypted
            max_connections=10,
            connection_timeout=30,
            status=Database.STATUS_ACTIVE
        )

        print_success(f"Database created: {db.name}")
        print_info(f"  ID: {db.id}")
        print_info(f"  Status: {db.status}")
        print_info(f"  Connection: {db.connection_string}")
        print_info(f"  Healthy: {db.is_healthy}")

        # Create database group
        group = DatabaseGroup.objects.create(
            id='group_001',
            name='Московский регион',
            description='Базы Москвы'
        )
        group.databases.add(db)

        print_success(f"DatabaseGroup created: {group.name}")
        print_info(f"  Databases count: {group.database_count}")

        # Test health check
        db.mark_health_check(success=True, response_time=15.5)
        db.refresh_from_db()

        print_success("Health check updated")
        print_info(f"  Status: {db.last_check_status}")
        print_info(f"  Avg response time: {db.avg_response_time:.2f}ms")

        return True

    except Exception as e:
        print_error(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_2_operation_models():
    """Test Operation models are working correctly."""
    print_header("TEST 2: Operation Models")

    try:
        # Clear existing data
        BatchOperation.objects.all().delete()
        Task.objects.all().delete()

        # Get test database
        db = Database.objects.get(id='test_db_001')

        # Create batch operation
        batch = BatchOperation.objects.create(
            id='batch_001',
            name='Создание пользователей',
            description='Массовое создание тестовых пользователей',
            operation_type=BatchOperation.TYPE_CREATE,
            target_entity='Справочник_Пользователи',
            payload={
                'users': [
                    {'name': 'Иванов И.И.', 'login': 'ivanov'},
                    {'name': 'Петров П.П.', 'login': 'petrov'}
                ]
            },
            config={'timeout': 60, 'retry': 3},
            status=BatchOperation.STATUS_PENDING
        )
        batch.target_databases.add(db)

        print_success(f"BatchOperation created: {batch.name}")
        print_info(f"  Type: {batch.operation_type}")
        print_info(f"  Status: {batch.status}")
        print_info(f"  Target databases: {batch.target_databases.count()}")

        # Create tasks
        task1 = Task.objects.create(
            id='task_001',
            batch_operation=batch,
            database=db,
            status=Task.STATUS_PENDING,
            max_retries=3
        )

        print_success(f"Task created: {task1.id}")
        print_info(f"  Database: {task1.database.name}")
        print_info(f"  Can retry: {task1.can_retry}")

        # Test task lifecycle
        task1.mark_started(worker_id='worker_001')
        print_success("Task marked as started")

        task1.mark_completed(result={'created_id': 'user_123'})
        print_success("Task marked as completed")

        # Update batch progress
        batch.update_progress()
        batch.refresh_from_db()

        print_success("Batch progress updated")
        print_info(f"  Progress: {batch.progress}%")
        print_info(f"  Success rate: {batch.success_rate:.1f}%")

        return True

    except Exception as e:
        print_error(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_3_template_models():
    """Test Template models are working correctly."""
    print_header("TEST 3: Template Models")

    try:
        # Clear existing data
        OperationTemplate.objects.all().delete()

        # Create template
        template = OperationTemplate.objects.create(
            id='template_001',
            name='Создание пользователя',
            description='Шаблон для создания пользователя в 1С',
            operation_type='create',
            target_entity='Справочник_Пользователи',
            template_data={
                'fields': {
                    'Наименование': '{{user.name}}',
                    'Код': '{{user.code}}',
                    'ИмяПользователя': '{{user.login}}'
                }
            },
            is_active=True
        )

        print_success(f"Template created: {template.name}")
        print_info(f"  Target entity: {template.target_entity}")
        print_info(f"  Active: {template.is_active}")
        print_info(f"  Fields: {list(template.template_data['fields'].keys())}")

        return True

    except Exception as e:
        print_error(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_4_odata_client():
    """Test OData Client with Mock 1C Server."""
    print_header("TEST 4: OData Client Integration")

    try:
        # Test connection to mock server
        client = ODataClient(
            base_url='http://cc1c-mock-1c-moscow:8080/odata/standard.odata',
            username='Администратор',
            password=''
        )

        print_success("ODataClient initialized")

        # Test metadata
        metadata = client.get_metadata()
        print_success(f"Metadata retrieved: {len(metadata)} bytes")

        # Test entity list
        entity = 'Catalog_Пользователи'
        users = client.get_entity_list(entity)
        print_success(f"Entity list retrieved: {len(users)} items")

        # Test create
        new_user = client.create_entity(entity, {
            'Наименование': 'Тестовый пользователь',
            'Код': 'TEST001'
        })
        print_success(f"Entity created: {new_user.get('Ref_Key')}")

        # Test get
        if new_user.get('Ref_Key'):
            user = client.get_entity(entity, new_user['Ref_Key'])
            print_success(f"Entity retrieved: {user.get('Наименование')}")

        return True

    except Exception as e:
        print_error(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_5_rest_api():
    """Test REST API endpoints."""
    print_header("TEST 5: REST API Endpoints")

    base_url = 'http://localhost:8000'

    try:
        # Test health endpoint
        response = requests.get(f'{base_url}/health')
        if response.status_code == 200:
            print_success(f"Health endpoint: {response.json()['status']}")
        else:
            print_error(f"Health endpoint failed: {response.status_code}")
            return False

        # Test databases list
        response = requests.get(f'{base_url}/api/v1/databases/')
        if response.status_code == 200:
            data = response.json()
            print_success(f"Databases list: {data['count']} items")
        else:
            print_error(f"Databases list failed: {response.status_code}")
            return False

        # Test database detail (if exists)
        if data['count'] > 0:
            db_id = data['results'][0]['id']
            response = requests.get(f'{base_url}/api/v1/databases/{db_id}/')
            if response.status_code == 200:
                db_data = response.json()
                print_success(f"Database detail: {db_data['name']}")
            else:
                print_error(f"Database detail failed: {response.status_code}")

        return True

    except Exception as e:
        print_error(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_6_database_service():
    """Test DatabaseService layer."""
    print_header("TEST 6: Database Service Layer")

    try:
        db = Database.objects.get(id='test_db_001')

        # Test health check
        result = DatabaseService.check_health(db)
        print_success(f"Health check: {result['status']}")
        print_info(f"  Response time: {result.get('response_time', 'N/A')}")

        # Test bulk health check
        databases = Database.objects.filter(status=Database.STATUS_ACTIVE)
        results = DatabaseService.bulk_health_check(databases)
        print_success(f"Bulk health check: {len(results)} databases")

        for db_id, result in results.items():
            status = "✓" if result['healthy'] else "✗"
            print_info(f"  {status} {result['database'].name}: {result['status']}")

        return True

    except Exception as e:
        print_error(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ==================== MAIN ====================

def main():
    print_header("Sprint 1.2 Comprehensive Test Suite")
    print_info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    tests = [
        ("Database Models", test_1_database_models),
        ("Operation Models", test_2_operation_models),
        ("Template Models", test_3_template_models),
        ("OData Client", test_4_odata_client),
        ("REST API", test_5_rest_api),
        ("Database Service", test_6_database_service),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print_error(f"Test '{name}' crashed: {e}")
            results.append((name, False))

    # Summary
    print_header("TEST SUMMARY")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = f"{Colors.GREEN}✓ PASS{Colors.END}" if result else f"{Colors.RED}✗ FAIL{Colors.END}"
        print(f"  {status}  {name}")

    print()
    print(f"Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print_info(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
