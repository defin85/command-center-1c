"""
Template management endpoints for API v2.

Provides action-based endpoints for operation template management.
"""

import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers

from apps.templates.models import OperationTemplate

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
