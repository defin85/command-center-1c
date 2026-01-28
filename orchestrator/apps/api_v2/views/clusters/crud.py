"""Cluster CRUD endpoints."""

from __future__ import annotations

from .common import *  # noqa: F403
from .common import _permission_denied

@extend_schema(
    tags=['v2'],
    summary='Create a new cluster',
    description='Create a new cluster. Requires name, ras_host, ras_port, rmngr_host, rmngr_port, and cluster_service_url.',
    request=ClusterSerializer,
    responses={
        201: ClusterCreateResponseSerializer,
        400: ClusterErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        409: ClusterErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_cluster(request):
    """
    POST /api/v2/clusters/create-cluster/

    Create a new cluster.

    Request Body:
        {
            "name": "cluster-name",
            "ras_host": "localhost",
            "ras_port": 1545,
            "rmngr_host": "localhost",
            "rmngr_port": 1541,
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
        409 - Cluster with same ras_host/ras_port + name already exists
    """
    # Validate required fields
    name = request.data.get('name')
    ras_host = request.data.get('ras_host')
    ras_port = request.data.get('ras_port')
    rmngr_host = request.data.get('rmngr_host')
    rmngr_port = request.data.get('rmngr_port')
    cluster_service_url = request.data.get('cluster_service_url')

    if not name:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'name is required'
            }
        }, status=400)

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
    if not rmngr_host:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'rmngr_host is required'
            }
        }, status=400)
    if not rmngr_port:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'rmngr_port is required'
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
                'message': f'Cluster with ras_host={ras_host} and ras_port={ras_port} and name={name} already exists'
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
        400: ClusterErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ClusterErrorResponseSerializer,
        409: ClusterErrorResponseSerializer,
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

    if not request.user.has_perm(perms.PERM_DATABASES_MANAGE_CLUSTER, cluster):
        return _permission_denied("You do not have permission to update this cluster.")

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
                'message': 'Cluster with this ras_host/ras_port and name already exists'
            }
        }, status=409)


