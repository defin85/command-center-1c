"""UI table metadata endpoint."""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .common import TableMetadataResponseSerializer, UiErrorResponseSerializer

from .table_metadata_parts.artifacts import TABLE_METADATA_PART as _ARTIFACTS
from .table_metadata_parts.clusters import TABLE_METADATA_PART as _CLUSTERS
from .table_metadata_parts.dashboard_clusters import TABLE_METADATA_PART as _DASHBOARD_CLUSTERS
from .table_metadata_parts.databases import TABLE_METADATA_PART as _DATABASES
from .table_metadata_parts.dlq import TABLE_METADATA_PART as _DLQ
from .table_metadata_parts.operation_targets import TABLE_METADATA_PART as _OPERATION_TARGETS
from .table_metadata_parts.operation_tasks import TABLE_METADATA_PART as _OPERATION_TASKS
from .table_metadata_parts.operations import TABLE_METADATA_PART as _OPERATIONS
from .table_metadata_parts.operations_recent import TABLE_METADATA_PART as _OPERATIONS_RECENT
from .table_metadata_parts.rbac_clusters import TABLE_METADATA_PART as _RBAC_CLUSTERS
from .table_metadata_parts.rbac_databases import TABLE_METADATA_PART as _RBAC_DATABASES
from .table_metadata_parts.rbac_dbms_users import TABLE_METADATA_PART as _RBAC_DBMS_USERS
from .table_metadata_parts.rbac_ib_users import TABLE_METADATA_PART as _RBAC_IB_USERS
from .table_metadata_parts.runtime_settings import TABLE_METADATA_PART as _RUNTIME_SETTINGS
from .table_metadata_parts.templates import TABLE_METADATA_PART as _TEMPLATES
from .table_metadata_parts.timeline_settings import TABLE_METADATA_PART as _TIMELINE_SETTINGS
from .table_metadata_parts.users import TABLE_METADATA_PART as _USERS
from .table_metadata_parts.workflows import TABLE_METADATA_PART as _WORKFLOWS

TABLE_METADATA = {}
TABLE_METADATA.update(_ARTIFACTS)
TABLE_METADATA.update(_CLUSTERS)
TABLE_METADATA.update(_DASHBOARD_CLUSTERS)
TABLE_METADATA.update(_DATABASES)
TABLE_METADATA.update(_DLQ)
TABLE_METADATA.update(_OPERATION_TARGETS)
TABLE_METADATA.update(_OPERATION_TASKS)
TABLE_METADATA.update(_OPERATIONS)
TABLE_METADATA.update(_OPERATIONS_RECENT)
TABLE_METADATA.update(_RBAC_CLUSTERS)
TABLE_METADATA.update(_RBAC_DATABASES)
TABLE_METADATA.update(_RBAC_DBMS_USERS)
TABLE_METADATA.update(_RBAC_IB_USERS)
TABLE_METADATA.update(_RUNTIME_SETTINGS)
TABLE_METADATA.update(_TEMPLATES)
TABLE_METADATA.update(_TIMELINE_SETTINGS)
TABLE_METADATA.update(_USERS)
TABLE_METADATA.update(_WORKFLOWS)


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
