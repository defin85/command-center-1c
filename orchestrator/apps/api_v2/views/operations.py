"""
Operation endpoints for API v2.

Provides action-based endpoints for batch operations management.
"""

import json
import logging
import os
import secrets
import time
import asyncio
import uuid
from typing import Any

import redis as redis_module
import redis.asyncio as redis_async
from django.conf import settings
from django.db.models import Count, F, Q
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_GET
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from asgiref.sync import sync_to_async
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.throttling import UserRateThrottle
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.operations.models import BatchOperation, Task, DriverCommandShortcut
from apps.operations.serializers import BatchOperationSerializer, TaskSerializer
from apps.operations.services import OperationsService
from apps.operations.ibcmd_cli_builder import (
    build_ibcmd_cli_argv,
    build_ibcmd_cli_argv_manual,
    build_ibcmd_connection_args,
    detect_connection_option_conflicts,
    flatten_connection_params,
)
from apps.operations.driver_catalog_effective import (
    compute_actor_roles_hash,
    compute_driver_catalog_etag,
    explain_command_denied,
    filter_catalog_for_user,
    get_actor_roles,
    get_command_min_db_level,
    get_effective_driver_catalog,
    get_effective_driver_catalog_lkg,
    resolve_driver_catalog_versions,
)
from apps.artifacts.storage import ArtifactStorageError
from apps.core import permission_codes as perms
from apps.databases.permissions import CanExecuteOperation
from apps.databases.services import PermissionService
from apps.databases.models import Database, PermissionLevel
from apps.runtime_settings.models import RuntimeSetting
from apps.runtime_settings.registry import RUNTIME_SETTINGS
from apps.templates.registry import get_registry, BackendType
from apps.templates.workflow.models import WorkflowTemplate
from apps.operations.prometheus_metrics import (
    record_api_v2_duration,
    record_api_v2_error,
    record_sse_ticket,
    sse_connection_open,
    sse_connection_close,
    record_sse_stream_error,
    record_sse_loop_duration,
    record_driver_command_denied,
)

logger = logging.getLogger(__name__)

# =============================================================================
# SSE Ticket Constants
# =============================================================================
SSE_TICKET_TTL = 30  # seconds
SSE_TICKET_PREFIX = "sse_ticket:"
SSE_MUX_TICKET_PREFIX = "sse_mux_ticket:"
SSE_BLOCK_MS = 1000
SSE_HEARTBEAT_INTERVAL_SECONDS = 10
SSE_MAX_CONNECTION_SECONDS = getattr(settings, "SSE_MAX_CONNECTION_SECONDS", 0)
SSE_MAX_IDLE_SECONDS = getattr(settings, "SSE_MAX_IDLE_SECONDS", 0)
OP_SSE_ACTIVE_PREFIX = "op_sse_active:"
OP_SSE_ACTIVE_TTL = 120
OP_SSE_MAX_STREAMS_KEY = "ui.operations.max_live_streams"
OP_SSE_MAX_STREAMS_DEFAULT = (
    RUNTIME_SETTINGS.get(OP_SSE_MAX_STREAMS_KEY).default
    if RUNTIME_SETTINGS.get(OP_SSE_MAX_STREAMS_KEY)
    else 10
)
OP_MUX_ACTIVE_PREFIX = "op_mux_active:"
OP_MUX_ACTIVE_TTL = 120
OP_MUX_MAX_STREAMS_KEY = "observability.operations.max_mux_streams"
OP_MUX_MAX_STREAMS_DEFAULT = (
    RUNTIME_SETTINGS.get(OP_MUX_MAX_STREAMS_KEY).default
    if RUNTIME_SETTINGS.get(OP_MUX_MAX_STREAMS_KEY)
    else 1
)
OP_MUX_MAX_SUBSCRIPTIONS_KEY = "observability.operations.max_subscriptions"
OP_MUX_MAX_SUBSCRIPTIONS_DEFAULT = (
    RUNTIME_SETTINGS.get(OP_MUX_MAX_SUBSCRIPTIONS_KEY).default
    if RUNTIME_SETTINGS.get(OP_MUX_MAX_SUBSCRIPTIONS_KEY)
    else 200
)
OP_MUX_SUB_PREFIX = "op_mux_sub:"
OP_MUX_LAST_PREFIX = "op_mux_last:"

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


# =============================================================================
# Response Serializers for OpenAPI documentation
# =============================================================================

class OperationErrorDetailSerializer(serializers.Serializer):
    """Error detail structure."""
    code = serializers.CharField(help_text="Error code (e.g., MISSING_PARAMETER)")
    message = serializers.CharField(help_text="Human-readable error message")
    details = serializers.DictField(required=False, help_text="Additional error details")


class OperationErrorResponseSerializer(serializers.Serializer):
    """Standard error response."""
    success = serializers.BooleanField(default=False)
    error = OperationErrorDetailSerializer()


class OperationProgressSerializer(serializers.Serializer):
    """Progress information for an operation."""
    total = serializers.IntegerField(help_text="Total number of tasks")
    completed = serializers.IntegerField(help_text="Number of completed tasks")
    failed = serializers.IntegerField(help_text="Number of failed tasks")
    pending = serializers.IntegerField(help_text="Number of pending/queued tasks")
    processing = serializers.IntegerField(help_text="Number of processing tasks")
    percent = serializers.IntegerField(help_text="Completion percentage (0-100)")


class OperationListResponseSerializer(serializers.Serializer):
    """Response for list_operations endpoint."""
    operations = BatchOperationSerializer(many=True)
    count = serializers.IntegerField(help_text="Number of operations in current page")
    total = serializers.IntegerField(help_text="Total number of operations matching filters")


class OperationDetailResponseSerializer(serializers.Serializer):
    """Response for get_operation endpoint."""
    operation = BatchOperationSerializer()
    tasks = TaskSerializer(many=True, required=False, help_text="Task details (if include_tasks=true)")
    progress = OperationProgressSerializer()


# =============================================================================
# Filters & Sorting
# =============================================================================

OPERATION_FILTER_FIELDS = {
    "name": {"field": "name", "type": "text"},
    "id": {"field": "id", "type": "text"},
    "status": {"field": "status", "type": "enum"},
    "operation_type": {"field": "operation_type", "type": "enum"},
    "created_by": {"field": "created_by", "type": "text"},
    "created_at": {"field": "created_at", "type": "datetime"},
    "duration_seconds": {"field": "duration_seconds", "type": "number"},
    "workflow_execution_id": {"field": "metadata__workflow_execution_id", "type": "text"},
    "node_id": {"field": "metadata__node_id", "type": "text"},
}

OPERATION_SORT_FIELDS = {
    "created_at": "created_at",
    "name": "name",
    "status": "status",
    "operation_type": "operation_type",
    "duration_seconds": "duration_seconds",
}

TASK_FILTER_FIELDS = {
    "database_name": {"field": "database_name", "type": "text"},
    "status": {"field": "status", "type": "enum"},
    "worker_id": {"field": "worker_id", "type": "text"},
    "error_message": {"field": "error_message", "type": "text"},
    "started_at": {"field": "started_at", "type": "datetime"},
    "completed_at": {"field": "completed_at", "type": "datetime"},
    "duration_seconds": {"field": "duration_seconds", "type": "number"},
}

TASK_SORT_FIELDS = {
    "database_name": "database_name",
    "status": "status",
    "worker_id": "worker_id",
    "started_at": "started_at",
    "completed_at": "completed_at",
    "duration_seconds": "duration_seconds",
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


def _apply_number_filter(qs, field: str, op: str, value: int | float):
    if op == "eq":
        return qs.filter(**{field: value})
    if op == "gt":
        return qs.filter(**{f"{field}__gt": value})
    if op == "gte":
        return qs.filter(**{f"{field}__gte": value})
    if op == "lt":
        return qs.filter(**{f"{field}__lt": value})
    if op == "lte":
        return qs.filter(**{f"{field}__lte": value})
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


def _apply_filters(qs, filters: dict, config: dict) -> tuple:
    for key, payload in filters.items():
        if key not in config:
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
        field_meta = config[key]
        field = field_meta["field"]
        field_type = field_meta["type"]
        if field_type == "text":
            qs = _apply_text_filter(qs, field, op, str(value))
        elif field_type == "number":
            try:
                num = float(value)
            except (ValueError, TypeError):
                return qs, {
                    "code": "INVALID_FILTER_VALUE",
                    "message": f"Invalid numeric value for {key}",
                }
            qs = _apply_number_filter(qs, field, op, num)
        elif field_type == "datetime":
            qs = _apply_datetime_filter(qs, field, op, str(value))
        elif field_type == "enum":
            qs = _apply_enum_filter(qs, field, op, value)
    return qs, None


def _apply_sort(qs, sort_payload: dict | None, config: dict) -> tuple:
    if not sort_payload:
        return qs, None
    key = sort_payload.get("key")
    order = sort_payload.get("order")
    if key not in config:
        return qs, {
            "code": "UNKNOWN_SORT",
            "message": f"Unknown sort key: {key}",
        }
    field = config[key]
    if order == "desc":
        return qs.order_by(f"-{field}"), None
    if order == "asc":
        return qs.order_by(field), None
    return qs, {
        "code": "INVALID_SORT",
        "message": "sort order must be 'asc' or 'desc'",
    }


class OperationCancelResponseSerializer(serializers.Serializer):
    """Response for cancel_operation endpoint."""
    operation_id = serializers.CharField(help_text="ID of the cancelled operation")
    cancelled = serializers.BooleanField(help_text="Whether cancellation was successful")
    message = serializers.CharField(help_text="Status message")


class OperationStreamStatusSerializer(serializers.Serializer):
    """Response for operation stream status."""
    active_streams = serializers.IntegerField(help_text="Active SSE streams for current user")
    max_streams = serializers.IntegerField(help_text="Maximum allowed SSE streams")


class OperationMuxStreamStatusSerializer(serializers.Serializer):
    """Response for multiplex stream status."""
    active_streams = serializers.IntegerField(help_text="Active multiplex SSE streams for current user")
    max_streams = serializers.IntegerField(help_text="Maximum allowed multiplex SSE streams")
    active_subscriptions = serializers.IntegerField(help_text="Active operation subscriptions for user")
    max_subscriptions = serializers.IntegerField(help_text="Maximum allowed subscriptions")


class OperationCatalogItemSerializer(serializers.Serializer):
    """Operation catalog entry for Operations Center."""
    id = serializers.CharField(help_text="Catalog item identifier")
    kind = serializers.ChoiceField(choices=["operation", "template"])
    operation_type = serializers.CharField(required=False, allow_null=True)
    template_id = serializers.CharField(required=False, allow_null=True)
    label = serializers.CharField()
    description = serializers.CharField()
    driver = serializers.CharField(help_text="Driver group (ras/odata/cli/ibcmd/workflow)")
    category = serializers.CharField()
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    requires_config = serializers.BooleanField()
    has_ui_form = serializers.BooleanField()
    icon = serializers.CharField(required=False, allow_null=True)
    deprecated = serializers.BooleanField()
    deprecated_message = serializers.CharField(required=False, allow_null=True)


class OperationCatalogResponseSerializer(serializers.Serializer):
    """Response for operation catalog endpoint."""
    items = OperationCatalogItemSerializer(many=True)
    count = serializers.IntegerField()


class CliCommandSerializer(serializers.Serializer):
    """Single CLI command descriptor."""
    id = serializers.CharField()
    label = serializers.CharField()
    usage = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    params = serializers.ListField(child=serializers.DictField(), required=False)
    source_section_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    source_section = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class CliCommandCatalogResponseSerializer(serializers.Serializer):
    """Response for CLI command catalog endpoint."""
    version = serializers.CharField()
    source = serializers.CharField()
    generated_at = serializers.CharField(required=False, allow_blank=True)
    commands = CliCommandSerializer(many=True)


# =============================================================================
# Driver Catalog v2 (schema-driven commands)
# =============================================================================

class DriverCatalogV2SourceSerializer(serializers.Serializer):
    type = serializers.CharField(required=False)
    doc_id = serializers.CharField(required=False, allow_blank=True)
    section_prefix = serializers.CharField(required=False, allow_blank=True)
    doc_url = serializers.CharField(required=False, allow_blank=True)
    hint = serializers.CharField(required=False, allow_blank=True)


class DriverCommandParamV2Serializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["flag", "positional"])
    flag = serializers.CharField(required=False, allow_blank=True)
    position = serializers.IntegerField(required=False, allow_null=True)
    required = serializers.BooleanField()
    expects_value = serializers.BooleanField()
    label = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    value_type = serializers.ChoiceField(
        choices=["string", "int", "float", "bool"],
        required=False,
        allow_null=True,
    )
    enum = serializers.ListField(child=serializers.CharField(), required=False)
    default = serializers.JSONField(required=False)
    repeatable = serializers.BooleanField(required=False)
    sensitive = serializers.BooleanField(required=False)
    artifact = serializers.JSONField(required=False)
    ui = serializers.JSONField(required=False)
    disabled = serializers.BooleanField(required=False)