@extend_schema(
    tags=['v2'],
    summary='Update cluster credentials',
    description='Set or reset cluster admin credentials.',
    request=ClusterCredentialsUpdateRequestSerializer,
    responses={
        200: ClusterCredentialsUpdateResponseSerializer,
        400: ClusterErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ClusterErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_cluster_credentials(request):
    """
    POST /api/v2/clusters/update-credentials/

    Update or reset cluster credentials.

    Request Body:
        {
            "cluster_id": "uuid",
            "username": "admin",        // optional
            "password": "secret",       // optional
            "reset": false              // optional, default: false
        }

    Response (200):
        {
            "cluster": {...},
            "message": "Cluster credentials updated"
        }
    """
    serializer = ClusterCredentialsUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'Invalid credentials payload',
                'details': serializer.errors
            }
        }, status=400)

    data = serializer.validated_data
    cluster_id = data['cluster_id']

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

    if not request.user.has_perm(perms.PERM_DATABASES_MANAGE_CLUSTER, cluster):
        return _permission_denied("You do not have permission to update cluster credentials.")

    reset = data.get('reset', False)
    updated_fields = []

    if reset:
        cluster.cluster_user = ''
        cluster.cluster_pwd = ''
        updated_fields.extend(['cluster_user', 'cluster_pwd'])
    else:
        username_provided = 'username' in data
        password_provided = 'password' in data

        if not username_provided and not password_provided:
            return Response({
                'success': False,
                'error': {
                    'code': 'MISSING_PARAMETER',
                    'message': 'username or password is required unless reset=true'
                }
            }, status=400)

        if username_provided:
            if data['username'] == '':
                return Response({
                    'success': False,
                    'error': {
                        'code': 'INVALID_PARAMETER',
                        'message': 'username cannot be empty (use reset=true to clear)'
                    }
                }, status=400)
            cluster.cluster_user = data['username']
            updated_fields.append('cluster_user')

        if password_provided:
            if data['password'] == '':
                return Response({
                    'success': False,
                    'error': {
                        'code': 'INVALID_PARAMETER',
                        'message': 'password cannot be empty (use reset=true to clear)'
                    }
                }, status=400)
            cluster.cluster_pwd = data['password']
            updated_fields.append('cluster_pwd')

    cluster.save(update_fields=[*updated_fields, 'updated_at'])

    log_admin_action(
        request,
        action='cluster.credentials.update',
        outcome='success',
        target_type='cluster',
        target_id=str(cluster.id),
        metadata={
            'reset': reset,
            'updated_fields': updated_fields,
            'configured': bool(cluster.cluster_pwd),
        },
    )

    return Response({
        'cluster': ClusterSerializer(cluster).data,
        'message': 'Cluster credentials updated'
    })


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
        400: ClusterErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ClusterErrorResponseSerializer,
        409: ClusterErrorResponseSerializer,
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

    if not request.user.has_perm(perms.PERM_DATABASES_ADMIN_CLUSTER, cluster):
        return _permission_denied("You do not have permission to delete this cluster.")

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
    description='Reset sync status for stuck clusters (pending -> failed). Can reset a specific cluster or all stuck clusters.',
    parameters=[
        OpenApiParameter(name='cluster_id', type=str, required=False, description='Cluster UUID (optional, resets specific cluster)'),
    ],
    request=ResetSyncStatusRequestSerializer,
    responses={
        200: ResetSyncStatusResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
        404: ClusterErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def reset_sync_status(request):
    """
    POST /api/v2/clusters/reset-sync-status/?cluster_id=X

    Reset sync status for a stuck cluster (pending -> failed).

    Query Parameters:
        - cluster_id: Cluster UUID (optional, resets specific cluster)

    Request Body (optional):
        { "all": false }

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
    request_serializer = ResetSyncStatusRequestSerializer(data=request.data or {})
    request_serializer.is_valid(raise_exception=True)

    cluster_id = request.query_params.get('cluster_id') or request_serializer.validated_data.get('cluster_id')
    reset_all = bool(request_serializer.validated_data.get('all', False))

    reset_clusters = []

    if cluster_id:
        # Reset specific cluster
        try:
            cluster = Cluster.objects.get(id=cluster_id)
        except Cluster.DoesNotExist:
            log_admin_action(
                request,
                action="clusters.reset_sync_status",
                outcome="error",
                target_type="cluster",
                target_id=str(cluster_id),
                metadata={"mode": "single"},
                error_message="CLUSTER_NOT_FOUND",
            )
            return Response({
                'success': False,
                'error': {
                    'code': 'CLUSTER_NOT_FOUND',
                    'message': 'Cluster not found'
                }
            }, status=404)

        old_status = cluster.last_sync_status
        if old_status == 'pending':
            cluster.last_sync_status = 'failed'
            cluster.last_sync_error = ''
            cluster.save(update_fields=['last_sync_status', 'last_sync_error'])
            reset_clusters.append({
                'id': str(cluster.id),
                'name': cluster.name,
                'old_status': old_status
            })
            logger.info(f"Reset sync status for cluster {cluster.name}: {old_status} -> failed")

    else:
        # Reset stuck clusters (pending) to failed (idle).
        # Note: reset_all is kept for backward compatibility with older clients.
        stuck_clusters = Cluster.objects.filter(last_sync_status='pending')
        for cluster in stuck_clusters:
            old_status = cluster.last_sync_status
            cluster.last_sync_status = 'failed'
            cluster.last_sync_error = ''
            cluster.save(update_fields=['last_sync_status', 'last_sync_error'])
            reset_clusters.append({
                'id': str(cluster.id),
                'name': cluster.name,
                'old_status': old_status
            })
            logger.info(f"Reset sync status for cluster {cluster.name}: {old_status} -> failed")

    log_admin_action(
        request,
        action="clusters.reset_sync_status",
        outcome="success" if reset_clusters else "noop",
        target_type="cluster",
        target_id=str(cluster_id) if cluster_id else "",
        metadata={
            "mode": "single" if cluster_id else ("all" if reset_all else "stuck"),
            "reset_count": len(reset_clusters),
            "clusters": [c["id"] for c in reset_clusters[:50]],
        },
    )

    return Response({
        'message': 'Sync status reset successfully' if reset_clusters else 'No clusters to reset',
        'reset_count': len(reset_clusters),
        'clusters': reset_clusters
    })


