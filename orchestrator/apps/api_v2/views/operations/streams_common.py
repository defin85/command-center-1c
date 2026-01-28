"""Operations streaming shared helpers."""

from __future__ import annotations

import json

import redis as redis_module
import redis.asyncio as redis_async
from asgiref.sync import sync_to_async
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.runtime_settings.models import RuntimeSetting
from apps.runtime_settings.registry import RUNTIME_SETTINGS

# =============================================================================
# SSE Ticket Constants
# =============================================================================
SSE_TICKET_TTL = 30  # seconds
SSE_TICKET_PREFIX = "sse_ticket:"
SSE_MUX_TICKET_PREFIX = "sse_mux_ticket:"
SSE_BLOCK_MS = 1000
SSE_HEARTBEAT_INTERVAL_SECONDS = 10
SSE_MAX_CONNECTION_SECONDS = getattr(settings, "SSE_MAX_CONNECTION_SECONDS", 0)
SSE_MAX_IDLE_SECONDS = getattr(settings, "SSE_MAX_IDLE_SECONDS", 0)
OP_SSE_ACTIVE_PREFIX = "op_sse_active:"
OP_SSE_ACTIVE_TTL = 120
OP_SSE_MAX_STREAMS_KEY = "ui.operations.max_live_streams"
OP_SSE_MAX_STREAMS_DEFAULT = (
    RUNTIME_SETTINGS.get(OP_SSE_MAX_STREAMS_KEY).default
    if RUNTIME_SETTINGS.get(OP_SSE_MAX_STREAMS_KEY)
    else 10
)
OP_MUX_ACTIVE_PREFIX = "op_mux_active:"
OP_MUX_ACTIVE_TTL = 120
OP_MUX_MAX_STREAMS_KEY = "observability.operations.max_mux_streams"
OP_MUX_MAX_STREAMS_DEFAULT = (
    RUNTIME_SETTINGS.get(OP_MUX_MAX_STREAMS_KEY).default
    if RUNTIME_SETTINGS.get(OP_MUX_MAX_STREAMS_KEY)
    else 1
)
OP_MUX_MAX_SUBSCRIPTIONS_KEY = "observability.operations.max_subscriptions"
OP_MUX_MAX_SUBSCRIPTIONS_DEFAULT = (
    RUNTIME_SETTINGS.get(OP_MUX_MAX_SUBSCRIPTIONS_KEY).default
    if RUNTIME_SETTINGS.get(OP_MUX_MAX_SUBSCRIPTIONS_KEY)
    else 200
)
OP_MUX_SUB_PREFIX = "op_mux_sub:"
OP_MUX_LAST_PREFIX = "op_mux_last:"


# =============================================================================
# SSE Streaming
# =============================================================================


def _get_redis_connection():
    """Get Redis connection for SSE tickets."""
    redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    return redis_module.from_url(redis_url, decode_responses=True)


def _get_async_redis_connection():
    redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    return redis_async.from_url(redis_url, decode_responses=True)


def _get_max_live_streams() -> int:
    setting = RuntimeSetting.objects.filter(key=OP_SSE_MAX_STREAMS_KEY).first()
    value = setting.value if setting else OP_SSE_MAX_STREAMS_DEFAULT
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return OP_SSE_MAX_STREAMS_DEFAULT
    return parsed if parsed > 0 else OP_SSE_MAX_STREAMS_DEFAULT


async def _get_max_live_streams_async() -> int:
    return await sync_to_async(_get_max_live_streams, thread_sensitive=True)()


def _get_max_mux_streams() -> int:
    setting = RuntimeSetting.objects.filter(key=OP_MUX_MAX_STREAMS_KEY).first()
    value = setting.value if setting else OP_MUX_MAX_STREAMS_DEFAULT
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return OP_MUX_MAX_STREAMS_DEFAULT
    return parsed if parsed > 0 else OP_MUX_MAX_STREAMS_DEFAULT


async def _get_max_mux_streams_async() -> int:
    return await sync_to_async(_get_max_mux_streams, thread_sensitive=True)()


def _get_max_mux_subscriptions() -> int:
    setting = RuntimeSetting.objects.filter(key=OP_MUX_MAX_SUBSCRIPTIONS_KEY).first()
    value = setting.value if setting else OP_MUX_MAX_SUBSCRIPTIONS_DEFAULT
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return OP_MUX_MAX_SUBSCRIPTIONS_DEFAULT
    return parsed if parsed > 0 else OP_MUX_MAX_SUBSCRIPTIONS_DEFAULT


async def _get_max_mux_subscriptions_async() -> int:
    return await sync_to_async(_get_max_mux_subscriptions, thread_sensitive=True)()


def _count_active_streams(redis_conn, user_id: int) -> int:
    pattern = f"{OP_SSE_ACTIVE_PREFIX}{user_id}:*"
    count = 0
    for _ in redis_conn.scan_iter(match=pattern, count=100):
        count += 1
    return count


def _count_active_mux_streams(redis_conn, user_id: int) -> int:
    pattern = f"{OP_MUX_ACTIVE_PREFIX}{user_id}:*"
    count = 0
    for _ in redis_conn.scan_iter(match=pattern, count=100):
        count += 1
    return count


async def _count_active_streams_async(redis_conn, user_id: int) -> int:
    pattern = f"{OP_SSE_ACTIVE_PREFIX}{user_id}:*"
    count = 0
    cursor = 0
    while True:
        cursor, keys = await redis_conn.scan(cursor=cursor, match=pattern, count=100)
        count += len(keys)
        if cursor == 0:
            break
    return count


async def _count_active_mux_streams_async(redis_conn, user_id: int) -> int:
    pattern = f"{OP_MUX_ACTIVE_PREFIX}{user_id}:*"
    count = 0
    cursor = 0
    while True:
        cursor, keys = await redis_conn.scan(cursor=cursor, match=pattern, count=100)
        count += len(keys)
        if cursor == 0:
            break
    return count


async def _validate_sse_ticket_async(ticket: str) -> tuple:
    """
    Validate and consume SSE ticket (async).

    Returns:
        (ticket_data, error_message) - ticket_data is None if validation failed
    """
    redis_conn = _get_async_redis_connection()
    try:
        ticket_key = f"{SSE_TICKET_PREFIX}{ticket}"
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


async def _authenticate_legacy_token_async(token: str):
    def _do_auth():
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        if not user:
            raise AuthenticationFailed('User not found')
        return user

    return await sync_to_async(_do_auth, thread_sensitive=True)()


async def _validate_mux_ticket_async(ticket: str) -> tuple:
    """
    Validate and consume multiplex SSE ticket (async).

    Returns:
        (ticket_data, error_message) - ticket_data is None if validation failed
    """
    redis_conn = _get_async_redis_connection()
    try:
        ticket_key = f"{SSE_MUX_TICKET_PREFIX}{ticket}"
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

