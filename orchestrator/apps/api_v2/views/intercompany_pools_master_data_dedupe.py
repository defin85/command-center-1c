from __future__ import annotations

from uuid import UUID

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.api_v2.serializers.common import ProblemDetailsErrorSerializer
from apps.intercompany_pools.master_data_dedupe import (
    MASTER_DATA_DEDUPE_INVALID_ACTION,
    apply_pool_master_data_dedupe_review_action,
    get_pool_master_data_dedupe_review_item,
    list_pool_master_data_dedupe_review_items,
    serialize_pool_master_data_dedupe_review_item,
)

from .intercompany_pools import _parse_limit, _problem, _resolve_tenant_id


def _validation_problem(*, detail: str, errors: object | None = None) -> Response:
    return _problem(
        code="VALIDATION_ERROR",
        title="Validation Error",
        detail=detail,
        status_code=http_status.HTTP_400_BAD_REQUEST,
        errors=errors,
    )


class PoolMasterDataDedupeSourceRecordSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    entity_type = serializers.CharField()
    cluster_id = serializers.UUIDField(required=False, allow_null=True)
    source_database_id = serializers.UUIDField(required=False, allow_null=True)
    source_database_name = serializers.CharField(required=False, allow_blank=True)
    source_ref = serializers.CharField()
    source_fingerprint = serializers.CharField(required=False, allow_blank=True)
    source_canonical_id = serializers.CharField(required=False, allow_blank=True)
    canonical_id = serializers.CharField(required=False, allow_blank=True)
    origin_kind = serializers.CharField(required=False, allow_blank=True)
    origin_ref = serializers.CharField(required=False, allow_blank=True)
    resolution_status = serializers.CharField()
    resolution_reason = serializers.CharField(required=False, allow_blank=True)
    normalized_signals = serializers.JSONField(required=False)
    payload_snapshot = serializers.JSONField(required=False)
    metadata = serializers.JSONField(required=False)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class PoolMasterDataDedupeClusterSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    entity_type = serializers.CharField()
    canonical_id = serializers.CharField(required=False, allow_blank=True)
    dedupe_key = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField()
    rollout_eligible = serializers.BooleanField()
    reason_code = serializers.CharField(required=False, allow_blank=True)
    reason_detail = serializers.CharField(required=False, allow_blank=True)
    normalized_signals = serializers.JSONField(required=False)
    conflicting_fields = serializers.ListField(child=serializers.CharField(), required=False)
    resolved_at = serializers.DateTimeField(required=False, allow_null=True)
    resolved_by_id = serializers.UUIDField(required=False, allow_null=True)


class PoolMasterDataDedupeReviewItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    cluster_id = serializers.UUIDField()
    entity_type = serializers.CharField()
    status = serializers.CharField()
    reason_code = serializers.CharField()
    conflicting_fields = serializers.ListField(child=serializers.CharField(), required=False)
    source_snapshot = serializers.JSONField(required=False)
    proposed_survivor_source_record_id = serializers.UUIDField(required=False, allow_null=True)
    cluster = PoolMasterDataDedupeClusterSerializer()
    source_records = PoolMasterDataDedupeSourceRecordSerializer(many=True)
    resolved_at = serializers.DateTimeField(required=False, allow_null=True)
    resolved_by_id = serializers.UUIDField(required=False, allow_null=True)
    resolved_by_username = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)
    metadata = serializers.JSONField(required=False)


class PoolMasterDataDedupeReviewListResponseSerializer(serializers.Serializer):
    items = PoolMasterDataDedupeReviewItemSerializer(many=True)
    count = serializers.IntegerField()
    meta = serializers.JSONField(required=False)


class PoolMasterDataDedupeReviewActionRequestSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=["accept_merge", "choose_survivor", "mark_distinct"],
    )
    source_record_id = serializers.UUIDField(required=False)
    note = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False)


class PoolMasterDataDedupeReviewActionResponseSerializer(serializers.Serializer):
    review_item = PoolMasterDataDedupeReviewItemSerializer()


class PoolMasterDataDedupeReviewListQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=200, default=50)
    offset = serializers.IntegerField(required=False, min_value=0, default=0)
    status = serializers.ChoiceField(
        required=False,
        choices=["pending_review", "resolved_auto", "resolved_manual", "superseded"],
    )
    entity_type = serializers.CharField(required=False, allow_blank=True)
    reason_code = serializers.CharField(required=False, allow_blank=True)
    cluster_id = serializers.UUIDField(required=False)
    database_id = serializers.UUIDField(required=False)


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_dedupe_review_list",
    summary="List master-data dedupe review items",
    parameters=[PoolMasterDataDedupeReviewListQuerySerializer],
    responses={
        200: PoolMasterDataDedupeReviewListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_master_data_dedupe_review_items(request):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    serializer = PoolMasterDataDedupeReviewListQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return _validation_problem(detail="Dedupe review query validation failed.", errors=serializer.errors)
    data = serializer.validated_data
    limit = _parse_limit(request.query_params.get("limit"), default=int(data.get("limit", 50)))
    offset = int(data.get("offset", 0))
    rows, total = list_pool_master_data_dedupe_review_items(
        tenant_id=str(tenant_id),
        status=data.get("status"),
        entity_type=data.get("entity_type"),
        reason_code=data.get("reason_code"),
        cluster_id=str(data.get("cluster_id")) if data.get("cluster_id") is not None else None,
        database_id=str(data.get("database_id")) if data.get("database_id") is not None else None,
        limit=limit,
        offset=offset,
    )
    return Response(
        {
            "items": [serialize_pool_master_data_dedupe_review_item(review_item=item) for item in rows],
            "count": total,
            "meta": {"limit": limit, "offset": offset, "total": total},
        },
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_dedupe_review_get",
    summary="Get master-data dedupe review item",
    responses={
        200: PoolMasterDataDedupeReviewActionResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_master_data_dedupe_review_item(request, id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    try:
        review_item = get_pool_master_data_dedupe_review_item(
            tenant_id=str(tenant_id),
            review_item_id=str(id),
        )
    except LookupError:
        return _problem(
            code="MASTER_DATA_DEDUPE_REVIEW_ITEM_NOT_FOUND",
            title="Master Data Dedupe Review Item Not Found",
            detail="Dedupe review item not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    return Response(
        {"review_item": serialize_pool_master_data_dedupe_review_item(review_item=review_item)},
        status=http_status.HTTP_200_OK,
    )


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_master_data_dedupe_review_action",
    summary="Apply master-data dedupe review action",
    request=PoolMasterDataDedupeReviewActionRequestSerializer,
    responses={
        200: PoolMasterDataDedupeReviewActionResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def apply_master_data_dedupe_review_action_endpoint(request, id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _validation_problem(detail="X-CC1C-Tenant-ID is required.")

    serializer = PoolMasterDataDedupeReviewActionRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _validation_problem(detail="Dedupe review action validation failed.", errors=serializer.errors)
    data = serializer.validated_data

    try:
        review_item = apply_pool_master_data_dedupe_review_action(
            tenant_id=str(tenant_id),
            review_item_id=str(id),
            action=str(data["action"]),
            actor_id=str(request.user.id),
            source_record_id=(
                str(data["source_record_id"])
                if data.get("source_record_id") is not None
                else None
            ),
            note=str(data.get("note") or ""),
            metadata=data.get("metadata"),
        )
    except LookupError:
        return _problem(
            code="MASTER_DATA_DEDUPE_REVIEW_ITEM_NOT_FOUND",
            title="Master Data Dedupe Review Item Not Found",
            detail="Dedupe review item not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    except ValueError as exc:
        code = MASTER_DATA_DEDUPE_INVALID_ACTION if MASTER_DATA_DEDUPE_INVALID_ACTION in str(exc) else "VALIDATION_ERROR"
        return _problem(
            code=code,
            title="Master Data Dedupe Action Invalid",
            detail=str(exc),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {"review_item": serialize_pool_master_data_dedupe_review_item(review_item=review_item)},
        status=http_status.HTTP_200_OK,
    )
