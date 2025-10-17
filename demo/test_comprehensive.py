#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Test Suite для Mock 1C OData Server
Включает unit tests, integration tests, edge cases, и performance tests
"""

import sys
import io
import os
import requests
import json
import uuid
import time
import threading
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Фикс для Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Configuration
MOCK_SERVERS = [
    {
        'name': 'Moscow',
        'base_url': 'http://localhost:8081',
        'db_name': 'moscow_001',
        'auth': ('Администратор', 'mock_password')
    },
    {
        'name': 'SPB',
        'base_url': 'http://localhost:8082',
        'db_name': 'spb_001',
        'auth': ('Администратор', 'mock_password')
    },
    {
        'name': 'EKB',
        'base_url': 'http://localhost:8083',
        'db_name': 'ekb_001',
        'auth': ('Администратор', 'mock_password')
    }
]

ORCHESTRATOR_URL = 'http://localhost:8000'

# Test results storage
test_results = []
test_categories = {
    'unit': [],
    'integration': [],
    'edge_case': [],
    'performance': [],
    'error_handling': []
}


class TestResult:
    """Test result model"""
    def __init__(self, category: str, name: str, passed: bool,
                 details: str = "", duration: float = 0.0, severity: str = 'normal'):
        self.category = category
        self.name = name
        self.passed = passed
        self.details = details
        self.duration = duration
        self.severity = severity  # 'critical', 'major', 'minor', 'normal'


def add_test_result(category: str, name: str, passed: bool,
                    details: str = "", duration: float = 0.0, severity: str = 'normal'):
    """Add test result to collection"""
    result = TestResult(category, name, passed, details, duration, severity)
    test_results.append(result)
    test_categories[category].append(result)

    status = "✓ PASS" if passed else "✗ FAIL"
    severity_mark = f"[{severity.upper()}]" if severity in ['critical', 'major'] else ""
    duration_str = f"({duration:.3f}s)" if duration > 0 else ""

    print(f"{status} {severity_mark} [{category}] {name} {duration_str}")
    if details:
        # Truncate long details
        if len(details) > 200:
            details = details[:200] + "..."
        print(f"    → {details}")


def measure_time(func):
    """Decorator to measure function execution time"""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        return result, duration
    return wrapper


# ============================================================================
# UNIT TESTS - Mock Server API
# ============================================================================

def test_health_endpoint(server: Dict):
    """Test: Health check endpoint"""
    try:
        start = time.time()
        response = requests.get(f"{server['base_url']}/health", timeout=5)
        duration = time.time() - start

        if response.status_code == 200:
            data = response.json()
            required_fields = ['status', 'database', 'entities', 'timestamp']
            missing = [f for f in required_fields if f not in data]

            if missing:
                add_test_result('unit', f"{server['name']} - Health endpoint format",
                              False, f"Missing fields: {missing}", duration, 'major')
            else:
                add_test_result('unit', f"{server['name']} - Health endpoint",
                              True, f"DB: {data['database']}", duration)
            return not missing
        else:
            add_test_result('unit', f"{server['name']} - Health endpoint",
                          False, f"Status: {response.status_code}", duration, 'critical')
            return False
    except Exception as e:
        add_test_result('unit', f"{server['name']} - Health endpoint",
                      False, f"Exception: {str(e)}", 0, 'critical')
        return False


def test_metadata_endpoint(server: Dict):
    """Test: OData metadata endpoint"""
    try:
        start = time.time()
        response = requests.get(
            f"{server['base_url']}/odata/standard.odata/$metadata",
            timeout=5
        )
        duration = time.time() - start

        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            if 'xml' not in content_type.lower():
                add_test_result('unit', f"{server['name']} - Metadata content-type",
                              False, f"Wrong content-type: {content_type}", duration, 'major')
                return False

            # Check XML content
            if '<edmx:Edmx' not in response.text:
                add_test_result('unit', f"{server['name']} - Metadata XML format",
                              False, "Invalid XML structure", duration, 'major')
                return False

            add_test_result('unit', f"{server['name']} - Metadata endpoint",
                          True, f"Size: {len(response.text)} bytes", duration)
            return True
        else:
            add_test_result('unit', f"{server['name']} - Metadata endpoint",
                          False, f"Status: {response.status_code}", duration, 'critical')
            return False
    except Exception as e:
        add_test_result('unit', f"{server['name']} - Metadata endpoint",
                      False, f"Exception: {str(e)}", 0, 'critical')
        return False


def test_authentication(server: Dict):
    """Test: HTTP Basic Authentication"""
    base_url = f"{server['base_url']}/odata/standard.odata"
    entity_type = 'Catalog_Пользователи'

    # Test 1: No auth
    try:
        start = time.time()
        response = requests.get(f"{base_url}/{entity_type}", timeout=5)
        duration = time.time() - start

        if response.status_code == 401:
            add_test_result('unit', f"{server['name']} - Auth: No credentials",
                          True, "Correctly rejected", duration)
        else:
            add_test_result('unit', f"{server['name']} - Auth: No credentials",
                          False, f"Expected 401, got {response.status_code}", duration, 'major')
    except Exception as e:
        add_test_result('unit', f"{server['name']} - Auth: No credentials",
                      False, f"Exception: {str(e)}", 0, 'major')

    # Test 2: Wrong password
    try:
        start = time.time()
        response = requests.get(
            f"{base_url}/{entity_type}",
            auth=(server['auth'][0], 'wrong_password'),
            timeout=5
        )
        duration = time.time() - start

        if response.status_code == 401:
            add_test_result('unit', f"{server['name']} - Auth: Wrong password",
                          True, "Correctly rejected", duration)
        else:
            add_test_result('unit', f"{server['name']} - Auth: Wrong password",
                          False, f"Expected 401, got {response.status_code}", duration, 'major')
    except Exception as e:
        add_test_result('unit', f"{server['name']} - Auth: Wrong password",
                      False, f"Exception: {str(e)}", 0, 'major')

    # Test 3: Correct credentials
    try:
        start = time.time()
        response = requests.get(
            f"{base_url}/{entity_type}",
            auth=server['auth'],
            timeout=5
        )
        duration = time.time() - start

        if response.status_code == 200:
            add_test_result('unit', f"{server['name']} - Auth: Correct credentials",
                          True, "Successfully authenticated", duration)
        else:
            add_test_result('unit', f"{server['name']} - Auth: Correct credentials",
                          False, f"Expected 200, got {response.status_code}", duration, 'critical')
    except Exception as e:
        add_test_result('unit', f"{server['name']} - Auth: Correct credentials",
                      False, f"Exception: {str(e)}", 0, 'critical')


def test_crud_operations(server: Dict):
    """Test: Basic CRUD operations"""
    base_url = f"{server['base_url']}/odata/standard.odata"
    auth = server['auth']
    entity_type = 'Catalog_Пользователи'

    test_entity = {
        'Description': f'Test User {server["db_name"]}',
        'Code': '99999',
        'ИмяПользователя': f'test_{server["db_name"]}',
        'Email': f'test@{server["db_name"]}.com'
    }

    created_id = None

    # CREATE
    try:
        start = time.time()
        response = requests.post(
            f"{base_url}/{entity_type}",
            json=test_entity,
            auth=auth,
            timeout=5
        )
        duration = time.time() - start

        if response.status_code == 201:
            created = response.json()
            created_id = created['d']['Ref_Key']

            # Validate UUID format
            try:
                uuid.UUID(created_id)
                add_test_result('unit', f"{server['name']} - CRUD: CREATE",
                              True, f"ID: {created_id[:8]}...", duration)
            except ValueError:
                add_test_result('unit', f"{server['name']} - CRUD: CREATE",
                              False, f"Invalid UUID format: {created_id}", duration, 'major')
                return False
        else:
            add_test_result('unit', f"{server['name']} - CRUD: CREATE",
                          False, f"Status: {response.status_code}", duration, 'critical')
            return False
    except Exception as e:
        add_test_result('unit', f"{server['name']} - CRUD: CREATE",
                      False, f"Exception: {str(e)}", 0, 'critical')
        return False

    # READ (list)
    try:
        start = time.time()
        response = requests.get(f"{base_url}/{entity_type}", auth=auth, timeout=5)
        duration = time.time() - start

        if response.status_code == 200:
            data = response.json()
            if 'd' in data and 'results' in data['d']:
                count = len(data['d']['results'])
                add_test_result('unit', f"{server['name']} - CRUD: READ (list)",
                              True, f"Found {count} entities", duration)
            else:
                add_test_result('unit', f"{server['name']} - CRUD: READ (list)",
                              False, "Invalid response format", duration, 'major')
        else:
            add_test_result('unit', f"{server['name']} - CRUD: READ (list)",
                          False, f"Status: {response.status_code}", duration, 'critical')
    except Exception as e:
        add_test_result('unit', f"{server['name']} - CRUD: READ (list)",
                      False, f"Exception: {str(e)}", 0, 'critical')

    # READ (by ID)
    if created_id:
        try:
            start = time.time()
            response = requests.get(
                f"{base_url}/{entity_type}(guid'{created_id}')",
                auth=auth,
                timeout=5
            )
            duration = time.time() - start

            if response.status_code == 200:
                entity = response.json()
                if entity['d']['Ref_Key'] == created_id:
                    add_test_result('unit', f"{server['name']} - CRUD: READ (by ID)",
                                  True, f"Retrieved correctly", duration)
                else:
                    add_test_result('unit', f"{server['name']} - CRUD: READ (by ID)",
                                  False, "ID mismatch", duration, 'major')
            else:
                add_test_result('unit', f"{server['name']} - CRUD: READ (by ID)",
                              False, f"Status: {response.status_code}", duration, 'critical')
        except Exception as e:
            add_test_result('unit', f"{server['name']} - CRUD: READ (by ID)",
                          False, f"Exception: {str(e)}", 0, 'critical')

    # UPDATE
    if created_id:
        try:
            start = time.time()
            update_data = {'Email': f'updated@{server["db_name"]}.com'}
            response = requests.patch(
                f"{base_url}/{entity_type}(guid'{created_id}')",
                json=update_data,
                auth=auth,
                timeout=5
            )
            duration = time.time() - start

            if response.status_code == 200:
                updated = response.json()
                if updated['d']['Email'] == update_data['Email']:
                    add_test_result('unit', f"{server['name']} - CRUD: UPDATE",
                                  True, "Email updated", duration)
                else:
                    add_test_result('unit', f"{server['name']} - CRUD: UPDATE",
                                  False, "Update not applied", duration, 'major')
            else:
                add_test_result('unit', f"{server['name']} - CRUD: UPDATE",
                              False, f"Status: {response.status_code}", duration, 'critical')
        except Exception as e:
            add_test_result('unit', f"{server['name']} - CRUD: UPDATE",
                          False, f"Exception: {str(e)}", 0, 'critical')

    # DELETE
    if created_id:
        try:
            start = time.time()
            response = requests.delete(
                f"{base_url}/{entity_type}(guid'{created_id}')",
                auth=auth,
                timeout=5
            )
            duration = time.time() - start

            if response.status_code == 204:
                # Verify deletion
                verify = requests.get(
                    f"{base_url}/{entity_type}(guid'{created_id}')",
                    auth=auth,
                    timeout=5
                )
                if verify.status_code == 404:
                    add_test_result('unit', f"{server['name']} - CRUD: DELETE",
                                  True, "Entity deleted", duration)
                else:
                    add_test_result('unit', f"{server['name']} - CRUD: DELETE",
                                  False, "Entity still exists", duration, 'major')
            else:
                add_test_result('unit', f"{server['name']} - CRUD: DELETE",
                              False, f"Status: {response.status_code}", duration, 'critical')
        except Exception as e:
            add_test_result('unit', f"{server['name']} - CRUD: DELETE",
                          False, f"Exception: {str(e)}", 0, 'critical')


# ============================================================================
# EDGE CASES & DATA VALIDATION
# ============================================================================

def test_edge_cases(server: Dict):
    """Test: Edge cases and boundary conditions"""
    base_url = f"{server['base_url']}/odata/standard.odata"
    auth = server['auth']
    entity_type = 'Catalog_Пользователи'

    # Test 1: Create with missing required fields
    try:
        start = time.time()
        response = requests.post(
            f"{base_url}/{entity_type}",
            json={'ИмяПользователя': 'test'},  # Missing Description and Code
            auth=auth,
            timeout=5
        )
        duration = time.time() - start

        if response.status_code == 400:
            add_test_result('edge_case', f"{server['name']} - Missing required fields",
                          True, "Correctly rejected", duration)
        else:
            add_test_result('edge_case', f"{server['name']} - Missing required fields",
                          False, f"Expected 400, got {response.status_code}", duration, 'major')
    except Exception as e:
        add_test_result('edge_case', f"{server['name']} - Missing required fields",
                      False, f"Exception: {str(e)}", 0, 'major')

    # Test 2: Update non-existent entity
    try:
        fake_id = str(uuid.uuid4())
        start = time.time()
        response = requests.patch(
            f"{base_url}/{entity_type}(guid'{fake_id}')",
            json={'Email': 'test@test.com'},
            auth=auth,
            timeout=5
        )
        duration = time.time() - start

        if response.status_code == 404:
            add_test_result('edge_case', f"{server['name']} - Update non-existent",
                          True, "Correctly returned 404", duration)
        else:
            add_test_result('edge_case', f"{server['name']} - Update non-existent",
                          False, f"Expected 404, got {response.status_code}", duration, 'major')
    except Exception as e:
        add_test_result('edge_case', f"{server['name']} - Update non-existent",
                      False, f"Exception: {str(e)}", 0, 'major')

    # Test 3: Delete non-existent entity
    try:
        fake_id = str(uuid.uuid4())
        start = time.time()
        response = requests.delete(
            f"{base_url}/{entity_type}(guid'{fake_id}')",
            auth=auth,
            timeout=5
        )
        duration = time.time() - start

        if response.status_code == 404:
            add_test_result('edge_case', f"{server['name']} - Delete non-existent",
                          True, "Correctly returned 404", duration)
        else:
            add_test_result('edge_case', f"{server['name']} - Delete non-existent",
                          False, f"Expected 404, got {response.status_code}", duration, 'major')
    except Exception as e:
        add_test_result('edge_case', f"{server['name']} - Delete non-existent",
                      False, f"Exception: {str(e)}", 0, 'major')

    # Test 4: Invalid UUID format
    try:
        start = time.time()
        response = requests.get(
            f"{base_url}/{entity_type}(guid'invalid-uuid')",
            auth=auth,
            timeout=5
        )
        duration = time.time() - start

        if response.status_code == 404:
            add_test_result('edge_case', f"{server['name']} - Invalid UUID",
                          True, "Handled gracefully", duration)
        else:
            add_test_result('edge_case', f"{server['name']} - Invalid UUID",
                          False, f"Expected 404, got {response.status_code}", duration, 'minor')
    except Exception as e:
        add_test_result('edge_case', f"{server['name']} - Invalid UUID",
                      False, f"Exception: {str(e)}", 0, 'minor')

    # Test 5: Long strings
    try:
        start = time.time()
        long_string = 'A' * 500
        response = requests.post(
            f"{base_url}/{entity_type}",
            json={
                'Description': long_string,
                'Code': '99999',
                'Email': 'test@test.com'
            },
            auth=auth,
            timeout=5
        )
        duration = time.time() - start

        if response.status_code == 201:
            # Clean up
            created_id = response.json()['d']['Ref_Key']
            requests.delete(f"{base_url}/{entity_type}(guid'{created_id}')", auth=auth, timeout=5)
            add_test_result('edge_case', f"{server['name']} - Long strings (500 chars)",
                          True, "Accepted", duration)
        else:
            add_test_result('edge_case', f"{server['name']} - Long strings (500 chars)",
                          False, f"Status: {response.status_code}", duration, 'minor')
    except Exception as e:
        add_test_result('edge_case', f"{server['name']} - Long strings",
                      False, f"Exception: {str(e)}", 0, 'minor')

    # Test 6: Special characters (кириллица)
    try:
        start = time.time()
        response = requests.post(
            f"{base_url}/{entity_type}",
            json={
                'Description': 'Тестовый пользователь №1',
                'Code': '12345',
                'ИмяПользователя': 'Иванов_И_И',
                'Email': 'иванов@тест.рф'
            },
            auth=auth,
            timeout=5
        )
        duration = time.time() - start

        if response.status_code == 201:
            created_id = response.json()['d']['Ref_Key']
            # Verify cyrillic was saved correctly
            verify = requests.get(
                f"{base_url}/{entity_type}(guid'{created_id}')",
                auth=auth,
                timeout=5
            )
            if verify.status_code == 200:
                entity = verify.json()['d']
                if 'Тестовый' in entity['Description']:
                    add_test_result('edge_case', f"{server['name']} - Cyrillic characters",
                                  True, "Correctly handled", duration)
                else:
                    add_test_result('edge_case', f"{server['name']} - Cyrillic characters",
                                  False, "Encoding corrupted", duration, 'major')
            # Clean up
            requests.delete(f"{base_url}/{entity_type}(guid'{created_id}')", auth=auth, timeout=5)
        else:
            add_test_result('edge_case', f"{server['name']} - Cyrillic characters",
                          False, f"Status: {response.status_code}", duration, 'major')
    except Exception as e:
        add_test_result('edge_case', f"{server['name']} - Cyrillic characters",
                      False, f"Exception: {str(e)}", 0, 'major')


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

def test_concurrent_requests(server: Dict):
    """Test: Concurrent request handling"""
    base_url = f"{server['base_url']}/odata/standard.odata"
    auth = server['auth']
    entity_type = 'Catalog_Пользователи'

    num_requests = 20
    created_ids = []

    def create_entity(index):
        try:
            response = requests.post(
                f"{base_url}/{entity_type}",
                json={
                    'Description': f'Concurrent Test {index}',
                    'Code': f'{10000 + index}',
                    'Email': f'test{index}@test.com'
                },
                auth=auth,
                timeout=10
            )
            if response.status_code == 201:
                return True, response.json()['d']['Ref_Key']
            return False, None
        except Exception as e:
            return False, str(e)

    start = time.time()
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(create_entity, i) for i in range(num_requests)]
        results = [future.result() for future in as_completed(futures)]
    duration = time.time() - start

    success_count = sum(1 for success, _ in results if success)
    created_ids = [id for success, id in results if success and isinstance(id, str)]

    # Clean up
    for entity_id in created_ids:
        try:
            requests.delete(f"{base_url}/{entity_type}(guid'{entity_id}')", auth=auth, timeout=5)
        except:
            pass

    if success_count == num_requests:
        req_per_sec = num_requests / duration
        add_test_result('performance', f"{server['name']} - Concurrent creates ({num_requests})",
                      True, f"{req_per_sec:.1f} req/s", duration)
    else:
        add_test_result('performance', f"{server['name']} - Concurrent creates",
                      False, f"Only {success_count}/{num_requests} succeeded", duration, 'major')


def test_response_time(server: Dict):
    """Test: Response time under normal load"""
    base_url = f"{server['base_url']}/odata/standard.odata"
    auth = server['auth']
    entity_type = 'Catalog_Пользователи'

    # Measure 10 sequential requests
    times = []
    for i in range(10):
        try:
            start = time.time()
            response = requests.get(f"{base_url}/{entity_type}", auth=auth, timeout=5)
            duration = time.time() - start
            if response.status_code == 200:
                times.append(duration)
        except:
            pass

    if times:
        avg_time = sum(times) / len(times)
        max_time = max(times)
        min_time = min(times)

        if avg_time < 0.1:  # < 100ms
            add_test_result('performance', f"{server['name']} - Response time",
                          True, f"Avg: {avg_time*1000:.0f}ms, Max: {max_time*1000:.0f}ms",
                          sum(times))
        else:
            add_test_result('performance', f"{server['name']} - Response time",
                          False, f"Slow: Avg {avg_time*1000:.0f}ms", sum(times), 'minor')
    else:
        add_test_result('performance', f"{server['name']} - Response time",
                      False, "No successful requests", 0, 'major')


# ============================================================================
# INTEGRATION TESTS - Orchestrator
# ============================================================================

def test_orchestrator_health():
    """Test: Django Orchestrator health"""
    try:
        start = time.time()
        response = requests.get(f"{ORCHESTRATOR_URL}/health", timeout=10)
        duration = time.time() - start

        if response.status_code == 200:
            data = response.json()
            add_test_result('integration', "Orchestrator health",
                          True, f"Status: {data.get('status')}", duration)
            return True
        else:
            add_test_result('integration', "Orchestrator health",
                          False, f"Status: {response.status_code}", duration, 'critical')
            return False
    except Exception as e:
        add_test_result('integration', "Orchestrator health",
                      False, f"Exception: {str(e)}", 0, 'critical')
        return False


def test_orchestrator_integration(server: Dict):
    """Test: Orchestrator → Mock Server integration"""
    # Note: This test may fail due to Django API not being fully implemented
    # This is acceptable for current phase
    try:
        start = time.time()
        db_data = {
            'name': f'Test {server["name"]}',
            'code': server['db_name'],
            'odata_url': f'{server["base_url"]}/odata/standard.odata',
            'username': server['auth'][0],
            'password': server['auth'][1],
            'is_active': True
        }

        response = requests.post(
            f"{ORCHESTRATOR_URL}/api/v1/databases/",
            json=db_data,
            timeout=10
        )
        duration = time.time() - start

        if response.status_code in [200, 201]:
            add_test_result('integration', f"Orchestrator DB API - {server['name']}",
                          True, "Database created", duration)
        else:
            # Expected to fail if API not implemented
            add_test_result('integration', f"Orchestrator DB API - {server['name']}",
                          False, f"Status: {response.status_code} (expected if API not ready)",
                          duration, 'minor')
    except Exception as e:
        add_test_result('integration', f"Orchestrator DB API - {server['name']}",
                      False, f"Exception: {str(e)} (expected if API not ready)", 0, 'minor')


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

def test_error_responses(server: Dict):
    """Test: OData error format compliance"""
    base_url = f"{server['base_url']}/odata/standard.odata"
    auth = server['auth']

    # Test 404 error format
    try:
        response = requests.get(
            f"{base_url}/NonExistentEntity",
            auth=auth,
            timeout=5
        )

        if response.status_code == 404:
            try:
                error_data = response.json()
                if 'odata.error' in error_data:
                    add_test_result('error_handling', f"{server['name']} - OData error format",
                                  True, "Correct format")
                else:
                    add_test_result('error_handling', f"{server['name']} - OData error format",
                                  False, "Non-standard format", 0, 'minor')
            except:
                add_test_result('error_handling', f"{server['name']} - OData error format",
                              False, "Not JSON", 0, 'minor')
    except Exception as e:
        add_test_result('error_handling', f"{server['name']} - Error responses",
                      False, f"Exception: {str(e)}", 0, 'minor')


# ============================================================================
# CONTAINER HEALTH TESTS
# ============================================================================

def test_containers_health():
    """Test: All containers are healthy"""
    import subprocess

    try:
        result = subprocess.run(
            ['docker-compose', '-f', 'docker-compose.demo.yml', 'ps', '--format', 'json'],
            capture_output=True,
            text=True,
            cwd='C:\\1CProject\\command-center-1c',
            timeout=10
        )

        if result.returncode == 0:
            # Parse output
            lines = result.stdout.strip().split('\n')
            containers = []
            for line in lines:
                if line:
                    try:
                        containers.append(json.loads(line))
                    except:
                        pass

            healthy_count = sum(1 for c in containers if 'healthy' in c.get('Health', '').lower() or c.get('State') == 'running')
            total_count = len(containers)

            if healthy_count == total_count and total_count >= 6:
                add_test_result('unit', "Container health check",
                              True, f"{healthy_count}/{total_count} containers healthy")
            else:
                add_test_result('unit', "Container health check",
                              False, f"Only {healthy_count}/{total_count} healthy", 0, 'major')
        else:
            add_test_result('unit', "Container health check",
                          False, "Failed to check containers", 0, 'major')
    except Exception as e:
        add_test_result('unit', "Container health check",
                      False, f"Exception: {str(e)}", 0, 'minor')


# ============================================================================
# MAIN TEST ORCHESTRATION
# ============================================================================

def print_header(title: str):
    """Print section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def print_summary():
    """Print test summary with statistics"""
    print_header("TEST SUMMARY")

    total = len(test_results)
    passed = sum(1 for r in test_results if r.passed)
    failed = total - passed

    # Count by severity
    critical_failed = sum(1 for r in test_results if not r.passed and r.severity == 'critical')
    major_failed = sum(1 for r in test_results if not r.passed and r.severity == 'major')
    minor_failed = sum(1 for r in test_results if not r.passed and r.severity == 'minor')

    # Count by category
    print("BY CATEGORY:")
    for category, results in test_categories.items():
        if results:
            cat_passed = sum(1 for r in results if r.passed)
            cat_total = len(results)
            print(f"  {category.upper():15s}: {cat_passed}/{cat_total} passed")

    print(f"\nOVERALL:")
    print(f"  Total tests: {total}")
    print(f"  Passed: {passed} ({passed/total*100:.1f}%)")
    print(f"  Failed: {failed} ({failed/total*100:.1f}%)")

    if failed > 0:
        print(f"\nBY SEVERITY:")
        print(f"  CRITICAL: {critical_failed}")
        print(f"  MAJOR: {major_failed}")
        print(f"  MINOR: {minor_failed}")
        print(f"  Normal: {failed - critical_failed - major_failed - minor_failed}")

    # Failed tests
    if failed > 0:
        print(f"\n{'='*70}")
        print("FAILED TESTS:")
        print(f"{'='*70}")

        for result in test_results:
            if not result.passed:
                severity_mark = f"[{result.severity.upper()}]" if result.severity in ['critical', 'major', 'minor'] else ""
                print(f"\n  {severity_mark} [{result.category}] {result.name}")
                if result.details:
                    details = result.details[:150] + "..." if len(result.details) > 150 else result.details
                    print(f"    → {details}")

    # Performance metrics
    perf_results = [r for r in test_results if r.category == 'performance' and r.passed]
    if perf_results:
        print(f"\n{'='*70}")
        print("PERFORMANCE METRICS:")
        print(f"{'='*70}")
        for result in perf_results:
            print(f"  {result.name}: {result.details}")

    print(f"\n{'='*70}\n")

    return failed == 0


