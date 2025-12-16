"""
System health check and configuration endpoints for API v2.

Provides comprehensive system health monitoring with parallel service checks
and system configuration for frontend defaults.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from django.conf import settings
from django.db import connection
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

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


@extend_schema(
    tags=['v2'],
    summary='Get system health status',
    description='Returns comprehensive system health status with parallel service checks for all monitored services.',
    responses={
        200: SystemHealthResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
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
    redis_client = None
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

    # Check Event Subscriber (via Redis consumer group)
    try:
        start = time.time()
        if redis_client is None:
            import redis
            redis_client = redis.Redis(host='localhost', port=6379, socket_timeout=2)
        # Check if orchestrator-group consumer exists on any stream
        stream = 'events:worker:cluster-synced'
        groups = redis_client.xinfo_groups(stream)
        response_time = (time.time() - start) * 1000
        orchestrator_group = next(
            (g for g in groups if g.get('name', b'').decode('utf-8') == 'orchestrator-group'),
            None
        )
        if orchestrator_group:
            consumers = orchestrator_group.get('consumers', 0)
            results.append({
                'name': 'Event Subscriber',
                'type': 'django',
                'status': 'online' if consumers > 0 else 'degraded',
                'response_time_ms': round(response_time, 2),
                'last_check': timezone.now().isoformat(),
                'details': {'consumers': consumers, 'stream': stream},
            })
        else:
            results.append({
                'name': 'Event Subscriber',
                'type': 'django',
                'status': 'offline',
                'response_time_ms': None,
                'last_check': timezone.now().isoformat(),
                'details': {'error': 'consumer_group_not_found'},
            })
    except Exception as e:
        logger.warning(f"Event Subscriber health check failed: {e}")
        results.append({
            'name': 'Event Subscriber',
            'type': 'django',
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


# =============================================================================
# System Configuration Endpoint
# =============================================================================

class SystemConfigSerializer(serializers.Serializer):
    """System configuration for frontend defaults."""
    ras_default_server = serializers.CharField(
        help_text="Default RAS server address for new clusters (e.g., localhost:1545)"
    )
    ras_adapter_url = serializers.CharField(
        help_text="RAS Adapter service URL (e.g., http://localhost:8188)"
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
            "ras_adapter_url": "http://localhost:8188"
        }
    """
    return Response({
        'ras_default_server': getattr(settings, 'RAS_DEFAULT_SERVER', 'localhost:1545'),
        'ras_adapter_url': getattr(settings, 'RAS_ADAPTER_URL', 'http://localhost:8188'),
    })
