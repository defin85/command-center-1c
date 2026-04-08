"""
Service Mesh monitoring endpoints for API v2.

Provides metrics and monitoring for the service mesh.
"""

import asyncio
import logging
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.operations.services.prometheus_client import (
    get_prometheus_client,
    SERVICE_CONFIG,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Response Serializers for OpenAPI documentation
# =============================================================================

class ServiceMeshErrorDetailSerializer(serializers.Serializer):
    """Error detail structure."""
    code = serializers.CharField(help_text="Error code")
    message = serializers.CharField(help_text="Human-readable error message")
    available_services = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of available service names"
    )


class ServiceMeshErrorResponseSerializer(serializers.Serializer):
    """Standard error response."""
    success = serializers.BooleanField(default=False)
    error = ServiceMeshErrorDetailSerializer()
    request_id = serializers.CharField()
    ui_action_id = serializers.CharField(required=False)


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
        help_text="Raw Prometheus metrics (reserved, may be empty even if requested)"
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

TYPE_MAP = {
    "frontend": "backend",
    "api-gateway": "backend",
    "orchestrator": "backend",
    "worker": "backend",
    "worker-workflows": "backend",
    "pool-outbox-dispatcher": "internal",
    "postgresql": "internal",
    "redis": "internal",
    "event-subscriber": "internal",
    "ras-server": "external",
}


def _map_metric_status(item) -> str:
    availability_status = getattr(item, "availability_status", "available")
    if availability_status == "unavailable":
        return "unreachable"
    if item.status == "healthy":
        return "healthy"
    return "degraded"


@extend_schema(
    tags=['v2'],
    summary='Get service mesh metrics',
    description='Get service mesh metrics and health status for all monitored services including Go services, Redis, and PostgreSQL.',
    parameters=[
        OpenApiParameter(name='service', type=str, required=False, description='Filter by service name (e.g., api-gateway, worker)'),
        OpenApiParameter(name='include_prometheus', type=bool, required=False, description='Include raw Prometheus metrics (reserved, default: false)'),
    ],
    responses={
        200: ServiceMetricsResponseSerializer,
        400: ServiceMeshErrorResponseSerializer,
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

    available_services = list(SERVICE_CONFIG.keys())
    if service_filter and service_filter not in SERVICE_CONFIG:
        return Response({
            'success': False,
            'error': {
                'code': 'UNKNOWN_SERVICE',
                'message': f'Unknown service: {service_filter}',
                'available_services': available_services
            }
        }, status=400)

    try:
        client = get_prometheus_client()
        if service_filter:
            metrics = [asyncio.run(client.get_service_metrics(service_filter))]
        else:
            metrics = asyncio.run(client.get_all_services_metrics())
    except Exception as e:
        logger.error(f"Prometheus metrics fetch failed: {e}")
        metrics = []

    all_services = []
    for item in metrics:
        status = _map_metric_status(item)
        all_services.append({
            "name": item.name,
            "type": TYPE_MAP.get(item.name, "backend"),
            "status": status,
            "response_time_ms": round(item.p95_latency_ms, 2) if item.p95_latency_ms else None,
            "details": {
                "display_name": item.display_name,
                "severity": item.status,
                "availability_status": getattr(item, "availability_status", "available"),
                "ops_per_minute": item.ops_per_minute,
                "active_operations": item.active_operations,
                "p95_latency_ms": item.p95_latency_ms,
                "error_rate": item.error_rate,
            },
        })

    # Calculate summary
    summary = {
        'total': len(all_services),
        'healthy': sum(1 for s in all_services if s['status'] == 'healthy'),
        'degraded': sum(1 for s in all_services if s['status'] == 'degraded'),
        'unreachable': sum(1 for s in all_services if s['status'] == 'unreachable'),
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
        response_data['prometheus_metrics'] = []

    return Response(response_data)


@extend_schema(
    tags=['v2'],
    summary='Get service metrics history',
    description='Get historical metrics for a specific service from Prometheus. Returns ops/minute, p95 latency, and error rate over time.',
    parameters=[
        OpenApiParameter(name='service', type=str, required=True, description='Service name (e.g., api-gateway, worker)'),
        OpenApiParameter(name='minutes', type=int, required=False, description='History period in minutes (default: 30, max: 1440)'),
    ],
    responses={
        200: ServiceHistoryResponseSerializer,
        400: ServiceMeshErrorResponseSerializer,
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
        data_points = asyncio.run(prometheus_client.get_historical_metrics(service, minutes))
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
