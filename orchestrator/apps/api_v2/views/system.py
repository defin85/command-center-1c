"""
System health check and configuration endpoints for API v2.

Provides comprehensive system health monitoring with parallel service checks
and system configuration for frontend defaults.
"""

import asyncio
import logging
import re
import time
import socket
from typing import Iterable

import httpx
import redis
from django.conf import settings
from django.db import connection
from django.core.cache import cache
from django.utils import timezone
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
from apps.operations.prometheus_metrics import (
    record_api_v2_duration,
    record_api_v2_error,
)

logger = logging.getLogger(__name__)
SYSTEM_HEALTH_CACHE_KEY = "system:health:prometheus"
SYSTEM_HEALTH_CACHE_TTL = getattr(settings, "SYSTEM_HEALTH_CACHE_TTL", 10)
SYSTEM_HEALTH_PROM_TIMEOUT = getattr(settings, "SYSTEM_HEALTH_PROM_TIMEOUT", 5)
SYSTEM_HEALTH_DIRECT_TIMEOUT = float(getattr(settings, "SYSTEM_HEALTH_DIRECT_TIMEOUT", 2))

EVENT_SUBSCRIBER_UP_PATTERN = re.compile(
    r'^cc1c_orchestrator_event_subscriber_up\{[^}]*group="orchestrator-group"[^}]*\}\s+([0-9eE+.\-]+)$',
    re.MULTILINE,
)
EVENT_SUBSCRIBER_CONSUMERS_PATTERN = re.compile(
    r'^cc1c_orchestrator_event_subscriber_consumers\{[^}]*group="orchestrator-group"[^}]*\}\s+([0-9eE+.\-]+)$',
    re.MULTILINE,
)
POOL_OUTBOX_DISPATCHER_UP_PATTERN = re.compile(
    r"^cc1c_orchestrator_pool_run_command_outbox_dispatcher_up(?:\{[^}]*\})?\s+([0-9eE+.\-]+)$",
    re.MULTILINE,
)


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
    })

