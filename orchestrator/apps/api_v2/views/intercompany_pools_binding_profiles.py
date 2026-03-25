from __future__ import annotations

from uuid import UUID

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.api_v2.serializers.common import ProblemDetailsErrorSerializer
from apps.intercompany_pools.binding_profile_topology_compatibility import (
    EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED,
)
from apps.intercompany_pools.binding_profiles_store import (
    BindingProfileCodeConflictError,
    BindingProfileLifecycleConflictError,
    BindingProfileNotFoundError,
    BindingProfileStoreError,
    BindingProfileTopologyCompatibilityError,
    create_canonical_binding_profile,
    deactivate_canonical_binding_profile,
    get_canonical_binding_profile,
    list_canonical_binding_profiles,
    revise_canonical_binding_profile,
)
from apps.tenancy.models import Tenant

from .intercompany_pools import (
    ExecutionPackTopologyCompatibilitySummarySerializer,
    _problem,
    _resolve_tenant_id,
)


class BindingProfileWorkflowDefinitionRefSerializer(serializers.Serializer):
    contract_version = serializers.CharField(required=False)
    workflow_definition_key = serializers.CharField()
    workflow_revision_id = serializers.CharField()
    workflow_revision = serializers.IntegerField(min_value=1)
    workflow_name = serializers.CharField()


class BindingProfileDecisionRefSerializer(serializers.Serializer):
    decision_table_id = serializers.CharField()
    decision_key = serializers.CharField()
    slot_key = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    decision_revision = serializers.IntegerField(min_value=1)


class BindingProfileRevisionWriteSerializer(serializers.Serializer):
    contract_version = serializers.CharField(required=False, allow_blank=False, default="binding_profile_revision.v1")
    workflow = BindingProfileWorkflowDefinitionRefSerializer()
    decisions = BindingProfileDecisionRefSerializer(many=True, required=False, default=list)
    parameters = serializers.JSONField(required=False, default=dict)
    role_mapping = serializers.DictField(child=serializers.CharField(), required=False, default=dict)
    metadata = serializers.JSONField(required=False, default=dict)


class BindingProfileRevisionReadSerializer(BindingProfileRevisionWriteSerializer):
    binding_profile_revision_id = serializers.CharField(required=True, allow_blank=False)
    binding_profile_id = serializers.UUIDField(required=True)
    revision_number = serializers.IntegerField(min_value=1, required=True)
    topology_template_compatibility = ExecutionPackTopologyCompatibilitySummarySerializer(required=True)
    created_by = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField(required=True)


