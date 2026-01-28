"""Cluster discovery endpoints."""

from __future__ import annotations

from .common import *  # noqa: F403
from .common import _is_staff, _permission_denied

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
        400: ClusterErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ClusterErrorResponseSerializer,
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

    if not request.user.has_perm(perms.PERM_DATABASES_VIEW_CLUSTER, cluster):
        return _permission_denied("You do not have permission to access this cluster.")

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

    if not _is_staff(request.user):
        databases_qs = PermissionService.filter_accessible_databases(
            request.user,
            databases_qs,
            PermissionLevel.VIEW,
        )

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
    request=DiscoverClustersRequestSerializer,
    responses={
        200: DiscoverClustersResponseSerializer,
        400: ClusterErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        409: ClusterErrorResponseSerializer,
        500: ClusterErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def discover_clusters(request):
    """
    POST /api/v2/clusters/discover-clusters/

    Trigger cluster discovery on a RAS server.

    Request Body:
        {
            "ras_host": "localhost",
            "ras_port": 1545,
            "cluster_service_url": "http://localhost:8188",  // optional, for future use
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
        400 - Missing ras_host/ras_port
        409 - Discovery already in progress
        500 - Failed to enqueue operation
    """
    # Get RAS host/port from body
    ras_host = request.data.get('ras_host')
    ras_port = request.data.get('ras_port')

    if not ras_host:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'ras_host is required'
            }
        }, status=400)
    if not ras_port:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'ras_port is required'
            }
        }, status=400)

    ras_server = f"{ras_host}:{ras_port}"

    # Optional fields
    cluster_service_url = request.data.get('cluster_service_url', '')  # For future Worker use
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
            'cluster_service_url': cluster_service_url,
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
