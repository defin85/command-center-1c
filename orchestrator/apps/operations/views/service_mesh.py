"""
REST API views for Service Mesh monitoring.

Provides endpoints for:
- Current service metrics
- Historical metrics for charts
- Recent operations filtered by service
"""
import logging
from datetime import datetime
from typing import List, Dict, Any

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from asgiref.sync import async_to_sync

from apps.operations.models import BatchOperation
from apps.operations.services.prometheus_client import (
    get_prometheus_client,
    SERVICE_CONFIG,
)

logger = logging.getLogger(__name__)


class ServiceMeshMetricsView(APIView):
    """
    GET /api/v1/service-mesh/metrics/

    Returns current metrics for all services in the mesh.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get current service mesh metrics",
        description="Returns real-time metrics for all services including ops/min, latency, error rate",
        responses={
            200: OpenApiResponse(
                description="Service mesh metrics",
                response={
                    'type': 'object',
                    'properties': {
                        'services': {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'name': {'type': 'string'},
                                    'display_name': {'type': 'string'},
                                    'status': {'type': 'string', 'enum': ['healthy', 'degraded', 'critical']},
                                    'ops_per_minute': {'type': 'number'},
                                    'active_operations': {'type': 'integer'},
                                    'p95_latency_ms': {'type': 'number'},
                                    'error_rate': {'type': 'number'},
                                    'last_updated': {'type': 'string', 'format': 'date-time'},
                                }
                            }
                        },
                        'connections': {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'source': {'type': 'string'},
                                    'target': {'type': 'string'},
                                    'requests_per_minute': {'type': 'number'},
                                    'avg_latency_ms': {'type': 'number'},
                                }
                            }
                        },
                        'overall_health': {'type': 'string', 'enum': ['healthy', 'degraded', 'critical']},
                        'timestamp': {'type': 'string', 'format': 'date-time'},
                    }
                }
            ),
            500: OpenApiResponse(description="Prometheus unavailable"),
        }
    )
    def get(self, request):
        """Get current metrics for all services."""
        try:
            client = get_prometheus_client()

            # Fetch metrics asynchronously
            services_metrics = async_to_sync(client.get_all_services_metrics)()
            connections = async_to_sync(client.get_service_connections)()
            overall_health = async_to_sync(client.get_overall_health)(services_metrics)

            return Response({
                'services': [m.to_dict() for m in services_metrics],
                'connections': [c.to_dict() for c in connections],
                'overall_health': overall_health,
                'timestamp': datetime.utcnow().isoformat(),
            })

        except Exception as e:
            logger.error(f"Error fetching service mesh metrics: {e}")
            # Return fallback data with degraded status
            return Response({
                'services': self._get_fallback_services(),
                'connections': [],
                'overall_health': 'degraded',
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
            })

    def _get_fallback_services(self) -> List[Dict[str, Any]]:
        """Generate fallback service data when Prometheus is unavailable."""
        fallback = []
        for name, config in SERVICE_CONFIG.items():
            fallback.append({
                'name': name,
                'display_name': config.get('display_name', name.title()),
                'status': 'degraded',
                'ops_per_minute': 0.0,
                'active_operations': 0,
                'p95_latency_ms': 0.0,
                'error_rate': 0.0,
                'last_updated': datetime.utcnow().isoformat(),
            })
        return fallback


class ServiceMeshHistoryView(APIView):
    """
    GET /api/v1/service-mesh/history/{service}/

    Returns historical metrics for a specific service.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get historical metrics for a service",
        description="Returns time-series metrics for charts (ops/min, latency, error rate)",
        parameters=[
            OpenApiParameter(
                name='service',
                type=str,
                location=OpenApiParameter.PATH,
                description='Service name (e.g., api-gateway, worker)',
            ),
            OpenApiParameter(
                name='minutes',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Number of minutes of history (default: 30)',
                default=30,
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Historical metrics data points",
                response={
                    'type': 'object',
                    'properties': {
                        'service': {'type': 'string'},
                        'minutes': {'type': 'integer'},
                        'data_points': {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'timestamp': {'type': 'string', 'format': 'date-time'},
                                    'ops_per_minute': {'type': 'number'},
                                    'p95_latency_ms': {'type': 'number'},
                                    'error_rate': {'type': 'number'},
                                }
                            }
                        },
                    }
                }
            ),
            400: OpenApiResponse(description="Invalid service name"),
            500: OpenApiResponse(description="Prometheus unavailable"),
        }
    )
    def get(self, request, service: str):
        """Get historical metrics for a specific service."""
        # Validate service name
        if service not in SERVICE_CONFIG:
            return Response(
                {'error': f'Unknown service: {service}. Valid services: {list(SERVICE_CONFIG.keys())}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        minutes = request.query_params.get('minutes', 30)
        try:
            minutes = int(minutes)
            minutes = max(5, min(minutes, 1440))  # Clamp to 5 min - 24 hours
        except ValueError:
            minutes = 30

        try:
            client = get_prometheus_client()
            data_points = async_to_sync(client.get_historical_metrics)(service, minutes)

            return Response({
                'service': service,
                'display_name': SERVICE_CONFIG[service].get('display_name', service.title()),
                'minutes': minutes,
                'data_points': data_points,
            })

        except Exception as e:
            logger.error(f"Error fetching historical metrics for {service}: {e}")
            return Response({
                'service': service,
                'display_name': SERVICE_CONFIG[service].get('display_name', service.title()),
                'minutes': minutes,
                'data_points': [],
                'error': str(e),
            })


class ServiceMeshOperationsView(APIView):
    """
    GET /api/v1/service-mesh/operations/

    Returns recent operations, optionally filtered by service.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get recent operations",
        description="Returns recent batch operations with optional service filter",
        parameters=[
            OpenApiParameter(
                name='service',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filter by service name',
                required=False,
            ),
            OpenApiParameter(
                name='limit',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Maximum number of operations to return (default: 50)',
                default=50,
            ),
            OpenApiParameter(
                name='status',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filter by operation status',
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="List of recent operations",
                response={
                    'type': 'object',
                    'properties': {
                        'operations': {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'id': {'type': 'string'},
                                    'name': {'type': 'string'},
                                    'operation_type': {'type': 'string'},
                                    'status': {'type': 'string'},
                                    'service': {'type': 'string'},
                                    'duration_seconds': {'type': 'number'},
                                    'created_at': {'type': 'string', 'format': 'date-time'},
                                    'completed_at': {'type': 'string', 'format': 'date-time'},
                                    'total_tasks': {'type': 'integer'},
                                    'completed_tasks': {'type': 'integer'},
                                    'failed_tasks': {'type': 'integer'},
                                }
                            }
                        },
                        'total': {'type': 'integer'},
                    }
                }
            ),
        }
    )
    def get(self, request):
        """Get recent operations with optional filtering."""
        service = request.query_params.get('service')
        status_filter = request.query_params.get('status')
        limit = request.query_params.get('limit', 50)

        try:
            limit = int(limit)
            limit = max(1, min(limit, 200))  # Clamp to 1-200
        except ValueError:
            limit = 50

        # Build queryset
        queryset = BatchOperation.objects.all().order_by('-created_at')

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Note: In a real implementation, you'd have a service field on BatchOperation
        # For now, we'll infer service from operation_type or metadata
        if service:
            # Filter based on operation metadata or type
            # This is a simplified implementation
            pass

        operations = queryset[:limit]

        # Format response
        ops_data = []
        for op in operations:
            # Infer service from operation type
            inferred_service = self._infer_service(op)

            ops_data.append({
                'id': str(op.id),
                'name': op.name,
                'operation_type': op.operation_type,
                'status': op.status,
                'service': inferred_service,
                'duration_seconds': op.duration_seconds,
                'created_at': op.created_at.isoformat() if op.created_at else None,
                'completed_at': op.completed_at.isoformat() if op.completed_at else None,
                'total_tasks': op.total_tasks,
                'completed_tasks': op.completed_tasks,
                'failed_tasks': op.failed_tasks,
                'progress': op.progress,
            })

        return Response({
            'operations': ops_data,
            'total': queryset.count(),
        })

    def _infer_service(self, operation: BatchOperation) -> str:
        """
        Infer which service handled an operation based on its type.

        This is a simplified heuristic - in production, you'd track this explicitly.
        """
        op_type = operation.operation_type.lower()

        if 'install' in op_type or 'extension' in op_type:
            return 'worker'
        elif 'ras' in op_type or 'cluster' in op_type or 'lock' in op_type:
            return 'ras-adapter'
        elif 'query' in op_type or 'odata' in op_type:
            return 'orchestrator'
        else:
            return 'worker'
