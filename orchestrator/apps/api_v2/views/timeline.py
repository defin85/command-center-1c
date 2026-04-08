"""
Timeline endpoints for API v2.

Provides public endpoints for operation timeline retrieval with JWT authentication
and ownership validation.
"""
import logging

from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.operations.services import TimelineService

logger = logging.getLogger(__name__)


# =============================================================================
# Serializers
# =============================================================================

class TimelineEventSerializer(serializers.Serializer):
    """Timeline event structure."""
    timestamp = serializers.IntegerField(help_text="Unix timestamp in milliseconds")
    event = serializers.CharField(help_text="Event name (e.g., operation.started)")
    service = serializers.CharField(help_text="Service that emitted the event")
    trace_id = serializers.CharField(required=False, allow_null=True, help_text="OpenTelemetry trace ID")
    workflow_execution_id = serializers.CharField(required=False, allow_null=True, help_text="Workflow execution ID")
    node_id = serializers.CharField(required=False, allow_null=True, help_text="Workflow node ID")
    root_operation_id = serializers.CharField(required=False, allow_null=True, help_text="Root operation ID")
    execution_consumer = serializers.CharField(required=False, allow_null=True, help_text="Execution consumer")
    lane = serializers.CharField(required=False, allow_null=True, help_text="QoS lane")
    metadata = serializers.DictField(required=False, help_text="Additional event metadata")


class GetOperationTimelineRequestSerializer(serializers.Serializer):
    """Request body for get_operation_timeline endpoint."""
    operation_id = serializers.CharField(
        required=True,
        help_text="Operation ID (UUID)"
    )
    limit = serializers.IntegerField(
        required=False,
        default=100,
        min_value=1,
        max_value=500,
        help_text="Maximum events to return (default: 100, max: 500)"
    )
    offset = serializers.IntegerField(
        required=False,
        default=0,
        min_value=0,
        help_text="Pagination offset (default: 0)"
    )


class GetOperationTimelineResponseSerializer(serializers.Serializer):
    """Response for get_operation_timeline endpoint."""
    operation_id = serializers.CharField(help_text="Operation ID")
    timeline = TimelineEventSerializer(many=True, help_text="List of timeline events")
    total_events = serializers.IntegerField(help_text="Total number of events")
    duration_ms = serializers.IntegerField(
        allow_null=True,
        help_text="Duration in milliseconds (null if < 2 events)"
    )


class TimelineErrorDetailSerializer(serializers.Serializer):
    """Error detail structure."""
    code = serializers.CharField(help_text="Error code")
    message = serializers.CharField(help_text="Human-readable error message")


class TimelineErrorResponseSerializer(serializers.Serializer):
    """Standard error response."""
    success = serializers.BooleanField(default=False)
    error = TimelineErrorDetailSerializer()
    request_id = serializers.CharField()
    ui_action_id = serializers.CharField(required=False)


# =============================================================================
# Endpoints
# =============================================================================

@extend_schema(
    tags=['v2'],
    summary='Get operation timeline',
    description='''
    Get the execution timeline for an operation.

    **Authentication:** Requires valid JWT token.

    **Authorization:** User must own the operation (created_by matches username)
    or be staff.

    **Response format:**
    - Timeline events are sorted chronologically (ascending)
    - Each event includes timestamp, event name, service, and optional metadata
    - Duration is calculated from first to last event (null if < 2 events)

    **Graceful degradation:**
    - If Redis is unavailable, returns empty timeline (not 500 error)
    ''',
    request=GetOperationTimelineRequestSerializer,
    responses={
        200: GetOperationTimelineResponseSerializer,
        400: TimelineErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        403: TimelineErrorResponseSerializer,
        404: TimelineErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_operation_timeline(request):
    """
    POST /api/v2/operations/get-operation-timeline/

    Get operation execution timeline from Redis.

    Request Body:
        {
            "operation_id": "uuid-string",
            "limit": 100,     // optional, default 100, max 500
            "offset": 0       // optional, default 0
        }

    Response (200 OK):
        {
            "operation_id": "uuid-string",
            "timeline": [
                {
                    "timestamp": 1734567890123,
                    "event": "operation.started",
                    "service": "worker",
                    "trace_id": "0123abcd...",
                    "workflow_execution_id": "wf-exec-123",
                    "node_id": "node-1",
                    "metadata": {}
                },
                ...
            ],
            "total_events": 5,
            "duration_ms": 1234
        }
    """
    # Validate request body
    serializer = GetOperationTimelineRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': str(serializer.errors)
            }
        }, status=status.HTTP_400_BAD_REQUEST)

    operation_id = serializer.validated_data['operation_id']
    limit = serializer.validated_data.get('limit', 100)
    offset = serializer.validated_data.get('offset', 0)

    # Get timeline with ownership validation
    result = TimelineService.get_timeline(
        operation_id=operation_id,
        limit=limit,
        offset=offset,
        user=request.user  # Enables ownership check
    )

    # Handle errors
    if not result.success:
        from apps.operations.services.timeline_service import TimelineErrorCode

        # Use error_code instead of string matching for security and reliability
        error_msg = result.error or "Unknown error"

        # Security: Both NOT_FOUND and FORBIDDEN return 404 to prevent information disclosure
        if result.error_code in (TimelineErrorCode.NOT_FOUND, TimelineErrorCode.FORBIDDEN):
            # Log FORBIDDEN separately for audit (already logged in service)
            return Response({
                'success': False,
                'error': {
                    'code': 'OPERATION_NOT_FOUND',
                    'message': error_msg
                }
            }, status=status.HTTP_404_NOT_FOUND)
        elif result.error_code == TimelineErrorCode.REDIS_ERROR:
            return Response({
                'success': False,
                'error': {
                    'code': 'REDIS_ERROR',
                    'message': error_msg
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response({
                'success': False,
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': error_msg
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Log access for audit
    logger.info(
        f"Timeline accessed for operation {operation_id}",
        extra={
            'operation_id': operation_id,
            'user': request.user.username,
            'total_events': result.total_events
        }
    )

    return Response({
        'operation_id': result.operation_id,
        'timeline': result.timeline,
        'total_events': result.total_events,
        'duration_ms': result.duration_ms
    }, status=status.HTTP_200_OK)
