"""
Database endpoints for API v2.

Provides action-based endpoints for database operations.
"""

import json
import logging
import secrets
import time

import redis as redis_module
import redis.asyncio as redis_async
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
from apps.operations.prometheus_metrics import (
    record_api_v2_duration,
    record_api_v2_error,
    record_sse_ticket,
    sse_connection_open,
    sse_connection_close,
    record_sse_stream_error,
    record_sse_loop_duration,
)

logger = logging.getLogger(__name__)

DB_SSE_TICKET_PREFIX = "db_sse_ticket:"
DB_SSE_TICKET_TTL = 30
DB_STREAM_NAME = "events:databases"
SSE_BLOCK_MS = 1000
SSE_HEARTBEAT_INTERVAL_SECONDS = 10
DB_SSE_ACTIVE_PREFIX = "db_sse_active:"
DB_SSE_ACTIVE_TTL = 60


def _get_redis_connection():
    redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    return redis_module.from_url(redis_url, decode_responses=True)


def _get_async_redis_connection():
    redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    return redis_async.from_url(redis_url, decode_responses=True)


async def _validate_db_stream_ticket(ticket: str) -> tuple[dict | None, str | None]:
    redis_conn = _get_async_redis_connection()

    try:
        ticket_key = f"{DB_SSE_TICKET_PREFIX}{ticket}"
        pipe = redis_conn.pipeline()
        pipe.get(ticket_key)
        pipe.delete(ticket_key)
        results = await pipe.execute()

        ticket_data_raw = results[0]
        if not ticket_data_raw:
            return None, "Invalid or expired ticket"

        return json.loads(ticket_data_raw), None
    finally:
        await redis_conn.close()


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


class DatabaseCredentialsUpdateRequestSerializer(serializers.Serializer):
    """Request body for update_database_credentials endpoint."""
    database_id = serializers.CharField(help_text="Database ID to update")
    username = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)
    reset = serializers.BooleanField(required=False, default=False)


