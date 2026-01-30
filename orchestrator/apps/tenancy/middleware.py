from __future__ import annotations

from .context import clear_current_tenant_id


class TenantContextCleanupMiddleware:
    """
    Clears thread-local tenant context between requests.

    Tenant is set during DRF authentication (apps.tenancy.authentication).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        clear_current_tenant_id()
        try:
            response = self.get_response(request)
        finally:
            clear_current_tenant_id()
        return response