class DriverCommandV2Serializer(serializers.Serializer):
    label = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    argv = serializers.ListField(child=serializers.CharField())
    scope = serializers.ChoiceField(choices=["per_database", "global"])
    risk_level = serializers.ChoiceField(choices=["safe", "dangerous"])
    params_by_name = serializers.DictField(child=DriverCommandParamV2Serializer(), required=False)
    ui = serializers.JSONField(required=False)
    source_section = serializers.CharField(required=False, allow_blank=True)
    disabled = serializers.BooleanField(required=False)
    permissions = serializers.JSONField(required=False)


class DriverCatalogV2Serializer(serializers.Serializer):
    catalog_version = serializers.IntegerField()
    driver = serializers.CharField()
    platform_version = serializers.CharField(required=False, allow_blank=True)
    source = DriverCatalogV2SourceSerializer(required=False)
    generated_at = serializers.CharField(required=False, allow_blank=True)
    commands_by_id = serializers.DictField(child=DriverCommandV2Serializer())


class DriverCommandsResponseV2Serializer(serializers.Serializer):
    driver = serializers.CharField()
    base_version = serializers.CharField(required=False, allow_blank=True)
    overrides_version = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    generated_at = serializers.CharField(required=False, allow_blank=True)
    catalog = DriverCatalogV2Serializer()


class DriverCommandShortcutSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    driver = serializers.CharField()
    command_id = serializers.CharField()
    title = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class ListDriverCommandShortcutsResponseSerializer(serializers.Serializer):
    items = DriverCommandShortcutSerializer(many=True)
    count = serializers.IntegerField()


class CreateDriverCommandShortcutRequestSerializer(serializers.Serializer):
    driver = serializers.ChoiceField(choices=[("ibcmd", "ibcmd")])
    command_id = serializers.CharField()
    title = serializers.CharField(max_length=255)


class DeleteDriverCommandShortcutRequestSerializer(serializers.Serializer):
    shortcut_id = serializers.UUIDField()


# =============================================================================
# Execute Operation Serializers
# =============================================================================

class ExecuteOperationRequestSerializer(serializers.Serializer):
    """Request body for execute_operation endpoint."""
    RAS_OPERATION_TYPES = [
        ('lock_scheduled_jobs', 'Lock Scheduled Jobs'),
        ('unlock_scheduled_jobs', 'Unlock Scheduled Jobs'),
        ('block_sessions', 'Block Sessions'),
        ('unblock_sessions', 'Unblock Sessions'),
        ('terminate_sessions', 'Terminate Sessions'),
    ]
    ODATA_OPERATION_TYPES = [
        ('create', 'Create Records'),
        ('update', 'Update Records'),
        ('delete', 'Delete Records'),
        ('query', 'Query Records'),
    ]
    CLI_OPERATION_TYPES = [
        ('designer_cli', 'Designer CLI'),
    ]

    operation_type = serializers.ChoiceField(
        choices=(
            RAS_OPERATION_TYPES
            + ODATA_OPERATION_TYPES
            + CLI_OPERATION_TYPES
        ),
        help_text="Operation type to execute"
    )
    database_ids = serializers.ListField(
        child=serializers.UUIDField(format='hex_verbose'),
        min_length=1,
        max_length=500,
        help_text="List of database UUIDs"
    )
    config = serializers.DictField(
        required=False,
        default=dict,
        help_text="Operation-specific configuration (e.g., message for block_sessions)"
    )


class ExecuteOperationResponseSerializer(serializers.Serializer):
    """Response for execute_operation endpoint."""
    operation_id = serializers.CharField(help_text="ID of the created operation")
    status = serializers.CharField(help_text="Operation status (queued)")
    total_tasks = serializers.IntegerField(help_text="Number of tasks created")
    message = serializers.CharField(help_text="Status message")


class ExecuteOperationThrottle(UserRateThrottle):
    """Rate limit: 30 operations per minute per user."""
    rate = '30/min'
    scope = 'execute_operation'


class IbcmdCliConnectionOfflineSerializer(serializers.Serializer):
    config = serializers.CharField(required=False, allow_blank=False)
    data = serializers.CharField(required=False, allow_blank=False)
    dbms = serializers.CharField(required=False, allow_blank=False)
    db_server = serializers.CharField(required=False, allow_blank=False)
    db_name = serializers.CharField(required=False, allow_blank=False)
    db_user = serializers.CharField(required=False, allow_blank=False)
    db_pwd = serializers.CharField(required=False, allow_blank=False, write_only=True)


class IbcmdCliConnectionSerializer(serializers.Serializer):
    remote = serializers.CharField(required=False, allow_blank=False)
    pid = serializers.IntegerField(required=False, allow_null=True)
    offline = IbcmdCliConnectionOfflineSerializer(required=False)


class ExecuteIbcmdCliOperationRequestSerializer(serializers.Serializer):
    """Request body for execute_ibcmd_cli_operation endpoint."""

    MODE_CHOICES = [
        ("guided", "guided"),
        ("manual", "manual"),
    ]

    command_id = serializers.CharField(help_text="IBCMD command id from driver catalog v2")
    mode = serializers.ChoiceField(choices=MODE_CHOICES, default="guided", required=False)

    database_ids = serializers.ListField(
        child=serializers.UUIDField(format='hex_verbose'),
        required=False,
        allow_empty=True,
        max_length=500,
        help_text="Target databases for per_database commands (empty for global)",
    )
    auth_database_id = serializers.UUIDField(
        required=False,
        help_text="Anchor database for global commands (RBAC + infobase user mapping)",
    )

    connection = IbcmdCliConnectionSerializer(required=False)
    params = serializers.DictField(required=False, default=dict)
    additional_args = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    stdin = serializers.CharField(required=False, allow_blank=True, default="")

    confirm_dangerous = serializers.BooleanField(required=False, default=False)
    timeout_seconds = serializers.IntegerField(required=False, min_value=1, max_value=3600, default=900)


class ExecuteIbcmdCliOperationThrottle(UserRateThrottle):
    """Rate limit: 10 ibcmd_cli operations per minute per user."""
    rate = '10/min'
    scope = 'execute_ibcmd_cli_operation'


def _split_select(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item.strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(',') if item.strip()]
    return []


def _enqueue_odata_operation(user, operation_type, database_ids, config):
    config = config or {}
    data: dict = {}
    filters: dict = {}
    options: dict = {}
    target_entity = config.get("entity") or config.get("entity_name")

    if operation_type in ("create", "update", "delete", "query") and not target_entity:
        raise ValueError("entity is required for OData operations")

    if operation_type == "query":
        if "filter" in config and config["filter"] is not None:
            options["filter"] = config["filter"]
        select_list = _split_select(config.get("select"))
        if select_list:
            options["select"] = select_list
        if config.get("top") is not None:
            options["top"] = config.get("top")
        if config.get("skip") is not None:
            options["skip"] = config.get("skip")
    elif operation_type == "create":
        data = config.get("data") or {}
        if not isinstance(data, dict):
            raise ValueError("data must be an object for create operation")
    elif operation_type == "update":
        data = config.get("data") or {}
        if not isinstance(data, dict):
            raise ValueError("data must be an object for update operation")
        entity_id = config.get("entity_id")
        if not entity_id:
            raise ValueError("entity_id is required for update operation")
        filters["entity_id"] = entity_id
    elif operation_type == "delete":
        entity_id = config.get("entity_id")
        if not entity_id:
            raise ValueError("entity_id is required for delete operation")
        filters["entity_id"] = entity_id
    else:
        raise ValueError(f"Unsupported OData operation_type: {operation_type}")

    return OperationsService.enqueue_odata_operation(
        operation_type=operation_type,
        database_ids=database_ids,
        target_entity=target_entity,
        data=data,
        filters=filters,
        options=options,
        user=user,
    )


# =============================================================================
# SSE Ticket Serializers
# =============================================================================

class SSETicketRequestSerializer(serializers.Serializer):
    """Request body for get_stream_ticket endpoint."""
    operation_id = serializers.CharField(help_text="Operation ID to subscribe to")
    client_id = serializers.CharField(required=False, help_text="Optional client identifier")


class SSETicketResponseSerializer(serializers.Serializer):
    """Response for get_stream_ticket endpoint."""
    ticket = serializers.CharField(help_text="Short-lived ticket for SSE connection")
    expires_in = serializers.IntegerField(help_text="Seconds until ticket expires")
    stream_url = serializers.CharField(help_text="SSE endpoint URL to connect to")


class OperationMuxSubscribeSerializer(serializers.Serializer):
    """Request body for multiplex stream subscribe."""
    operation_ids = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
        help_text="Operation IDs to subscribe to",
    )


class OperationMuxUnsubscribeSerializer(serializers.Serializer):
    """Request body for multiplex stream unsubscribe."""
    operation_ids = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
        help_text="Operation IDs to unsubscribe from",
    )


class OperationMuxTicketRequestSerializer(serializers.Serializer):
    """Request body for multiplex stream ticket."""
    client_id = serializers.CharField(required=False, help_text="Optional client identifier")


