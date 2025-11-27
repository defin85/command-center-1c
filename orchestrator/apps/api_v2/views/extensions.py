"""
Extension management endpoints for API v2.

Provides action-based endpoints for extension installation management.
"""

import logging

from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.databases.models import Database, ExtensionInstallation
from apps.databases.serializers import ExtensionInstallationSerializer

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_extensions(request):
    """
    GET /api/v2/extensions/list-extensions/

    List all extension installations with optional filtering.

    Query Parameters:
        - database_id: Filter by database ID
        - status: Filter by status (pending, in_progress, completed, failed)
        - extension_name: Filter by extension name
        - limit: Maximum results (default: 50)
        - offset: Pagination offset (default: 0)

    Response:
        {
            "extensions": [...],
            "count": 50,
            "total": 200,
            "summary": {
                "pending": 10,
                "in_progress": 5,
                "completed": 180,
                "failed": 5
            }
        }
    """
    database_id = request.query_params.get('database_id')
    status = request.query_params.get('status')
    extension_name = request.query_params.get('extension_name')

    # Safely parse integer parameters with validation
    try:
        limit = int(request.query_params.get('limit', 50))
        limit = max(1, min(limit, 1000))  # Clamp to [1, 1000]
    except (ValueError, TypeError):
        limit = 50

    try:
        offset = int(request.query_params.get('offset', 0))
        offset = max(0, offset)
    except (ValueError, TypeError):
        offset = 0

    qs = ExtensionInstallation.objects.select_related('database')

    if database_id:
        qs = qs.filter(database_id=database_id)
    if status:
        qs = qs.filter(status=status)
    if extension_name:
        qs = qs.filter(extension_name=extension_name)

    qs = qs.order_by('-created_at')

    total = qs.count()

    # Calculate summary
    summary = {
        'pending': qs.filter(status=ExtensionInstallation.STATUS_PENDING).count(),
        'in_progress': qs.filter(status=ExtensionInstallation.STATUS_IN_PROGRESS).count(),
        'completed': qs.filter(status=ExtensionInstallation.STATUS_COMPLETED).count(),
        'failed': qs.filter(status=ExtensionInstallation.STATUS_FAILED).count(),
    }

    # Apply pagination
    qs = qs[offset:offset + limit]

    serializer = ExtensionInstallationSerializer(qs, many=True)

    return Response({
        'extensions': serializer.data,
        'count': len(serializer.data),
        'total': total,
        'summary': summary,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_install_status(request):
    """
    GET /api/v2/extensions/get-install-status/?database_id=X

    Get extension installation status for a specific database.

    Query Parameters:
        - database_id: Database ID (required)
        - extension_name: Extension name (default: ODataAutoConfig)

    Response:
        {
            "database_id": "string",
            "database_name": "string",
            "extension_name": "ODataAutoConfig",
            "status": "completed|failed|pending|in_progress|none",
            "installation": {...},  // Latest installation record if exists
            "history": [...]  // Installation history
        }
    """
    database_id = request.query_params.get('database_id')
    extension_name = request.query_params.get('extension_name', 'ODataAutoConfig')

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

    # Get installation records
    installations = ExtensionInstallation.objects.filter(
        database=db,
        extension_name=extension_name
    ).order_by('-created_at')

    latest = installations.first()

    # Determine current status
    if latest:
        current_status = latest.status
        installation_data = ExtensionInstallationSerializer(latest).data
    else:
        current_status = 'none'
        installation_data = None

    # Get history (last 10 installations)
    history = ExtensionInstallationSerializer(installations[:10], many=True).data

    return Response({
        'database_id': database_id,
        'database_name': db.name,
        'extension_name': extension_name,
        'status': current_status,
        'installation': installation_data,
        'history': history,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def retry_installation(request):
    """
    POST /api/v2/extensions/retry-installation/

    Retry extension installation for a specific database.

    Request Body:
        {
            "database_id": "string",
            "extension_name": "ODataAutoConfig"  // optional
        }

    Response:
        {
            "database_id": "string",
            "installation_id": "uuid",
            "status": "pending",
            "message": "Installation retry scheduled"
        }
    """
    database_id = request.data.get('database_id')
    extension_name = request.data.get('extension_name', 'ODataAutoConfig')

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

    # Use select_for_update() in transaction to prevent race condition (TOCTOU)
    from django.db import transaction

    with transaction.atomic():
        # Check if there's already an active installation (with row-level lock)
        active_installation = ExtensionInstallation.objects.select_for_update().filter(
            database=db,
            extension_name=extension_name,
            status__in=[
                ExtensionInstallation.STATUS_PENDING,
                ExtensionInstallation.STATUS_IN_PROGRESS
            ]
        ).first()

        if active_installation:
            return Response({
                'success': False,
                'error': {
                    'code': 'INSTALLATION_IN_PROGRESS',
                    'message': 'Installation already in progress',
                    'database_id': database_id,
                    'installation_id': str(active_installation.id),
                    'status': active_installation.status
                }
            }, status=400)

        # Get previous installation for retry count
        previous = ExtensionInstallation.objects.filter(
            database=db,
            extension_name=extension_name
        ).order_by('-created_at').first()

        retry_count = (previous.retry_count + 1) if previous else 0

        # Create new installation record (inside transaction)
        installation = ExtensionInstallation.objects.create(
            database=db,
            extension_name=extension_name,
            status=ExtensionInstallation.STATUS_PENDING,
            retry_count=retry_count,
        )

    # Trigger async installation via Celery
    try:
        from apps.databases.tasks import queue_extension_installation
        # Use existing queue_extension_installation task
        task = queue_extension_installation.delay(
            [str(database_id)],
            {'name': extension_name, 'path': f'C:\\Extensions\\{extension_name}.cfe'}
        )

        # Audit logging
        logger.info(
            f"Extension installation retry scheduled",
            extra={
                'installation_id': str(installation.id),
                'database_id': database_id,
                'extension_name': extension_name,
                'retry_count': retry_count,
                'requested_by': request.user.username if request.user else 'anonymous',
                'celery_task_id': task.id,
            }
        )

        return Response({
            'database_id': database_id,
            'installation_id': str(installation.id),
            'status': 'pending',
            'celery_task_id': task.id,
            'message': 'Installation retry scheduled',
        })
    except ImportError as e:
        logger.error(f"Celery task not found: {e}")
        logger.warning("Extension installation task unavailable - using fallback")

        # Audit logging for fallback
        logger.info(
            f"Extension installation queued (Celery unavailable)",
            extra={
                'installation_id': str(installation.id),
                'database_id': database_id,
                'extension_name': extension_name,
                'retry_count': retry_count,
                'requested_by': request.user.username if request.user else 'anonymous',
            }
        )

        return Response({
            'database_id': database_id,
            'installation_id': str(installation.id),
            'status': 'pending',
            'message': 'Installation queued (async worker unavailable)',
        })
    except Exception as e:
        logger.warning(f"Celery unavailable for extension install: {e}")
        logger.warning("Extension installation will be processed by background worker")

        # Audit logging for fallback
        logger.info(
            f"Extension installation queued (Celery unavailable)",
            extra={
                'installation_id': str(installation.id),
                'database_id': database_id,
                'extension_name': extension_name,
                'retry_count': retry_count,
                'requested_by': request.user.username if request.user else 'anonymous',
            }
        )

        return Response({
            'database_id': database_id,
            'installation_id': str(installation.id),
            'status': 'pending',
            'message': 'Installation queued (async worker unavailable)',
        })
