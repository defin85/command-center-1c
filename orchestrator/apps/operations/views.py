from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.conf import settings
from .models import BatchOperation, Task
from .serializers import BatchOperationSerializer
from .redis_client import redis_client
import logging
import json
import redis as redis_module

logger = logging.getLogger(__name__)


def health_check(request):
    """Health check endpoint."""
    return JsonResponse({
        'status': 'healthy',
        'service': 'orchestrator',
    })


class BatchOperationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing batch operations."""

    queryset = BatchOperation.objects.all().prefetch_related('target_databases')
    serializer_class = BatchOperationSerializer
    filterset_fields = ['status', 'operation_type']
    ordering = ['-created_at']

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a batch operation."""
        operation = self.get_object()
        if operation.status in [BatchOperation.STATUS_PENDING, BatchOperation.STATUS_PROCESSING]:
            operation.status = BatchOperation.STATUS_CANCELLED
            operation.save()
            return Response({'status': 'cancelled'})
        return Response(
            {'error': 'Operation cannot be cancelled'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@extend_schema(
    summary="Callback от Go Worker после завершения операции",
    description="""
    Принимает результат выполнения операции от Go Worker.
    Обновляет статусы BatchOperation и Task.
    """,
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'operation_id': {'type': 'string'},
                'status': {'type': 'string', 'enum': ['completed', 'failed', 'timeout']},
                'results': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'database_id': {'type': 'string'},
                            'success': {'type': 'boolean'},
                            'data': {'type': 'object'},
                            'error': {'type': 'string'},
                            'error_code': {'type': 'string'},
                            'duration_seconds': {'type': 'number'}
                        }
                    }
                },
                'summary': {
                    'type': 'object',
                    'properties': {
                        'total': {'type': 'integer'},
                        'succeeded': {'type': 'integer'},
                        'failed': {'type': 'integer'}
                    }
                },
                'worker_id': {'type': 'string'}
            },
            'required': ['operation_id', 'status', 'results']
        }
    },
    responses={
        200: OpenApiResponse(description="Callback processed successfully"),
        400: OpenApiResponse(description="Invalid request"),
        404: OpenApiResponse(description="Operation not found")
    }
)
def operation_callback(request, operation_id):
    """
    Callback endpoint для Go Worker.

    POST /api/v1/operations/{operation_id}/callback

    Payload (OperationResult):
    {
        "operation_id": "uuid",
        "status": "completed|failed|timeout",
        "results": [
            {
                "database_id": "uuid",
                "success": true,
                "data": {...},
                "error": null,
                "duration_seconds": 2.5
            }
        ],
        "summary": {
            "total": 10,
            "succeeded": 8,
            "failed": 2
        },
        "worker_id": "worker-1"
    }
    """
    logger.info(f"Received callback for operation {operation_id}")

    # Validate operation_id match
    payload_op_id = request.data.get("operation_id")
    if payload_op_id != operation_id:
        return Response(
            {"error": "operation_id mismatch"},
            status=status.HTTP_400_BAD_REQUEST
        )

    result_status = request.data.get("status")
    results = request.data.get("results", [])
    worker_id = request.data.get("worker_id")

    if not result_status or not isinstance(results, list):
        return Response(
            {"error": "Invalid payload: missing status or results"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Get operation
        operation = BatchOperation.objects.get(id=operation_id)

        # Update operation status
        if result_status == "completed":
            operation.status = BatchOperation.STATUS_COMPLETED
        elif result_status == "failed":
            operation.status = BatchOperation.STATUS_FAILED
        elif result_status == "timeout":
            operation.status = BatchOperation.STATUS_FAILED  # Timeout = Failed

        operation.save(update_fields=["status", "updated_at"])

        # Update tasks
        for result in results:
            database_id = result.get("database_id")
            success = result.get("success")

            try:
                task = Task.objects.get(
                    batch_operation=operation,
                    database_id=database_id
                )

                # Set worker_id
                if worker_id:
                    task.worker_id = worker_id

                if success:
                    task.mark_completed(result=result.get("data"))
                else:
                    task.mark_failed(
                        error_message=result.get("error", "Unknown error"),
                        error_code=result.get("error_code", "UNKNOWN_ERROR"),
                        should_retry=True  # Will check retry_count internally
                    )

            except Task.DoesNotExist:
                logger.warning(
                    f"Task not found for database {database_id} in operation {operation_id}"
                )

        # Update operation progress
        operation.update_progress()

        # Extend idempotency lock to 24 hours
        redis_client.extend_lock(operation_id, ttl_seconds=86400)

        logger.info(
            f"Callback processed for operation {operation_id}",
            extra={
                "status": result_status,
                "total_results": len(results),
                "worker_id": worker_id
            }
        )

        return Response({"status": "ok"}, status=status.HTTP_200_OK)

    except BatchOperation.DoesNotExist:
        logger.error(f"Operation {operation_id} not found")
        return Response(
            {"error": f"Operation {operation_id} not found"},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
def operation_stream(request, operation_id):
    """
    SSE endpoint для real-time updates операции.

    GET /api/v1/operations/{operation_id}/stream?token={jwt_token}

    NOTE: EventSource не поддерживает custom headers, поэтому токен передается через query parameter.

    Клиент подключается через EventSource и получает события в real-time:
    - PENDING → QUEUED → PROCESSING → UPLOADING → INSTALLING → VERIFYING → SUCCESS/FAILED

    Event format:
    data: {"state": "PROCESSING", "microservice": "worker", "message": "...", "timestamp": "..."}
    """
    # Manual authentication via query parameter (EventSource limitation)
    from rest_framework_simplejwt.authentication import JWTAuthentication
    from rest_framework.exceptions import AuthenticationFailed

    token = request.GET.get('token')
    if not token:
        return JsonResponse({'error': 'Missing token parameter'}, status=401)

    try:
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        if not user:
            raise AuthenticationFailed('User not found')
    except Exception as e:
        logger.error(f"SSE authentication failed: {e}")
        return JsonResponse({'error': 'Invalid token'}, status=401)

    logger.info(f"SSE stream requested for operation {operation_id} by user {user.username}")

    def event_stream():
        """Generator для SSE событий."""
        logger.info(f"event_stream: Starting for operation {operation_id}")

        # Подключиться к Redis PubSub
        redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
        redis_conn = redis_module.from_url(
            redis_url,
            decode_responses=True
        )
        pubsub = redis_conn.pubsub()
        channel = f"operation:{operation_id}:events"
        pubsub.subscribe(channel)
        logger.info(f"event_stream: Subscribed to channel {channel}")

        # Отправить начальное состояние
        try:
            operation = BatchOperation.objects.get(id=operation_id)
            logger.info(f"event_stream: Found operation with status {operation.status}")
            initial_event = {
                "version": "1.0",
                "operation_id": str(operation_id),
                "timestamp": timezone.now().isoformat(),
                "state": operation.status.upper(),
                "microservice": "orchestrator",
                "message": f"Операция в статусе {operation.status}",
                "metadata": {
                    "operation_type": operation.operation_type,
                    "created_at": operation.created_at.isoformat()
                }
            }
            logger.info("event_stream: Sending initial event")
            yield f"data: {json.dumps(initial_event)}\n\n"
            logger.info("event_stream: Initial event sent")
        except BatchOperation.DoesNotExist:
            error_event = {
                "error": "Operation not found",
                "operation_id": str(operation_id)
            }
            yield f"data: {json.dumps(error_event)}\n\n"
            pubsub.unsubscribe()
            pubsub.close()
            redis_conn.close()
            return

        # Слушать события из Redis PubSub
        try:
            for message in pubsub.listen():
                if message['type'] == 'message':
                    # Переслать событие клиенту
                    yield f"data: {message['data']}\n\n"
        except GeneratorExit:
            # Клиент отключился
            logger.info(f"Client disconnected from SSE stream for operation {operation_id}")
        finally:
            pubsub.unsubscribe()
            pubsub.close()
            redis_conn.close()

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
    return response
