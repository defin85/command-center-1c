"""
Template management endpoints for API v2.

Provides action-based endpoints for operation template management.
"""

import hashlib
import json
import logging
import re

from django.db import transaction
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.api_v2.serializers.common import ErrorResponseSerializer
from apps.core import permission_codes as perms
from apps.databases.models import PermissionLevel
from apps.templates.models import OperationExposure, OperationTemplate
from apps.templates.operation_catalog_service import (
    delete_template_exposure,
    list_template_exposures_queryset,
    serialize_template_exposure,
    upsert_template_exposure,
)
from apps.templates.rbac import TemplatePermissionService
from apps.templates.registry import get_registry
from apps.operations.services.admin_action_audit import log_admin_action

logger = logging.getLogger(__name__)


def _permission_denied(message: str):
    return Response(
        {"success": False, "error": {"code": "PERMISSION_DENIED", "message": message}},
        status=403,
    )


class OperationTemplateSerializer(serializers.Serializer):
    """Serializer for template exposure materialized from unified operation catalog."""

    id = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True, required=False)
    operation_type = serializers.CharField()
    target_entity = serializers.CharField()
    template_data = serializers.JSONField()
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class OperationTemplateWriteSerializer(serializers.Serializer):
    id = serializers.CharField(required=False)
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    operation_type = serializers.CharField()
    target_entity = serializers.CharField()
    template_data = serializers.JSONField()
    is_active = serializers.BooleanField(default=True)

    def validate(self, attrs):
        if not attrs.get("name"):
            raise serializers.ValidationError("name is required")
        if not attrs.get("operation_type"):
            raise serializers.ValidationError("operation_type is required")
        if not attrs.get("template_data"):
            raise serializers.ValidationError("template_data is required")
        return attrs


class OperationTemplateIdSerializer(serializers.Serializer):
    template_id = serializers.CharField()


# =============================================================================
# Response Serializers for OpenAPI documentation
# =============================================================================

class OperationTemplateListResponseSerializer(serializers.Serializer):
    """Response for list_templates endpoint."""
    templates = OperationTemplateSerializer(many=True, help_text="List of operation templates")
    count = serializers.IntegerField(help_text="Number of templates in current page")
    total = serializers.IntegerField(help_text="Total number of templates matching filters")


class OperationTemplateDetailResponseSerializer(serializers.Serializer):
    template = OperationTemplateSerializer()


TEMPLATE_FILTER_FIELDS = {
    "name": {"field": "label", "type": "text"},
    "description": {"field": "description", "type": "text"},
    "operation_type": {"field": "definition__executor_payload__operation_type", "type": "enum"},
    "target_entity": {"field": "definition__executor_payload__target_entity", "type": "enum"},
    "is_active": {"field": "is_active", "type": "bool"},
    "created_at": {"field": "created_at", "type": "datetime"},
    "updated_at": {"field": "updated_at", "type": "datetime"},
}

TEMPLATE_SORT_FIELDS = {
    "name": "label",
    "operation_type": "definition__executor_payload__operation_type",
    "target_entity": "definition__executor_payload__target_entity",
    "is_active": "is_active",
    "created_at": "created_at",
    "updated_at": "updated_at",
}


def _parse_filters(raw_filters: str | None) -> tuple[dict, dict | None]:
    if not raw_filters:
        return {}, None
    try:
        payload = json.loads(raw_filters)
    except json.JSONDecodeError:
        return {}, {
            "code": "INVALID_FILTERS",
            "message": "filters must be valid JSON object",
        }
    if not isinstance(payload, dict):
        return {}, {
            "code": "INVALID_FILTERS",
            "message": "filters must be a JSON object",
        }
    return payload, None


def _parse_sort(raw_sort: str | None) -> tuple[dict | None, dict | None]:
    if not raw_sort:
        return None, None
    try:
        payload = json.loads(raw_sort)
    except json.JSONDecodeError:
        return None, {
            "code": "INVALID_SORT",
            "message": "sort must be valid JSON object",
        }
    if not isinstance(payload, dict):
        return None, {
            "code": "INVALID_SORT",
            "message": "sort must be a JSON object",
        }
    return payload, None


