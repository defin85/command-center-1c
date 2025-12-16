"""
Template management endpoints for API v2.

Provides action-based endpoints for operation template management.
"""

import logging

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.api_v2.serializers.common import ErrorResponseSerializer
from apps.templates.models import OperationTemplate
from apps.templates.registry import get_registry
from apps.operations.services.admin_action_audit import log_admin_action

logger = logging.getLogger(__name__)


class OperationTemplateSerializer(serializers.ModelSerializer):
    """Serializer for OperationTemplate model."""

    class Meta:
        model = OperationTemplate
        fields = [
            'id',
            'name',
            'description',
            'operation_type',
            'target_entity',
            'template_data',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# =============================================================================
# Response Serializers for OpenAPI documentation
# =============================================================================

class OperationTemplateListResponseSerializer(serializers.Serializer):
    """Response for list_templates endpoint."""
    templates = OperationTemplateSerializer(many=True, help_text="List of operation templates")
    count = serializers.IntegerField(help_text="Total number of templates (before pagination)")


@extend_schema(
    tags=['v2'],
    summary='List operation templates',
    description='List all operation templates with optional filtering by type, target entity, and active status.',
    parameters=[
        OpenApiParameter(name='operation_type', type=str, required=False, description='Filter by operation type'),
        OpenApiParameter(name='target_entity', type=str, required=False, description='Filter by target entity'),
        OpenApiParameter(name='is_active', type=bool, required=False, description='Filter by active status (true/false)'),
        OpenApiParameter(name='limit', type=int, required=False, description='Maximum results (default: 50, max: 1000)'),
        OpenApiParameter(name='offset', type=int, required=False, description='Pagination offset (default: 0)'),
    ],
    responses={
        200: OperationTemplateListResponseSerializer,
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
        - limit: Maximum results (default: 50)
        - offset: Pagination offset (default: 0)

    Response:
        {
            "templates": [...],
            "count": N
        }
    """
    operation_type = request.query_params.get('operation_type')
    target_entity = request.query_params.get('target_entity')
    is_active = request.query_params.get('is_active')

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

    qs = OperationTemplate.objects.all()

    # Apply filters
    if operation_type:
        qs = qs.filter(operation_type=operation_type)
    if target_entity:
        qs = qs.filter(target_entity=target_entity)
    if is_active is not None:
        # Parse boolean from string
        is_active_bool = is_active.lower() in ('true', '1', 'yes')
        qs = qs.filter(is_active=is_active_bool)

    qs = qs.order_by('name')

    total = qs.count()

    # Apply pagination
    qs = qs[offset:offset + limit]

    serializer = OperationTemplateSerializer(qs, many=True)

    return Response({
        'templates': serializer.data,
        'count': total,
    })


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
    description='Synchronize OperationTemplate records with the in-code operation registry. Staff-only.',
    request=OperationTemplateSyncRequestSerializer,
    responses={
        200: OperationTemplateSyncResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def sync_from_registry(request):
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

            try:
                template = OperationTemplate.objects.get(id=template_id)
            except OperationTemplate.DoesNotExist:
                created += 1
                if not dry_run:
                    OperationTemplate.objects.create(id=template_id, **defaults)
                continue

            changed_fields = [key for key, value in defaults.items() if getattr(template, key) != value]
            if not changed_fields:
                unchanged += 1
                continue

            updated += 1
            if not dry_run:
                for key in changed_fields:
                    setattr(template, key, defaults[key])
                template.save(update_fields=changed_fields)

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