@extend_schema(
    tags=['v2'],
    summary='List batch operations',
    description='List all batch operations with optional filtering by status, type, and creator.',
    parameters=[
        OpenApiParameter(
            name='operation_id',
            type=str,
            required=False,
            description='Filter by operation ID'
        ),
        OpenApiParameter(
            name='status',
            type=str,
            required=False,
            description='Filter by status (pending, queued, processing, completed, failed, cancelled)'
        ),
        OpenApiParameter(
            name='operation_type',
            type=str,
            required=False,
            description='Filter by type (create, update, delete, query, designer_cli)'
        ),
        OpenApiParameter(
            name='created_by',
            type=str,
            required=False,
            description='Filter by creator username'
        ),
        OpenApiParameter(
            name='search',
            type=str,
            required=False,
            description='Search by name, description, or ID'
        ),
        OpenApiParameter(
            name='filters',
            type=str,
            required=False,
            description='JSON object with filter conditions'
        ),
        OpenApiParameter(
            name='sort',
            type=str,
            required=False,
            description='JSON object with sort configuration'
        ),
        OpenApiParameter(
            name='workflow_execution_id',
            type=str,
            required=False,
            description='Filter by workflow execution ID'
        ),
        OpenApiParameter(
            name='node_id',
            type=str,
            required=False,
            description='Filter by workflow node ID'
        ),
        OpenApiParameter(
            name='limit',
            type=int,
            required=False,
            description='Maximum results (default: 50, max: 1000)'
        ),
        OpenApiParameter(
            name='offset',
            type=int,
            required=False,
            description='Pagination offset (default: 0)'
        ),
    ],
    responses={
        200: OperationListResponseSerializer,
        400: OperationErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_operations(request):
    """
    GET /api/v2/operations/list-operations/

    List all batch operations with optional filtering.

    Query Parameters:
        - operation_id: Filter by operation ID
        - status: Filter by status (pending, queued, processing, completed, failed, cancelled)
        - operation_type: Filter by type (create, update, delete, query, designer_cli)
        - created_by: Filter by creator username
        - search: Search by name, description, or ID
        - filters: JSON object with filter conditions
        - sort: JSON object with sort configuration
        - workflow_execution_id: Filter by workflow execution ID
        - node_id: Filter by workflow node ID
        - limit: Maximum results (default: 50)
        - offset: Pagination offset (default: 0)

    Response:
        {
            "operations": [...],
            "count": 50,
            "total": 200
        }
    """
    status = request.query_params.get('status')
    operation_type = request.query_params.get('operation_type')
    created_by = request.query_params.get('created_by')
    operation_id = request.query_params.get('operation_id')
    workflow_execution_id = request.query_params.get('workflow_execution_id')
    node_id = request.query_params.get('node_id')
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

    qs = BatchOperation.objects.prefetch_related('target_databases')

    if status:
        qs = qs.filter(status=status)
    if operation_type:
        qs = qs.filter(operation_type=operation_type)
    if created_by:
        qs = qs.filter(created_by=created_by)
    if operation_id:
        operation_id = operation_id.strip()
    if operation_id:
        qs = qs.filter(id__iexact=operation_id)
    if workflow_execution_id:
        qs = qs.filter(metadata__workflow_execution_id=workflow_execution_id)
    if node_id:
        qs = qs.filter(metadata__node_id=node_id)

    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(description__icontains=search)
            | Q(id__icontains=search)
            | Q(created_by__icontains=search)
        )

    filters_payload, filters_error = _parse_filters(raw_filters)
    if filters_error:
        return Response({"success": False, "error": filters_error}, status=400)
    if filters_payload:
        qs, apply_error = _apply_filters(qs, filters_payload, OPERATION_FILTER_FIELDS)
        if apply_error:
            return Response({"success": False, "error": apply_error}, status=400)

    sort_payload, sort_error = _parse_sort(raw_sort)
    if sort_error:
        return Response({"success": False, "error": sort_error}, status=400)
    if sort_payload:
        qs, apply_sort_error = _apply_sort(qs, sort_payload, OPERATION_SORT_FIELDS)
        if apply_sort_error:
            return Response({"success": False, "error": apply_sort_error}, status=400)
    else:
        # Order by most recent first
        qs = qs.order_by('-created_at')

    if not request.user.is_staff:
        accessible_db_ids = PermissionService.filter_accessible_databases(
            request.user,
            Database.objects.all(),
            PermissionLevel.VIEW,
        ).values_list("id", flat=True)

        qs = qs.annotate(
            total_db_count=Count("target_databases", distinct=True),
            accessible_db_count=Count(
                "target_databases",
                filter=Q(target_databases__id__in=accessible_db_ids),
                distinct=True,
            ),
        ).filter(
            Q(created_by=request.user.username)
            | Q(total_db_count=F("accessible_db_count"), total_db_count__gt=0)
        )

    total = qs.count()
    qs = qs[offset:offset + limit]

    serializer = BatchOperationSerializer(qs, many=True)

    return Response({
        'operations': serializer.data,
        'count': len(serializer.data),
        'total': total,
    })


@extend_schema(
    tags=['v2'],
    summary='Get operation details',
    description='Get detailed information about a specific operation including tasks and progress.',
    parameters=[
        OpenApiParameter(
            name='operation_id',
            type=str,
            required=True,
            description='Operation ID (UUID)'
        ),
        OpenApiParameter(
            name='include_tasks',
            type=bool,
            required=False,
            description='Include task details (default: true)'
        ),
        OpenApiParameter(
            name='task_limit',
            type=int,
            required=False,
            description='Maximum tasks returned (default: 100)'
        ),
        OpenApiParameter(
            name='task_offset',
            type=int,
            required=False,
            description='Task pagination offset (default: 0)'
        ),
        OpenApiParameter(
            name='task_filters',
            type=str,
            required=False,
            description='JSON object with task filter conditions'
        ),
        OpenApiParameter(
            name='task_sort',
            type=str,
            required=False,
            description='JSON object with task sort configuration'
        ),
    ],
    responses={
        200: OperationDetailResponseSerializer,
        400: OperationErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: OperationErrorResponseSerializer,
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_operation(request):
    """
    GET /api/v2/operations/get-operation/?operation_id=X

    Get detailed information about a specific operation.

    Query Parameters:
        - operation_id: Operation ID (required)
        - include_tasks: Include task details (default: true)
        - task_limit: Maximum tasks returned (default: 100)
        - task_offset: Task pagination offset (default: 0)
        - task_filters: JSON object with task filter conditions
        - task_sort: JSON object with task sort configuration

    Response:
        {
            "operation": {...},
            "tasks": [...],
            "progress": {
                "total": 100,
                "completed": 95,
                "failed": 5,
                "pending": 0,
                "percent": 100
            }
        }
    """
    operation_id = request.query_params.get('operation_id')
    include_tasks = request.query_params.get('include_tasks', 'true').lower() == 'true'
    raw_task_filters = request.query_params.get('task_filters')
    raw_task_sort = request.query_params.get('task_sort')

    try:
        task_limit = int(request.query_params.get('task_limit', 100))
    except (TypeError, ValueError):
        task_limit = 100
    task_limit = max(1, min(task_limit, 500))

    try:
        task_offset = int(request.query_params.get('task_offset', 0))
    except (TypeError, ValueError):
        task_offset = 0
    task_offset = max(0, task_offset)

    if not operation_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'operation_id is required'
            }
        }, status=400)

    try:
        operation = BatchOperation.objects.prefetch_related(
            'tasks', 'target_databases'
        ).get(id=operation_id)
    except BatchOperation.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'OPERATION_NOT_FOUND',
                'message': 'Operation not found'
            }
        }, status=404)

    allowed, _denied = _resolve_operation_access(request.user, [operation])
    if str(operation.id) not in allowed:
        return Response({
            'success': False,
            'error': {
                'code': 'FORBIDDEN',
                'message': 'You do not have permission to view this operation',
            }
        }, status=403)

    serializer = BatchOperationSerializer(operation)

    # Build progress info
    tasks = operation.tasks.all()
    progress = {
        'total': tasks.count(),
        'completed': tasks.filter(status=Task.STATUS_COMPLETED).count(),
        'failed': tasks.filter(status=Task.STATUS_FAILED).count(),
        'pending': tasks.filter(status__in=[Task.STATUS_PENDING, Task.STATUS_QUEUED]).count(),
        'processing': tasks.filter(status=Task.STATUS_PROCESSING).count(),
        'percent': operation.progress,
    }

    response_data = {
        'operation': serializer.data,
        'progress': progress,
    }

    if include_tasks:
        tasks_qs = tasks

        task_filters_payload, task_filters_error = _parse_filters(raw_task_filters)
        if task_filters_error:
            return Response({"success": False, "error": task_filters_error}, status=400)
        if task_filters_payload:
            tasks_qs, apply_error = _apply_filters(tasks_qs, task_filters_payload, TASK_FILTER_FIELDS)
            if apply_error:
                return Response({"success": False, "error": apply_error}, status=400)

        task_sort_payload, task_sort_error = _parse_sort(raw_task_sort)
        if task_sort_error:
            return Response({"success": False, "error": task_sort_error}, status=400)
        if task_sort_payload:
            tasks_qs, apply_sort_error = _apply_sort(tasks_qs, task_sort_payload, TASK_SORT_FIELDS)
            if apply_sort_error:
                return Response({"success": False, "error": apply_sort_error}, status=400)

        task_serializer = TaskSerializer(tasks_qs[task_offset:task_offset + task_limit], many=True)
        response_data['tasks'] = task_serializer.data

    return Response(response_data)


class CancelOperationRequestSerializer(serializers.Serializer):
    """Request body for cancel_operation endpoint."""
    operation_id = serializers.CharField(help_text="ID of the operation to cancel (UUID)")


@extend_schema(
    tags=['v2'],
    summary='Cancel operation',
    description='Cancel a running or pending operation. Already completed or cancelled operations cannot be cancelled.',
    request=CancelOperationRequestSerializer,
    responses={
        200: OperationCancelResponseSerializer,
        400: OperationErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: OperationErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_operation(request):
    """
    POST /api/v2/operations/cancel-operation/

    Cancel a running or pending operation.

    Request Body:
        {
            "operation_id": "string"
        }

    Response:
        {
            "operation_id": "string",
            "cancelled": true,
            "message": "Operation cancelled successfully"
        }
    """
    operation_id = request.data.get('operation_id')

    if not operation_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'operation_id is required'
            }
        }, status=400)

    try:
        operation = BatchOperation.objects.get(id=operation_id)
    except BatchOperation.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'OPERATION_NOT_FOUND',
                'message': 'Operation not found'
            }
        }, status=404)

    if not request.user.is_staff and operation.created_by != request.user.username:
        target_ids = list(operation.target_databases.values_list("id", flat=True))
        if not target_ids:
            return Response({
                'success': False,
                'error': {
                    'code': 'FORBIDDEN',
                    'message': 'You do not have permission to cancel this operation',
                }
            }, status=403)

        allowed, denied = PermissionService.check_bulk_permission(
            request.user,
            [str(db_id) for db_id in target_ids],
            PermissionLevel.MANAGE,
        )
        if not allowed:
            denied_str = ", ".join(denied[:5])
            msg = f"Access denied for databases: {denied_str}"
            if len(denied) > 5:
                msg += f" and {len(denied) - 5} more"
            return Response({
                'success': False,
                'error': {
                    'code': 'FORBIDDEN',
                    'message': msg,
                }
            }, status=403)

    # Check if operation can be cancelled
    if operation.status in [BatchOperation.STATUS_COMPLETED, BatchOperation.STATUS_CANCELLED]:
        return Response({
            'operation_id': operation_id,
            'cancelled': False,
            'message': f'Operation cannot be cancelled (status: {operation.status})',
        }, status=400)

    # Cancel the operation
    operation.status = BatchOperation.STATUS_CANCELLED
    operation.completed_at = timezone.now()
    operation.save(update_fields=['status', 'completed_at', 'updated_at'])

    # Cancel pending tasks
    cancelled_tasks = Task.objects.filter(
        batch_operation=operation,
        status__in=[Task.STATUS_PENDING, Task.STATUS_QUEUED]
    ).update(status=Task.STATUS_CANCELLED)

    # Note: Go Worker handles task cancellation via Redis events
    # No need to revoke tasks here - operation status change triggers cancellation

    # Audit logging
    logger.info(
        "Operation cancelled by user",
        extra={
            'operation_id': operation_id,
            'operation_type': operation.operation_type,
            'cancelled_by': request.user.username if request.user else 'anonymous',
            'cancelled_tasks_count': cancelled_tasks,
        }
    )

    return Response({
        'operation_id': operation_id,
        'cancelled': True,
        'message': 'Operation cancelled successfully',
    })


# =============================================================================
# Execute RAS Operation
# =============================================================================

@extend_schema(
    tags=['v2'],
    summary='Execute RAS operation',
    description='''
    Queue an operation for execution on selected databases.

    **Supported operation types:**
    - RAS: `lock_scheduled_jobs`, `unlock_scheduled_jobs`, `block_sessions`,
      `unblock_sessions`, `terminate_sessions`
    - OData: `create`, `update`, `delete`, `query`
    - CLI: `designer_cli`

    **Config notes:**
    - RAS block_sessions: `message`, `permission_code`, `denied_from`, `denied_to`, `parameter`
    - OData query: `entity`, `filter`, `select`, `top`, `skip`
    - OData update/delete: `entity`, `entity_id`
    - CLI designer_cli: `command` + `args` + optional `options`
    ''',
    request=ExecuteOperationRequestSerializer,
    responses={
        202: ExecuteOperationResponseSerializer,
        400: OperationErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, CanExecuteOperation])
@throttle_classes([ExecuteOperationThrottle])
def execute_operation(request):
    """
    POST /api/v2/operations/execute/

    Queue an operation for multiple databases.

    Request Body:
        {
            "operation_type": "lock_scheduled_jobs",
            "database_ids": ["uuid1", "uuid2"],
            "config": {}  // optional
        }

    Response (202 Accepted):
        {
            "operation_id": "uuid",
            "status": "queued",
            "total_tasks": 2,
            "message": "lock_scheduled_jobs queued for 2 database(s)"
        }
    """
    serializer = ExecuteOperationRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    operation_type = serializer.validated_data['operation_type']
    database_ids = serializer.validated_data['database_ids']
    config = serializer.validated_data.get('config', {})

    try:
        if operation_type in dict(ExecuteOperationRequestSerializer.RAS_OPERATION_TYPES):
            batch_operation = OperationsService.enqueue_ras_operation(
                operation_type=operation_type,
                database_ids=database_ids,
                config=config,
                user=request.user,
            )
        elif operation_type in dict(ExecuteOperationRequestSerializer.CLI_OPERATION_TYPES):
            if not config.get("command"):
                raise ValueError("command is required for designer_cli")
            batch_operation = OperationsService.enqueue_cli_operation(
                operation_type=operation_type,
                database_ids=database_ids,
                config=config,
                user=request.user,
            )
        elif operation_type in dict(ExecuteOperationRequestSerializer.ODATA_OPERATION_TYPES):
            batch_operation = _enqueue_odata_operation(request.user, operation_type, database_ids, config)
        else:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_OPERATION',
                    'message': f'Unsupported operation_type: {operation_type}',
                }
            }, status=http_status.HTTP_400_BAD_REQUEST)

        logger.info(
            f"Operation {operation_type} queued",
            extra={
                'operation_id': str(batch_operation.id),
                'operation_type': operation_type,
                'database_count': len(database_ids),
                'created_by': request.user.username if request.user else 'anonymous',
            }
        )

        return Response({
            'operation_id': str(batch_operation.id),
            'status': batch_operation.status,
            'total_tasks': batch_operation.total_tasks,
            'message': f'{operation_type} queued for {len(database_ids)} database(s)',
        }, status=http_status.HTTP_202_ACCEPTED)

    except ValueError as e:
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': str(e)
            }
        }, status=400)

    except Exception as e:
        logger.error(f"Error executing RAS operation: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'Failed to queue operation'
            }
        }, status=500)


