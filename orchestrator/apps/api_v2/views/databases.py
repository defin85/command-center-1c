"""
Database endpoints for API v2.

Provides action-based endpoints for database operations.
"""

import logging

from django.db.models import Q
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.databases.models import Database
from apps.databases.serializers import DatabaseSerializer, ClusterSerializer
from apps.operations.services.admin_action_audit import log_admin_action

logger = logging.getLogger(__name__)


# =============================================================================
# Response Serializers for OpenAPI documentation
# =============================================================================

class ErrorDetailSerializer(serializers.Serializer):
    """Error detail structure."""
    code = serializers.CharField(help_text="Error code (e.g., MISSING_PARAMETER)")
    message = serializers.CharField(help_text="Human-readable error message")
    details = serializers.DictField(required=False, help_text="Additional error details")


class ErrorResponseSerializer(serializers.Serializer):
    """Standard error response."""
    success = serializers.BooleanField(default=False)
    error = ErrorDetailSerializer()


class DatabaseListFiltersSerializer(serializers.Serializer):
    """Applied filters for database list."""
    cluster_id = serializers.UUIDField(required=False)
    status = serializers.CharField(required=False)
    health_status = serializers.CharField(required=False)
    search = serializers.CharField(required=False)


class DatabaseListResponseSerializer(serializers.Serializer):
    """Response for list_databases endpoint."""
    databases = DatabaseSerializer(many=True)
    count = serializers.IntegerField(help_text="Number of databases in current page")
    total = serializers.IntegerField(help_text="Total number of databases matching filters")


class DatabaseDetailResponseSerializer(serializers.Serializer):
    """Response for get_database endpoint."""
    database = DatabaseSerializer()
    cluster = ClusterSerializer(required=False, allow_null=True, help_text="Cluster info if database belongs to a cluster")


class HealthCheckResponseSerializer(serializers.Serializer):
    """Response for health_check endpoint."""
    database_id = serializers.CharField(help_text="Database UUID")
    status = serializers.ChoiceField(
        choices=['ok', 'degraded', 'down'],
        help_text="Health status: ok, degraded, or down"
    )
    response_time_ms = serializers.FloatField(help_text="Response time in milliseconds")
    checked_at = serializers.DateTimeField(help_text="Timestamp of the health check")


class HealthCheckResultSerializer(serializers.Serializer):
    """Single result in bulk health check."""
    database_id = serializers.CharField(help_text="Database UUID")
    status = serializers.ChoiceField(
        choices=['ok', 'degraded', 'down', 'error'],
        help_text="Health status"
    )
    response_time_ms = serializers.FloatField(required=False, help_text="Response time in milliseconds")
    error = serializers.CharField(required=False, help_text="Error message if check failed")


class HealthCheckSummarySerializer(serializers.Serializer):
    """Summary of bulk health check results."""
    total = serializers.IntegerField(help_text="Total databases checked")
    healthy = serializers.IntegerField(help_text="Number of healthy databases (status=ok)")
    degraded = serializers.IntegerField(help_text="Number of degraded databases")
    down = serializers.IntegerField(help_text="Number of down databases")


class BulkHealthCheckResponseSerializer(serializers.Serializer):
    """Response for bulk_health_check endpoint."""
    results = HealthCheckResultSerializer(many=True)
    summary = HealthCheckSummarySerializer()


class BulkHealthCheckRequestSerializer(serializers.Serializer):
    """Request body for bulk_health_check endpoint."""
    database_ids = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of database UUIDs to check"
    )
    cluster_id = serializers.UUIDField(
        required=False,
        help_text="Check all databases in this cluster"
    )


class HealthCheckRequestSerializer(serializers.Serializer):
    """Request body for health_check endpoint."""
    database_id = serializers.CharField(help_text="Database UUID to check")


class SetDatabaseStatusRequestSerializer(serializers.Serializer):
    """Request body for set_status endpoint."""

    database_ids = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
        max_length=500,
        help_text="List of database IDs to update",
    )
    status = serializers.ChoiceField(
        choices=[
            Database.STATUS_ACTIVE,
            Database.STATUS_INACTIVE,
            Database.STATUS_MAINTENANCE,
        ],
        help_text="New database status (active, inactive, maintenance)",
    )
    reason = serializers.CharField(required=False, allow_blank=True)


class SetDatabaseStatusResponseSerializer(serializers.Serializer):
    """Response for set_status endpoint."""

    updated = serializers.IntegerField()
    not_found = serializers.ListField(child=serializers.CharField())
    status = serializers.CharField()
    message = serializers.CharField()


