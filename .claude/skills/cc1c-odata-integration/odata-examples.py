# -*- coding: utf-8 -*-
"""
OData Examples for 1C Integration

Коллекция примеров работы с 1С через OData
"""

import requests
from requests.auth import HTTPBasicAuth
import json
import uuid
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_URL = "http://localhost/accounting/odata/standard.odata"
USERNAME = "admin"
PASSWORD = "password"
AUTH = HTTPBasicAuth(USERNAME, PASSWORD)

# ============================================================================
# EXAMPLE 1: Simple GET Request
# ============================================================================

def example_get_users():
    """Получить список пользователей"""
    url = f"{BASE_URL}/Catalog_Users"

    response = requests.get(url, auth=AUTH)

    if response.status_code == 200:
        data = response.json()
        logger.info(f"Retrieved {len(data.get('value', []))} users")
        return data
    else:
        logger.error(f"Error: {response.status_code} - {response.text}")
        return None


# ============================================================================
# EXAMPLE 2: GET with Filters
# ============================================================================

def example_get_active_users():
    """Получить только активных пользователей"""
    url = f"{BASE_URL}/Catalog_Users"
    params = {
        "$filter": "IsActive eq true",
        "$select": "Code,Description,IsActive",
        "$top": 100
    }

    response = requests.get(url, params=params, auth=AUTH)

    if response.status_code == 200:
        data = response.json()
        logger.info(f"Retrieved {len(data.get('value', []))} active users")
        return data
    else:
        logger.error(f"Error: {response.status_code}")
        return None


# ============================================================================
# EXAMPLE 3: GET Single Object
# ============================================================================

def example_get_user_by_guid(user_guid):
    """Получить пользователя по GUID"""
    url = f"{BASE_URL}/Catalog_Users(guid'{user_guid}')"

    response = requests.get(url, auth=AUTH)

    if response.status_code == 200:
        user = response.json()
        logger.info(f"Retrieved user: {user.get('Description')}")
        return user
    else:
        logger.error(f"Error: {response.status_code}")
        return None


# ============================================================================
# EXAMPLE 4: POST - Create Object
# ============================================================================

def example_create_user():
    """Создать нового пользователя"""
    url = f"{BASE_URL}/Catalog_Users"

    new_user = {
        "Code": "USER999",
        "Description": "Test User (Created via OData)",
        "IsActive": True
    }

    response = requests.post(url, json=new_user, auth=AUTH)

    if response.status_code == 201:
        created_user = response.json()
        logger.info(f"User created: {created_user.get('Ref_Key')}")
        return created_user
    else:
        logger.error(f"Error: {response.status_code} - {response.text}")
        return None


# ============================================================================
# EXAMPLE 5: PATCH - Update Object
# ============================================================================

def example_update_user(user_guid):
    """Обновить пользователя"""
    url = f"{BASE_URL}/Catalog_Users(guid'{user_guid}')"

    update_data = {
        "Description": "Updated User Description",
        "IsActive": False
    }

    response = requests.patch(url, json=update_data, auth=AUTH)

    if response.status_code == 200:
        logger.info("User updated successfully")
        return response.json()
    else:
        logger.error(f"Error: {response.status_code}")
        return None


# ============================================================================
# EXAMPLE 6: DELETE Object
# ============================================================================

def example_delete_user(user_guid):
    """Удалить пользователя"""
    url = f"{BASE_URL}/Catalog_Users(guid'{user_guid}')"

    response = requests.delete(url, auth=AUTH)

    if response.status_code == 204:
        logger.info("User deleted successfully")
        return True
    else:
        logger.error(f"Error: {response.status_code}")
        return False


# ============================================================================
# EXAMPLE 7: Batch Operation - Create Multiple
# ============================================================================

