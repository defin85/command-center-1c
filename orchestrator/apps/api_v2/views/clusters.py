"""
Cluster endpoints for API v2.

Provides action-based endpoints for cluster operations.
"""

import json
import logging
import uuid
from datetime import date

from django.db import IntegrityError
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.core import permission_codes as perms
from apps.databases.models import Cluster, PermissionLevel
from apps.databases.serializers import ClusterSerializer, DatabaseSerializer
from apps.databases.services import PermissionService
from apps.operations.models import BatchOperation
from apps.operations.services.admin_action_audit import log_admin_action

logger = logging.getLogger(__name__)

CLUSTER_FILTER_FIELDS = {
    "name": {"field": "name", "type": "text"},
    "ras_server": {"field": "ras_server", "type": "text"},
    "status": {"field": "status", "type": "enum"},
    "databases_count": {"field": "databases_count", "type": "number"},
    "last_sync": {"field": "last_sync", "type": "datetime"},
    "credentials": {"field": "cluster_pwd", "type": "credentials"},
}

CLUSTER_SORT_FIELDS = {
    "name": "name",
    "ras_server": "ras_server",
    "status": "status",
    "databases_count": "databases_count",
    "last_sync": "last_sync",
}


def _is_staff(user) -> bool:
    return bool(user and user.is_staff)


def _permission_denied(message: str):
    return Response({
        "success": False,
        "error": {
            "code": "PERMISSION_DENIED",
            "message": message,
        },
    }, status=403)


def _parse_filters(raw_filters: str | None) -> tuple[dict, dict | None]:
    if not raw_filters:
        return {}, None
    try:
        payload = json.loads(raw_filters)
    except json.JSONDecodeError:
        return {}, {
            "code": "INVALID_FILTERS",
            "message": "filters must be valid JSON object",
        }
    if not isinstance(payload, dict):
        return {}, {
            "code": "INVALID_FILTERS",
            "message": "filters must be a JSON object",
        }
    return payload, None


def _parse_sort(raw_sort: str | None) -> tuple[dict | None, dict | None]:
    if not raw_sort:
        return None, None
    try:
        payload = json.loads(raw_sort)
    except json.JSONDecodeError:
        return None, {
            "code": "INVALID_SORT",
            "message": "sort must be valid JSON object",
        }
    if not isinstance(payload, dict):
        return None, {
            "code": "INVALID_SORT",
            "message": "sort must be a JSON object",
        }
    return payload, None


def _apply_text_filter(qs, field: str, op: str, value: str):
    if op == "contains":
        return qs.filter(**{f"{field}__icontains": value})
    if op == "eq":
        return qs.filter(**{field: value})
    return qs


def _apply_number_filter(qs, field: str, op: str, value: int | float):
    if op == "eq":
        return qs.filter(**{field: value})
    if op == "gt":
        return qs.filter(**{f"{field}__gt": value})
    if op == "gte":
        return qs.filter(**{f"{field}__gte": value})
    if op == "lt":
        return qs.filter(**{f"{field}__lt": value})
    if op == "lte":
        return qs.filter(**{f"{field}__lte": value})
    return qs


def _apply_datetime_filter(qs, field: str, op: str, value: str):
    parsed_date = None
    try:
        parsed_date = date.fromisoformat(value)
    except (ValueError, TypeError):
        parsed_date = None
    if op in ("contains", "eq") and parsed_date is None:
        return qs.filter(**{f"{field}__icontains": value})
    if parsed_date:
        if op == "eq":
            return qs.filter(**{f"{field}__date": parsed_date})
        if op == "before":
            return qs.filter(**{f"{field}__date__lt": parsed_date})
        if op == "after":
            return qs.filter(**{f"{field}__date__gt": parsed_date})
    return qs


def _apply_enum_filter(qs, field: str, op: str, value):
    if op == "in" and isinstance(value, list):
        return qs.filter(**{f"{field}__in": value})
    return qs.filter(**{field: value})


