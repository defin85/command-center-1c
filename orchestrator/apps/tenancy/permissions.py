from __future__ import annotations

from django.db import transaction
from rest_framework.permissions import BasePermission

from apps.tenancy.authentication import _get_header_tenant_id, _resolve_tenant_for_user
from apps.tenancy.context import set_current_tenant_id


class TenantContextPermission(BasePermission):
    """
    Ensure tenant context is resolved for the request.

    Why: DRF test client `force_authenticate(...)` bypasses authentication classes, so
    `TenantContextAuthentication` may not run. This permission provides a stable
    tenant context for both real requests and tests, based on the same resolver
    logic (header -> active preference -> first membership).
    """

    def has_permission(self, request, view) -> bool:
        if getattr(request, "tenant_id", None):
            set_current_tenant_id(str(request.tenant_id))
            return True

        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return True

        header_tenant_id = _get_header_tenant_id(request)
        with transaction.atomic():
            tenant = _resolve_tenant_for_user(user, header_tenant_id)

        request.tenant = tenant
        request.tenant_id = str(tenant.id)
        set_current_tenant_id(str(tenant.id))
        return True

