"""
Tenant endpoints for API v2.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.tenancy.models import TenantMember, UserTenantPreference


class TenantItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    slug = serializers.CharField()
    name = serializers.CharField()
    role = serializers.CharField()


class ListMyTenantsResponseSerializer(serializers.Serializer):
    active_tenant_id = serializers.UUIDField(allow_null=True)
    tenants = TenantItemSerializer(many=True)


def build_tenant_context_payload(*, user) -> dict:
    memberships = (
        TenantMember.objects.filter(user_id=user.id)
        .select_related("tenant")
        .order_by("tenant__name")
    )
    pref = UserTenantPreference.objects.filter(user_id=user.id).first()

    tenants_out = []
    for membership in memberships:
        tenants_out.append(
            {
                "id": membership.tenant_id,
                "slug": membership.tenant.slug,
                "name": membership.tenant.name,
                "role": membership.role,
            }
        )

    return {
        "active_tenant_id": pref.active_tenant_id if pref else None,
        "tenants": tenants_out,
    }


@extend_schema(
    tags=["v2"],
    summary="List my tenants",
    description="List tenants available for the current user (membership scoped).",
    responses={
        200: ListMyTenantsResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_my_tenants(request):
    return Response(build_tenant_context_payload(user=request.user))


class SetActiveTenantRequestSerializer(serializers.Serializer):
    tenant_id = serializers.UUIDField()


class SetActiveTenantResponseSerializer(serializers.Serializer):
    active_tenant_id = serializers.UUIDField()


@extend_schema(
    tags=["v2"],
    summary="Set active tenant",
    description="Persist active tenant for the current user.",
    request=SetActiveTenantRequestSerializer,
    responses={
        200: SetActiveTenantResponseSerializer,
        400: OpenApiResponse(description="Validation error"),
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_active_tenant(request):
    serializer = SetActiveTenantRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": serializer.errors}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tenant_id = str(serializer.validated_data["tenant_id"])
    if not TenantMember.objects.filter(user_id=request.user.id, tenant_id=tenant_id).exists():
        return Response(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "No access to tenant"}},
            status=status.HTTP_403_FORBIDDEN,
        )

    pref, _ = UserTenantPreference.objects.get_or_create(user_id=request.user.id)
    pref.active_tenant_id = tenant_id
    pref.save(update_fields=["active_tenant", "updated_at"])

    return Response({"active_tenant_id": pref.active_tenant_id})