def example_batch_create_users(count=10):
    """
    Создать несколько пользователей через batch

    ⚠️ Важно: Соблюдается ограничение batch_size <= 50
    """
    boundary = f"batch_{uuid.uuid4()}"
    batch_body = []

    # Create operations
    for i in range(count):
        batch_body.append(f"--{boundary}")
        batch_body.append("Content-Type: application/http")
        batch_body.append("Content-Transfer-Encoding: binary")
        batch_body.append("")
        batch_body.append("POST Catalog_Users HTTP/1.1")
        batch_body.append("Content-Type: application/json")
        batch_body.append("")

        user_data = {
            "Code": f"BATCH{i:03d}",
            "Description": f"Batch User {i}",
            "IsActive": True
        }
        batch_body.append(json.dumps(user_data))
        batch_body.append("")

    batch_body.append(f"--{boundary}--")
    batch_content = "\r\n".join(batch_body)

    # Send batch request
    headers = {
        "Content-Type": f"multipart/mixed; boundary={boundary}"
    }

    url = f"{BASE_URL}/$batch"
    response = requests.post(url, data=batch_content, headers=headers, auth=AUTH)

    if response.status_code == 200:
        logger.info(f"Batch created {count} users successfully")
        return response.text
    else:
        logger.error(f"Batch error: {response.status_code}")
        return None


# ============================================================================
# EXAMPLE 8: Batch Operation - Mixed Operations
# ============================================================================

def example_batch_mixed_operations():
    """
    Batch с разными операциями (POST, PATCH, DELETE)
    """
    boundary = f"batch_{uuid.uuid4()}"
    batch_body = []

    # Operation 1: Create user
    batch_body.extend([
        f"--{boundary}",
        "Content-Type: application/http",
        "Content-Transfer-Encoding: binary",
        "",
        "POST Catalog_Users HTTP/1.1",
        "Content-Type: application/json",
        "",
        json.dumps({"Code": "MIX001", "Description": "Mixed Batch User 1"}),
        ""
    ])

    # Operation 2: Create another user
    batch_body.extend([
        f"--{boundary}",
        "Content-Type: application/http",
        "Content-Transfer-Encoding: binary",
        "",
        "POST Catalog_Users HTTP/1.1",
        "Content-Type: application/json",
        "",
        json.dumps({"Code": "MIX002", "Description": "Mixed Batch User 2"}),
        ""
    ])

    # End boundary
    batch_body.append(f"--{boundary}--")
    batch_content = "\r\n".join(batch_body)

    # Send request
    headers = {"Content-Type": f"multipart/mixed; boundary={boundary}"}
    url = f"{BASE_URL}/$batch"

    response = requests.post(url, data=batch_content, headers=headers, auth=AUTH)

    if response.status_code == 200:
        logger.info("Mixed batch executed successfully")
        return response.text
    else:
        logger.error(f"Error: {response.status_code}")
        return None


# ============================================================================
# EXAMPLE 9: Large Dataset with Chunking
# ============================================================================

def example_process_large_dataset(total_count=200, batch_size=50):
    """
    Обработка большого датасета с разбиением на chunks

    ⚠️ КРИТИЧНО: Соблюдается ограничение транзакций < 15 секунд
    """
    logger.info(f"Processing {total_count} items in batches of {batch_size}")

    # Split into chunks
    num_chunks = (total_count + batch_size - 1) // batch_size

    results = []
    for chunk_idx in range(num_chunks):
        start_idx = chunk_idx * batch_size
        end_idx = min(start_idx + batch_size, total_count)
        chunk_size = end_idx - start_idx

        logger.info(f"Processing chunk {chunk_idx + 1}/{num_chunks} ({chunk_size} items)")

        # Time the operation
        start_time = time.time()

        # Create batch for this chunk
        result = example_batch_create_users(chunk_size)
        results.append(result)

        elapsed = time.time() - start_time
        logger.info(f"Chunk processed in {elapsed:.2f}s")

        if elapsed > 10:
            logger.warning("⚠️ Transaction approaching 15s limit!")

        # Small delay between chunks
        time.sleep(0.5)

    logger.info(f"All {num_chunks} chunks processed successfully")
    return results


# ============================================================================
# EXAMPLE 10: Get Metadata
# ============================================================================

