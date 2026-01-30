"""Database core endpoints."""

from __future__ import annotations

from .common import *  # noqa: F403
from .common import _apply_filters, _is_staff, _parse_filters, _parse_sort, _permission_denied

@extend_schema(
    tags=['v2'],
    summary='List all databases',
    description='List all databases with optional filtering by cluster, status, health status, and search term. Supports pagination.',
    parameters=[
        OpenApiParameter(name='cluster_id', type=str, required=False, description='Filter by cluster UUID'),
        OpenApiParameter(name='status', type=str, required=False, description='Filter by status (active, inactive, error, maintenance)'),
        OpenApiParameter(name='health_status', type=str, required=False, description='Filter by health status (ok, degraded, down, unknown)'),
        OpenApiParameter(name='search', type=str, required=False, description='Search by name or description'),
        OpenApiParameter(name='filters', type=str, required=False, description='JSON object with filter conditions'),
        OpenApiParameter(name='sort', type=str, required=False, description='JSON object with sort configuration'),
        OpenApiParameter(name='limit', type=int, required=False, description='Maximum results (default: 100, max: 1000)'),
        OpenApiParameter(name='offset', type=int, required=False, description='Pagination offset (default: 0)'),
    ],
    responses={
        200: DatabaseListResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_databases(request):
    """
    GET /api/v2/databases/list-databases/

    List all databases with optional filtering.

    Query Parameters:
        - cluster_id: Filter by cluster UUID
        - status: Filter by status (active, inactive, error, maintenance)
        - health_status: Filter by health status (ok, degraded, down, unknown)
        - search: Search by name or description
        - limit: Maximum results (default: 100)
        - offset: Pagination offset (default: 0)

    Response:
        {
            "databases": [...],
            "count": 100,
            "total": 700
        }
    """
    if not request.user.has_perm(perms.PERM_DATABASES_VIEW_DATABASE):
        return _permission_denied("You do not have permission to view databases.")

    cluster_id = request.query_params.get('cluster_id')
    status = request.query_params.get('status')
    health_status = request.query_params.get('health_status')
    search = request.query_params.get('search')
    raw_filters = request.query_params.get('filters')
    raw_sort = request.query_params.get('sort')

    # Safely parse integer parameters with validation
    try:
        limit = int(request.query_params.get('limit', 100))
        limit = max(1, min(limit, 1000))  # Clamp to [1, 1000]
    except (ValueError, TypeError):
        limit = 100

    try:
        offset = int(request.query_params.get('offset', 0))
        offset = max(0, offset)
    except (ValueError, TypeError):
        offset = 0

    raw_tenant_header = request.META.get("HTTP_X_CC1C_TENANT_ID")
    has_tenant_header = raw_tenant_header is not None and str(raw_tenant_header).strip() != ""

    if _is_staff(request.user) and not has_tenant_header:
        qs = Database.all_objects.all()
    else:
        tenant_id = getattr(request, "tenant_id", None)
        if not tenant_id:
            return _permission_denied("Tenant context is missing.")
        qs = Database.all_objects.filter(tenant_id=str(tenant_id))

    # Apply filters
    if cluster_id:
        qs = qs.filter(cluster_id=cluster_id)
    if status:
        qs = qs.filter(status=status)
    if health_status:
        qs = qs.filter(last_check_status=health_status)

    filters_payload, filters_error = _parse_filters(raw_filters)
    if filters_error:
        return Response(
            {"success": False, "error": filters_error},
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    if filters_payload:
        qs, apply_error = _apply_filters(qs, filters_payload)
        if apply_error:
            return Response(
                {"success": False, "error": apply_error},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

    sort_payload, sort_error = _parse_sort(raw_sort)
    if sort_error:
        return Response(
            {"success": False, "error": sort_error},
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    if sort_payload:
        sort_key = sort_payload.get('key')
        sort_order = sort_payload.get('order', 'asc')
        if sort_key not in DATABASE_SORT_FIELDS:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "UNKNOWN_SORT",
                        "message": f"Unknown sort key: {sort_key}",
                    },
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        order_field = DATABASE_SORT_FIELDS[sort_key]
        if sort_order == 'desc':
            order_field = f"-{order_field}"
        qs = qs.order_by(order_field)
    if search:
        qs = qs.filter(
            Q(name__icontains=search) | Q(description__icontains=search) | Q(host__icontains=search)
        )

    if not _is_staff(request.user):
        qs = PermissionService.filter_accessible_databases(
            request.user,
            qs,
            PermissionLevel.VIEW,
        )

    # Get total count before pagination
    total = qs.count()

    # Apply pagination
    qs = qs[offset:offset + limit]

    serializer = DatabaseSerializer(qs, many=True)

    return Response({
        'databases': serializer.data,
        'count': len(serializer.data),
        'total': total,
    })


@extend_schema(
    tags=['v2'],
    summary='Get database details',
    description='Get detailed information about a specific database including cluster info.',
    parameters=[
        OpenApiParameter(name='database_id', type=str, required=True, description='Database UUID'),
    ],
    responses={
        200: DatabaseDetailResponseSerializer,
        400: DatabaseErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: DatabaseErrorResponseSerializer,
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_database(request):
    """
    GET /api/v2/databases/get-database/?database_id=X

    Get detailed information about a specific database.

    Query Parameters:
        - database_id: Database ID (required)

    Response:
        {
            "database": {...},
            "cluster": {...}
        }
    """
    database_id = request.query_params.get('database_id')

    if not database_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'database_id is required'
            }
        }, status=400)

    try:
        db = Database.objects.select_related('cluster').get(id=database_id)
    except Database.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'DATABASE_NOT_FOUND',
                'message': 'Database not found'
            }
        }, status=404)

    if not request.user.has_perm(perms.PERM_DATABASES_VIEW_DATABASE, db):
        return _permission_denied("You do not have permission to access this database.")

    serializer = DatabaseSerializer(db)

    # Include cluster info if available
    cluster_info = None
    if db.cluster:
        cluster_info = ClusterSerializer(db.cluster).data

    return Response({
        'database': serializer.data,
        'cluster': cluster_info,
    })


