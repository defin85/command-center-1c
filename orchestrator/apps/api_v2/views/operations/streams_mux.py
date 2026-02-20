"""Operations streaming endpoints: multiplex stream (mux)."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time

from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.operations.models import BatchOperation
from apps.operations.prometheus_metrics import (
    record_api_v2_duration,
    record_sse_loop_duration,
    record_sse_stream_error,
    sse_connection_close,
    sse_connection_open,
)

from .access import resolve_operation_access
from .schemas import (
    OperationErrorResponseSerializer,
    OperationMuxStreamStatusSerializer,
    OperationMuxSubscribeSerializer,
    OperationMuxTicketRequestSerializer,
    OperationMuxUnsubscribeSerializer,
    SSETicketResponseSerializer,
)
from .streams_common import (
    OP_MUX_ACTIVE_PREFIX,
    OP_MUX_ACTIVE_TTL,
    OP_MUX_LAST_PREFIX,
    OP_MUX_SUB_PREFIX,
    SSE_BLOCK_MS,
    SSE_HEARTBEAT_INTERVAL_SECONDS,
    SSE_MAX_CONNECTION_SECONDS,
    SSE_MAX_IDLE_SECONDS,
    SSE_MUX_TICKET_PREFIX,
    SSE_TICKET_TTL,
    _count_active_mux_streams,
    _count_active_mux_streams_async,
    _get_async_redis_connection,
    _get_max_mux_streams,
    _get_max_mux_streams_async,
    _get_max_mux_subscriptions,
    _get_redis_connection,
    _validate_mux_ticket_async,
)
from .streams_sse import _normalize_observability_fields

logger = logging.getLogger(__name__)

@extend_schema(
    tags=['v2'],
    summary='Get multiplex SSE stream status',
    description='Get active multiplex SSE stream count for current user.',
    responses={
        200: OperationMuxStreamStatusSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_stream_mux_status(request):
    redis_conn = _get_redis_connection()
    try:
        active_count = _count_active_mux_streams(redis_conn, request.user.id)
        sub_key = f"{OP_MUX_SUB_PREFIX}{request.user.id}"
        active_subscriptions = redis_conn.scard(sub_key)
    finally:
        redis_conn.close()

    return Response({
        "active_streams": active_count,
        "max_streams": _get_max_mux_streams(),
        "active_subscriptions": active_subscriptions,
        "max_subscriptions": _get_max_mux_subscriptions(),
    })


@extend_schema(
    tags=['v2'],
    summary='Subscribe to multiplex stream operations',
    request=OperationMuxSubscribeSerializer,
    responses={
        200: OpenApiResponse(description='Subscription updated'),
        401: OpenApiResponse(description='Unauthorized'),
        429: OperationErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subscribe_operation_streams(request):
    serializer = OperationMuxSubscribeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    operation_ids = list({str(op_id) for op_id in serializer.validated_data['operation_ids']})

    operations = list(
        BatchOperation.objects.filter(id__in=operation_ids).prefetch_related('target_databases')
    )
    found_ids = {str(op.id) for op in operations}
    missing = [op_id for op_id in operation_ids if op_id not in found_ids]

    allowed, denied = resolve_operation_access(request.user, operations)

    redis_conn = _get_redis_connection()
    try:
        sub_key = f"{OP_MUX_SUB_PREFIX}{request.user.id}"
        last_key = f"{OP_MUX_LAST_PREFIX}{request.user.id}"
        existing = redis_conn.smembers(sub_key)

        allowed_new = [op_id for op_id in allowed if op_id not in existing]
        max_subscriptions = _get_max_mux_subscriptions()
        if len(existing) + len(allowed_new) > max_subscriptions:
            response = Response({
                'success': False,
                'error': {
                    'code': 'STREAM_SUBSCRIPTION_LIMIT',
                    'message': 'Too many subscribed operations',
                    'max_subscriptions': max_subscriptions,
                    'current_subscriptions': len(existing),
                    'requested': len(allowed_new),
                }
            }, status=429)
            response['Retry-After'] = "60"
            return response

        if allowed_new:
            redis_conn.sadd(sub_key, *allowed_new)
            mapping = {op_id: '$' for op_id in allowed_new}
            redis_conn.hset(last_key, mapping=mapping)

        return Response({
            "subscribed": allowed,
            "denied": denied,
            "missing": missing,
            "active_subscriptions": len(existing) + len(allowed_new),
            "max_subscriptions": max_subscriptions,
        })
    finally:
        redis_conn.close()


@extend_schema(
    tags=['v2'],
    summary='Unsubscribe from multiplex stream operations',
    request=OperationMuxUnsubscribeSerializer,
    responses={
        200: OpenApiResponse(description='Subscription updated'),
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unsubscribe_operation_streams(request):
    serializer = OperationMuxUnsubscribeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    operation_ids = list({str(op_id) for op_id in serializer.validated_data['operation_ids']})

    redis_conn = _get_redis_connection()
    try:
        sub_key = f"{OP_MUX_SUB_PREFIX}{request.user.id}"
        last_key = f"{OP_MUX_LAST_PREFIX}{request.user.id}"
        if operation_ids:
            redis_conn.srem(sub_key, *operation_ids)
            redis_conn.hdel(last_key, *operation_ids)
        active_count = redis_conn.scard(sub_key)
        return Response({
            "unsubscribed": operation_ids,
            "active_subscriptions": active_count,
            "max_subscriptions": _get_max_mux_subscriptions(),
        })
    finally:
        redis_conn.close()


@extend_schema(
    tags=['v2'],
    summary='Get multiplex SSE stream ticket',
    request=OperationMuxTicketRequestSerializer,
    responses={
        200: SSETicketResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        429: OperationErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_mux_stream_ticket(request):
    serializer = OperationMuxTicketRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    client_id = serializer.validated_data.get('client_id')

    redis_conn = _get_redis_connection()
    active_key = f"{OP_MUX_ACTIVE_PREFIX}{request.user.id}"

    try:
        max_streams = _get_max_mux_streams()
        if max_streams > 0:
            active_count = _count_active_mux_streams(redis_conn, request.user.id)
            if active_count >= max_streams:
                response = Response({
                    'success': False,
                    'error': {
                        'code': 'STREAM_LIMIT_EXCEEDED',
                        'message': 'Too many active streams',
                        'max_streams': max_streams,
                    }
                }, status=429)
                response['Retry-After'] = "60"
                return response

        ttl = redis_conn.ttl(active_key)
        if ttl and ttl > 0:
            if client_id:
                current_value = redis_conn.get(active_key)
                if current_value == client_id:
                    ticket = secrets.token_urlsafe(32)
                    ticket_data = {
                        'user_id': request.user.id,
                        'username': request.user.username,
                        'client_id': client_id,
                        'created_at': timezone.now().isoformat(),
                    }
                    redis_conn.setex(
                        f"{SSE_MUX_TICKET_PREFIX}{ticket}",
                        SSE_TICKET_TTL,
                        json.dumps(ticket_data)
                    )
                    return Response({
                        'ticket': ticket,
                        'expires_in': SSE_TICKET_TTL,
                        'stream_url': f'/api/v2/operations/stream-mux/?ticket={ticket}'
                    })
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

        ticket = secrets.token_urlsafe(32)
        ticket_data = {
            'user_id': request.user.id,
            'username': request.user.username,
            'client_id': client_id,
            'created_at': timezone.now().isoformat(),
        }
        redis_conn.setex(
            f"{SSE_MUX_TICKET_PREFIX}{ticket}",
            SSE_TICKET_TTL,
            json.dumps(ticket_data)
        )
    finally:
        redis_conn.close()

    return Response({
        'ticket': ticket,
        'expires_in': SSE_TICKET_TTL,
        'stream_url': f'/api/v2/operations/stream-mux/?ticket={ticket}'
    })


async def operation_stream_mux(request):
    """
    GET /api/v2/operations/stream-mux/?ticket=xxx

    SSE endpoint for multiplex operation updates.
    """
    start_time = time.monotonic()
    endpoint = "operations.stream_mux"
    ticket = request.GET.get('ticket')

    if not ticket:
        record_api_v2_duration(endpoint, "unauthorized", time.monotonic() - start_time)
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'ticket is required'
            }
        }, status=401)

    ticket_data, error = await _validate_mux_ticket_async(ticket)
    if error:
        record_api_v2_duration(endpoint, "unauthorized", time.monotonic() - start_time)
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'INVALID_TICKET',
                'message': error
            }
        }, status=401)

    user_id = ticket_data.get('user_id')
    username = ticket_data.get('username')
    client_id = ticket_data.get('client_id')
    if not user_id:
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'INVALID_TICKET',
                'message': 'Missing user_id'
            }
        }, status=401)

    active_key = f"{OP_MUX_ACTIVE_PREFIX}{user_id}"
    active_value = client_id or secrets.token_urlsafe(12)
    active_conn = _get_async_redis_connection()
    try:
        max_streams = await _get_max_mux_streams_async()
        if max_streams > 0:
            active_count = await _count_active_mux_streams_async(active_conn, user_id)
            if active_count >= max_streams:
                record_api_v2_duration(endpoint, "limit", time.monotonic() - start_time)
                response = JsonResponse({
                    'success': False,
                    'error': {
                        'code': 'STREAM_LIMIT_EXCEEDED',
                        'message': 'Too many active streams',
                        'max_streams': max_streams,
                    }
                }, status=429)
                response['Retry-After'] = "60"
                return response

        if not await active_conn.set(active_key, active_value, nx=True, ex=OP_MUX_ACTIVE_TTL):
            current_value = await active_conn.get(active_key)
            if current_value != active_value:
                record_api_v2_duration(endpoint, "conflict", time.monotonic() - start_time)
                return JsonResponse({
                    'success': False,
                    'error': {
                        'code': 'STREAM_ALREADY_ACTIVE',
                        'message': 'Operation stream already active for this user'
                    }
                }, status=429)
            await active_conn.expire(active_key, OP_MUX_ACTIVE_TTL)
    finally:
        await active_conn.close()

    async def event_generator():
        logger.info(f"operation_stream_mux: Starting for user {username}")
        sse_connection_open("operations_mux")

        redis_conn = _get_async_redis_connection()
        sub_key = f"{OP_MUX_SUB_PREFIX}{user_id}"
        last_key = f"{OP_MUX_LAST_PREFIX}{user_id}"
        last_heartbeat = time.monotonic()
        stream_started_at = time.monotonic()
        last_event_at = stream_started_at

        try:
            while True:
                loop_start = time.monotonic()
                now = time.monotonic()
                if SSE_MAX_CONNECTION_SECONDS and now - stream_started_at > SSE_MAX_CONNECTION_SECONDS:
                    logger.info("operation_stream_mux: max connection time reached (user=%s)", username)
                    break
                if SSE_MAX_IDLE_SECONDS and now - last_event_at > SSE_MAX_IDLE_SECONDS:
                    logger.info("operation_stream_mux: idle timeout reached (user=%s)", username)
                    break
                subscriptions = await redis_conn.smembers(sub_key)
                if not subscriptions:
                    now = time.monotonic()
                    if now - last_heartbeat >= SSE_HEARTBEAT_INTERVAL_SECONDS:
                        try:
                            await redis_conn.expire(active_key, OP_MUX_ACTIVE_TTL)
                        except Exception:
                            pass
                        yield ": heartbeat\n\n"
                        last_heartbeat = now
                    record_sse_loop_duration("operations_mux", time.monotonic() - loop_start)
                    await asyncio.sleep(0.5)
                    continue

                last_ids = await redis_conn.hmget(last_key, *subscriptions)
                stream_map = {}
                for op_id, last_id in zip(subscriptions, last_ids):
                    stream_map[f"events:operation:{op_id}"] = last_id or '$'

                messages = await redis_conn.xread(stream_map, block=SSE_BLOCK_MS, count=10)
                if not messages:
                    now = time.monotonic()
                    if now - last_heartbeat >= SSE_HEARTBEAT_INTERVAL_SECONDS:
                        try:
                            await redis_conn.expire(active_key, OP_MUX_ACTIVE_TTL)
                        except Exception:
                            pass
                        yield ": heartbeat\n\n"
                        last_heartbeat = now
                    record_sse_loop_duration("operations_mux", time.monotonic() - loop_start)
                    continue

                for stream, stream_messages in messages:
                    op_id = stream.split(":")[-1]
                    for msg_id, fields in stream_messages:
                        event_data = fields.get('data', '{}')
                        event_type = fields.get('event_type') or 'message'
                        try:
                            decoded_event = json.loads(event_data)
                            if isinstance(decoded_event, dict):
                                event_data = json.dumps(
                                    _normalize_observability_fields(
                                        decoded_event,
                                        operation_id=str(op_id),
                                    )
                                )
                        except (TypeError, json.JSONDecodeError):
                            pass
                        try:
                            await redis_conn.hset(last_key, op_id, msg_id)
                            await redis_conn.expire(active_key, OP_MUX_ACTIVE_TTL)
                        except Exception:
                            pass
                        yield f"event: {event_type}\n"
                        yield f"id: {msg_id}\n"
                        yield f"data: {event_data}\n\n"
                        last_event_at = time.monotonic()

                record_sse_loop_duration("operations_mux", time.monotonic() - loop_start)

        except asyncio.CancelledError:
            logger.info("operation_stream_mux: cancelled user=%s", username)
        except GeneratorExit:
            logger.info(f"operation_stream_mux: client disconnected user={username}")
        except Exception as e:
            logger.error(f"operation_stream_mux error: {e}")
            record_sse_stream_error("operations_mux", "event_loop")
            raise
        finally:
            try:
                current_value = await redis_conn.get(active_key)
                if current_value == active_value:
                    await redis_conn.delete(active_key)
                await redis_conn.close()
            except Exception:
                pass
            sse_connection_close("operations_mux")

    record_api_v2_duration(endpoint, "stream_start", time.monotonic() - start_time)
    response = StreamingHttpResponse(
        event_generator(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
