"""
Database endpoints for API v2.

Provides action-based endpoints for database operations.
"""

import json
import logging
import secrets

import redis as redis_module
from django.conf import settings
from django.db.models import Q
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.databases.models import Cluster, Database
from apps.databases.serializers import DatabaseSerializer, ClusterSerializer
from apps.operations.services import OperationsService
from apps.operations.services.admin_action_audit import log_admin_action

logger = logging.getLogger(__name__)

DB_SSE_TICKET_PREFIX = "db_sse_ticket:"
DB_SSE_TICKET_TTL = 30
DB_STREAM_NAME = "events:databases"


def _get_redis_connection():
    redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    return redis_module.from_url(redis_url, decode_responses=True)


def _validate_db_stream_ticket(ticket: str) -> tuple[dict | None, str | None]:
    redis_conn = _get_redis_connection()

    try:
        ticket_key = f"{DB_SSE_TICKET_PREFIX}{ticket}"
        pipe = redis_conn.pipeline()
        pipe.get(ticket_key)
        pipe.delete(ticket_key)
        results = pipe.execute()

        ticket_data_raw = results[0]
        if not ticket_data_raw:
            return None, "Invalid or expired ticket"

        return json.loads(ticket_data_raw), None
    finally:
        redis_conn.close()


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


class HealthCheckEnqueueResponseSerializer(serializers.Serializer):
    """Response for health_check endpoints (operation queued)."""
    operation_id = serializers.CharField(help_text="ID of the created operation")
    status = serializers.CharField(help_text="Operation status (queued)")
    total_tasks = serializers.IntegerField(help_text="Number of tasks created")
    message = serializers.CharField(help_text="Status message")


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


class DatabaseStreamTicketRequestSerializer(serializers.Serializer):
    """Request body for database stream ticket endpoint."""

    cluster_id = serializers.UUIDField(required=False, allow_null=True)


class DatabaseStreamTicketResponseSerializer(serializers.Serializer):
    """Response for database stream ticket endpoint."""

    ticket = serializers.CharField(help_text="Short-lived ticket for SSE connection")
    expires_in = serializers.IntegerField(help_text="Seconds until ticket expires")
    stream_url = serializers.CharField(help_text="SSE endpoint URL to connect to")
    message = serializers.CharField()


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
    description='Queue OData health check for a specific database.',
    request=HealthCheckRequestSerializer,
    responses={
        202: HealthCheckEnqueueResponseSerializer,
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

    Queue health check for a specific database.

    Request Body:
        {
            "database_id": "string"
        }

    Response (202 Accepted):
        {
            "operation_id": "uuid",
            "status": "queued",
            "total_tasks": 1,
            "message": "health_check queued for 1 database(s)"
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

    enqueue_result = OperationsService.enqueue_health_check(
        database_ids=[database_id],
        created_by=request.user.username if request.user else "system",
    )
    if not enqueue_result.success:
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': enqueue_result.error or 'Failed to queue health check'
            }
        }, status=500)

    return Response({
        'operation_id': enqueue_result.operation_id,
        'status': enqueue_result.status,
        'total_tasks': enqueue_result.metadata.get('database_count', 1),
        'message': 'health_check queued for 1 database(s)',
    }, status=http_status.HTTP_202_ACCEPTED)


