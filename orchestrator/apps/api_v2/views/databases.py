"""
Database endpoints for API v2.

Provides action-based endpoints for database operations.
"""

import logging

from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.databases.models import Database
from apps.databases.serializers import DatabaseSerializer

logger = logging.getLogger(__name__)


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
        from apps.databases.serializers import ClusterSerializer
        cluster_info = ClusterSerializer(db.cluster).data

    return Response({
        'database': serializer.data,
        'cluster': cluster_info,
    })


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
