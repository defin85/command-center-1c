#!/usr/bin/env python3
"""
Automated Test Script для Demo стенда CommandCenter1C

Проверяет работоспособность всех компонентов:
- Mock 1C OData Servers
- Django Orchestrator
- Integration между компонентами
"""

import requests
import json
import time
import sys
from typing import Dict, List, Tuple


# ANSI цвета для вывода
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_success(message: str):
    print(f"{Colors.GREEN}[OK]{Colors.RESET} {message}")


def print_error(message: str):
    print(f"{Colors.RED}[FAIL]{Colors.RESET} {message}")


def print_info(message: str):
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {message}")


def print_section(title: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


# Configuration
MOCK_SERVERS = [
    {
        'name': 'Moscow',
        'base_url': 'http://localhost:8081',
        'db_name': 'moscow_001',
        'auth': ('Администратор', 'mock_password')
    },
    {
        'name': 'St. Petersburg',
        'base_url': 'http://localhost:8082',
        'db_name': 'spb_001',
        'auth': ('Администратор', 'mock_password')
    },
    {
        'name': 'Ekaterinburg',
        'base_url': 'http://localhost:8083',
        'db_name': 'ekb_001',
        'auth': ('Администратор', 'mock_password')
    }
]

ORCHESTRATOR_URL = 'http://localhost:8000'

# Test results
test_results: List[Tuple[str, bool, str]] = []


def add_test_result(test_name: str, passed: bool, details: str = ""):
    """Добавление результата теста"""
    test_results.append((test_name, passed, details))
    if passed:
        print_success(f"{test_name}")
        if details:
            print(f"  {Colors.YELLOW}{details}{Colors.RESET}")
    else:
        print_error(f"{test_name}")
        if details:
            print(f"  {Colors.RED}{details}{Colors.RESET}")


def test_mock_server_health(server: Dict) -> bool:
    """Тест: Health check mock сервера"""
    try:
        response = requests.get(f"{server['base_url']}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            add_test_result(
                f"Mock {server['name']} - Health Check",
                True,
                f"Database: {data.get('database')}, Status: {data.get('status')}"
            )
            return True
        else:
            add_test_result(
                f"Mock {server['name']} - Health Check",
                False,
                f"Status code: {response.status_code}"
            )
            return False
    except Exception as e:
        add_test_result(
            f"Mock {server['name']} - Health Check",
            False,
            f"Exception: {str(e)}"
        )
        return False


def test_mock_server_metadata(server: Dict) -> bool:
    """Тест: Получение метаданных OData"""
    try:
        response = requests.get(
            f"{server['base_url']}/odata/standard.odata/$metadata",
            timeout=5
        )
        if response.status_code == 200 and 'xml' in response.headers.get('Content-Type', ''):
            add_test_result(
                f"Mock {server['name']} - Metadata",
                True,
                f"Content-Type: {response.headers.get('Content-Type')}"
            )
            return True
        else:
            add_test_result(
                f"Mock {server['name']} - Metadata",
                False,
                f"Status: {response.status_code}"
            )
            return False
    except Exception as e:
        add_test_result(
            f"Mock {server['name']} - Metadata",
            False,
            f"Exception: {str(e)}"
        )
        return False


def test_mock_server_crud(server: Dict) -> bool:
    """Тест: CRUD операции через mock сервер"""
    base_url = f"{server['base_url']}/odata/standard.odata"
    auth = server['auth']
    entity_type = 'Catalog_Пользователи'

    test_entity = {
        'Description': f'Тестовый пользователь {server["name"]}',
        'Code': '99999',
        'ИмяПользователя': f'test_{server["db_name"]}',
        'Email': f'test@{server["db_name"]}.com'
    }

    created_id = None

    try:
        # CREATE
        response = requests.post(
            f"{base_url}/{entity_type}",
            json=test_entity,
            auth=auth,
            timeout=5
        )

        if response.status_code != 201:
            add_test_result(
                f"Mock {server['name']} - CREATE",
                False,
                f"Status: {response.status_code}"
            )
            return False

        created = response.json()
        created_id = created['d']['Ref_Key']
        add_test_result(
            f"Mock {server['name']} - CREATE",
            True,
            f"Created ID: {created_id}"
        )

        # READ (list)
        response = requests.get(
            f"{base_url}/{entity_type}",
            auth=auth,
            timeout=5
        )

        if response.status_code != 200:
            add_test_result(
                f"Mock {server['name']} - READ (list)",
                False,
                f"Status: {response.status_code}"
            )
            return False

        entities = response.json()
        count = len(entities['d']['results'])
        add_test_result(
            f"Mock {server['name']} - READ (list)",
            True,
            f"Found {count} entities"
        )

        # READ (by ID)
        response = requests.get(
            f"{base_url}/{entity_type}(guid'{created_id}')",
            auth=auth,
            timeout=5
        )

        if response.status_code != 200:
            add_test_result(
                f"Mock {server['name']} - READ (by ID)",
                False,
                f"Status: {response.status_code}"
            )
            return False

        entity = response.json()
        add_test_result(
            f"Mock {server['name']} - READ (by ID)",
            True,
            f"Description: {entity['d']['Description']}"
        )

        # UPDATE
        update_data = {'Email': f'updated@{server["db_name"]}.com'}
        response = requests.patch(
            f"{base_url}/{entity_type}(guid'{created_id}')",
            json=update_data,
            auth=auth,
            timeout=5
        )

        if response.status_code != 200:
            add_test_result(
                f"Mock {server['name']} - UPDATE",
                False,
                f"Status: {response.status_code}"
            )
            return False

        updated = response.json()
        add_test_result(
            f"Mock {server['name']} - UPDATE",
            True,
            f"New Email: {updated['d']['Email']}"
        )

        # DELETE
        response = requests.delete(
            f"{base_url}/{entity_type}(guid'{created_id}')",
            auth=auth,
            timeout=5
        )

        if response.status_code != 204:
            add_test_result(
                f"Mock {server['name']} - DELETE",
                False,
                f"Status: {response.status_code}"
            )
            return False

        add_test_result(
            f"Mock {server['name']} - DELETE",
            True,
            f"Deleted ID: {created_id}"
        )

        return True

    except Exception as e:
        add_test_result(
            f"Mock {server['name']} - CRUD",
            False,
            f"Exception: {str(e)}"
        )
        return False


def test_orchestrator_health() -> bool:
    """Тест: Health check Django Orchestrator"""
    try:
        response = requests.get(f"{ORCHESTRATOR_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            add_test_result(
                "Orchestrator - Health Check",
                True,
                f"Status: {data.get('status')}"
            )
            return True
        else:
            add_test_result(
                "Orchestrator - Health Check",
                False,
                f"Status code: {response.status_code}"
            )
            return False
    except Exception as e:
        add_test_result(
            "Orchestrator - Health Check",
            False,
            f"Exception: {str(e)}"
        )
        return False


def test_orchestrator_database_api(server: Dict) -> bool:
    """Тест: Django Database API"""
    try:
        # CREATE Database
        database_data = {
            'name': f'Test DB {server["name"]}',
            'code': server['db_name'],
            'odata_url': f'{server["base_url"]}/odata/standard.odata',
            'username': server['auth'][0],
            'password': server['auth'][1],
            'is_active': True
        }

        response = requests.post(
            f"{ORCHESTRATOR_URL}/api/v1/databases/",
            json=database_data,
            timeout=10
        )

        if response.status_code not in [200, 201]:
            add_test_result(
                f"Orchestrator - CREATE Database ({server['name']})",
                False,
                f"Status: {response.status_code}, Response: {response.text}"
            )
            return False

        created_db = response.json()
        db_id = created_db.get('id')
        add_test_result(
            f"Orchestrator - CREATE Database ({server['name']})",
            True,
            f"Created DB ID: {db_id}"
        )

        # GET Database list
        response = requests.get(
            f"{ORCHESTRATOR_URL}/api/v1/databases/",
            timeout=10
        )

        if response.status_code != 200:
            add_test_result(
                "Orchestrator - GET Databases",
                False,
                f"Status: {response.status_code}"
            )
            return False

        databases = response.json()
        add_test_result(
            "Orchestrator - GET Databases",
            True,
            f"Found {len(databases)} databases"
        )

        return True

    except Exception as e:
        add_test_result(
            f"Orchestrator - Database API ({server['name']})",
            False,
            f"Exception: {str(e)}"
        )
        return False


def test_orchestrator_health_check(server: Dict) -> bool:
    """Тест: Health check через Django API"""
    try:
        # Сначала получаем список баз
        response = requests.get(
            f"{ORCHESTRATOR_URL}/api/v1/databases/",
            timeout=10
        )

        if response.status_code != 200:
            add_test_result(
                f"Orchestrator - Health Check ({server['name']})",
                False,
                "Failed to get databases list"
            )
            return False

        databases = response.json()

        # Находим нашу базу
        target_db = None
        for db in databases:
            if db.get('code') == server['db_name']:
                target_db = db
                break

        if not target_db:
            add_test_result(
                f"Orchestrator - Health Check ({server['name']})",
                False,
                f"Database {server['db_name']} not found"
            )
            return False

        # Выполняем health check
        response = requests.post(
            f"{ORCHESTRATOR_URL}/api/v1/databases/{target_db['id']}/health_check/",
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            add_test_result(
                f"Orchestrator - Health Check ({server['name']})",
                True,
                f"Success: {result.get('success')}, Message: {result.get('message')}"
            )
            return True
        else:
            add_test_result(
                f"Orchestrator - Health Check ({server['name']})",
                False,
                f"Status: {response.status_code}"
            )
            return False

    except Exception as e:
        add_test_result(
            f"Orchestrator - Health Check ({server['name']})",
            False,
            f"Exception: {str(e)}"
        )
        return False


def print_summary():
    """Вывод итоговой статистики"""
    print_section("Test Summary")

    total = len(test_results)
    passed = sum(1 for _, p, _ in test_results if p)
    failed = total - passed

    print(f"Total tests: {total}")
    print(f"{Colors.GREEN}Passed: {passed}{Colors.RESET}")
    print(f"{Colors.RED}Failed: {failed}{Colors.RESET}")
    print(f"Success rate: {(passed/total)*100:.1f}%\n")

    if failed > 0:
        print(f"{Colors.RED}{Colors.BOLD}Failed tests:{Colors.RESET}")
        for name, passed, details in test_results:
            if not passed:
                print(f"  {Colors.RED}[FAIL] {name}{Colors.RESET}")
                if details:
                    print(f"    {details}")


def wait_for_services():
    """Ожидание запуска всех сервисов"""
    print_section("Waiting for services to start")

    services = [
        ('Mock Moscow', 'http://localhost:8081/health'),
        ('Mock SPB', 'http://localhost:8082/health'),
        ('Mock EKB', 'http://localhost:8083/health'),
        ('Orchestrator', 'http://localhost:8000/health'),
    ]

    max_attempts = 30
    for service_name, url in services:
        print_info(f"Checking {service_name}...")
        for attempt in range(max_attempts):
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    print_success(f"{service_name} is ready")
                    break
            except:
                pass

            if attempt == max_attempts - 1:
                print_error(f"{service_name} is not responding after {max_attempts} attempts")
                return False

            time.sleep(2)

    return True


def main():
    """Основная функция запуска тестов"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("=" * 60)
    print("    CommandCenter1C Demo Test Suite")
    print("=" * 60)
    print(f"{Colors.RESET}\n")

    # Ожидание запуска сервисов
    if not wait_for_services():
        print_error("Services are not ready. Exiting.")
        sys.exit(1)

    # Тесты Mock серверов
    print_section("Testing Mock 1C OData Servers")
    for server in MOCK_SERVERS:
        test_mock_server_health(server)
        test_mock_server_metadata(server)
        test_mock_server_crud(server)

    # Тесты Orchestrator
    print_section("Testing Django Orchestrator")
    test_orchestrator_health()

    # Интеграционные тесты
    print_section("Testing Integration")
    for server in MOCK_SERVERS:
        test_orchestrator_database_api(server)
        test_orchestrator_health_check(server)

    # Итоговая статистика
    print_summary()

    # Exit code
    failed_count = sum(1 for _, p, _ in test_results if not p)
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == '__main__':
    main()
