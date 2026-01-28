"""Command schemas audit endpoint."""

from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.operations.models import AdminActionAuditLog

from .common import (
    CommandSchemasAuditListResponseSerializer,
    ErrorResponseSerializer,
    COMMAND_SCHEMA_DRIVER_CHOICES,
    record_driver_catalog_editor_error,
    _ensure_manage_driver_catalogs,
)

@extend_schema(
    tags=["v2"],
    summary="List command schemas audit log entries",
    parameters=[
        OpenApiParameter(name="driver", type=str, required=False, description="Driver name (cli/ibcmd)"),
        OpenApiParameter(name="limit", type=int, required=False),
        OpenApiParameter(name="offset", type=int, required=False),
    ],
    responses={200: CommandSchemasAuditListResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
def list_command_schemas_audit(request):
    denied = _ensure_manage_driver_catalogs(request, action="audit.list")
    if denied:
        return denied

    driver = (request.query_params.get("driver") or "").strip().lower()
    if driver and driver not in COMMAND_SCHEMA_DRIVER_CHOICES:
        record_driver_catalog_editor_error("unknown", action="audit.list", code="UNKNOWN_DRIVER")
        return Response({
            "success": False,
            "error": {"code": "UNKNOWN_DRIVER", "message": f"Unknown driver: {driver}"},
        }, status=400)

    try:
        limit = int(request.query_params.get("limit") or 100)
        offset = int(request.query_params.get("offset") or 0)
    except (TypeError, ValueError):
        record_driver_catalog_editor_error(driver if driver else "all", action="audit.list", code="INVALID_PAGINATION")
        return Response({
            "success": False,
            "error": {"code": "INVALID_PAGINATION", "message": "limit/offset must be integers"},
        }, status=400)

    if limit < 1 or limit > 500 or offset < 0:
        record_driver_catalog_editor_error(driver if driver else "all", action="audit.list", code="INVALID_PAGINATION")
        return Response({
            "success": False,
            "error": {"code": "INVALID_PAGINATION", "message": "limit must be 1..500 and offset >= 0"},
        }, status=400)

    qs = AdminActionAuditLog.objects.select_related("actor").filter(
        target_type="driver_catalog",
        action__startswith="driver_catalog.",
    )
    if driver:
        qs = qs.filter(target_id=driver)

    total = qs.count()
    rows = list(qs.order_by("-created_at")[offset : offset + limit])

    items = [
        {
            "id": row.id,
            "created_at": row.created_at,
            "action": row.action,
            "outcome": row.outcome,
            "actor_username": row.actor_username,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "metadata": row.metadata or {},
            "error_message": row.error_message or "",
        }
        for row in rows
    ]

    return Response({"items": items, "count": len(items), "total": total})
