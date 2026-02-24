from __future__ import annotations

import json
import logging
from datetime import datetime, timezone as dt_timezone
from typing import Any

from django.utils import timezone

from apps.operations.redis_client import redis_client


logger = logging.getLogger(__name__)


POOL_OUTBOX_DISPATCHER_HEARTBEAT_KEY = "cc1c:pool_run_command_outbox_dispatcher:heartbeat"
DEFAULT_POOL_OUTBOX_DISPATCHER_HEARTBEAT_TTL_SECONDS = 30


def write_pool_outbox_dispatcher_heartbeat(
    *,
    claimed: int,
    dispatched: int,
    failed: int,
    interval_seconds: float,
    heartbeat_ttl_seconds: int = DEFAULT_POOL_OUTBOX_DISPATCHER_HEARTBEAT_TTL_SECONDS,
    now: datetime | None = None,
) -> None:
    """Persist best-effort heartbeat for runtime health monitoring."""
    timestamp = now or timezone.now()
    payload = {
        "timestamp": timestamp.isoformat(),
        "claimed": max(0, int(claimed)),
        "dispatched": max(0, int(dispatched)),
        "failed": max(0, int(failed)),
        "interval_seconds": max(0.1, float(interval_seconds)),
    }
    try:
        redis_client.client.set(
            POOL_OUTBOX_DISPATCHER_HEARTBEAT_KEY,
            json.dumps(payload, separators=(",", ":")),
            ex=max(1, int(heartbeat_ttl_seconds)),
        )
    except Exception as exc:
        logger.debug("Failed to write pool outbox dispatcher heartbeat: %s", exc)


def read_pool_outbox_dispatcher_heartbeat() -> dict[str, Any] | None:
    """Read heartbeat payload from Redis, returns None on errors."""
    try:
        raw_payload = redis_client.client.get(POOL_OUTBOX_DISPATCHER_HEARTBEAT_KEY)
    except Exception:
        return None
    if not raw_payload:
        return None
    try:
        parsed = json.loads(raw_payload)
    except (TypeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_pool_outbox_dispatcher_heartbeat_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if timezone.is_naive(parsed):
        return parsed.replace(tzinfo=dt_timezone.utc)
    return parsed
