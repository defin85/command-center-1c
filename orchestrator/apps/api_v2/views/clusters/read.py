"""Cluster read/sync endpoints."""

from __future__ import annotations

from .common import *  # noqa: F403
from .common import _apply_filters, _is_staff, _parse_filters, _parse_sort, _permission_denied

@extend_schema(
    tags=['v2'],
    summary='List all clusters',
    description='List all clusters with database counts. Supports filtering by status and RAS server.',
    parameters=[
        OpenApiParameter(name='status', type=str, required=False, description='Filter by status (active, inactive, error, maintenance)'),
        OpenApiParameter(name='ras_server', type=str, required=False, description='Filter by RAS server address'),
        OpenApiParameter(name='search', type=str, required=False, description='Search by name or RAS server'),
        OpenApiParameter(name='filters', type=str, required=False, description='JSON object with filter conditions'),
        OpenApiParameter(name='sort', type=str, required=False, description='JSON object with sort configuration'),
        OpenApiParameter(name='limit', type=int, required=False, description='Maximum results (default: 100, max: 1000)'),
        OpenApiParameter(name='offset', type=int, required=False, description='Pagination offset (default: 0)'),
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
        - search: Search by name or RAS server
        - filters: JSON object with filter conditions
        - sort: JSON object with sort configuration
        - limit: Maximum results (default: 100)
        - offset: Pagination offset (default: 0)

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
    if not request.user.has_perm(perms.PERM_DATABASES_VIEW_CLUSTER):
        return _permission_denied("You do not have permission to view clusters.")

    status = request.query_params.get('status')
    ras_server = request.query_params.get('ras_server')
    search = request.query_params.get('search')
    raw_filters = request.query_params.get('filters')
    raw_sort = request.query_params.get('sort')

    try:
        limit = int(request.query_params.get('limit', 100))
        limit = max(1, min(limit, 1000))
    except (ValueError, TypeError):
        limit = 100

    try:
        offset = int(request.query_params.get('offset', 0))
        offset = max(0, offset)
    except (ValueError, TypeError):
        offset = 0

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
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(ras_server__icontains=search))

    filters_payload, filters_error = _parse_filters(raw_filters)
    if filters_error:
        return Response(
            {"success": False, "error": filters_error},
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    if filters_payload:
        qs, apply_error = _apply_filters(qs, filters_payload)
        if apply_error:
            return Response(
                {"success": False, "error": apply_error},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

    sort_payload, sort_error = _parse_sort(raw_sort)
    if sort_error:
        return Response(
            {"success": False, "error": sort_error},
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    if sort_payload:
        sort_key = sort_payload.get('key')
        sort_order = sort_payload.get('order', 'asc')
        if sort_key not in CLUSTER_SORT_FIELDS:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "UNKNOWN_SORT",
                        "message": f"Unknown sort key: {sort_key}",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        order_field = CLUSTER_SORT_FIELDS[sort_key]
        if sort_order == 'desc':
            order_field = f"-{order_field}"
        qs = qs.order_by(order_field)

    if not _is_staff(request.user):
        qs = PermissionService.filter_accessible_clusters(
            request.user,
            qs,
            PermissionLevel.VIEW,
        )

    total = qs.count()
    qs = qs[offset:offset + limit]

    serializer = ClusterSerializer(qs, many=True)

    # Enrich with annotated healthy database counts
    clusters_data = serializer.data
    for i, cluster in enumerate(qs):
        clusters_data[i]['healthy_databases_count'] = cluster.healthy_databases_count

    return Response({
        'clusters': clusters_data,
        'count': len(clusters_data),
        'total': total,
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
        400: ClusterErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ClusterErrorResponseSerializer,
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

    if not request.user.has_perm(perms.PERM_DATABASES_VIEW_CLUSTER, cluster):
        return _permission_denied("You do not have permission to access this cluster.")

    serializer = ClusterSerializer(cluster)

    # Get database statistics
    databases = cluster.databases.all()
    if not _is_staff(request.user):
        databases = PermissionService.filter_accessible_databases(
            request.user,
            databases,
            PermissionLevel.VIEW,
        )
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
        400: ClusterErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ClusterErrorResponseSerializer,
        500: ClusterErrorResponseSerializer,
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

    if not request.user.has_perm(perms.PERM_DATABASES_OPERATE_CLUSTER, cluster):
        return _permission_denied("You do not have permission to sync this cluster.")

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

        # Enqueue completed but failed (no exception) - return a proper HTTP response.
        logger.warning(f"Go Worker enqueue failed: {result.error}")

        operation.status = BatchOperation.STATUS_FAILED
        operation.failed_tasks = 1
        operation.completed_at = timezone.now()
        operation.metadata = {'error': result.error, 'sync_mode': 'enqueue_failed', 'enqueue_status': result.status}
        operation.save(update_fields=['status', 'failed_tasks', 'completed_at', 'metadata', 'updated_at'])

        if result.status == 'duplicate':
            return Response({
                'success': False,
                'operation_id': str(operation.id),
                'error': {
                    'code': 'SYNC_IN_PROGRESS',
                    'message': result.error or 'Cluster sync already in progress',
                }
            }, status=409)

        return Response({
            'success': False,
            'operation_id': str(operation.id),
            'error': {
                'code': 'ENQUEUE_FAILED',
                'message': result.error or 'Failed to enqueue sync_cluster operation',
            }
        }, status=500)
    except Exception as e:
        logger.warning(f"Go Worker unavailable for cluster sync: {e}")

        operation.status = BatchOperation.STATUS_FAILED
        operation.failed_tasks = 1
        operation.completed_at = timezone.now()
        operation.metadata = {'error': str(e), 'sync_mode': 'worker_unavailable'}
        operation.save(update_fields=['status', 'failed_tasks', 'completed_at', 'metadata', 'updated_at'])

        return Response({
            'success': False,
            'operation_id': str(operation.id),
            'error': {
                'code': 'WORKER_UNAVAILABLE',
                'message': 'Go Worker unavailable for cluster sync'
            }
        }, status=503)