class BindingProfileSummarySerializer(serializers.Serializer):
    binding_profile_id = serializers.UUIDField(required=True)
    code = serializers.SlugField(max_length=128)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=["active", "deactivated"])
    latest_revision_number = serializers.IntegerField(min_value=1)
    latest_revision = BindingProfileRevisionReadSerializer()
    created_by = serializers.CharField(required=False, allow_blank=True)
    updated_by = serializers.CharField(required=False, allow_blank=True)
    deactivated_by = serializers.CharField(required=False, allow_blank=True)
    deactivated_at = serializers.DateTimeField(required=False, allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class BindingProfileUsageRevisionSummarySerializer(serializers.Serializer):
    binding_profile_revision_id = serializers.CharField(required=True, allow_blank=False)
    binding_profile_revision_number = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    attachment_count = serializers.IntegerField(min_value=0, required=True)


class BindingProfileUsageAttachmentSerializer(serializers.Serializer):
    pool_id = serializers.UUIDField(required=True)
    pool_code = serializers.CharField(required=True)
    pool_name = serializers.CharField(required=True)
    binding_id = serializers.CharField(required=True, allow_blank=False)
    attachment_revision = serializers.IntegerField(min_value=1, required=True)
    binding_profile_revision_id = serializers.CharField(required=True, allow_blank=False)
    binding_profile_revision_number = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    status = serializers.CharField(required=True)
    selector = serializers.JSONField(required=True)
    effective_from = serializers.DateField(required=True)
    effective_to = serializers.DateField(required=False, allow_null=True)


class BindingProfileUsageSummarySerializer(serializers.Serializer):
    attachment_count = serializers.IntegerField(min_value=0, required=True)
    revision_summary = BindingProfileUsageRevisionSummarySerializer(many=True)
    attachments = BindingProfileUsageAttachmentSerializer(many=True)


class BindingProfileDetailSerializer(BindingProfileSummarySerializer):
    revisions = BindingProfileRevisionReadSerializer(many=True)
    usage_summary = BindingProfileUsageSummarySerializer()


class BindingProfileCreateRequestSerializer(serializers.Serializer):
    code = serializers.SlugField(max_length=128)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    revision = BindingProfileRevisionWriteSerializer()


class BindingProfileRevisionCreateRequestSerializer(serializers.Serializer):
    revision = BindingProfileRevisionWriteSerializer()


class BindingProfileListResponseSerializer(serializers.Serializer):
    binding_profiles = BindingProfileSummarySerializer(many=True)
    count = serializers.IntegerField()


class BindingProfileDetailResponseSerializer(serializers.Serializer):
    binding_profile = BindingProfileDetailSerializer()


class BindingProfileMutationResponseSerializer(serializers.Serializer):
    binding_profile = BindingProfileDetailSerializer()


def _resolve_tenant(*, tenant_id: str) -> Tenant | None:
    return Tenant.objects.filter(id=tenant_id).first()


def _binding_profile_store_problem(exc: BindingProfileStoreError) -> Response:
    if isinstance(exc, BindingProfileCodeConflictError):
        return _problem(
            code="BINDING_PROFILE_CODE_CONFLICT",
            title="Execution Pack Code Conflict",
            detail=str(exc),
            status_code=http_status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, BindingProfileLifecycleConflictError):
        return _problem(
            code="BINDING_PROFILE_LIFECYCLE_CONFLICT",
            title="Execution Pack Lifecycle Conflict",
            detail=str(exc),
            status_code=http_status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, BindingProfileTopologyCompatibilityError):
        return _problem(
            code=EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED,
            title="Execution Pack Topology Alias Required",
            detail=(
                "Execution pack revision is not reusable for template-based topology authoring. "
                "Publish topology-aware decision revisions in /decisions before saving /pools/execution-packs."
            ),
            status_code=http_status.HTTP_400_BAD_REQUEST,
            errors=exc.errors,
        )
    return _problem(
        code="VALIDATION_ERROR",
        title="Validation Error",
        detail=str(exc),
        status_code=http_status.HTTP_400_BAD_REQUEST,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_binding_profiles_list",
    summary="List reusable execution packs",
    responses={
        200: BindingProfileListResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
    methods=["GET"],
)
@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_binding_profiles_create",
    summary="Create reusable execution pack",
    request=BindingProfileCreateRequestSerializer,
    responses={
        201: BindingProfileMutationResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
    methods=["POST"],
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def binding_profiles_collection(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )
    tenant = _resolve_tenant(tenant_id=tenant_id)
    if tenant is None:
        return _problem(
            code="TENANT_NOT_FOUND",
            title="Tenant Not Found",
            detail="Tenant not found in current context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        profiles = list_canonical_binding_profiles(tenant=tenant)
        return Response(
            {
                "binding_profiles": profiles,
                "count": len(profiles),
            },
            status=http_status.HTTP_200_OK,
        )

    serializer = BindingProfileCreateRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(serializer.errors),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    try:
        binding_profile = create_canonical_binding_profile(
            tenant=tenant,
            binding_profile=dict(serializer.validated_data),
            actor_username=request.user.username if request.user and request.user.is_authenticated else "",
        )
    except BindingProfileStoreError as exc:
        return _binding_profile_store_problem(exc)

    return Response(
        {"binding_profile": binding_profile},
        status=http_status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_binding_profiles_detail",
    summary="Get reusable execution pack detail",
    responses={
        200: BindingProfileDetailResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def binding_profile_detail(request, binding_profile_id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )
    tenant = _resolve_tenant(tenant_id=tenant_id)
    if tenant is None:
        return _problem(
            code="TENANT_NOT_FOUND",
            title="Tenant Not Found",
            detail="Tenant not found in current context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    try:
        binding_profile = get_canonical_binding_profile(
            tenant=tenant,
            binding_profile_id=str(binding_profile_id),
        )
    except BindingProfileNotFoundError:
        return _problem(
            code="BINDING_PROFILE_NOT_FOUND",
            title="Execution Pack Not Found",
            detail="Execution pack not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    except BindingProfileStoreError as exc:
        return _binding_profile_store_problem(exc)

    return Response({"binding_profile": binding_profile}, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_binding_profiles_revise",
    summary="Create a new immutable execution-pack revision",
    request=BindingProfileRevisionCreateRequestSerializer,
    responses={
        201: BindingProfileMutationResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
        (409, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def binding_profile_revisions(request, binding_profile_id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )
    tenant = _resolve_tenant(tenant_id=tenant_id)
    if tenant is None:
        return _problem(
            code="TENANT_NOT_FOUND",
            title="Tenant Not Found",
            detail="Tenant not found in current context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    serializer = BindingProfileRevisionCreateRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(serializer.errors),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    try:
        binding_profile = revise_canonical_binding_profile(
            tenant=tenant,
            binding_profile_id=str(binding_profile_id),
            revision=dict(serializer.validated_data["revision"]),
            actor_username=request.user.username if request.user and request.user.is_authenticated else "",
        )
    except BindingProfileNotFoundError:
        return _problem(
            code="BINDING_PROFILE_NOT_FOUND",
            title="Execution Pack Not Found",
            detail="Execution pack not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    except BindingProfileStoreError as exc:
        return _binding_profile_store_problem(exc)

    return Response({"binding_profile": binding_profile}, status=http_status.HTTP_201_CREATED)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_binding_profiles_deactivate",
    summary="Deactivate reusable execution pack",
    request=None,
    responses={
        200: BindingProfileMutationResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def deactivate_binding_profile(request, binding_profile_id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )
    tenant = _resolve_tenant(tenant_id=tenant_id)
    if tenant is None:
        return _problem(
            code="TENANT_NOT_FOUND",
            title="Tenant Not Found",
            detail="Tenant not found in current context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    try:
        binding_profile = deactivate_canonical_binding_profile(
            tenant=tenant,
            binding_profile_id=str(binding_profile_id),
            actor_username=request.user.username if request.user and request.user.is_authenticated else "",
        )
    except BindingProfileNotFoundError:
        return _problem(
            code="BINDING_PROFILE_NOT_FOUND",
            title="Execution Pack Not Found",
            detail="Execution pack not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    except BindingProfileStoreError as exc:
        return _binding_profile_store_problem(exc)

    return Response({"binding_profile": binding_profile}, status=http_status.HTTP_200_OK)
