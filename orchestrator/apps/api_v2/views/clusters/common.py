# ruff: noqa: F401
"""
Cluster endpoints for API v2.

Provides action-based endpoints for cluster operations.
"""

import json
import logging
import uuid
from datetime import date

from django.db import IntegrityError
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.core import permission_codes as perms
from apps.databases.models import Cluster, PermissionLevel
from apps.databases.serializers import ClusterSerializer, DatabaseSerializer
from apps.databases.services import PermissionService
from apps.operations.models import BatchOperation
from apps.operations.services.admin_action_audit import log_admin_action

logger = logging.getLogger(__name__)

CLUSTER_FILTER_FIELDS = {
    "name": {"field": "name", "type": "text"},
    "ras_server": {"field": "ras_server", "type": "text"},
    "status": {"field": "status", "type": "enum"},
    "databases_count": {"field": "databases_count", "type": "number"},
    "last_sync": {"field": "last_sync", "type": "datetime"},
    "credentials": {"field": "cluster_pwd", "type": "credentials"},
}

CLUSTER_SORT_FIELDS = {
    "name": "name",
    "ras_server": "ras_server",
    "status": "status",
    "databases_count": "databases_count",
    "last_sync": "last_sync",
}


def _is_staff(user) -> bool:
    return bool(user and user.is_staff)


def _permission_denied(message: str):
    return Response({
        "success": False,
        "error": {
            "code": "PERMISSION_DENIED",
            "message": message,
        },
    }, status=403)


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
    parsed_date = None
    try:
        parsed_date = date.fromisoformat(value)
    except (ValueError, TypeError):
        parsed_date = None
    if op in ("contains", "eq") and parsed_date is None:
        return qs.filter(**{f"{field}__icontains": value})
    if parsed_date:
        if op == "eq":
            return qs.filter(**{f"{field}__date": parsed_date})
        if op == "before":
            return qs.filter(**{f"{field}__date__lt": parsed_date})
        if op == "after":
            return qs.filter(**{f"{field}__date__gt": parsed_date})
    return qs


def _apply_enum_filter(qs, field: str, op: str, value):
    if op == "in" and isinstance(value, list):
        return qs.filter(**{f"{field}__in": value})
    return qs.filter(**{field: value})


def _apply_credentials_filter(qs, value: str):
    if value == "configured":
        return qs.exclude(Q(cluster_pwd__isnull=True) | Q(cluster_pwd=""))
    if value == "missing":
        return qs.filter(Q(cluster_pwd__isnull=True) | Q(cluster_pwd=""))
    return qs


def _apply_filters(qs, filters: dict) -> tuple:
    for key, payload in filters.items():
        if key not in CLUSTER_FILTER_FIELDS:
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
        config = CLUSTER_FILTER_FIELDS[key]
        field_type = config["type"]
        field = config["field"]
        if field_type == "text":
            qs = _apply_text_filter(qs, field, op, str(value))
        elif field_type == "number":
            try:
                num = int(value)
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
        elif field_type == "credentials":
            qs = _apply_credentials_filter(qs, str(value))
    return qs, None


# =============================================================================
# Response Serializers for OpenAPI documentation
# =============================================================================

class ClusterErrorDetailSerializer(serializers.Serializer):
    """Error detail structure."""
    code = serializers.CharField(help_text="Error code (e.g., MISSING_PARAMETER)")
    message = serializers.CharField(help_text="Human-readable error message")
    details = serializers.DictField(required=False, help_text="Additional error details")


class ClusterErrorResponseSerializer(serializers.Serializer):
    """Standard error response."""
    success = serializers.BooleanField(default=False)
    error = ClusterErrorDetailSerializer()


class ClusterListResponseSerializer(serializers.Serializer):
    """Response for list_clusters endpoint."""
    clusters = ClusterSerializer(many=True)
    count = serializers.IntegerField(help_text="Number of clusters in current page")
    total = serializers.IntegerField(help_text="Total number of clusters matching filters")


