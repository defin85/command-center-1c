from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import IsInternalService
from .views_common import exclude_schema


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def get_operation_timeline(request):
    """
    POST /api/v2/internal/get-operation-timeline

    Get operation execution timeline from Redis.

    NOTE: Internal endpoint - no ownership check (service-to-service).
    For public access with ownership validation, use:
    POST /api/v2/operations/get-operation-timeline/

    Request body:
        operation_id: str (required)
        limit: int (default: 100, max: 500)
        offset: int (default: 0)

    Response:
    {
        "operation_id": "op-123",
        "timeline": [
            {
                "timestamp": 1734567890123,
                "event": "operation.started",
                "service": "worker",
                "metadata": {}
            }
        ],
        "total_events": 5,
        "duration_ms": 1234
    }
    """
    from apps.operations.services import TimelineService

    # Parse request body
    operation_id = request.data.get("operation_id")
    if not operation_id:
        return Response({"success": False, "error": "operation_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    # Parse params from body
    try:
        limit = min(int(request.data.get("limit", 100)), 500)
        offset = max(int(request.data.get("offset", 0)), 0)
    except (ValueError, TypeError):
        limit, offset = 100, 0

    # Get timeline via service (user=None skips ownership check for internal calls)
    result = TimelineService.get_timeline(operation_id=operation_id, limit=limit, offset=offset, user=None)

    if not result.success:
        from apps.operations.services.timeline_service import TimelineErrorCode

        error_msg = result.error or "Unknown error"

        # Use error_code instead of string matching
        if result.error_code == TimelineErrorCode.NOT_FOUND:
            return Response({"success": False, "error": error_msg}, status=status.HTTP_404_NOT_FOUND)
        return Response({"success": False, "error": error_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(
        {
            "operation_id": result.operation_id,
            "timeline": result.timeline,
            "total_events": result.total_events,
            "duration_ms": result.duration_ms,
        },
        status=status.HTTP_200_OK,
    )

