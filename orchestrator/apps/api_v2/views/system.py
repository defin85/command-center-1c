"""
System health check and configuration endpoints for API v2.

Provides comprehensive system health monitoring with parallel service checks
and system configuration for frontend defaults.
"""

import logging
from django.conf import settings
from django.utils import timezone
from asgiref.sync import async_to_sync
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.operations.services.prometheus_client import (
    get_prometheus_client,
    SERVICE_CONFIG,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Response Serializers for OpenAPI documentation
# =============================================================================

class ServiceHealthSerializer(serializers.Serializer):
    """Health status of a single service."""
    name = serializers.CharField(help_text="Service name (e.g., API Gateway, PostgreSQL)")
    type = serializers.CharField(help_text="Service type (go-service, django, database, cache, monitoring, tracing)")
    url = serializers.CharField(required=False, help_text="Health check URL")
    status = serializers.ChoiceField(
        choices=['online', 'offline', 'degraded'],
        help_text="Service status"
    )
    response_time_ms = serializers.FloatField(
        required=False, allow_null=True,
        help_text="Response time in milliseconds"
    )
    last_check = serializers.DateTimeField(help_text="Timestamp of last health check")
    details = serializers.DictField(required=False, help_text="Additional details (error info, etc.)")


class SystemStatisticsSerializer(serializers.Serializer):
    """Aggregated statistics for all services."""
    total = serializers.IntegerField(help_text="Total number of services")
    online = serializers.IntegerField(help_text="Number of online services")
    offline = serializers.IntegerField(help_text="Number of offline services")
    degraded = serializers.IntegerField(help_text="Number of degraded services")


class SystemHealthResponseSerializer(serializers.Serializer):
    """Response for system_health endpoint."""
    timestamp = serializers.DateTimeField(help_text="Current timestamp")
    overall_status = serializers.ChoiceField(
        choices=['healthy', 'degraded', 'critical'],
        help_text="Overall system status"
    )
    services = ServiceHealthSerializer(many=True, help_text="List of service health statuses")
    statistics = SystemStatisticsSerializer(help_text="Aggregated statistics")

# =============================================================================
# Current User Endpoint (SPA identity)
# =============================================================================


class CurrentUserSerializer(serializers.Serializer):
    """Minimal identity payload for SPA."""
    id = serializers.IntegerField()
    username = serializers.CharField()
    is_staff = serializers.BooleanField()
    is_superuser = serializers.BooleanField()


@extend_schema(
    tags=['v2'],
    summary='Get current user',
    description='Returns the currently authenticated user (minimal identity for SPA header/roles).',
    responses={
        200: CurrentUserSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_me(request):
    """
    GET /api/v2/system/me/

    Returns minimal identity information for SPA.
    """
    user = request.user
    return Response({
        'id': user.id,
        'username': user.get_username(),
        'is_staff': bool(getattr(user, 'is_staff', False)),
        'is_superuser': bool(getattr(user, 'is_superuser', False)),
    })

class SystemHealthView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['v2'],
        summary='Get system health status',
        description='Returns comprehensive system health status with parallel service checks for all monitored services.',
        responses={
            200: SystemHealthResponseSerializer,
            401: OpenApiResponse(description='Unauthorized'),
        }
    )
    def get(self, request):
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
        status_map = {
            "healthy": "online",
            "degraded": "degraded",
            "critical": "offline",
        }

        api_gateway_url = getattr(settings, 'API_GATEWAY_URL', 'http://localhost:8180').rstrip('/')
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173').rstrip('/')
        worker_url = getattr(settings, 'WORKER_URL', 'http://localhost:9091').rstrip('/')

        url_map = {
            "frontend": f"{frontend_url}/",
            "api-gateway": api_gateway_url,
            "orchestrator": "http://localhost:8200",
            "worker": worker_url,
        }

        type_map = {
            "frontend": "frontend",
            "api-gateway": "go-service",
            "orchestrator": "django",
            "worker": "go-service",
            "postgresql": "database",
            "redis": "cache",
            "event-subscriber": "django",
            "ras-server": "external",
        }

        try:
            client = get_prometheus_client()
            services_metrics = async_to_sync(client.get_all_services_metrics)()
            overall_health = async_to_sync(client.get_overall_health)(services_metrics)
        except Exception as e:
            logger.error(f"Prometheus health fetch failed: {e}")
            services_metrics = []
            overall_health = "critical"

        results = []
        for metrics in services_metrics:
            config = SERVICE_CONFIG.get(metrics.name, {})
            display_name = config.get("display_name", metrics.name.title())
            status = status_map.get(metrics.status, "offline")
            results.append({
                "name": display_name,
                "type": type_map.get(metrics.name, "go-service"),
                "url": url_map.get(metrics.name),
                "status": status,
                "response_time_ms": None,
                "last_check": timezone.now().isoformat(),
                "details": {
                    "source": "prometheus",
                    "ops_per_minute": metrics.ops_per_minute,
                    "active_operations": metrics.active_operations,
                    "p95_latency_ms": metrics.p95_latency_ms,
                    "error_rate": metrics.error_rate,
                },
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
        overall = overall_health

        return Response({
            'timestamp': timezone.now().isoformat(),
            'overall_status': overall,
            'services': results,
            'statistics': statistics,
        })


# =============================================================================
# System Configuration Endpoint
# =============================================================================

class SystemConfigSerializer(serializers.Serializer):
    """System configuration for frontend defaults."""
    ras_default_server = serializers.CharField(
        help_text="Default RAS server address for new clusters (e.g., localhost:1545)"
    )


@extend_schema(
    tags=['v2'],
    summary='Get system configuration',
    description='Returns system configuration values for frontend defaults.',
    responses={
        200: SystemConfigSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_config(request):
    """
    GET /api/v2/system/config/

    Returns system configuration for frontend defaults.
    These values come from Django settings (environment variables).

    Response:
        {
            "ras_default_server": "localhost:1539",
            "ras_default_server": "localhost:1539"
        }
    """
    return Response({
        'ras_default_server': getattr(settings, 'RAS_DEFAULT_SERVER', 'localhost:1545'),
    })
