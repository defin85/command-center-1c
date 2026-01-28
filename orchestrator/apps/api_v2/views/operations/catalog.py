"""Operations endpoint: operation catalog."""

from __future__ import annotations

import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.databases.models import Database, PermissionLevel
from apps.databases.services import PermissionService
from apps.templates.registry import BackendType, get_registry
from apps.templates.workflow.models import WorkflowTemplate

from .schemas import OperationCatalogResponseSerializer

logger = logging.getLogger(__name__)

# =============================================================================
# Operation Catalog Constants
# =============================================================================
OPERATION_CATALOG_DRIVER_ORDER = {
    "ras": 1,
    "odata": 2,
    "cli": 3,
    "ibcmd": 4,
    "workflow": 5,
}

OPERATION_CATALOG_UI_META = {
    "lock_scheduled_jobs": {
        "icon": "LockOutlined",
        "requires_config": False,
    },
    "unlock_scheduled_jobs": {
        "icon": "UnlockOutlined",
        "requires_config": False,
    },
    "block_sessions": {
        "icon": "StopOutlined",
        "requires_config": True,
    },
    "unblock_sessions": {
        "icon": "CheckCircleOutlined",
        "requires_config": False,
    },
    "terminate_sessions": {
        "icon": "CloseCircleOutlined",
        "requires_config": True,
    },
    "designer_cli": {
        "icon": "CodeOutlined",
        "requires_config": True,
    },
    "query": {
        "icon": "SearchOutlined",
        "requires_config": True,
    },
    "sync_cluster": {
        "icon": "SyncOutlined",
        "requires_config": False,
    },
    "health_check": {
        "icon": "HeartOutlined",
        "requires_config": False,
    },
    "ibcmd_cli": {
        "icon": "CodeOutlined",
        "requires_config": True,
    },
}

CLI_OPERATION_IDS = {
    "designer_cli",
}

EXTRA_OPERATION_CATALOG = [
    {
        "id": "sync_cluster",
        "label": "Sync Cluster",
        "description": "Synchronize cluster data with RAS.",
        "driver": "ras",
        "category": "ras",
        "tags": ["cluster", "sync"],
        "requires_config": False,
        "has_ui_form": True,
        "icon": "SyncOutlined",
    },
    {
        "id": "health_check",
        "label": "Health Check",
        "description": "Check database connectivity via OData.",
        "driver": "odata",
        "category": "odata",
        "tags": ["health", "odata"],
        "requires_config": False,
        "has_ui_form": True,
        "icon": "HeartOutlined",
    },
    {
        "id": "ibcmd_cli",
        "label": "IBCMD CLI",
        "description": "Schema-driven IBCMD command execution.",
        "driver": "ibcmd",
        "category": "ibcmd",
        "tags": ["ibcmd", "cli"],
        "requires_config": True,
        "has_ui_form": True,
        "icon": "CodeOutlined",
    },
]

DEPRECATED_OPERATIONS: dict[str, str] = {}



def _resolve_catalog_driver(operation_id: str, backend: BackendType | None) -> str:
    if operation_id in CLI_OPERATION_IDS:
        return "cli"
    if backend == BackendType.RAS:
        return "ras"
    if backend == BackendType.ODATA:
        return "odata"
    if backend == BackendType.IBCMD:
        return "ibcmd"
    if backend == BackendType.CLI:
        return "cli"
    if backend is None:
        return "workflow"
    return str(backend.value)


def _get_deprecated_meta(operation_id: str) -> tuple[bool, str | None]:
    deprecated_message = DEPRECATED_OPERATIONS.get(operation_id)
    if deprecated_message:
        return True, deprecated_message
    return False, None


