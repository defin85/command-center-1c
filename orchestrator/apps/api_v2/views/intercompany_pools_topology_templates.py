from __future__ import annotations

from uuid import UUID

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.api_v2.serializers.common import ProblemDetailsErrorSerializer
from apps.intercompany_pools.topology_template_store import (
    TopologyTemplateStoreError,
    create_topology_template,
    create_topology_template_revision,
    list_topology_templates,
    serialize_topology_template,
)

from .intercompany_pools import _problem, _resolve_tenant_id


class TopologyTemplateNodeSerializer(serializers.Serializer):
    slot_key = serializers.CharField()
    label = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    is_root = serializers.BooleanField(required=False, default=False)
    metadata = serializers.JSONField(required=False, default=dict)


class TopologyTemplateEdgeSerializer(serializers.Serializer):
    parent_slot_key = serializers.CharField()
    child_slot_key = serializers.CharField()
    weight = serializers.CharField(required=False)
    min_amount = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    max_amount = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    document_policy_key = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    metadata = serializers.JSONField(required=False, default=dict)


class TopologyTemplateRevisionSerializer(serializers.Serializer):
    topology_template_revision_id = serializers.CharField()
    topology_template_id = serializers.UUIDField()
    revision_number = serializers.IntegerField(min_value=1)
    nodes = TopologyTemplateNodeSerializer(many=True)
    edges = TopologyTemplateEdgeSerializer(many=True)
    metadata = serializers.JSONField(required=False)
    created_at = serializers.DateTimeField()


class TopologyTemplateSerializer(serializers.Serializer):
    topology_template_id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=["active", "deactivated"])
    metadata = serializers.JSONField(required=False)
    latest_revision_number = serializers.IntegerField(min_value=1)
    latest_revision = TopologyTemplateRevisionSerializer()
    revisions = TopologyTemplateRevisionSerializer(many=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class TopologyTemplateListResponseSerializer(serializers.Serializer):
    topology_templates = TopologyTemplateSerializer(many=True)
    count = serializers.IntegerField()


class TopologyTemplateRevisionWriteSerializer(serializers.Serializer):
    nodes = TopologyTemplateNodeSerializer(many=True, allow_empty=False)
    edges = TopologyTemplateEdgeSerializer(many=True, required=False, default=list)
    metadata = serializers.JSONField(required=False, default=dict)


class TopologyTemplateCreateRequestSerializer(serializers.Serializer):
    code = serializers.SlugField(max_length=128)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    metadata = serializers.JSONField(required=False, default=dict)
    revision = TopologyTemplateRevisionWriteSerializer()

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be an object")
        return value


class TopologyTemplateRevisionCreateRequestSerializer(serializers.Serializer):
    revision = TopologyTemplateRevisionWriteSerializer()


class TopologyTemplateMutationResponseSerializer(serializers.Serializer):
    topology_template = TopologyTemplateSerializer()


def _resolve_topology_template_store_error_response(exc: TopologyTemplateStoreError) -> Response:
    status_code = http_status.HTTP_400_BAD_REQUEST
    if exc.code in {"TOPOLOGY_TEMPLATE_NOT_FOUND", "TOPOLOGY_TEMPLATE_REVISION_NOT_FOUND"}:
        status_code = http_status.HTTP_404_NOT_FOUND
    elif exc.code == "VALIDATION_ERROR":
        status_code = http_status.HTTP_400_BAD_REQUEST
    return _problem(
        code=exc.code,
        title="Topology Template Error",
        detail=exc.detail,
        status_code=status_code,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_topology_templates_collection",
    summary="List or create topology templates",
    request=TopologyTemplateCreateRequestSerializer,
    responses={
        200: TopologyTemplateListResponseSerializer,
        201: TopologyTemplateMutationResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def topology_templates_collection(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    if request.method == "GET":
        templates = list_topology_templates(tenant_id=tenant_id)
        serialized = [serialize_topology_template(template) for template in templates]
        return Response(
            {
                "topology_templates": serialized,
                "count": len(serialized),
            },
            status=http_status.HTTP_200_OK,
        )

    serializer = TopologyTemplateCreateRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(serializer.errors),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    try:
        template = create_topology_template(
            tenant_id=tenant_id,
            code=data["code"],
            name=data["name"],
            description=data.get("description", ""),
            metadata=dict(data.get("metadata") or {}),
            revision=dict(data.get("revision") or {}),
            actor_username=getattr(getattr(request, "user", None), "username", "") or "",
        )
    except TopologyTemplateStoreError as exc:
        return _resolve_topology_template_store_error_response(exc)

    return Response(
        {"topology_template": serialize_topology_template(template)},
        status=http_status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_topology_templates_revisions_create",
    summary="Create topology template revision",
    request=TopologyTemplateRevisionCreateRequestSerializer,
    responses={
        201: TopologyTemplateMutationResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def topology_template_revisions(request, topology_template_id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    serializer = TopologyTemplateRevisionCreateRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(serializer.errors),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    try:
        revision = create_topology_template_revision(
            tenant_id=tenant_id,
            topology_template_id=topology_template_id,
            revision=dict(data.get("revision") or {}),
            actor_username=getattr(getattr(request, "user", None), "username", "") or "",
        )
    except TopologyTemplateStoreError as exc:
        return _resolve_topology_template_store_error_response(exc)

    template = revision.template
    return Response(
        {"topology_template": serialize_topology_template(template)},
        status=http_status.HTTP_201_CREATED,
    )