class ClusterStatisticsSerializer(serializers.Serializer):
    """Statistics for a cluster."""
    total_databases = serializers.IntegerField()
    healthy_databases = serializers.IntegerField()
    databases_by_status = serializers.DictField(child=serializers.IntegerField())


class ClusterDetailResponseSerializer(serializers.Serializer):
    """Response for get_cluster endpoint."""
    cluster = ClusterSerializer()
    databases = DatabaseSerializer(many=True)
    statistics = ClusterStatisticsSerializer()


class ClusterCreateResponseSerializer(serializers.Serializer):
    """Response for create_cluster endpoint."""
    cluster = ClusterSerializer()
    message = serializers.CharField()


class ClusterUpdateResponseSerializer(serializers.Serializer):
    """Response for update_cluster endpoint."""
    cluster = ClusterSerializer()
    message = serializers.CharField()


class ClusterCredentialsUpdateRequestSerializer(serializers.Serializer):
    """Request body for update_cluster_credentials endpoint."""
    cluster_id = serializers.UUIDField()
    username = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)
    reset = serializers.BooleanField(required=False, default=False)


class ClusterCredentialsUpdateResponseSerializer(serializers.Serializer):
    """Response for update_cluster_credentials endpoint."""
    cluster = ClusterSerializer()
    message = serializers.CharField()


class ClusterDeleteResponseSerializer(serializers.Serializer):
    """Response for delete_cluster endpoint."""
    message = serializers.CharField()
    cluster_id = serializers.UUIDField()


class ClusterSyncResponseSerializer(serializers.Serializer):
    """Response for sync_cluster endpoint."""
    cluster_id = serializers.UUIDField()
    operation_id = serializers.CharField(required=False, help_text="BatchOperation ID for tracking")
    status = serializers.CharField(help_text="Sync status: syncing, success")
    task_id = serializers.CharField(required=False, help_text="Task ID (if async)")
    message = serializers.CharField()
    databases_found = serializers.IntegerField(required=False)
    created = serializers.IntegerField(required=False)
    updated = serializers.IntegerField(required=False)
    errors = serializers.ListField(child=serializers.CharField(), required=False)


class DiscoverClustersResponseSerializer(serializers.Serializer):
    """Response for discover_clusters endpoint."""
    operation_id = serializers.CharField(help_text="BatchOperation ID for tracking")
    status = serializers.CharField(help_text="Status: discovering, error")
    message = serializers.CharField()


class DiscoverClustersRequestSerializer(serializers.Serializer):
    """Request body for discover_clusters endpoint."""
    ras_host = serializers.CharField(help_text="RAS host")
    ras_port = serializers.IntegerField(help_text="RAS port")
    cluster_service_url = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="RAS adapter URL (optional, reserved for worker usage)",
    )
    cluster_user = serializers.CharField(required=False, allow_blank=True)
    cluster_pwd = serializers.CharField(required=False, allow_blank=True, write_only=True)


class ClusterFiltersSerializer(serializers.Serializer):
    """Applied filters."""
    status = serializers.CharField(required=False)
    health_status = serializers.CharField(required=False)


class ClusterDatabasesResponseSerializer(serializers.Serializer):
    """Response for get_cluster_databases endpoint."""
    cluster_id = serializers.UUIDField()
    cluster_name = serializers.CharField()
    databases = DatabaseSerializer(many=True)
    count = serializers.IntegerField()
    filters = ClusterFiltersSerializer()


class ResetClusterInfoSerializer(serializers.Serializer):
    """Info about reset cluster."""
    id = serializers.UUIDField()
    name = serializers.CharField()
    old_status = serializers.CharField()

class ResetSyncStatusRequestSerializer(serializers.Serializer):
    cluster_id = serializers.UUIDField(required=False)
    all = serializers.BooleanField(required=False, default=False)


class ResetSyncStatusResponseSerializer(serializers.Serializer):
    """Response for reset_sync_status endpoint."""
    message = serializers.CharField()
    reset_count = serializers.IntegerField()
    clusters = ResetClusterInfoSerializer(many=True)