def _apply_credentials_filter(qs, value: str):
    if value == "configured":
        return qs.exclude(Q(cluster_pwd__isnull=True) | Q(cluster_pwd=""))
    if value == "missing":
        return qs.filter(Q(cluster_pwd__isnull=True) | Q(cluster_pwd=""))
    return qs


def _apply_filters(qs, filters: dict) -> tuple:
    for key, payload in filters.items():
        if key not in CLUSTER_FILTER_FIELDS:
            return qs, {
                "code": "UNKNOWN_FILTER",
                "message": f"Unknown filter key: {key}",
            }
        value = payload
        op = "eq"
        if isinstance(payload, dict):
            op = payload.get("op", "eq")
            value = payload.get("value")
        if value in (None, ""):
            continue
        config = CLUSTER_FILTER_FIELDS[key]
        field_type = config["type"]
        field = config["field"]
        if field_type == "text":
            qs = _apply_text_filter(qs, field, op, str(value))
        elif field_type == "number":
            try:
                num = int(value)
            except (ValueError, TypeError):
                return qs, {
                    "code": "INVALID_FILTER_VALUE",
                    "message": f"Invalid numeric value for {key}",
                }
            qs = _apply_number_filter(qs, field, op, num)
        elif field_type == "datetime":
            qs = _apply_datetime_filter(qs, field, op, str(value))
        elif field_type == "enum":
            qs = _apply_enum_filter(qs, field, op, value)
        elif field_type == "credentials":
            qs = _apply_credentials_filter(qs, str(value))
    return qs, None


# =============================================================================
# Response Serializers for OpenAPI documentation
# =============================================================================

class ClusterErrorDetailSerializer(serializers.Serializer):
    """Error detail structure."""
    code = serializers.CharField(help_text="Error code (e.g., MISSING_PARAMETER)")
    message = serializers.CharField(help_text="Human-readable error message")
    details = serializers.DictField(required=False, help_text="Additional error details")


class ClusterErrorResponseSerializer(serializers.Serializer):
    """Standard error response."""
    success = serializers.BooleanField(default=False)
    error = ClusterErrorDetailSerializer()


class ClusterListResponseSerializer(serializers.Serializer):
    """Response for list_clusters endpoint."""
    clusters = ClusterSerializer(many=True)
    count = serializers.IntegerField(help_text="Number of clusters in current page")
    total = serializers.IntegerField(help_text="Total number of clusters matching filters")


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


class ClusterCredentialsUpdateRequestSerializer(serializers.Serializer):
    """Request body for update_cluster_credentials endpoint."""
    cluster_id = serializers.UUIDField()
    username = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)
    reset = serializers.BooleanField(required=False, default=False)


class ClusterCredentialsUpdateResponseSerializer(serializers.Serializer):
    """Response for update_cluster_credentials endpoint."""
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


class DiscoverClustersRequestSerializer(serializers.Serializer):
    """Request body for discover_clusters endpoint."""
    ras_host = serializers.CharField(help_text="RAS host")
    ras_port = serializers.IntegerField(help_text="RAS port")
    cluster_service_url = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="RAS adapter URL (optional, reserved for worker usage)",
    )
    cluster_user = serializers.CharField(required=False, allow_blank=True)
    cluster_pwd = serializers.CharField(required=False, allow_blank=True, write_only=True)


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

class ResetSyncStatusRequestSerializer(serializers.Serializer):
    cluster_id = serializers.UUIDField(required=False)
    all = serializers.BooleanField(required=False, default=False)


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
        else:
            logger.warning(f"Go Worker enqueue failed: {result.error}")
    except Exception as e:
        logger.warning(f"Go Worker unavailable for cluster sync: {e}")

        operation.status = BatchOperation.STATUS_FAILED
        operation.failed_tasks = 1
        operation.completed_at = timezone.now()
        operation.metadata = {'error': str(e), 'sync_mode': 'worker_unavailable'}
        operation.save()

        return Response({
            'success': False,
            'operation_id': str(operation.id),
            'error': {
                'code': 'WORKER_UNAVAILABLE',
                'message': 'Go Worker unavailable for cluster sync'
            }
        }, status=503)


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