class SystemHealthView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _normalize_disabled_services(raw_value: object) -> set[str]:
        if isinstance(raw_value, str):
            values = [part.strip().lower() for part in raw_value.split(",")]
        elif isinstance(raw_value, Iterable):
            values = [str(item).strip().lower() for item in raw_value]
        else:
            values = []
        known = set(SERVICE_CONFIG.keys())
        return {value for value in values if value and value in known}

    @staticmethod
    def _build_cache_key(disabled_services: set[str]) -> str:
        if not disabled_services:
            return SYSTEM_HEALTH_CACHE_KEY
        suffix = ",".join(sorted(disabled_services))
        return f"{SYSTEM_HEALTH_CACHE_KEY}:{suffix}"

    @staticmethod
    def _calculate_overall(statuses: list[str]) -> str:
        if not statuses:
            return "degraded"
        if any(status == "offline" for status in statuses):
            return "critical"
        if any(status == "degraded" for status in statuses):
            return "degraded"
        return "healthy"

    @staticmethod
    def _strip_internal_fields(results: list[dict]) -> list[dict]:
        return [{k: v for k, v in item.items() if k != "_service_key"} for item in results]

    def _build_service_payload(
        self,
        service_key: str,
        status: str,
        type_map: dict,
        url_map: dict,
        source: str,
        response_time_ms: float | None = None,
        details: dict | None = None,
    ) -> dict:
        config = SERVICE_CONFIG.get(service_key, {})
        payload_details = {"source": source}
        if details:
            payload_details.update(details)
        return {
            "_service_key": service_key,
            "name": config.get("display_name", service_key.title()),
            "type": type_map.get(service_key, "go-service"),
            "url": url_map.get(service_key),
            "status": status,
            "response_time_ms": response_time_ms,
            "last_check": timezone.now().isoformat(),
            "details": payload_details,
        }

    def _check_http_service(
        self,
        client: httpx.Client,
        service_key: str,
        url: str,
        type_map: dict,
        url_map: dict,
    ) -> dict:
        started = time.monotonic()
        try:
            response = client.get(url)
            elapsed = (time.monotonic() - started) * 1000
            if 200 <= response.status_code < 400:
                status = "online"
            elif 400 <= response.status_code < 500:
                status = "degraded"
            else:
                status = "offline"
            return self._build_service_payload(
                service_key,
                status,
                type_map,
                url_map,
                source="direct",
                response_time_ms=round(elapsed, 2),
                details={"http_status": response.status_code},
            )
        except Exception as exc:
            return self._build_service_payload(
                service_key,
                "offline",
                type_map,
                url_map,
                source="direct",
                details={"error": str(exc)},
            )

    def _check_postgresql(self, type_map: dict, url_map: dict) -> dict:
        started = time.monotonic()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            elapsed = (time.monotonic() - started) * 1000
            return self._build_service_payload(
                "postgresql",
                "online",
                type_map,
                url_map,
                source="direct",
                response_time_ms=round(elapsed, 2),
            )
        except Exception as exc:
            return self._build_service_payload(
                "postgresql",
                "offline",
                type_map,
                url_map,
                source="direct",
                details={"error": str(exc)},
            )

    def _check_redis(self, type_map: dict, url_map: dict) -> dict:
        redis_password = getattr(settings, "REDIS_PASSWORD", None)
        started = time.monotonic()
        try:
            client = redis.Redis(
                host=getattr(settings, "REDIS_HOST", "localhost"),
                port=int(getattr(settings, "REDIS_PORT", "6379")),
                db=int(getattr(settings, "REDIS_DB", "0")),
                password=redis_password if redis_password else None,
                socket_connect_timeout=SYSTEM_HEALTH_DIRECT_TIMEOUT,
                socket_timeout=SYSTEM_HEALTH_DIRECT_TIMEOUT,
            )
            client.ping()
            elapsed = (time.monotonic() - started) * 1000
            return self._build_service_payload(
                "redis",
                "online",
                type_map,
                url_map,
                source="direct",
                response_time_ms=round(elapsed, 2),
            )
        except Exception as exc:
            return self._build_service_payload(
                "redis",
                "offline",
                type_map,
                url_map,
                source="direct",
                details={"error": str(exc)},
            )

    def _check_ras_server(self, type_map: dict, url_map: dict) -> dict:
        ras_server = str(getattr(settings, "RAS_DEFAULT_SERVER", "localhost:1545"))
        host, _, port_str = ras_server.partition(":")
        try:
            port = int(port_str or "1545")
        except ValueError:
            port = 1545
        started = time.monotonic()
        try:
            with socket.create_connection(
                (host or "localhost", port),
                timeout=SYSTEM_HEALTH_DIRECT_TIMEOUT,
            ):
                elapsed = (time.monotonic() - started) * 1000
                return self._build_service_payload(
                    "ras-server",
                    "online",
                    type_map,
                    url_map,
                    source="direct",
                    response_time_ms=round(elapsed, 2),
                    details={"target": ras_server},
                )
        except Exception as exc:
            return self._build_service_payload(
                "ras-server",
                "offline",
                type_map,
                url_map,
                source="direct",
                details={"target": ras_server, "error": str(exc)},
            )

    def _check_orchestrator_runtime_services(
        self,
        client: httpx.Client,
        url_map: dict,
        type_map: dict,
    ) -> list[dict]:
        metrics_url = f"{url_map.get('orchestrator', 'http://localhost:8200').rstrip('/')}/metrics"
        try:
            response = client.get(metrics_url)
            response.raise_for_status()
            metrics_text = response.text
        except Exception as exc:
            fallback_details = {
                "error": str(exc),
                "note": "orchestrator metrics unavailable",
            }
            return [
                self._build_service_payload(
                    "event-subscriber",
                    "degraded",
                    type_map,
                    url_map,
                    source="direct",
                    details=fallback_details,
                ),
                self._build_service_payload(
                    "pool-outbox-dispatcher",
                    "degraded",
                    type_map,
                    url_map,
                    source="direct",
                    details=fallback_details,
                ),
            ]

        event_up_values = [
            float(value)
            for value in EVENT_SUBSCRIBER_UP_PATTERN.findall(metrics_text)
        ]
        event_consumers_values = [
            float(value)
            for value in EVENT_SUBSCRIBER_CONSUMERS_PATTERN.findall(metrics_text)
        ]
        dispatcher_up_values = [
            float(value)
            for value in POOL_OUTBOX_DISPATCHER_UP_PATTERN.findall(metrics_text)
        ]

        if not event_up_values:
            event_status = "degraded"
            event_details = {"note": "event_subscriber_up metric missing"}
        else:
            min_up = min(event_up_values)
            max_consumers = max(event_consumers_values) if event_consumers_values else 0.0
            if min_up < 0.5:
                event_status = "offline"
            elif max_consumers < 1:
                event_status = "degraded"
            else:
                event_status = "online"
            event_details = {
                "min_up": min_up,
                "max_consumers": max_consumers,
            }

        if not dispatcher_up_values:
            dispatcher_status = "degraded"
            dispatcher_details = {"note": "dispatcher_up metric missing"}
        else:
            max_up = max(dispatcher_up_values)
            dispatcher_status = "online" if max_up >= 0.5 else "offline"
            dispatcher_details = {"max_up": max_up}

        return [
            self._build_service_payload(
                "event-subscriber",
                event_status,
                type_map,
                url_map,
                source="direct",
                details=event_details,
            ),
            self._build_service_payload(
                "pool-outbox-dispatcher",
                dispatcher_status,
                type_map,
                url_map,
                source="direct",
                details=dispatcher_details,
            ),
        ]

    def _build_direct_fallback_results(self, url_map: dict, type_map: dict) -> list[dict]:
        results_by_key: dict[str, dict] = {}
        direct_health_urls = {
            "frontend": url_map.get("frontend"),
            "api-gateway": (
                f"{url_map['api-gateway'].rstrip('/')}/health"
                if url_map.get("api-gateway")
                else None
            ),
            "orchestrator": (
                f"{url_map['orchestrator'].rstrip('/')}/health"
                if url_map.get("orchestrator")
                else None
            ),
            "worker": (
                f"{url_map['worker'].rstrip('/')}/health"
                if url_map.get("worker")
                else None
            ),
            "worker-workflows": (
                f"{url_map['worker-workflows'].rstrip('/')}/health"
                if url_map.get("worker-workflows")
                else None
            ),
            "minio": (
                f"{url_map['minio'].rstrip('/')}/minio/health/ready"
                if url_map.get("minio")
                else None
            ),
        }
        with httpx.Client(
            timeout=SYSTEM_HEALTH_DIRECT_TIMEOUT,
            follow_redirects=True,
        ) as http_client:
            for service_key, service_url in direct_health_urls.items():
                if not service_url:
                    continue
                results_by_key[service_key] = self._check_http_service(
                    http_client,
                    service_key,
                    service_url,
                    type_map,
                    url_map,
                )

            runtime_results = self._check_orchestrator_runtime_services(
                http_client,
                url_map,
                type_map,
            )
            for result in runtime_results:
                results_by_key[result["_service_key"]] = result

        results_by_key["postgresql"] = self._check_postgresql(type_map, url_map)
        results_by_key["redis"] = self._check_redis(type_map, url_map)
        results_by_key["ras-server"] = self._check_ras_server(type_map, url_map)

        ordered_results = []
        for service_key in SERVICE_CONFIG.keys():
            if service_key in results_by_key:
                ordered_results.append(results_by_key[service_key])
            else:
                ordered_results.append(
                    self._build_service_payload(
                        service_key,
                        "degraded",
                        type_map,
                        url_map,
                        source="direct",
                        details={"note": "no direct check configured"},
                    )
                )
        return ordered_results

    def _apply_disabled_services(self, results: list[dict], disabled_services: set[str]) -> None:
        for result in results:
            service_key = result.get("_service_key")
            if service_key not in disabled_services:
                continue
            details = dict(result.get("details") or {})
            details["disabled"] = True
            details["disabled_reason"] = "excluded by SYSTEM_HEALTH_DISABLED_SERVICES"
            if result.get("status") == "offline":
                result["status"] = "degraded"
            result["details"] = details

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
        start_time = time.monotonic()
        endpoint = "system.health"
        disabled_services = self._normalize_disabled_services(
            getattr(settings, "SYSTEM_HEALTH_DISABLED_SERVICES", ())
        )
        status_map = {
            "healthy": "online",
            "degraded": "degraded",
            "critical": "offline",
        }

        api_gateway_url = getattr(settings, 'API_GATEWAY_URL', 'http://localhost:8180').rstrip('/')
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:15173').rstrip('/')
        worker_url = getattr(settings, 'WORKER_URL', 'http://localhost:9191').rstrip('/')
        worker_workflows_url = getattr(
            settings,
            'WORKER_WORKFLOWS_URL',
            'http://localhost:9092',
        ).rstrip('/')
        minio_endpoint = getattr(settings, 'MINIO_ENDPOINT', 'localhost:9000').lstrip('/')
        minio_secure = getattr(settings, 'MINIO_SECURE', False)
        minio_url = f"{'https' if minio_secure else 'http'}://{minio_endpoint}"

        url_map = {
            "frontend": f"{frontend_url}/",
            "api-gateway": api_gateway_url,
            "orchestrator": "http://localhost:8200",
            "worker": worker_url,
            "worker-workflows": worker_workflows_url,
            "pool-outbox-dispatcher": "http://localhost:8200/metrics",
            "minio": minio_url,
        }

        type_map = {
            "frontend": "frontend",
            "api-gateway": "go-service",
            "orchestrator": "django",
            "worker": "go-service",
            "worker-workflows": "go-service",
            "pool-outbox-dispatcher": "django",
            "postgresql": "database",
            "redis": "cache",
            "minio": "storage",
            "event-subscriber": "django",
            "ras-server": "external",
        }

        cache_key = self._build_cache_key(disabled_services)
        cached_payload = cache.get(cache_key)
        if cached_payload:
            record_api_v2_duration(endpoint, "cached", time.monotonic() - start_time)
            return Response(cached_payload)

        services_metrics = []
        prometheus_failed = False
        try:
            client = get_prometheus_client()

            async def _fetch_metrics():
                ping_result = await asyncio.wait_for(
                    client.query("up"),
                    timeout=SYSTEM_HEALTH_PROM_TIMEOUT,
                )
                if ping_result.get("status") == "error":
                    raise RuntimeError(
                        f"prometheus unavailable: {ping_result.get('error', 'unknown error')}"
                    )
                services = await asyncio.wait_for(
                    client.get_all_services_metrics(),
                    timeout=SYSTEM_HEALTH_PROM_TIMEOUT,
                )
                overall = await client.get_overall_health(services)
                return services, overall

            services_metrics, overall_health = asyncio.run(_fetch_metrics())
        except asyncio.TimeoutError:
            logger.warning("Prometheus health fetch timed out")
            record_api_v2_error(endpoint, "prometheus_timeout")
            prometheus_failed = True
        except Exception as e:
            logger.error(f"Prometheus health fetch failed: {e}")
            record_api_v2_error(endpoint, e.__class__.__name__)
            prometheus_failed = True

        if services_metrics:
            results = []
            for metrics in services_metrics:
                status = status_map.get(metrics.status, "offline")
                results.append(
                    self._build_service_payload(
                        metrics.name,
                        status,
                        type_map,
                        url_map,
                        source="prometheus",
                        details={
                            "ops_per_minute": metrics.ops_per_minute,
                            "active_operations": metrics.active_operations,
                            "p95_latency_ms": metrics.p95_latency_ms,
                            "error_rate": metrics.error_rate,
                        },
                    )
                )
        else:
            if prometheus_failed:
                logger.info("system.health switching to direct fallback checks")
            results = self._build_direct_fallback_results(url_map, type_map)

        self._apply_disabled_services(results, disabled_services)

        considered_results = [
            result for result in results
            if result.get("_service_key") not in disabled_services
        ]
        statuses = [result["status"] for result in considered_results]
        statistics = {
            'total': len(considered_results),
            'online': sum(1 for s in statuses if s == 'online'),
            'offline': sum(1 for s in statuses if s == 'offline'),
            'degraded': sum(1 for s in statuses if s == 'degraded'),
        }

        overall = self._calculate_overall(statuses)

        payload = {
            'timestamp': timezone.now().isoformat(),
            'overall_status': overall,
            'services': self._strip_internal_fields(results),
            'statistics': statistics,
        }
        cache.set(cache_key, payload, SYSTEM_HEALTH_CACHE_TTL)
        duration = time.monotonic() - start_time
        record_api_v2_duration(endpoint, "ok", duration)
        if duration > 2:
            logger.warning("system.health slow response %.2fs", duration)
        return Response(payload)


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