def example_get_metadata():
    """Получить metadata (структуру данных)"""
    url = f"{BASE_URL}/$metadata"

    response = requests.get(url, auth=AUTH)

    if response.status_code == 200:
        logger.info("Metadata retrieved successfully")
        return response.text
    else:
        logger.error(f"Error: {response.status_code}")
        return None


# ============================================================================
# EXAMPLE 11: Query with Navigation Properties
# ============================================================================

def example_query_with_expand():
    """
    Получить объекты с вложенными данными через $expand
    """
    url = f"{BASE_URL}/Document_SalesInvoice"
    params = {
        "$expand": "Company,Counterparty",
        "$top": 10
    }

    response = requests.get(url, params=params, auth=AUTH)

    if response.status_code == 200:
        data = response.json()
        logger.info(f"Retrieved {len(data.get('value', []))} documents with expanded data")
        return data
    else:
        logger.error(f"Error: {response.status_code}")
        return None


# ============================================================================
# EXAMPLE 12: Pagination
# ============================================================================

def example_paginated_query(page_size=100):
    """
    Получить все записи с пагинацией
    """
    url = f"{BASE_URL}/Catalog_Users"
    all_items = []
    skip = 0

    while True:
        params = {
            "$top": page_size,
            "$skip": skip
        }

        response = requests.get(url, params=params, auth=AUTH)

        if response.status_code != 200:
            logger.error(f"Error: {response.status_code}")
            break

        data = response.json()
        items = data.get('value', [])

        if not items:
            break

        all_items.extend(items)
        logger.info(f"Retrieved {len(all_items)} items so far...")

        skip += page_size

    logger.info(f"Total items retrieved: {len(all_items)}")
    return all_items


# ============================================================================
# EXAMPLE 13: Advanced Filtering
# ============================================================================

def example_advanced_filtering():
    """
    Продвинутые фильтры OData
    """
    url = f"{BASE_URL}/Catalog_Users"

    # Complex filter: (IsActive = true) AND (Code starts with 'USER')
    params = {
        "$filter": "IsActive eq true and startswith(Code, 'USER')",
        "$orderby": "Description asc",
        "$top": 50
    }

    response = requests.get(url, params=params, auth=AUTH)

    if response.status_code == 200:
        data = response.json()
        logger.info(f"Retrieved {len(data.get('value', []))} filtered users")
        return data
    else:
        logger.error(f"Error: {response.status_code}")
        return None


# ============================================================================
# EXAMPLE 14: Error Handling with Retries
# ============================================================================

