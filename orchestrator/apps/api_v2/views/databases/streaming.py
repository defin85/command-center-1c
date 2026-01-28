"""Database streaming endpoints."""

from __future__ import annotations

from .common import *  # noqa: F403
from .common import (
    _get_async_redis_connection,
    _get_redis_connection,
    _is_staff,
    _permission_denied,
    _validate_db_stream_ticket,
)

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
        400: DatabaseErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: DatabaseErrorResponseSerializer,
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

    if not _is_staff(request.user):
        if not cluster_id:
            return _permission_denied("cluster_id is required for non-staff users.")

        cluster = Cluster.objects.get(id=cluster_id)
        if not request.user.has_perm(perms.PERM_DATABASES_VIEW_CLUSTER, cluster):
            return _permission_denied("You do not have permission to access this cluster.")

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


@extend_schema(
    tags=['v2'],
    summary='Database SSE stream',
    description='SSE endpoint for database updates. Use ticket from /databases/stream-ticket/.',
    parameters=[
        OpenApiParameter(
            name='ticket',
            type=str,
            location=OpenApiParameter.QUERY,
            required=True,
            description='Short-lived SSE ticket from /databases/stream-ticket/.',
        ),
    ],
    responses={
        200: OpenApiResponse(description='SSE stream (text/event-stream)'),
        401: OpenApiResponse(description='Unauthorized'),
    },
)
@require_GET
async def database_stream(request):
    return await _database_stream_async(request)


async def _database_stream_async(request):
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
    user = await sync_to_async(User.objects.get)(id=user_id)
    is_staff = user.is_staff
    allowed_db_ids: set[str] | None = None

    if not is_staff:
        def _load_allowed_ids():
            qs = Database.objects.all()
            if cluster_id:
                qs = qs.filter(cluster_id=cluster_id)
            qs = PermissionService.filter_accessible_databases(
                user,
                qs,
                PermissionLevel.VIEW,
            )
            return {str(db_id) for db_id in qs.values_list('id', flat=True)}

        allowed_db_ids = await sync_to_async(_load_allowed_ids, thread_sensitive=True)()
        if not allowed_db_ids:
            return JsonResponse({
                'success': False,
                'error': {
                    'code': 'PERMISSION_DENIED',
                    'message': 'No accessible databases for stream',
                }
            }, status=403)

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
        stream_started_at = time.monotonic()
        last_event_at = stream_started_at

        try:
            ready_event = {
                "version": "1.0",
                "type": "database_stream_connected",
                "timestamp": timezone.now().isoformat(),
                "cluster_id": cluster_id,
            }
            yield "event: database_stream_connected\n"
            yield f"data: {json.dumps(ready_event)}\n\n"
            last_event_at = time.monotonic()

            while True:
                loop_start = time.monotonic()
                now = time.monotonic()
                if SSE_MAX_CONNECTION_SECONDS and now - stream_started_at > SSE_MAX_CONNECTION_SECONDS:
                    logger.info("database_stream: max connection time reached (user=%s)", username)
                    break
                if SSE_MAX_IDLE_SECONDS and now - last_event_at > SSE_MAX_IDLE_SECONDS:
                    logger.info("database_stream: idle timeout reached (user=%s)", username)
                    break
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
                        if allowed_db_ids is not None:
                            event_db_id = fields.get('database_id')
                            if not event_db_id or event_db_id not in allowed_db_ids:
                                last_id = msg_id
                                continue
                        try:
                            await redis_conn.expire(active_key, DB_SSE_ACTIVE_TTL)
                        except Exception:
                            pass
                        yield f"event: {event_type}\n"
                        yield f"id: {msg_id}\n"
                        yield f"data: {event_data}\n\n"
                        last_id = msg_id
                        last_event_at = time.monotonic()
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
        except asyncio.CancelledError:
            logger.info("database_stream: cancelled (user=%s)", username)
        except GeneratorExit:
            logger.info("database_stream: client disconnected (user=%s)", username)
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
