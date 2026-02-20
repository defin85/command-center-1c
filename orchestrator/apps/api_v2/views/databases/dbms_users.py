# ruff: noqa: F405
"""DBMS user endpoints."""

from __future__ import annotations

from .common import *  # noqa: F403

@extend_schema(
    tags=['v2'],
    summary='List DBMS users',
    description='List manually mapped DBMS users for offline ibcmd connection for a database.',
    parameters=[
        OpenApiParameter(name='database_id', type=str, required=True, description='Database ID'),
        OpenApiParameter(name='search', type=str, required=False, description='Search by DB username or linked CC user'),
        OpenApiParameter(name='auth_type', type=str, required=False, description='Filter by auth type'),
        OpenApiParameter(name='is_service', type=bool, required=False, description='Filter by service account'),
        OpenApiParameter(name='has_user', type=bool, required=False, description='Filter by linked CC user'),
        OpenApiParameter(name='limit', type=int, required=False, description='Maximum results (default: 100, max: 1000)'),
        OpenApiParameter(name='offset', type=int, required=False, description='Pagination offset (default: 0)'),
    ],
    responses={
        200: DbmsUserListResponseSerializer,
        400: OpenApiResponse(description='Invalid request'),
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
        404: OpenApiResponse(description='Database not found'),
    }
)
@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_dbms_users(request):
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

    search = (request.query_params.get('search') or '').strip()
    auth_type = (request.query_params.get('auth_type') or '').strip()
    is_service = (request.query_params.get('is_service') or '').strip().lower()
    has_user = (request.query_params.get('has_user') or '').strip().lower()
    try:
        limit = int(request.query_params.get('limit', 100))
        limit = max(1, min(limit, 1000))
    except (TypeError, ValueError):
        limit = 100
    try:
        offset = int(request.query_params.get('offset', 0))
        offset = max(0, offset)
    except (TypeError, ValueError):
        offset = 0

    qs = DbmsUserMapping.objects.filter(database=db).select_related('user')
    if search:
        search_user_id = None
        if search.isdigit():
            try:
                search_user_id = int(search)
            except ValueError:
                search_user_id = None

        search_q = Q(db_username__icontains=search) | Q(user__username__icontains=search)
        if search_user_id is not None:
            search_q = search_q | Q(user__id=search_user_id)

        qs = qs.filter(search_q)
    if auth_type in {'local', 'service', 'other'}:
        qs = qs.filter(auth_type=auth_type)
    if is_service in {'true', '1', 'yes'}:
        qs = qs.filter(is_service=True)
    elif is_service in {'false', '0', 'no'}:
        qs = qs.filter(is_service=False)
    if has_user in {'true', '1', 'yes'}:
        qs = qs.filter(user__isnull=False)
    elif has_user in {'false', '0', 'no'}:
        qs = qs.filter(user__isnull=True)

    total = qs.count()
    qs = qs.order_by('db_username')[offset:offset + limit]
    data = DbmsUserMappingSerializer(qs, many=True).data

    return Response({
        'users': data,
        'count': len(data),
        'total': total,
    })


@extend_schema(
    tags=['v2'],
    summary='Create DBMS user mapping',
    description='Create a manual DBMS user mapping for a database (offline ibcmd connection).',
    request=DbmsUserMappingCreateSerializer,
    responses={
        201: DbmsUserMappingSerializer,
        400: OpenApiResponse(description='Invalid request'),
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
        404: OpenApiResponse(description='Database not found'),
        409: OpenApiResponse(description='Duplicate entry'),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_dbms_user(request):
    serializer = DbmsUserMappingCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'Invalid payload',
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

    user = None
    user_id = data.get('user_id')
    if user_id is not None:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': {
                    'code': 'USER_NOT_FOUND',
                    'message': 'User not found'
                }
            }, status=400)

    is_service = bool(data.get('is_service', False))
    if is_service and user is not None:
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'Service DBMS mapping must not be linked to a CC user'
            }
        }, status=400)
    if not is_service and user is None:
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'user_id is required unless is_service=true'
            }
        }, status=400)

    try:
        # Keep DB errors isolated (esp. under transactional test runners).
        with transaction.atomic():
            mapping = DbmsUserMapping.objects.create(
                database=db,
                user=user,
                db_username=data['db_username'].strip(),
                db_password=data.get('db_password', ''),
                auth_type=data.get('auth_type', DbmsUserMapping._meta.get_field('auth_type').default),
                is_service=is_service,
                notes=data.get('notes', '').strip(),
                created_by=request.user,
                updated_by=request.user,
            )
    except IntegrityError:
        return Response({
            'success': False,
            'error': {
                'code': 'DUPLICATE_ENTRY',
                'message': 'DBMS user mapping already exists for this database'
            }
        }, status=409)

    log_admin_action(
        request,
        action='database.dbms_user.create',
        outcome='success',
        target_type='database',
        target_id=str(db.id),
        metadata={'db_username': mapping.db_username, 'is_service': mapping.is_service},
    )

    return Response(DbmsUserMappingSerializer(mapping).data, status=201)


