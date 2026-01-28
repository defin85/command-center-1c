"""Infobase user endpoints."""

from __future__ import annotations

from .common import *  # noqa: F403

@extend_schema(
    tags=['v2'],
    summary='List infobase users',
    description='List manually mapped infobase users for a database.',
    parameters=[
        OpenApiParameter(name='database_id', type=str, required=True, description='Database ID'),
        OpenApiParameter(name='search', type=str, required=False, description='Search by username or display name'),
        OpenApiParameter(name='auth_type', type=str, required=False, description='Filter by auth type'),
        OpenApiParameter(name='is_service', type=bool, required=False, description='Filter by service account'),
        OpenApiParameter(name='has_user', type=bool, required=False, description='Filter by linked CC user'),
        OpenApiParameter(name='limit', type=int, required=False, description='Maximum results (default: 100, max: 1000)'),
        OpenApiParameter(name='offset', type=int, required=False, description='Pagination offset (default: 0)'),
    ],
    responses={
        200: InfobaseUserListResponseSerializer,
        400: OpenApiResponse(description='Invalid request'),
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
        404: OpenApiResponse(description='Database not found'),
    }
)
@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_infobase_users(request):
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

    qs = InfobaseUserMapping.objects.filter(database=db).select_related('user')
    if search:
        qs = qs.filter(
            Q(ib_username__icontains=search)
            | Q(ib_display_name__icontains=search)
            | Q(user__username__icontains=search)
        )
    if auth_type in {'local', 'ad', 'service', 'other'}:
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
    qs = qs.order_by('ib_username')[offset:offset + limit]
    data = InfobaseUserMappingSerializer(qs, many=True).data

    return Response({
        'users': data,
        'count': len(data),
        'total': total,
    })


