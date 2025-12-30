"""
Events API views for storing failed events (PostgreSQL fallback).
Internal API for Go services when Redis is unavailable.
"""

import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.core.permissions import IsInternalService
from apps.operations.models import FailedEvent

logger = logging.getLogger(__name__)


class StoreFailedEventRequestSerializer(serializers.Serializer):
    channel = serializers.CharField()
    event_type = serializers.CharField()
    correlation_id = serializers.CharField()
    payload = serializers.JSONField()
    source_service = serializers.CharField()
    original_timestamp = serializers.DateTimeField(required=False)


class StoreFailedEventResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    event_id = serializers.IntegerField()


class PendingEventsResponseSerializer(serializers.Serializer):
    pending_count = serializers.IntegerField()
    failed_count = serializers.IntegerField()


@extend_schema(
    tags=['v2'],
    summary='Store failed event',
    description='Internal endpoint to store events that failed to publish to Redis.',
    request=StoreFailedEventRequestSerializer,
    responses={
        201: StoreFailedEventResponseSerializer,
        400: OpenApiResponse(description='Bad request'),
        403: OpenApiResponse(description='Forbidden'),
        500: OpenApiResponse(description='Internal server error'),
    },
)
@api_view(['POST'])
@permission_classes([IsInternalService])  # Internal service-to-service call (requires WORKER_API_KEY or service JWT)
def store_failed_event(request):
    """
    POST /api/v2/events/store-failed/

    Internal endpoint for Go services to store events that failed to publish to Redis.

    Request body:
    {
        "channel": "events:orchestrator:operation:completed",
        "event_type": "orchestrator.operation.completed",
        "correlation_id": "corr-456",
        "payload": {"operation_id": "op-123", "success": true},
        "source_service": "worker",
        "original_timestamp": "2025-11-28T12:00:00Z"
    }
    """
    required_fields = ['channel', 'event_type', 'correlation_id', 'payload', 'source_service']

    for field in required_fields:
        if field not in request.data:
            return Response(
                {'error': f'{field} required'},
                status=status.HTTP_400_BAD_REQUEST
            )

    # Parse original timestamp or use now
    original_timestamp = request.data.get('original_timestamp')
    if original_timestamp:
        original_timestamp = parse_datetime(original_timestamp) or timezone.now()
    else:
        original_timestamp = timezone.now()

    try:
        event = FailedEvent.objects.create(
            channel=request.data['channel'],
            event_type=request.data['event_type'],
            correlation_id=request.data['correlation_id'],
            payload=request.data['payload'],
            source_service=request.data['source_service'],
            original_timestamp=original_timestamp,
        )

        logger.warning(
            f"Stored failed event: {event.event_type} (correlation_id={event.correlation_id})"
        )

        return Response({
            'status': 'stored',
            'event_id': event.id,
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Failed to store event: {e}")
        return Response(
            {'error': 'Failed to store event'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['v2'],
    summary='Get pending events stats',
    description='Returns counts of pending and failed events (for monitoring).',
    responses={
        200: PendingEventsResponseSerializer,
    },
)
@api_view(['GET'])
@permission_classes([AllowAny])
def get_pending_events(request):
    """
    GET /api/v2/events/pending/

    Returns count and list of pending events (for monitoring).
    """
    pending_count = FailedEvent.objects.filter(status=FailedEvent.STATUS_PENDING).count()
    failed_count = FailedEvent.objects.filter(status=FailedEvent.STATUS_FAILED).count()

    return Response({
        'pending_count': pending_count,
        'failed_count': failed_count,
    })
