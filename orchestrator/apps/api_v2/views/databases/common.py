# ruff: noqa: F401
"""
Database endpoints for API v2.

Provides action-based endpoints for database operations.
"""

import asyncio
import json
import logging
import secrets
import time
from datetime import date

import redis as redis_module
import redis.asyncio as redis_async
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from rest_framework import serializers, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.core import permission_codes as perms
from apps.databases.extensions_snapshot import normalize_extensions_snapshot
from apps.databases.models import (
    Cluster,
    Database,
    DatabaseExtensionsSnapshot,
    DbmsUserMapping,
    InfobaseUserMapping,
    PermissionLevel,
)
from apps.databases.services import PermissionService
from apps.databases.serializers import (
    ClusterSerializer,
    DatabaseSerializer,
    DbmsUserMappingSerializer,
    DbmsUserMappingCreateSerializer,
    DbmsUserMappingDeleteSerializer,
    DbmsUserMappingUpdateSerializer,
    DbmsUserPasswordResetSerializer,
    DbmsUserPasswordSetSerializer,
    InfobaseUserMappingSerializer,
    InfobaseUserMappingCreateSerializer,
    InfobaseUserMappingDeleteSerializer,
    InfobaseUserMappingUpdateSerializer,
    InfobaseUserPasswordResetSerializer,
    InfobaseUserPasswordSetSerializer,
)
from apps.operations.prometheus_metrics import (
    record_api_v2_duration,
    record_api_v2_error,
    record_sse_loop_duration,
    record_sse_stream_error,
    record_sse_ticket,
    sse_connection_close,
    sse_connection_open,
)
from apps.operations.services import OperationsService
from apps.operations.services.admin_action_audit import log_admin_action

logger = logging.getLogger(__name__)
User = get_user_model()

DB_SSE_TICKET_PREFIX = "db_sse_ticket:"
DB_SSE_TICKET_TTL = 30
DB_STREAM_NAME = "events:databases"
SSE_BLOCK_MS = 1000
SSE_HEARTBEAT_INTERVAL_SECONDS = 10
SSE_MAX_CONNECTION_SECONDS = getattr(settings, "SSE_MAX_CONNECTION_SECONDS", 0)
SSE_MAX_IDLE_SECONDS = getattr(settings, "SSE_MAX_IDLE_SECONDS", 0)
DB_SSE_ACTIVE_PREFIX = "db_sse_active:"
DB_SSE_ACTIVE_TTL = 60

DATABASE_FILTER_FIELDS = {
    "name": {"field": "name", "type": "text"},
    "host": {"field": "host", "type": "text"},
    "port": {"field": "port", "type": "number"},
    "status": {"field": "status", "type": "enum"},
    "last_check_status": {"field": "last_check_status", "type": "enum"},
    "last_check": {"field": "last_check", "type": "datetime"},
    "credentials": {"field": "password", "type": "credentials"},
    "restrictions": {"field": "metadata", "type": "restrictions"},
}

