"""Workflow template catalog endpoints."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import logging

from django.db import close_old_connections
from django.db.models import Count, Q
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

import uuid

from apps.core import permission_codes as perms
from apps.databases.models import PermissionLevel
from apps.templates.rbac import TemplatePermissionService
from apps.templates.workflow.models import WorkflowTemplate, WorkflowExecution, WorkflowStepResult
from apps.templates.workflow.serializers import (
    WorkflowTemplateListSerializer,
    WorkflowTemplateDetailSerializer,
    WorkflowExecutionListSerializer,
    WorkflowExecutionDetailSerializer,
    WorkflowStepResultSerializer,
)
from apps.api_v2.serializers.common import ErrorResponseSerializer, ExecutionBindingSerializer, ExecutionPlanSerializer
from apps.operations.utils.feature_flags import is_go_workflow_engine_enabled

logger = logging.getLogger(__name__)

from .common import (
    _permission_denied,
)


class TemplateListItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    category = serializers.CharField()
    icon = serializers.CharField(required=False, allow_blank=True)
    workflow_type = serializers.CharField()
    version_number = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class TemplateListResponseSerializer(serializers.Serializer):
    templates = TemplateListItemSerializer(many=True)
    count = serializers.IntegerField()


class TemplateSchemaResponseSerializer(serializers.Serializer):
    workflow_id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    category = serializers.CharField()
    icon = serializers.CharField(required=False, allow_blank=True)
    input_schema = serializers.JSONField(required=False, allow_null=True)

@extend_schema(
    tags=['v2'],
    summary='List workflow templates for Operations Center',
    description='List all active workflow templates available for Operations Center (is_template=true, is_active=true).',
    parameters=[
        OpenApiParameter(
            name='category', type=str, required=False,
            description='Filter by category (ras, odata, system, custom)'
        ),
        OpenApiParameter(
            name='search', type=str, required=False,
            description='Search by name or description'
        ),
    ],
    responses={
        200: TemplateListResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_templates(request):
    """
    GET /api/v2/workflows/list-templates/

    List all workflow templates available for Operations Center.

    Query Parameters:
        - category: Filter by category (ras, odata, system, custom)
        - search: Search by name or description

    Response:
        {
            "templates": [...],
            "count": 10
        }
    """
    if not request.user.has_perm(perms.PERM_TEMPLATES_VIEW_WORKFLOW_TEMPLATE):
        return _permission_denied("You do not have permission to view workflows.")

    category = request.query_params.get('category')
    search = request.query_params.get('search')

    # Only show active templates marked for Operations Center
    qs = WorkflowTemplate.objects.filter(
        is_template=True,
        is_active=True,
        is_valid=True,
    )

    if category:
        qs = qs.filter(category=category)

    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    qs = qs.order_by('category', 'name')

    if not request.user.is_staff:
        qs = TemplatePermissionService.filter_accessible_workflow_templates(
            request.user,
            qs,
            min_level=PermissionLevel.VIEW,
        )

    templates_data = []
    for template in qs:
        templates_data.append({
            'id': template.id,
            'name': template.name,
            'description': template.description,
            'category': template.category,
            'icon': template.icon,
            'workflow_type': template.workflow_type,
            'version_number': template.version_number,
            'created_at': template.created_at,
        })

    logger.debug(
        "Listed workflow templates for Operations Center",
        extra={
            'user': request.user.username,
            'category': category,
            'search': search,
            'count': len(templates_data),
        }
    )

    return Response({
        'templates': templates_data,
        'count': len(templates_data),
    })


@extend_schema(
    tags=['v2'],
    summary='Get workflow template schema',
    description='Get the input schema for a specific workflow template (for dynamic form generation).',
    parameters=[
        OpenApiParameter(
            name='workflow_id', type=str, required=True,
            description='Workflow template UUID'
        ),
    ],
    responses={
        200: TemplateSchemaResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_template_schema(request):
    """
    GET /api/v2/workflows/get-template-schema/?workflow_id=X

    Get the input schema for a workflow template.

    Query Parameters:
        - workflow_id: Workflow template UUID (required)

    Response:
        {
            "workflow_id": "uuid",
            "name": "Template Name",
            "description": "...",
            "category": "ras",
            "icon": "PlayCircleOutlined",
            "input_schema": {...}
        }
    """
    workflow_id = request.query_params.get('workflow_id')

    if not workflow_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'workflow_id is required'
            }
        }, status=400)

    # Validate UUID format
    try:
        uuid.UUID(workflow_id)
    except ValueError:
        return Response({
            'success': False,
            'error': {
                'code': 'INVALID_UUID',
                'message': 'workflow_id must be a valid UUID'
            }
        }, status=400)

    try:
        template = WorkflowTemplate.objects.get(
            id=workflow_id,
            is_template=True,
            is_active=True,
        )
    except WorkflowTemplate.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'TEMPLATE_NOT_FOUND',
                'message': 'Workflow template not found or not available for Operations Center'
            }
        }, status=404)

    if not request.user.has_perm(perms.PERM_TEMPLATES_VIEW_WORKFLOW_TEMPLATE, template):
        return _permission_denied("You do not have permission to access this workflow.")

    logger.info(
        "Retrieved workflow template schema",
        extra={
            'user': request.user.username,
            'workflow_id': str(workflow_id),
            'template_name': template.name,
        }
    )

    return Response({
        'workflow_id': str(template.id),
        'name': template.name,
        'description': template.description,
        'category': template.category,
        'icon': template.icon,
        'input_schema': template.input_schema,
    })
