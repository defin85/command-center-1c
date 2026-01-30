"""
Tenant-scoped mapping endpoints (MVP: extensions_inventory).
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.mappings.extensions_inventory import build_canonical_extensions_inventory, validate_extensions_inventory
from apps.mappings.models import TenantMappingSpec
from apps.operations.models import CommandResultSnapshot
from apps.tenancy.models import TenantMember


def _tenant_admin_required(request):
    tenant_id = str(request.tenant_id)
    is_tenant_admin = TenantMember.objects.filter(user_id=request.user.id, tenant_id=tenant_id, role=TenantMember.ROLE_ADMIN).exists()
    if not (request.user.is_staff or is_tenant_admin):
        return None, Response(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "Tenant admin only"}},
            status=status.HTTP_403_FORBIDDEN,
        )
    return tenant_id, None


class MappingSpecSerializer(serializers.Serializer):
    entity_kind = serializers.CharField()
    status = serializers.ChoiceField(choices=["draft", "published"])
    spec = serializers.JSONField()


@extend_schema(
    tags=["v2"],
    summary="Get mapping spec",
    parameters=[
        OpenApiParameter(name="entity_kind", type=str, required=True),
        OpenApiParameter(name="status", type=str, required=False, description="draft|published (default published)"),
    ],
    responses={
        200: MappingSpecSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: OpenApiResponse(description="Not found"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_mapping_spec(request):
    tenant_id, err = _tenant_admin_required(request)
    if err:
        return err

    entity_kind = str(request.query_params.get("entity_kind") or "").strip()
    if not entity_kind:
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "entity_kind is required"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    status_value = str(request.query_params.get("status") or "").strip() or TenantMappingSpec.STATUS_PUBLISHED
    if status_value not in {TenantMappingSpec.STATUS_DRAFT, TenantMappingSpec.STATUS_PUBLISHED}:
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "invalid status"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    row = TenantMappingSpec.objects.filter(tenant_id=tenant_id, entity_kind=entity_kind, status=status_value).values("entity_kind", "status", "spec").first()
    if row is None:
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Mapping not found"}},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(row)


class UpsertMappingSpecRequestSerializer(serializers.Serializer):
    entity_kind = serializers.CharField()
    status = serializers.ChoiceField(choices=["draft", "published"])
    spec = serializers.JSONField()


@extend_schema(
    tags=["v2"],
    summary="Upsert mapping spec",
    request=UpsertMappingSpecRequestSerializer,
    responses={
        200: MappingSpecSerializer,
        400: OpenApiResponse(description="Validation error"),
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def upsert_mapping_spec(request):
    tenant_id, err = _tenant_admin_required(request)
    if err:
        return err

    serializer = UpsertMappingSpecRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": serializer.errors}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    entity_kind = serializer.validated_data["entity_kind"].strip()
    status_value = serializer.validated_data["status"]
    spec = serializer.validated_data["spec"]

    row, _ = TenantMappingSpec.objects.update_or_create(
        tenant_id=tenant_id,
        entity_kind=entity_kind,
        status=status_value,
        defaults={"spec": spec},
    )
    return Response({"entity_kind": row.entity_kind, "status": row.status, "spec": row.spec})


class PreviewMappingRequestSerializer(serializers.Serializer):
    entity_kind = serializers.CharField()
    snapshot_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=["draft", "published"], required=False)


class PreviewMappingResponseSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    errors = serializers.ListField(child=serializers.CharField())
    canonical = serializers.JSONField()


@extend_schema(
    tags=["v2"],
    summary="Preview mapping against snapshot",
    description="Apply mapping to saved snapshot and validate canonical schema.",
    request=PreviewMappingRequestSerializer,
    responses={
        200: PreviewMappingResponseSerializer,
        400: OpenApiResponse(description="Validation error"),
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: OpenApiResponse(description="Not found"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def preview_mapping(request):
    tenant_id, err = _tenant_admin_required(request)
    if err:
        return err

    serializer = PreviewMappingRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": serializer.errors}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    entity_kind = serializer.validated_data["entity_kind"].strip()
    snapshot_id = serializer.validated_data["snapshot_id"]
    status_value = serializer.validated_data.get("status") or TenantMappingSpec.STATUS_PUBLISHED

    spec_row = TenantMappingSpec.objects.filter(tenant_id=tenant_id, entity_kind=entity_kind, status=status_value).values_list("spec", flat=True).first()
    spec = spec_row if isinstance(spec_row, dict) else {}

    snap = CommandResultSnapshot.objects.filter(tenant_id=tenant_id, id=snapshot_id).values_list("normalized_payload", flat=True).first()
    if snap is None:
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Snapshot not found"}},
            status=status.HTTP_404_NOT_FOUND,
        )

    if entity_kind == TenantMappingSpec.ENTITY_EXTENSIONS_INVENTORY:
        canonical = build_canonical_extensions_inventory(snap, spec)
        errors = validate_extensions_inventory(canonical)
        return Response({"ok": not errors, "errors": errors, "canonical": canonical})

    return Response(
        {"success": False, "error": {"code": "NOT_SUPPORTED", "message": f"Unsupported entity_kind: {entity_kind}"}},
        status=status.HTTP_400_BAD_REQUEST,
    )