@extend_schema(
    tags=['v2'],
    summary='Get database extensions snapshot',
    description='Get latest known extensions snapshot for a database (if any).',
    parameters=[
        OpenApiParameter(name='database_id', type=str, required=True, description='Database UUID'),
    ],
    responses={
        200: DatabaseExtensionsSnapshotResponseSerializer,
        400: DatabaseErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
        404: DatabaseErrorResponseSerializer,
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_extensions_snapshot(request):
    """
    GET /api/v2/databases/get-extensions-snapshot/?database_id=X

    Returns latest known extensions snapshot for the database.

    Response (200):
        {
            "database_id": "...",
            "snapshot": {...},
            "updated_at": "...",
            "source_operation_id": "..."
        }
    """
    database_id = request.query_params.get('database_id')

    if not database_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'database_id is required'
            }
        }, status=400)

    try:
        db = Database.objects.get(id=database_id)
    except Database.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'DATABASE_NOT_FOUND',
                'message': 'Database not found'
            }
        }, status=404)

    if not request.user.has_perm(perms.PERM_DATABASES_VIEW_DATABASE, db):
        return _permission_denied("You do not have permission to access this database.")

    snapshot = {}
    updated_at = None
    source_operation_id = ""
    try:
        snapshot_obj = db.extensions_snapshot
        snapshot = snapshot_obj.snapshot or {}
        if snapshot:
            snapshot = normalize_extensions_snapshot(snapshot)
            try:
                from apps.mappings.extensions_inventory import build_canonical_extensions_inventory
                from apps.mappings.models import TenantMappingSpec

                spec = TenantMappingSpec.objects.filter(
                    tenant_id=db.tenant_id,
                    entity_kind=TenantMappingSpec.ENTITY_EXTENSIONS_INVENTORY,
                    status=TenantMappingSpec.STATUS_PUBLISHED,
                ).values_list("spec", flat=True).first()
                spec_dict = spec if isinstance(spec, dict) else {}
                canonical = build_canonical_extensions_inventory(snapshot, spec_dict)
                snapshot["extensions"] = canonical.get("extensions", [])
            except Exception:
                pass
        updated_at = snapshot_obj.updated_at
        source_operation_id = snapshot_obj.source_operation_id or ""
    except DatabaseExtensionsSnapshot.DoesNotExist:
        pass

    return Response(
        {
            "database_id": str(db.id),
            "snapshot": snapshot,
            "updated_at": updated_at,
            "source_operation_id": source_operation_id,
        }
    )


