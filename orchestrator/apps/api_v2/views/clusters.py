"""
Cluster endpoints for API v2.

Provides action-based endpoints for cluster operations.
"""

import logging

from django.db import IntegrityError
from django.db.models import Count, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.databases.models import Cluster
from apps.databases.serializers import ClusterSerializer, DatabaseSerializer

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
    POST /api/v2/clusters/sync-cluster/?cluster_id=X

    Trigger synchronization of a cluster with RAS.

    Query Parameters:
        - cluster_id: Cluster UUID (required, can also be in body)

    Response:
        {
            "cluster_id": "uuid",
            "status": "syncing",
            "message": "Cluster synchronization started"
        }
    """
    # Support both query params (frontend) and body (API clients)
    cluster_id = request.query_params.get('cluster_id')
    if not cluster_id and request.data:
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
        from apps.databases.tasks import sync_cluster_task

        # Запускаем задачу синхронизации с передачей cluster_id
        task = sync_cluster_task.apply_async(args=[str(cluster_id)])

        return Response({
            'cluster_id': str(cluster_id),
            'status': 'syncing',
            'task_id': task.id,
            'message': 'Cluster synchronization started',
        })
    except ImportError as e:
        logger.error(f"Celery task not found: {e}")
        # Fallback: выполняем синхронизацию синхронно (как в админке)
        logger.warning("Celery unavailable - running sync synchronously")

        try:
            from apps.databases.services import ClusterService
            result = ClusterService.sync_infobases(cluster)

            return Response({
                'cluster_id': str(cluster_id),
                'status': 'success',
                'message': 'Cluster synchronization completed',
                'databases_found': result['created'] + result['updated'],
                'created': result['created'],
                'updated': result['updated'],
                'errors': result['errors'],
            })
        except Exception as sync_error:
            logger.error(f"Sync failed: {sync_error}")
            return Response({
                'success': False,
                'error': {
                    'code': 'SYNC_FAILED',
                    'message': str(sync_error)
                }
            }, status=500)

    except Exception as e:
        logger.error(f"Failed to start cluster sync: {e}")
        # Fallback: выполняем синхронизацию синхронно
        logger.warning("Celery error - running sync synchronously")

        try:
            from apps.databases.services import ClusterService
            result = ClusterService.sync_infobases(cluster)

            return Response({
                'cluster_id': str(cluster_id),
                'status': 'success',
                'message': 'Cluster synchronization completed',
                'databases_found': result['created'] + result['updated'],
                'created': result['created'],
                'updated': result['updated'],
                'errors': result['errors'],
            })
        except Exception as sync_error:
            logger.error(f"Sync failed: {sync_error}")
            return Response({
                'success': False,
                'error': {
                    'code': 'SYNC_FAILED',
                    'message': str(sync_error)
                }
            }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_cluster(request):
    """
    POST /api/v2/clusters/create-cluster/

    Create a new cluster.

    Request Body:
        {
            "name": "cluster-name",
            "ras_server": "localhost:1545",
            "cluster_service_url": "http://localhost:8087",
            "cluster_user": "admin",  // optional
            "cluster_pwd": "password",  // optional
            "description": "Optional description",  // optional
            "status": "active",  // optional, default: active
            "metadata": {}  // optional
        }

    Response (201):
        {
            "cluster": {...},
            "message": "Cluster created successfully"
        }

    Errors:
        400 - Missing required fields or validation error
        409 - Cluster with same ras_server + name already exists
    """
    # Validate required fields
    name = request.data.get('name')
    ras_server = request.data.get('ras_server')
    cluster_service_url = request.data.get('cluster_service_url')

    if not name:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'name is required'
            }
        }, status=400)

    if not ras_server:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'ras_server is required'
            }
        }, status=400)

    if not cluster_service_url:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'cluster_service_url is required'
            }
        }, status=400)

    # Create cluster using serializer
    serializer = ClusterSerializer(data=request.data)

    if not serializer.is_valid():
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'Invalid cluster data',
                'details': serializer.errors
            }
        }, status=400)

    try:
        cluster = serializer.save()
        logger.info(f"Cluster created: {cluster.name} ({cluster.id})")

        return Response({
            'cluster': ClusterSerializer(cluster).data,
            'message': 'Cluster created successfully'
        }, status=201)

    except IntegrityError as e:
        logger.warning(f"Cluster creation failed - duplicate: {e}")
        return Response({
            'success': False,
            'error': {
                'code': 'DUPLICATE_CLUSTER',
                'message': f'Cluster with ras_server={ras_server} and name={name} already exists'
            }
        }, status=409)


@api_view(['PUT', 'POST'])
@permission_classes([IsAuthenticated])
def update_cluster(request):
    """
    PUT /api/v2/clusters/update-cluster/?cluster_id=X
    POST /api/v2/clusters/update-cluster/  (cluster_id in body)

    Update cluster information.

    Query Parameters:
        - cluster_id: Cluster UUID (can be in query or body)

    Request Body:
        {
            "cluster_id": "uuid",  // optional if in query
            "name": "new-name",  // optional
            "description": "new description",  // optional
            "status": "maintenance",  // optional
            "cluster_user": "admin",  // optional
            "cluster_pwd": "password",  // optional
            "metadata": {}  // optional
        }

    Response (200):
        {
            "cluster": {...},
            "message": "Cluster updated successfully"
        }

    Errors:
        400 - Missing cluster_id
        404 - Cluster not found
    """
    # Get cluster_id from query params or body
    cluster_id = request.query_params.get('cluster_id') or request.data.get('cluster_id')

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

    # Partial update
    serializer = ClusterSerializer(cluster, data=request.data, partial=True)

    if not serializer.is_valid():
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'Invalid cluster data',
                'details': serializer.errors
            }
        }, status=400)

    try:
        cluster = serializer.save()
        logger.info(f"Cluster updated: {cluster.name} ({cluster.id})")

        return Response({
            'cluster': ClusterSerializer(cluster).data,
            'message': 'Cluster updated successfully'
        })

    except IntegrityError as e:
        logger.warning(f"Cluster update failed - duplicate: {e}")
        return Response({
            'success': False,
            'error': {
                'code': 'DUPLICATE_CLUSTER',
                'message': 'Cluster with this ras_server and name already exists'
            }
        }, status=409)


@api_view(['DELETE', 'POST'])
@permission_classes([IsAuthenticated])
def delete_cluster(request):
    """
    DELETE /api/v2/clusters/delete-cluster/?cluster_id=X
    POST /api/v2/clusters/delete-cluster/  (cluster_id in body)

    Delete a cluster.

    Query Parameters:
        - cluster_id: Cluster UUID (can be in query or body)

    Request Body (optional):
        {
            "cluster_id": "uuid",  // optional if in query
            "force": false  // optional, default: false
        }

    Response (200):
        {
            "message": "Cluster deleted successfully",
            "cluster_id": "uuid"
        }

    Errors:
        400 - Missing cluster_id
        404 - Cluster not found
        409 - Cluster has databases and force=false
    """
    # Get cluster_id from query params or body
    cluster_id = request.query_params.get('cluster_id') or request.data.get('cluster_id')

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

    # Check if cluster has databases
    databases_count = cluster.databases.count()
    force = request.data.get('force', False)

    if databases_count > 0 and not force:
        return Response({
            'success': False,
            'error': {
                'code': 'CLUSTER_HAS_DATABASES',
                'message': f'Cluster has {databases_count} database(s). Use force=true to delete anyway.',
                'databases_count': databases_count
            }
        }, status=409)

    cluster_name = cluster.name
    cluster.delete()

    logger.info(f"Cluster deleted: {cluster_name} ({cluster_id}), force={force}")

    return Response({
        'message': 'Cluster deleted successfully',
        'cluster_id': str(cluster_id)
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cluster_databases(request):
    """
    GET /api/v2/clusters/get-cluster-databases/?cluster_id=X&status=active

    Get all databases for a specific cluster with optional filtering.

    Query Parameters:
        - cluster_id: Cluster UUID (required)
        - status: Filter by database status (optional)
        - health_status: Filter by health check status (optional)

    Response (200):
        {
            "cluster_id": "uuid",
            "cluster_name": "cluster-name",
            "databases": [...],
            "count": 100,
            "filters": {
                "status": "active",
                "health_status": "ok"
            }
        }

    Errors:
        400 - Missing cluster_id
        404 - Cluster not found
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
        cluster = Cluster.objects.get(id=cluster_id)
    except Cluster.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'CLUSTER_NOT_FOUND',
                'message': 'Cluster not found'
            }
        }, status=404)

    # Get databases with optional filtering
    databases_qs = cluster.databases.all()

    status_filter = request.query_params.get('status')
    health_status_filter = request.query_params.get('health_status')

    filters_applied = {}

    if status_filter:
        databases_qs = databases_qs.filter(status=status_filter)
        filters_applied['status'] = status_filter

    if health_status_filter:
        databases_qs = databases_qs.filter(last_check_status=health_status_filter)
        filters_applied['health_status'] = health_status_filter

    # Serialize databases
    serializer = DatabaseSerializer(databases_qs, many=True)

    return Response({
        'cluster_id': str(cluster_id),
        'cluster_name': cluster.name,
        'databases': serializer.data,
        'count': len(serializer.data),
        'filters': filters_applied
    })