def _perform_odata_health_check(db, timeout=None):
    """
    Helper function to perform OData health check on a database.

    Args:
        db: Database instance
        timeout: Optional timeout in seconds

    Returns:
        tuple: (health_status, response_time)
    """
    import time
    import requests

    start_time = time.time()
    try:
        # Simple OData metadata check
        odata_url = db.odata_url.rstrip('/') + '/$metadata'
        response = requests.get(
            odata_url,
            auth=(db.username, db.password),
            timeout=timeout or db.connection_timeout or 30,
        )

        response_time = (time.time() - start_time) * 1000  # ms

        if response.status_code == 200:
            health_status = 'ok'
            db.mark_health_check(success=True, response_time=response_time)
        else:
            health_status = 'degraded'
            db.mark_health_check(success=False)

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        health_status = 'down'
        db.mark_health_check(success=False)
        logger.warning(f"Health check failed for {db.name}: {e}")

    return health_status, response_time


@extend_schema(
    tags=['v2'],
    summary='List all databases',
    description='List all databases with optional filtering by cluster, status, health status, and search term. Supports pagination.',
    parameters=[
        OpenApiParameter(name='cluster_id', type=str, required=False, description='Filter by cluster UUID'),
        OpenApiParameter(name='status', type=str, required=False, description='Filter by status (active, inactive, error, maintenance)'),
        OpenApiParameter(name='health_status', type=str, required=False, description='Filter by health status (ok, degraded, down, unknown)'),
        OpenApiParameter(name='search', type=str, required=False, description='Search by name or description'),
        OpenApiParameter(name='limit', type=int, required=False, description='Maximum results (default: 100, max: 1000)'),
        OpenApiParameter(name='offset', type=int, required=False, description='Pagination offset (default: 0)'),
    ],
    responses={
        200: DatabaseListResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_databases(request):
    """
    GET /api/v2/databases/list-databases/

    List all databases with optional filtering.

    Query Parameters:
        - cluster_id: Filter by cluster UUID
        - status: Filter by status (active, inactive, error, maintenance)
        - health_status: Filter by health status (ok, degraded, down, unknown)
        - search: Search by name or description
        - limit: Maximum results (default: 100)
        - offset: Pagination offset (default: 0)

    Response:
        {
            "databases": [...],
            "count": 100,
            "total": 700
        }
    """
    cluster_id = request.query_params.get('cluster_id')
    status = request.query_params.get('status')
    health_status = request.query_params.get('health_status')
    search = request.query_params.get('search')

    # Safely parse integer parameters with validation
    try:
        limit = int(request.query_params.get('limit', 100))
        limit = max(1, min(limit, 1000))  # Clamp to [1, 1000]
    except (ValueError, TypeError):
        limit = 100

    try:
        offset = int(request.query_params.get('offset', 0))
        offset = max(0, offset)
    except (ValueError, TypeError):
        offset = 0

    qs = Database.objects.all()

    # Apply filters
    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)
    if status:
        qs = qs.filter(status=status)
    if health_status:
        qs = qs.filter(last_check_status=health_status)
    if search:
        qs = qs.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    # Get total count before pagination
    total = qs.count()

    # Apply pagination
    qs = qs[offset:offset + limit]

    serializer = DatabaseSerializer(qs, many=True)

    return Response({
        'databases': serializer.data,
        'count': len(serializer.data),
        'total': total,
    })


@extend_schema(
    tags=['v2'],
    summary='Get database details',
    description='Get detailed information about a specific database including cluster info.',
    parameters=[
        OpenApiParameter(name='database_id', type=str, required=True, description='Database UUID'),
    ],
    responses={
        200: DatabaseDetailResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_database(request):
    """
    GET /api/v2/databases/get-database/?database_id=X

    Get detailed information about a specific database.

    Query Parameters:
        - database_id: Database ID (required)

    Response:
        {
            "database": {...},
            "cluster": {...}
        }
    """
    database_id = request.query_params.get('database_id')

    if not database_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'database_id is required'
            }
        }, status=400)

    try:
        db = Database.objects.select_related('cluster').get(id=database_id)
    except Database.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'DATABASE_NOT_FOUND',
                'message': 'Database not found'
            }
        }, status=404)

    serializer = DatabaseSerializer(db)

    # Include cluster info if available
    cluster_info = None
    if db.cluster:
        cluster_info = ClusterSerializer(db.cluster).data

    return Response({
        'database': serializer.data,
        'cluster': cluster_info,
    })


