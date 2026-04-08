from __future__ import annotations

from typing import Any
from uuid import UUID

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.api_v2.serializers.common import ProblemDetailsErrorSerializer
from apps.api_v2.observability import (
    apply_correlation_headers,
    log_problem_response,
    with_problem_correlation,
)
from apps.api_v2.views.databases.common import _resolve_tenant_id as _resolve_default_tenant_id
from apps.intercompany_pools.document_policy_migrations import (
    DocumentPolicyMigrationError,
    migrate_legacy_edge_document_policy,
)
from apps.intercompany_pools.models import OrganizationPool, PoolEdgeVersion
from apps.templates.workflow.decision_tables import (
    build_decision_table_contract,
    build_decision_table_metadata_context,
)
from apps.templates.workflow.models import DecisionTable


class PoolDocumentPolicyMigrationRequestSerializer(serializers.Serializer):
    edge_version_id = serializers.UUIDField()
    decision_table_id = serializers.CharField(required=False, allow_blank=True, default="")
    name = serializers.CharField(required=False, allow_blank=True, default="")
    description = serializers.CharField(required=False, allow_blank=True, default="")


class PoolDocumentPolicyMigrationDecisionRefSerializer(serializers.Serializer):
    decision_id = serializers.UUIDField()
    decision_table_id = serializers.CharField()
    decision_revision = serializers.IntegerField(min_value=1)


class PoolDocumentPolicyMigrationBindingDecisionRefSerializer(serializers.Serializer):
    decision_table_id = serializers.CharField()
    decision_key = serializers.CharField()
    slot_key = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    decision_revision = serializers.IntegerField(min_value=1)


class PoolDocumentPolicyMigrationAffectedBindingSerializer(serializers.Serializer):
    binding_id = serializers.CharField()
    revision = serializers.IntegerField(min_value=1)
    updated = serializers.BooleanField()
    decision_ref = PoolDocumentPolicyMigrationBindingDecisionRefSerializer()


class PoolDocumentPolicyMigrationSourceSerializer(serializers.Serializer):
    kind = serializers.CharField()
    source_path = serializers.CharField()
    pool_id = serializers.UUIDField()
    pool_code = serializers.CharField()
    edge_version_id = serializers.UUIDField()
    parent_node_version_id = serializers.UUIDField()
    child_node_version_id = serializers.UUIDField()
    parent_organization_id = serializers.UUIDField()
    child_organization_id = serializers.UUIDField()
    parent_organization_name = serializers.CharField()
    child_organization_name = serializers.CharField()
    child_database_id = serializers.UUIDField()
    effective_from = serializers.DateField()
    effective_to = serializers.DateField(required=False, allow_null=True)
    legacy_policy_hash = serializers.CharField()


class PoolDocumentPolicyMigrationReportSerializer(serializers.Serializer):
    created = serializers.BooleanField()
    reused_existing_revision = serializers.BooleanField()
    binding_update_required = serializers.BooleanField()
    slot_key = serializers.CharField()
    legacy_payload_removed = serializers.BooleanField()
    source = PoolDocumentPolicyMigrationSourceSerializer()
    decision_ref = PoolDocumentPolicyMigrationDecisionRefSerializer()
    affected_bindings = PoolDocumentPolicyMigrationAffectedBindingSerializer(many=True)


class PoolDocumentPolicyMigrationDecisionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    decision_table_id = serializers.CharField()
    decision_key = serializers.CharField()
    decision_revision = serializers.IntegerField(min_value=1)
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    inputs = serializers.JSONField()
    outputs = serializers.JSONField()
    rules = serializers.JSONField()
    hit_policy = serializers.CharField()
    validation_mode = serializers.CharField()
    is_active = serializers.BooleanField()
    parent_version = serializers.UUIDField(required=False, allow_null=True)
    metadata_context = serializers.JSONField(required=False, allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class PoolDocumentPolicyMigrationResponseSerializer(serializers.Serializer):
    decision = PoolDocumentPolicyMigrationDecisionSerializer()
    metadata_context = serializers.JSONField()
    migration = PoolDocumentPolicyMigrationReportSerializer()


def _resolve_tenant_id(request) -> str | None:
    header_value = str(
        request.headers.get("X-CC1C-Tenant-ID")
        or request.META.get("HTTP_X_CC1C_TENANT_ID")
        or ""
    ).strip()
    if header_value:
        return header_value
    return _resolve_default_tenant_id(request)


def _problem(*, code: str, title: str, detail: str, status_code: int) -> Response:
    payload = with_problem_correlation(
        {
            "type": "about:blank",
            "title": title,
            "status": status_code,
            "code": code,
            "detail": detail,
        }
    )
    log_problem_response(payload)
    response = Response(
        payload,
        status=status_code,
        content_type="application/problem+json",
    )
    return apply_correlation_headers(response)


def _serialize_decision(decision: DecisionTable) -> dict[str, Any]:
    contract = build_decision_table_contract(decision_table=decision)
    return {
        "id": str(decision.id),
        "decision_table_id": contract.decision_table_id,
        "decision_key": contract.decision_key,
        "decision_revision": contract.decision_revision,
        "name": contract.name,
        "description": decision.description,
        "inputs": [field.model_dump(mode="json") for field in contract.inputs],
        "outputs": [field.model_dump(mode="json") for field in contract.outputs],
        "rules": [rule.model_dump(mode="json") for rule in contract.rules],
        "hit_policy": contract.hit_policy.value,
        "validation_mode": contract.validation_mode.value,
        "is_active": decision.is_active,
        "parent_version": str(decision.parent_version_id) if decision.parent_version_id else None,
        "metadata_context": build_decision_table_metadata_context(
            metadata_context=decision.metadata_context if isinstance(decision.metadata_context, dict) else None
        ),
        "created_at": decision.created_at,
        "updated_at": decision.updated_at,
    }


@extend_schema(
    tags=["v2"],
    operation_id="v2_pools_document_policy_migrate",
    summary="Materialize legacy edge document policy into a decision revision",
    request=PoolDocumentPolicyMigrationRequestSerializer,
    responses={
        200: PoolDocumentPolicyMigrationResponseSerializer,
        201: PoolDocumentPolicyMigrationResponseSerializer,
        (400, "application/problem+json"): ProblemDetailsErrorSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        (404, "application/problem+json"): ProblemDetailsErrorSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def migrate_pool_edge_document_policy(request, pool_id: UUID):
    tenant_id = _resolve_tenant_id(request)
    if not tenant_id:
        return _problem(
            code="TENANT_CONTEXT_REQUIRED",
            title="Tenant Context Required",
            detail="X-CC1C-Tenant-ID is required.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    pool = OrganizationPool.objects.filter(id=pool_id, tenant_id=tenant_id).first()
    if pool is None:
        return _problem(
            code="POOL_NOT_FOUND",
            title="Pool Not Found",
            detail="Organization pool not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    serializer = PoolDocumentPolicyMigrationRequestSerializer(data=request.data or {})
    if not serializer.is_valid():
        return _problem(
            code="VALIDATION_ERROR",
            title="Validation Error",
            detail=str(serializer.errors),
            status_code=http_status.HTTP_400_BAD_REQUEST,
        )

    edge = (
        PoolEdgeVersion.objects.select_related(
            "parent_node__organization",
            "child_node__organization__database",
        )
        .filter(id=serializer.validated_data["edge_version_id"], pool=pool)
        .first()
    )
    if edge is None:
        return _problem(
            code="POOL_EDGE_NOT_FOUND",
            title="Pool Edge Not Found",
            detail="Topology edge not found in current tenant context.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    try:
        result = migrate_legacy_edge_document_policy(
            tenant_id=tenant_id,
            pool=pool,
            edge_version=edge,
            created_by=request.user,
            actor_username=str(getattr(request.user, "username", "") or "").strip(),
            decision_table_id=serializer.validated_data.get("decision_table_id", ""),
            name=serializer.validated_data.get("name", ""),
            description=serializer.validated_data.get("description", ""),
        )
    except DocumentPolicyMigrationError as exc:
        return _problem(
            code=exc.code,
            title="Document Policy Migration Error",
            detail=exc.detail,
            status_code=exc.status_code,
        )

    payload = {
        "decision": _serialize_decision(result.decision),
        "metadata_context": result.metadata_context,
        "migration": result.migration_report,
    }
    response_status = http_status.HTTP_201_CREATED if result.created else http_status.HTTP_200_OK
    return Response(payload, status=response_status)