class DatabaseCredentialsUpdateResponseSerializer(serializers.Serializer):
    """Response for update_database_credentials endpoint."""
    database = DatabaseSerializer()
    message = serializers.CharField()


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
    force = serializers.BooleanField(required=False, default=False)


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
    summary='Update database credentials',
    description='Set or reset database OData credentials.',
    request=DatabaseCredentialsUpdateRequestSerializer,
    responses={
        200: DatabaseCredentialsUpdateResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_database_credentials(request):
    """
    POST /api/v2/databases/update-credentials/

    Update or reset database credentials.

    Request Body:
        {
            "database_id": "db-123",
            "username": "odata_user",   // optional
            "password": "secret",       // optional
            "reset": false              // optional, default: false
        }

    Response (200):
        {
            "database": {...},
            "message": "Database credentials updated"
        }
    """
    serializer = DatabaseCredentialsUpdateRequestSerializer(data=request.data)
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
    database_id = data['database_id']

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

    reset = data.get('reset', False)
    updated_fields = []

    if reset:
        db.username = ''
        db.password = ''
        updated_fields.extend(['username', 'password'])
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
            db.username = data['username']
            updated_fields.append('username')

        if password_provided:
            if data['password'] == '':
                return Response({
                    'success': False,
                    'error': {
                        'code': 'INVALID_PARAMETER',
                        'message': 'password cannot be empty (use reset=true to clear)'
                    }
                }, status=400)
            db.password = data['password']
            updated_fields.append('password')

    db.save(update_fields=[*updated_fields, 'updated_at'])

    log_admin_action(
        request,
        action='database.credentials.update',
        outcome='success',
        target_type='database',
        target_id=str(db.id),
        metadata={
            'reset': reset,
            'updated_fields': updated_fields,
            'configured': bool(db.password),
        },
    )

    return Response({
        'database': DatabaseSerializer(db).data,
        'message': 'Database credentials updated'
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
    start_time = time.monotonic()
    endpoint = "databases.stream_ticket"
    serializer = DatabaseStreamTicketRequestSerializer(data=request.data or {})
    serializer.is_valid(raise_exception=True)

    cluster_id = serializer.validated_data.get('cluster_id')
    force = serializer.validated_data.get('force', False)

    if cluster_id and not Cluster.objects.filter(id=cluster_id).exists():
        record_api_v2_duration(endpoint, "not_found", time.monotonic() - start_time)
        record_sse_ticket("databases", "not_found")
        return Response({
            'success': False,
            'error': {
                'code': 'CLUSTER_NOT_FOUND',
                'message': 'Cluster not found'
            }
        }, status=404)

    redis_conn = _get_redis_connection()
    active_key = f"{DB_SSE_ACTIVE_PREFIX}{request.user.id}"

    try:
        ttl = redis_conn.ttl(active_key)
        if ttl and ttl > 0 and not force:
            record_api_v2_duration(endpoint, "conflict", time.monotonic() - start_time)
            record_sse_ticket("databases", "conflict")
            response = Response({
                'success': False,
                'error': {
                    'code': 'STREAM_ALREADY_ACTIVE',
                    'message': 'Database stream already active for this user',
                    'retry_after': ttl,
                }
            }, status=429)
            response['Retry-After'] = str(ttl)
            return response

        ticket = secrets.token_urlsafe(32)
        ticket_data = {
            'user_id': request.user.id,
            'username': request.user.username,
            'cluster_id': str(cluster_id) if cluster_id else None,
            'created_at': timezone.now().isoformat(),
            'force': force,
        }
        redis_conn.setex(
            f"{DB_SSE_TICKET_PREFIX}{ticket}",
            DB_SSE_TICKET_TTL,
            json.dumps(ticket_data),
        )
        record_api_v2_duration(endpoint, "ok", time.monotonic() - start_time)
        record_sse_ticket("databases", "ok")
    except Exception as exc:
        record_api_v2_duration(endpoint, "error", time.monotonic() - start_time)
        record_api_v2_error(endpoint, exc.__class__.__name__)
        record_sse_ticket("databases", "error")
        raise
    finally:
        redis_conn.close()

    return Response({
        'ticket': ticket,
        'expires_in': DB_SSE_TICKET_TTL,
        'stream_url': f'/api/v2/databases/stream/?ticket={ticket}',
    })


async def database_stream(request):
    start_time = time.monotonic()
    endpoint = "databases.stream"
    ticket = request.GET.get('ticket')

    if not ticket:
        record_api_v2_duration(endpoint, "unauthorized", time.monotonic() - start_time)
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'ticket is required (use /databases/stream-ticket/ to obtain)'
            }
        }, status=401)

    ticket_data, error = await _validate_db_stream_ticket(ticket)
    if error:
        record_api_v2_duration(endpoint, "unauthorized", time.monotonic() - start_time)
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'INVALID_TICKET',
                'message': error
            }
        }, status=401)

    cluster_id = ticket_data.get('cluster_id')
    username = ticket_data.get('username')
    user_id = ticket_data.get('user_id')
    force = bool(ticket_data.get('force'))
    logger.info("Database SSE stream started for user %s (cluster=%s)", username, cluster_id or "all")

    active_key = f"{DB_SSE_ACTIVE_PREFIX}{user_id}"
    active_value = secrets.token_urlsafe(12)
    active_conn = _get_async_redis_connection()
    try:
        if force:
            await active_conn.set(active_key, active_value, ex=DB_SSE_ACTIVE_TTL)
        else:
            if not await active_conn.set(active_key, active_value, nx=True, ex=DB_SSE_ACTIVE_TTL):
                record_api_v2_duration(endpoint, "conflict", time.monotonic() - start_time)
                return JsonResponse({
                    'success': False,
                    'error': {
                        'code': 'STREAM_ALREADY_ACTIVE',
                        'message': 'Database stream already active for this user'
                    }
                }, status=429)
    finally:
        await active_conn.close()

    async def event_generator():
        logger.info("database_stream: starting event generator")
        sse_connection_open("databases")
        redis_conn = _get_async_redis_connection()
        stream_name = DB_STREAM_NAME
        last_event_id = request.headers.get("Last-Event-ID")
        last_id = last_event_id or '$'
        last_heartbeat = time.monotonic()

        try:
            ready_event = {
                "version": "1.0",
                "type": "database_stream_connected",
                "timestamp": timezone.now().isoformat(),
                "cluster_id": cluster_id,
            }
            yield "event: database_stream_connected\n"
            yield f"data: {json.dumps(ready_event)}\n\n"

            while True:
                loop_start = time.monotonic()
                try:
                    current_value = await redis_conn.get(active_key)
                    if current_value and current_value != active_value:
                        logger.info("database_stream: replaced by new stream (user=%s)", username)
                        break
                    if current_value is None:
                        await redis_conn.set(active_key, active_value, ex=DB_SSE_ACTIVE_TTL)
                except Exception:
                    pass
                messages = await redis_conn.xread({stream_name: last_id}, block=SSE_BLOCK_MS, count=10)

                if not messages:
                    now = time.monotonic()
                    if now - last_heartbeat >= SSE_HEARTBEAT_INTERVAL_SECONDS:
                        try:
                            await redis_conn.expire(active_key, DB_SSE_ACTIVE_TTL)
                        except Exception:
                            pass
                        yield ": heartbeat\n\n"
                        last_heartbeat = now
                    record_sse_loop_duration("databases", time.monotonic() - loop_start)
                    continue

                for _, stream_messages in messages:
                    for msg_id, fields in stream_messages:
                        if cluster_id:
                            event_cluster_id = fields.get('cluster_id') or ''
                            if event_cluster_id != cluster_id:
                                last_id = msg_id
                                continue

                        event_data = fields.get('data', '{}')
                        event_type = fields.get('event_type') or 'database_update'
                        try:
                            await redis_conn.expire(active_key, DB_SSE_ACTIVE_TTL)
                        except Exception:
                            pass
                        yield f"event: {event_type}\n"
                        yield f"id: {msg_id}\n"
                        yield f"data: {event_data}\n\n"
                        last_id = msg_id
                loop_duration = time.monotonic() - loop_start
                record_sse_loop_duration("databases", loop_duration)
                if loop_duration > 5:
                    logger.warning(
                        "database_stream: slow loop %.2fs (cluster=%s)",
                        loop_duration,
                        cluster_id or "all",
                    )

        except GeneratorExit:
            logger.info("Client disconnected from database SSE stream")
        except Exception as exc:
            logger.error("Database SSE stream error: %s", exc)
            record_sse_stream_error("databases", "event_loop")
            raise
        finally:
            try:
                current_value = await redis_conn.get(active_key)
                if current_value == active_value:
                    await redis_conn.delete(active_key)
                await redis_conn.close()
            except Exception:
                pass
            sse_connection_close("databases")

    record_api_v2_duration(endpoint, "stream_start", time.monotonic() - start_time)
    response = StreamingHttpResponse(
        event_generator(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