# =============================================================================
# Execute IBCMD CLI (schema-driven)
# =============================================================================

@extend_schema(
    tags=['v2'],
    summary='Execute schema-driven IBCMD command (ibcmd_cli)',
    description='''
    Queue schema-driven IBCMD command for execution.

    Uses driver catalog v2 (base@approved + overrides@active) to validate `command_id`
    and build canonical `argv[]`.

    Supports both scopes:
    - per_database: executes per selected database
    - global: executes once (requires `auth_database_id` for RBAC + IB user mapping)

    Dangerous commands require `confirm_dangerous=true`.
    ''',
    request=ExecuteIbcmdCliOperationRequestSerializer,
    responses={
        202: ExecuteOperationResponseSerializer,
        400: OperationErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
        409: OpenApiResponse(description='Conflict'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ExecuteIbcmdCliOperationThrottle])
def execute_ibcmd_cli_operation(request):
    serializer = ExecuteIbcmdCliOperationRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return _execute_ibcmd_cli_validated(request, serializer.validated_data)


def _execute_ibcmd_cli_validated(
    request,
    validated_data: dict[str, Any],
    *,
    legacy_operation_type: str | None = None,
):
    from apps.databases.models import Database, PermissionLevel
    from apps.databases.services import PermissionService
    from apps.operations.models import BatchOperation, Task

    command_id = str(validated_data.get('command_id') or '').strip()
    mode = str(validated_data.get('mode') or 'guided').strip().lower()
    database_ids = [str(db_id) for db_id in (validated_data.get('database_ids') or [])]
    auth_database_id = validated_data.get('auth_database_id')
    connection = validated_data.get('connection') or {}
    params = validated_data.get('params') or {}
    additional_args = validated_data.get('additional_args') or []
    stdin = validated_data.get('stdin') or ""
    confirm_dangerous = bool(validated_data.get('confirm_dangerous') or False)
    timeout_seconds = int(validated_data.get('timeout_seconds') or 900)

    if not command_id:
        return Response({
            "success": False,
            "error": {"code": "MISSING_COMMAND_ID", "message": "command_id is required"},
        }, status=400)

    resolved = resolve_driver_catalog_versions("ibcmd")
    if resolved.base_version is None:
        return Response({
            "success": False,
            "error": {"code": "CATALOG_NOT_AVAILABLE", "message": "ibcmd catalog is not imported yet"},
        }, status=400)

    effective = get_effective_driver_catalog(
        driver="ibcmd",
        base_version=resolved.base_version,
        overrides_version=resolved.overrides_version,
    )
    catalog = filter_catalog_for_user(request.user, effective.catalog)

    raw_commands_by_id = effective.catalog.get("commands_by_id") if isinstance(effective.catalog, dict) else None
    if not isinstance(raw_commands_by_id, dict):
        raw_commands_by_id = None

    commands_by_id = catalog.get("commands_by_id") if isinstance(catalog, dict) else None
    if not isinstance(commands_by_id, dict):
        return Response({
            "success": False,
            "error": {"code": "CATALOG_INVALID", "message": "ibcmd catalog is invalid"},
        }, status=500)

    command = commands_by_id.get(command_id)
    if not isinstance(command, dict):
        raw_command = raw_commands_by_id.get(command_id) if raw_commands_by_id else None
        if isinstance(raw_command, dict):
            reason = explain_command_denied(request.user, raw_command) or "denied"
            record_driver_command_denied("ibcmd", reason)
            logger.warning(
                "Driver command denied by RBAC filter",
                extra={
                    "driver": "ibcmd",
                    "command_id": command_id,
                    "reason": reason,
                    "user": getattr(request.user, "username", None),
                    "roles": get_actor_roles(request.user),
                },
            )
        return Response({
            "success": False,
            "error": {"code": "UNKNOWN_COMMAND", "message": f"Unknown command_id: {command_id}"},
        }, status=400)

    if command.get("disabled") is True:
        record_driver_command_denied("ibcmd", "disabled")
        return Response({
            "success": False,
            "error": {"code": "UNKNOWN_COMMAND", "message": f"Unknown command_id: {command_id}"},
        }, status=400)

    scope = str(command.get("scope") or "").strip().lower()
    if scope not in {"per_database", "global"}:
        return Response({
            "success": False,
            "error": {"code": "COMMAND_INVALID", "message": "Command scope is invalid"},
        }, status=500)

    risk_level = str(command.get("risk_level") or "").strip().lower()

    required_capability_perm = (
        perms.PERM_OPERATIONS_EXECUTE_DANGEROUS_OPERATION
        if risk_level == "dangerous"
        else perms.PERM_OPERATIONS_EXECUTE_SAFE_OPERATION
    )
    if not request.user.has_perm(required_capability_perm):
        reason = "capability_dangerous_denied" if risk_level == "dangerous" else "capability_safe_denied"
        record_driver_command_denied("ibcmd", reason)
        message = "You do not have permission to execute dangerous operations."
        if risk_level != "dangerous":
            message = "You do not have permission to execute operations."
        return Response(
            {"success": False, "error": {"code": "PERMISSION_DENIED", "message": message}},
            status=403,
        )

    if risk_level == "dangerous" and not confirm_dangerous:
        return Response({
            "success": False,
            "error": {
                "code": "DANGEROUS_CONFIRM_REQUIRED",
                "message": "confirm_dangerous=true is required for dangerous commands",
            },
        }, status=400)

    required_level = PermissionLevel.OPERATE
    if risk_level == "dangerous":
        required_level = PermissionLevel.MANAGE
    min_db_level = get_command_min_db_level(command)
    if min_db_level in {"operate", "manage", "admin"}:
        required_level = {
            "operate": PermissionLevel.OPERATE,
            "manage": PermissionLevel.MANAGE,
            "admin": PermissionLevel.ADMIN,
        }[min_db_level]

    if scope == "global":
        if database_ids:
            return Response({
                "success": False,
                "error": {"code": "DATABASE_IDS_NOT_ALLOWED", "message": "database_ids must be empty for global scope"},
            }, status=400)
        if auth_database_id is None:
            return Response({
                "success": False,
                "error": {"code": "MISSING_AUTH_DATABASE", "message": "auth_database_id is required for global scope"},
            }, status=400)

        auth_db_id = str(auth_database_id)
        allowed, denied = PermissionService.check_bulk_permission(
            request.user,
            [auth_db_id],
            required_level,
        )
        if not allowed:
            return Response({
                "success": False,
                "error": {"code": "PERMISSION_DENIED", "message": f"Access denied for database: {', '.join(denied)}"},
            }, status=403)

        if not Database.objects.filter(id=auth_db_id).exists():
            return Response({
                "success": False,
                "error": {"code": "UNKNOWN_DATABASE", "message": f"Unknown auth_database_id: {auth_db_id}"},
            }, status=400)
    else:
        if not database_ids:
            return Response({
                "success": False,
                "error": {"code": "MISSING_DATABASE_IDS", "message": "database_ids cannot be empty for per_database scope"},
            }, status=400)

        allowed, denied = PermissionService.check_bulk_permission(
            request.user,
            database_ids,
            required_level,
        )
        if not allowed:
            denied_str = ", ".join(denied[:5])
            msg = f"Access denied for databases: {denied_str}"
            if len(denied) > 5:
                msg += f" and {len(denied) - 5} more"
            return Response({
                "success": False,
                "error": {"code": "PERMISSION_DENIED", "message": msg},
            }, status=403)

    merged_params = dict(params) if isinstance(params, dict) else {}
    connection_dict = dict(connection) if isinstance(connection, dict) else {}

    for token in additional_args:
        t = str(token or "").strip().lower()
        if t in {"--pid", "-p"} or t.startswith("--pid=") or t.startswith("-p=") or t.startswith("-p "):
            return Response({
                "success": False,
                "error": {"code": "PID_IN_ARGS_NOT_ALLOWED", "message": "Use connection.pid instead of --pid in additional_args"},
            }, status=400)

    flattened_connection = flatten_connection_params(connection_dict) if connection_dict else {}
    if flattened_connection:
        conflicts = detect_connection_option_conflicts(
            connection_params=flattened_connection,
            additional_args=list(additional_args or []),
        )
        if conflicts:
            conflict_list = ", ".join(sorted(set(conflicts)))
            return Response({
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"duplicate driver-level options in additional_args: {conflict_list}",
                },
            }, status=400)

        if isinstance(params, dict) and params:
            overlap = [
                key
                for key in flattened_connection.keys()
                if key in params and params.get(key) not in (None, "")
            ]
            if overlap:
                overlap_list = ", ".join(sorted(set(str(k) for k in overlap)))
                return Response({
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": f"driver-level options must be provided via connection (not params): {overlap_list}",
                    },
                }, status=400)

    if "pid" not in connection_dict:
        for key, value in list(merged_params.items()):
            if str(key or "").strip().lower() != "pid":
                continue
            if value is None or value == "":
                break
            try:
                connection_dict["pid"] = int(value)
                merged_params.pop(key, None)
            except (TypeError, ValueError):
                return Response({
                    "success": False,
                    "error": {"code": "PID_INVALID", "message": "pid must be an integer"},
                }, status=400)
            break

    if connection_dict.get("pid") is not None:
        env = (os.environ.get("APP_ENV") or os.environ.get("ENVIRONMENT") or "").strip().lower()
        if env in {"prod", "production"}:
            return Response({
                "success": False,
                "error": {"code": "PID_NOT_ALLOWED", "message": "--pid is not allowed in production"},
            }, status=400)

    pre_args = build_ibcmd_connection_args(
        driver_schema=catalog.get("driver_schema") if isinstance(catalog, dict) else None,
        connection=connection_dict,
    )

    try:
        builder = build_ibcmd_cli_argv_manual if mode == "manual" else build_ibcmd_cli_argv
        argv, argv_masked = builder(command=command, params=merged_params, additional_args=additional_args, pre_args=pre_args)
    except ValueError as exc:
        return Response({
            "success": False,
            "error": {"code": "VALIDATION_ERROR", "message": str(exc)},
        }, status=400)

    payload_data = {
        "command_id": command_id,
        "mode": mode,
        "argv": argv,
        "argv_masked": argv_masked,
        "stdin": stdin,
        "connection": connection_dict,
    }
    payload_options: dict[str, Any] = {}
    if scope == "global":
        payload_options["target_scope"] = "global"
        payload_data["auth_database_id"] = str(auth_database_id)

        tmp_payload = {"data": payload_data, "filters": {}, "options": {}}
        target_ref = OperationsService._compute_global_target_ref(tmp_payload)
        if not target_ref:
            return Response({
                "success": False,
                "error": {"code": "MISSING_CONNECTION", "message": "connection is required for global scope"},
            }, status=400)

        payload_options["target_ref"] = target_ref

        if hasattr(OperationsService, "_extract_target_scope"):
            try:
                from apps.operations.redis_client import redis_client
                if redis_client.check_global_target_lock(target_ref):
                    return Response({
                        "success": False,
                        "error": {"code": "GLOBAL_TARGET_LOCKED", "message": "Global target already in progress"},
                    }, status=409)
            except Exception:
                pass

    payload = {"data": payload_data, "filters": {}, "options": payload_options}

    databases = []
    if scope == "per_database":
        databases = list(Database.objects.filter(id__in=database_ids))
        found = {str(db.id) for db in databases}
        missing = [db_id for db_id in database_ids if db_id not in found]
        if missing:
            return Response({
                "success": False,
                "error": {
                    "code": "UNKNOWN_DATABASE",
                    "message": f"Unknown database_ids: {', '.join(missing[:5])}",
                },
            }, status=400)

    operation_id = str(uuid.uuid4())
    operation_name = f"ibcmd_cli {command_id}"
    if scope == "per_database":
        operation_name = f"{operation_name} - {len(databases)} databases"
    else:
        operation_name = f"{operation_name} (global)"

    batch_operation = BatchOperation.objects.create(
        id=operation_id,
        name=operation_name,
        operation_type=BatchOperation.TYPE_IBCMD_CLI,
        target_entity="Infobase" if scope == "per_database" else "StandaloneServer",
        status=BatchOperation.STATUS_PENDING,
        payload=payload,
        config={
            "batch_size": 1,
            "timeout_seconds": timeout_seconds,
            "retry_count": 1,
            "priority": "normal",
        },
        total_tasks=1 if scope == "global" else len(databases),
        created_by=request.user.username if request.user else "system",
        metadata={
            "tags": (
                ["ibcmd", "ibcmd_cli", command_id]
                if not legacy_operation_type
                else ["ibcmd", "ibcmd_cli", command_id, f"legacy:{legacy_operation_type}"]
            ),
            "command_id": command_id,
            "risk_level": risk_level,
            "scope": scope,
            "mode": mode,
            "actor_roles": get_actor_roles(request.user),
            "catalog_base_version": str(effective.base_version),
            "catalog_base_version_id": str(effective.base_version_id),
            "catalog_overrides_version": str(effective.overrides_version) if effective.overrides_version else None,
            "catalog_overrides_version_id": (
                str(effective.overrides_version_id) if effective.overrides_version_id else None
            ),
            "legacy_operation_type": legacy_operation_type,
        },
    )

    if scope == "global":
        Task.objects.create(
            id=str(uuid.uuid4()),
            batch_operation=batch_operation,
            database=None,
            status=Task.STATUS_PENDING,
        )
    else:
        batch_operation.target_databases.set(databases)
        Task.objects.bulk_create([
            Task(
                id=str(uuid.uuid4()),
                batch_operation=batch_operation,
                database=db,
                status=Task.STATUS_PENDING,
            )
            for db in databases
        ])

    enqueue_res = OperationsService.enqueue_operation(operation_id)
    if not enqueue_res.success:
        if enqueue_res.status == "duplicate":
            batch_operation.status = BatchOperation.STATUS_CANCELLED
            batch_operation.metadata["error"] = enqueue_res.error or "duplicate"
            batch_operation.save(update_fields=["status", "metadata", "updated_at"])
            return Response({
                "success": False,
                "error": {"code": "DUPLICATE", "message": enqueue_res.error or "duplicate"},
            }, status=409)

        batch_operation.status = BatchOperation.STATUS_FAILED
        batch_operation.metadata["error"] = enqueue_res.error or "enqueue_failed"
        batch_operation.save(update_fields=["status", "metadata", "updated_at"])
        return Response({
            "success": False,
            "error": {"code": "ENQUEUE_FAILED", "message": "Failed to queue operation"},
        }, status=500)

    return Response({
        "operation_id": operation_id,
        "status": "queued",
        "total_tasks": batch_operation.total_tasks,
        "message": f"ibcmd_cli queued: {command_id}",
    }, status=http_status.HTTP_202_ACCEPTED)

