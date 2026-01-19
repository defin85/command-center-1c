"""
UI metadata endpoints for API v2.

Provides server-driven table metadata for dynamic UI configuration.
"""

import logging
import uuid

from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.core import permission_codes as perms
from apps.operations.driver_catalog_effective import (
    filter_catalog_for_user,
    get_effective_driver_catalog,
    resolve_driver_catalog_versions,
)
from apps.runtime_settings.action_catalog import UI_ACTION_CATALOG_KEY, ensure_valid_action_catalog
from apps.runtime_settings.models import RuntimeSetting
from apps.templates.workflow.models import WorkflowTemplate

logger = logging.getLogger(__name__)


class UiErrorDetailSerializer(serializers.Serializer):
    """Error detail structure."""
    code = serializers.CharField(help_text="Error code (e.g., MISSING_PARAMETER)")
    message = serializers.CharField(help_text="Human-readable error message")
    details = serializers.DictField(required=False, help_text="Additional error details")


class UiErrorResponseSerializer(serializers.Serializer):
    """Standard error response."""
    success = serializers.BooleanField(default=False)
    error = UiErrorDetailSerializer()


class TableFilterOptionSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()


class TableFilterMetadataSerializer(serializers.Serializer):
    type = serializers.CharField()
    operators = serializers.ListField(child=serializers.CharField(), required=False)
    options = TableFilterOptionSerializer(many=True, required=False)
    placeholder = serializers.CharField(required=False)


class TableColumnMetadataSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    group_key = serializers.CharField(required=False, allow_null=True)
    group_label = serializers.CharField(required=False, allow_null=True)
    sortable = serializers.BooleanField(default=False)
    data_type = serializers.CharField(required=False)
    filter = TableFilterMetadataSerializer(required=False)
    server_field = serializers.CharField(required=False)


class TableMetadataResponseSerializer(serializers.Serializer):
    table_id = serializers.CharField()
    version = serializers.CharField()
    columns = TableColumnMetadataSerializer(many=True)


