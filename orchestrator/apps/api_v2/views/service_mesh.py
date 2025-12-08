"""
Service Mesh monitoring endpoints for API v2.

Provides metrics and monitoring for the service mesh.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

logger = logging.getLogger(__name__)


# =============================================================================
# Response Serializers for OpenAPI documentation
# =============================================================================

class ErrorDetailSerializer(serializers.Serializer):
    """Error detail structure."""
    code = serializers.CharField(help_text="Error code")
    message = serializers.CharField(help_text="Human-readable error message")
    available_services = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of available service names"
    )


class ErrorResponseSerializer(serializers.Serializer):
    """Standard error response."""
    success = serializers.BooleanField(default=False)
    error = ErrorDetailSerializer()


class ServiceMetricSerializer(serializers.Serializer):
    """Metrics for a single service."""
    name = serializers.CharField(help_text="Service name (e.g., api-gateway, worker)")
    type = serializers.CharField(help_text="Service type (backend, internal)")
    status = serializers.ChoiceField(
        choices=['healthy', 'degraded', 'timeout', 'unreachable', 'error', 'unknown'],
        help_text="Service health status"
    )
    response_time_ms = serializers.FloatField(
        required=False, allow_null=True,
        help_text="Response time in milliseconds"
    )
    error = serializers.CharField(required=False, allow_null=True, help_text="Error message if any")
    details = serializers.DictField(required=False, help_text="Additional service details")


class ServiceMeshSummarySerializer(serializers.Serializer):
    """Summary statistics for service mesh."""
    total = serializers.IntegerField(help_text="Total number of services")
    healthy = serializers.IntegerField(help_text="Number of healthy services")
    degraded = serializers.IntegerField(help_text="Number of degraded services")
    unreachable = serializers.IntegerField(help_text="Number of unreachable services")
    error = serializers.IntegerField(help_text="Number of services in error state")


class PrometheusMetricSerializer(serializers.Serializer):
    """Prometheus metrics for a service."""
    service = serializers.CharField(help_text="Service name")
    metrics = serializers.CharField(help_text="Raw Prometheus metrics text")


class ServiceMetricsResponseSerializer(serializers.Serializer):
    """Response for get_metrics endpoint."""
    status = serializers.ChoiceField(
        choices=['healthy', 'degraded', 'unhealthy'],
        help_text="Overall service mesh status"
    )
    services = ServiceMetricSerializer(many=True, help_text="List of service metrics")
    summary = ServiceMeshSummarySerializer(help_text="Summary statistics")
    timestamp = serializers.DateTimeField(help_text="Timestamp of metrics collection")
    prometheus_metrics = PrometheusMetricSerializer(
        many=True, required=False,
        help_text="Raw Prometheus metrics (only if include_prometheus=true)"
    )


class HistoryDataPointSerializer(serializers.Serializer):
    """Single data point in history."""
    timestamp = serializers.DateTimeField(help_text="Data point timestamp")
    ops_per_minute = serializers.FloatField(
        required=False, allow_null=True,
        help_text="Operations per minute"
    )
    p95_latency_ms = serializers.FloatField(
        required=False, allow_null=True,
        help_text="95th percentile latency in milliseconds"
    )
    error_rate = serializers.FloatField(
        required=False, allow_null=True,
        help_text="Error rate (0.0 to 1.0)"
    )


class ServiceHistoryResponseSerializer(serializers.Serializer):
    """Response for get_history endpoint."""
    service = serializers.CharField(help_text="Service name")
    display_name = serializers.CharField(help_text="Human-readable service name")
    minutes = serializers.IntegerField(help_text="History period in minutes")
    data_points = HistoryDataPointSerializer(many=True, help_text="Historical data points")

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


@extend_schema(
    tags=['v2'],
    summary='Get service mesh metrics',
    description='Get service mesh metrics and health status for all monitored services including Go services, Redis, and PostgreSQL.',
    parameters=[
        OpenApiParameter(name='service', type=str, required=False, description='Filter by service name (e.g., api-gateway, worker)'),
        OpenApiParameter(name='include_prometheus', type=bool, required=False, description='Include raw Prometheus metrics (default: false)'),
    ],
    responses={
        200: ServiceMetricsResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
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

    # Add internal infrastructure metrics
    internal_services = []

    # Check Redis
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


@extend_schema(
    tags=['v2'],
    summary='Get service metrics history',
    description='Get historical metrics for a specific service from Prometheus. Returns ops/minute, p95 latency, and error rate over time.',
    parameters=[
        OpenApiParameter(name='service', type=str, required=True, description='Service name (e.g., api-gateway, worker, ras-adapter)'),
        OpenApiParameter(name='minutes', type=int, required=False, description='History period in minutes (default: 30, max: 1440)'),
    ],
    responses={
        200: ServiceHistoryResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
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
