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


def check_service(name: str, service_type: str, url: str) -> dict:
    """
    Check health of a single service.

    Args:
        name: Service display name
        service_type: Service type (go-service, database, cache)
        url: Health check endpoint URL

    Returns:
        dict with service health info in frontend-compatible format
    """
    import time
    start_time = time.time()

    try:
        resp = requests.get(url, timeout=HEALTH_TIMEOUT)
        response_time_ms = (time.time() - start_time) * 1000
        status = 'online' if resp.status_code == 200 else 'degraded'
        return {
            'name': name,
            'type': service_type,
            'url': url,
            'status': status,
            'response_time_ms': round(response_time_ms, 2),
            'last_check': timezone.now().isoformat(),
        }
    except requests.exceptions.Timeout:
        return {
            'name': name,
            'type': service_type,
            'url': url,
            'status': 'offline',
            'response_time_ms': None,
            'last_check': timezone.now().isoformat(),
            'details': {'error': 'timeout'},
        }
    except requests.exceptions.ConnectionError:
        return {
            'name': name,
            'type': service_type,
            'url': url,
            'status': 'offline',
            'response_time_ms': None,
            'last_check': timezone.now().isoformat(),
            'details': {'error': 'connection_refused'},
        }
    except Exception as e:
        logger.warning(f"Health check failed for {name}: {e}")
        return {
            'name': name,
            'type': service_type,
            'url': url,
            'status': 'offline',
            'response_time_ms': None,
            'last_check': timezone.now().isoformat(),
            'details': {'error': str(e)},
        }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_health(request):
    """
    GET /api/v2/system/health/

    Returns comprehensive system health status with parallel service checks.

    Response format matches frontend SystemHealthResponse interface:
        {
            "timestamp": "2024-01-01T00:00:00Z",
            "overall_status": "healthy|degraded|critical",
            "services": [
                {
                    "name": "API Gateway",
                    "type": "go-service",
                    "url": "http://localhost:8180/health",
                    "status": "online|offline|degraded",
                    "response_time_ms": 12.5,
                    "last_check": "2024-01-01T00:00:00Z"
                }
            ],
            "statistics": {
                "total": 4,
                "online": 3,
                "offline": 1,
                "degraded": 0
            }
        }
    """
    import time

    # Services to check: (name, type, url)
    # Ports outside Windows reserved ranges (7913-8012, 8013-8112):
    # API Gateway: 8180, Orchestrator: 8200, RAS Adapter: 8188
    #
    # Monitoring ports depend on USE_DOCKER mode:
    # - Native (systemd): Grafana=3000, Jaeger requires manual install
    # - Docker: Grafana=5000, Jaeger=16686
    import os
    use_docker = os.environ.get('USE_DOCKER', 'true').lower() == 'true'
    grafana_port = '5000' if use_docker else '3000'

    services = [
        ('API Gateway', 'go-service', 'http://localhost:8180/health'),
        ('RAS Adapter', 'go-service', 'http://localhost:8188/health'),
        ('Worker', 'go-service', 'http://localhost:9091/health'),
        ('Orchestrator', 'django', 'http://localhost:8200/health'),
        ('Prometheus', 'monitoring', 'http://localhost:9090/-/healthy'),
        ('Grafana', 'monitoring', f'http://localhost:{grafana_port}/api/health'),
        ('Jaeger', 'tracing', 'http://localhost:16686/'),
    ]

    results = []

    # Check external services in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(check_service, name, stype, url): name
            for name, stype, url in services
        }
        try:
            for future in as_completed(futures, timeout=3.0):
                try:
                    results.append(future.result())
                except Exception as e:
                    service_name = futures[future]
                    logger.warning(f"Health check failed for {service_name}: {e}")
                    results.append({
                        'name': service_name,
                        'type': 'go-service',
                        'status': 'offline',
                        'response_time_ms': None,
                        'last_check': timezone.now().isoformat(),
                        'details': {'error': str(e)},
                    })
        except TimeoutError:
            for future, service_name in futures.items():
                if not future.done():
                    future.cancel()
                    results.append({
                        'name': service_name,
                        'type': 'go-service',
                        'status': 'offline',
                        'response_time_ms': None,
                        'last_check': timezone.now().isoformat(),
                        'details': {'error': 'timeout'},
                    })

    # Check PostgreSQL
    try:
        start = time.time()
        connection.ensure_connection()
        response_time = (time.time() - start) * 1000
        results.append({
            'name': 'PostgreSQL',
            'type': 'database',
            'status': 'online',
            'response_time_ms': round(response_time, 2),
            'last_check': timezone.now().isoformat(),
        })
    except Exception as e:
        logger.warning(f"PostgreSQL health check failed: {e}")
        results.append({
            'name': 'PostgreSQL',
            'type': 'database',
            'status': 'offline',
            'response_time_ms': None,
            'last_check': timezone.now().isoformat(),
            'details': {'error': str(e)},
        })

    # Check Redis (direct connection)
    try:
        import redis
        start = time.time()
        redis_client = redis.Redis(host='localhost', port=6379, socket_timeout=2)
        redis_client.ping()
        response_time = (time.time() - start) * 1000
        results.append({
            'name': 'Redis',
            'type': 'cache',
            'status': 'online',
            'response_time_ms': round(response_time, 2),
            'last_check': timezone.now().isoformat(),
        })
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        results.append({
            'name': 'Redis',
            'type': 'cache',
            'status': 'offline',
            'response_time_ms': None,
            'last_check': timezone.now().isoformat(),
            'details': {'error': str(e)},
        })

    # Calculate statistics
    statuses = [r['status'] for r in results]
    statistics = {
        'total': len(results),
        'online': sum(1 for s in statuses if s == 'online'),
        'offline': sum(1 for s in statuses if s == 'offline'),
        'degraded': sum(1 for s in statuses if s == 'degraded'),
    }

    # Determine overall status (frontend uses: healthy, degraded, critical)
    if statistics['offline'] > 0:
        overall = 'critical'
    elif statistics['degraded'] > 0:
        overall = 'degraded'
    else:
        overall = 'healthy'

    return Response({
        'timestamp': timezone.now().isoformat(),
        'overall_status': overall,
        'services': results,
        'statistics': statistics,
    })