TABLE_METADATA = {
    "databases": {
        "table_id": "databases",
        "version": "2025-12-24",
        "columns": [
            {
                "key": "name",
                "label": "Name",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Name"},
                "server_field": "name",
            },
            {
                "key": "host",
                "label": "Host",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Host"},
                "server_field": "host",
            },
            {
                "key": "port",
                "label": "Port",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "number",
                "filter": {"type": "number", "operators": ["eq", "gt", "lt"], "placeholder": "Port"},
                "server_field": "port",
            },
            {
                "key": "status",
                "label": "Status",
                "group_key": "status",
                "group_label": "Status",
                "sortable": False,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "active", "label": "Active"},
                        {"value": "inactive", "label": "Inactive"},
                        {"value": "maintenance", "label": "Maintenance"},
                        {"value": "error", "label": "Error"},
                    ],
                },
                "server_field": "status",
            },
            {
                "key": "last_check_status",
                "label": "Health",
                "group_key": "status",
                "group_label": "Status",
                "sortable": False,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "ok", "label": "OK"},
                        {"value": "degraded", "label": "Degraded"},
                        {"value": "down", "label": "Down"},
                        {"value": "unknown", "label": "Unknown"},
                    ],
                },
                "server_field": "last_check_status",
            },
            {
                "key": "last_check",
                "label": "Last Check",
                "group_key": "status",
                "group_label": "Status",
                "sortable": True,
                "data_type": "datetime",
                "filter": {"type": "date", "operators": ["eq", "before", "after"], "placeholder": "Last check"},
                "server_field": "last_check",
            },
            {
                "key": "credentials",
                "label": "Credentials",
                "group_key": "access",
                "group_label": "Access",
                "sortable": False,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq"],
                    "options": [
                        {"value": "configured", "label": "Configured"},
                        {"value": "missing", "label": "Missing"},
                    ],
                },
                "server_field": "credentials",
            },
            {
                "key": "restrictions",
                "label": "Restrictions",
                "group_key": "access",
                "group_label": "Access",
                "sortable": False,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq"],
                    "options": [
                        {"value": "jobs_locked", "label": "Jobs: Locked"},
                        {"value": "jobs_allowed", "label": "Jobs: Allowed"},
                        {"value": "jobs_unknown", "label": "Jobs: Unknown"},
                        {"value": "sessions_blocked", "label": "Sessions: Blocked"},
                        {"value": "sessions_allowed", "label": "Sessions: Allowed"},
                        {"value": "sessions_unknown", "label": "Sessions: Unknown"},
                    ],
                },
                "server_field": "restrictions",
            },
            {
                "key": "actions",
                "label": "Actions",
                "group_key": "actions",
                "group_label": "Actions",
                "sortable": False,
                "data_type": "action",
            },
        ],
    }
    ,
    "clusters": {
        "table_id": "clusters",
        "version": "2025-12-24",
        "columns": [
            {
                "key": "name",
                "label": "Name",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Name"},
                "server_field": "name",
            },
            {
                "key": "ras_server",
                "label": "RAS Server",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "RAS Server"},
                "server_field": "ras_server",
            },
            {
                "key": "status",
                "label": "Status",
                "group_key": "status",
                "group_label": "Status",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "active", "label": "Active"},
                        {"value": "inactive", "label": "Inactive"},
                        {"value": "maintenance", "label": "Maintenance"},
                        {"value": "error", "label": "Error"},
                    ],
                },
                "server_field": "status",
            },
            {
                "key": "databases_count",
                "label": "Databases",
                "group_key": "status",
                "group_label": "Status",
                "sortable": True,
                "data_type": "number",
                "filter": {"type": "number", "operators": ["eq", "gt", "lt"], "placeholder": "Databases count"},
                "server_field": "databases_count",
            },
            {
                "key": "last_sync",
                "label": "Last Sync",
                "group_key": "status",
                "group_label": "Status",
                "sortable": True,
                "data_type": "datetime",
                "filter": {"type": "date", "operators": ["eq", "before", "after"], "placeholder": "Last sync"},
                "server_field": "last_sync",
            },
            {
                "key": "credentials",
                "label": "Credentials",
                "group_key": "access",
                "group_label": "Access",
                "sortable": False,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq"],
                    "options": [
                        {"value": "configured", "label": "Configured"},
                        {"value": "missing", "label": "Missing"},
                    ],
                },
                "server_field": "credentials",
            },
            {
                "key": "actions",
                "label": "Actions",
                "group_key": "actions",
                "group_label": "Actions",
                "sortable": False,
                "data_type": "action",
            },
        ],
    },
    "operations": {
        "table_id": "operations",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "name",
                "label": "Name",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Name"},
                "server_field": "name",
            },
            {
                "key": "id",
                "label": "Operation ID",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["eq"], "placeholder": "Operation ID"},
                "server_field": "id",
            },
            {
                "key": "workflow_execution_id",
                "label": "Workflow",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Workflow ID"},
                "server_field": "workflow_execution_id",
            },
            {
                "key": "operation_type",
                "label": "Type",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "designer_cli", "label": "designer_cli"},
                        {"value": "lock_scheduled_jobs", "label": "lock_scheduled_jobs"},
                        {"value": "unlock_scheduled_jobs", "label": "unlock_scheduled_jobs"},
                        {"value": "terminate_sessions", "label": "terminate_sessions"},
                        {"value": "block_sessions", "label": "block_sessions"},
                        {"value": "unblock_sessions", "label": "unblock_sessions"},
                        {"value": "query", "label": "query"},
                        {"value": "sync_cluster", "label": "sync_cluster"},
                        {"value": "health_check", "label": "health_check"},
                    ],
                },
                "server_field": "operation_type",
            },
            {
                "key": "status",
                "label": "Status",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "pending", "label": "pending"},
                        {"value": "queued", "label": "queued"},
                        {"value": "processing", "label": "processing"},
                        {"value": "completed", "label": "completed"},
                        {"value": "failed", "label": "failed"},
                        {"value": "cancelled", "label": "cancelled"},
                    ],
                },
                "server_field": "status",
            },
            {
                "key": "progress",
                "label": "Progress",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "number",
            },
            {
                "key": "databases",
                "label": "Databases",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "created_at",
                "label": "Created",
                "group_key": "time",
                "group_label": "Time",
                "sortable": True,
                "data_type": "datetime",
                "filter": {"type": "date", "operators": ["eq", "before", "after"], "placeholder": "Created at"},
                "server_field": "created_at",
            },
            {
                "key": "duration_seconds",
                "label": "Duration",
                "group_key": "time",
                "group_label": "Time",
                "sortable": True,
                "data_type": "number",
                "filter": {"type": "number", "operators": ["eq", "gt", "lt"], "placeholder": "Duration (s)"},
                "server_field": "duration_seconds",
            },
            {
                "key": "actions",
                "label": "Actions",
                "group_key": "actions",
                "group_label": "Actions",
                "sortable": False,
                "data_type": "action",
            },
        ],
    },
    "operations_recent": {
        "table_id": "operations_recent",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "id",
                "label": "ID",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "ID"},
            },
            {
                "key": "name",
                "label": "Name",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Name"},
            },
            {
                "key": "service",
                "label": "Service",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Service"},
            },
            {
                "key": "status",
                "label": "Status",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "pending", "label": "pending"},
                        {"value": "queued", "label": "queued"},
                        {"value": "processing", "label": "processing"},
                        {"value": "completed", "label": "completed"},
                        {"value": "failed", "label": "failed"},
                        {"value": "cancelled", "label": "cancelled"},
                    ],
                },
            },
            {
                "key": "progress",
                "label": "Progress",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Progress"},
            },
            {
                "key": "durationSeconds",
                "label": "Duration",
                "group_key": "time",
                "group_label": "Time",
                "sortable": True,
                "data_type": "number",
                "filter": {"type": "number", "operators": ["eq", "gt", "lt"], "placeholder": "Duration (s)"},
            },
            {
                "key": "createdAt",
                "label": "Created",
                "group_key": "time",
                "group_label": "Time",
                "sortable": True,
                "data_type": "datetime",
                "filter": {"type": "date", "operators": ["eq", "before", "after"], "placeholder": "Created at"},
            },
            {
                "key": "actions",
                "label": "Actions",
                "group_key": "actions",
                "group_label": "Actions",
                "sortable": False,
                "data_type": "action",
            },
        ],
    },
    "dashboard_clusters": {
        "table_id": "dashboard_clusters",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "name",
                "label": "Name",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Name"},
            },
            {
                "key": "databases",
                "label": "Databases",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Databases"},
            },
            {
                "key": "status",
                "label": "Status",
                "group_key": "status",
                "group_label": "Status",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "healthy", "label": "healthy"},
                        {"value": "degraded", "label": "degraded"},
                        {"value": "critical", "label": "critical"},
                    ],
                },
            },
        ],
    },
    "runtime_settings": {
        "table_id": "runtime_settings",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "key",
                "label": "Key",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Key"},
            },
            {
                "key": "description",
                "label": "Описание",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Описание"},
            },
            {
                "key": "value",
                "label": "Значение",
                "group_key": "value",
                "group_label": "Value",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Значение"},
            },
            {
                "key": "default",
                "label": "Default",
                "group_key": "value",
                "group_label": "Value",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Default"},
            },
            {
                "key": "range",
                "label": "Диапазон",
                "group_key": "value",
                "group_label": "Value",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Диапазон"},
            },
            {
                "key": "actions",
                "label": "Действия",
                "group_key": "actions",
                "group_label": "Actions",
                "sortable": False,
                "data_type": "action",
            },
        ],
    },
    "timeline_settings": {
        "table_id": "timeline_settings",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "key",
                "label": "Key",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Key"},
            },
            {
                "key": "description",
                "label": "Описание",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Описание"},
            },
            {
                "key": "value",
                "label": "Значение",
                "group_key": "value",
                "group_label": "Value",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Значение"},
            },
            {
                "key": "default",
                "label": "Default",
                "group_key": "value",
                "group_label": "Value",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Default"},
            },
            {
                "key": "range",
                "label": "Диапазон",
                "group_key": "value",
                "group_label": "Value",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Диапазон"},
            },
            {
                "key": "actions",
                "label": "Действия",
                "group_key": "actions",
                "group_label": "Actions",
                "sortable": False,
                "data_type": "action",
            },
        ],
    },
    "operation_tasks": {
        "table_id": "operation_tasks",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "database_name",
                "label": "Database",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Database"},
                "server_field": "database_name",
            },
            {
                "key": "status",
                "label": "Status",
                "group_key": "status",
                "group_label": "Status",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "pending", "label": "pending"},
                        {"value": "queued", "label": "queued"},
                        {"value": "processing", "label": "processing"},
                        {"value": "completed", "label": "completed"},
                        {"value": "failed", "label": "failed"},
                        {"value": "retry", "label": "retry"},
                        {"value": "cancelled", "label": "cancelled"},
                    ],
                },
                "server_field": "status",
            },
            {
                "key": "started_at",
                "label": "Started",
                "group_key": "time",
                "group_label": "Time",
                "sortable": True,
                "data_type": "datetime",
                "filter": {"type": "date", "operators": ["eq", "before", "after"], "placeholder": "Started at"},
                "server_field": "started_at",
            },
            {
                "key": "completed_at",
                "label": "Completed",
                "group_key": "time",
                "group_label": "Time",
                "sortable": True,
                "data_type": "datetime",
                "filter": {"type": "date", "operators": ["eq", "before", "after"], "placeholder": "Completed at"},
                "server_field": "completed_at",
            },
            {
                "key": "duration_seconds",
                "label": "Duration",
                "group_key": "time",
                "group_label": "Time",
                "sortable": True,
                "data_type": "number",
                "filter": {"type": "number", "operators": ["eq", "gt", "lt"], "placeholder": "Duration (s)"},
                "server_field": "duration_seconds",
            },
            {
                "key": "worker_id",
                "label": "Worker",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Worker ID"},
                "server_field": "worker_id",
            },
            {
                "key": "error_message",
                "label": "Error",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Error message"},
                "server_field": "error_message",
            },
        ],
    },
    "templates": {
        "table_id": "templates",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "name",
                "label": "Name",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Name"},
                "server_field": "name",
            },
            {
                "key": "operation_type",
                "label": "Operation Type",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "designer_cli", "label": "designer_cli"},
                        {"value": "lock_scheduled_jobs", "label": "lock_scheduled_jobs"},
                        {"value": "unlock_scheduled_jobs", "label": "unlock_scheduled_jobs"},
                        {"value": "terminate_sessions", "label": "terminate_sessions"},
                        {"value": "block_sessions", "label": "block_sessions"},
                        {"value": "unblock_sessions", "label": "unblock_sessions"},
                        {"value": "query", "label": "query"},
                        {"value": "sync_cluster", "label": "sync_cluster"},
                        {"value": "health_check", "label": "health_check"},
                    ],
                },
                "server_field": "operation_type",
            },
            {
                "key": "target_entity",
                "label": "Target",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "database", "label": "database"},
                        {"value": "cluster", "label": "cluster"},
                        {"value": "system", "label": "system"},
                        {"value": "extension", "label": "extension"},
                    ],
                },
                "server_field": "target_entity",
            },
            {
                "key": "is_active",
                "label": "Active",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": True,
                "data_type": "boolean",
                "filter": {"type": "boolean", "operators": ["eq"], "placeholder": "Active"},
                "server_field": "is_active",
            },
            {
                "key": "updated_at",
                "label": "Updated",
                "group_key": "time",
                "group_label": "Time",
                "sortable": True,
                "data_type": "datetime",
                "filter": {"type": "date", "operators": ["eq", "before", "after"], "placeholder": "Updated at"},
                "server_field": "updated_at",
            },
        ],
    },
    "dlq": {
        "table_id": "dlq",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "failed_at",
                "label": "Failed at",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "datetime",
                "filter": {"type": "date", "operators": ["eq", "before", "after"], "placeholder": "Failed at"},
                "server_field": "failed_at",
            },
            {
                "key": "operation_id",
                "label": "Operation",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Operation ID"},
                "server_field": "operation_id",
            },
            {
                "key": "error_code",
                "label": "Error",
                "group_key": "details",
                "group_label": "Details",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Error code"},
                "server_field": "error_code",
            },
            {
                "key": "error_message",
                "label": "Message",
                "group_key": "details",
                "group_label": "Details",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Error message"},
                "server_field": "error_message",
            },
            {
                "key": "worker_id",
                "label": "Worker",
                "group_key": "details",
                "group_label": "Details",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Worker ID"},
                "server_field": "worker_id",
            },
            {
                "key": "actions",
                "label": "Actions",
                "group_key": "actions",
                "group_label": "Actions",
                "sortable": False,
                "data_type": "action",
            },
        ],
    },
    "operation_targets": {
        "table_id": "operation_targets",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "name",
                "label": "Database",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Database"},
                "server_field": "name",
            },
            {
                "key": "cluster",
                "label": "Cluster",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "status",
                "label": "Status",
                "group_key": "status",
                "group_label": "Status",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "active", "label": "Active"},
                        {"value": "inactive", "label": "Inactive"},
                        {"value": "maintenance", "label": "Maintenance"},
                        {"value": "error", "label": "Error"},
                    ],
                },
                "server_field": "status",
            },
            {
                "key": "last_check_status",
                "label": "Health",
                "group_key": "status",
                "group_label": "Status",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "ok", "label": "OK"},
                        {"value": "degraded", "label": "Degraded"},
                        {"value": "down", "label": "Down"},
                        {"value": "unknown", "label": "Unknown"},
                    ],
                },
                "server_field": "last_check_status",
            },
        ],
    },
    "workflows": {
        "table_id": "workflows",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "name",
                "label": "Name",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Name"},
                "server_field": "name",
            },
            {
                "key": "workflow_type",
                "label": "Type",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "sequential", "label": "sequential"},
                        {"value": "parallel", "label": "parallel"},
                        {"value": "conditional", "label": "conditional"},
                        {"value": "complex", "label": "complex"},
                    ],
                },
                "server_field": "workflow_type",
            },
            {
                "key": "is_active",
                "label": "Status",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "boolean",
                "filter": {"type": "boolean", "operators": ["eq"], "placeholder": "Active"},
                "server_field": "is_active",
            },
            {
                "key": "node_count",
                "label": "Nodes",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "number",
            },
            {
                "key": "updated_at",
                "label": "Updated",
                "group_key": "time",
                "group_label": "Time",
                "sortable": True,
                "data_type": "datetime",
            },
            {
                "key": "actions",
                "label": "Actions",
                "group_key": "actions",
                "group_label": "Actions",
                "sortable": False,
                "data_type": "action",
            },
        ],
    },
    "rbac_clusters": {
        "table_id": "rbac_clusters",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "user_id",
                "label": "User",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "number",
                "filter": {"type": "number", "operators": ["eq"], "placeholder": "User ID"},
                "server_field": "user_id",
            },
            {
                "key": "cluster",
                "label": "Cluster",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "level",
                "label": "Level",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "VIEW", "label": "VIEW"},
                        {"value": "OPERATE", "label": "OPERATE"},
                        {"value": "MANAGE", "label": "MANAGE"},
                        {"value": "ADMIN", "label": "ADMIN"},
                    ],
                },
                "server_field": "level",
            },
            {
                "key": "granted_at",
                "label": "Granted At",
                "group_key": "time",
                "group_label": "Time",
                "sortable": False,
                "data_type": "datetime",
            },
            {
                "key": "granted_by",
                "label": "Granted By",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "notes",
                "label": "Notes",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "actions",
                "label": "Action",
                "group_key": "actions",
                "group_label": "Actions",
                "sortable": False,
                "data_type": "action",
            },
        ],
    },
    "rbac_databases": {
        "table_id": "rbac_databases",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "user_id",
                "label": "User",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "number",
                "filter": {"type": "number", "operators": ["eq"], "placeholder": "User ID"},
                "server_field": "user_id",
            },
            {
                "key": "database",
                "label": "Database",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "database_id",
                "label": "Database ID",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Database ID"},
                "server_field": "database_id",
            },
            {
                "key": "level",
                "label": "Level",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "VIEW", "label": "VIEW"},
                        {"value": "OPERATE", "label": "OPERATE"},
                        {"value": "MANAGE", "label": "MANAGE"},
                        {"value": "ADMIN", "label": "ADMIN"},
                    ],
                },
                "server_field": "level",
            },
            {
                "key": "granted_at",
                "label": "Granted At",
                "group_key": "time",
                "group_label": "Time",
                "sortable": False,
                "data_type": "datetime",
            },
            {
                "key": "granted_by",
                "label": "Granted By",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "notes",
                "label": "Notes",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "actions",
                "label": "Action",
                "group_key": "actions",
                "group_label": "Actions",
                "sortable": False,
                "data_type": "action",
            },
        ],
    },
    "rbac_ib_users": {
        "table_id": "rbac_ib_users",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "ib_user",
                "label": "IB User",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "cc_user",
                "label": "CC User",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "roles",
                "label": "Roles",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "auth_type",
                "label": "Auth",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "enum",
            },
            {
                "key": "is_service",
                "label": "Service",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "boolean",
            },
            {
                "key": "password",
                "label": "Password",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "actions",
                "label": "Action",
                "group_key": "actions",
                "group_label": "Actions",
                "sortable": False,
                "data_type": "action",
            },
        ],
    },
    "users": {
        "table_id": "users",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "username",
                "label": "Username",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Username"},
                "server_field": "username",
            },
            {
                "key": "email",
                "label": "Email",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Email"},
                "server_field": "email",
            },
            {
                "key": "is_staff",
                "label": "Staff",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "boolean",
                "filter": {"type": "boolean", "operators": ["eq"], "placeholder": "Staff"},
                "server_field": "is_staff",
            },
            {
                "key": "is_active",
                "label": "Active",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "boolean",
                "filter": {"type": "boolean", "operators": ["eq"], "placeholder": "Active"},
                "server_field": "is_active",
            },
            {
                "key": "last_login",
                "label": "Last Login",
                "group_key": "time",
                "group_label": "Time",
                "sortable": False,
                "data_type": "datetime",
            },
            {
                "key": "date_joined",
                "label": "Created",
                "group_key": "time",
                "group_label": "Time",
                "sortable": False,
                "data_type": "datetime",
            },
            {
                "key": "actions",
                "label": "Action",
                "group_key": "actions",
                "group_label": "Actions",
                "sortable": False,
                "data_type": "action",
            },
        ],
    },
    "artifacts": {
        "table_id": "artifacts",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "name",
                "label": "Name",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Name"},
                "server_field": "name",
            },
            {
                "key": "kind",
                "label": "Kind",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "extension", "label": "Расширение конфигурации (.cfe)"},
                        {"value": "config_xml", "label": "Выгрузка конфигурации XML (.xml)"},
                        {"value": "dt_backup", "label": "Выгрузка ИБ (.dt)"},
                        {"value": "epf", "label": "Внешняя обработка (.epf)"},
                        {"value": "erf", "label": "Внешний отчет (.erf)"},
                        {"value": "ibcmd_package", "label": "Пакет IBCMD (.zip)"},
                        {"value": "ras_script", "label": "Скрипт RAS (.txt)"},
                        {"value": "other", "label": "Другое"},
                    ],
                },
                "server_field": "kind",
            },
            {
                "key": "tags",
                "label": "Tags",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Tag"},
                "server_field": "tag",
            },
            {
                "key": "created_at",
                "label": "Created",
                "group_key": "time",
                "group_label": "Time",
                "sortable": True,
                "data_type": "datetime",
                "filter": {"type": "date", "operators": ["eq", "before", "after"], "placeholder": "Created"},
                "server_field": "created_at",
            },
            {
                "key": "actions",
                "label": "Actions",
                "group_key": "actions",
                "group_label": "Actions",
                "sortable": False,
                "data_type": "action",
            },
        ],
    },
}


