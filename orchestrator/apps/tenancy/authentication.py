from __future__ import annotations

import uuid

from django.db import transaction
from rest_framework.authentication import BaseAuthentication, SessionAuthentication
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.authentication import ServiceJWTAuthentication, ServiceUser
from apps.tenancy.context import set_current_tenant_id


TENANT_HEADER = "HTTP_X_CC1C_TENANT_ID"


def _get_header_tenant_id(request) -> str | None:
    raw = request.META.get(TENANT_HEADER)
    if raw is None:
        return None
    raw_str = str(raw).strip()
    if not raw_str:
        return None
    try:
        return str(uuid.UUID(raw_str))
    except Exception as exc:
        raise ValidationError({"tenant_id": "Invalid tenant id"}) from exc


def _resolve_tenant_for_user(user, header_tenant_id: str | None):
    from apps.tenancy.models import Tenant, TenantMember, UserTenantPreference

    default_tenant = Tenant.objects.filter(slug="default").first()
    if default_tenant is None:
        default_tenant = Tenant.objects.create(slug="default", name="Default")

    if isinstance(user, ServiceUser):
        # Internal services: require tenant context, but do not enforce membership.
        if header_tenant_id:
            tenant = Tenant.objects.filter(id=header_tenant_id).first()
            return tenant or default_tenant
        return default_tenant

    if header_tenant_id:
        tenant = Tenant.objects.filter(id=header_tenant_id).first()
        if tenant is None:
            raise PermissionDenied("Tenant not found")
        if not TenantMember.objects.filter(tenant=tenant, user_id=user.id).exists():
            raise PermissionDenied("Tenant access denied")
        return tenant

    pref = UserTenantPreference.objects.filter(user_id=user.id).select_related("active_tenant").first()
    if pref and pref.active_tenant_id:
        tenant = pref.active_tenant
        if not TenantMember.objects.filter(tenant=tenant, user_id=user.id).exists():
            raise PermissionDenied("Tenant access denied")
        return tenant

    membership = TenantMember.objects.filter(user_id=user.id).select_related("tenant").order_by("tenant__name").first()
    if membership:
        tenant = membership.tenant
        if pref is None:
            UserTenantPreference.objects.create(user_id=user.id, active_tenant=tenant)
        else:
            pref.active_tenant = tenant
            pref.save(update_fields=["active_tenant", "updated_at"])
        return tenant

    # No memberships: fail closed (expected to be created via migration or user provisioning).
    raise PermissionDenied("Tenant access denied")


class TenantContextAuthentication(BaseAuthentication):
    """
    Authenticates request (JWT/service + session) and sets tenant context.

    Tenant is resolved from:
      - X-CC1C-Tenant-ID header (preferred), else
      - user active tenant preference, else
      - first membership, else
      - default tenant (service users only).
    """

    def __init__(self):
        self._jwt = ServiceJWTAuthentication()
        self._session = SessionAuthentication()

    def authenticate(self, request):
        forced_user = getattr(request, "_force_auth_user", None)
        forced_token = getattr(request, "_force_auth_token", None)
        if forced_user is None and getattr(request, "_request", None) is not None:
            forced_user = getattr(request._request, "_force_auth_user", None)
            forced_token = getattr(request._request, "_force_auth_token", None)
        if forced_user is not None:
            self._apply_tenant_context(request, forced_user)
            return (forced_user, forced_token)

        jwt_result = self._jwt.authenticate(request)
        if jwt_result:
            user, token = jwt_result
            self._apply_tenant_context(request, user)
            return (user, token)

        session_result = self._session.authenticate(request)
        if session_result:
            user, auth = session_result
            self._apply_tenant_context(request, user)
            return (user, auth)

        return None

    def _apply_tenant_context(self, request, user) -> None:
        header_tenant_id = _get_header_tenant_id(request)
        with transaction.atomic():
            tenant = _resolve_tenant_for_user(user, header_tenant_id)
        request.tenant = tenant
        request.tenant_id = str(tenant.id)
        set_current_tenant_id(str(tenant.id))

    def authenticate_header(self, request) -> str:
        # Keep BearerAuth semantics for OpenAPI.
        return "Bearer"


# drf-spectacular OpenAPI integration
try:
    from drf_spectacular.extensions import OpenApiAuthenticationExtension
except Exception:  # pragma: no cover
    OpenApiAuthenticationExtension = None


if OpenApiAuthenticationExtension is not None:
    class TenantContextAuthenticationScheme(OpenApiAuthenticationExtension):
        target_class = "apps.tenancy.authentication.TenantContextAuthentication"
        name = "bearerAuth"

        def get_security_definition(self, auto_schema):
            return {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
