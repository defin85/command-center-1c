"""
Audit API views for logging Saga compensation results.
Internal API for Go Worker to report compensation execution outcomes.
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status, serializers
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.core.permissions import IsInternalService
from apps.operations.models import CompensationAuditLog

logger = logging.getLogger(__name__)

class CompensationResultSerializer(serializers.Serializer):
    name = serializers.CharField()
    success = serializers.BooleanField()
    attempts = serializers.IntegerField(required=False)
    total_duration = serializers.FloatField(required=False)
    error = serializers.CharField(required=False, allow_blank=True)
    executed_at = serializers.DateTimeField(required=False)


class CompensationLogRequestSerializer(serializers.Serializer):
    operation_id = serializers.CharField()
    results = CompensationResultSerializer(many=True)


class CompensationLogResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    count = serializers.IntegerField()


@extend_schema(
    tags=['v2'],
    summary='Log compensation results',
    request=CompensationLogRequestSerializer,
    responses={
        201: CompensationLogResponseSerializer,
        400: OpenApiResponse(description='Bad request'),
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
        500: OpenApiResponse(description='Internal server error'),
    },
)
@api_view(['POST'])
@permission_classes([IsInternalService])  # Internal service-to-service call (requires WORKER_API_KEY or service JWT)
def log_compensation(request):
    """
    POST /api/v2/audit/log-compensation/

    Internal endpoint for Go Worker to log compensation results.

    Request body:
    {
        "operation_id": "op-123",
        "results": [
            {
                "name": "unlock_infobase",
                "success": true,
                "attempts": 2,
                "total_duration": 3.5,
                "error": "",
                "executed_at": "2025-11-28T12:00:00Z"
            }
        ]
    }
    """
    operation_id = request.data.get('operation_id')
    results = request.data.get('results', [])

    if not operation_id:
        return Response(
            {'error': 'operation_id required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not results:
        return Response(
            {'error': 'results required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Batch create audit logs
    logs = []
    for result in results:
        executed_at = result.get('executed_at')
        if executed_at:
            executed_at = parse_datetime(executed_at) or timezone.now()
        else:
            executed_at = timezone.now()

        logs.append(CompensationAuditLog(
            operation_id=operation_id,
            compensation_name=result.get('name', 'unknown'),
            success=result.get('success', False),
            attempts=result.get('attempts', 1),
            duration_seconds=result.get('total_duration', 0),
            error_message=result.get('error', ''),
            executed_at=executed_at,
        ))

    try:
        CompensationAuditLog.objects.bulk_create(logs)
        logger.info(
            f"Logged {len(logs)} compensation results for operation {operation_id}"
        )
    except Exception as e:
        logger.error(f"Failed to log compensation: {e}")
        return Response(
            {'error': 'Failed to save audit logs'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return Response({
        'status': 'logged',
        'count': len(logs),
    }, status=status.HTTP_201_CREATED)
