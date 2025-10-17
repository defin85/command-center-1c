#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance Testing для Mock 1C OData Server
"""

import sys
import io
import requests
import time
import base64
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

MOCK_SERVERS = [
    {'name': 'Moscow', 'base_url': 'http://localhost:8081', 'username': 'Администратор', 'password': 'mock_password'},
    {'name': 'SPB', 'base_url': 'http://localhost:8082', 'username': 'Администратор', 'password': 'mock_password'},
    {'name': 'EKB', 'base_url': 'http://localhost:8083', 'username': 'Администратор', 'password': 'mock_password'},
]


def get_auth_header(username: str, password: str) -> Dict[str, str]:
    """Generate HTTP Basic Auth header"""
    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode('utf-8')).decode('ascii')
    return {'Authorization': f'Basic {encoded}'}


def create_entity(server: Dict, index: int) -> tuple:
    """Create a single entity"""
    base_url = f"{server['base_url']}/odata/standard.odata"
    headers = get_auth_header(server['username'], server['password'])
    entity_type = 'Catalog_Пользователи'

    entity = {
        'Description': f'Test User {index}',
        'Code': f'{10000 + index}',
        'ИмяПользователя': f'user_{index}',
        'Email': f'user{index}@test.com'
    }

    try:
        start = time.time()
        response = requests.post(
            f"{base_url}/{entity_type}",
            json=entity,
            headers=headers,
            timeout=10
        )
        duration = time.time() - start

        if response.status_code == 201:
            entity_id = response.json()['d']['Ref_Key']
            return True, entity_id, duration
        else:
            return False, f"Status {response.status_code}", duration
    except Exception as e:
        return False, str(e), 0


def read_entities(server: Dict) -> tuple:
    """Read list of entities"""
    base_url = f"{server['base_url']}/odata/standard.odata"
    headers = get_auth_header(server['username'], server['password'])
    entity_type = 'Catalog_Пользователи'

    try:
        start = time.time()
        response = requests.get(
            f"{base_url}/{entity_type}",
            headers=headers,
            timeout=10
        )
        duration = time.time() - start

        if response.status_code == 200:
            count = len(response.json()['d']['results'])
            return True, count, duration
        else:
            return False, response.status_code, duration
    except Exception as e:
        return False, str(e), 0


def cleanup_entities(server: Dict, entity_ids: List[str]):
    """Delete entities"""
    base_url = f"{server['base_url']}/odata/standard.odata"
    headers = get_auth_header(server['username'], server['password'])
    entity_type = 'Catalog_Пользователи'

    deleted = 0
    for entity_id in entity_ids:
        try:
            response = requests.delete(
                f"{base_url}/{entity_type}(guid'{entity_id}')",
                headers=headers,
                timeout=5
            )
            if response.status_code == 204:
                deleted += 1
        except:
            pass

    return deleted


def test_sequential_performance(server: Dict, num_requests: int = 50):
    """Test sequential request performance"""
    print(f"\n{server['name']}: Sequential Performance Test ({num_requests} requests)")
    print("-" * 60)

    times = []
    success_count = 0

    for i in range(num_requests):
        success, _, duration = read_entities(server)
        if success:
            times.append(duration)
            success_count += 1

    if times:
        total_time = sum(times)
        avg_time = total_time / len(times)
        min_time = min(times)
        max_time = max(times)
        req_per_sec = len(times) / total_time

        print(f"  Total time: {total_time:.2f}s")
        print(f"  Success rate: {success_count}/{num_requests} ({success_count/num_requests*100:.1f}%)")
        print(f"  Avg response time: {avg_time*1000:.1f}ms")
        print(f"  Min response time: {min_time*1000:.1f}ms")
        print(f"  Max response time: {max_time*1000:.1f}ms")
        print(f"  Throughput: {req_per_sec:.1f} req/s")

        return {
            'total_time': total_time,
            'avg_time': avg_time,
            'throughput': req_per_sec,
            'success_rate': success_count/num_requests*100
        }
    else:
        print(f"  ✗ All requests failed")
        return None


def test_concurrent_performance(server: Dict, num_requests: int = 100, workers: int = 10):
    """Test concurrent request performance"""
    print(f"\n{server['name']}: Concurrent Performance Test ({num_requests} requests, {workers} workers)")
    print("-" * 60)

    entity_ids = []
    times = []

    start_time = time.time()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(create_entity, server, i) for i in range(num_requests)]

        for future in as_completed(futures):
            success, result, duration = future.result()
            if success:
                entity_ids.append(result)
                times.append(duration)

    total_time = time.time() - start_time

    success_count = len(entity_ids)
    if times:
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        req_per_sec = success_count / total_time

        print(f"  Total time: {total_time:.2f}s")
        print(f"  Success rate: {success_count}/{num_requests} ({success_count/num_requests*100:.1f}%)")
        print(f"  Avg response time: {avg_time*1000:.1f}ms")
        print(f"  Min response time: {min_time*1000:.1f}ms")
        print(f"  Max response time: {max_time*1000:.1f}ms")
        print(f"  Throughput: {req_per_sec:.1f} req/s")

        # Cleanup
        print(f"  Cleaning up {len(entity_ids)} entities...")
        deleted = cleanup_entities(server, entity_ids)
        print(f"  Deleted: {deleted}/{len(entity_ids)}")

        return {
            'total_time': total_time,
            'avg_time': avg_time,
            'throughput': req_per_sec,
            'success_rate': success_count/num_requests*100
        }
    else:
        print(f"  ✗ All requests failed")
        return None


def test_bulk_operations(server: Dict, bulk_size: int = 200):
    """Test bulk create/delete operations"""
    print(f"\n{server['name']}: Bulk Operations Test ({bulk_size} entities)")
    print("-" * 60)

    # Bulk create
    print(f"  Creating {bulk_size} entities...")
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(create_entity, server, i) for i in range(bulk_size)]
        entity_ids = []

        for future in as_completed(futures):
            success, result, _ = future.result()
            if success:
                entity_ids.append(result)

    create_time = time.time() - start_time
    create_rate = len(entity_ids) / create_time

    print(f"    Created: {len(entity_ids)}/{bulk_size}")
    print(f"    Time: {create_time:.2f}s")
    print(f"    Rate: {create_rate:.1f} creates/s")

    # Read all
    print(f"  Reading all entities...")
    success, count, read_time = read_entities(server)
    if success:
        print(f"    Found: {count} entities")
        print(f"    Time: {read_time*1000:.1f}ms")

    # Bulk delete
    print(f"  Deleting {len(entity_ids)} entities...")
    start_time = time.time()
    deleted = cleanup_entities(server, entity_ids)
    delete_time = time.time() - start_time
    delete_rate = deleted / delete_time

    print(f"    Deleted: {deleted}/{len(entity_ids)}")
    print(f"    Time: {delete_time:.2f}s")
    print(f"    Rate: {delete_rate:.1f} deletes/s")

    return {
        'create_rate': create_rate,
        'delete_rate': delete_rate,
        'success_rate': len(entity_ids)/bulk_size*100
    }


def test_stress(server: Dict, duration_sec: int = 10):
    """Stress test - maximum load for N seconds"""
    print(f"\n{server['name']}: Stress Test ({duration_sec}s maximum load)")
    print("-" * 60)

    entity_ids = []
    request_count = 0
    error_count = 0
    times = []

    start_time = time.time()
    end_time = start_time + duration_sec

    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = []

        while time.time() < end_time:
            future = executor.submit(create_entity, server, request_count)
            futures.append(future)
            request_count += 1

            # Process completed futures
            done_futures = [f for f in futures if f.done()]
            for f in done_futures:
                futures.remove(f)
                try:
                    success, result, duration = f.result()
                    if success:
                        entity_ids.append(result)
                        times.append(duration)
                    else:
                        error_count += 1
                except:
                    error_count += 1

        # Wait for remaining
        for future in futures:
            try:
                success, result, duration = future.result()
                if success:
                    entity_ids.append(result)
                    times.append(duration)
                else:
                    error_count += 1
            except:
                error_count += 1

    total_time = time.time() - start_time
    success_count = len(entity_ids)

    if times:
        avg_time = sum(times) / len(times)
        max_time = max(times)
        req_per_sec = success_count / total_time

        print(f"  Duration: {total_time:.2f}s")
        print(f"  Total requests: {request_count}")
        print(f"  Successful: {success_count}")
        print(f"  Failed: {error_count}")
        print(f"  Success rate: {success_count/request_count*100:.1f}%")
        print(f"  Avg response time: {avg_time*1000:.1f}ms")
        print(f"  Max response time: {max_time*1000:.1f}ms")
        print(f"  Throughput: {req_per_sec:.1f} req/s")

        # Cleanup
        print(f"  Cleaning up...")
        deleted = cleanup_entities(server, entity_ids)
        print(f"  Deleted: {deleted}/{len(entity_ids)}")

        return {
            'throughput': req_per_sec,
            'success_rate': success_count/request_count*100,
            'max_response_time': max_time
        }
    else:
        print(f"  ✗ All requests failed")
        return None


def main():
    """Main test runner"""
    print("\n" + "="*70)
    print("  Mock 1C OData Server - Performance Testing")
    print("="*70)

    all_results = {}

    for server in MOCK_SERVERS:
        print(f"\n{'='*70}")
        print(f"  Testing Server: {server['name']}")
        print(f"  URL: {server['base_url']}")
        print(f"{'='*70}")

        results = {}

        # Test 1: Sequential performance
        results['sequential'] = test_sequential_performance(server, num_requests=50)

        # Test 2: Concurrent performance
        results['concurrent'] = test_concurrent_performance(server, num_requests=100, workers=10)

        # Test 3: Bulk operations
        results['bulk'] = test_bulk_operations(server, bulk_size=200)

        # Test 4: Stress test
        results['stress'] = test_stress(server, duration_sec=10)

        all_results[server['name']] = results

    # Summary
    print("\n" + "="*70)
    print("  PERFORMANCE SUMMARY")
    print("="*70)

    for server_name, results in all_results.items():
        print(f"\n{server_name}:")
        if results.get('sequential'):
            print(f"  Sequential: {results['sequential']['throughput']:.1f} req/s")
        if results.get('concurrent'):
            print(f"  Concurrent: {results['concurrent']['throughput']:.1f} req/s")
        if results.get('bulk'):
            print(f"  Bulk create: {results['bulk']['create_rate']:.1f} creates/s")
            print(f"  Bulk delete: {results['bulk']['delete_rate']:.1f} deletes/s")
        if results.get('stress'):
            print(f"  Stress test: {results['stress']['throughput']:.1f} req/s (max load)")
            print(f"  Max response time: {results['stress']['max_response_time']*1000:.1f}ms")

    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