class ActionCatalogExecutorFixedSerializer(serializers.Serializer):
    confirm_dangerous = serializers.BooleanField(required=False)
    timeout_seconds = serializers.IntegerField(required=False)


class ActionCatalogExecutorSerializer(serializers.Serializer):
    kind = serializers.CharField()
    driver = serializers.CharField(required=False)
    command_id = serializers.CharField(required=False)
    workflow_id = serializers.CharField(required=False)
    mode = serializers.CharField(required=False)
    params = serializers.DictField(required=False)
    additional_args = serializers.ListField(child=serializers.CharField(), required=False)
    stdin = serializers.CharField(required=False, allow_blank=True)
    fixed = ActionCatalogExecutorFixedSerializer(required=False)


class ActionCatalogActionSerializer(serializers.Serializer):
    id = serializers.CharField()
    label = serializers.CharField()
    contexts = serializers.ListField(child=serializers.CharField())
    executor = ActionCatalogExecutorSerializer()


class ExtensionsActionCatalogSerializer(serializers.Serializer):
    actions = ActionCatalogActionSerializer(many=True)


class ActionCatalogResponseSerializer(serializers.Serializer):
    catalog_version = serializers.IntegerField()
    extensions = ExtensionsActionCatalogSerializer()


def _get_effective_commands_by_id(user, driver: str) -> dict[str, dict] | None:
    try:
        versions = resolve_driver_catalog_versions(driver)
        if versions.base_version is None:
            return None
        effective = get_effective_driver_catalog(
            driver=driver,
            base_version=versions.base_version,
            overrides_version=versions.overrides_version,
        )
        filtered = filter_catalog_for_user(user, effective.catalog)
        commands_by_id = filtered.get("commands_by_id")
        if isinstance(commands_by_id, dict):
            return commands_by_id
        return None
    except Exception as exc:
        logger.warning(
            "Failed to resolve effective driver catalog for action catalog",
            extra={
                "driver": str(driver),
                "error": str(exc),
            },
        )
        return None