def _apply_text_filter(qs, field: str, op: str, value: str):
    if op == "contains":
        return qs.filter(**{f"{field}__icontains": value})
    if op == "eq":
        return qs.filter(**{field: value})
    return qs


def _apply_datetime_filter(qs, field: str, op: str, value: str):
    parsed = parse_datetime(value)
    if op in ("contains", "eq") and parsed is None:
        return qs.filter(**{f"{field}__icontains": value})
    if parsed:
        if op == "eq":
            return qs.filter(**{f"{field}__date": parsed.date()})
        if op == "before":
            return qs.filter(**{f"{field}__date__lt": parsed.date()})
        if op == "after":
            return qs.filter(**{f"{field}__date__gt": parsed.date()})
    return qs


def _apply_enum_filter(qs, field: str, op: str, value):
    if op == "in" and isinstance(value, list):
        return qs.filter(**{f"{field}__in": value})
    return qs.filter(**{field: value})


def _apply_bool_filter(qs, field: str, value):
    if isinstance(value, bool):
        return qs.filter(**{field: value})
    if isinstance(value, str):
        return qs.filter(**{field: value.lower() in ("true", "1", "yes")})
    return qs


def _apply_filters(qs, filters: dict) -> tuple:
    for key, payload in filters.items():
        if key not in TEMPLATE_FILTER_FIELDS:
            return qs, {
                "code": "UNKNOWN_FILTER",
                "message": f"Unknown filter key: {key}",
            }
        value = payload
        op = "eq"
        if isinstance(payload, dict):
            op = payload.get("op", "eq")
            value = payload.get("value")
        if value in (None, ""):
            continue
        config = TEMPLATE_FILTER_FIELDS[key]
        field = config["field"]
        field_type = config["type"]
        if field_type == "text":
            qs = _apply_text_filter(qs, field, op, str(value))
        elif field_type == "enum":
            qs = _apply_enum_filter(qs, field, op, value)
        elif field_type == "bool":
            qs = _apply_bool_filter(qs, field, value)
        elif field_type == "datetime":
            qs = _apply_datetime_filter(qs, field, op, str(value))
    return qs, None


def _apply_sort(qs, sort_payload: dict | None) -> tuple:
    if not sort_payload:
        return qs, None
    key = sort_payload.get("key")
    order = sort_payload.get("order")
    if key not in TEMPLATE_SORT_FIELDS:
        return qs, {
            "code": "UNKNOWN_SORT",
            "message": f"Unknown sort key: {key}",
        }
    field = TEMPLATE_SORT_FIELDS[key]
    if order == "desc":
        return qs.order_by(f"-{field}"), None
    if order == "asc":
        return qs.order_by(field), None
    return qs, {
        "code": "INVALID_SORT",
        "message": "sort order must be 'asc' or 'desc'",
    }


