"""Operations streaming endpoints: stream tickets + status."""

from __future__ import annotations

import json
import secrets
import time

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.operations.models import BatchOperation
from apps.operations.prometheus_metrics import record_api_v2_duration, record_api_v2_error, record_sse_ticket

from .schemas import (
    OperationErrorResponseSerializer,
    OperationStreamStatusSerializer,
    SSETicketRequestSerializer,
    SSETicketResponseSerializer,
)
from .streams_common import (
    OP_SSE_ACTIVE_PREFIX,
    SSE_TICKET_PREFIX,
    SSE_TICKET_TTL,
    _count_active_streams,
    _get_max_live_streams,
    _get_redis_connection,
)

@extend_schema(
    tags=['v2'],
    summary='Get SSE stream ticket',
    description='''
    Obtain a short-lived, single-use ticket for SSE stream authentication.

    The ticket is valid for 30 seconds and can only be used once.
    This allows secure SSE connections without exposing JWT tokens in URLs.
    ''',
    request=SSETicketRequestSerializer,
    responses={
        200: SSETicketResponseSerializer,
        400: OperationErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: OperationErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_stream_ticket(request):
    """
    POST /api/v2/operations/stream-ticket/

    Get a short-lived ticket for SSE stream authentication.

    Request Body:
        {"operation_id": "uuid"}

    Response:
        {
            "ticket": "random_string",
            "expires_in": 30,
            "stream_url": "/api/v2/operations/stream/?ticket=..."
        }
    """
    start_time = time.monotonic()
    endpoint = "operations.stream_ticket"
    serializer = SSETicketRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    operation_id = serializer.validated_data['operation_id']
    client_id = serializer.validated_data.get('client_id')

    # Verify operation exists and user has permission
    operation = BatchOperation.objects.filter(id=operation_id).first()
    if not operation:
        record_api_v2_duration(endpoint, "not_found", time.monotonic() - start_time)
        record_sse_ticket("operations", "not_found")
        return Response({
            'success': False,
            'error': {
                'code': 'OPERATION_NOT_FOUND',
                'message': 'Operation not found'
            }
        }, status=404)

    # Authorization check: user must own the operation or be staff
    if operation.created_by != request.user.username and not request.user.is_staff:
        record_api_v2_duration(endpoint, "forbidden", time.monotonic() - start_time)
        record_sse_ticket("operations", "forbidden")
        return Response({
            'success': False,
            'error': {
                'code': 'FORBIDDEN',
                'message': 'You do not have permission to subscribe to this operation'
            }
        }, status=403)

    redis_conn = _get_redis_connection()
    active_key = f"{OP_SSE_ACTIVE_PREFIX}{request.user.id}:{operation_id}"

    try:
        max_live_streams = _get_max_live_streams()
        if max_live_streams > 0:
            active_count = _count_active_streams(redis_conn, request.user.id)
            if active_count >= max_live_streams:
                record_api_v2_duration(endpoint, "limit", time.monotonic() - start_time)
                record_sse_ticket("operations", "limit")
                response = Response({
                    'success': False,
                    'error': {
                        'code': 'STREAM_LIMIT_EXCEEDED',
                        'message': 'Too many active streams',
                        'max_streams': max_live_streams,
                    }
                }, status=429)
                response['Retry-After'] = "60"
                return response

        ttl = redis_conn.ttl(active_key)
        if ttl and ttl > 0:
            if client_id:
                current_value = redis_conn.get(active_key)
                if current_value == client_id:
                    record_api_v2_duration(endpoint, "ok", time.monotonic() - start_time)
                    record_sse_ticket("operations", "ok")
                    ticket = secrets.token_urlsafe(32)
                    ticket_data = {
                        'user_id': request.user.id,
                        'username': request.user.username,
                        'operation_id': operation_id,
                        'client_id': client_id,
                        'created_at': timezone.now().isoformat(),
                    }
                    redis_conn.setex(
                        f"{SSE_TICKET_PREFIX}{ticket}",
                        SSE_TICKET_TTL,
                        json.dumps(ticket_data)
                    )
                    return Response({
                        'ticket': ticket,
                        'expires_in': SSE_TICKET_TTL,
                        'stream_url': f'/api/v2/operations/stream/?ticket={ticket}'
                    })
            record_api_v2_duration(endpoint, "conflict", time.monotonic() - start_time)
            record_sse_ticket("operations", "conflict")
            response = Response({
                'success': False,
                'error': {
                    'code': 'STREAM_ALREADY_ACTIVE',
                    'message': 'Operation stream already active for this user',
                    'retry_after': ttl,
                }
            }, status=429)
            response['Retry-After'] = str(ttl)
            return response

        # Generate secure random ticket
        ticket = secrets.token_urlsafe(32)

        ticket_data = {
            'user_id': request.user.id,
            'username': request.user.username,
            'operation_id': operation_id,
            'client_id': client_id,
            'created_at': timezone.now().isoformat(),
        }

        redis_conn.setex(
            f"{SSE_TICKET_PREFIX}{ticket}",
            SSE_TICKET_TTL,
            json.dumps(ticket_data)
        )
        record_api_v2_duration(endpoint, "ok", time.monotonic() - start_time)
        record_sse_ticket("operations", "ok")
    except Exception as exc:
        record_api_v2_duration(endpoint, "error", time.monotonic() - start_time)
        record_api_v2_error(endpoint, exc.__class__.__name__)
        record_sse_ticket("operations", "error")
        raise
    finally:
        redis_conn.close()

    return Response({
        'ticket': ticket,
        'expires_in': SSE_TICKET_TTL,
        'stream_url': f'/api/v2/operations/stream/?ticket={ticket}'
    })


@extend_schema(
    tags=['v2'],
    summary='Get SSE stream status',
    description='Get active SSE stream count for current user.',
    responses={
        200: OperationStreamStatusSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_stream_status(request):
    redis_conn = _get_redis_connection()
    try:
        active_count = _count_active_streams(redis_conn, request.user.id)
    finally:
        redis_conn.close()

    return Response({
        "active_streams": active_count,
        "max_streams": _get_max_live_streams(),
    })

