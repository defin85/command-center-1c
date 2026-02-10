"""Preferred manual operation template bindings endpoints (tenant-scoped)."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core import permission_codes as perms
from apps.tenancy.authentication import TENANT_HEADER
from apps.templates.manual_operations import is_supported_manual_operation
from apps.templates.models import ManualOperationTemplateBinding, OperationExposure


def _forbidden() -> Response:
    return Response(
        {"success": False, "error": {"code": "FORBIDDEN", "message": "Permission denied"}},
        status=http_status.HTTP_403_FORBIDDEN,
    )


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


def _serialize_binding(row: ManualOperationTemplateBinding) -> dict[str, Any]:
    return {
        "manual_operation": row.manual_operation,
        "template_id": row.template_id,
        "updated_by": str(row.updated_by_id) if row.updated_by_id else None,
        "updated_at": row.updated_at,
    }


def _resolve_template_exposure(*, tenant_id: str, template_id: str) -> OperationExposure | None:
    base = OperationExposure.objects.select_related("definition").filter(
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias=template_id,
    )
    tenant_row = base.filter(tenant_id=tenant_id).first()
    if tenant_row is not None:
        return tenant_row
    return base.filter(tenant__isnull=True).first()


class ManualOperationBindingSerializer(serializers.Serializer):
    manual_operation = serializers.CharField()
    template_id = serializers.CharField()
    updated_by = serializers.CharField(required=False, allow_null=True)
    updated_at = serializers.DateTimeField()


class ManualOperationBindingListResponseSerializer(serializers.Serializer):
    bindings = ManualOperationBindingSerializer(many=True)


class ManualOperationBindingResponseSerializer(serializers.Serializer):
    binding = ManualOperationBindingSerializer()


class ManualOperationBindingDeleteResponseSerializer(serializers.Serializer):
    deleted = serializers.BooleanField()
    manual_operation = serializers.CharField()


class ManualOperationBindingUpsertRequestSerializer(serializers.Serializer):
    template_id = serializers.CharField()


@extend_schema(
    tags=["v2"],
    summary="List preferred manual operation bindings",
    description="List preferred template bindings for manual operations in current tenant.",
    responses={
        200: ManualOperationBindingListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_manual_operation_bindings(request):
    if not request.user.has_perm(perms.PERM_DATABASES_VIEW_DATABASE):
        return _forbidden()

    tenant_id = str(request.tenant_id)
    rows = (
        ManualOperationTemplateBinding.objects.filter(tenant_id=tenant_id)
        .select_related("updated_by")
        .order_by("manual_operation")
    )
    return Response({"bindings": [_serialize_binding(row) for row in rows]})


def _upsert_manual_operation_binding(request, manual_operation: str):
    if not request.user.has_perm(perms.PERM_DATABASES_MANAGE_DATABASE):
        return _forbidden()
    denied = _require_tenant_header_for_staff_mutating(request)
    if denied:
        return denied

    op_key = str(manual_operation or "").strip()
    if not is_supported_manual_operation(op_key):
        return Response(
            {"success": False, "error": {"code": "INVALID_PARAMETER", "message": "unknown manual_operation"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    serializer = ManualOperationBindingUpsertRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    template_id = str(serializer.validated_data.get("template_id") or "").strip()
    if not template_id:
        return Response(
            {"success": False, "error": {"code": "INVALID_PARAMETER", "message": "template_id is required"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    tenant_id = str(request.tenant_id)
    exposure = _resolve_template_exposure(tenant_id=tenant_id, template_id=template_id)
    if exposure is None:
        return Response(
            {"success": False, "error": {"code": "INVALID_PARAMETER", "message": "template_id not found"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    capability = str(exposure.capability or "").strip()
    if capability != op_key:
        return Response(
            {"success": False, "error": {"code": "CONFIGURATION_ERROR", "message": "template is not compatible with manual_operation"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    row, _ = ManualOperationTemplateBinding.objects.update_or_create(
        tenant_id=tenant_id,
        manual_operation=op_key,
        defaults={
            "template_id": template_id,
            "updated_by": request.user,
        },
    )
    return Response({"binding": _serialize_binding(row)})


def _delete_manual_operation_binding(request, manual_operation: str):
    if not request.user.has_perm(perms.PERM_DATABASES_MANAGE_DATABASE):
        return _forbidden()
    denied = _require_tenant_header_for_staff_mutating(request)
    if denied:
        return denied

    op_key = str(manual_operation or "").strip()
    if not is_supported_manual_operation(op_key):
        return Response(
            {"success": False, "error": {"code": "INVALID_PARAMETER", "message": "unknown manual_operation"}},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    tenant_id = str(request.tenant_id)
    deleted, _ = ManualOperationTemplateBinding.objects.filter(
        tenant_id=tenant_id,
        manual_operation=op_key,
    ).delete()
    return Response({"deleted": bool(deleted), "manual_operation": op_key})


@extend_schema(
    methods=["PUT"],
    tags=["v2"],
    summary="Upsert preferred manual operation binding",
    description="Upsert preferred template binding for the manual operation.",
    parameters=[
        OpenApiParameter(name="manual_operation", location=OpenApiParameter.PATH, required=True, type=str),
    ],
    request=ManualOperationBindingUpsertRequestSerializer,
    responses={
        200: ManualOperationBindingResponseSerializer,
        400: OpenApiResponse(description="Validation/configuration error"),
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@extend_schema(
    methods=["DELETE"],
    tags=["v2"],
    summary="Delete preferred manual operation binding",
    description="Delete preferred template binding for the manual operation.",
    parameters=[
        OpenApiParameter(name="manual_operation", location=OpenApiParameter.PATH, required=True, type=str),
    ],
    responses={
        200: ManualOperationBindingDeleteResponseSerializer,
        400: OpenApiResponse(description="Validation error"),
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def manual_operation_binding_detail(request, manual_operation: str):
    if request.method == "PUT":
        return _upsert_manual_operation_binding(request, manual_operation)
    return _delete_manual_operation_binding(request, manual_operation)
