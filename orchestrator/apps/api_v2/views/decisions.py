from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core import permission_codes as perms
from apps.api_v2.serializers.common import ErrorResponseSerializer
from apps.templates.workflow.decision_tables import (
    build_decision_table_contract,
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
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class DecisionTableListResponseSerializer(serializers.Serializer):
    decisions = DecisionTableReadSerializer(many=True)
    count = serializers.IntegerField()


class DecisionTableDetailResponseSerializer(serializers.Serializer):
    decision = DecisionTableReadSerializer()


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


def _serialize_decision_table(decision_table: DecisionTable) -> dict[str, Any]:
    contract = build_decision_table_contract(decision_table=decision_table)
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
        "created_at": decision_table.created_at,
        "updated_at": decision_table.updated_at,
    }


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
    if request.method == "GET":
        decisions = list(
            DecisionTable.objects.select_related("parent_version")
            .order_by("decision_table_id", "-version_number", "-created_at")
        )
        payload = {
            "decisions": [_serialize_decision_table(item) for item in decisions],
            "count": len(decisions),
        }
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
        decision = create_decision_table_revision(
            contract=serializer.validated_data,
            created_by=request.user,
        )
    except ValueError as exc:
        return Response(
            {
                "success": False,
                "error": {
                    "code": "CREATE_ERROR",
                    "message": str(exc),
                },
            },
            status=400,
        )

    return Response({"decision": _serialize_decision_table(decision)}, status=201)


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
    return Response({"decision": _serialize_decision_table(decision)}, status=200)
