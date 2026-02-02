import logging

from django.db import close_old_connections as django_close_old_connections
from django.db import connections

from apps.operations.models import Task
from apps.operations.redis_client import redis_client as operations_redis_client

logger = logging.getLogger("apps.operations.event_subscriber")

def close_old_connections() -> None:
    """
    Best-effort DB connection refresh for long-running subscriber processes.

    Django's close_old_connections() is request-oriented. In a long-running
    consumer, a DB connection can be closed by the server while Django still
    holds a non-None wrapper.connection object. That leads to:
      psycopg.OperationalError: the connection is closed

    This wrapper keeps the existing behavior but additionally closes wrappers
    whose underlying DB connection is already closed.
    """

    # IMPORTANT: Never attempt to close/refresh connections while inside an
    # active transaction (atomic block). Event handlers can be invoked within
    # `transaction.atomic()` in EventSubscriber._handle_message; closing there
    # can turn a healthy connection into "the connection is closed" mid-flight.
    try:
        for conn in connections.all():
            if getattr(conn, "in_atomic_block", False):
                return
    except Exception:
        # Best-effort: if we can't detect atomic state, fall back to default behavior.
        pass

    django_close_old_connections()

    # Best-effort: close wrappers that still hold a closed underlying connection.
    # This forces Django to establish a new connection on next DB access.
    try:
        for conn in connections.all():
            raw = conn.connection
            if raw is None:
                continue
            closed = getattr(raw, "closed", None)
            if closed:
                conn.close()
                continue

            # Some cases (esp. long-lived psycopg3 connections) can still blow up with
            # "the connection is closed" even when `raw.closed` is falsy.
            # `is_usable()` does a tiny round-trip and reliably detects unusable sockets.
            try:
                usable = conn.is_usable()
            except Exception:
                usable = False
            if not usable:
                conn.close()
    except Exception:
        try:
            connections.close_all()
        except Exception:
            pass

__all__ = [
    "Task",
    "close_old_connections",
    "logger",
    "operations_redis_client",
]