@extend_schema(
    tags=['v2'],
    summary='Create infobase user mapping',
    description='Create a manual infobase user mapping for a database.',
    request=InfobaseUserMappingCreateSerializer,
    responses={
        201: InfobaseUserMappingSerializer,
        400: OpenApiResponse(description='Invalid request'),
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
        404: OpenApiResponse(description='Database not found'),
        409: OpenApiResponse(description='Duplicate entry'),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_infobase_user(request):
    serializer = InfobaseUserMappingCreateSerializer(data=request.data)
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

    ib_roles = data.get('ib_roles', [])
    ib_roles = [role.strip() for role in ib_roles if isinstance(role, str) and role.strip()]

    try:
        mapping = InfobaseUserMapping.objects.create(
            database=db,
            user=user,
            ib_username=data['ib_username'].strip(),
            ib_display_name=data.get('ib_display_name', '').strip(),
            ib_roles=ib_roles,
            ib_password=data.get('ib_password', ''),
            auth_type=data.get('auth_type', InfobaseUserMapping._meta.get_field('auth_type').default),
            is_service=bool(data.get('is_service', False)),
            notes=data.get('notes', '').strip(),
            created_by=request.user,
            updated_by=request.user,
        )
    except IntegrityError:
        return Response({
            'success': False,
            'error': {
                'code': 'DUPLICATE_ENTRY',
                'message': 'Infobase user already exists for this database'
            }
        }, status=409)

    log_admin_action(
        request,
        action='database.ib_user.create',
        outcome='success',
        target_type='database',
        target_id=str(db.id),
        metadata={'ib_username': mapping.ib_username},
    )

    return Response(InfobaseUserMappingSerializer(mapping).data, status=201)


@extend_schema(
    tags=['v2'],
    summary='Update infobase user mapping',
    description='Update a manual infobase user mapping.',
    request=InfobaseUserMappingUpdateSerializer,
    responses={
        200: InfobaseUserMappingSerializer,
        400: OpenApiResponse(description='Invalid request'),
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
        404: OpenApiResponse(description='Not found'),
        409: OpenApiResponse(description='Duplicate entry'),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def update_infobase_user(request):
    serializer = InfobaseUserMappingUpdateSerializer(data=request.data)
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
        mapping = InfobaseUserMapping.objects.select_related('database').get(id=data['id'])
    except InfobaseUserMapping.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'Infobase user not found'
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

    if 'ib_username' in data:
        mapping.ib_username = data['ib_username'].strip()
    if 'ib_display_name' in data:
        mapping.ib_display_name = data.get('ib_display_name', '').strip()
    if 'ib_roles' in data:
        ib_roles = data.get('ib_roles') or []
        mapping.ib_roles = [role.strip() for role in ib_roles if isinstance(role, str) and role.strip()]
    if 'auth_type' in data:
        mapping.auth_type = data['auth_type']
    if 'is_service' in data:
        mapping.is_service = bool(data['is_service'])
    if 'notes' in data:
        mapping.notes = data.get('notes', '').strip()

    mapping.updated_by = request.user
    try:
        mapping.save()
    except IntegrityError:
        return Response({
            'success': False,
            'error': {
                'code': 'DUPLICATE_ENTRY',
                'message': 'Infobase user already exists for this database'
            }
        }, status=409)

    log_admin_action(
        request,
        action='database.ib_user.update',
        outcome='success',
        target_type='database',
        target_id=str(mapping.database.id),
        metadata={'ib_username': mapping.ib_username},
    )

    return Response(InfobaseUserMappingSerializer(mapping).data)


@extend_schema(
    tags=['v2'],
    summary='Delete infobase user mapping',
    description='Delete a manual infobase user mapping.',
    request=InfobaseUserMappingDeleteSerializer,
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
def delete_infobase_user(request):
    serializer = InfobaseUserMappingDeleteSerializer(data=request.data)
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
        mapping = InfobaseUserMapping.objects.select_related('database').get(id=mapping_id)
    except InfobaseUserMapping.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'Infobase user not found'
            }
        }, status=404)

    ib_username = mapping.ib_username
    database_id = str(mapping.database.id)
    mapping.delete()

    log_admin_action(
        request,
        action='database.ib_user.delete',
        outcome='success',
        target_type='database',
        target_id=database_id,
        metadata={'ib_username': ib_username},
    )

    return Response({'message': 'Infobase user deleted'})


@extend_schema(
    tags=['v2'],
    summary='Set infobase user password',
    description='Set password for a manual infobase user mapping.',
    request=InfobaseUserPasswordSetSerializer,
    responses={
        200: InfobaseUserMappingSerializer,
        400: OpenApiResponse(description='Invalid request'),
        401: OpenApiResponse(description='Unauthorized'),
        403: OpenApiResponse(description='Forbidden'),
        404: OpenApiResponse(description='Not found'),
    }
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def set_infobase_user_password(request):
    serializer = InfobaseUserPasswordSetSerializer(data=request.data)
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
        mapping = InfobaseUserMapping.objects.select_related('database').get(id=data['id'])
    except InfobaseUserMapping.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'Infobase user not found'
            }
        }, status=404)

    mapping.ib_password = data['password']
    mapping.updated_by = request.user
    mapping.save(update_fields=['ib_password', 'updated_by', 'updated_at'])

    log_admin_action(
        request,
        action='database.ib_user.set_password',
        outcome='success',
        target_type='database',
        target_id=str(mapping.database.id),
        metadata={'ib_username': mapping.ib_username},
    )

    return Response(InfobaseUserMappingSerializer(mapping).data)


@extend_schema(
    tags=['v2'],
    summary='Reset infobase user password',
    description='Reset password for a manual infobase user mapping.',
    request=InfobaseUserPasswordResetSerializer,
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
def reset_infobase_user_password(request):
    serializer = InfobaseUserPasswordResetSerializer(data=request.data)
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
        mapping = InfobaseUserMapping.objects.select_related('database').get(id=mapping_id)
    except InfobaseUserMapping.DoesNotExist:
        return Response({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'Infobase user not found'
            }
        }, status=404)

    mapping.ib_password = ''
    mapping.updated_by = request.user
    mapping.save(update_fields=['ib_password', 'updated_by', 'updated_at'])

    log_admin_action(
        request,
        action='database.ib_user.reset_password',
        outcome='success',
        target_type='database',
        target_id=str(mapping.database.id),
        metadata={'ib_username': mapping.ib_username},
    )

    return Response({'message': 'Infobase user password reset'})