def _filter_extensions_actions_for_user(user, actions: list[dict]) -> list[dict]:
    if not actions:
        return []

    commands_cache: dict[str, dict[str, dict] | None] = {}
    filtered_actions: list[dict] = []

    for action in actions:
        if not isinstance(action, dict):
            continue

        executor = action.get("executor")
        if not isinstance(executor, dict):
            continue

        kind = executor.get("kind")
        if kind in ("ibcmd_cli", "designer_cli"):
            driver = executor.get("driver")
            command_id = executor.get("command_id")
            if not isinstance(driver, str):
                continue
            cache_key = driver.strip().lower()
            if not cache_key:
                continue
            if not isinstance(command_id, str):
                continue
            normalized_command_id = command_id.strip()
            if not normalized_command_id:
                continue
            if cache_key not in commands_cache:
                commands_cache[cache_key] = _get_effective_commands_by_id(user, cache_key)
            commands_by_id = commands_cache.get(cache_key) or {}
            if normalized_command_id not in commands_by_id:
                continue
            filtered_actions.append(action)
            continue

        if kind == "workflow":
            workflow_id = executor.get("workflow_id")
            if not isinstance(workflow_id, str) or not workflow_id.strip():
                continue
            normalized_workflow_id = workflow_id.strip()
            try:
                workflow_uuid = uuid.UUID(normalized_workflow_id)
            except (ValueError, AttributeError):
                continue
            workflow = WorkflowTemplate.objects.filter(id=workflow_uuid).first()
            if workflow is None:
                continue
            if not workflow.is_active or not workflow.is_valid:
                continue
            if not user.has_perm(perms.PERM_TEMPLATES_EXECUTE_WORKFLOW_TEMPLATE, workflow):
                continue
            filtered_actions.append(action)
            continue

    return filtered_actions


