from __future__ import annotations

from typing import Any

from django.db.models import Q
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.templates.models import OperationDefinition, OperationExposure
from apps.templates.operation_catalog_service import (
    filter_exposures_queryset,
    list_migration_issues_queryset,
    resolve_definition,
    resolve_exposure,
    validate_exposure_payload,
)


def _parse_int(raw: Any, default: int, min_value: int, max_value: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(min_value, min(max_value, value))


def _forbidden_staff_only() -> Response:
    return Response(
        {"success": False, "error": {"code": "FORBIDDEN", "message": "Staff only"}},
        status=http_status.HTTP_403_FORBIDDEN,
    )


def _serialize_definition(definition: OperationDefinition) -> dict[str, Any]:
    return {
        "id": str(definition.id),
        "tenant_scope": definition.tenant_scope,
        "executor_kind": definition.executor_kind,
        "executor_payload": definition.executor_payload if isinstance(definition.executor_payload, dict) else {},
        "contract_version": definition.contract_version,
        "fingerprint": definition.fingerprint,
        "status": definition.status,
        "created_at": definition.created_at,
        "updated_at": definition.updated_at,
    }


def _serialize_exposure(exposure: OperationExposure) -> dict[str, Any]:
    return {
        "id": str(exposure.id),
        "definition_id": str(exposure.definition_id),
        "surface": exposure.surface,
        "alias": exposure.alias,
        "tenant_id": str(exposure.tenant_id) if exposure.tenant_id else None,
        "name": exposure.label,
        "description": exposure.description or None,
        "is_active": exposure.is_active,
        "capability": exposure.capability,
        "contexts": exposure.contexts if isinstance(exposure.contexts, list) else [],
        "display_order": exposure.display_order,
        "capability_config": exposure.capability_config if isinstance(exposure.capability_config, dict) else {},
        "status": exposure.status,
        "created_at": exposure.created_at,
        "updated_at": exposure.updated_at,
    }


class OperationCatalogDefinitionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_scope = serializers.CharField()
    executor_kind = serializers.CharField()
    executor_payload = serializers.JSONField()
    contract_version = serializers.IntegerField()
    fingerprint = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class OperationCatalogExposureSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    definition_id = serializers.UUIDField()
    surface = serializers.CharField()
    alias = serializers.CharField()
    tenant_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    is_active = serializers.BooleanField()
    capability = serializers.CharField(required=False, allow_blank=True)
    contexts = serializers.ListField(child=serializers.CharField(), required=False)
    display_order = serializers.IntegerField(required=False)
    capability_config = serializers.JSONField(required=False)
    status = serializers.CharField()
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class OperationCatalogDefinitionListResponseSerializer(serializers.Serializer):
    definitions = OperationCatalogDefinitionSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class OperationCatalogDefinitionDetailResponseSerializer(serializers.Serializer):
    definition = OperationCatalogDefinitionSerializer()
    exposures = serializers.ListField(child=serializers.JSONField())


class OperationCatalogExposureListResponseSerializer(serializers.Serializer):
    exposures = OperationCatalogExposureSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class OperationCatalogExposureDetailResponseSerializer(serializers.Serializer):
    exposure = OperationCatalogExposureSerializer()
    definition = OperationCatalogDefinitionSerializer()


class OperationCatalogExposureUpsertRequestSerializer(serializers.Serializer):
    exposure_id = serializers.UUIDField(required=False)
    definition_id = serializers.UUIDField(required=False, allow_null=True)
    definition = serializers.JSONField(required=False)
    exposure = serializers.JSONField()


class OperationCatalogValidationErrorSerializer(serializers.Serializer):
    path = serializers.CharField()
    code = serializers.CharField()
    message = serializers.CharField()


class OperationCatalogExposurePublishResponseSerializer(serializers.Serializer):
    published = serializers.BooleanField()
    exposure = OperationCatalogExposureSerializer()
    validation_errors = OperationCatalogValidationErrorSerializer(many=True)


class OperationCatalogValidateRequestSerializer(serializers.Serializer):
    definition = serializers.JSONField(required=False)
    exposure = serializers.JSONField()


class OperationCatalogValidateResponseSerializer(serializers.Serializer):
    valid = serializers.BooleanField()
    errors = OperationCatalogValidationErrorSerializer(many=True)


class OperationCatalogMigrationIssueSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    source_type = serializers.CharField()
    source_id = serializers.CharField()
    tenant_id = serializers.UUIDField(required=False, allow_null=True)
    exposure_id = serializers.UUIDField(required=False, allow_null=True)
    severity = serializers.CharField()
    code = serializers.CharField()
    message = serializers.CharField()
    details = serializers.JSONField()
    created_at = serializers.DateTimeField()


class OperationCatalogMigrationIssuesResponseSerializer(serializers.Serializer):
    issues = OperationCatalogMigrationIssueSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


@extend_schema(
    tags=["v2"],
    summary="List operation definitions",
    responses={
        200: OperationCatalogDefinitionListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_operation_definitions(request):
    if not getattr(request.user, "is_staff", False):
        return _forbidden_staff_only()

    tenant_scope = str(request.query_params.get("tenant_scope") or "").strip()
    executor_kind = str(request.query_params.get("executor_kind") or "").strip()
    status = str(request.query_params.get("status") or "").strip()
    q = str(request.query_params.get("q") or "").strip()
    limit = _parse_int(request.query_params.get("limit"), default=50, min_value=1, max_value=1000)
    offset = _parse_int(request.query_params.get("offset"), default=0, min_value=0, max_value=100000)

    qs = OperationDefinition.objects.all().order_by("tenant_scope", "id")
    if tenant_scope:
        qs = qs.filter(tenant_scope=tenant_scope)
    if executor_kind:
        qs = qs.filter(executor_kind=executor_kind)
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(exposures__alias__icontains=q)
            | Q(exposures__label__icontains=q)
            | Q(exposures__capability__icontains=q)
        ).distinct()

    total = qs.count()
    rows = list(qs[offset:offset + limit])
    payload = [_serialize_definition(row) for row in rows]
    return Response({"definitions": payload, "count": len(payload), "total": total})


@extend_schema(
    tags=["v2"],
    summary="Get operation definition",
    responses={
        200: OperationCatalogDefinitionDetailResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: OpenApiResponse(description="Not found"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_operation_definition(request, definition_id: str):
    if not getattr(request.user, "is_staff", False):
        return _forbidden_staff_only()
    definition = OperationDefinition.objects.filter(id=definition_id).first()
    if definition is None:
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Definition not found"}},
            status=http_status.HTTP_404_NOT_FOUND,
        )
    exposures = list(
        definition.exposures.values("id", "surface", "alias", "status").order_by("surface", "alias")
    )
    for row in exposures:
        row["id"] = str(row["id"])
    return Response({"definition": _serialize_definition(definition), "exposures": exposures})


@extend_schema(
    tags=["v2"],
    summary="List operation exposures",
    responses={
        200: OperationCatalogExposureListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def list_operation_exposures(request):
    if request.method == "POST":
        return _upsert_operation_exposure_impl(request)

    if not getattr(request.user, "is_staff", False):
        return _forbidden_staff_only()

    surface = str(request.query_params.get("surface") or "").strip() or None
    tenant_id = str(request.query_params.get("tenant_id") or "").strip() or None
    capability = str(request.query_params.get("capability") or "").strip() or None
    status = str(request.query_params.get("status") or "").strip() or None
    alias = str(request.query_params.get("alias") or "").strip() or None
    limit = _parse_int(request.query_params.get("limit"), default=50, min_value=1, max_value=1000)
    offset = _parse_int(request.query_params.get("offset"), default=0, min_value=0, max_value=100000)

    qs = filter_exposures_queryset(
        surface=surface,
        tenant_id=tenant_id,
        capability=capability,
        status=status,
        alias=alias,
    )
    total = qs.count()
    rows = list(qs[offset:offset + limit])
    payload = [_serialize_exposure(row) for row in rows]
    return Response({"exposures": payload, "count": len(payload), "total": total})


def _coerce_definition_payload(raw: Any) -> tuple[dict[str, Any], list[dict[str, str]]]:
    if not isinstance(raw, dict):
        return {}, [{"path": "definition", "code": "INVALID", "message": "definition must be an object"}]
    executor_payload = raw.get("executor_payload")
    if not isinstance(executor_payload, dict):
        return {}, [{"path": "definition.executor_payload", "code": "REQUIRED", "message": "executor_payload is required"}]
    return {
        "tenant_scope": str(raw.get("tenant_scope") or "global").strip() or "global",
        "executor_kind": str(raw.get("executor_kind") or "").strip(),
        "executor_payload": executor_payload,
        "contract_version": int(raw.get("contract_version") or 1),
    }, []


def _coerce_exposure_payload(raw: Any) -> tuple[dict[str, Any], list[dict[str, str]]]:
    if not isinstance(raw, dict):
        return {}, [{"path": "exposure", "code": "INVALID", "message": "exposure must be an object"}]
    errors: list[dict[str, str]] = []
    surface = str(raw.get("surface") or "").strip()
    alias = str(raw.get("alias") or "").strip()
    name = str(raw.get("name") or "").strip()
    if not surface:
        errors.append({"path": "exposure.surface", "code": "REQUIRED", "message": "surface is required"})
    if not alias:
        errors.append({"path": "exposure.alias", "code": "REQUIRED", "message": "alias is required"})
    if not name:
        errors.append({"path": "exposure.name", "code": "REQUIRED", "message": "name is required"})
    contexts_raw = raw.get("contexts")
    contexts = [str(v) for v in contexts_raw if isinstance(v, str)] if isinstance(contexts_raw, list) else []
    return {
        "surface": surface,
        "alias": alias,
        "tenant_id": str(raw.get("tenant_id") or "").strip() or None,
        "name": name,
        "description": str(raw.get("description") or ""),
        "is_active": bool(raw.get("is_active", True)),
        "capability": str(raw.get("capability") or "").strip(),
        "contexts": contexts,
        "display_order": int(raw.get("display_order") or 0),
        "capability_config": raw.get("capability_config") if isinstance(raw.get("capability_config"), dict) else {},
        "status": str(raw.get("status") or OperationExposure.STATUS_DRAFT),
    }, errors


@extend_schema(
    tags=["v2"],
    summary="Upsert operation exposure",
    request=OperationCatalogExposureUpsertRequestSerializer,
    responses={
        200: OperationCatalogExposureDetailResponseSerializer,
        400: OpenApiResponse(description="Validation error"),
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upsert_operation_exposure(request):
    return _upsert_operation_exposure_impl(request)


def _upsert_operation_exposure_impl(request):
    if not getattr(request.user, "is_staff", False):
        return _forbidden_staff_only()

    serializer = OperationCatalogExposureUpsertRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    payload = serializer.validated_data

    exposure_payload, exposure_errors = _coerce_exposure_payload(payload.get("exposure"))
    if exposure_errors:
        return Response({"success": False, "error": {"code": "VALIDATION_ERROR", "message": exposure_errors}}, status=400)

    definition_id = payload.get("definition_id")
    definition_obj = None
    definition_payload: dict[str, Any] | None = None
    if definition_id:
        definition_obj = OperationDefinition.objects.filter(id=definition_id).first()
        if definition_obj is None:
            return Response(
                {"success": False, "error": {"code": "NOT_FOUND", "message": "Definition not found"}},
                status=http_status.HTTP_404_NOT_FOUND,
            )
        definition_payload = definition_obj.executor_payload if isinstance(definition_obj.executor_payload, dict) else {}
    else:
        definition_payload, definition_errors = _coerce_definition_payload(payload.get("definition"))
        if definition_errors:
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": definition_errors}},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

    errors = validate_exposure_payload(
        definition_payload=definition_payload or {},
        capability=exposure_payload.get("capability", ""),
        capability_config=exposure_payload.get("capability_config", {}),
    )
    if errors:
        exposure_payload["status"] = OperationExposure.STATUS_INVALID

    if definition_obj is None:
        definition_obj, _ = resolve_definition(
            tenant_scope=definition_payload["tenant_scope"],
            executor_kind=definition_payload["executor_kind"],
            executor_payload=definition_payload["executor_payload"],
            contract_version=definition_payload["contract_version"],
        )

    exposure_obj, _ = resolve_exposure(
        definition=definition_obj,
        surface=exposure_payload["surface"],
        alias=exposure_payload["alias"],
        tenant_id=exposure_payload["tenant_id"],
        label=exposure_payload["name"],
        description=exposure_payload["description"],
        is_active=exposure_payload["is_active"],
        capability=exposure_payload["capability"],
        contexts=exposure_payload["contexts"],
        display_order=exposure_payload["display_order"],
        capability_config=exposure_payload["capability_config"],
        status=exposure_payload["status"],
    )

    return Response({"exposure": _serialize_exposure(exposure_obj), "definition": _serialize_definition(definition_obj)})


@extend_schema(
    tags=["v2"],
    summary="Publish operation exposure",
    responses={
        200: OperationCatalogExposurePublishResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: OpenApiResponse(description="Not found"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def publish_operation_exposure(request, exposure_id: str):
    if not getattr(request.user, "is_staff", False):
        return _forbidden_staff_only()
    exposure = OperationExposure.objects.select_related("definition").filter(id=exposure_id).first()
    if exposure is None:
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Exposure not found"}},
            status=http_status.HTTP_404_NOT_FOUND,
        )
    definition_payload = exposure.definition.executor_payload if isinstance(exposure.definition.executor_payload, dict) else {}
    capability_config = exposure.capability_config if isinstance(exposure.capability_config, dict) else {}
    errors = validate_exposure_payload(
        definition_payload=definition_payload,
        capability=exposure.capability,
        capability_config=capability_config,
    )
    if errors:
        exposure.status = OperationExposure.STATUS_INVALID
        exposure.save(update_fields=["status", "updated_at"])
        return Response({"published": False, "exposure": _serialize_exposure(exposure), "validation_errors": errors})

    exposure.status = OperationExposure.STATUS_PUBLISHED
    exposure.save(update_fields=["status", "updated_at"])
    return Response({"published": True, "exposure": _serialize_exposure(exposure), "validation_errors": []})


@extend_schema(
    tags=["v2"],
    summary="Validate operation exposure",
    request=OperationCatalogValidateRequestSerializer,
    responses={
        200: OperationCatalogValidateResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def validate_operation_exposure(request):
    if not getattr(request.user, "is_staff", False):
        return _forbidden_staff_only()

    serializer = OperationCatalogValidateRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    payload = serializer.validated_data

    exposure_payload, exposure_errors = _coerce_exposure_payload(payload.get("exposure"))
    if exposure_errors:
        return Response({"valid": False, "errors": exposure_errors})

    definition_payload, definition_errors = _coerce_definition_payload(payload.get("definition"))
    if definition_errors:
        return Response({"valid": False, "errors": definition_errors})

    errors = validate_exposure_payload(
        definition_payload=definition_payload["executor_payload"],
        capability=exposure_payload.get("capability", ""),
        capability_config=exposure_payload.get("capability_config", {}),
    )
    return Response({"valid": len(errors) == 0, "errors": errors})


@extend_schema(
    tags=["v2"],
    summary="List operation catalog migration issues",
    responses={
        200: OperationCatalogMigrationIssuesResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_operation_catalog_migration_issues(request):
    if not getattr(request.user, "is_staff", False):
        return _forbidden_staff_only()
    limit = _parse_int(request.query_params.get("limit"), default=50, min_value=1, max_value=1000)
    offset = _parse_int(request.query_params.get("offset"), default=0, min_value=0, max_value=100000)
    qs = list_migration_issues_queryset()
    total = qs.count()
    rows = list(qs[offset:offset + limit])
    issues = [
        {
            "id": str(row.id),
            "source_type": row.source_type,
            "source_id": row.source_id,
            "tenant_id": str(row.tenant_id) if row.tenant_id else None,
            "exposure_id": str(row.exposure_id) if row.exposure_id else None,
            "severity": row.severity,
            "code": row.code,
            "message": row.message,
            "details": row.details if isinstance(row.details, dict) else {},
            "created_at": row.created_at,
        }
        for row in rows
    ]
    return Response({"issues": issues, "count": len(issues), "total": total})
