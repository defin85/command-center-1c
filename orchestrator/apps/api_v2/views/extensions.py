"""
Extension management endpoints for API v2.

Provides action-based endpoints for extension installation management.
"""

import logging
import uuid as uuid_lib

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Max, Q
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.databases.models import Database, ExtensionInstallation
from apps.databases.serializers import ExtensionInstallationSerializer
from apps.api_v2.views.clusters import ErrorResponseSerializer

logger = logging.getLogger(__name__)


# =============================================================================
# Response Serializers for OpenAPI documentation
# =============================================================================

class ExtensionSummarySerializer(serializers.Serializer):
    """Summary statistics for extensions."""
    pending = serializers.IntegerField(help_text="Number of pending installations")
    in_progress = serializers.IntegerField(help_text="Number of installations in progress")
    completed = serializers.IntegerField(help_text="Number of completed installations")
    failed = serializers.IntegerField(help_text="Number of failed installations")


class ExtensionListResponseSerializer(serializers.Serializer):
    """Response for list_extensions endpoint."""
    extensions = ExtensionInstallationSerializer(many=True)
    count = serializers.IntegerField(help_text="Number of extensions returned")
    total = serializers.IntegerField(help_text="Total number of extensions matching filters")
    summary = ExtensionSummarySerializer()


class InstallStatusResponseSerializer(serializers.Serializer):
    """Response for get_install_status endpoint."""
    database_id = serializers.CharField(help_text="Database UUID")
    database_name = serializers.CharField(help_text="Database name")
    extension_name = serializers.CharField(help_text="Extension name")
    status = serializers.CharField(help_text="Current status: completed, failed, pending, in_progress, none")
    installation = ExtensionInstallationSerializer(required=False, allow_null=True)
    history = ExtensionInstallationSerializer(many=True)


class InstallProgressStatsSerializer(serializers.Serializer):
    """Progress statistics for batch installation."""
    total = serializers.IntegerField(help_text="Total number of installations")
    pending = serializers.IntegerField(help_text="Number of pending installations")
    in_progress = serializers.IntegerField(help_text="Number of installations in progress")
    completed = serializers.IntegerField(help_text="Number of completed installations")
    failed = serializers.IntegerField(help_text="Number of failed installations")
    percent_complete = serializers.FloatField(help_text="Percentage of completed installations")


class InstallProgressDatabaseSerializer(serializers.Serializer):
    """Database status in installation progress."""
    database_id = serializers.CharField(help_text="Database UUID")
    database_name = serializers.CharField(help_text="Database name")
    status = serializers.CharField(help_text="Installation status")
    error_message = serializers.CharField(required=False, allow_null=True)
    updated_at = serializers.CharField(required=False, allow_null=True)


class InstallProgressResponseSerializer(serializers.Serializer):
    """Response for get_install_progress endpoint."""
    progress = InstallProgressStatsSerializer()
    databases = InstallProgressDatabaseSerializer(many=True)


class BatchInstallItemSerializer(serializers.Serializer):
    """Single item in batch installation result."""
    database_id = serializers.CharField(help_text="Database UUID")
    installation_id = serializers.CharField(required=False, help_text="Installation UUID (if queued)")
    status = serializers.CharField(help_text="Status: pending or skipped")
    reason = serializers.CharField(required=False, help_text="Skip reason (if skipped)")
    existing_installation_id = serializers.CharField(required=False, help_text="Existing installation ID (if skipped)")


class BatchInstallResponseSerializer(serializers.Serializer):
    """Response for batch_install endpoint."""
    batch_id = serializers.CharField(help_text="Batch operation UUID")
    total = serializers.IntegerField(help_text="Total number of databases in request")
    queued = serializers.IntegerField(help_text="Number of installations queued")
    skipped = serializers.IntegerField(help_text="Number of databases skipped")
    installations = BatchInstallItemSerializer(many=True)


class RetryInstallationResponseSerializer(serializers.Serializer):
    """Response for retry_installation endpoint."""
    database_id = serializers.CharField(help_text="Database UUID")
    installation_id = serializers.CharField(help_text="New installation UUID")
    status = serializers.CharField(help_text="Installation status: pending")
    task_id = serializers.CharField(required=False, help_text="Task ID (if async)")
    message = serializers.CharField(help_text="Status message")