@extend_schema(
    tags=['v2'],
    summary='List operation templates',
    description='List all operation templates with optional filtering by type, target entity, and active status.',
    parameters=[
        OpenApiParameter(name='operation_type', type=str, required=False, description='Filter by operation type'),
        OpenApiParameter(name='target_entity', type=str, required=False, description='Filter by target entity'),
        OpenApiParameter(name='is_active', type=bool, required=False, description='Filter by active status (true/false)'),
        OpenApiParameter(name='search', type=str, required=False, description='Search by name or description'),
        OpenApiParameter(name='filters', type=str, required=False, description='JSON object with filter conditions'),
        OpenApiParameter(name='sort', type=str, required=False, description='JSON object with sort configuration'),
        OpenApiParameter(name='limit', type=int, required=False, description='Maximum results (default: 50, max: 1000)'),
        OpenApiParameter(name='offset', type=int, required=False, description='Pagination offset (default: 0)'),
    ],
    responses={
        200: OperationTemplateListResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_templates(request):
    """
    GET /api/v2/templates/list-templates/

    List all operation templates with optional filtering.

    Query Parameters:
        - operation_type: Filter by operation type
        - target_entity: Filter by target entity
        - is_active: Filter by active status (true/false)
        - search: Search by name or description
        - filters: JSON object with filter conditions
        - sort: JSON object with sort configuration
        - limit: Maximum results (default: 50)
        - offset: Pagination offset (default: 0)

    Response:
        {
            "templates": [...],
            "count": N,
            "total": N
        }
    """
    if not request.user.has_perm(perms.PERM_TEMPLATES_VIEW_OPERATION_TEMPLATE):
        return _permission_denied("You do not have permission to view templates.")

    operation_type = request.query_params.get('operation_type')
    target_entity = request.query_params.get('target_entity')
    is_active = request.query_params.get('is_active')
    search = request.query_params.get('search')
    raw_filters = request.query_params.get('filters')
    raw_sort = request.query_params.get('sort')

    # Safely parse integer parameters with validation
    try:
        limit = int(request.query_params.get('limit', 50))
        limit = max(1, min(limit, 1000))  # Clamp to [1, 1000]
    except (ValueError, TypeError):
        limit = 50

    try:
        offset = int(request.query_params.get('offset', 0))
        offset = max(0, offset)
    except (ValueError, TypeError):
        offset = 0

    qs = list_template_exposures_queryset()

    # Apply filters
    if operation_type:
        qs = qs.filter(definition__executor_payload__operation_type=operation_type)
    if target_entity:
        qs = qs.filter(definition__executor_payload__target_entity=target_entity)
    if is_active is not None:
        # Parse boolean from string
        is_active_bool = is_active.lower() in ('true', '1', 'yes')
        qs = qs.filter(is_active=is_active_bool)

    if search:
        qs = qs.filter(Q(label__icontains=search) | Q(description__icontains=search))

    filters_payload, filters_error = _parse_filters(raw_filters)
    if filters_error:
        return Response({"success": False, "error": filters_error}, status=400)
    if filters_payload:
        qs, apply_error = _apply_filters(qs, filters_payload)
        if apply_error:
            return Response({"success": False, "error": apply_error}, status=400)

    sort_payload, sort_error = _parse_sort(raw_sort)
    if sort_error:
        return Response({"success": False, "error": sort_error}, status=400)
    if sort_payload:
        qs, apply_sort_error = _apply_sort(qs, sort_payload)
        if apply_sort_error:
            return Response({"success": False, "error": apply_sort_error}, status=400)
    else:
        qs = qs.order_by('name')

    if not request.user.is_staff:
        allowed_templates_qs = TemplatePermissionService.filter_accessible_operation_templates(
            request.user,
            OperationTemplate.objects.all(),
            min_level=PermissionLevel.VIEW,
        )
        allowed_ids = list(allowed_templates_qs.values_list("id", flat=True))
        qs = qs.filter(alias__in=allowed_ids)

    total = qs.count()

    # Apply pagination
    qs = qs[offset:offset + limit]

    serialized_rows = [serialize_template_exposure(exposure) for exposure in qs]
    serializer = OperationTemplateSerializer(serialized_rows, many=True)

    return Response({
        'templates': serializer.data,
        'count': len(serializer.data),
        'total': total,
    })


def _generate_template_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        slug = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    base = f"tpl-custom-{slug}"
    exists_base = OperationExposure.objects.filter(
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias=base,
        tenant__isnull=True,
    ).exists()
    if not exists_base:
        return base
    counter = 2
    while OperationExposure.objects.filter(
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias=f"{base}-{counter}",
        tenant__isnull=True,
    ).exists():
        counter += 1
    return f"{base}-{counter}"


def _validate_operation_type(value: str) -> dict | None:
    registry = get_registry()
    if registry.get_all() and not registry.is_valid(value):
        return {
            "code": "UNKNOWN_OPERATION",
            "message": f"Unknown operation_type: {value}",
        }
    return None


@extend_schema(
    tags=['v2'],
    summary='Create operation template',
    description='Create a custom operation template. Requires templates.manage_operation_template.',
    request=OperationTemplateWriteSerializer,
    responses={
        200: OperationTemplateDetailResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_template(request):
    if not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_OPERATION_TEMPLATE):
        return _permission_denied("You do not have permission to manage templates.")

    serializer = OperationTemplateWriteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=400)

    data = serializer.validated_data
    template_id = data.get("id") or _generate_template_id(data["name"])
    op_error = _validate_operation_type(data["operation_type"])
    if op_error:
        return Response({"success": False, "error": op_error}, status=400)

    if OperationExposure.objects.filter(
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias=template_id,
        tenant__isnull=True,
    ).exists():
        return Response({
            "success": False,
            "error": {"code": "TEMPLATE_EXISTS", "message": f"Template {template_id} already exists"},
        }, status=400)

    exposure, _created = upsert_template_exposure(
        template_id=template_id,
        name=data["name"],
        description=data.get("description", ""),
        operation_type=data["operation_type"],
        target_entity=data["target_entity"],
        template_data=data["template_data"],
        is_active=data.get("is_active", True),
    )

    log_admin_action(
        request,
        action="templates.create",
        outcome="success",
        target_type="operation_template",
        metadata={"template_id": template_id},
    )

    return Response({"template": OperationTemplateSerializer(serialize_template_exposure(exposure)).data})


@extend_schema(
    tags=['v2'],
    summary='Update operation template',
    description='Update an existing operation template. Requires templates.manage_operation_template.',
    request=OperationTemplateWriteSerializer,
    responses={
        200: OperationTemplateDetailResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_template(request):
    serializer = OperationTemplateWriteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=400)

    data = serializer.validated_data
    template_id = data.get("id")
    if not template_id:
        return Response({
            "success": False,
            "error": {"code": "MISSING_ID", "message": "id is required for update"},
        }, status=400)
    op_error = _validate_operation_type(data["operation_type"])
    if op_error:
        return Response({"success": False, "error": op_error}, status=400)

    exposure = (
        OperationExposure.objects.select_related("definition")
        .filter(
            surface=OperationExposure.SURFACE_TEMPLATE,
            alias=template_id,
            tenant__isnull=True,
        )
        .first()
    )
    if exposure is None:
        return Response({
            "success": False,
            "error": {"code": "NOT_FOUND", "message": f"Template {template_id} not found"},
        }, status=404)

    legacy_template = OperationTemplate.objects.filter(id=template_id).first()
    if legacy_template is not None:
        if not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_OPERATION_TEMPLATE, legacy_template):
            return _permission_denied("You do not have permission to manage this template.")
    elif not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_OPERATION_TEMPLATE):
        return _permission_denied("You do not have permission to manage templates.")

    before = serialize_template_exposure(exposure)
    desired = {
        "name": data["name"],
        "description": data.get("description", ""),
        "operation_type": data["operation_type"],
        "target_entity": data["target_entity"],
        "template_data": data["template_data"],
        "is_active": data.get("is_active", True),
    }
    changed = [field for field, value in desired.items() if before.get(field) != value]

    updated_exposure, _created = upsert_template_exposure(
        template_id=template_id,
        name=desired["name"],
        description=desired["description"],
        operation_type=desired["operation_type"],
        target_entity=desired["target_entity"],
        template_data=desired["template_data"],
        is_active=desired["is_active"],
    )

    log_admin_action(
        request,
        action="templates.update",
        outcome="success",
        target_type="operation_template",
        metadata={"template_id": template_id, "changed_fields": changed},
    )

    return Response({"template": OperationTemplateSerializer(serialize_template_exposure(updated_exposure)).data})


@extend_schema(
    tags=['v2'],
    summary='Delete operation template',
    description='Delete an operation template. Requires templates.manage_operation_template.',
    request=OperationTemplateIdSerializer,
    responses={
        200: OperationTemplateDetailResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_template(request):
    serializer = OperationTemplateIdSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=400)

    template_id = serializer.validated_data["template_id"]
    exposure = (
        OperationExposure.objects.select_related("definition")
        .filter(
            surface=OperationExposure.SURFACE_TEMPLATE,
            alias=template_id,
            tenant__isnull=True,
        )
        .first()
    )
    if exposure is None:
        return Response({
            "success": False,
            "error": {"code": "NOT_FOUND", "message": f"Template {template_id} not found"},
        }, status=404)

    legacy_template = OperationTemplate.objects.filter(id=template_id).first()
    if legacy_template is not None:
        if not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_OPERATION_TEMPLATE, legacy_template):
            return _permission_denied("You do not have permission to manage this template.")
    elif not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_OPERATION_TEMPLATE):
        return _permission_denied("You do not have permission to manage templates.")

    deleted_exposure = delete_template_exposure(template_id=template_id)
    if deleted_exposure is None:
        return Response({
            "success": False,
            "error": {"code": "NOT_FOUND", "message": f"Template {template_id} not found"},
        }, status=404)

    log_admin_action(
        request,
        action="templates.delete",
        outcome="success",
        target_type="operation_template",
        metadata={"template_id": template_id},
    )

    return Response({"template": OperationTemplateSerializer(serialize_template_exposure(deleted_exposure)).data})