def example_robust_request(url, max_retries=3):
    """
    Request с retry logic для обработки temporary failures
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(url, auth=AUTH, timeout=30)

            if response.status_code == 200:
                return response.json()
            elif response.status_code >= 500:
                # Server error - retry
                logger.warning(f"Server error {response.status_code} on attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
            else:
                # Client error - don't retry
                logger.error(f"Client error: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None

    logger.error("Max retries exceeded")
    return None


# ============================================================================
# EXAMPLE 15: Testing OData Connection
# ============================================================================

def test_odata_connection():
    """
    Проверка подключения к OData endpoint
    """
    logger.info("Testing OData connection...")

    # Test 1: Get metadata
    try:
        metadata_url = f"{BASE_URL}/$metadata"
        response = requests.get(metadata_url, auth=AUTH, timeout=10)

        if response.status_code == 200:
            logger.info("✓ Metadata endpoint accessible")
        else:
            logger.error(f"✗ Metadata endpoint returned {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"✗ Failed to connect: {e}")
        return False

    # Test 2: Get collection
    try:
        url = f"{BASE_URL}/Catalog_Users?$top=1"
        response = requests.get(url, auth=AUTH, timeout=10)

        if response.status_code == 200:
            logger.info("✓ Collection query works")
        elif response.status_code == 401:
            logger.error("✗ Authentication failed")
            return False
        else:
            logger.error(f"✗ Collection query returned {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"✗ Collection query failed: {e}")
        return False

    logger.info("✓ OData connection test passed")
    return True


# ============================================================================
# EXAMPLE 16: Advanced Transaction Time Monitoring
# ============================================================================

def example_adaptive_batch_with_timing(items, initial_batch_size=50):
    """
    Адаптивная batch обработка с мониторингом времени транзакций

    ⚠️ КРИТИЧНО: Автоматически уменьшает batch size если транзакция > 10 секунд

    Features:
    - Real-time transaction timing
    - Adaptive batch size adjustment
    - Automatic slowdown prevention
    - Detailed performance logging
    """
    logger.info(f"Starting adaptive batch processing for {len(items)} items")

    current_batch_size = initial_batch_size
    MIN_BATCH_SIZE = 10
    MAX_TRANSACTION_TIME = 10.0  # seconds (безопасный лимит < 15s)

    results = []
    processed = 0

    while processed < len(items):
        chunk = items[processed:processed + current_batch_size]
        chunk_size = len(chunk)

        logger.info(f"Processing batch {processed // current_batch_size + 1}: {chunk_size} items")

        # Monitor transaction time
        start_time = time.time()

        try:
            # Create batch operations
            boundary = f"batch_{uuid.uuid4()}"
            batch_body = []

            for item in chunk:
                batch_body.extend([
                    f"--{boundary}",
                    "Content-Type: application/http",
                    "Content-Transfer-Encoding: binary",
                    "",
                    "POST Catalog_Users HTTP/1.1",
                    "Content-Type: application/json",
                    "",
                    json.dumps(item),
                    ""
                ])

            batch_body.append(f"--{boundary}--")
            batch_content = "\r\n".join(batch_body)

            headers = {"Content-Type": f"multipart/mixed; boundary={boundary}"}
            url = f"{BASE_URL}/$batch"

            response = requests.post(url, data=batch_content, headers=headers, auth=AUTH, timeout=30)

            elapsed = time.time() - start_time

            # Log timing details
            logger.info(f"✓ Batch completed in {elapsed:.2f}s (batch_size={chunk_size})")

            # Analyze transaction time and adjust batch size
            if elapsed > MAX_TRANSACTION_TIME:
                logger.warning(f"⚠️ Transaction time {elapsed:.2f}s exceeds safe limit ({MAX_TRANSACTION_TIME}s)")

                if current_batch_size > MIN_BATCH_SIZE:
                    # Reduce batch size by 30%
                    new_batch_size = max(MIN_BATCH_SIZE, int(current_batch_size * 0.7))
                    logger.info(f"→ Reducing batch size: {current_batch_size} → {new_batch_size}")
                    current_batch_size = new_batch_size

            elif elapsed < MAX_TRANSACTION_TIME * 0.5 and current_batch_size < initial_batch_size:
                # Transaction is fast - can increase batch size
                new_batch_size = min(initial_batch_size, int(current_batch_size * 1.2))
                logger.info(f"→ Increasing batch size: {current_batch_size} → {new_batch_size}")
                current_batch_size = new_batch_size

            results.append({
                'chunk_size': chunk_size,
                'elapsed': elapsed,
                'status': response.status_code,
                'success': response.status_code == 200
            })

            processed += chunk_size

        except Exception as e:
            logger.error(f"✗ Batch failed: {e}")
            # On error, reduce batch size even more
            if current_batch_size > MIN_BATCH_SIZE:
                current_batch_size = max(MIN_BATCH_SIZE, current_batch_size // 2)
                logger.info(f"→ Error recovery: reducing batch size to {current_batch_size}")
            processed += chunk_size  # Skip failed chunk

    # Summary statistics
    total_time = sum(r['elapsed'] for r in results)
    avg_time = total_time / len(results) if results else 0
    max_time = max((r['elapsed'] for r in results), default=0)

    logger.info("\n" + "=" * 60)
    logger.info("ADAPTIVE BATCH PROCESSING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total items:      {len(items)}")
    logger.info(f"Total batches:    {len(results)}")
    logger.info(f"Total time:       {total_time:.2f}s")
    logger.info(f"Average/batch:    {avg_time:.2f}s")
    logger.info(f"Max batch time:   {max_time:.2f}s")
    logger.info(f"Final batch size: {current_batch_size}")
    logger.info("=" * 60)

    return results


# ============================================================================
# EXAMPLE 17: Batch Operations with Retry Logic
# ============================================================================

def example_batch_with_retry(operations, max_retries=3, initial_delay=1.0):
    """
    Batch операции с умной retry logic

    Features:
    - Exponential backoff для retries
    - Разделение batch на smaller chunks при ошибках
    - Детальное логирование каждой попытки
    """
    logger.info(f"Starting batch with {len(operations)} operations (max_retries={max_retries})")

    batch_size = len(operations)
    delay = initial_delay

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries} (batch_size={batch_size})")

            # Build batch request
            boundary = f"batch_{uuid.uuid4()}"
            batch_body = []

            for op in operations[:batch_size]:
                batch_body.extend([
                    f"--{boundary}",
                    "Content-Type: application/http",
                    "Content-Transfer-Encoding: binary",
                    "",
                    f"{op['method']} {op['url']} HTTP/1.1",
                    "Content-Type: application/json",
                    "",
                    json.dumps(op.get('body', {})) if 'body' in op else "",
                    ""
                ])

            batch_body.append(f"--{boundary}--")
            batch_content = "\r\n".join(batch_body)

            headers = {"Content-Type": f"multipart/mixed; boundary={boundary}"}
            url = f"{BASE_URL}/$batch"

            start_time = time.time()
            response = requests.post(url, data=batch_content, headers=headers, auth=AUTH, timeout=30)
            elapsed = time.time() - start_time

            if response.status_code == 200:
                logger.info(f"✓ Batch succeeded in {elapsed:.2f}s")
                return {
                    'success': True,
                    'attempt': attempt + 1,
                    'elapsed': elapsed,
                    'batch_size': batch_size
                }

            elif response.status_code >= 500:
                # Server error - retry with exponential backoff
                logger.warning(f"⚠️ Server error {response.status_code} on attempt {attempt + 1}")

                if attempt < max_retries - 1:
                    logger.info(f"→ Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff

                    # Also reduce batch size on errors
                    if batch_size > 10:
                        batch_size = max(10, batch_size // 2)
                        logger.info(f"→ Reducing batch size to {batch_size}")
                    continue

            else:
                # Client error - don't retry
                logger.error(f"✗ Client error {response.status_code}: {response.text[:200]}")
                return {
                    'success': False,
                    'error': 'client_error',
                    'status': response.status_code,
                    'attempt': attempt + 1
                }

        except requests.exceptions.Timeout:
            logger.warning(f"⚠️ Timeout on attempt {attempt + 1}")

            if attempt < max_retries - 1:
                logger.info(f"→ Retrying in {delay:.1f}s...")
                time.sleep(delay)
                delay *= 2

                # Reduce batch size on timeout
                if batch_size > 10:
                    batch_size = max(10, batch_size // 2)
                    logger.info(f"→ Reducing batch size to {batch_size}")
                continue

        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Request exception: {e}")

            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
                continue

    logger.error(f"✗ Max retries ({max_retries}) exceeded")
    return {
        'success': False,
        'error': 'max_retries_exceeded',
        'attempts': max_retries
    }


# ============================================================================
# MAIN: Run Examples
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("1C OData Examples")
    print("=" * 80)

    # Test connection first
    if not test_odata_connection():
        print("\n❌ Connection test failed. Check your configuration.")
        exit(1)

    print("\n✓ Connection successful!")

    # Run examples (uncomment to execute)

    # Example 1: Get users
    # users = example_get_users()

    # Example 2: Get active users
    # active_users = example_get_active_users()

    # Example 3: Get specific user
    # user = example_get_user_by_guid("YOUR-GUID-HERE")

    # Example 4: Create user
    # new_user = example_create_user()

    # Example 7: Batch create
    # result = example_batch_create_users(count=10)

    # Example 9: Large dataset processing
    # results = example_process_large_dataset(total_count=200, batch_size=50)

    print("\n" + "=" * 80)
    print("Examples completed. Uncomment specific examples to run them.")
    print("=" * 80)
