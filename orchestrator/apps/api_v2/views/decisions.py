from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core import permission_codes as perms
from apps.api_v2.serializers.common import ErrorResponseSerializer
from apps.api_v2.views.databases.common import _resolve_tenant_id as _resolve_default_tenant_id
from apps.databases.models import Database
from apps.intercompany_pools.document_policy_contract import (
    DOCUMENT_POLICY_METADATA_KEY,
    validate_document_policy_v1,
)
from apps.intercompany_pools.metadata_catalog import (
    MetadataCatalogError,
    build_metadata_catalog_api_payload,
    describe_metadata_catalog_snapshot_resolution,
    read_metadata_catalog_snapshot,
    validate_document_policy_references,
)
from apps.templates.workflow.decision_tables import (
    assess_decision_table_metadata_compatibility,
    build_decision_table_contract,
    build_decision_table_metadata_context,
    create_decision_table_revision,
)
from apps.templates.workflow.models import DecisionTable


class DecisionFieldSerializer(serializers.Serializer):
    name = serializers.CharField()
    value_type = serializers.CharField()
    required = serializers.BooleanField(required=False, default=True)


class DecisionRuleSerializer(serializers.Serializer):
    rule_id = serializers.CharField()
    conditions = serializers.JSONField(required=False, default=dict)
    outputs = serializers.JSONField()
    priority = serializers.IntegerField(required=False, default=0)


class DecisionTableWriteSerializer(serializers.Serializer):
    database_id = serializers.CharField(required=False)
    decision_table_id = serializers.CharField(required=False)
    decision_key = serializers.CharField(required=False)
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True, default="")
    inputs = DecisionFieldSerializer(many=True, required=False, default=list)
    outputs = DecisionFieldSerializer(many=True, required=False, default=list)
    rules = DecisionRuleSerializer(many=True)
    hit_policy = serializers.CharField(required=False, default="first_match")
    validation_mode = serializers.CharField(required=False, default="fail_closed")
    is_active = serializers.BooleanField(required=False, default=True)
    parent_version_id = serializers.UUIDField(required=False)


class DecisionTableContextQuerySerializer(serializers.Serializer):
    database_id = serializers.CharField(required=False)


class DecisionMetadataContextSerializer(serializers.Serializer):
    database_id = serializers.CharField()
    snapshot_id = serializers.CharField()
    source = serializers.CharField()
    fetched_at = serializers.DateTimeField()
    catalog_version = serializers.CharField()
    config_name = serializers.CharField()
    config_version = serializers.CharField()
    config_generation_id = serializers.CharField(required=False, allow_blank=True)
    extensions_fingerprint = serializers.CharField()
    metadata_hash = serializers.CharField()
    observed_metadata_hash = serializers.CharField(required=False, allow_blank=True)
    publication_drift = serializers.BooleanField(required=False)
    resolution_mode = serializers.CharField()
    is_shared_snapshot = serializers.BooleanField()
    provenance_database_id = serializers.CharField()
    provenance_confirmed_at = serializers.DateTimeField()
    documents = serializers.JSONField()


class DecisionRevisionMetadataContextSerializer(serializers.Serializer):
    database_id = serializers.CharField(required=False)
    snapshot_id = serializers.CharField(required=False)
    config_name = serializers.CharField(required=False)
    config_version = serializers.CharField(required=False)
    config_generation_id = serializers.CharField(required=False)
    extensions_fingerprint = serializers.CharField(required=False)
    metadata_hash = serializers.CharField(required=False)
    observed_metadata_hash = serializers.CharField(required=False)
    publication_drift = serializers.BooleanField(required=False)
    resolution_mode = serializers.CharField(required=False)
    is_shared_snapshot = serializers.BooleanField(required=False)
    provenance_database_id = serializers.CharField(required=False)
    provenance_confirmed_at = serializers.CharField(required=False)


class DecisionMetadataCompatibilitySerializer(serializers.Serializer):
    status = serializers.CharField()
    reason = serializers.CharField(required=False, allow_null=True)
    is_compatible = serializers.BooleanField()


class DecisionTableReadSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    decision_table_id = serializers.CharField()
    decision_key = serializers.CharField()
    decision_revision = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    inputs = DecisionFieldSerializer(many=True)
    outputs = DecisionFieldSerializer(many=True)
    rules = DecisionRuleSerializer(many=True)
    hit_policy = serializers.CharField()
    validation_mode = serializers.CharField()
    is_active = serializers.BooleanField()
    parent_version = serializers.UUIDField(required=False, allow_null=True)
    metadata_context = DecisionRevisionMetadataContextSerializer(required=False, allow_null=True)
    metadata_compatibility = DecisionMetadataCompatibilitySerializer(required=False, allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class DecisionTableListResponseSerializer(serializers.Serializer):
    decisions = DecisionTableReadSerializer(many=True)
    count = serializers.IntegerField()
    metadata_context = DecisionMetadataContextSerializer(required=False)


class DecisionTableDetailResponseSerializer(serializers.Serializer):
    decision = DecisionTableReadSerializer()
    metadata_context = DecisionMetadataContextSerializer(required=False)


def _permission_denied() -> Response:
    return Response(
        {
            "success": False,
            "error": {
                "code": "PERMISSION_DENIED",
                "message": "You do not have permission to manage decisions.",
            },
        },
        status=403,
    )


def _error(*, code: str, message: str, status: int) -> Response:
    return Response(
        {
            "success": False,
            "error": {
                "code": code,
                "message": message,
            },
        },
        status=status,
    )


def _resolve_tenant_id(request) -> str | None:
    header_value = str(
        request.headers.get("X-CC1C-Tenant-ID")
        or request.META.get("HTTP_X_CC1C_TENANT_ID")
        or ""
    ).strip()
    if header_value:
        return header_value
    return _resolve_default_tenant_id(request)


def _serialize_decision_table(
    decision_table: DecisionTable,
    *,
    metadata_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = build_decision_table_contract(decision_table=decision_table)
    stored_metadata_context = build_decision_table_metadata_context(
        metadata_context=decision_table.metadata_context
        if isinstance(decision_table.metadata_context, dict)
        else None
    )
    metadata_compatibility = assess_decision_table_metadata_compatibility(
        decision_table=decision_table,
        metadata_context=metadata_context,
    )
    return {
        "id": str(decision_table.id),
        "decision_table_id": contract.decision_table_id,
        "decision_key": contract.decision_key,
        "decision_revision": contract.decision_revision,
        "name": contract.name,
        "description": decision_table.description,
        "inputs": [field.model_dump(mode="json") for field in contract.inputs],
        "outputs": [field.model_dump(mode="json") for field in contract.outputs],
        "rules": [rule.model_dump(mode="json") for rule in contract.rules],
        "hit_policy": contract.hit_policy.value,
        "validation_mode": contract.validation_mode.value,
        "is_active": decision_table.is_active,
        "parent_version": str(decision_table.parent_version_id) if decision_table.parent_version_id else None,
        "metadata_context": stored_metadata_context,
        "metadata_compatibility": metadata_compatibility,
        "created_at": decision_table.created_at,
        "updated_at": decision_table.updated_at,
    }


def _resolve_metadata_context(
    *,
    request,
    database_id: str | None,
) -> tuple[dict[str, Any] | None, Any | None, Response | None]:
    normalized_database_id = str(database_id or "").strip()
    if not normalized_database_id:
        return None, None, None

    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return None, None, _error(
            code="TENANT_CONTEXT_REQUIRED",
            message="X-CC1C-Tenant-ID is required.",
            status=400,
        )

    database = Database.objects.filter(id=normalized_database_id, tenant_id=tenant_id).first()
    if database is None:
        return None, None, _error(
            code="DATABASE_NOT_FOUND",
            message="Database not found in current tenant context.",
            status=404,
        )

    try:
        snapshot, source = read_metadata_catalog_snapshot(
            tenant_id=tenant_id,
            database=database,
            requested_by_username=str(getattr(request.user, "username", "") or "").strip(),
            allow_cold_bootstrap=True,
        )
    except MetadataCatalogError as exc:
        return None, None, _error(code=exc.code, message=exc.detail, status=exc.status_code)

    resolution = describe_metadata_catalog_snapshot_resolution(
        tenant_id=tenant_id,
        database=database,
        snapshot=snapshot,
    )
    payload = build_metadata_catalog_api_payload(
        database=database,
        snapshot=snapshot,
        source=source,
        resolution=resolution,
    )
    return payload, snapshot, None


def _normalize_document_policy_payload(
    *,
    payload: dict[str, Any],
    snapshot,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    if str(payload.get("decision_key") or "").strip() != DOCUMENT_POLICY_METADATA_KEY or snapshot is None:
        return payload, []

    normalized_payload = dict(payload)
    normalized_rules: list[dict[str, Any]] = []
    referential_errors: list[dict[str, str]] = []
    for rule_index, raw_rule in enumerate(list(payload.get("rules") or [])):
        rule = dict(raw_rule)
        outputs = dict(rule.get("outputs") or {})
        normalized_policy = validate_document_policy_v1(
            policy=outputs.get(DOCUMENT_POLICY_METADATA_KEY)
        )
        referential_errors.extend(
            validate_document_policy_references(
                policy=normalized_policy,
                snapshot=snapshot,
                path_prefix=f"rules[{rule_index}].outputs.{DOCUMENT_POLICY_METADATA_KEY}",
            )
        )
        outputs[DOCUMENT_POLICY_METADATA_KEY] = normalized_policy
        rule["outputs"] = outputs
        normalized_rules.append(rule)
    normalized_payload["rules"] = normalized_rules
    return normalized_payload, referential_errors


def _requires_document_policy_metadata_context(*, payload: dict[str, Any]) -> bool:
    return str(payload.get("decision_key") or "").strip() == DOCUMENT_POLICY_METADATA_KEY


@extend_schema(
    tags=["v2"],
    operation_id="v2_decisions_collection",
    summary="List or create decision tables",
    request=DecisionTableWriteSerializer,
    responses={
        200: DecisionTableListResponseSerializer,
        201: DecisionTableDetailResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: ErrorResponseSerializer,
    },
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def decisions_collection(request):
    metadata_context_serializer = (
        DecisionTableContextQuerySerializer(data=request.query_params)
        if request.method == "GET"
        else DecisionTableContextQuerySerializer(data=request.data or {})
    )
    if not metadata_context_serializer.is_valid():
        return _error(
            code="VALIDATION_ERROR",
            message=str(metadata_context_serializer.errors),
            status=400,
        )
    metadata_context, snapshot, metadata_error = _resolve_metadata_context(
        request=request,
        database_id=metadata_context_serializer.validated_data.get("database_id"),
    )
    if metadata_error is not None:
        return metadata_error

    if request.method == "GET":
        decisions = list(
            DecisionTable.objects.select_related("parent_version")
            .order_by("decision_table_id", "-version_number", "-created_at")
        )
        payload = {
            "decisions": [
                _serialize_decision_table(item, metadata_context=metadata_context)
                for item in decisions
            ],
            "count": len(decisions),
        }
        if metadata_context is not None:
            payload["metadata_context"] = metadata_context
        return Response(payload, status=200)

    if not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_WORKFLOW_TEMPLATE):
        return _permission_denied()

    serializer = DecisionTableWriteSerializer(data=request.data or {})
    if not serializer.is_valid():
        return Response(
            {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(serializer.errors),
                },
            },
            status=400,
        )

    try:
        normalized_payload = dict(serializer.validated_data)
        normalized_payload.pop("database_id", None)
        if _requires_document_policy_metadata_context(payload=normalized_payload) and metadata_context is None:
            return _error(
                code="POOL_METADATA_CONTEXT_REQUIRED",
                message="database_id is required for document_policy decision authoring.",
                status=400,
            )
        normalized_payload, referential_errors = _normalize_document_policy_payload(
            payload=normalized_payload,
            snapshot=snapshot,
        )
        if referential_errors:
            first_error = referential_errors[0]
            return _error(
                code=str(first_error.get("code") or "VALIDATION_ERROR"),
                message=str(first_error.get("detail") or "Document policy references are invalid."),
                status=400,
            )
        normalized_payload["metadata_context"] = build_decision_table_metadata_context(
            metadata_context=metadata_context,
        )
        decision = create_decision_table_revision(
            contract=normalized_payload,
            created_by=request.user,
        )
    except ValueError as exc:
        return _error(
            code="CREATE_ERROR",
            message=str(exc),
            status=400,
        )

    payload = {"decision": _serialize_decision_table(decision, metadata_context=metadata_context)}
    if metadata_context is not None:
        payload["metadata_context"] = metadata_context
    return Response(payload, status=201)


@extend_schema(
    tags=["v2"],
    operation_id="v2_decisions_detail",
    summary="Get decision table detail",
    responses={
        200: DecisionTableDetailResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: ErrorResponseSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def decision_detail(request, decision_id):
    context_serializer = DecisionTableContextQuerySerializer(data=request.query_params)
    if not context_serializer.is_valid():
        return _error(
            code="VALIDATION_ERROR",
            message=str(context_serializer.errors),
            status=400,
        )
    metadata_context, _snapshot, metadata_error = _resolve_metadata_context(
        request=request,
        database_id=context_serializer.validated_data.get("database_id"),
    )
    if metadata_error is not None:
        return metadata_error

    decision = (
        DecisionTable.objects.select_related("parent_version")
        .filter(id=decision_id)
        .first()
    )
    if decision is None:
        return Response(
            {
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Decision table was not found.",
                },
            },
            status=404,
        )
    payload = {"decision": _serialize_decision_table(decision, metadata_context=metadata_context)}
    if metadata_context is not None:
        payload["metadata_context"] = metadata_context
    return Response(payload, status=200)
