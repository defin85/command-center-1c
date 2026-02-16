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
from apps.intercompany_pools.runtime_template_registry import (
    get_pool_runtime_template_aliases,
    inspect_pool_runtime_template_registry,
    sync_pool_runtime_template_registry,
)
from apps.operations.services.admin_action_audit import log_admin_action
from apps.templates.models import OperationExposure
from apps.templates.operation_catalog_service import (
    normalize_executor_kind,
    serialize_template_exposure,
    upsert_template_exposure,
    validate_exposure_payload,
)
from apps.templates.registry import get_registry


_SYSTEM_MANAGED_POOL_RUNTIME_ALIASES = set(get_pool_runtime_template_aliases())


def _permission_denied(message: str):
    return Response(
        {"success": False, "error": {"code": "PERMISSION_DENIED", "message": message}},
        status=403,
    )


class OperationTemplateSyncRequestSerializer(serializers.Serializer):
    dry_run = serializers.BooleanField(required=False, default=False)
    include_pool_runtime = serializers.BooleanField(required=False, default=False)


class OperationTemplateSyncResponseSerializer(serializers.Serializer):
    created = serializers.IntegerField()
    updated = serializers.IntegerField()
    unchanged = serializers.IntegerField()
    message = serializers.CharField()


class PoolRuntimeRegistryEntrySerializer(serializers.Serializer):
    alias = serializers.CharField()
    label = serializers.CharField()
    status = serializers.CharField()
    issues = serializers.ListField(child=serializers.CharField())
    exposure_id = serializers.UUIDField(required=False, allow_null=True)
    exposure_revision = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    operation_type = serializers.CharField()
    target_entity = serializers.CharField()
    is_active = serializers.BooleanField()
    exposure_status = serializers.CharField()
    system_managed = serializers.BooleanField()
    domain = serializers.CharField()


class PoolRuntimeRegistryInspectResponseSerializer(serializers.Serializer):
    contract_version = serializers.CharField()
    entries = PoolRuntimeRegistryEntrySerializer(many=True)
    count = serializers.IntegerField()


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
    include_pool_runtime = request_serializer.validated_data.get('include_pool_runtime', False)

    registry = get_registry()
    templates_data = list(registry.get_for_template_sync() or [])
    if not templates_data and not include_pool_runtime:
        log_admin_action(
            request,
            action="templates.sync_from_registry",
            outcome="error",
            target_type="template_registry",
            metadata={"dry_run": dry_run, "include_pool_runtime": include_pool_runtime},
            error_message="REGISTRY_EMPTY",
        )
        return Response({
            'success': False,
            'error': {
                'code': 'REGISTRY_EMPTY',
                'message': 'No operation types registered in registry',
            }
        }, status=400)

    validation_issues: list[dict] = []
    for data in templates_data:
        template_id = str(data.get("id") or "").strip()
        if template_id in _SYSTEM_MANAGED_POOL_RUNTIME_ALIASES:
            continue
        operation_type = str(data.get("operation_type") or "").strip()
        validation_errors = validate_exposure_payload(
            executor_kind=normalize_executor_kind(operation_type),
            definition_payload={
                "operation_type": operation_type,
                "target_entity": str(data.get("target_entity") or "").strip(),
                "template_data": data.get("template_data"),
            },
            capability=f"templates.{operation_type or 'legacy'}",
            capability_config={},
        )
        if validation_errors:
            validation_issues.append(
                {
                    "template_id": template_id,
                    "operation_type": operation_type,
                    "errors": validation_errors,
                }
            )
    if validation_issues:
        log_admin_action(
            request,
            action="templates.sync_from_registry",
            outcome="error",
            target_type="template_registry",
            metadata={
                "dry_run": dry_run,
                "include_pool_runtime": include_pool_runtime,
                "validation_issue_count": len(validation_issues),
            },
            error_message="VALIDATION_ERROR",
        )
        return Response(
            {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Registry templates failed runtime-contract validation",
                    "details": validation_issues,
                },
            },
            status=400,
        )

    created = 0
    updated = 0
    unchanged = 0

    def apply_sync():
        nonlocal created, updated, unchanged

        for data in templates_data:
            template_id = data['id']
            if template_id in _SYSTEM_MANAGED_POOL_RUNTIME_ALIASES:
                unchanged += 1
                continue
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
            if (
                exposure is not None
                and bool(getattr(exposure, "system_managed", False))
                and str(getattr(exposure, "domain", "") or "") == OperationExposure.DOMAIN_POOL_RUNTIME
            ):
                unchanged += 1
                continue
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

    def sync_pool_runtime_aliases() -> None:
        nonlocal created, updated, unchanged
        if not include_pool_runtime:
            return
        pool_runtime_result = sync_pool_runtime_template_registry(dry_run=dry_run)
        created += int(pool_runtime_result.created)
        updated += int(pool_runtime_result.updated)
        unchanged += int(pool_runtime_result.unchanged)

    if dry_run:
        apply_sync()
        sync_pool_runtime_aliases()
    else:
        with transaction.atomic():
            apply_sync()
            sync_pool_runtime_aliases()

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
            "include_pool_runtime": include_pool_runtime,
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


@extend_schema(
    tags=["v2"],
    summary="Inspect pool runtime template registry",
    description="Read-only diagnostics for system-managed pool runtime template aliases.",
    responses={
        200: PoolRuntimeRegistryInspectResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def inspect_pool_runtime_registry(request):
    if not getattr(request.user, "is_staff", False):
        return _permission_denied("Staff only")

    entries = inspect_pool_runtime_template_registry()
    payload = {
        "contract_version": "pool_runtime.v1",
        "entries": [
            {
                "alias": item.alias,
                "label": item.label,
                "status": item.status,
                "issues": list(item.issues),
                "exposure_id": item.exposure_id,
                "exposure_revision": item.exposure_revision,
                "operation_type": item.operation_type,
                "target_entity": item.target_entity,
                "is_active": item.is_active,
                "exposure_status": item.exposure_status,
                "system_managed": item.system_managed,
                "domain": item.domain,
            }
            for item in entries
        ],
        "count": len(entries),
    }
    return Response(payload)