@extend_schema(
    tags=['v2'],
    summary='Update database credentials',
    description='Set or reset database OData credentials.',
    request=DatabaseCredentialsUpdateRequestSerializer,
    responses={
        200: DatabaseCredentialsUpdateResponseSerializer,
        400: DatabaseErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: DatabaseErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_database_credentials(request):
    """
    POST /api/v2/databases/update-credentials/

    Update or reset database credentials.

    Request Body:
        {
            "database_id": "db-123",
            "username": "odata_user",   // optional
            "password": "secret",       // optional
            "reset": false              // optional, default: false
        }

    Response (200):
        {
            "database": {...},
            "message": "Database credentials updated"
        }
    """
    serializer = DatabaseCredentialsUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'Invalid credentials payload',
                'details': serializer.errors
            }
        }, status=400)

    data = serializer.validated_data
    database_id = data['database_id']

    try:
        db = Database.objects.get(id=database_id)
    except Database.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'DATABASE_NOT_FOUND',
                'message': 'Database not found'
            }
        }, status=404)

    if not request.user.has_perm(perms.PERM_DATABASES_MANAGE_DATABASE, db):
        return _permission_denied("You do not have permission to update database credentials.")

    reset = data.get('reset', False)
    updated_fields = []

    if reset:
        db.username = ''
        db.password = ''
        updated_fields.extend(['username', 'password'])
    else:
        username_provided = 'username' in data
        password_provided = 'password' in data

        if not username_provided and not password_provided:
            return Response({
                'success': False,
                'error': {
                    'code': 'MISSING_PARAMETER',
                    'message': 'username or password is required unless reset=true'
                }
            }, status=400)

        if username_provided:
            if data['username'] == '':
                return Response({
                    'success': False,
                    'error': {
                        'code': 'INVALID_PARAMETER',
                        'message': 'username cannot be empty (use reset=true to clear)'
                    }
                }, status=400)
            db.username = data['username']
            updated_fields.append('username')

        if password_provided:
            if data['password'] == '':
                return Response({
                    'success': False,
                    'error': {
                        'code': 'INVALID_PARAMETER',
                        'message': 'password cannot be empty (use reset=true to clear)'
                    }
                }, status=400)
            db.password = data['password']
            updated_fields.append('password')

    db.save(update_fields=[*updated_fields, 'updated_at'])

    log_admin_action(
        request,
        action='database.credentials.update',
        outcome='success',
        target_type='database',
        target_id=str(db.id),
        metadata={
            'reset': reset,
            'updated_fields': updated_fields,
            'configured': bool(db.password),
        },
    )

    return Response({
        'database': DatabaseSerializer(db).data,
        'message': 'Database credentials updated'
    })


@extend_schema(
    tags=['v2'],
    summary='Health check database',
    description='Queue OData health check for a specific database.',
    request=HealthCheckRequestSerializer,
    responses={
        202: HealthCheckEnqueueResponseSerializer,
        400: DatabaseErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: DatabaseErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def health_check(request):
    """
    POST /api/v2/databases/health-check/

    Queue health check for a specific database.

    Request Body:
        {
            "database_id": "string"
        }

    Response (202 Accepted):
        {
            "operation_id": "uuid",
            "status": "queued",
            "total_tasks": 1,
            "message": "health_check queued for 1 database(s)"
        }
    """
    database_id = request.data.get('database_id')

    if not database_id:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'database_id is required'
            }
        }, status=400)

    try:
        db = Database.objects.get(id=database_id)
    except Database.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'DATABASE_NOT_FOUND',
                'message': 'Database not found'
            }
        }, status=404)

    if not request.user.has_perm(perms.PERM_DATABASES_OPERATE_DATABASE, db):
        return _permission_denied("You do not have permission to run health check.")

    enqueue_result = OperationsService.enqueue_health_check(
        database_ids=[database_id],
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
        'total_tasks': enqueue_result.metadata.get('database_count', 1),
        'message': 'health_check queued for 1 database(s)',
    }, status=http_status.HTTP_202_ACCEPTED)