DATABASE_SORT_FIELDS = {
    "name": "name",
    "host": "host",
    "port": "port",
    "status": "status",
    "last_check_status": "last_check_status",
    "last_check": "last_check",
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


def _resolve_tenant_id(request) -> str | None:
    """
    Resolve tenant_id for the current request.

    In production, tenant context is applied by TenantContextAuthentication.
    In tests, DRF `force_authenticate()` may bypass authentication classes, so
    request.tenant_id can be missing even though tenant scoping is expected.
    For forced-auth requests we fall back to the default tenant.
    """
    tenant_id = getattr(request, "tenant_id", None)
    if tenant_id:
        return str(tenant_id)

    underlying = getattr(request, "_request", None)
    if underlying is not None:
        tenant_id = getattr(underlying, "tenant_id", None)
        if tenant_id:
            return str(tenant_id)

    forced_user = getattr(request, "_force_auth_user", None)
    if forced_user is None and underlying is not None:
        forced_user = getattr(underlying, "_force_auth_user", None)
    if forced_user is None:
        return None

    try:
        from apps.tenancy.models import Tenant

        default_tenant_id = Tenant.objects.filter(slug="default").values_list("id", flat=True).first()
        return str(default_tenant_id) if default_tenant_id else None
    except Exception:
        return None


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
        return qs.exclude(Q(password__isnull=True) | Q(password=""))
    if value == "missing":
        return qs.filter(Q(password__isnull=True) | Q(password=""))
    return qs


def _apply_restrictions_filter(qs, value: str):
    if value == "jobs_locked":
        return qs.filter(metadata__scheduled_jobs_deny=True)
    if value == "jobs_allowed":
        return qs.filter(metadata__scheduled_jobs_deny=False)
    if value == "jobs_unknown":
        return qs.filter(Q(metadata__scheduled_jobs_deny__isnull=True) | Q(metadata__scheduled_jobs_deny=None))
    if value == "sessions_blocked":
        return qs.filter(metadata__sessions_deny=True)
    if value == "sessions_allowed":
        return qs.filter(metadata__sessions_deny=False)
    if value == "sessions_unknown":
        return qs.filter(Q(metadata__sessions_deny__isnull=True) | Q(metadata__sessions_deny=None))
    return qs


def _apply_filters(qs, filters: dict) -> tuple:
    for key, payload in filters.items():
        if key not in DATABASE_FILTER_FIELDS:
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
        config = DATABASE_FILTER_FIELDS[key]
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
        elif field_type == "restrictions":
            qs = _apply_restrictions_filter(qs, str(value))
    return qs, None


def _get_redis_connection():
    redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    return redis_module.from_url(redis_url, decode_responses=True)


def _get_async_redis_connection():
    redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    return redis_async.from_url(redis_url, decode_responses=True)


async def _validate_db_stream_ticket(ticket: str) -> tuple[dict | None, str | None]:
    redis_conn = _get_async_redis_connection()

    try:
        ticket_key = f"{DB_SSE_TICKET_PREFIX}{ticket}"
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


# =============================================================================
# Response Serializers for OpenAPI documentation
# =============================================================================

class DatabaseErrorDetailSerializer(serializers.Serializer):
    """Error detail structure."""
    code = serializers.CharField(help_text="Error code (e.g., MISSING_PARAMETER)")
    message = serializers.CharField(help_text="Human-readable error message")
    details = serializers.DictField(required=False, help_text="Additional error details")


class DatabaseErrorResponseSerializer(serializers.Serializer):
    """Standard error response."""
    success = serializers.BooleanField(default=False)
    error = DatabaseErrorDetailSerializer()


class DatabaseListFiltersSerializer(serializers.Serializer):
    """Applied filters for database list."""
    cluster_id = serializers.UUIDField(required=False)
    status = serializers.CharField(required=False)
    health_status = serializers.CharField(required=False)
    search = serializers.CharField(required=False)


class DatabaseListResponseSerializer(serializers.Serializer):
    """Response for list_databases endpoint."""
    databases = DatabaseSerializer(many=True)
    count = serializers.IntegerField(help_text="Number of databases in current page")
    total = serializers.IntegerField(help_text="Total number of databases matching filters")


class DatabaseDetailResponseSerializer(serializers.Serializer):
    """Response for get_database endpoint."""
    database = DatabaseSerializer()
    cluster = ClusterSerializer(required=False, allow_null=True, help_text="Cluster info if database belongs to a cluster")


class DatabaseExtensionsSnapshotResponseSerializer(serializers.Serializer):
    """Response for get_extensions_snapshot endpoint."""
    database_id = serializers.UUIDField(help_text="Database UUID")
    snapshot = serializers.JSONField(help_text="Latest known extensions snapshot (empty object if not available)")
    updated_at = serializers.DateTimeField(allow_null=True, required=False)
    source_operation_id = serializers.CharField(allow_blank=True, required=False)


class DatabaseCredentialsUpdateRequestSerializer(serializers.Serializer):
    """Request body for update_database_credentials endpoint."""
    database_id = serializers.CharField(help_text="Database ID to update")
    username = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)
    reset = serializers.BooleanField(required=False, default=False)


class DatabaseCredentialsUpdateResponseSerializer(serializers.Serializer):
    """Response for update_database_credentials endpoint."""
    database = DatabaseSerializer()
    message = serializers.CharField()

class DatabaseDbmsMetadataUpdateRequestSerializer(serializers.Serializer):
    """Request body for update_dbms_metadata endpoint."""
    database_id = serializers.CharField(help_text="Database ID to update")
    dbms = serializers.CharField(required=False, allow_blank=True)
    db_server = serializers.CharField(required=False, allow_blank=True)
    db_name = serializers.CharField(required=False, allow_blank=True)
    reset = serializers.BooleanField(required=False, default=False)


class DatabaseDbmsMetadataUpdateResponseSerializer(serializers.Serializer):
    """Response for update_dbms_metadata endpoint."""
    database = DatabaseSerializer()
    message = serializers.CharField()


_IBCMD_OFFLINE_FORBIDDEN_KEYS = {
    "db_user",
    "db_pwd",
    "db_password",
}