@extend_schema(
    tags=["v2"],
    summary="Get effective action catalog",
    description="Returns effective action catalog for the current user (RBAC + driver catalogs + workflows).",
    responses={
        200: ActionCatalogResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_action_catalog(request):
    raw = RuntimeSetting.objects.filter(key=UI_ACTION_CATALOG_KEY).values_list("value", flat=True).first()
    catalog, errors = ensure_valid_action_catalog(raw)
    if errors:
        logger.warning(
            "ui.action_catalog is invalid; failing closed",
            extra={
                "error_count": len(errors),
                "errors": [err.to_text() for err in errors[:10]],
            },
        )

    extensions = catalog.get("extensions")
    if not isinstance(extensions, dict):
        return Response({"catalog_version": 1, "extensions": {"actions": []}})

    actions = extensions.get("actions")
    if not isinstance(actions, list):
        return Response({"catalog_version": 1, "extensions": {"actions": []}})

    filtered_actions = _filter_extensions_actions_for_user(request.user, actions)
    return Response(
        {
            "catalog_version": catalog.get("catalog_version", 1),
            "extensions": {"actions": filtered_actions},
        }
    )


@extend_schema(
    tags=['v2'],
    summary='Get table metadata',
    description='Returns metadata for server-driven table configuration.',
    parameters=[
        OpenApiParameter(name='table', type=str, required=True, description='Table identifier'),
    ],
    responses={
        200: TableMetadataResponseSerializer,
        400: UiErrorResponseSerializer,
        404: UiErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_table_metadata(request):
    table = request.query_params.get('table')
    if not table:
        return Response(
            {
                "success": False,
                "error": {
                    "code": "MISSING_PARAMETER",
                    "message": "Missing required parameter: table",
                },
            },
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    metadata = TABLE_METADATA.get(table)
    if not metadata:
        return Response(
            {
                "success": False,
                "error": {
                    "code": "UNKNOWN_TABLE",
                    "message": f"Unknown table: {table}",
                },
            },
            status=http_status.HTTP_404_NOT_FOUND,
        )

    return Response(metadata)
