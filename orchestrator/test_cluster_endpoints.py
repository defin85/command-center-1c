#!/usr/bin/env python
"""
Test script for Cluster CRUD endpoints (API v2).

Usage:
    python test_cluster_endpoints.py
"""

# ruff: noqa: E402

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from rest_framework.test import APIRequestFactory
from django.contrib.auth.models import User
from apps.api_v2.views import clusters
from apps.databases.models import Cluster


def test_create_cluster():
    """Test create_cluster endpoint."""
    print("\n=== Testing create_cluster ===")

    factory = APIRequestFactory()
    user = User.objects.first() or User.objects.create_user('testuser', password='test')

    # Test missing required field
    request = factory.post('/api/v2/clusters/create-cluster/', {}, format='json')
    request.user = user
    response = clusters.create_cluster(request)

    print(f"Missing name: {response.status_code} - {response.data}")
    assert response.status_code == 400

    # Test valid creation
    data = {
        'name': 'test-cluster',
        'ras_server': 'localhost:1545',
        'cluster_service_url': 'http://localhost:8087',
        'description': 'Test cluster'
    }
    request = factory.post('/api/v2/clusters/create-cluster/', data, format='json')
    request.user = user
    response = clusters.create_cluster(request)

    print(f"Valid creation: {response.status_code} - {response.data.get('message')}")
    assert response.status_code == 201

    cluster_id = response.data['cluster']['id']

    # Test duplicate
    request = factory.post('/api/v2/clusters/create-cluster/', data, format='json')
    request.user = user
    response = clusters.create_cluster(request)

    print(f"Duplicate: {response.status_code} - {response.data.get('error', {}).get('code')}")
    assert response.status_code == 409

    return cluster_id


def test_update_cluster(cluster_id):
    """Test update_cluster endpoint."""
    print("\n=== Testing update_cluster ===")

    factory = APIRequestFactory()
    user = User.objects.first()

    # Test update
    data = {
        'description': 'Updated description',
        'status': 'maintenance'
    }
    request = factory.put(f'/api/v2/clusters/update-cluster/?cluster_id={cluster_id}', data, format='json')
    request.user = user
    response = clusters.update_cluster(request)

    print(f"Update: {response.status_code} - {response.data.get('message')}")
    assert response.status_code == 200
    assert response.data['cluster']['description'] == 'Updated description'

    # Test not found
    request = factory.put('/api/v2/clusters/update-cluster/?cluster_id=00000000-0000-0000-0000-000000000000', {}, format='json')
    request.user = user
    response = clusters.update_cluster(request)

    print(f"Not found: {response.status_code} - {response.data.get('error', {}).get('code')}")
    assert response.status_code == 404


def test_get_cluster_databases(cluster_id):
    """Test get_cluster_databases endpoint."""
    print("\n=== Testing get_cluster_databases ===")

    factory = APIRequestFactory()
    user = User.objects.first()

    request = factory.get(f'/api/v2/clusters/get-cluster-databases/?cluster_id={cluster_id}')
    request.user = user
    response = clusters.get_cluster_databases(request)

    print(f"Get databases: {response.status_code} - Count: {response.data.get('count')}")
    assert response.status_code == 200


def test_delete_cluster(cluster_id):
    """Test delete_cluster endpoint."""
    print("\n=== Testing delete_cluster ===")

    factory = APIRequestFactory()
    user = User.objects.first()

    # Test delete without force (should succeed if no databases)
    request = factory.delete(f'/api/v2/clusters/delete-cluster/?cluster_id={cluster_id}')
    request.user = user
    response = clusters.delete_cluster(request)

    print(f"Delete: {response.status_code} - {response.data.get('message')}")
    assert response.status_code in (200, 409)

    if response.status_code == 409:
        # Has databases, try with force
        data = {'force': True}
        request = factory.post(f'/api/v2/clusters/delete-cluster/?cluster_id={cluster_id}', data, format='json')
        request.user = user
        response = clusters.delete_cluster(request)

        print(f"Delete with force: {response.status_code} - {response.data.get('message')}")
        assert response.status_code == 200


def cleanup():
    """Cleanup test data."""
    print("\n=== Cleanup ===")
    Cluster.objects.filter(name='test-cluster').delete()
    print("Test cluster deleted")


if __name__ == '__main__':
    try:
        # Create and test
        cluster_id = test_create_cluster()
        test_update_cluster(cluster_id)
        test_get_cluster_databases(cluster_id)
        test_delete_cluster(cluster_id)

        print("\n[OK] All tests passed!")

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cleanup()
