"""
System health check endpoints for API v2.

Provides comprehensive system health monitoring with parallel service checks.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from django.db import connection
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)

# Health check timeout in seconds
HEALTH_TIMEOUT = 1.5


def check_service(name: str, url: str) -> dict:
    """
    Check health of a single service.

    Args:
        name: Service name for response
        url: Health check endpoint URL

    Returns:
        dict with 'name' and 'status' keys
    """
    try:
        resp = requests.get(url, timeout=HEALTH_TIMEOUT)
        status = 'healthy' if resp.status_code == 200 else 'degraded'
        return {'name': name, 'status': status}
    except requests.exceptions.Timeout:
        return {'name': name, 'status': 'timeout'}
    except requests.exceptions.ConnectionError:
        return {'name': name, 'status': 'unhealthy'}
    except Exception as e:
        logger.warning(f"Health check failed for {name}: {e}")
        return {'name': name, 'status': 'unhealthy'}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_health(request):
    """
    GET /api/v2/system/health/

    Returns comprehensive system health status with parallel service checks.

    Response:
        {
            "status": "healthy|degraded|unhealthy",
            "services": [
                {"name": "api-gateway", "status": "healthy"},
                {"name": "ras-adapter", "status": "healthy"},
                {"name": "postgresql", "status": "healthy"},
                {"name": "redis", "status": "healthy"}
            ],
            "timestamp": "2024-01-01T00:00:00Z"
        }
    """
    # External services to check
    services = [
        ('api-gateway', 'http://localhost:8080/health'),
        ('ras-adapter', 'http://localhost:8088/health'),
    ]

    results = []

    # Check external services in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(check_service, name, url): name
            for name, url in services
        }
        try:
            for future in as_completed(futures, timeout=2.0):
                try:
                    results.append(future.result())
                except Exception as e:
                    service_name = futures[future]
                    logger.warning(f"Health check failed for {service_name}: {e}")
                    results.append({'name': service_name, 'status': 'unhealthy'})
        except TimeoutError:
            # Handle case when as_completed times out
            for future, service_name in futures.items():
                if not future.done():
                    future.cancel()
                    results.append({'name': service_name, 'status': 'timeout'})

    # Check PostgreSQL
    try:
        connection.ensure_connection()
        results.append({'name': 'postgresql', 'status': 'healthy'})
    except Exception as e:
        logger.warning(f"PostgreSQL health check failed: {e}")
        results.append({'name': 'postgresql', 'status': 'unhealthy'})

    # Check Redis
    try:
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        redis_conn.ping()
        results.append({'name': 'redis', 'status': 'healthy'})
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        results.append({'name': 'redis', 'status': 'unhealthy'})

    # Determine overall status
    statuses = [r['status'] for r in results]
    if all(s == 'healthy' for s in statuses):
        overall = 'healthy'
    elif any(s == 'unhealthy' for s in statuses):
        overall = 'unhealthy'
    else:
        overall = 'degraded'

    return Response({
        'status': overall,
        'services': results,
        'timestamp': timezone.now().isoformat(),
    })