def wait_for_services():
    """Wait for all services to be ready"""
    print_header("Waiting for services")

    services = [
        ('Mock Moscow', 'http://localhost:8081/health'),
        ('Mock SPB', 'http://localhost:8082/health'),
        ('Mock EKB', 'http://localhost:8083/health'),
        ('Orchestrator', 'http://localhost:8000/health'),
    ]

    all_ready = True
    for name, url in services:
        ready = False
        for attempt in range(15):
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    print(f"✓ {name} is ready")
                    ready = True
                    break
            except:
                pass
            time.sleep(2)

        if not ready:
            print(f"✗ {name} is NOT ready")
            all_ready = False

    return all_ready


def main():
    """Main test runner"""
    print("\n" + "="*70)
    print("  CommandCenter1C - Comprehensive Test Suite")
    print("  Mock 1C OData Server Testing")
    print("="*70)

    # Wait for services
    if not wait_for_services():
        print("\n⚠ WARNING: Some services are not ready. Tests may fail.")
        time.sleep(2)

    # Container health check
    print_header("Container Health Check")
    test_containers_health()

    # Unit tests for each mock server
    print_header("UNIT TESTS - Mock Server API")
    for server in MOCK_SERVERS:
        test_health_endpoint(server)
        test_metadata_endpoint(server)
        test_authentication(server)
        test_crud_operations(server)

    # Edge cases
    print_header("EDGE CASES & DATA VALIDATION")
    for server in MOCK_SERVERS:
        test_edge_cases(server)

    # Error handling
    print_header("ERROR HANDLING")
    for server in MOCK_SERVERS:
        test_error_responses(server)

    # Performance tests
    print_header("PERFORMANCE TESTS")
    for server in MOCK_SERVERS:
        test_response_time(server)
        test_concurrent_requests(server)

    # Integration tests
    print_header("INTEGRATION TESTS - Orchestrator")
    test_orchestrator_health()
    for server in MOCK_SERVERS:
        test_orchestrator_integration(server)

    # Summary
    success = print_summary()

    return 0 if success else 1


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