class DatabaseIbcmdConnectionProfileUpdateRequestSerializer(serializers.Serializer):
    """Request body for update_ibcmd_connection_profile endpoint."""
    database_id = serializers.CharField(help_text="Database ID to update")
    reset = serializers.BooleanField(required=False, default=False)
    remote = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="IBCMD --remote=<url> (SSH URL, must start with ssh://)",
    )
    pid = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="IBCMD --pid=<pid> (optional)",
    )
    offline = serializers.DictField(
        required=False,
        child=serializers.CharField(allow_blank=True),
        help_text="IBCMD offline flags (raw dict, no secrets)",
    )

    def validate_remote(self, value: str) -> str:
        v = str(value or "").strip()
        if not v:
            return ""
        if not v.lower().startswith("ssh://"):
            raise serializers.ValidationError("remote must be an ssh:// URL")
        return v

    def validate_pid(self, value: int | None) -> int | None:
        if value in (None, ""):
            return None
        try:
            pid = int(value)
        except (TypeError, ValueError):
            raise serializers.ValidationError("pid must be an integer") from None
        if pid <= 0:
            raise serializers.ValidationError("pid must be a positive integer")
        return pid

    def validate_offline(self, value):
        if value in (None, ""):
            return None
        if not isinstance(value, dict):
            raise serializers.ValidationError("offline must be an object")
        forbidden = [k for k in value.keys() if str(k).strip().lower() in _IBCMD_OFFLINE_FORBIDDEN_KEYS]
        if forbidden:
            raise serializers.ValidationError(
                {k: "not allowed (secrets must not be stored in database metadata)" for k in forbidden}
            )
        # Keep raw dict as-is (values are already validated as strings).
        return value


class DatabaseIbcmdConnectionProfileUpdateResponseSerializer(serializers.Serializer):
    """Response for update_ibcmd_connection_profile endpoint."""
    database = DatabaseSerializer()
    message = serializers.CharField()


class InfobaseUserListResponseSerializer(serializers.Serializer):
    """Response for list_infobase_users endpoint."""
    users = InfobaseUserMappingSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class DbmsUserListResponseSerializer(serializers.Serializer):
    """Response for list_dbms_users endpoint."""
    users = DbmsUserMappingSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class HealthCheckEnqueueResponseSerializer(serializers.Serializer):
    """Response for health_check endpoints (operation queued)."""
    operation_id = serializers.CharField(help_text="ID of the created operation")
    status = serializers.CharField(help_text="Operation status (queued)")
    total_tasks = serializers.IntegerField(help_text="Number of tasks created")
    message = serializers.CharField(help_text="Status message")


class BulkHealthCheckRequestSerializer(serializers.Serializer):
    """Request body for bulk_health_check endpoint."""
    database_ids = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of database UUIDs to check"
    )
    cluster_id = serializers.UUIDField(
        required=False,
        help_text="Check all databases in this cluster"
    )


class HealthCheckRequestSerializer(serializers.Serializer):
    """Request body for health_check endpoint."""
    database_id = serializers.CharField(help_text="Database UUID to check")


class SetDatabaseStatusRequestSerializer(serializers.Serializer):
    """Request body for set_status endpoint."""

    database_ids = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
        max_length=500,
        help_text="List of database IDs to update",
    )
    status = serializers.ChoiceField(
        choices=[
            Database.STATUS_ACTIVE,
            Database.STATUS_INACTIVE,
            Database.STATUS_MAINTENANCE,
        ],
        help_text="New database status (active, inactive, maintenance)",
    )
    reason = serializers.CharField(required=False, allow_blank=True)


class SetDatabaseStatusResponseSerializer(serializers.Serializer):
    """Response for set_status endpoint."""

    updated = serializers.IntegerField()
    not_found = serializers.ListField(child=serializers.CharField())
    status = serializers.CharField()


class DatabaseStreamTicketRequestSerializer(serializers.Serializer):
    """Request body for database stream ticket endpoint."""

    cluster_id = serializers.UUIDField(required=False, allow_null=True)
    force = serializers.BooleanField(required=False, default=False)


class DatabaseStreamTicketResponseSerializer(serializers.Serializer):
    """Response for database stream ticket endpoint."""

    ticket = serializers.CharField(help_text="Short-lived ticket for SSE connection")
    expires_in = serializers.IntegerField(help_text="Seconds until ticket expires")
    stream_url = serializers.CharField(help_text="SSE endpoint URL to connect to")
    message = serializers.CharField()
