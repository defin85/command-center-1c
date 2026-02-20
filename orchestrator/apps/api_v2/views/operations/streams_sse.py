"""Operations streaming endpoint: per-operation SSE stream."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time

from asgiref.sync import sync_to_async
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema

from apps.operations.models import BatchOperation
from apps.operations.prometheus_metrics import (
    record_api_v2_duration,
    record_api_v2_error,
    record_sse_loop_duration,
    record_sse_stream_error,
    sse_connection_close,
    sse_connection_open,
)

from .streams_common import (
    OP_SSE_ACTIVE_PREFIX,
    OP_SSE_ACTIVE_TTL,
    SSE_BLOCK_MS,
    SSE_HEARTBEAT_INTERVAL_SECONDS,
    SSE_MAX_CONNECTION_SECONDS,
    SSE_MAX_IDLE_SECONDS,
    _authenticate_legacy_token_async,
    _count_active_streams_async,
    _get_async_redis_connection,
    _get_max_live_streams_async,
    _validate_sse_ticket_async,
)

logger = logging.getLogger(__name__)


def _normalize_observability_fields(event_payload: dict, *, operation_id: str) -> dict:
    event = dict(event_payload if isinstance(event_payload, dict) else {})
    metadata = event.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    workflow_execution_id = event.get("workflow_execution_id") or metadata.get("workflow_execution_id")
    node_id = event.get("node_id") or metadata.get("node_id")
    root_operation_id = event.get("root_operation_id") or metadata.get("root_operation_id") or operation_id
    execution_consumer = (
        str(event.get("execution_consumer") or metadata.get("execution_consumer") or "").strip()
        or "operations"
    )
    lane = str(event.get("lane") or metadata.get("lane") or "").strip() or execution_consumer

    metadata["root_operation_id"] = root_operation_id
    metadata["execution_consumer"] = execution_consumer
    metadata["lane"] = lane
    if workflow_execution_id:
        metadata["workflow_execution_id"] = workflow_execution_id
    if node_id:
        metadata["node_id"] = node_id

    event["workflow_execution_id"] = workflow_execution_id
    event["node_id"] = node_id
    event["root_operation_id"] = root_operation_id
    event["execution_consumer"] = execution_consumer
    event["lane"] = lane
    event["metadata"] = metadata
    return event


@extend_schema(
    tags=['v2'],
    summary='Operation SSE stream',
    description='SSE endpoint for real-time operation updates. Prefer ticket-based auth via /stream-ticket/.',
    parameters=[
        OpenApiParameter(
            name='ticket',
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description='Short-lived SSE ticket from /operations/stream-ticket/.',
        ),
        OpenApiParameter(
            name='operation_id',
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description='Operation ID (deprecated legacy token auth).',
        ),
        OpenApiParameter(
            name='token',
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description='Legacy token auth (deprecated).',
        ),
    ],
    responses={
        200: OpenApiResponse(description='SSE stream (text/event-stream)'),
        401: OpenApiResponse(description='Unauthorized'),
    },
)
@require_GET
async def operation_stream(request):
    """
    GET /api/v2/operations/stream/?ticket=xxx
    GET /api/v2/operations/stream/?operation_id=xxx&token=xxx (deprecated)

    SSE endpoint for real-time operation updates.

    Prefer ticket-based auth via /stream-ticket/ endpoint for security.
    """
    start_time = time.monotonic()
    endpoint = "operations.stream"
    ticket = request.GET.get('ticket')
    token = request.GET.get('token')
    operation_id = request.GET.get('operation_id')

    # Validate: need either ticket or (token + operation_id)
    if not ticket and not token:
        record_api_v2_duration(endpoint, "unauthorized", time.monotonic() - start_time)
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'ticket is required (use /stream-ticket/ to obtain)'
            }
        }, status=401)

    # Prefer ticket-based auth (secure)
    user_id = None
    if ticket:
        ticket_data, error = await _validate_sse_ticket_async(ticket)
        if error:
            record_api_v2_duration(endpoint, "unauthorized", time.monotonic() - start_time)
            return JsonResponse({
                'success': False,
                'error': {
                    'code': 'INVALID_TICKET',
                    'message': error
                }
            }, status=401)

        operation_id = ticket_data['operation_id']
        username = ticket_data['username']
        user_id = ticket_data.get("user_id")

    else:
        # Legacy token auth (deprecated - log warning)
        logger.warning(
            "SSE stream using deprecated token auth. "
            "Please migrate to ticket-based auth via /stream-ticket/"
        )

        if not operation_id:
            record_api_v2_duration(endpoint, "bad_request", time.monotonic() - start_time)
            return JsonResponse({
                'success': False,
                'error': {
                    'code': 'MISSING_PARAMETER',
                    'message': 'operation_id is required with token auth'
                }
            }, status=400)

        try:
            user = await _authenticate_legacy_token_async(token)
            username = user.username
            user_id = user.id
        except Exception as e:
            logger.error(f"SSE authentication failed: {e}")
            record_api_v2_duration(endpoint, "unauthorized", time.monotonic() - start_time)
            record_api_v2_error(endpoint, e.__class__.__name__)
            return JsonResponse({
                'success': False,
                'error': {
                    'code': 'INVALID_TOKEN',
                    'message': 'Invalid or expired token'
                }
            }, status=401)

    logger.info(f"SSE stream started for operation {operation_id} by user {username}")

    active_key = None
    active_value = None
    if user_id:
        active_key = f"{OP_SSE_ACTIVE_PREFIX}{user_id}:{operation_id}"
        active_value = ticket_data.get("client_id") if ticket else None
        if not active_value:
            active_value = secrets.token_urlsafe(12)
        active_conn = _get_async_redis_connection()
        try:
            max_live_streams = await _get_max_live_streams_async()
            if max_live_streams > 0:
                active_count = await _count_active_streams_async(active_conn, user_id)
                if active_count >= max_live_streams:
                    record_api_v2_duration(endpoint, "limit", time.monotonic() - start_time)
                    response = JsonResponse({
                        'success': False,
                        'error': {
                            'code': 'STREAM_LIMIT_EXCEEDED',
                            'message': 'Too many active streams',
                            'max_streams': max_live_streams,
                        }
                    }, status=429)
                    response['Retry-After'] = "60"
                    return response

            if not await active_conn.set(active_key, active_value, nx=True, ex=OP_SSE_ACTIVE_TTL):
                record_api_v2_duration(endpoint, "conflict", time.monotonic() - start_time)
                return JsonResponse({
                    'success': False,
                    'error': {
                        'code': 'STREAM_ALREADY_ACTIVE',
                        'message': 'Operation stream already active for this user'
                    }
                }, status=429)
        finally:
            await active_conn.close()

    async def event_generator():
        """Generator for SSE events using Redis Streams (XREAD)."""
        logger.info(f"event_generator: Starting for operation {operation_id}")
        sse_connection_open("operations")

        # Connect to Redis
        redis_conn = _get_async_redis_connection()
        stream_name = f"events:operation:{operation_id}"
        logger.info(f"event_generator: Will read from stream {stream_name}")
        stream_started_at = time.monotonic()
        last_event_at = stream_started_at

        # Send initial state
        try:
            operation = await sync_to_async(
                BatchOperation.objects.get,
                thread_sensitive=True,
            )(id=operation_id)
            logger.info(f"event_generator: Found operation with status {operation.status}")
            operation_metadata = operation.metadata or {}
            initial_event = {
                "version": "1.0",
                "operation_id": str(operation_id),
                "timestamp": timezone.now().isoformat(),
                "state": operation.status.upper(),
                "microservice": "orchestrator",
                "message": f"Operation status: {operation.status}",
                "trace_id": operation_metadata.get("trace_id"),
                "workflow_execution_id": operation_metadata.get("workflow_execution_id"),
                "node_id": operation_metadata.get("node_id"),
                "root_operation_id": operation_metadata.get("root_operation_id") or str(operation_id),
                "execution_consumer": (
                    str(operation_metadata.get("execution_consumer") or "").strip() or "operations"
                ),
                "lane": (
                    str(operation_metadata.get("lane") or "").strip()
                    or str(operation_metadata.get("execution_consumer") or "").strip()
                    or "operations"
                ),
                "metadata": {
                    "operation_type": operation.operation_type,
                    "created_at": operation.created_at.isoformat(),
                }
            }
            initial_event = _normalize_observability_fields(
                initial_event,
                operation_id=str(operation_id),
            )
            logger.info("event_generator: Sending initial event")
            yield f"data: {json.dumps(initial_event)}\n\n"
            logger.info("event_generator: Initial event sent")
            last_event_at = time.monotonic()
        except BatchOperation.DoesNotExist:
            error_event = {
                "error": "Operation not found",
                "operation_id": str(operation_id)
            }
            yield f"data: {json.dumps(error_event)}\n\n"
            await redis_conn.close()
            record_sse_stream_error("operations", "missing_operation")
            return

        # Read events from Redis Stream using XREAD
        # Start with '0-0' to read from beginning for complete operation history
        # (MAXLEN=1000 ensures all events of typical operation are preserved)
        last_event_id = request.headers.get("Last-Event-ID")
        last_id = last_event_id or '0-0'
        last_heartbeat = time.monotonic()

        try:
            while True:
                loop_start = time.monotonic()
                now = time.monotonic()
                if SSE_MAX_CONNECTION_SECONDS and now - stream_started_at > SSE_MAX_CONNECTION_SECONDS:
                    logger.info("operation_stream: max connection time reached (operation_id=%s)", operation_id)
                    break
                if SSE_MAX_IDLE_SECONDS and now - last_event_at > SSE_MAX_IDLE_SECONDS:
                    logger.info("operation_stream: idle timeout reached (operation_id=%s)", operation_id)
                    break
                # XREAD with short block timeout
                # Returns: [(stream_name, [(msg_id, {fields}), ...])] or None on timeout
                messages = await redis_conn.xread({stream_name: last_id}, block=SSE_BLOCK_MS, count=10)

                if not messages:
                    # Timeout - send heartbeat comment to keep connection alive
                    now = time.monotonic()
                    if now - last_heartbeat >= SSE_HEARTBEAT_INTERVAL_SECONDS:
                        if active_key:
                            try:
                                await redis_conn.expire(active_key, OP_SSE_ACTIVE_TTL)
                            except Exception:
                                pass
                        yield ": heartbeat\n\n"
                        last_heartbeat = now
                    record_sse_loop_duration("operations", time.monotonic() - loop_start)
                    continue

                for stream, stream_messages in messages:
                    for msg_id, fields in stream_messages:
                        # Extract event data from stream message
                        # Format: {"event_type": "...", "data": "json_string", "operation_id": "..."}
                        event_data = fields.get('data', '{}')
                        try:
                            decoded_event = json.loads(event_data)
                            if isinstance(decoded_event, dict):
                                event_data = json.dumps(
                                    _normalize_observability_fields(
                                        decoded_event,
                                        operation_id=str(operation_id),
                                    )
                                )
                        except (TypeError, json.JSONDecodeError):
                            pass
                        event_type = fields.get('event_type') or 'message'
                        if active_key:
                            try:
                                await redis_conn.expire(active_key, OP_SSE_ACTIVE_TTL)
                            except Exception:
                                pass
                        yield f"event: {event_type}\n"
                        yield f"id: {msg_id}\n"
                        yield f"data: {event_data}\n\n"
                        last_id = msg_id
                        last_event_at = time.monotonic()
                loop_duration = time.monotonic() - loop_start
                record_sse_loop_duration("operations", loop_duration)
                if loop_duration > 5:
                    logger.warning("operation_stream: slow loop %.2fs (operation_id=%s)", loop_duration, operation_id)

        except asyncio.CancelledError:
            logger.info("operation_stream: cancelled (operation_id=%s)", operation_id)
        except GeneratorExit:
            # Client disconnected
            logger.info(f"Client disconnected from SSE stream for operation {operation_id}")
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            record_sse_stream_error("operations", "event_loop")
            raise
        finally:
            try:
                if active_key and active_value:
                    current_value = await redis_conn.get(active_key)
                    if current_value == active_value:
                        await redis_conn.delete(active_key)
                await redis_conn.close()
            except Exception:
                pass  # Игнорируем ошибки при закрытии
            sse_connection_close("operations")

    record_api_v2_duration(endpoint, "stream_start", time.monotonic() - start_time)
    response = StreamingHttpResponse(
        event_generator(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
    return response
