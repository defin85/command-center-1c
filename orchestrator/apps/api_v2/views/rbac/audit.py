"""RBAC endpoints: admin audit log."""

from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.operations.models import AdminActionAuditLog

from .common import _ensure_manage_rbac, _parse_pagination
from .serializers_core import AdminAuditLogListResponseSerializer

# =============================================================================
# Audit (SPA-primary)
# =============================================================================


def _parse_dt(value: str | None):
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


@extend_schema(
    tags=["v2"],
    summary="List admin audit log entries",
    parameters=[
        OpenApiParameter(name="action", type=str, required=False),
        OpenApiParameter(name="outcome", type=str, required=False),
        OpenApiParameter(name="actor", type=str, required=False, description="Filter by actor_username (contains)"),
        OpenApiParameter(name="target_type", type=str, required=False),
        OpenApiParameter(name="target_id", type=str, required=False),
        OpenApiParameter(name="since", type=str, required=False),
        OpenApiParameter(name="until", type=str, required=False),
        OpenApiParameter(name="search", type=str, required=False),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: AdminAuditLogListResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_admin_audit(request):
    denied = _ensure_manage_rbac(request)
    if denied:
        return denied

    pagination = _parse_pagination(request, default_limit=100, max_limit=500)
    qs = AdminActionAuditLog.objects.select_related("actor").all()

    action = (request.query_params.get("action") or "").strip()
    if action:
        qs = qs.filter(action=action)

    outcome = (request.query_params.get("outcome") or "").strip()
    if outcome:
        qs = qs.filter(outcome=outcome)

    actor = (request.query_params.get("actor") or "").strip()
    if actor:
        qs = qs.filter(actor_username__icontains=actor)

    target_type = (request.query_params.get("target_type") or "").strip()
    if target_type:
        qs = qs.filter(target_type=target_type)

    target_id = (request.query_params.get("target_id") or "").strip()
    if target_id:
        qs = qs.filter(target_id=target_id)

    since = _parse_dt(request.query_params.get("since"))
    if since:
        qs = qs.filter(created_at__gte=since)

    until = _parse_dt(request.query_params.get("until"))
    if until:
        qs = qs.filter(created_at__lte=until)

    search = (request.query_params.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(action__icontains=search)
            | Q(actor_username__icontains=search)
            | Q(target_type__icontains=search)
            | Q(target_id__icontains=search)
        )

    total = qs.count()
    rows = list(qs.order_by("-created_at")[pagination.offset: pagination.offset + pagination.limit])

    data = [
        {
            "id": row.id,
            "created_at": row.created_at,
            "action": row.action,
            "outcome": row.outcome,
            "actor_username": row.actor_username,
            "actor_id": row.actor_id,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "metadata": row.metadata or {},
            "error_message": row.error_message or "",
        }
        for row in rows
    ]
    return Response({"items": data, "count": len(data), "total": total})