# Configuration
EXTENSION_BASE_PATH = getattr(settings, 'EXTENSION_BASE_PATH', '/var/lib/1c/extensions')
MAX_BATCH_SIZE = 100


def validate_uuid(value: str, param_name: str = 'id') -> bool:
    """Validate that value is a valid UUID."""
    try:
        uuid_lib.UUID(value)
        return True
    except (ValueError, TypeError):
        return False


@extend_schema(
    tags=['v2'],
    summary='List extension installations',
    description='List all extension installations with optional filtering by database, status, and extension name.',
    parameters=[
        OpenApiParameter(name='database_id', type=str, required=False, description='Filter by database UUID'),
        OpenApiParameter(name='status', type=str, required=False, description='Filter by status (pending, in_progress, completed, failed)'),
        OpenApiParameter(name='extension_name', type=str, required=False, description='Filter by extension name'),
        OpenApiParameter(name='limit', type=int, required=False, description='Maximum results (default: 50, max: 1000)'),
        OpenApiParameter(name='offset', type=int, required=False, description='Pagination offset (default: 0)'),
    ],
    responses={
        200: ExtensionListResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
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

    # Calculate summary using single aggregate query (avoids N+1)
    summary = qs.aggregate(
        pending=Count('id', filter=Q(status=ExtensionInstallation.STATUS_PENDING)),
        in_progress=Count('id', filter=Q(status=ExtensionInstallation.STATUS_IN_PROGRESS)),
        completed=Count('id', filter=Q(status=ExtensionInstallation.STATUS_COMPLETED)),
        failed=Count('id', filter=Q(status=ExtensionInstallation.STATUS_FAILED)),
    )

    # Apply pagination
    qs = qs[offset:offset + limit]

    serializer = ExtensionInstallationSerializer(qs, many=True)

    return Response({
        'extensions': serializer.data,
        'count': len(serializer.data),
        'total': total,
        'summary': summary,
    })


@extend_schema(
    tags=['v2'],
    summary='Get extension installation status',
    description='Get extension installation status for a specific database, including latest installation and history.',
    parameters=[
        OpenApiParameter(name='database_id', type=str, required=True, description='Database UUID (required)'),
        OpenApiParameter(name='extension_name', type=str, required=False, description='Extension name (default: ODataAutoConfig)'),
    ],
    responses={
        200: InstallStatusResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
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

    if not validate_uuid(database_id, 'database_id'):
        return Response({
            'success': False,
            'error': {
                'code': 'INVALID_PARAMETER',
                'message': 'database_id must be a valid UUID'
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


class RetryInstallationRequestSerializer(serializers.Serializer):
    """Request body for retry_installation endpoint."""
    database_id = serializers.CharField(help_text="Database UUID (required)")
    extension_name = serializers.CharField(required=False, default='ODataAutoConfig', help_text="Extension name (default: ODataAutoConfig)")


@extend_schema(
    tags=['v2'],
    summary='Retry extension installation',
    description='Retry extension installation for a specific database. Creates a new installation record and queues the task.',
    request=RetryInstallationRequestSerializer,
    responses={
        200: RetryInstallationResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
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

    if not validate_uuid(database_id, 'database_id'):
        return Response({
            'success': False,
            'error': {
                'code': 'INVALID_PARAMETER',
                'message': 'database_id must be a valid UUID'
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

    # Trigger async installation via Go Worker (or Celery fallback)
    from apps.operations.services import OperationsService

    extension_config = {
        'name': extension_name,
        'path': f'{EXTENSION_BASE_PATH}/{extension_name}.cfe',
        'extension_id': str(installation.id),
    }

    if OperationsService.is_celery_enabled():
        # Legacy Celery path
        try:
            from apps.databases.tasks import queue_extension_installation
            task = queue_extension_installation.delay(
                [str(database_id)],
                {'name': extension_name, 'path': f'{EXTENSION_BASE_PATH}/{extension_name}.cfe'}
            )

            logger.info(
                "Extension installation retry scheduled via Celery",
                extra={
                    'installation_id': str(installation.id),
                    'database_id': database_id,
                    'extension_name': extension_name,
                    'retry_count': retry_count,
                    'requested_by': request.user.username if request.user else 'anonymous',
                    'task_id': task.id,
                }
            )

            return Response({
                'database_id': database_id,
                'installation_id': str(installation.id),
                'status': 'pending',
                'task_id': task.id,
                'message': 'Installation retry scheduled (Celery)',
            })
        except Exception as e:
            logger.warning(f"Celery unavailable: {e}")
    else:
        # New Go Worker path
        try:
            result = OperationsService.enqueue_extension_install(
                database_ids=[str(database_id)],
                extension_config=extension_config,
                created_by=request.user.username if request.user else 'anonymous'
            )

            if result.success:
                logger.info(
                    "Extension installation retry scheduled via Go Worker",
                    extra={
                        'installation_id': str(installation.id),
                        'database_id': database_id,
                        'extension_name': extension_name,
                        'retry_count': retry_count,
                        'requested_by': request.user.username if request.user else 'anonymous',
                        'operation_id': result.operation_id,
                    }
                )

                return Response({
                    'database_id': database_id,
                    'installation_id': str(installation.id),
                    'status': 'pending',
                    'operation_id': result.operation_id,
                    'message': 'Installation retry scheduled (Go Worker)',
                })
            else:
                logger.warning(f"Go Worker enqueue failed: {result.error}")
        except Exception as e:
            logger.warning(f"Go Worker unavailable: {e}")

    # Fallback response
    logger.info(
        "Extension installation queued (async worker unavailable)",
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


class BatchInstallRequestSerializer(serializers.Serializer):
    """Request body for batch_install endpoint."""
    database_ids = serializers.ListField(
        child=serializers.CharField(),
        help_text="List of database UUIDs to install extension to"
    )
    extension_name = serializers.CharField(
        required=False,
        default='ODataAutoConfig',
        help_text="Extension name (default: ODataAutoConfig)"
    )
    extension_path = serializers.CharField(
        required=False,
        help_text="Path to extension file (optional)"
    )


@extend_schema(
    tags=['v2'],
    summary='Batch install extension',
    description='Batch install extension to multiple databases. Skips databases that already have installation in progress.',
    request=BatchInstallRequestSerializer,
    responses={
        200: BatchInstallResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
        404: ErrorResponseSerializer,
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_install(request):
    """
    POST /api/v2/extensions/batch-install/

    Batch install extension to multiple databases.

    Request Body:
        {
            "database_ids": ["uuid1", "uuid2", ...],
            "extension_name": "ODataAutoConfig",  // optional
            "extension_path": "C:\\Extensions\\ODataAutoConfig.cfe"  // optional
        }

    Response:
        {
            "batch_id": "uuid",
            "total": 10,
            "queued": 8,
            "skipped": 2,
            "installations": [
                {"database_id": "uuid1", "installation_id": "uuid", "status": "pending"},
                {"database_id": "uuid2", "status": "skipped", "reason": "already_in_progress"}
            ]
        }
    """
    database_ids = request.data.get('database_ids', [])

    # Validate batch size limit
    if isinstance(database_ids, list) and len(database_ids) > MAX_BATCH_SIZE:
        return Response({
            'success': False,
            'error': {
                'code': 'BATCH_TOO_LARGE',
                'message': f'Maximum {MAX_BATCH_SIZE} databases per batch'
            }
        }, status=400)

    extension_name = request.data.get('extension_name', 'ODataAutoConfig')
    extension_path = request.data.get(
        'extension_path',
        f'{EXTENSION_BASE_PATH}/{extension_name}.cfe'
    )

    if not database_ids:
        return Response({
            'success': False,
            'error': {
                'code': 'MISSING_PARAMETER',
                'message': 'database_ids is required and must be a non-empty list'
            }
        }, status=400)

    if not isinstance(database_ids, list):
        return Response({
            'success': False,
            'error': {
                'code': 'INVALID_PARAMETER',
                'message': 'database_ids must be a list'
            }
        }, status=400)

    # Validate all database IDs are valid UUIDs
    invalid_uuids = [db_id for db_id in database_ids if not validate_uuid(str(db_id), 'database_id')]
    if invalid_uuids:
        return Response({
            'success': False,
            'error': {
                'code': 'INVALID_PARAMETER',
                'message': f'Invalid UUID format for database_ids: {invalid_uuids}'
            }
        }, status=400)

    # Validate all database IDs exist
    existing_dbs = Database.objects.filter(id__in=database_ids)
    existing_db_ids = set(str(db.id) for db in existing_dbs)
    missing_ids = [db_id for db_id in database_ids if str(db_id) not in existing_db_ids]

    if missing_ids:
        return Response({
            'success': False,
            'error': {
                'code': 'DATABASES_NOT_FOUND',
                'message': f'Some databases not found: {missing_ids}'
            }
        }, status=404)

    batch_id = str(uuid_lib.uuid4())
    installations = []
    queued_count = 0
    skipped_count = 0

    for db in existing_dbs:
        with transaction.atomic():
            # Check if there's already an active installation
            active_installation = ExtensionInstallation.objects.select_for_update().filter(
                database=db,
                extension_name=extension_name,
                status__in=[
                    ExtensionInstallation.STATUS_PENDING,
                    ExtensionInstallation.STATUS_IN_PROGRESS
                ]
            ).first()

            if active_installation:
                installations.append({
                    'database_id': str(db.id),
                    'status': 'skipped',
                    'reason': 'already_in_progress',
                    'existing_installation_id': str(active_installation.id)
                })
                skipped_count += 1
                continue

            # Get previous installation for retry count
            previous = ExtensionInstallation.objects.filter(
                database=db,
                extension_name=extension_name
            ).order_by('-created_at').first()

            retry_count = (previous.retry_count + 1) if previous else 0

            # Create new installation record
            installation = ExtensionInstallation.objects.create(
                database=db,
                extension_name=extension_name,
                status=ExtensionInstallation.STATUS_PENDING,
                retry_count=retry_count,
            )

            installations.append({
                'database_id': str(db.id),
                'installation_id': str(installation.id),
                'status': 'pending'
            })
            queued_count += 1

    # Trigger async batch installation via Go Worker (or Celery fallback)
    queued_db_ids = [
        inst['database_id'] for inst in installations
        if inst['status'] == 'pending'
    ]

    if queued_db_ids:
        from apps.operations.services import OperationsService

        extension_config = {
            'name': extension_name,
            'path': extension_path,
        }

        if OperationsService.is_celery_enabled():
            # Legacy Celery path
            try:
                from apps.databases.tasks import queue_extension_installation
                task = queue_extension_installation.delay(
                    queued_db_ids,
                    {'name': extension_name, 'path': extension_path}
                )

                logger.info(
                    "Batch extension installation scheduled via Celery",
                    extra={
                        'batch_id': batch_id,
                        'total': len(database_ids),
                        'queued': queued_count,
                        'skipped': skipped_count,
                        'requested_by': request.user.username if request.user else 'anonymous',
                        'task_id': task.id,
                    }
                )
            except Exception as e:
                logger.warning(f"Celery unavailable for batch install: {e}")
        else:
            # New Go Worker path
            try:
                result = OperationsService.enqueue_extension_install(
                    database_ids=queued_db_ids,
                    extension_config=extension_config,
                    created_by=request.user.username if request.user else 'anonymous'
                )

                if result.success:
                    logger.info(
                        "Batch extension installation scheduled via Go Worker",
                        extra={
                            'batch_id': batch_id,
                            'total': len(database_ids),
                            'queued': queued_count,
                            'skipped': skipped_count,
                            'requested_by': request.user.username if request.user else 'anonymous',
                            'operation_id': result.operation_id,
                        }
                    )
                else:
                    logger.warning(f"Go Worker enqueue failed for batch install: {result.error}")
            except Exception as e:
                logger.warning(f"Go Worker unavailable for batch install: {e}")

    return Response({
        'batch_id': batch_id,
        'total': len(database_ids),
        'queued': queued_count,
        'skipped': skipped_count,
        'installations': installations,
    })


@extend_schema(
    tags=['v2'],
    summary='Get extension installation progress',
    description='Get progress of extension installations across databases. Shows aggregated statistics and per-database status.',
    parameters=[
        OpenApiParameter(name='database_ids', type=str, required=False, description='Comma-separated list of database UUIDs (optional)'),
        OpenApiParameter(name='extension_name', type=str, required=False, description='Extension name filter (default: ODataAutoConfig)'),
    ],
    responses={
        200: InstallProgressResponseSerializer,
        400: ErrorResponseSerializer,
        401: OpenApiResponse(description='Unauthorized'),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_install_progress(request):
    """
    GET /api/v2/extensions/get-install-progress/

    Get progress of extension installations.

    Query Parameters:
        - database_ids: Comma-separated list of database IDs (optional)
        - extension_name: Extension name filter (optional, default: ODataAutoConfig)

    Response:
        {
            "progress": {
                "total": 10,
                "pending": 2,
                "in_progress": 3,
                "completed": 4,
                "failed": 1,
                "percent_complete": 50.0
            },
            "databases": [
                {
                    "database_id": "uuid",
                    "database_name": "DB1",
                    "status": "completed",
                    "updated_at": "2024-01-01T00:00:00Z"
                }
            ]
        }
    """
    database_ids_str = request.query_params.get('database_ids', '')
    extension_name = request.query_params.get('extension_name', 'ODataAutoConfig')

    database_ids = [
        db_id.strip()
        for db_id in database_ids_str.split(',')
        if db_id.strip()
    ] if database_ids_str else []

    # Validate all database IDs are valid UUIDs (if provided)
    if database_ids:
        invalid_uuids = [db_id for db_id in database_ids if not validate_uuid(db_id, 'database_id')]
        if invalid_uuids:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_PARAMETER',
                    'message': f'Invalid UUID format for database_ids: {invalid_uuids}'
                }
            }, status=400)

    qs = ExtensionInstallation.objects.filter(
        extension_name=extension_name
    ).select_related('database')

    if database_ids:
        qs = qs.filter(database_id__in=database_ids)

    # Get latest installation per database
    latest_ids = ExtensionInstallation.objects.filter(
        extension_name=extension_name
    )
    if database_ids:
        latest_ids = latest_ids.filter(database_id__in=database_ids)

    latest_ids = latest_ids.values('database_id').annotate(
        latest_id=Max('id')
    ).values_list('latest_id', flat=True)

    latest_installations = ExtensionInstallation.objects.filter(
        id__in=latest_ids
    ).select_related('database')

    # Calculate progress using single aggregate query (avoids N+1)
    progress_stats = latest_installations.aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status=ExtensionInstallation.STATUS_PENDING)),
        in_progress=Count('id', filter=Q(status=ExtensionInstallation.STATUS_IN_PROGRESS)),
        completed=Count('id', filter=Q(status=ExtensionInstallation.STATUS_COMPLETED)),
        failed=Count('id', filter=Q(status=ExtensionInstallation.STATUS_FAILED)),
    )

    total = progress_stats['total']
    pending = progress_stats['pending']
    in_progress = progress_stats['in_progress']
    completed = progress_stats['completed']
    failed = progress_stats['failed']

    percent_complete = (
        round((completed / total) * 100, 1) if total > 0 else 0.0
    )

    databases = []
    for inst in latest_installations.order_by('-updated_at')[:100]:
        databases.append({
            'database_id': str(inst.database_id),
            'database_name': inst.database.name if inst.database else 'Unknown',
            'status': inst.status,
            'error_message': inst.error_message if inst.status == ExtensionInstallation.STATUS_FAILED else None,
            'updated_at': inst.updated_at.isoformat() if inst.updated_at else None,
        })

    return Response({
        'progress': {
            'total': total,
            'pending': pending,
            'in_progress': in_progress,
            'completed': completed,
            'failed': failed,
            'percent_complete': percent_complete,
        },
        'databases': databases,
    })