@extend_schema(
    tags=['v2'],
    summary='Get operations catalog',
    description='List available operation types and workflow templates for Operations Center.',
    responses={
        200: OperationCatalogResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_operation_catalog(request):
    if not request.user.is_staff:
        accessible = PermissionService.filter_accessible_databases(
            request.user,
            Database.objects.all(),
            PermissionLevel.OPERATE,
        )
        if not accessible.exists():
            return Response({
                "items": [],
                "count": 0,
            })

    registry = get_registry()
    items = []
    seen_ids: set[str] = set()

    for op in registry.get_all():
        op_id = op.id
        seen_ids.add(op_id)
        ui_meta = OPERATION_CATALOG_UI_META.get(op_id, {})
        requires_config = ui_meta.get(
            "requires_config",
            bool(op.required_parameters or op.optional_parameters),
        )
        has_ui_form = op_id in OPERATION_CATALOG_UI_META
        driver = _resolve_catalog_driver(op_id, op.backend)
        tags = list(op.tags) if op.tags else []
        if driver and driver not in tags:
            tags.insert(0, driver)
        if op.category and op.category not in tags:
            tags.insert(0, op.category)
        deprecated, deprecated_message = _get_deprecated_meta(op_id)

        items.append({
            "id": op_id,
            "kind": "operation",
            "operation_type": op_id,
            "template_id": None,
            "label": op.name,
            "description": op.description,
            "driver": driver,
            "category": driver,
            "tags": tags,
            "requires_config": requires_config,
            "has_ui_form": has_ui_form,
            "icon": ui_meta.get("icon"),
            "deprecated": deprecated,
            "deprecated_message": deprecated_message,
        })

    for extra in EXTRA_OPERATION_CATALOG:
        op_id = extra["id"]
        if op_id in seen_ids:
            continue
        deprecated, deprecated_message = _get_deprecated_meta(op_id)
        extra_tags = list(extra.get("tags", []))
        driver_tag = extra.get("driver")
        if driver_tag and driver_tag not in extra_tags:
            extra_tags.insert(0, driver_tag)
        items.append({
            "id": op_id,
            "kind": "operation",
            "operation_type": op_id,
            "template_id": None,
            "label": extra["label"],
            "description": extra["description"],
            "driver": extra["driver"],
            "category": extra.get("category", extra["driver"]),
            "tags": extra_tags,
            "requires_config": extra["requires_config"],
            "has_ui_form": extra["has_ui_form"],
            "icon": extra.get("icon"),
            "deprecated": deprecated,
            "deprecated_message": deprecated_message,
        })

    templates = WorkflowTemplate.objects.filter(
        is_template=True,
        is_active=True,
        is_valid=True,
    ).order_by("name")
    for template in templates:
        tags = []
        if template.category:
            tags.append(template.category)
        if "workflow" not in tags:
            tags.insert(0, "workflow")
        items.append({
            "id": str(template.id),
            "kind": "template",
            "operation_type": None,
            "template_id": str(template.id),
            "label": template.name,
            "description": template.description,
            "driver": "workflow",
            "category": "workflow",
            "tags": tags,
            "requires_config": template.input_schema is not None,
            "has_ui_form": True,
            "icon": template.icon or None,
            "deprecated": False,
            "deprecated_message": None,
        })

    if not request.user.is_staff:
        items = [
            item
            for item in items
            if not (
                item.get("kind") == "operation"
                and str(item.get("operation_type") or "").startswith("ibcmd_")
                and item.get("operation_type") != "ibcmd_cli"
            )
        ]

    items.sort(
        key=lambda item: (
            OPERATION_CATALOG_DRIVER_ORDER.get(item["driver"], 99),
            item["label"].lower(),
        )
    )

    for item in items:
        if item.get("kind") == "operation" and not item.get("operation_type"):
            logger.error(
                "Operation catalog item missing operation_type",
                extra={"item": item, "user": request.user.username},
            )
            return Response({
                "success": False,
                "error": {
                    "code": "CATALOG_ITEM_INVALID",
                    "message": "Operation catalog item missing operation_type",
                },
            }, status=500)
        if item.get("kind") == "template" and not item.get("template_id"):
            logger.error(
                "Operation catalog item missing template_id",
                extra={"item": item, "user": request.user.username},
            )
            return Response({
                "success": False,
                "error": {
                    "code": "CATALOG_ITEM_INVALID",
                    "message": "Operation catalog item missing template_id",
                },
            }, status=500)

    return Response({
        "items": items,
        "count": len(items),
    })