class OperationTemplateSyncRequestSerializer(serializers.Serializer):
    dry_run = serializers.BooleanField(required=False, default=False)


class OperationTemplateSyncResponseSerializer(serializers.Serializer):
    created = serializers.IntegerField()
    updated = serializers.IntegerField()
    unchanged = serializers.IntegerField()
    message = serializers.CharField()


@extend_schema(
    tags=['v2'],
    summary='Sync templates from registry',
    description='Synchronize OperationTemplate records with the in-code operation registry. Requires templates.manage_operation_template.',
    request=OperationTemplateSyncRequestSerializer,
    responses={
        200: OperationTemplateSyncResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_from_registry(request):
    if not request.user.has_perm(perms.PERM_TEMPLATES_MANAGE_OPERATION_TEMPLATE):
        return _permission_denied("You do not have permission to manage templates.")

    """
    POST /api/v2/templates/sync-from-registry/

    Synchronize OperationTemplate records with the operation registry.

    Request Body (optional):
        { "dry_run": false }

    Response:
        {
            "created": 1,
            "updated": 0,
            "unchanged": 10,
            "message": "Sync completed"
        }
    """
    request_serializer = OperationTemplateSyncRequestSerializer(data=request.data)
    request_serializer.is_valid(raise_exception=True)
    dry_run = request_serializer.validated_data.get('dry_run', False)

    registry = get_registry()
    templates_data = registry.get_for_template_sync()
    if not templates_data:
        log_admin_action(
            request,
            action="templates.sync_from_registry",
            outcome="error",
            target_type="template_registry",
            metadata={"dry_run": dry_run},
            error_message="REGISTRY_EMPTY",
        )
        return Response({
            'success': False,
            'error': {
                'code': 'REGISTRY_EMPTY',
                'message': 'No operation types registered in registry',
            }
        }, status=400)

    created = 0
    updated = 0
    unchanged = 0

    def apply_sync():
        nonlocal created, updated, unchanged

        for data in templates_data:
            template_id = data['id']
            defaults = {
                'name': data.get('name', ''),
                'description': data.get('description', ''),
                'operation_type': data.get('operation_type', ''),
                'target_entity': data.get('target_entity', ''),
                'template_data': data.get('template_data', {}),
                'is_active': data.get('is_active', True),
            }

            exposure = (
                OperationExposure.objects.select_related("definition")
                .filter(
                    surface=OperationExposure.SURFACE_TEMPLATE,
                    alias=template_id,
                    tenant__isnull=True,
                )
                .first()
            )
            if exposure is None:
                created += 1
                if not dry_run:
                    upsert_template_exposure(
                        template_id=template_id,
                        name=defaults["name"],
                        description=defaults["description"],
                        operation_type=defaults["operation_type"],
                        target_entity=defaults["target_entity"],
                        template_data=defaults["template_data"],
                        is_active=defaults["is_active"],
                    )
                continue

            current = serialize_template_exposure(exposure)
            changed_fields = [key for key, value in defaults.items() if current.get(key) != value]
            if not changed_fields:
                unchanged += 1
                continue

            updated += 1
            if not dry_run:
                upsert_template_exposure(
                    template_id=template_id,
                    name=defaults["name"],
                    description=defaults["description"],
                    operation_type=defaults["operation_type"],
                    target_entity=defaults["target_entity"],
                    template_data=defaults["template_data"],
                    is_active=defaults["is_active"],
                )

    if dry_run:
        apply_sync()
    else:
        with transaction.atomic():
            apply_sync()

    if dry_run:
        message = "Dry run completed (no changes applied)"
    else:
        message = "Sync completed"

    log_admin_action(
        request,
        action="templates.sync_from_registry",
        outcome="success",
        target_type="template_registry",
        metadata={
            "dry_run": dry_run,
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
        },
    )

    return Response({
        'created': created,
        'updated': updated,
        'unchanged': unchanged,
        'message': message,
    })
