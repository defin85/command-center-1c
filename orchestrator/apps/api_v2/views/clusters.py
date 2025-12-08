"""
Cluster endpoints for API v2.

Provides action-based endpoints for cluster operations.
"""

import logging
import uuid

from django.db import IntegrityError
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.databases.models import Cluster
from apps.databases.serializers import ClusterSerializer, DatabaseSerializer
from apps.operations.models import BatchOperation

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


class ClusterListResponseSerializer(serializers.Serializer):
    """Response for list_clusters endpoint."""
    clusters = ClusterSerializer(many=True)
    count = serializers.IntegerField(help_text="Total number of clusters")


class ClusterStatisticsSerializer(serializers.Serializer):
    """Statistics for a cluster."""
    total_databases = serializers.IntegerField()
    healthy_databases = serializers.IntegerField()
    databases_by_status = serializers.DictField(child=serializers.IntegerField())


class ClusterDetailResponseSerializer(serializers.Serializer):
    """Response for get_cluster endpoint."""
    cluster = ClusterSerializer()
    databases = DatabaseSerializer(many=True)
    statistics = ClusterStatisticsSerializer()


class ClusterCreateResponseSerializer(serializers.Serializer):
    """Response for create_cluster endpoint."""
    cluster = ClusterSerializer()
    message = serializers.CharField()


class ClusterUpdateResponseSerializer(serializers.Serializer):
    """Response for update_cluster endpoint."""
    cluster = ClusterSerializer()
    message = serializers.CharField()


class ClusterDeleteResponseSerializer(serializers.Serializer):
    """Response for delete_cluster endpoint."""
    message = serializers.CharField()
    cluster_id = serializers.UUIDField()


class ClusterSyncResponseSerializer(serializers.Serializer):
    """Response for sync_cluster endpoint."""
    cluster_id = serializers.UUIDField()
    operation_id = serializers.CharField(required=False, help_text="BatchOperation ID for tracking")
    status = serializers.CharField(help_text="Sync status: syncing, success")
    task_id = serializers.CharField(required=False, help_text="Task ID (if async)")
    message = serializers.CharField()
    databases_found = serializers.IntegerField(required=False)
    created = serializers.IntegerField(required=False)
    updated = serializers.IntegerField(required=False)
    errors = serializers.ListField(child=serializers.CharField(), required=False)


class DiscoverClustersResponseSerializer(serializers.Serializer):
    """Response for discover_clusters endpoint."""
    operation_id = serializers.CharField(help_text="BatchOperation ID for tracking")
    status = serializers.CharField(help_text="Status: discovering, error")
    message = serializers.CharField()


class ClusterFiltersSerializer(serializers.Serializer):
    """Applied filters."""
    status = serializers.CharField(required=False)
    health_status = serializers.CharField(required=False)


class ClusterDatabasesResponseSerializer(serializers.Serializer):
    """Response for get_cluster_databases endpoint."""
    cluster_id = serializers.UUIDField()
    cluster_name = serializers.CharField()
    databases = DatabaseSerializer(many=True)
    count = serializers.IntegerField()
    filters = ClusterFiltersSerializer()


class ResetClusterInfoSerializer(serializers.Serializer):
    """Info about reset cluster."""
    id = serializers.UUIDField()
    name = serializers.CharField()
    old_status = serializers.CharField()


class ResetSyncStatusResponseSerializer(serializers.Serializer):
    """Response for reset_sync_status endpoint."""
    message = serializers.CharField()
    reset_count = serializers.IntegerField()
    clusters = ResetClusterInfoSerializer(many=True)