@extend_schema(
    tags=['v2'],
    summary='Update DBMS user mapping',
    description='Update a manual DBMS user mapping.',
    request=DbmsUserMappingUpdateSerializer,
    responses={
        200: DbmsUserMappingSerializer,
        400: OpenApiResponse(description='Invalid request'),
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
        404: OpenApiResponse(description='Not found'),
        409: OpenApiResponse(description='Duplicate entry'),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def update_dbms_user(request):
    serializer = DbmsUserMappingUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'Invalid payload',
                'details': serializer.errors
            }
        }, status=400)

    data = serializer.validated_data
    try:
        mapping = DbmsUserMapping.objects.select_related('database').get(id=data['id'])
    except DbmsUserMapping.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'DBMS user mapping not found'
            }
        }, status=404)

    if 'user_id' in data:
        user_id = data.get('user_id')
        if user_id is None:
            mapping.user = None
        else:
            try:
                mapping.user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': {
                        'code': 'USER_NOT_FOUND',
                        'message': 'User not found'
                    }
                }, status=400)

    if 'db_username' in data:
        mapping.db_username = data['db_username'].strip()
    if 'auth_type' in data:
        mapping.auth_type = data['auth_type']
    if 'is_service' in data:
        mapping.is_service = bool(data['is_service'])
        if mapping.is_service:
            mapping.user = None
    if 'notes' in data:
        mapping.notes = data.get('notes', '').strip()

    if not mapping.is_service and mapping.user_id is None:
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'user_id is required unless is_service=true'
            }
        }, status=400)

    mapping.updated_by = request.user
    try:
        # Keep DB errors isolated (esp. under transactional test runners).
        with transaction.atomic():
            mapping.save()
    except IntegrityError:
        return Response({
            'success': False,
            'error': {
                'code': 'DUPLICATE_ENTRY',
                'message': 'DBMS user mapping already exists for this database'
            }
        }, status=409)

    log_admin_action(
        request,
        action='database.dbms_user.update',
        outcome='success',
        target_type='database',
        target_id=str(mapping.database.id),
        metadata={'db_username': mapping.db_username, 'is_service': mapping.is_service},
    )

    return Response(DbmsUserMappingSerializer(mapping).data)


@extend_schema(
    tags=['v2'],
    summary='Delete DBMS user mapping',
    description='Delete a manual DBMS user mapping.',
    request=DbmsUserMappingDeleteSerializer,
    responses={
        200: OpenApiResponse(description='Deleted'),
        400: OpenApiResponse(description='Invalid request'),
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
        404: OpenApiResponse(description='Not found'),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def delete_dbms_user(request):
    serializer = DbmsUserMappingDeleteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'Invalid payload',
                'details': serializer.errors
            }
        }, status=400)

    mapping_id = serializer.validated_data['id']
    try:
        mapping = DbmsUserMapping.objects.select_related('database').get(id=mapping_id)
    except DbmsUserMapping.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'DBMS user mapping not found'
            }
        }, status=404)

    db_username = mapping.db_username
    database_id = str(mapping.database.id)
    mapping.delete()

    log_admin_action(
        request,
        action='database.dbms_user.delete',
        outcome='success',
        target_type='database',
        target_id=database_id,
        metadata={'db_username': db_username},
    )

    return Response({'message': 'DBMS user mapping deleted'})


@extend_schema(
    tags=['v2'],
    summary='Set DBMS user password',
    description='Set password for a manual DBMS user mapping.',
    request=DbmsUserPasswordSetSerializer,
    responses={
        200: DbmsUserMappingSerializer,
        400: OpenApiResponse(description='Invalid request'),
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
        404: OpenApiResponse(description='Not found'),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def set_dbms_user_password(request):
    serializer = DbmsUserPasswordSetSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'Invalid payload',
                'details': serializer.errors
            }
        }, status=400)

    data = serializer.validated_data
    try:
        mapping = DbmsUserMapping.objects.select_related('database').get(id=data['id'])
    except DbmsUserMapping.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'DBMS user mapping not found'
            }
        }, status=404)

    mapping.db_password = data['password']
    mapping.updated_by = request.user
    mapping.save(update_fields=['db_password', 'updated_by', 'updated_at'])

    log_admin_action(
        request,
        action='database.dbms_user.set_password',
        outcome='success',
        target_type='database',
        target_id=str(mapping.database.id),
        metadata={'db_username': mapping.db_username},
    )

    return Response(DbmsUserMappingSerializer(mapping).data)


@extend_schema(
    tags=['v2'],
    summary='Reset DBMS user password',
    description='Reset password for a manual DBMS user mapping.',
    request=DbmsUserPasswordResetSerializer,
    responses={
        200: OpenApiResponse(description='Password reset'),
        400: OpenApiResponse(description='Invalid request'),
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
        404: OpenApiResponse(description='Not found'),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def reset_dbms_user_password(request):
    serializer = DbmsUserPasswordResetSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'Invalid payload',
                'details': serializer.errors
            }
        }, status=400)

    mapping_id = serializer.validated_data['id']
    try:
        mapping = DbmsUserMapping.objects.select_related('database').get(id=mapping_id)
    except DbmsUserMapping.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'DBMS user mapping not found'
            }
        }, status=404)

    mapping.db_password = ''
    mapping.updated_by = request.user
    mapping.save(update_fields=['db_password', 'updated_by', 'updated_at'])

    log_admin_action(
        request,
        action='database.dbms_user.reset_password',
        outcome='success',
        target_type='database',
        target_id=str(mapping.database.id),
        metadata={'db_username': mapping.db_username},
    )

    return Response({'message': 'DBMS user password reset'})



