"""Operations endpoint: execute_operation."""

from __future__ import annotations

import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.databases.permissions import CanExecuteOperation
from apps.operations.services import OperationsService

from .schemas import (
    ExecuteOperationRequestSerializer,
    ExecuteOperationResponseSerializer,
    ExecuteOperationThrottle,
    OperationErrorResponseSerializer,
)

logger = logging.getLogger(__name__)

def _split_select(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item.strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(',') if item.strip()]
    return []


def _enqueue_odata_operation(user, operation_type, database_ids, config):
    config = config or {}
    data: dict = {}
    filters: dict = {}
    options: dict = {}
    target_entity = config.get("entity") or config.get("entity_name")

    if operation_type in ("create", "update", "delete", "query") and not target_entity:
        raise ValueError("entity is required for OData operations")

    if operation_type == "query":
        if "filter" in config and config["filter"] is not None:
            options["filter"] = config["filter"]
        select_list = _split_select(config.get("select"))
        if select_list:
            options["select"] = select_list
        if config.get("top") is not None:
            options["top"] = config.get("top")
        if config.get("skip") is not None:
            options["skip"] = config.get("skip")
    elif operation_type == "create":
        data = config.get("data") or {}
        if not isinstance(data, dict):
            raise ValueError("data must be an object for create operation")
    elif operation_type == "update":
        data = config.get("data") or {}
        if not isinstance(data, dict):
            raise ValueError("data must be an object for update operation")
        entity_id = config.get("entity_id")
        if not entity_id:
            raise ValueError("entity_id is required for update operation")
        filters["entity_id"] = entity_id
    elif operation_type == "delete":
        entity_id = config.get("entity_id")
        if not entity_id:
            raise ValueError("entity_id is required for delete operation")
        filters["entity_id"] = entity_id
    else:
        raise ValueError(f"Unsupported OData operation_type: {operation_type}")

    return OperationsService.enqueue_odata_operation(
        operation_type=operation_type,
        database_ids=database_ids,
        target_entity=target_entity,
        data=data,
        filters=filters,
        options=options,
        user=user,
    )

@extend_schema(
    tags=['v2'],
    summary='Execute RAS operation',
    description='''
    Queue an operation for execution on selected databases.

    **Supported operation types:**
    - RAS: `lock_scheduled_jobs`, `unlock_scheduled_jobs`, `block_sessions`,
      `unblock_sessions`, `terminate_sessions`
    - OData: `create`, `update`, `delete`, `query`
    - CLI: `designer_cli`

    **Config notes:**
    - RAS block_sessions: `message`, `permission_code`, `denied_from`, `denied_to`, `parameter`
    - OData query: `entity`, `filter`, `select`, `top`, `skip`
    - OData update/delete: `entity`, `entity_id`
    - CLI designer_cli: `command` + `args` + optional `options`
    ''',
    request=ExecuteOperationRequestSerializer,
    responses={
        202: ExecuteOperationResponseSerializer,
        400: OperationErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, CanExecuteOperation])
@throttle_classes([ExecuteOperationThrottle])
def execute_operation(request):
    """
    POST /api/v2/operations/execute/

    Queue an operation for multiple databases.

    Request Body:
        {
            "operation_type": "lock_scheduled_jobs",
            "database_ids": ["uuid1", "uuid2"],
            "config": {}  // optional
        }

    Response (202 Accepted):
        {
            "operation_id": "uuid",
            "status": "queued",
            "total_tasks": 2,
            "message": "lock_scheduled_jobs queued for 2 database(s)"
        }
    """
    serializer = ExecuteOperationRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    operation_type = serializer.validated_data['operation_type']
    database_ids = serializer.validated_data['database_ids']
    config = serializer.validated_data.get('config', {})

    try:
        if operation_type in dict(ExecuteOperationRequestSerializer.RAS_OPERATION_TYPES):
            batch_operation = OperationsService.enqueue_ras_operation(
                operation_type=operation_type,
                database_ids=database_ids,
                config=config,
                user=request.user,
            )
        elif operation_type in dict(ExecuteOperationRequestSerializer.CLI_OPERATION_TYPES):
            if not config.get("command"):
                raise ValueError("command is required for designer_cli")
            batch_operation = OperationsService.enqueue_cli_operation(
                operation_type=operation_type,
                database_ids=database_ids,
                config=config,
                user=request.user,
            )
        elif operation_type in dict(ExecuteOperationRequestSerializer.ODATA_OPERATION_TYPES):
            batch_operation = _enqueue_odata_operation(request.user, operation_type, database_ids, config)
        else:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_OPERATION',
                    'message': f'Unsupported operation_type: {operation_type}',
                }
            }, status=http_status.HTTP_400_BAD_REQUEST)

        logger.info(
            f"Operation {operation_type} queued",
            extra={
                'operation_id': str(batch_operation.id),
                'operation_type': operation_type,
                'database_count': len(database_ids),
                'created_by': request.user.username if request.user else 'anonymous',
            }
        )

        return Response({
            'operation_id': str(batch_operation.id),
            'status': batch_operation.status,
            'total_tasks': batch_operation.total_tasks,
            'message': f'{operation_type} queued for {len(database_ids)} database(s)',
        }, status=http_status.HTTP_202_ACCEPTED)

    except ValueError as e:
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': str(e)
            }
        }, status=400)

    except Exception as e:
        logger.error(f"Error executing RAS operation: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'Failed to queue operation'
            }
        }, status=500)


