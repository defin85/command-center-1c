"""
Extensions flags policy endpoints for API v2.

Tenant-scoped policy for 3 flags:
  - active
  - safe_mode
  - unsafe_action_protection

Note: staff mutating operations require explicit X-CC1C-Tenant-ID to avoid ambiguity.
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core import permission_codes as perms
from apps.databases.extensions_snapshot import normalize_extensions_snapshot
from apps.databases.models import Database, DatabaseExtensionsSnapshot, ExtensionFlagsPolicy, PermissionLevel
from apps.databases.services import PermissionService
from apps.mappings.extensions_inventory import build_canonical_extensions_inventory
from apps.mappings.models import TenantMappingSpec
from apps.operations.services.admin_action_audit import log_admin_action
from apps.tenancy.authentication import TENANT_HEADER


def _is_staff(user) -> bool:
    return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))


def _has_explicit_tenant_header(request) -> bool:
    raw = None
    try:
        raw = request.META.get(TENANT_HEADER)
    except Exception:
        raw = None
    if raw is None and getattr(request, "_request", None) is not None:
        try:
            raw = request._request.META.get(TENANT_HEADER)
        except Exception:
            raw = None
    return bool(str(raw).strip()) if raw is not None else False


def _require_tenant_header_for_staff_mutating(request) -> Response | None:
    if _is_staff(request.user) and not _has_explicit_tenant_header(request):
        return Response(
            {"success": False, "error": {"code": "TENANT_CONTEXT_REQUIRED", "message": "X-CC1C-Tenant-ID is required"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    return None


def _require_manage_permission(request) -> Response | None:
    # Policy mutating operations are a governance action: require manage_database permission.
    if not request.user.has_perm(perms.PERM_DATABASES_MANAGE_DATABASE):
        return Response(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "Permission denied"}},
            status=http_status.HTTP_403_FORBIDDEN,
        )
    return None


class ExtensionsFlagsPolicySerializer(serializers.Serializer):
    extension_name = serializers.CharField()
    active = serializers.BooleanField(allow_null=True, required=True)
    safe_mode = serializers.BooleanField(allow_null=True, required=True)
    unsafe_action_protection = serializers.BooleanField(allow_null=True, required=True)
    updated_at = serializers.DateTimeField(allow_null=True, required=True)


class ExtensionsFlagsPolicyListResponseSerializer(serializers.Serializer):
    policies = ExtensionsFlagsPolicySerializer(many=True)


class ExtensionsFlagsPolicyUpsertRequestSerializer(serializers.Serializer):
    active = serializers.BooleanField(allow_null=True, required=True)
    safe_mode = serializers.BooleanField(allow_null=True, required=True)
    unsafe_action_protection = serializers.BooleanField(allow_null=True, required=True)
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class ExtensionsFlagsPolicyAdoptRequestSerializer(serializers.Serializer):
    database_id = serializers.UUIDField(format="hex_verbose")
    extension_name = serializers.CharField()
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True)


def _policy_to_dict(obj: ExtensionFlagsPolicy) -> dict[str, Any]:
    return {
        "extension_name": obj.extension_name,
        "active": obj.active,
        "safe_mode": obj.safe_mode,
        "unsafe_action_protection": obj.unsafe_action_protection,
        "updated_at": obj.updated_at,
    }


def _get_published_extensions_mapping_spec(tenant_id: str) -> dict:
    spec = TenantMappingSpec.objects.filter(
        tenant_id=tenant_id,
        entity_kind=TenantMappingSpec.ENTITY_EXTENSIONS_INVENTORY,
        status=TenantMappingSpec.STATUS_PUBLISHED,
    ).values_list("spec", flat=True).first()
    return spec if isinstance(spec, dict) else {}


def _extract_observed_flags_from_db(*, db: Database, extension_name: str) -> dict[str, bool | None]:
    try:
        snapshot_obj: DatabaseExtensionsSnapshot = db.extensions_snapshot
        raw_snapshot = snapshot_obj.snapshot or {}
    except DatabaseExtensionsSnapshot.DoesNotExist:
        return {"active": None, "safe_mode": None, "unsafe_action_protection": None}

    payload = normalize_extensions_snapshot(raw_snapshot)
    if payload.get("parse_error"):
        return {"active": None, "safe_mode": None, "unsafe_action_protection": None}

    spec = _get_published_extensions_mapping_spec(str(db.tenant_id))
    canonical = build_canonical_extensions_inventory(payload, spec)
    extensions = canonical.get("extensions")
    if not isinstance(extensions, list):
        return {"active": None, "safe_mode": None, "unsafe_action_protection": None}

    found = None
    for item in extensions:
        if not isinstance(item, dict):
            continue
        if str(item.get("name") or "").strip() != extension_name:
            continue
        found = item
        break
    if found is None:
        return {"active": None, "safe_mode": None, "unsafe_action_protection": None}

    active = found.get("is_active")
    if not isinstance(active, bool):
        active = None
    safe_mode = found.get("safe_mode")
    if not isinstance(safe_mode, bool):
        safe_mode = None
    unsafe_action_protection = found.get("unsafe_action_protection")
    if not isinstance(unsafe_action_protection, bool):
        unsafe_action_protection = None

    return {
        "active": active,
        "safe_mode": safe_mode,
        "unsafe_action_protection": unsafe_action_protection,
    }


@extend_schema(
    tags=["v2"],
    summary="Extensions flags policy list",
    description="List extensions flags policy for current tenant context.",
    responses={
        200: ExtensionsFlagsPolicyListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_extensions_flags_policy(request):
    if not request.user.has_perm(perms.PERM_DATABASES_VIEW_DATABASE):
        return Response(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "Permission denied"}},
            status=http_status.HTTP_403_FORBIDDEN,
        )

    tenant_id = str(request.tenant_id)
    qs = ExtensionFlagsPolicy.objects.filter(tenant_id=tenant_id).order_by("extension_name")
    return Response({"policies": [_policy_to_dict(obj) for obj in qs]})


@extend_schema(
    tags=["v2"],
    summary="Extensions flags policy upsert",
    description="Upsert flags policy for a single extension name.",
    parameters=[
        OpenApiParameter(name="extension_name", type=str, location=OpenApiParameter.PATH, required=True),
    ],
    request=ExtensionsFlagsPolicyUpsertRequestSerializer,
    responses={
        200: ExtensionsFlagsPolicySerializer,
        400: OpenApiResponse(description="Validation error"),
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def upsert_extensions_flags_policy(request, extension_name: str):
    denied = _require_manage_permission(request)
    if denied:
        return denied
    denied = _require_tenant_header_for_staff_mutating(request)
    if denied:
        return denied

    serializer = ExtensionsFlagsPolicyUpsertRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    tenant_id = str(request.tenant_id)
    ext_name = str(extension_name or "").strip()
    if not ext_name:
        return Response(
            {"success": False, "error": {"code": "INVALID_PARAMETER", "message": "extension_name is required"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    obj, created = ExtensionFlagsPolicy.objects.get_or_create(
        tenant_id=tenant_id,
        extension_name=ext_name,
        defaults={"created_by": request.user, "updated_by": request.user},
    )
    obj.active = serializer.validated_data["active"]
    obj.safe_mode = serializer.validated_data["safe_mode"]
    obj.unsafe_action_protection = serializer.validated_data["unsafe_action_protection"]
    obj.updated_by = request.user
    obj.save(update_fields=["active", "safe_mode", "unsafe_action_protection", "updated_by", "updated_at"])

    log_admin_action(
        request,
        action="extensions.flags_policy.upsert",
        outcome="success",
        target_type="extensions.flags_policy",
        target_id=obj.extension_name,
        metadata={
            "tenant_id": tenant_id,
            "created": bool(created),
            "reason": serializer.validated_data.get("reason"),
        },
    )

    return Response(_policy_to_dict(obj))


@extend_schema(
    tags=["v2"],
    summary="Extensions flags policy adopt",
    description="Adopt flags policy for a single extension name from a database observed snapshot.",
    request=ExtensionsFlagsPolicyAdoptRequestSerializer,
    responses={
        200: ExtensionsFlagsPolicySerializer,
        400: OpenApiResponse(description="Validation error"),
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: OpenApiResponse(description="Not found"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def adopt_extensions_flags_policy(request):
    denied = _require_manage_permission(request)
    if denied:
        return denied
    denied = _require_tenant_header_for_staff_mutating(request)
    if denied:
        return denied

    serializer = ExtensionsFlagsPolicyAdoptRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    tenant_id = str(request.tenant_id)
    database_id = str(serializer.validated_data["database_id"])
    extension_name = str(serializer.validated_data["extension_name"] or "").strip()
    if not extension_name:
        return Response(
            {"success": False, "error": {"code": "INVALID_PARAMETER", "message": "extension_name is required"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    # NOTE: Database.objects is tenant-scoped (by tenant context).
    db = Database.objects.filter(id=database_id).select_related("cluster").first()
    if db is None:
        return Response(
            {"success": False, "error": {"code": "DATABASE_NOT_FOUND", "message": "Database not found"}},
            status=http_status.HTTP_404_NOT_FOUND,
        )
    if not _is_staff(request.user):
        allowed = PermissionService.filter_accessible_databases(
            request.user,
            Database.objects.filter(id=db.id),
            PermissionLevel.VIEW,
        ).exists()
        if not allowed:
            return Response(
                {"success": False, "error": {"code": "FORBIDDEN", "message": "Permission denied"}},
                status=http_status.HTTP_403_FORBIDDEN,
            )

    observed = _extract_observed_flags_from_db(db=db, extension_name=extension_name)

    obj, created = ExtensionFlagsPolicy.objects.get_or_create(
        tenant_id=tenant_id,
        extension_name=extension_name,
        defaults={"created_by": request.user, "updated_by": request.user},
    )
    obj.active = observed["active"]
    obj.safe_mode = observed["safe_mode"]
    obj.unsafe_action_protection = observed["unsafe_action_protection"]
    obj.updated_by = request.user
    obj.save(update_fields=["active", "safe_mode", "unsafe_action_protection", "updated_by", "updated_at"])

    log_admin_action(
        request,
        action="extensions.flags_policy.adopt",
        outcome="success",
        target_type="extensions.flags_policy",
        target_id=obj.extension_name,
        metadata={
            "tenant_id": tenant_id,
            "database_id": database_id,
            "created": bool(created),
            "reason": serializer.validated_data.get("reason"),
        },
    )

    return Response(_policy_to_dict(obj))
