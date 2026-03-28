from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.intercompany_pools.factual_scheduler_runtime import (
    trigger_pool_factual_active_sync_window,
    trigger_pool_factual_closed_quarter_reconcile_window,
)

from .permissions import IsInternalService
from .views_common import exclude_schema


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def trigger_pool_factual_active_sync_window_view(request):
    tenant_id = str((request.data or {}).get("tenant_id") or "").strip() or None
    payload = trigger_pool_factual_active_sync_window(tenant_id=tenant_id)
    return Response({"success": True, **payload}, status=status.HTTP_200_OK)


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def trigger_pool_factual_closed_quarter_reconcile_window_view(request):
    tenant_id = str((request.data or {}).get("tenant_id") or "").strip() or None
    payload = trigger_pool_factual_closed_quarter_reconcile_window(tenant_id=tenant_id)
    return Response({"success": True, **payload}, status=status.HTTP_200_OK)
