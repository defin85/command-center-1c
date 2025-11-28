"""
Service Mesh monitoring endpoints for API v2.

Provides metrics and monitoring for the service mesh.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)

# Service endpoints for metrics collection
# Ports outside Windows reserved ranges (7913-8012, 8013-8112):
# API Gateway: 8180, RAS Adapter: 8188, Batch Service: 8187
MONITORED_SERVICES = [
    {
        'name': 'api-gateway',
        'type': 'backend',
        'health_url': 'http://localhost:8180/health',
        'metrics_url': 'http://localhost:8180/metrics',
    },
    {
        'name': 'ras-adapter',
        'type': 'backend',
        'health_url': 'http://localhost:8188/health',
        'metrics_url': 'http://localhost:8188/metrics',
    },
    {
        'name': 'worker',
        'type': 'backend',
        'health_url': 'http://localhost:9091/health',
        'metrics_url': 'http://localhost:9091/metrics',
    },
    {
        'name': 'batch-service',
        'type': 'backend',
        'health_url': 'http://localhost:8187/health',
        'metrics_url': 'http://localhost:8187/metrics',
    },
]


def fetch_service_health(service: dict, timeout: float = 2.0) -> dict:
    """
    Fetch health status from a service.

    Args:
        service: Service configuration dict
        timeout: Request timeout in seconds

    Returns:
        dict with service health information
    """
    result = {
        'name': service['name'],
        'type': service['type'],
        'status': 'unknown',
        'response_time_ms': None,
        'error': None,
    }

    import time
    start = time.time()

    try:
        resp = requests.get(service['health_url'], timeout=timeout)
        response_time = (time.time() - start) * 1000

        result['response_time_ms'] = round(response_time, 2)

        if resp.status_code == 200:
            result['status'] = 'healthy'
            # Try to parse health response
            try:
                health_data = resp.json()
                result['details'] = health_data
            except Exception:
                pass
        else:
            result['status'] = 'degraded'

    except requests.exceptions.Timeout:
        result['status'] = 'timeout'
        result['response_time_ms'] = round((time.time() - start) * 1000, 2)
    except requests.exceptions.ConnectionError:
        result['status'] = 'unreachable'
        result['error'] = 'Connection refused'
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)

    return result


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_metrics(request):
    """
    GET /api/v2/service-mesh/get-metrics/

    Get service mesh metrics and health status.

    Query Parameters:
        - service: Filter by service name (optional)
        - include_prometheus: Include Prometheus metrics (default: false)

    Response:
        {
            "status": "healthy|degraded|unhealthy",
            "services": [
                {
                    "name": "api-gateway",
                    "type": "backend",
                    "status": "healthy",
                    "response_time_ms": 50.5,
                    "details": {...}
                },
                ...
            ],
            "summary": {
                "total": 4,
                "healthy": 3,
                "degraded": 1,
                "unreachable": 0
            },
            "timestamp": "2024-01-01T00:00:00Z"
        }
    """
    service_filter = request.query_params.get('service')
    include_prometheus = request.query_params.get('include_prometheus', 'false').lower() == 'true'

    # Filter services if requested
    services_to_check = MONITORED_SERVICES
    if service_filter:
        services_to_check = [s for s in MONITORED_SERVICES if s['name'] == service_filter]
        if not services_to_check:
            return Response({
                'success': False,
                'error': {
                    'code': 'UNKNOWN_SERVICE',
                    'message': f'Unknown service: {service_filter}',
                    'available_services': [s['name'] for s in MONITORED_SERVICES]
                }
            }, status=400)

    # Fetch health from all services in parallel
    results = []
    with ThreadPoolExecutor(max_workers=len(services_to_check)) as executor:
        futures = {
            executor.submit(fetch_service_health, svc): svc
            for svc in services_to_check
        }
        for future in as_completed(futures, timeout=5.0):
            try:
                results.append(future.result())
            except Exception as e:
                svc = futures[future]
                results.append({
                    'name': svc['name'],
                    'type': svc['type'],
                    'status': 'error',
                    'error': str(e),
                })

    # Add Django/Celery internal metrics
    internal_services = []

    # Check Celery workers
    try:
        from celery import current_app
        inspect = current_app.control.inspect(timeout=1.0)
        active = inspect.active()
        if active:
            worker_count = len(active)
            total_tasks = sum(len(tasks) for tasks in active.values())
            internal_services.append({
                'name': 'celery-workers',
                'type': 'internal',
                'status': 'healthy',
                'details': {
                    'worker_count': worker_count,
                    'active_tasks': total_tasks,
                },
            })
        else:
            internal_services.append({
                'name': 'celery-workers',
                'type': 'internal',
                'status': 'unreachable',
                'error': 'No workers available',
            })
    except Exception as e:
        internal_services.append({
            'name': 'celery-workers',
            'type': 'internal',
            'status': 'error',
            'error': str(e),
        })

    # Check Redis (Celery broker)
    try:
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        info = redis_conn.info()
        internal_services.append({
            'name': 'redis',
            'type': 'internal',
            'status': 'healthy',
            'details': {
                'connected_clients': info.get('connected_clients'),
                'used_memory_human': info.get('used_memory_human'),
            },
        })
    except Exception as e:
        internal_services.append({
            'name': 'redis',
            'type': 'internal',
            'status': 'unreachable',
            'error': str(e),
        })

    # Check PostgreSQL
    try:
        from django.db import connection
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        internal_services.append({
            'name': 'postgresql',
            'type': 'internal',
            'status': 'healthy',
        })
    except Exception as e:
        internal_services.append({
            'name': 'postgresql',
            'type': 'internal',
            'status': 'unreachable',
            'error': str(e),
        })

    # Combine results
    all_services = results + internal_services

    # Calculate summary
    summary = {
        'total': len(all_services),
        'healthy': sum(1 for s in all_services if s['status'] == 'healthy'),
        'degraded': sum(1 for s in all_services if s['status'] == 'degraded'),
        'unreachable': sum(1 for s in all_services if s['status'] in ['unreachable', 'timeout']),
        'error': sum(1 for s in all_services if s['status'] == 'error'),
    }

    # Determine overall status
    if summary['unreachable'] > 0 or summary['error'] > 0:
        overall_status = 'unhealthy'
    elif summary['degraded'] > 0:
        overall_status = 'degraded'
    else:
        overall_status = 'healthy'

    response_data = {
        'status': overall_status,
        'services': all_services,
        'summary': summary,
        'timestamp': timezone.now().isoformat(),
    }

    # Include Prometheus metrics if requested
    if include_prometheus:
        prometheus_metrics = []
        for svc in services_to_check:
            if svc.get('metrics_url'):
                try:
                    resp = requests.get(svc['metrics_url'], timeout=2.0)
                    if resp.status_code == 200:
                        prometheus_metrics.append({
                            'service': svc['name'],
                            'metrics': resp.text[:50000],  # Increased limit from 5000 to 50000
                        })
                except Exception:
                    pass
        response_data['prometheus_metrics'] = prometheus_metrics

    return Response(response_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_history(request):
    """
    GET /api/v2/service-mesh/get-history/

    Get historical metrics for a specific service.

    Query Parameters:
        - service: str (required) - Service name (e.g., 'api-gateway', 'worker')
        - minutes: int (optional, default=30) - Period of history in minutes

    Response:
        {
            "service": "api-gateway",
            "display_name": "API Gateway",
            "minutes": 30,
            "data_points": [
                {
                    "timestamp": "2024-01-01T00:00:00",
                    "ops_per_minute": 150.5,
                    "p95_latency_ms": 45.2,
                    "error_rate": 0.001
                },
                ...
            ]
        }
    """
    import asyncio
    from apps.operations.services.prometheus_client import (
        get_prometheus_client,
        SERVICE_CONFIG,
    )

    service = request.query_params.get('service')

    if not service:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'service parameter is required',
                'available_services': list(SERVICE_CONFIG.keys())
            }
        }, status=400)

    # Validate service name
    if service not in SERVICE_CONFIG:
        return Response({
            'success': False,
            'error': {
                'code': 'UNKNOWN_SERVICE',
                'message': f'Unknown service: {service}',
                'available_services': list(SERVICE_CONFIG.keys())
            }
        }, status=400)

    # Parse minutes parameter
    try:
        minutes = int(request.query_params.get('minutes', 30))
        minutes = max(1, min(minutes, 1440))  # Clamp to [1, 1440] (max 24 hours)
    except (ValueError, TypeError):
        minutes = 30

    # Get service display name
    config = SERVICE_CONFIG.get(service, {})
    display_name = config.get('display_name', service.title())

    # Fetch historical metrics from Prometheus
    data_points = []
    try:
        prometheus_client = get_prometheus_client()

        # Run async function in sync context using asyncio.run()
        # This is safer than manually managing event loops
        data_points = asyncio.run(
            prometheus_client.get_historical_metrics(service, minutes)
        )

    except Exception as e:
        logger.warning(
            f"Failed to fetch Prometheus metrics for {service}: {e}",
            extra={'service': service, 'minutes': minutes}
        )
        # Return empty list on Prometheus error - service mesh page can still work
        data_points = []

    return Response({
        'service': service,
        'display_name': display_name,
        'minutes': minutes,
        'data_points': data_points,
    })
