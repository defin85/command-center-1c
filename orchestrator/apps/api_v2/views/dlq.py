"""
Dead Letter Queue (DLQ) endpoints for API v2.

Provides operator/admin access to inspect and retry DLQ messages produced by Go Worker.

DLQ source: Redis Stream `commands:worker:dlq`
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from apps.api_v2.serializers.common import ErrorResponseSerializer
from apps.operations.models import BatchOperation
from apps.operations.services.admin_action_audit import log_admin_action
from apps.operations.services.operations_service import OperationsService

logger = logging.getLogger(__name__)


DLQ_STREAM = "commands:worker:dlq"


def _get_redis_client() -> redis.Redis:
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=int(settings.REDIS_PORT),
        db=int(settings.REDIS_DB),
        decode_responses=True,
        socket_timeout=2,
    )


class DLQMessageSerializer(serializers.Serializer):
    dlq_message_id = serializers.CharField(help_text="Redis Stream entry ID")
    original_message_id = serializers.CharField(required=False)
    correlation_id = serializers.CharField(required=False, allow_blank=True)
    operation_id = serializers.CharField(required=False, allow_blank=True)
    event_type = serializers.CharField(required=False, allow_blank=True)
    error_code = serializers.CharField(required=False, allow_blank=True)
    error_message = serializers.CharField(required=False, allow_blank=True)
    worker_id = serializers.CharField(required=False, allow_blank=True)
    failed_at = serializers.CharField(required=False, allow_blank=True)


class DLQListResponseSerializer(serializers.Serializer):
    messages = DLQMessageSerializer(many=True)
    count = serializers.IntegerField()
    total = serializers.IntegerField()


class DLQRetryRequestSerializer(serializers.Serializer):
    original_message_id = serializers.CharField(required=False, allow_blank=True)
    operation_id = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)


class DLQRetryResponseSerializer(serializers.Serializer):
    enqueued = serializers.BooleanField()
    operation_id = serializers.CharField(required=False, allow_blank=True)
    message = serializers.CharField()


@dataclass(frozen=True)
class _DLQFilters:
    operation_id: Optional[str]
    error_code: Optional[str]
    since: Optional[datetime]
    limit: int
    offset: int


def _parse_filters(request) -> _DLQFilters:
    operation_id = (request.query_params.get("operation_id") or "").strip() or None
    error_code = (request.query_params.get("error_code") or "").strip() or None

    since_raw = (request.query_params.get("since") or "").strip()
    since = parse_datetime(since_raw) if since_raw else None

    try:
        limit = int(request.query_params.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 200))

    try:
        offset = int(request.query_params.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, offset)

    return _DLQFilters(operation_id=operation_id, error_code=error_code, since=since, limit=limit, offset=offset)


def _normalize_dlq_entry(entry_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "dlq_message_id": entry_id,
        "original_message_id": fields.get("original_message_id", ""),
        "correlation_id": fields.get("correlation_id", ""),
        "operation_id": fields.get("operation_id", ""),
        "event_type": fields.get("event_type", ""),
        "error_code": fields.get("error_code", ""),
        "error_message": fields.get("error_message", ""),
        "worker_id": fields.get("worker_id", ""),
        "failed_at": fields.get("failed_at", ""),
    }


def _passes_filters(entry: Dict[str, Any], filters: _DLQFilters) -> bool:
    if filters.operation_id and entry.get("operation_id") != filters.operation_id:
        return False
    if filters.error_code and entry.get("error_code") != filters.error_code:
        return False
    if filters.since:
        failed_at_raw = entry.get("failed_at") or ""
        failed_at = parse_datetime(failed_at_raw)
        if failed_at and failed_at < filters.since:
            return False
    return True


@extend_schema(
    tags=["v2"],
    summary="List DLQ messages",
    description="List recent DLQ entries from Redis Stream `commands:worker:dlq`. Staff-only.",
    parameters=[
        OpenApiParameter(name="operation_id", type=str, required=False),
        OpenApiParameter(name="error_code", type=str, required=False),
        OpenApiParameter(name="since", type=str, required=False, description="RFC3339 timestamp filter"),
        OpenApiParameter(name="limit", type=int, required=False, description="1..200 (default 50)"),
        OpenApiParameter(name="offset", type=int, required=False, description="Offset within the fetched window"),
    ],
    responses={
        200: DLQListResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
def list_dlq(request):
    filters = _parse_filters(request)

    client = _get_redis_client()
    fetch_count = filters.limit + filters.offset

    try:
        total = int(client.xlen(DLQ_STREAM))
        raw_items = client.xrevrange(DLQ_STREAM, max="+", min="-", count=fetch_count)
    except Exception as e:
        logger.error("DLQ list failed: %s", e, exc_info=True)
        return Response(
            {"success": False, "error": {"code": "REDIS_ERROR", "message": "Failed to read DLQ"}},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    items: List[Dict[str, Any]] = []
    for entry_id, fields in raw_items:
        entry = _normalize_dlq_entry(entry_id, fields)
        if _passes_filters(entry, filters):
            items.append(entry)

    sliced = items[filters.offset:filters.offset + filters.limit]

    return Response(
        {
            "messages": sliced,
            "count": len(sliced),
            "total": total,
        }
    )


@extend_schema(
    tags=["v2"],
    summary="Get DLQ message",
    description="Fetch a single DLQ entry by stream entry id or original_message_id. Staff-only.",
    parameters=[
        OpenApiParameter(name="dlq_message_id", type=str, required=False, description="Redis Stream entry ID"),
        OpenApiParameter(name="original_message_id", type=str, required=False, description="Original stream message ID"),
    ],
    responses={
        200: DLQMessageSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
        404: ErrorResponseSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
def get_dlq(request):
    dlq_message_id = (request.query_params.get("dlq_message_id") or "").strip()
    original_message_id = (request.query_params.get("original_message_id") or "").strip()
    if not dlq_message_id and not original_message_id:
        return Response(
            {"success": False, "error": {"code": "MISSING_PARAMETER", "message": "dlq_message_id or original_message_id is required"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    client = _get_redis_client()

    try:
        if dlq_message_id:
            items = client.xrange(DLQ_STREAM, min=dlq_message_id, max=dlq_message_id, count=1)
            if not items:
                return Response(
                    {"success": False, "error": {"code": "NOT_FOUND", "message": "DLQ message not found"}},
                    status=status.HTTP_404_NOT_FOUND,
                )
            entry_id, fields = items[0]
            return Response(_normalize_dlq_entry(entry_id, fields))

        # original_message_id lookup: scan recent window (bounded)
        raw_items = client.xrevrange(DLQ_STREAM, max="+", min="-", count=500)
        for entry_id, fields in raw_items:
            if str(fields.get("original_message_id", "")) == original_message_id:
                return Response(_normalize_dlq_entry(entry_id, fields))
    except Exception as e:
        logger.error("DLQ get failed: %s", e, exc_info=True)
        return Response(
            {"success": False, "error": {"code": "REDIS_ERROR", "message": "Failed to read DLQ"}},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(
        {"success": False, "error": {"code": "NOT_FOUND", "message": "DLQ message not found"}},
        status=status.HTTP_404_NOT_FOUND,
    )


@extend_schema(
    tags=["v2"],
    summary="Retry DLQ message",
    description="Retry an operation associated with a DLQ entry by re-enqueueing it to worker stream. Staff-only.",
    request=DLQRetryRequestSerializer,
    responses={
        200: DLQRetryResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description="Unauthorized"),
        403: OpenApiResponse(description="Forbidden"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def retry_dlq(request):
    serializer = DLQRetryRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    operation_id = (serializer.validated_data.get("operation_id") or "").strip()
    original_message_id = (serializer.validated_data.get("original_message_id") or "").strip()
    reason = (serializer.validated_data.get("reason") or "").strip()

    if not operation_id and not original_message_id:
        log_admin_action(
            request,
            action="dlq.retry",
            outcome="error",
            target_type="dlq",
            metadata={"operation_id": None, "original_message_id": None},
            error_message="MISSING_PARAMETER",
        )
        return Response(
            {"success": False, "error": {"code": "MISSING_PARAMETER", "message": "operation_id or original_message_id is required"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not operation_id and original_message_id:
        # Lookup recent DLQ entries for operation_id.
        client = _get_redis_client()
        try:
            raw_items = client.xrevrange(DLQ_STREAM, max="+", min="-", count=500)
            for _entry_id, fields in raw_items:
                if str(fields.get("original_message_id", "")) == original_message_id:
                    operation_id = str(fields.get("operation_id", "")).strip()
                    break
        except Exception as e:
            logger.error("DLQ retry lookup failed: %s", e, exc_info=True)
            log_admin_action(
                request,
                action="dlq.retry",
                outcome="error",
                target_type="dlq",
                metadata={"original_message_id": original_message_id},
                error_message="REDIS_ERROR",
            )
            return Response(
                {"success": False, "error": {"code": "REDIS_ERROR", "message": "Failed to read DLQ"}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    if not operation_id:
        log_admin_action(
            request,
            action="dlq.retry",
            outcome="error",
            target_type="dlq",
            metadata={"original_message_id": original_message_id},
            error_message="OPERATION_ID_MISSING",
        )
        return Response(
            {"success": False, "error": {"code": "OPERATION_ID_MISSING", "message": "DLQ entry does not contain operation_id"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = OperationsService.enqueue_operation(operation_id)
    if not result.success:
        log_admin_action(
            request,
            action="dlq.retry",
            outcome="error",
            target_type="batch_operation",
            target_id=operation_id,
            metadata={"original_message_id": original_message_id or None, "reason": reason or None},
            error_message="ENQUEUE_FAILED",
        )
        return Response(
            {"success": False, "error": {"code": "ENQUEUE_FAILED", "message": result.error or "Failed to enqueue operation"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Minimal audit trail: store retry metadata on BatchOperation.metadata (best-effort).
    try:
        with transaction.atomic():
            op = BatchOperation.objects.select_for_update().get(id=operation_id)
            retries = op.metadata.get("dlq_retries")
            if not isinstance(retries, list):
                retries = []
            retries.append(
                {
                    "at": timezone.now().isoformat(),
                    "user_id": getattr(request.user, "id", None),
                    "username": getattr(request.user, "username", ""),
                    "original_message_id": original_message_id or None,
                    "reason": reason or None,
                }
            )
            op.metadata["dlq_retries"] = retries
            op.save(update_fields=["metadata", "updated_at"])
    except BatchOperation.DoesNotExist:
        logger.warning("DLQ retry audit skipped: BatchOperation not found: %s", operation_id)
    except Exception as e:
        logger.warning("DLQ retry audit failed: %s", e, exc_info=True)

    log_admin_action(
        request,
        action="dlq.retry",
        outcome="success",
        target_type="batch_operation",
        target_id=operation_id,
        metadata={"original_message_id": original_message_id or None, "reason": reason or None},
    )

    return Response(
        {
            "enqueued": True,
            "operation_id": operation_id,
            "message": "Operation re-enqueued successfully",
        }
    )
