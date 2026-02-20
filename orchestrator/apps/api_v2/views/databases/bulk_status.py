# ruff: noqa: F405
"""Database bulk/status endpoints."""

from __future__ import annotations

from .common import *  # noqa: F403
from .common import _is_staff, _permission_denied

@extend_schema(
    tags=['v2'],
    summary='Bulk health check databases',
    description='Queue health check on multiple databases. Provide either database_ids or cluster_id.',
    request=BulkHealthCheckRequestSerializer,
    responses={
        202: HealthCheckEnqueueResponseSerializer,
        400: DatabaseErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_health_check(request):
    """
    POST /api/v2/databases/bulk-health-check/

    Queue health check on multiple databases.

    Request Body:
        {
            "database_ids": ["id1", "id2", ...],
            "cluster_id": "optional-cluster-id"
        }

    Response (202 Accepted):
        {
            "operation_id": "uuid",
            "status": "queued",
            "total_tasks": 10,
            "message": "health_check queued for 10 database(s)"
        }
    """
    database_ids = request.data.get('database_ids', [])
    cluster_id = request.data.get('cluster_id')

    if not request.user.has_perm(perms.PERM_DATABASES_OPERATE_DATABASE):
        return _permission_denied("You do not have permission to run health check.")

    # Build queryset
    if database_ids:
        qs = Database.objects.filter(id__in=database_ids)
    elif cluster_id:
        qs = Database.objects.filter(cluster_id=cluster_id)
    else:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'Either database_ids or cluster_id is required'
            }
        }, status=400)

    databases = list(qs)
    if not databases:
        return Response({
            'success': False,
            'error': {
                'code': 'DATABASES_NOT_FOUND',
                'message': 'No databases found for the request'
            }
        }, status=400)

    if not _is_staff(request.user):
        all_allowed, denied = PermissionService.check_bulk_permission(
            request.user,
            [str(db.id) for db in databases],
            PermissionLevel.OPERATE,
        )
        if not all_allowed:
            denied_str = ', '.join(denied[:5])
            message = f"Access denied for databases: {denied_str}"
            if len(denied) > 5:
                message += f" and {len(denied) - 5} more"
            return Response({
                'success': False,
                'error': {
                    'code': 'PERMISSION_DENIED',
                    'message': message,
                }
            }, status=403)

    enqueue_result = OperationsService.enqueue_health_check(
        database_ids=[str(db.id) for db in databases],
        created_by=request.user.username if request.user else "system",
    )
    if not enqueue_result.success:
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': enqueue_result.error or 'Failed to queue health check'
            }
        }, status=500)

    return Response({
        'operation_id': enqueue_result.operation_id,
        'status': enqueue_result.status,
        'total_tasks': enqueue_result.metadata.get('database_count', len(databases)),
        'message': f'health_check queued for {len(databases)} database(s)',
    }, status=http_status.HTTP_202_ACCEPTED)


@extend_schema(
    tags=['v2'],
    summary='Set database status',
    description='Set status for one or more databases (staff-only). Intended for operator control (exclude from ops, maintenance windows, etc.).',
    request=SetDatabaseStatusRequestSerializer,
    responses={
        200: SetDatabaseStatusResponseSerializer,
        400: DatabaseErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def set_status(request):
    """
    POST /api/v2/databases/set-status/

    Set status for one or more databases.

    Request body:
        {
          "database_ids": ["id1", "id2"],
          "status": "maintenance",
          "reason": "Planned maintenance window"  // optional
        }
    """
    serializer = SetDatabaseStatusRequestSerializer(data=request.data or {})
    serializer.is_valid(raise_exception=True)

    database_ids = [str(x).strip() for x in serializer.validated_data['database_ids']]
    new_status = serializer.validated_data['status']
    reason = serializer.validated_data.get('reason', '')

    existing_ids = set(Database.objects.filter(id__in=database_ids).values_list('id', flat=True))
    not_found = [db_id for db_id in database_ids if db_id not in existing_ids]

    updated = Database.objects.filter(id__in=list(existing_ids)).update(status=new_status)

    log_admin_action(
        request,
        action="databases.set_status",
        outcome="success",
        target_type="database",
        target_id="bulk" if len(database_ids) > 1 else (database_ids[0] if database_ids else ""),
        metadata={
            "status": new_status,
            "reason": reason,
            "database_ids": database_ids[:200],
            "not_found": not_found[:200],
            "updated": updated,
        },
    )

    message = f"Status set to '{new_status}' for {updated} database(s)"
    if not_found:
        message += f" ({len(not_found)} not found)"

    return Response(
        {
            "updated": updated,
            "not_found": not_found,
            "status": new_status,
            "message": message,
        }
    )


# =============================================================================
# SSE Streaming (Databases)
# =============================================================================