# =============================================================================
# SSE Streaming
# =============================================================================


def _get_redis_connection():
    """Get Redis connection for SSE tickets."""
    redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    return redis_module.from_url(redis_url, decode_responses=True)


def _get_async_redis_connection():
    redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    return redis_async.from_url(redis_url, decode_responses=True)


def _get_max_live_streams() -> int:
    setting = RuntimeSetting.objects.filter(key=OP_SSE_MAX_STREAMS_KEY).first()
    value = setting.value if setting else OP_SSE_MAX_STREAMS_DEFAULT
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return OP_SSE_MAX_STREAMS_DEFAULT
    return parsed if parsed > 0 else OP_SSE_MAX_STREAMS_DEFAULT


async def _get_max_live_streams_async() -> int:
    return await sync_to_async(_get_max_live_streams, thread_sensitive=True)()


def _get_max_mux_streams() -> int:
    setting = RuntimeSetting.objects.filter(key=OP_MUX_MAX_STREAMS_KEY).first()
    value = setting.value if setting else OP_MUX_MAX_STREAMS_DEFAULT
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return OP_MUX_MAX_STREAMS_DEFAULT
    return parsed if parsed > 0 else OP_MUX_MAX_STREAMS_DEFAULT


async def _get_max_mux_streams_async() -> int:
    return await sync_to_async(_get_max_mux_streams, thread_sensitive=True)()


def _get_max_mux_subscriptions() -> int:
    setting = RuntimeSetting.objects.filter(key=OP_MUX_MAX_SUBSCRIPTIONS_KEY).first()
    value = setting.value if setting else OP_MUX_MAX_SUBSCRIPTIONS_DEFAULT
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return OP_MUX_MAX_SUBSCRIPTIONS_DEFAULT
    return parsed if parsed > 0 else OP_MUX_MAX_SUBSCRIPTIONS_DEFAULT


async def _get_max_mux_subscriptions_async() -> int:
    return await sync_to_async(_get_max_mux_subscriptions, thread_sensitive=True)()


def _count_active_streams(redis_conn, user_id: int) -> int:
    pattern = f"{OP_SSE_ACTIVE_PREFIX}{user_id}:*"
    count = 0
    for _ in redis_conn.scan_iter(match=pattern, count=100):
        count += 1
    return count


def _count_active_mux_streams(redis_conn, user_id: int) -> int:
    pattern = f"{OP_MUX_ACTIVE_PREFIX}{user_id}:*"
    count = 0
    for _ in redis_conn.scan_iter(match=pattern, count=100):
        count += 1
    return count


async def _count_active_streams_async(redis_conn, user_id: int) -> int:
    pattern = f"{OP_SSE_ACTIVE_PREFIX}{user_id}:*"
    count = 0
    cursor = 0
    while True:
        cursor, keys = await redis_conn.scan(cursor=cursor, match=pattern, count=100)
        count += len(keys)
        if cursor == 0:
            break
    return count


async def _count_active_mux_streams_async(redis_conn, user_id: int) -> int:
    pattern = f"{OP_MUX_ACTIVE_PREFIX}{user_id}:*"
    count = 0
    cursor = 0
    while True:
        cursor, keys = await redis_conn.scan(cursor=cursor, match=pattern, count=100)
        count += len(keys)
        if cursor == 0:
            break
    return count


async def _validate_sse_ticket_async(ticket: str) -> tuple:
    """
    Validate and consume SSE ticket (async).

    Returns:
        (ticket_data, error_message) - ticket_data is None if validation failed
    """
    redis_conn = _get_async_redis_connection()
    try:
        ticket_key = f"{SSE_TICKET_PREFIX}{ticket}"
        pipe = redis_conn.pipeline()
        pipe.get(ticket_key)
        pipe.delete(ticket_key)
        results = await pipe.execute()

        ticket_data_raw = results[0]
        if not ticket_data_raw:
            return None, "Invalid or expired ticket"

        return json.loads(ticket_data_raw), None
    finally:
        await redis_conn.close()


async def _authenticate_legacy_token_async(token: str):
    def _do_auth():
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        if not user:
            raise AuthenticationFailed('User not found')
        return user

    return await sync_to_async(_do_auth, thread_sensitive=True)()


async def _validate_mux_ticket_async(ticket: str) -> tuple:
    """
    Validate and consume multiplex SSE ticket (async).

    Returns:
        (ticket_data, error_message) - ticket_data is None if validation failed
    """
    redis_conn = _get_async_redis_connection()
    try:
        ticket_key = f"{SSE_MUX_TICKET_PREFIX}{ticket}"
        pipe = redis_conn.pipeline()
        pipe.get(ticket_key)
        pipe.delete(ticket_key)
        results = await pipe.execute()

        ticket_data_raw = results[0]
        if not ticket_data_raw:
            return None, "Invalid or expired ticket"

        return json.loads(ticket_data_raw), None
    finally:
        await redis_conn.close()
