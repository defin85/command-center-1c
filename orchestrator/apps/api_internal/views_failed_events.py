from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import IsInternalService
from .serializers import (
    FailedEventFailedSerializer,
    FailedEventReplayedSerializer,
    FailedEventsCleanupSerializer,
    FailedEventSerializer,
)
from .views_common import exclude_schema, logger


@exclude_schema
@api_view(["GET"])
@permission_classes([IsInternalService])
def list_pending_failed_events(request):
    """
    GET /api/v2/internal/list-pending-failed-events?batch_size=100

    Get pending failed events for replay.
    Called by Go Worker to fetch events that need to be replayed to Redis.

    Query params:
        batch_size: int (default: 100, max: 1000)

    Response:
    {
        "success": true,
        "events": [...],
        "count": 10
    }
    """
    from apps.operations.models import FailedEvent

    # Parse batch_size from query params
    try:
        batch_size = int(request.query_params.get("batch_size", 100))
        batch_size = min(max(batch_size, 1), 1000)  # Clamp to 1-1000
    except (ValueError, TypeError):
        batch_size = 100

    # Get pending events that haven't exceeded max retries
    events = (
        FailedEvent.objects.filter(status=FailedEvent.STATUS_PENDING)
        .filter(retry_count__lt=models.F("max_retries"))
        .order_by("created_at")[:batch_size]
    )

    serializer = FailedEventSerializer(events, many=True)

    logger.debug(f"Fetched {len(serializer.data)} pending failed events")

    return Response({"success": True, "events": serializer.data, "count": len(serializer.data)}, status=status.HTTP_200_OK)


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def mark_event_replayed(request):
    """
    POST /api/v2/internal/mark-event-replayed?event_id=X

    Mark event as successfully replayed.
    Called by Go Worker after successfully publishing event to Redis.

    Query params:
        event_id: int (required)

    Request body:
    {
        "replayed_at": "2025-01-01T12:00:00Z"  // optional
    }

    Response:
    {
        "success": true,
        "event_id": 123,
        "status": "replayed"
    }
    """
    from apps.operations.models import FailedEvent

    event_id = request.query_params.get("event_id")
    if not event_id:
        return Response(
            {"success": False, "error": {"event_id": "This query parameter is required"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        event_id = int(event_id)
    except ValueError:
        return Response(
            {"success": False, "error": {"event_id": "Must be an integer"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = FailedEventReplayedSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    try:
        event = FailedEvent.objects.get(id=event_id)
    except FailedEvent.DoesNotExist:
        return Response({"success": False, "error": f"FailedEvent {event_id} not found"}, status=status.HTTP_404_NOT_FOUND)

    # Mark as replayed
    replayed_at = serializer.validated_data.get("replayed_at") or timezone.now()
    event.status = FailedEvent.STATUS_REPLAYED
    event.replayed_at = replayed_at
    event.save(update_fields=["status", "replayed_at", "updated_at"])

    logger.info(f"Failed event replayed: id={event_id}, " f"correlation_id={event.correlation_id}")

    return Response({"success": True, "event_id": event_id, "status": "replayed"}, status=status.HTTP_200_OK)


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def mark_event_failed(request):
    """
    POST /api/v2/internal/mark-event-failed?event_id=X

    Mark event as failed (increment retry count).
    Called by Go Worker when replay attempt fails.

    Query params:
        event_id: int (required)

    Request body:
    {
        "error_message": "Connection refused",
        "increment_retry": true  // default: true
    }

    Response:
    {
        "success": true,
        "event_id": 123,
        "new_status": "pending",
        "retry_count": 3
    }
    """
    from apps.operations.models import FailedEvent

    event_id = request.query_params.get("event_id")
    if not event_id:
        return Response(
            {"success": False, "error": {"event_id": "This query parameter is required"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        event_id = int(event_id)
    except ValueError:
        return Response(
            {"success": False, "error": {"event_id": "Must be an integer"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = FailedEventFailedSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    # Use select_for_update to prevent race condition
    with transaction.atomic():
        try:
            event = FailedEvent.objects.select_for_update().get(id=event_id)
        except FailedEvent.DoesNotExist:
            return Response({"success": False, "error": f"FailedEvent {event_id} not found"}, status=status.HTTP_404_NOT_FOUND)

        # Update error message
        event.last_error = data["error_message"]

        # Increment retry count if requested
        if data.get("increment_retry", True):
            event.retry_count += 1

        # Check if max retries exceeded
        if event.retry_count >= event.max_retries:
            event.status = FailedEvent.STATUS_FAILED
        else:
            event.status = FailedEvent.STATUS_PENDING

        event.save(update_fields=["last_error", "retry_count", "status", "updated_at"])

    logger.info(f"Failed event retry failed: id={event_id}, " f"retry_count={event.retry_count}, status={event.status}")

    return Response(
        {"success": True, "event_id": event_id, "new_status": event.status, "retry_count": event.retry_count},
        status=status.HTTP_200_OK,
    )


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def cleanup_failed_events(request):
    """
    POST /api/v2/internal/cleanup-failed-events

    Delete old replayed events.
    Called by Go Worker periodically to clean up storage.

    Request body:
    {
        "retention_days": 7  // default: 7
    }

    Response:
    {
        "success": true,
        "deleted_count": 150
    }
    """
    from apps.operations.models import FailedEvent

    serializer = FailedEventsCleanupSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    retention_days = serializer.validated_data.get("retention_days", 7)
    cutoff_date = timezone.now() - timedelta(days=retention_days)

    # Delete old events in a transaction
    with transaction.atomic():
        # Delete old replayed events
        deleted_count, _ = FailedEvent.objects.filter(status=FailedEvent.STATUS_REPLAYED, replayed_at__lt=cutoff_date).delete()

        # Also delete old permanently failed events
        failed_deleted, _ = FailedEvent.objects.filter(status=FailedEvent.STATUS_FAILED, updated_at__lt=cutoff_date).delete()

    total_deleted = deleted_count + failed_deleted

    logger.info(f"Failed events cleanup: deleted {total_deleted} events " f"(replayed: {deleted_count}, failed: {failed_deleted})")

    return Response({"success": True, "deleted_count": total_deleted}, status=status.HTTP_200_OK)

