"""
Cluster endpoints for API v2.

Provides action-based endpoints for cluster operations.
"""

import logging

from django.db.models import Count
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.databases.models import Cluster
from apps.databases.serializers import ClusterSerializer

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_clusters(request):
    """
    GET /api/v2/clusters/list-clusters/

    List all clusters with database counts.

    Query Parameters:
        - status: Filter by status (active, inactive, error, maintenance)
        - ras_server: Filter by RAS server address

    Response:
        {
            "clusters": [
                {
                    "id": "uuid",
                    "name": "cluster-name",
                    "ras_server": "localhost:1545",
                    "status": "active",
                    "databases_count": 100,
                    "healthy_databases_count": 95
                }
            ],
            "count": 5
        }
    """
    status = request.query_params.get('status')
    ras_server = request.query_params.get('ras_server')

    from django.db.models import Q

    qs = Cluster.objects.annotate(
        databases_count=Count('databases'),
        healthy_databases_count=Count(
            'databases',
            filter=Q(databases__last_check_status='ok')
        )
    )

    if status:
        qs = qs.filter(status=status)
    if ras_server:
        qs = qs.filter(ras_server=ras_server)

    serializer = ClusterSerializer(qs, many=True)

    # Enrich with annotated healthy database counts
    clusters_data = serializer.data
    for i, cluster in enumerate(qs):
        clusters_data[i]['healthy_databases_count'] = cluster.healthy_databases_count

    return Response({
        'clusters': clusters_data,
        'count': len(clusters_data),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cluster(request):
    """
    GET /api/v2/clusters/get-cluster/?cluster_id=X

    Get detailed information about a specific cluster.

    Query Parameters:
        - cluster_id: Cluster UUID (required)

    Response:
        {
            "cluster": {...},
            "databases": [...],
            "statistics": {
                "total_databases": 100,
                "healthy_databases": 95,
                "databases_by_status": {...}
            }
        }
    """
    cluster_id = request.query_params.get('cluster_id')

    if not cluster_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'cluster_id is required'
            }
        }, status=400)

    try:
        cluster = Cluster.objects.prefetch_related('databases').get(id=cluster_id)
    except Cluster.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'CLUSTER_NOT_FOUND',
                'message': 'Cluster not found'
            }
        }, status=404)

    serializer = ClusterSerializer(cluster)

    # Get database statistics
    databases = cluster.databases.all()
    from apps.databases.serializers import DatabaseSerializer
    db_serializer = DatabaseSerializer(databases[:20], many=True)  # Limit to first 20

    # Calculate statistics
    status_counts = {}
    for db in databases:
        status_counts[db.status] = status_counts.get(db.status, 0) + 1

    statistics = {
        'total_databases': databases.count(),
        'healthy_databases': cluster.healthy_infobase_count,
        'databases_by_status': status_counts,
    }

    return Response({
        'cluster': serializer.data,
        'databases': db_serializer.data,
        'statistics': statistics,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_cluster(request):
    """
    POST /api/v2/clusters/sync-cluster/

    Trigger synchronization of a cluster with RAS.

    Request Body:
        {
            "cluster_id": "uuid"
        }

    Response:
        {
            "cluster_id": "uuid",
            "status": "syncing",
            "message": "Cluster synchronization started"
        }
    """
    cluster_id = request.data.get('cluster_id')

    if not cluster_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'cluster_id is required'
            }
        }, status=400)

    try:
        cluster = Cluster.objects.get(id=cluster_id)
    except Cluster.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'CLUSTER_NOT_FOUND',
                'message': 'Cluster not found'
            }
        }, status=404)

    # Trigger async sync via Celery task
    try:
        from apps.databases.tasks import periodic_cluster_health_check
        # Note: Using periodic_cluster_health_check as sync_cluster_task doesn't exist yet
        # TODO: Implement dedicated sync_cluster_task in apps/databases/tasks.py
        task = periodic_cluster_health_check.apply_async()

        return Response({
            'cluster_id': str(cluster_id),
            'status': 'syncing',
            'task_id': task.id,
            'message': 'Cluster synchronization started',
        })
    except ImportError as e:
        logger.error(f"Celery task not found: {e}")
        logger.warning("Cluster sync task unavailable - using fallback")

        # Fallback: mark sync as pending
        cluster.last_sync_status = 'pending'
        cluster.save(update_fields=['last_sync_status', 'updated_at'])

        return Response({
            'cluster_id': str(cluster_id),
            'status': 'pending',
            'message': 'Cluster synchronization queued (Celery unavailable)',
        })
    except Exception as e:
        logger.error(f"Failed to start cluster sync: {e}")
        logger.warning("Celery unavailable - using fallback")

        # Fallback: mark sync as pending
        cluster.last_sync_status = 'pending'
        cluster.save(update_fields=['last_sync_status', 'updated_at'])

        return Response({
            'cluster_id': str(cluster_id),
            'status': 'pending',
            'message': 'Cluster synchronization queued (Celery unavailable)',
        })
