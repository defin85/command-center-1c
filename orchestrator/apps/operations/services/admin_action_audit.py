"""Helpers for auditing operator/admin actions (SPA-primary flows)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.http import HttpRequest

from apps.operations.models import AdminActionAuditLog
from apps.operations.prometheus_metrics import record_admin_action

logger = logging.getLogger(__name__)


def log_admin_action(
    request: Optional[HttpRequest],
    *,
    action: str,
    outcome: str,
    target_type: str = "",
    target_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    error_message: str = "",
) -> None:
    """
    Best-effort audit logging + metrics.

    Never raises: failures are logged and ignored.
    """

    record_admin_action(action, outcome)

    try:
        actor = getattr(request, "user", None) if request is not None else None
        actor_username = getattr(actor, "username", "") if actor is not None else ""
        actor_ip = None
        user_agent = ""

        if request is not None:
            actor_ip = request.META.get("REMOTE_ADDR")
            user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:256]

        AdminActionAuditLog.objects.create(
            action=action,
            outcome=outcome,
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            actor_username=actor_username or "",
            actor_ip=actor_ip,
            user_agent=user_agent,
            target_type=target_type or "",
            target_id=target_id or "",
            metadata=metadata or {},
            error_message=error_message or "",
        )
    except Exception as e:
        logger.warning("Admin action audit write failed: %s", e, exc_info=True)