@extend_schema(
    tags=['v2'],
    summary='Get SSE stream ticket',
    description='''
    Obtain a short-lived, single-use ticket for SSE stream authentication.

    The ticket is valid for 30 seconds and can only be used once.
    This allows secure SSE connections without exposing JWT tokens in URLs.
    ''',
    request=SSETicketRequestSerializer,
    responses={
        200: SSETicketResponseSerializer,
        400: OperationErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: OperationErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_stream_ticket(request):
    """
    POST /api/v2/operations/stream-ticket/

    Get a short-lived ticket for SSE stream authentication.

    Request Body:
        {"operation_id": "uuid"}

    Response:
        {
            "ticket": "random_string",
            "expires_in": 30,
            "stream_url": "/api/v2/operations/stream/?ticket=..."
        }
    """
    start_time = time.monotonic()
    endpoint = "operations.stream_ticket"
    serializer = SSETicketRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    operation_id = serializer.validated_data['operation_id']
    client_id = serializer.validated_data.get('client_id')

    # Verify operation exists and user has permission
    operation = BatchOperation.objects.filter(id=operation_id).first()
    if not operation:
        record_api_v2_duration(endpoint, "not_found", time.monotonic() - start_time)
        record_sse_ticket("operations", "not_found")
        return Response({
            'success': False,
            'error': {
                'code': 'OPERATION_NOT_FOUND',
                'message': 'Operation not found'
            }
        }, status=404)

    # Authorization check: user must own the operation or be staff
    if operation.created_by != request.user.username and not request.user.is_staff:
        record_api_v2_duration(endpoint, "forbidden", time.monotonic() - start_time)
        record_sse_ticket("operations", "forbidden")
        return Response({
            'success': False,
            'error': {
                'code': 'FORBIDDEN',
                'message': 'You do not have permission to subscribe to this operation'
            }
        }, status=403)

    redis_conn = _get_redis_connection()
    active_key = f"{OP_SSE_ACTIVE_PREFIX}{request.user.id}:{operation_id}"

    try:
        max_live_streams = _get_max_live_streams()
        if max_live_streams > 0:
            active_count = _count_active_streams(redis_conn, request.user.id)
            if active_count >= max_live_streams:
                record_api_v2_duration(endpoint, "limit", time.monotonic() - start_time)
                record_sse_ticket("operations", "limit")
                response = Response({
                    'success': False,
                    'error': {
                        'code': 'STREAM_LIMIT_EXCEEDED',
                        'message': 'Too many active streams',
                        'max_streams': max_live_streams,
                    }
                }, status=429)
                response['Retry-After'] = "60"
                return response

        ttl = redis_conn.ttl(active_key)
        if ttl and ttl > 0:
            if client_id:
                current_value = redis_conn.get(active_key)
                if current_value == client_id:
                    record_api_v2_duration(endpoint, "ok", time.monotonic() - start_time)
                    record_sse_ticket("operations", "ok")
                    ticket = secrets.token_urlsafe(32)
                    ticket_data = {
                        'user_id': request.user.id,
                        'username': request.user.username,
                        'operation_id': operation_id,
                        'client_id': client_id,
                        'created_at': timezone.now().isoformat(),
                    }
                    redis_conn.setex(
                        f"{SSE_TICKET_PREFIX}{ticket}",
                        SSE_TICKET_TTL,
                        json.dumps(ticket_data)
                    )
                    return Response({
                        'ticket': ticket,
                        'expires_in': SSE_TICKET_TTL,
                        'stream_url': f'/api/v2/operations/stream/?ticket={ticket}'
                    })
            record_api_v2_duration(endpoint, "conflict", time.monotonic() - start_time)
            record_sse_ticket("operations", "conflict")
            response = Response({
                'success': False,
                'error': {
                    'code': 'STREAM_ALREADY_ACTIVE',
                    'message': 'Operation stream already active for this user',
                    'retry_after': ttl,
                }
            }, status=429)
            response['Retry-After'] = str(ttl)
            return response

        # Generate secure random ticket
        ticket = secrets.token_urlsafe(32)

        ticket_data = {
            'user_id': request.user.id,
            'username': request.user.username,
            'operation_id': operation_id,
            'client_id': client_id,
            'created_at': timezone.now().isoformat(),
        }

        redis_conn.setex(
            f"{SSE_TICKET_PREFIX}{ticket}",
            SSE_TICKET_TTL,
            json.dumps(ticket_data)
        )
        record_api_v2_duration(endpoint, "ok", time.monotonic() - start_time)
        record_sse_ticket("operations", "ok")
    except Exception as exc:
        record_api_v2_duration(endpoint, "error", time.monotonic() - start_time)
        record_api_v2_error(endpoint, exc.__class__.__name__)
        record_sse_ticket("operations", "error")
        raise
    finally:
        redis_conn.close()

    return Response({
        'ticket': ticket,
        'expires_in': SSE_TICKET_TTL,
        'stream_url': f'/api/v2/operations/stream/?ticket={ticket}'
    })


@extend_schema(
    tags=['v2'],
    summary='Get SSE stream status',
    description='Get active SSE stream count for current user.',
    responses={
        200: OperationStreamStatusSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_stream_status(request):
    redis_conn = _get_redis_connection()
    try:
        active_count = _count_active_streams(redis_conn, request.user.id)
    finally:
        redis_conn.close()

    return Response({
        "active_streams": active_count,
        "max_streams": _get_max_live_streams(),
    })


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


@extend_schema(
    tags=["v2"],
    summary="List driver command shortcuts",
    description="List current user's saved command shortcuts (per driver).",
    parameters=[
        OpenApiParameter(
            name="driver",
            type=str,
            required=False,
            description="Driver name (currently: ibcmd).",
        ),
    ],
    responses={
        200: ListDriverCommandShortcutsResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_driver_command_shortcuts(request):
    driver = str(request.query_params.get("driver") or "ibcmd").strip().lower()
    if driver != "ibcmd":
        return Response(
            {"success": False, "error": {"code": "INVALID_DRIVER", "message": "Only driver=ibcmd is supported"}},
            status=400,
        )

    qs = DriverCommandShortcut.objects.filter(user=request.user, driver=driver).order_by("title", "created_at")

    resolved = resolve_driver_catalog_versions(driver)
    if resolved.base_version is not None:
        try:
            effective = get_effective_driver_catalog(
                driver=driver,
                base_version=resolved.base_version,
                overrides_version=resolved.overrides_version,
            )
            catalog = filter_catalog_for_user(request.user, effective.catalog)
            commands_by_id = catalog.get("commands_by_id") if isinstance(catalog, dict) else None
            if isinstance(commands_by_id, dict) and commands_by_id:
                qs = qs.filter(command_id__in=list(commands_by_id.keys()))
        except Exception:
            pass
    items = [
        {
            "id": row.id,
            "driver": row.driver,
            "command_id": row.command_id,
            "title": row.title,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in qs
    ]

    return Response({"items": items, "count": len(items)})


@extend_schema(
    tags=["v2"],
    summary="Create driver command shortcut",
    description="Create a per-user shortcut to a schema-driven driver command (command_id).",
    request=CreateDriverCommandShortcutRequestSerializer,
    responses={
        201: DriverCommandShortcutSerializer,
        400: OperationErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_driver_command_shortcut(request):
    serializer = CreateDriverCommandShortcutRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    driver = str(serializer.validated_data["driver"] or "").strip().lower()
    command_id = str(serializer.validated_data["command_id"] or "").strip()
    title = str(serializer.validated_data["title"] or "").strip()

    if not command_id:
        return Response(
            {"success": False, "error": {"code": "MISSING_COMMAND_ID", "message": "command_id is required"}},
            status=400,
        )
    if not title:
        return Response(
            {"success": False, "error": {"code": "MISSING_TITLE", "message": "title is required"}},
            status=400,
        )

    resolved = resolve_driver_catalog_versions(driver)
    if resolved.base_version is None:
        return Response(
            {"success": False, "error": {"code": "CATALOG_NOT_AVAILABLE", "message": f"{driver} catalog is not imported yet"}},
            status=400,
        )

    effective = get_effective_driver_catalog(
        driver=driver,
        base_version=resolved.base_version,
        overrides_version=resolved.overrides_version,
    )
    catalog = filter_catalog_for_user(request.user, effective.catalog)
    commands_by_id = catalog.get("commands_by_id") if isinstance(catalog, dict) else None
    if not isinstance(commands_by_id, dict):
        return Response(
            {"success": False, "error": {"code": "CATALOG_INVALID", "message": f"{driver} catalog is invalid"}},
            status=500,
        )

    cmd = commands_by_id.get(command_id)
    if not isinstance(cmd, dict) or cmd.get("disabled") is True:
        return Response(
            {"success": False, "error": {"code": "UNKNOWN_COMMAND", "message": f"Unknown command_id: {command_id}"}},
            status=400,
        )

    shortcut = DriverCommandShortcut.objects.create(
        user=request.user,
        driver=driver,
        command_id=command_id,
        title=title,
    )

    return Response(
        {
            "id": shortcut.id,
            "driver": shortcut.driver,
            "command_id": shortcut.command_id,
            "title": shortcut.title,
            "created_at": shortcut.created_at,
            "updated_at": shortcut.updated_at,
        },
        status=201,
    )


@extend_schema(
    tags=["v2"],
    summary="Delete driver command shortcut",
    description="Delete a per-user command shortcut by id.",
    request=DeleteDriverCommandShortcutRequestSerializer,
    responses={
        200: OpenApiResponse(description="OK"),
        400: OperationErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        404: OperationErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def delete_driver_command_shortcut(request):
    serializer = DeleteDriverCommandShortcutRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    shortcut_id = serializer.validated_data["shortcut_id"]
    qs = DriverCommandShortcut.objects.filter(id=shortcut_id, user=request.user)
    if not qs.exists():
        return Response(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Shortcut not found"}},
            status=404,
        )

    qs.delete()
    return Response({"success": True, "deleted": True})


@extend_schema(
    tags=['v2'],
    summary='Get CLI command catalog',
    description='List supported DESIGNER batch commands for designer_cli.',
    responses={
        200: CliCommandCatalogResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cli_command_catalog(request):
    roles_hash = compute_actor_roles_hash(request.user)

    resolved = resolve_driver_catalog_versions("cli")
    if resolved.base_version is None:
        payload = {
            "version": "unknown",
            "source": "command_schemas",
            "generated_at": "",
            "commands": [],
        }
        etag = compute_driver_catalog_etag(
            driver="cli",
            base_version_id=None,
            overrides_version_id=None,
            roles_hash=roles_hash,
        )
        response = Response(payload)
        response["ETag"] = etag
        response["Cache-Control"] = "private, max-age=0"
        return response

    effective = get_effective_driver_catalog(
        driver="cli",
        base_version=resolved.base_version,
        overrides_version=resolved.overrides_version,
    )
    catalog_v2 = filter_catalog_for_user(request.user, effective.catalog)

    source_meta = catalog_v2.get("source") if isinstance(catalog_v2, dict) else {}
    if not isinstance(source_meta, dict):
        source_meta = {}

    version_str = str(catalog_v2.get("platform_version") or "").strip() or "unknown"
    source_str = str(
        source_meta.get("doc_url")
        or source_meta.get("doc_id")
        or source_meta.get("hint")
        or "command_schemas"
    ).strip() or "command_schemas"
    generated_at = str(catalog_v2.get("generated_at") or "").strip()

    commands_by_id = catalog_v2.get("commands_by_id") if isinstance(catalog_v2, dict) else {}
    if not isinstance(commands_by_id, dict):
        commands_by_id = {}

    commands = []
    for cmd_id in sorted(k for k in commands_by_id.keys() if isinstance(k, str) and k.strip()):
        cmd = commands_by_id.get(cmd_id)
        if not isinstance(cmd, dict):
            continue

        item: dict[str, Any] = {
            "id": cmd_id,
            "label": str(cmd.get("label") or cmd_id),
        }

        description = cmd.get("description")
        if isinstance(description, str) and description:
            item["description"] = description

        argv = cmd.get("argv")
        if isinstance(argv, list) and argv and all(isinstance(x, str) and x.strip() for x in argv):
            item["usage"] = " ".join(str(x).strip() for x in argv if str(x).strip())

        source_section = cmd.get("source_section")
        if isinstance(source_section, str) and source_section:
            item["source_section"] = source_section

        params_by_name = cmd.get("params_by_name")
        if isinstance(params_by_name, dict) and params_by_name:
            params = []
            for name, schema in sorted(params_by_name.items(), key=lambda kv: str(kv[0])):
                if not isinstance(name, str) or not name.strip() or not isinstance(schema, dict):
                    continue

                param: dict[str, Any] = {"name": name}
                kind = str(schema.get("kind") or "").strip() or "flag"
                param["kind"] = kind

                label = schema.get("label")
                if isinstance(label, str) and label:
                    param["label"] = label

                required = schema.get("required")
                if isinstance(required, bool):
                    param["required"] = required

                expects_value = schema.get("expects_value")
                if isinstance(expects_value, bool):
                    param["expects_value"] = expects_value

                flag = schema.get("flag")
                if isinstance(flag, str) and flag:
                    param["flag"] = flag

                params.append(param)

            if params:
                commands.append({**item, "params": params})
                continue

        commands.append(item)

    payload = {
        "version": version_str,
        "source": source_str,
        "generated_at": generated_at,
        "commands": commands,
    }

    etag = compute_driver_catalog_etag(
        driver="cli",
        base_version_id=effective.base_version_id,
        overrides_version_id=effective.overrides_version_id,
        roles_hash=roles_hash,
    )
    response = Response(payload)
    response["ETag"] = etag
    response["Cache-Control"] = "private, max-age=0"
    return response


@extend_schema(
    tags=["v2"],
    summary="Get driver command catalog (v2)",
    description=(
        "Return schema-driven command catalog for the requested driver.\n\n"
        "Supports conditional requests via ETag/If-None-Match (returns 304)."
    ),
    parameters=[
        OpenApiParameter(
            name="driver",
            type=str,
            required=True,
            description="Driver name (cli/ibcmd)",
        ),
    ],
    responses={
        200: DriverCommandsResponseV2Serializer,
        304: OpenApiResponse(description="Not Modified"),
        400: OperationErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_driver_commands(request):
    driver = str(request.query_params.get("driver") or "").strip()
    if not driver:
        return Response({
            "success": False,
            "error": {"code": "MISSING_DRIVER", "message": "driver is required"},
        }, status=400)

    driver = driver.lower()
    if driver not in {"cli", "ibcmd"}:
        return Response({
            "success": False,
            "error": {"code": "UNKNOWN_DRIVER", "message": f"Unknown driver: {driver}"},
        }, status=400)

    roles_hash = compute_actor_roles_hash(request.user)

    resolved = resolve_driver_catalog_versions(driver)
    if resolved.base_version is not None:
        base_version_id = str(resolved.base_version.id)
        overrides_version_id = str(resolved.overrides_version.id) if resolved.overrides_version is not None else None
        current_etag = compute_driver_catalog_etag(
            driver=driver,
            base_version_id=base_version_id,
            overrides_version_id=overrides_version_id,
            roles_hash=roles_hash,
        )
        if request.headers.get("If-None-Match") == current_etag:
            response = Response(status=304)
            response["ETag"] = current_etag
            return response

        try:
            effective = get_effective_driver_catalog(
                driver=driver,
                base_version=resolved.base_version,
                overrides_version=resolved.overrides_version,
            )
            catalog = filter_catalog_for_user(request.user, effective.catalog)
            etag = compute_driver_catalog_etag(
                driver=driver,
                base_version_id=effective.base_version_id,
                overrides_version_id=effective.overrides_version_id,
                roles_hash=roles_hash,
            )

            payload = {
                "driver": driver,
                "base_version": str(effective.base_version),
                "overrides_version": str(effective.overrides_version) if effective.overrides_version else None,
                "generated_at": str(catalog.get("generated_at") or ""),
                "catalog": catalog,
            }
            response = Response(payload)
            response["ETag"] = etag
            response["Cache-Control"] = "private, max-age=0"
            return response
        except (ArtifactStorageError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            error_message = str(exc)
            if isinstance(exc, ArtifactStorageError):
                logger.warning(
                    "Failed to load driver catalog from storage",
                    extra={"driver": driver, "error": error_message},
                )
                error_code = "STORAGE_ERROR"
            else:
                logger.warning(
                    "Failed to parse driver catalog",
                    extra={"driver": driver, "error": error_message},
                )
                error_code = "CATALOG_INVALID"

        lkg = get_effective_driver_catalog_lkg(driver)
        if lkg is not None:
            etag = compute_driver_catalog_etag(
                driver=driver,
                base_version_id=lkg.base_version_id,
                overrides_version_id=lkg.overrides_version_id,
                roles_hash=roles_hash,
            )
            if request.headers.get("If-None-Match") == etag:
                response = Response(status=304)
                response["ETag"] = etag
                return response

            catalog = filter_catalog_for_user(request.user, lkg.catalog)
            payload = {
                "driver": driver,
                "base_version": str(lkg.base_version),
                "overrides_version": str(lkg.overrides_version) if lkg.overrides_version else None,
                "generated_at": str(catalog.get("generated_at") or ""),
                "catalog": catalog,
            }
            response = Response(payload)
            response["ETag"] = etag
            response["Cache-Control"] = "private, max-age=0"
            return response

        return Response(
            {"success": False, "error": {"code": error_code, "message": error_message}},
            status=500,
        )

    payload = {
        "driver": driver,
        "base_version": "unknown",
        "overrides_version": None,
        "generated_at": "",
        "catalog": {
            "catalog_version": 2,
            "driver": driver,
            "platform_version": "",
            "source": {"type": "not_available", "hint": f"{driver} catalog is not imported yet"},
            "generated_at": "",
            "commands_by_id": {},
        },
    }
    etag = compute_driver_catalog_etag(
        driver=driver,
        base_version_id=None,
        overrides_version_id=None,
        roles_hash=roles_hash,
    )

    if request.headers.get("If-None-Match") == etag:
        response = Response(status=304)
        response["ETag"] = etag
        return response

    response = Response(payload)
    response["ETag"] = etag
    response["Cache-Control"] = "private, max-age=0"
    return response


@extend_schema(
    tags=['v2'],
    summary='Get multiplex SSE stream status',
    description='Get active multiplex SSE stream count for current user.',
    responses={
        200: OperationMuxStreamStatusSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_stream_mux_status(request):
    redis_conn = _get_redis_connection()
    try:
        active_count = _count_active_mux_streams(redis_conn, request.user.id)
        sub_key = f"{OP_MUX_SUB_PREFIX}{request.user.id}"
        active_subscriptions = redis_conn.scard(sub_key)
    finally:
        redis_conn.close()

    return Response({
        "active_streams": active_count,
        "max_streams": _get_max_mux_streams(),
        "active_subscriptions": active_subscriptions,
        "max_subscriptions": _get_max_mux_subscriptions(),
    })


def _resolve_operation_access(user, operations):
    allowed = []
    denied = []

    if user.is_staff:
        return [str(op.id) for op in operations], denied

    op_db_ids: dict[str, list[str]] = {}
    all_db_ids: set[str] = set()
    for op in operations:
        db_ids = [str(db.id) for db in op.target_databases.all()]
        op_db_ids[str(op.id)] = db_ids
        all_db_ids.update(db_ids)

    databases = list(
        Database.objects.filter(id__in=all_db_ids)
        .select_related('cluster')
        .only('id', 'cluster_id')
    )
    levels = PermissionService.get_user_levels_for_databases_bulk(user, databases)

    for op in operations:
        op_id = str(op.id)
        db_ids = op_db_ids.get(op_id, [])
        if not db_ids:
            if op.created_by == user.username:
                allowed.append(op_id)
            else:
                denied.append(op_id)
            continue

        has_access = True
        for db_id in db_ids:
            level = levels.get(db_id)
            if level is None or level < PermissionLevel.VIEW:
                has_access = False
                break
        if has_access:
            allowed.append(op_id)
        else:
            denied.append(op_id)

    return allowed, denied


@extend_schema(
    tags=['v2'],
    summary='Subscribe to multiplex stream operations',
    request=OperationMuxSubscribeSerializer,
    responses={
        200: OpenApiResponse(description='Subscription updated'),
        401: OpenApiResponse(description='Unauthorized'),
        429: OperationErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subscribe_operation_streams(request):
    serializer = OperationMuxSubscribeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    operation_ids = list({str(op_id) for op_id in serializer.validated_data['operation_ids']})

    operations = list(
        BatchOperation.objects.filter(id__in=operation_ids).prefetch_related('target_databases')
    )
    found_ids = {str(op.id) for op in operations}
    missing = [op_id for op_id in operation_ids if op_id not in found_ids]

    allowed, denied = _resolve_operation_access(request.user, operations)

    redis_conn = _get_redis_connection()
    try:
        sub_key = f"{OP_MUX_SUB_PREFIX}{request.user.id}"
        last_key = f"{OP_MUX_LAST_PREFIX}{request.user.id}"
        existing = redis_conn.smembers(sub_key)

        allowed_new = [op_id for op_id in allowed if op_id not in existing]
        max_subscriptions = _get_max_mux_subscriptions()
        if len(existing) + len(allowed_new) > max_subscriptions:
            response = Response({
                'success': False,
                'error': {
                    'code': 'STREAM_SUBSCRIPTION_LIMIT',
                    'message': 'Too many subscribed operations',
                    'max_subscriptions': max_subscriptions,
                    'current_subscriptions': len(existing),
                    'requested': len(allowed_new),
                }
            }, status=429)
            response['Retry-After'] = "60"
            return response

        if allowed_new:
            redis_conn.sadd(sub_key, *allowed_new)
            mapping = {op_id: '$' for op_id in allowed_new}
            redis_conn.hset(last_key, mapping=mapping)

        return Response({
            "subscribed": allowed,
            "denied": denied,
            "missing": missing,
            "active_subscriptions": len(existing) + len(allowed_new),
            "max_subscriptions": max_subscriptions,
        })
    finally:
        redis_conn.close()


@extend_schema(
    tags=['v2'],
    summary='Unsubscribe from multiplex stream operations',
    request=OperationMuxUnsubscribeSerializer,
    responses={
        200: OpenApiResponse(description='Subscription updated'),
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unsubscribe_operation_streams(request):
    serializer = OperationMuxUnsubscribeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    operation_ids = list({str(op_id) for op_id in serializer.validated_data['operation_ids']})

    redis_conn = _get_redis_connection()
    try:
        sub_key = f"{OP_MUX_SUB_PREFIX}{request.user.id}"
        last_key = f"{OP_MUX_LAST_PREFIX}{request.user.id}"
        if operation_ids:
            redis_conn.srem(sub_key, *operation_ids)
            redis_conn.hdel(last_key, *operation_ids)
        active_count = redis_conn.scard(sub_key)
        return Response({
            "unsubscribed": operation_ids,
            "active_subscriptions": active_count,
            "max_subscriptions": _get_max_mux_subscriptions(),
        })
    finally:
        redis_conn.close()


@extend_schema(
    tags=['v2'],
    summary='Get multiplex SSE stream ticket',
    request=OperationMuxTicketRequestSerializer,
    responses={
        200: SSETicketResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        429: OperationErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_mux_stream_ticket(request):
    serializer = OperationMuxTicketRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    client_id = serializer.validated_data.get('client_id')

    redis_conn = _get_redis_connection()
    active_key = f"{OP_MUX_ACTIVE_PREFIX}{request.user.id}"

    try:
        max_streams = _get_max_mux_streams()
        if max_streams > 0:
            active_count = _count_active_mux_streams(redis_conn, request.user.id)
            if active_count >= max_streams:
                response = Response({
                    'success': False,
                    'error': {
                        'code': 'STREAM_LIMIT_EXCEEDED',
                        'message': 'Too many active streams',
                        'max_streams': max_streams,
                    }
                }, status=429)
                response['Retry-After'] = "60"
                return response

        ttl = redis_conn.ttl(active_key)
        if ttl and ttl > 0:
            if client_id:
                current_value = redis_conn.get(active_key)
                if current_value == client_id:
                    ticket = secrets.token_urlsafe(32)
                    ticket_data = {
                        'user_id': request.user.id,
                        'username': request.user.username,
                        'client_id': client_id,
                        'created_at': timezone.now().isoformat(),
                    }
                    redis_conn.setex(
                        f"{SSE_MUX_TICKET_PREFIX}{ticket}",
                        SSE_TICKET_TTL,
                        json.dumps(ticket_data)
                    )
                    return Response({
                        'ticket': ticket,
                        'expires_in': SSE_TICKET_TTL,
                        'stream_url': f'/api/v2/operations/stream-mux/?ticket={ticket}'
                    })
            response = Response({
                'success': False,
                'error': {
                    'code': 'STREAM_ALREADY_ACTIVE',
                    'message': 'Operation stream already active for this user',
                    'retry_after': ttl,
                }
            }, status=429)
            response['Retry-After'] = str(ttl)
            return response

        ticket = secrets.token_urlsafe(32)
        ticket_data = {
            'user_id': request.user.id,
            'username': request.user.username,
            'client_id': client_id,
            'created_at': timezone.now().isoformat(),
        }
        redis_conn.setex(
            f"{SSE_MUX_TICKET_PREFIX}{ticket}",
            SSE_TICKET_TTL,
            json.dumps(ticket_data)
        )
    finally:
        redis_conn.close()

    return Response({
        'ticket': ticket,
        'expires_in': SSE_TICKET_TTL,
        'stream_url': f'/api/v2/operations/stream-mux/?ticket={ticket}'
    })


async def operation_stream_mux(request):
    """
    GET /api/v2/operations/stream-mux/?ticket=xxx

    SSE endpoint for multiplex operation updates.
    """
    start_time = time.monotonic()
    endpoint = "operations.stream_mux"
    ticket = request.GET.get('ticket')

    if not ticket:
        record_api_v2_duration(endpoint, "unauthorized", time.monotonic() - start_time)
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'ticket is required'
            }
        }, status=401)

    ticket_data, error = await _validate_mux_ticket_async(ticket)
    if error:
        record_api_v2_duration(endpoint, "unauthorized", time.monotonic() - start_time)
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'INVALID_TICKET',
                'message': error
            }
        }, status=401)

    user_id = ticket_data.get('user_id')
    username = ticket_data.get('username')
    client_id = ticket_data.get('client_id')
    if not user_id:
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'INVALID_TICKET',
                'message': 'Missing user_id'
            }
        }, status=401)

    active_key = f"{OP_MUX_ACTIVE_PREFIX}{user_id}"
    active_value = client_id or secrets.token_urlsafe(12)
    active_conn = _get_async_redis_connection()
    try:
        max_streams = await _get_max_mux_streams_async()
        if max_streams > 0:
            active_count = await _count_active_mux_streams_async(active_conn, user_id)
            if active_count >= max_streams:
                record_api_v2_duration(endpoint, "limit", time.monotonic() - start_time)
                response = JsonResponse({
                    'success': False,
                    'error': {
                        'code': 'STREAM_LIMIT_EXCEEDED',
                        'message': 'Too many active streams',
                        'max_streams': max_streams,
                    }
                }, status=429)
                response['Retry-After'] = "60"
                return response

        if not await active_conn.set(active_key, active_value, nx=True, ex=OP_MUX_ACTIVE_TTL):
            current_value = await active_conn.get(active_key)
            if current_value != active_value:
                record_api_v2_duration(endpoint, "conflict", time.monotonic() - start_time)
                return JsonResponse({
                    'success': False,
                    'error': {
                        'code': 'STREAM_ALREADY_ACTIVE',
                        'message': 'Operation stream already active for this user'
                    }
                }, status=429)
            await active_conn.expire(active_key, OP_MUX_ACTIVE_TTL)
    finally:
        await active_conn.close()

    async def event_generator():
        logger.info(f"operation_stream_mux: Starting for user {username}")
        sse_connection_open("operations_mux")

        redis_conn = _get_async_redis_connection()
        sub_key = f"{OP_MUX_SUB_PREFIX}{user_id}"
        last_key = f"{OP_MUX_LAST_PREFIX}{user_id}"
        last_heartbeat = time.monotonic()
        stream_started_at = time.monotonic()
        last_event_at = stream_started_at

        try:
            while True:
                loop_start = time.monotonic()
                now = time.monotonic()
                if SSE_MAX_CONNECTION_SECONDS and now - stream_started_at > SSE_MAX_CONNECTION_SECONDS:
                    logger.info("operation_stream_mux: max connection time reached (user=%s)", username)
                    break
                if SSE_MAX_IDLE_SECONDS and now - last_event_at > SSE_MAX_IDLE_SECONDS:
                    logger.info("operation_stream_mux: idle timeout reached (user=%s)", username)
                    break
                subscriptions = await redis_conn.smembers(sub_key)
                if not subscriptions:
                    now = time.monotonic()
                    if now - last_heartbeat >= SSE_HEARTBEAT_INTERVAL_SECONDS:
                        try:
                            await redis_conn.expire(active_key, OP_MUX_ACTIVE_TTL)
                        except Exception:
                            pass
                        yield ": heartbeat\n\n"
                        last_heartbeat = now
                    record_sse_loop_duration("operations_mux", time.monotonic() - loop_start)
                    await asyncio.sleep(0.5)
                    continue

                last_ids = await redis_conn.hmget(last_key, *subscriptions)
                stream_map = {}
                for op_id, last_id in zip(subscriptions, last_ids):
                    stream_map[f"events:operation:{op_id}"] = last_id or '$'

                messages = await redis_conn.xread(stream_map, block=SSE_BLOCK_MS, count=10)
                if not messages:
                    now = time.monotonic()
                    if now - last_heartbeat >= SSE_HEARTBEAT_INTERVAL_SECONDS:
                        try:
                            await redis_conn.expire(active_key, OP_MUX_ACTIVE_TTL)
                        except Exception:
                            pass
                        yield ": heartbeat\n\n"
                        last_heartbeat = now
                    record_sse_loop_duration("operations_mux", time.monotonic() - loop_start)
                    continue

                for stream, stream_messages in messages:
                    op_id = stream.split(":")[-1]
                    for msg_id, fields in stream_messages:
                        event_data = fields.get('data', '{}')
                        event_type = fields.get('event_type') or 'message'
                        try:
                            await redis_conn.hset(last_key, op_id, msg_id)
                            await redis_conn.expire(active_key, OP_MUX_ACTIVE_TTL)
                        except Exception:
                            pass
                        yield f"event: {event_type}\n"
                        yield f"id: {msg_id}\n"
                        yield f"data: {event_data}\n\n"
                        last_event_at = time.monotonic()

                record_sse_loop_duration("operations_mux", time.monotonic() - loop_start)

        except asyncio.CancelledError:
            logger.info("operation_stream_mux: cancelled user=%s", username)
        except GeneratorExit:
            logger.info(f"operation_stream_mux: client disconnected user={username}")
        except Exception as e:
            logger.error(f"operation_stream_mux error: {e}")
            record_sse_stream_error("operations_mux", "event_loop")
            raise
        finally:
            try:
                current_value = await redis_conn.get(active_key)
                if current_value == active_value:
                    await redis_conn.delete(active_key)
                await redis_conn.close()
            except Exception:
                pass
            sse_connection_close("operations_mux")

    record_api_v2_duration(endpoint, "stream_start", time.monotonic() - start_time)
    response = StreamingHttpResponse(
        event_generator(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@extend_schema(
    tags=['v2'],
    summary='Operation SSE stream',
    description='SSE endpoint for real-time operation updates. Prefer ticket-based auth via /stream-ticket/.',
    parameters=[
        OpenApiParameter(
            name='ticket',
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description='Short-lived SSE ticket from /operations/stream-ticket/.',
        ),
        OpenApiParameter(
            name='operation_id',
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description='Operation ID (deprecated legacy token auth).',
        ),
        OpenApiParameter(
            name='token',
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description='Legacy token auth (deprecated).',
        ),
    ],
    responses={
        200: OpenApiResponse(description='SSE stream (text/event-stream)'),
        401: OpenApiResponse(description='Unauthorized'),
    },
)
@require_GET
async def operation_stream(request):
    """
    GET /api/v2/operations/stream/?ticket=xxx
    GET /api/v2/operations/stream/?operation_id=xxx&token=xxx (deprecated)

    SSE endpoint for real-time operation updates.

    Prefer ticket-based auth via /stream-ticket/ endpoint for security.
    """
    start_time = time.monotonic()
    endpoint = "operations.stream"
    ticket = request.GET.get('ticket')
    token = request.GET.get('token')
    operation_id = request.GET.get('operation_id')

    # Validate: need either ticket or (token + operation_id)
    if not ticket and not token:
        record_api_v2_duration(endpoint, "unauthorized", time.monotonic() - start_time)
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'ticket is required (use /stream-ticket/ to obtain)'
            }
        }, status=401)

    # Prefer ticket-based auth (secure)
    user_id = None
    if ticket:
        ticket_data, error = await _validate_sse_ticket_async(ticket)
        if error:
            record_api_v2_duration(endpoint, "unauthorized", time.monotonic() - start_time)
            return JsonResponse({
                'success': False,
                'error': {
                    'code': 'INVALID_TICKET',
                    'message': error
                }
            }, status=401)

        operation_id = ticket_data['operation_id']
        username = ticket_data['username']
        user_id = ticket_data.get("user_id")

    else:
        # Legacy token auth (deprecated - log warning)
        logger.warning(
            "SSE stream using deprecated token auth. "
            "Please migrate to ticket-based auth via /stream-ticket/"
        )

        if not operation_id:
            record_api_v2_duration(endpoint, "bad_request", time.monotonic() - start_time)
            return JsonResponse({
                'success': False,
                'error': {
                    'code': 'MISSING_PARAMETER',
                    'message': 'operation_id is required with token auth'
                }
            }, status=400)

        try:
            user = await _authenticate_legacy_token_async(token)
            username = user.username
            user_id = user.id
        except Exception as e:
            logger.error(f"SSE authentication failed: {e}")
            record_api_v2_duration(endpoint, "unauthorized", time.monotonic() - start_time)
            record_api_v2_error(endpoint, e.__class__.__name__)
            return JsonResponse({
                'success': False,
                'error': {
                    'code': 'INVALID_TOKEN',
                    'message': 'Invalid or expired token'
                }
            }, status=401)

    logger.info(f"SSE stream started for operation {operation_id} by user {username}")

    active_key = None
    active_value = None
    if user_id:
        active_key = f"{OP_SSE_ACTIVE_PREFIX}{user_id}:{operation_id}"
        active_value = ticket_data.get("client_id") if ticket else None
        if not active_value:
            active_value = secrets.token_urlsafe(12)
        active_conn = _get_async_redis_connection()
        try:
            max_live_streams = await _get_max_live_streams_async()
            if max_live_streams > 0:
                active_count = await _count_active_streams_async(active_conn, user_id)
                if active_count >= max_live_streams:
                    record_api_v2_duration(endpoint, "limit", time.monotonic() - start_time)
                    response = JsonResponse({
                        'success': False,
                        'error': {
                            'code': 'STREAM_LIMIT_EXCEEDED',
                            'message': 'Too many active streams',
                            'max_streams': max_live_streams,
                        }
                    }, status=429)
                    response['Retry-After'] = "60"
                    return response

            if not await active_conn.set(active_key, active_value, nx=True, ex=OP_SSE_ACTIVE_TTL):
                record_api_v2_duration(endpoint, "conflict", time.monotonic() - start_time)
                return JsonResponse({
                    'success': False,
                    'error': {
                        'code': 'STREAM_ALREADY_ACTIVE',
                        'message': 'Operation stream already active for this user'
                    }
                }, status=429)
        finally:
            await active_conn.close()

    async def event_generator():
        """Generator for SSE events using Redis Streams (XREAD)."""
        logger.info(f"event_generator: Starting for operation {operation_id}")
        sse_connection_open("operations")

        # Connect to Redis
        redis_conn = _get_async_redis_connection()
        stream_name = f"events:operation:{operation_id}"
        logger.info(f"event_generator: Will read from stream {stream_name}")
        stream_started_at = time.monotonic()
        last_event_at = stream_started_at

        # Send initial state
        try:
            operation = await sync_to_async(
                BatchOperation.objects.get,
                thread_sensitive=True,
            )(id=operation_id)
            logger.info(f"event_generator: Found operation with status {operation.status}")
            operation_metadata = operation.metadata or {}
            initial_event = {
                "version": "1.0",
                "operation_id": str(operation_id),
                "timestamp": timezone.now().isoformat(),
                "state": operation.status.upper(),
                "microservice": "orchestrator",
                "message": f"Operation status: {operation.status}",
                "trace_id": operation_metadata.get("trace_id"),
                "workflow_execution_id": operation_metadata.get("workflow_execution_id"),
                "node_id": operation_metadata.get("node_id"),
                "metadata": {
                    "operation_type": operation.operation_type,
                    "created_at": operation.created_at.isoformat(),
                }
            }
            logger.info("event_generator: Sending initial event")
            yield f"data: {json.dumps(initial_event)}\n\n"
            logger.info("event_generator: Initial event sent")
            last_event_at = time.monotonic()
        except BatchOperation.DoesNotExist:
            error_event = {
                "error": "Operation not found",
                "operation_id": str(operation_id)
            }
            yield f"data: {json.dumps(error_event)}\n\n"
            await redis_conn.close()
            record_sse_stream_error("operations", "missing_operation")
            return

        # Read events from Redis Stream using XREAD
        # Start with '0-0' to read from beginning for complete operation history
        # (MAXLEN=1000 ensures all events of typical operation are preserved)
        last_event_id = request.headers.get("Last-Event-ID")
        last_id = last_event_id or '0-0'
        last_heartbeat = time.monotonic()

        try:
            while True:
                loop_start = time.monotonic()
                now = time.monotonic()
                if SSE_MAX_CONNECTION_SECONDS and now - stream_started_at > SSE_MAX_CONNECTION_SECONDS:
                    logger.info("operation_stream: max connection time reached (operation_id=%s)", operation_id)
                    break
                if SSE_MAX_IDLE_SECONDS and now - last_event_at > SSE_MAX_IDLE_SECONDS:
                    logger.info("operation_stream: idle timeout reached (operation_id=%s)", operation_id)
                    break
                # XREAD with short block timeout
                # Returns: [(stream_name, [(msg_id, {fields}), ...])] or None on timeout
                messages = await redis_conn.xread({stream_name: last_id}, block=SSE_BLOCK_MS, count=10)

                if not messages:
                    # Timeout - send heartbeat comment to keep connection alive
                    now = time.monotonic()
                    if now - last_heartbeat >= SSE_HEARTBEAT_INTERVAL_SECONDS:
                        if active_key:
                            try:
                                await redis_conn.expire(active_key, OP_SSE_ACTIVE_TTL)
                            except Exception:
                                pass
                        yield ": heartbeat\n\n"
                        last_heartbeat = now
                    record_sse_loop_duration("operations", time.monotonic() - loop_start)
                    continue

                for stream, stream_messages in messages:
                    for msg_id, fields in stream_messages:
                        # Extract event data from stream message
                        # Format: {"event_type": "...", "data": "json_string", "operation_id": "..."}
                        event_data = fields.get('data', '{}')
                        event_type = fields.get('event_type') or 'message'
                        if active_key:
                            try:
                                await redis_conn.expire(active_key, OP_SSE_ACTIVE_TTL)
                            except Exception:
                                pass
                        yield f"event: {event_type}\n"
                        yield f"id: {msg_id}\n"
                        yield f"data: {event_data}\n\n"
                        last_id = msg_id
                        last_event_at = time.monotonic()
                loop_duration = time.monotonic() - loop_start
                record_sse_loop_duration("operations", loop_duration)
                if loop_duration > 5:
                    logger.warning("operation_stream: slow loop %.2fs (operation_id=%s)", loop_duration, operation_id)

        except asyncio.CancelledError:
            logger.info("operation_stream: cancelled (operation_id=%s)", operation_id)
        except GeneratorExit:
            # Client disconnected
            logger.info(f"Client disconnected from SSE stream for operation {operation_id}")
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            record_sse_stream_error("operations", "event_loop")
            raise
        finally:
            try:
                if active_key and active_value:
                    current_value = await redis_conn.get(active_key)
                    if current_value == active_value:
                        await redis_conn.delete(active_key)
                await redis_conn.close()
            except Exception:
                pass  # Игнорируем ошибки при закрытии
            sse_connection_close("operations")

    record_api_v2_duration(endpoint, "stream_start", time.monotonic() - start_time)
    response = StreamingHttpResponse(
        event_generator(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
    return response
