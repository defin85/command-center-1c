"""
Template sync endpoint for API v2.

Legacy template CRUD/list endpoints were decommissioned.
"""

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.api_v2.serializers.common import ErrorResponseSerializer
from apps.core import permission_codes as perms
from apps.operations.services.admin_action_audit import log_admin_action
from apps.templates.models import OperationExposure
from apps.templates.operation_catalog_service import serialize_template_exposure, upsert_template_exposure
from apps.templates.registry import get_registry


def _permission_denied(message: str):
    return Response(
        {"success": False, "error": {"code": "PERMISSION_DENIED", "message": message}},
        status=403,
    )


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
    description='Synchronize template exposures (`OperationExposure` + `OperationDefinition`) with the in-code operation registry. Requires templates.manage_operation_template.',
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

    Synchronize template exposures with the operation registry.

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