@extend_schema(
    tags=['v2'],
    summary='Bulk health check databases',
    description='Queue health check on multiple databases. Provide either database_ids or cluster_id.',
    request=BulkHealthCheckRequestSerializer,
    responses={
        202: HealthCheckEnqueueResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_health_check(request):
    """
    POST /api/v2/databases/bulk-health-check/

    Queue health check on multiple databases.

    Request Body:
        {
            "database_ids": ["id1", "id2", ...],
            "cluster_id": "optional-cluster-id"
        }

    Response (202 Accepted):
        {
            "operation_id": "uuid",
            "status": "queued",
            "total_tasks": 10,
            "message": "health_check queued for 10 database(s)"
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

    databases = list(qs)
    if not databases:
        return Response({
            'success': False,
            'error': {
                'code': 'DATABASES_NOT_FOUND',
                'message': 'No databases found for the request'
            }
        }, status=400)

    enqueue_result = OperationsService.enqueue_health_check(
        database_ids=[str(db.id) for db in databases],
        created_by=request.user.username if request.user else "system",
    )
    if not enqueue_result.success:
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': enqueue_result.error or 'Failed to queue health check'
            }
        }, status=500)

    return Response({
        'operation_id': enqueue_result.operation_id,
        'status': enqueue_result.status,
        'total_tasks': enqueue_result.metadata.get('database_count', len(databases)),
        'message': f'health_check queued for {len(databases)} database(s)',
    }, status=http_status.HTTP_202_ACCEPTED)


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


# =============================================================================
# SSE Streaming (Databases)
# =============================================================================


@extend_schema(
    tags=['v2'],
    summary='Get database SSE stream ticket',
    description='''
    Obtain a short-lived, single-use ticket for database SSE stream authentication.

    The ticket is valid for 30 seconds and can only be used once.
    ''',
    request=DatabaseStreamTicketRequestSerializer,
    responses={
        200: DatabaseStreamTicketResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_database_stream_ticket(request):
    serializer = DatabaseStreamTicketRequestSerializer(data=request.data or {})
    serializer.is_valid(raise_exception=True)

    cluster_id = serializer.validated_data.get('cluster_id')

    if cluster_id and not Cluster.objects.filter(id=cluster_id).exists():
        return Response({
            'success': False,
            'error': {
                'code': 'CLUSTER_NOT_FOUND',
                'message': 'Cluster not found'
            }
        }, status=404)

    ticket = secrets.token_urlsafe(32)
    redis_conn = _get_redis_connection()

    try:
        ticket_data = {
            'user_id': request.user.id,
            'username': request.user.username,
            'cluster_id': str(cluster_id) if cluster_id else None,
            'created_at': timezone.now().isoformat(),
        }
        redis_conn.setex(
            f"{DB_SSE_TICKET_PREFIX}{ticket}",
            DB_SSE_TICKET_TTL,
            json.dumps(ticket_data),
        )
    finally:
        redis_conn.close()

    return Response({
        'ticket': ticket,
        'expires_in': DB_SSE_TICKET_TTL,
        'stream_url': f'/api/v2/databases/stream/?ticket={ticket}',
    })


@extend_schema(
    tags=['v2'],
    summary='Stream database updates (SSE)',
    description='''
    Real-time Server-Sent Events (SSE) stream for database updates.

    **Authentication:** Use ticket from /databases/stream-ticket/ endpoint.
    ''',
    parameters=[
        OpenApiParameter(
            name='ticket',
            type=str,
            required=True,
            description='Short-lived SSE ticket from /databases/stream-ticket/'
        ),
    ],
    responses={
        200: OpenApiResponse(description='SSE stream (text/event-stream)'),
        400: ErrorResponseSerializer,
        401: ErrorResponseSerializer,
        404: ErrorResponseSerializer,
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def database_stream(request):
    ticket = request.query_params.get('ticket')

    if not ticket:
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'ticket is required (use /databases/stream-ticket/ to obtain)'
            }
        }, status=401)

    ticket_data, error = _validate_db_stream_ticket(ticket)
    if error:
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'INVALID_TICKET',
                'message': error
            }
        }, status=401)

    cluster_id = ticket_data.get('cluster_id')
    username = ticket_data.get('username')
    logger.info("Database SSE stream started for user %s (cluster=%s)", username, cluster_id or "all")

    def event_generator():
        logger.info("database_stream: starting event generator")
        redis_conn = _get_redis_connection()
        stream_name = DB_STREAM_NAME
        last_id = '$'

        try:
            ready_event = {
                "version": "1.0",
                "type": "database_stream_connected",
                "timestamp": timezone.now().isoformat(),
                "cluster_id": cluster_id,
            }
            yield f"data: {json.dumps(ready_event)}\n\n"

            while True:
                messages = redis_conn.xread({stream_name: last_id}, block=5000, count=10)

                if not messages:
                    yield ": heartbeat\n\n"
                    continue

                for _, stream_messages in messages:
                    for msg_id, fields in stream_messages:
                        if cluster_id:
                            event_cluster_id = fields.get('cluster_id') or ''
                            if event_cluster_id != cluster_id:
                                last_id = msg_id
                                continue

                        event_data = fields.get('data', '{}')
                        yield f"data: {event_data}\n\n"
                        last_id = msg_id

        except GeneratorExit:
            logger.info("Client disconnected from database SSE stream")
        except Exception as exc:
            logger.error("Database SSE stream error: %s", exc)
            raise
        finally:
            try:
                redis_conn.close()
            except Exception:
                pass

    response = StreamingHttpResponse(
        event_generator(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
