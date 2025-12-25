"""
UI metadata endpoints for API v2.

Provides server-driven table metadata for dynamic UI configuration.
"""

from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse


class ErrorDetailSerializer(serializers.Serializer):
    """Error detail structure."""
    code = serializers.CharField(help_text="Error code (e.g., MISSING_PARAMETER)")
    message = serializers.CharField(help_text="Human-readable error message")
    details = serializers.DictField(required=False, help_text="Additional error details")


class ErrorResponseSerializer(serializers.Serializer):
    """Standard error response."""
    success = serializers.BooleanField(default=False)
    error = ErrorDetailSerializer()


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
                "filter": {"type": "text", "operators": ["eq"], "placeholder": "Port"},
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
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Last check"},
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
                "server_field": "password",
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
                "server_field": "metadata",
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
                "filter": {"type": "text", "operators": ["eq"], "placeholder": "Databases count"},
                "server_field": "databases_count",
            },
            {
                "key": "last_sync",
                "label": "Last Sync",
                "group_key": "status",
                "group_label": "Status",
                "sortable": True,
                "data_type": "datetime",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Last sync"},
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
                "server_field": "cluster_pwd",
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


@extend_schema(
    tags=['v2'],
    summary='Get table metadata',
    description='Returns metadata for server-driven table configuration.',
    parameters=[
        OpenApiParameter(name='table', type=str, required=True, description='Table identifier'),
    ],
    responses={
        200: TableMetadataResponseSerializer,
        400: ErrorResponseSerializer,
        404: ErrorResponseSerializer,
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