@extend_schema(
    tags=['v2'],
    summary='List all clusters',
    description='List all clusters with database counts. Supports filtering by status and RAS server.',
    parameters=[
        OpenApiParameter(name='status', type=str, required=False, description='Filter by status (active, inactive, error, maintenance)'),
        OpenApiParameter(name='ras_server', type=str, required=False, description='Filter by RAS server address'),
    ],
    responses={
        200: ClusterListResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
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


@extend_schema(
    tags=['v2'],
    summary='Get cluster details',
    description='Get detailed information about a specific cluster including databases and statistics.',
    parameters=[
        OpenApiParameter(name='cluster_id', type=str, required=True, description='Cluster UUID'),
    ],
    responses={
        200: ClusterDetailResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
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


@extend_schema(
    tags=['v2'],
    summary='Sync cluster with RAS',
    description='Trigger synchronization of a cluster with RAS. The sync runs asynchronously via Celery if available.',
    parameters=[
        OpenApiParameter(name='cluster_id', type=str, required=False, description='Cluster UUID (can also be in request body)'),
    ],
    request=None,
    responses={
        200: ClusterSyncResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
        500: ErrorResponseSerializer,
    }
)
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

    # Trigger async sync via Go Worker (or Celery fallback)
    from apps.operations.services import OperationsService

    # Create BatchOperation for tracking in Service Mesh
    operation = BatchOperation.objects.create(
        id=str(uuid.uuid4()),
        name=f"Sync cluster: {cluster.name}",
        description=f"Synchronizing infobases from RAS for cluster {cluster.name}",
        operation_type=BatchOperation.TYPE_SYNC_CLUSTER,
        target_entity=cluster.name,
        payload={'cluster_id': str(cluster_id)},
        status=BatchOperation.STATUS_QUEUED,
        total_tasks=1,
        created_by=request.user.username if request.user.is_authenticated else 'system',
    )

    try:
        result = OperationsService.enqueue_cluster_sync(
            cluster_id=str(cluster_id),
            operation_id=str(operation.id),
            created_by=request.user.username if request.user.is_authenticated else 'system'
        )

        if result.success:
            logger.info(
                "Cluster sync started via Go Worker",
                extra={
                    'cluster_id': str(cluster_id),
                    'operation_id': result.operation_id,
                }
            )

            return Response({
                'cluster_id': str(cluster_id),
                'operation_id': result.operation_id,
                'status': 'syncing',
                'message': 'Cluster synchronization started',
            })
        else:
            logger.warning(f"Go Worker enqueue failed: {result.error}")
    except Exception as e:
        logger.warning(f"Go Worker unavailable for cluster sync: {e}")

    # Fallback: synchronous execution
    logger.warning("Async workers unavailable - running sync synchronously")

    # Обновляем BatchOperation - начало синхронной обработки
    operation.status = BatchOperation.STATUS_PROCESSING
    operation.started_at = timezone.now()
    operation.save(update_fields=['status', 'started_at'])

    try:
        from apps.databases.services import ClusterService
        result = ClusterService.sync_infobases(cluster)

        # Обновляем BatchOperation - успех
        operation.status = BatchOperation.STATUS_COMPLETED
        operation.completed_tasks = 1
        operation.progress = 100
        operation.completed_at = timezone.now()
        operation.metadata = {
            'created': result['created'],
            'updated': result['updated'],
            'errors': result['errors'],
            'databases_found': result['created'] + result['updated'],
            'sync_mode': 'synchronous',
        }
        operation.save()

        return Response({
            'cluster_id': str(cluster_id),
            'operation_id': str(operation.id),
            'status': 'success',
            'message': 'Cluster synchronization completed',
            'databases_found': result['created'] + result['updated'],
            'created': result['created'],
            'updated': result['updated'],
            'errors': result['errors'],
        })
    except Exception as sync_error:
        logger.error(f"Sync failed: {sync_error}")

        # Обновляем BatchOperation - ошибка
        operation.status = BatchOperation.STATUS_FAILED
        operation.failed_tasks = 1
        operation.completed_at = timezone.now()
        operation.metadata = {'error': str(sync_error), 'sync_mode': 'synchronous'}
        operation.save()

        return Response({
            'success': False,
            'operation_id': str(operation.id),
            'error': {
                'code': 'SYNC_FAILED',
                'message': str(sync_error)
            }
        }, status=500)


@extend_schema(
    tags=['v2'],
    summary='Create a new cluster',
    description='Create a new cluster. Requires name, ras_server, and cluster_service_url.',
    request=ClusterSerializer,
    responses={
        201: ClusterCreateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        409: ErrorResponseSerializer,
    }
)
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


@extend_schema(
    tags=['v2'],
    summary='Update cluster',
    description='Update cluster information. Supports partial updates.',
    parameters=[
        OpenApiParameter(name='cluster_id', type=str, required=False, description='Cluster UUID (can also be in request body)'),
    ],
    request=ClusterSerializer,
    responses={
        200: ClusterUpdateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
        409: ErrorResponseSerializer,
    }
)
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


@extend_schema(
    tags=['v2'],
    summary='Delete cluster',
    description='Delete a cluster. Use force=true to delete cluster with existing databases.',
    parameters=[
        OpenApiParameter(name='cluster_id', type=str, required=False, description='Cluster UUID (can also be in request body)'),
    ],
    request=None,
    responses={
        200: ClusterDeleteResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
        409: ErrorResponseSerializer,
    }
)
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


@extend_schema(
    tags=['v2'],
    summary='Reset sync status',
    description='Reset sync status for stuck clusters (pending -> idle). Can reset specific cluster or all stuck clusters.',
    parameters=[
        OpenApiParameter(name='cluster_id', type=str, required=False, description='Cluster UUID (optional, resets specific cluster)'),
    ],
    request=None,
    responses={
        200: ResetSyncStatusResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reset_sync_status(request):
    """
    POST /api/v2/clusters/reset-sync-status/?cluster_id=X

    Reset sync status for a stuck cluster (pending -> idle).

    Query Parameters:
        - cluster_id: Cluster UUID (optional, resets specific cluster)

    Request Body (optional):
        {
            "cluster_id": "uuid",  // optional, reset specific cluster
            "all": false  // optional, reset all stuck clusters
        }

    Response (200):
        {
            "message": "Sync status reset successfully",
            "reset_count": 1,
            "clusters": [
                {"id": "uuid", "name": "cluster-name", "old_status": "pending"}
            ]
        }

    Errors:
        404 - Cluster not found (when cluster_id specified)
    """
    cluster_id = request.query_params.get('cluster_id') or request.data.get('cluster_id')
    reset_all = request.data.get('all', False)

    reset_clusters = []

    if cluster_id:
        # Reset specific cluster
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

        old_status = cluster.last_sync_status
        if old_status != 'pending':
            cluster.last_sync_status = 'pending'
            cluster.last_sync_error = ''
            cluster.save(update_fields=['last_sync_status', 'last_sync_error'])
            reset_clusters.append({
                'id': str(cluster.id),
                'name': cluster.name,
                'old_status': old_status
            })
            logger.info(f"Reset sync status for cluster {cluster.name}: {old_status} -> pending")

    elif reset_all:
        # Reset all non-pending clusters
        clusters = Cluster.objects.exclude(last_sync_status='pending')
        for cluster in clusters:
            old_status = cluster.last_sync_status
            cluster.last_sync_status = 'pending'
            cluster.last_sync_error = ''
            cluster.save(update_fields=['last_sync_status', 'last_sync_error'])
            reset_clusters.append({
                'id': str(cluster.id),
                'name': cluster.name,
                'old_status': old_status
            })
            logger.info(f"Reset sync status for cluster {cluster.name}: {old_status} -> pending")

    else:
        # Reset stuck clusters (failed or pending for too long) to success
        stuck_clusters = Cluster.objects.filter(last_sync_status__in=['pending', 'failed'])
        for cluster in stuck_clusters:
            old_status = cluster.last_sync_status
            cluster.last_sync_status = 'success'
            cluster.last_sync_error = ''
            cluster.save(update_fields=['last_sync_status', 'last_sync_error'])
            reset_clusters.append({
                'id': str(cluster.id),
                'name': cluster.name,
                'old_status': old_status
            })
            logger.info(f"Reset sync status for cluster {cluster.name}: {old_status} -> success")

    return Response({
        'message': 'Sync status reset successfully' if reset_clusters else 'No clusters to reset',
        'reset_count': len(reset_clusters),
        'clusters': reset_clusters
    })


@extend_schema(
    tags=['v2'],
    summary='Get cluster databases',
    description='Get all databases for a specific cluster with optional filtering by status.',
    parameters=[
        OpenApiParameter(name='cluster_id', type=str, required=True, description='Cluster UUID'),
        OpenApiParameter(name='status', type=str, required=False, description='Filter by database status'),
        OpenApiParameter(name='health_status', type=str, required=False, description='Filter by health check status'),
    ],
    responses={
        200: ClusterDatabasesResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
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


@extend_schema(
    tags=['v2'],
    summary='Discover clusters on RAS server',
    description='Trigger cluster discovery on a RAS server. Creates or updates Cluster records for all found clusters.',
    request=None,
    responses={
        200: DiscoverClustersResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        409: ErrorResponseSerializer,
        500: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def discover_clusters(request):
    """
    POST /api/v2/clusters/discover-clusters/

    Trigger cluster discovery on a RAS server.

    Request Body:
        {
            "ras_server": "localhost:1545",
            "cluster_user": "admin",  // optional
            "cluster_pwd": "password"  // optional
        }

    Response (200):
        {
            "operation_id": "uuid",
            "status": "discovering",
            "message": "Cluster discovery started"
        }

    Errors:
        400 - Missing ras_server
        409 - Discovery already in progress
        500 - Failed to enqueue operation
    """
    # Get ras_server from body
    ras_server = request.data.get('ras_server')

    if not ras_server:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'ras_server is required'
            }
        }, status=400)

    # Optional credentials
    cluster_user = request.data.get('cluster_user', '')
    cluster_pwd = request.data.get('cluster_pwd', '')

    # Create BatchOperation for tracking
    operation = BatchOperation.objects.create(
        id=str(uuid.uuid4()),
        name=f"Discover clusters: {ras_server}",
        description=f"Discovering clusters on RAS server {ras_server}",
        operation_type=BatchOperation.TYPE_DISCOVER_CLUSTERS,
        target_entity=ras_server,
        payload={
            'ras_server': ras_server,
            'cluster_user': cluster_user,
        },
        status=BatchOperation.STATUS_QUEUED,
        total_tasks=1,
        created_by=request.user.username if request.user.is_authenticated else 'system',
    )

    # Enqueue to Go Worker
    from apps.operations.services import OperationsService

    result = OperationsService.enqueue_discover_clusters(
        ras_server=ras_server,
        operation_id=str(operation.id),
        cluster_user=cluster_user,
        cluster_pwd=cluster_pwd,
        created_by=request.user.username if request.user.is_authenticated else 'system'
    )

    if result.success:
        logger.info(
            "Cluster discovery started",
            extra={
                'ras_server': ras_server,
                'operation_id': result.operation_id,
            }
        )

        return Response({
            'operation_id': result.operation_id,
            'status': 'discovering',
            'message': 'Cluster discovery started',
        })

    else:
        # Update BatchOperation status on failure
        operation.status = BatchOperation.STATUS_FAILED
        operation.metadata = {'error': result.error}
        operation.save(update_fields=['status', 'metadata', 'updated_at'])

        # Check if duplicate
        if result.status == 'duplicate':
            return Response({
                'success': False,
                'error': {
                    'code': 'DISCOVERY_IN_PROGRESS',
                    'message': result.error
                }
            }, status=409)

        return Response({
            'success': False,
            'error': {
                'code': 'ENQUEUE_FAILED',
                'message': result.error
            }
        }, status=500)