@extend_schema(
    tags=['v2'],
    summary='Health check database',
    description='Perform OData health check on a specific database. Checks connectivity and response time.',
    request=HealthCheckRequestSerializer,
    responses={
        200: HealthCheckResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def health_check(request):
    """
    POST /api/v2/databases/health-check/

    Perform health check on a specific database.

    Request Body:
        {
            "database_id": "string"
        }

    Response:
        {
            "database_id": "string",
            "status": "ok|degraded|down",
            "response_time_ms": 150,
            "checked_at": "2024-01-01T00:00:00Z"
        }
    """
    database_id = request.data.get('database_id')

    if not database_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'database_id is required'
            }
        }, status=400)

    try:
        db = Database.objects.get(id=database_id)
    except Database.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'DATABASE_NOT_FOUND',
                'message': 'Database not found'
            }
        }, status=404)

    # Perform OData health check using helper function
    from django.utils import timezone

    health_status, response_time = _perform_odata_health_check(db)

    return Response({
        'database_id': database_id,
        'status': health_status,
        'response_time_ms': round(response_time, 2),
        'checked_at': timezone.now().isoformat(),
    })


@extend_schema(
    tags=['v2'],
    summary='Bulk health check databases',
    description='Perform health check on multiple databases in parallel. Provide either database_ids or cluster_id. Max 50 databases per request.',
    request=BulkHealthCheckRequestSerializer,
    responses={
        200: BulkHealthCheckResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_health_check(request):
    """
    POST /api/v2/databases/bulk-health-check/

    Perform health check on multiple databases.

    Request Body:
        {
            "database_ids": ["id1", "id2", ...],
            "cluster_id": "optional-cluster-id"
        }

    Response:
        {
            "results": [
                {"database_id": "id1", "status": "ok", "response_time_ms": 100},
                {"database_id": "id2", "status": "down", "response_time_ms": 5000}
            ],
            "summary": {
                "total": 10,
                "healthy": 8,
                "degraded": 1,
                "down": 1
            }
        }
    """
    database_ids = request.data.get('database_ids', [])
    cluster_id = request.data.get('cluster_id')

    # Build queryset
    if database_ids:
        qs = Database.objects.filter(id__in=database_ids)
    elif cluster_id:
        qs = Database.objects.filter(cluster_id=cluster_id)
    else:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'Either database_ids or cluster_id is required'
            }
        }, status=400)

    # Limit batch size
    databases = list(qs[:50])  # Max 50 at once

    results = []
    summary = {'total': len(databases), 'healthy': 0, 'degraded': 0, 'down': 0}

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def check_db(db):
        # Use helper function with max 10s timeout for bulk operations
        health_status, response_time = _perform_odata_health_check(db, timeout=10)
        return {
            'database_id': str(db.id),
            'status': health_status,
            'response_time_ms': round(response_time, 2)
        }

    # Check in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_db, db): db for db in databases}
        for future in as_completed(futures, timeout=60):
            try:
                result = future.result()
                results.append(result)
                if result['status'] == 'ok':
                    summary['healthy'] += 1
                elif result['status'] == 'degraded':
                    summary['degraded'] += 1
                else:
                    summary['down'] += 1
            except Exception as e:
                db = futures[future]
                results.append({'database_id': db.id, 'status': 'error', 'error': str(e)})
                summary['down'] += 1

    return Response({
        'results': results,
        'summary': summary,
    })


@extend_schema(
    tags=['v2'],
    summary='Set database status',
    description='Set status for one or more databases (staff-only). Intended for operator control (exclude from ops, maintenance windows, etc.).',
    request=SetDatabaseStatusRequestSerializer,
    responses={
        200: SetDatabaseStatusResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def set_status(request):
    """
    POST /api/v2/databases/set-status/

    Set status for one or more databases.

    Request body:
        {
          "database_ids": ["id1", "id2"],
          "status": "maintenance",
          "reason": "Planned maintenance window"  // optional
        }
    """
    serializer = SetDatabaseStatusRequestSerializer(data=request.data or {})
    serializer.is_valid(raise_exception=True)

    database_ids = [str(x).strip() for x in serializer.validated_data['database_ids']]
    new_status = serializer.validated_data['status']
    reason = serializer.validated_data.get('reason', '')

    existing_ids = set(Database.objects.filter(id__in=database_ids).values_list('id', flat=True))
    not_found = [db_id for db_id in database_ids if db_id not in existing_ids]

    updated = Database.objects.filter(id__in=list(existing_ids)).update(status=new_status)

    log_admin_action(
        request,
        action="databases.set_status",
        outcome="success",
        target_type="database",
        target_id="bulk" if len(database_ids) > 1 else (database_ids[0] if database_ids else ""),
        metadata={
            "status": new_status,
            "reason": reason,
            "database_ids": database_ids[:200],
            "not_found": not_found[:200],
            "updated": updated,
        },
    )

    message = f"Status set to '{new_status}' for {updated} database(s)"
    if not_found:
        message += f" ({len(not_found)} not found)"

    return Response(
        {
            "updated": updated,
            "not_found": not_found,
            "status": new_status,
            "message": message,
        }
    )
