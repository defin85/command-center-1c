#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Suite с обходом проблемы кириллицы в HTTP Basic Auth
Использует прямую установку заголовка Authorization
"""

import sys
import io
import requests
import json
import uuid
import base64
from typing import Dict

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

MOCK_SERVER = {
    'name': 'Moscow',
    'base_url': 'http://localhost:8081',
    'db_name': 'moscow_001',
    'username': 'Администратор',
    'password': 'mock_password'
}


def get_auth_header(username: str, password: str) -> Dict[str, str]:
    """Generate HTTP Basic Auth header with UTF-8 encoding"""
    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode('utf-8')).decode('ascii')
    return {'Authorization': f'Basic {encoded}'}


def test_basic_operations():
    """Test basic CRUD operations with cyrillic auth"""
    base_url = f"{MOCK_SERVER['base_url']}/odata/standard.odata"
    headers = get_auth_header(MOCK_SERVER['username'], MOCK_SERVER['password'])
    entity_type = 'Catalog_Пользователи'

    print("\n" + "="*70)
    print("Testing Mock 1C OData Server with Cyrillic Auth Workaround")
    print("="*70 + "\n")

    # Test 1: Health check (no auth)
    print("1. Health Check...")
    try:
        response = requests.get(f"{MOCK_SERVER['base_url']}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Health check OK: {data['database']}, {data['status']}")
        else:
            print(f"   ✗ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"   ✗ Exception: {e}")

    # Test 2: Metadata (no auth)
    print("\n2. Metadata Endpoint...")
    try:
        response = requests.get(f"{base_url}/$metadata", timeout=5)
        if response.status_code == 200:
            print(f"   ✓ Metadata OK: {len(response.text)} bytes")
        else:
            print(f"   ✗ Metadata failed: {response.status_code}")
    except Exception as e:
        print(f"   ✗ Exception: {e}")

    # Test 3: List entities (with auth)
    print("\n3. List Entities (with Cyrillic auth)...")
    try:
        response = requests.get(f"{base_url}/{entity_type}", headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            count = len(data['d']['results'])
            print(f"   ✓ List OK: Found {count} entities")
        else:
            print(f"   ✗ List failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   ✗ Exception: {e}")

    # Test 4: CREATE entity
    print("\n4. CREATE Entity...")
    test_entity = {
        'Description': 'Тестовый пользователь',
        'Code': '99999',
        'ИмяПользователя': 'test_user_cyrillic',
        'Email': 'test@example.com'
    }

    created_id = None
    try:
        response = requests.post(
            f"{base_url}/{entity_type}",
            json=test_entity,
            headers=headers,
            timeout=5
        )
        if response.status_code == 201:
            created = response.json()
            created_id = created['d']['Ref_Key']
            print(f"   ✓ CREATE OK: ID = {created_id}")
            print(f"   Description: {created['d']['Description']}")
        else:
            print(f"   ✗ CREATE failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   ✗ Exception: {e}")

    # Test 5: READ by ID
    if created_id:
        print(f"\n5. READ Entity by ID...")
        try:
            response = requests.get(
                f"{base_url}/{entity_type}(guid'{created_id}')",
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                entity = response.json()['d']
                print(f"   ✓ READ OK")
                print(f"   Description: {entity['Description']}")
                print(f"   Email: {entity['Email']}")
            else:
                print(f"   ✗ READ failed: {response.status_code}")
        except Exception as e:
            print(f"   ✗ Exception: {e}")

    # Test 6: UPDATE entity
    if created_id:
        print(f"\n6. UPDATE Entity...")
        try:
            update_data = {'Email': 'updated@example.com'}
            response = requests.patch(
                f"{base_url}/{entity_type}(guid'{created_id}')",
                json=update_data,
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                updated = response.json()['d']
                print(f"   ✓ UPDATE OK")
                print(f"   New Email: {updated['Email']}")
            else:
                print(f"   ✗ UPDATE failed: {response.status_code}")
        except Exception as e:
            print(f"   ✗ Exception: {e}")

    # Test 7: DELETE entity
    if created_id:
        print(f"\n7. DELETE Entity...")
        try:
            response = requests.delete(
                f"{base_url}/{entity_type}(guid'{created_id}')",
                headers=headers,
                timeout=5
            )
            if response.status_code == 204:
                print(f"   ✓ DELETE OK")

                # Verify deletion
                verify = requests.get(
                    f"{base_url}/{entity_type}(guid'{created_id}')",
                    headers=headers,
                    timeout=5
                )
                if verify.status_code == 404:
                    print(f"   ✓ Deletion verified (404)")
                else:
                    print(f"   ⚠ Entity still exists (status: {verify.status_code})")
            else:
                print(f"   ✗ DELETE failed: {response.status_code}")
        except Exception as e:
            print(f"   ✗ Exception: {e}")

    # Test 8: Test wrong credentials
    print(f"\n8. Test Wrong Credentials...")
    try:
        wrong_headers = get_auth_header(MOCK_SERVER['username'], 'wrong_password')
        response = requests.get(
            f"{base_url}/{entity_type}",
            headers=wrong_headers,
            timeout=5
        )
        if response.status_code == 401:
            print(f"   ✓ Correctly rejected with 401")
        else:
            print(f"   ✗ Wrong status: {response.status_code} (expected 401)")
    except Exception as e:
        print(f"   ✗ Exception: {e}")

    # Test 9: Test missing auth
    print(f"\n9. Test Missing Auth...")
    try:
        response = requests.get(f"{base_url}/{entity_type}", timeout=5)
        if response.status_code == 401:
            print(f"   ✓ Correctly rejected with 401")
        else:
            print(f"   ✗ Wrong status: {response.status_code} (expected 401)")
    except Exception as e:
        print(f"   ✗ Exception: {e}")

    # Test 10: Test invalid entity type
    print(f"\n10. Test Invalid Entity Type...")
    try:
        response = requests.get(
            f"{base_url}/NonExistentEntity",
            headers=headers,
            timeout=5
        )
        if response.status_code == 404:
            error_data = response.json()
            if 'odata.error' in error_data:
                print(f"   ✓ Correctly returned 404 with OData error format")
            else:
                print(f"   ⚠ 404 but wrong error format")
        else:
            print(f"   ✗ Wrong status: {response.status_code} (expected 404)")
    except Exception as e:
        print(f"   ✗ Exception: {e}")

    # Test 11: Test special characters (full cyrillic)
    print(f"\n11. Test Full Cyrillic Data...")
    try:
        cyrillic_entity = {
            'Description': 'Иванов Иван Иванович',
            'Code': '00001',
            'ИмяПользователя': 'Иванов_И_И',
            'Email': 'ivanov@компания.рф'
        }
        response = requests.post(
            f"{base_url}/{entity_type}",
            json=cyrillic_entity,
            headers=headers,
            timeout=5
        )
        if response.status_code == 201:
            created = response.json()['d']
            cyrillic_id = created['Ref_Key']
            print(f"   ✓ CREATE with Cyrillic OK")
            print(f"   Description: {created['Description']}")

            # Verify readback
            verify = requests.get(
                f"{base_url}/{entity_type}(guid'{cyrillic_id}')",
                headers=headers,
                timeout=5
            )
            if verify.status_code == 200:
                entity = verify.json()['d']
                if 'Иванов' in entity['Description']:
                    print(f"   ✓ Cyrillic encoding preserved correctly")
                else:
                    print(f"   ⚠ Cyrillic encoding corrupted: {entity['Description']}")

            # Cleanup
            requests.delete(
                f"{base_url}/{entity_type}(guid'{cyrillic_id}')",
                headers=headers,
                timeout=5
            )
        else:
            print(f"   ✗ CREATE failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   ✗ Exception: {e}")

    # Test 12: Test duplicate Ref_Key
    print(f"\n12. Test Duplicate Ref_Key...")
    try:
        test_id = str(uuid.uuid4())
        entity1 = {
            'Ref_Key': test_id,
            'Description': 'First Entity',
            'Code': '10001',
            'Email': 'first@test.com'
        }
        entity2 = {
            'Ref_Key': test_id,  # Same ID
            'Description': 'Second Entity',
            'Code': '10002',
            'Email': 'second@test.com'
        }

        # Create first
        response1 = requests.post(
            f"{base_url}/{entity_type}",
            json=entity1,
            headers=headers,
            timeout=5
        )

        if response1.status_code == 201:
            # Try to create duplicate
            response2 = requests.post(
                f"{base_url}/{entity_type}",
                json=entity2,
                headers=headers,
                timeout=5
            )

            if response2.status_code == 409:
                print(f"   ✓ Duplicate correctly rejected with 409")
            else:
                print(f"   ✗ Wrong status: {response2.status_code} (expected 409)")

            # Cleanup
            requests.delete(
                f"{base_url}/{entity_type}(guid'{test_id}')",
                headers=headers,
                timeout=5
            )
        else:
            print(f"   ✗ First CREATE failed: {response1.status_code}")
    except Exception as e:
        print(f"   ✗ Exception: {e}")

    print("\n" + "="*70)
    print("Testing Complete!")
    print("="*70 + "\n")


if __name__ == '__main__':
    test_basic_operations()
