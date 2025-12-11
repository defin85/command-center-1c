"""REST API Views для databases app."""

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from django.db.models import Count, Q, Avg
from django.utils import timezone

from .models import Database, DatabaseGroup, ExtensionInstallation, Cluster
from .serializers import DatabaseSerializer, DatabaseGroupSerializer, ExtensionInstallationSerializer, ClusterSerializer
from .services import DatabaseService
from .storage import ExtensionStorageService


class DatabaseGroupViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления группами баз данных.

    Endpoints:
    - GET /api/v1/groups/ - список групп
    - POST /api/v1/groups/ - создать группу
    - GET /api/v1/groups/{id}/ - получить группу
    - PUT/PATCH /api/v1/groups/{id}/ - обновить группу
    - DELETE /api/v1/groups/{id}/ - удалить группу
    - POST /api/v1/groups/{id}/health_check/ - проверить все базы в группе
    """

    queryset = DatabaseGroup.objects.all()
    serializer_class = DatabaseGroupSerializer
    search_fields = ['name', 'description']
    ordering = ['-created_at']

    @extend_schema(
        summary="Health check для всех баз в группе",
        description="Проверяет все базы данных в указанной группе",
        responses={
            200: OpenApiResponse(
                description="Health check выполнен для всех баз в группе",
                response={
                    'type': 'object',
                    'properties': {
                        'group_name': {'type': 'string'},
                        'total': {'type': 'integer'},
                        'healthy': {'type': 'integer'},
                        'unhealthy': {'type': 'integer'},
                        'results': {
                            'type': 'array',
                            'items': {'type': 'object'}
                        }
                    }
                }
            ),
            404: OpenApiResponse(description="Группа не найдена")
        }
    )
    @action(detail=True, methods=['post'], url_path='health-check')
    def health_check(self, request, pk=None):
        """
        Проверить здоровье всех баз в группе.

        POST /api/v1/groups/{id}/health-check/
        """
        group = self.get_object()

        # Выполняем group health check через service
        result = DatabaseService.health_check_group(group)

        return Response(result)


# Installation Service views

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_install_extension(request):
    """Запуск массовой установки расширения на группу баз"""
    database_ids = request.data.get('database_ids', [])
    extension_config = request.data.get('extension_config', {})

    # Валидация
    if not extension_config.get('name') or not extension_config.get('path'):
        return Response(
            {"error": "extension_config must contain 'name' and 'path'"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Если "all", взять все активные базы
    if isinstance(database_ids, str) and database_ids == "all":
        database_ids = list(Database.objects.filter(status='active').values_list('id', flat=True))
    elif not isinstance(database_ids, list):
        return Response(
            {"error": "database_ids must be a list of integers or 'all'"},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not database_ids:
        return Response(
            {"error": "database_ids is empty"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Use Go Worker or Celery fallback
    from apps.operations.services import OperationsService

    if OperationsService.is_celery_enabled():
        # Legacy Celery path
        from .tasks import queue_extension_installation
        task = queue_extension_installation.delay(database_ids, extension_config)
        return Response({
            "task_id": str(task.id),
            "total_databases": len(database_ids),
            "status": "queued"
        }, status=status.HTTP_201_CREATED)
    else:
        # New Go Worker path
        result = OperationsService.enqueue_extension_install(
            database_ids=[str(db_id) for db_id in database_ids],
            extension_config=extension_config,
            created_by=request.user.username if request.user and request.user.is_authenticated else 'system'
        )

        if result.success:
            return Response({
                "operation_id": result.operation_id,
                "total_databases": len(database_ids),
                "status": "queued"
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                "error": result.error,
                "status": "error"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def installation_progress(request, task_id):
    """Real-time прогресс установки"""
    installations = ExtensionInstallation.objects.all()

    stats = installations.aggregate(
        total=Count('id'),
        completed=Count('id', filter=Q(status='completed')),
        failed=Count('id', filter=Q(status='failed')),
        in_progress=Count('id', filter=Q(status='in_progress')),
        pending=Count('id', filter=Q(status='pending'))
    )

    total = stats['total'] or 1
    progress_percent = (stats['completed'] / total) * 100 if total > 0 else 0

    # Простая оценка оставшегося времени (можно улучшить)
    avg_duration = installations.filter(
        status='completed',
        duration_seconds__isnull=False
    ).aggregate(avg=Avg('duration_seconds'))['avg'] or 60

    remaining_tasks = stats['pending'] + stats['in_progress']
    estimated_time_remaining = int(remaining_tasks * avg_duration / 10)  # 10 параллельных

    return Response({
        "total": stats['total'],
        "completed": stats['completed'],
        "failed": stats['failed'],
        "in_progress": stats['in_progress'],
        "pending": stats['pending'],
        "progress_percent": round(progress_percent, 2),
        "estimated_time_remaining": estimated_time_remaining
    })


@api_view(['GET'])
def extension_status(request, pk):
    """Статус установки для конкретной базы"""
    try:
        installation = ExtensionInstallation.objects.filter(
            database_id=pk
        ).order_by('-created_at').first()

        if not installation:
            return Response(
                {"error": "No installation found for this database"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ExtensionInstallationSerializer(installation)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ======== Extension Storage Endpoints ========
@api_view(['POST'])
@permission_classes([])  # No authentication required for callbacks from batch-service
@extend_schema(
    summary="Callback от batch-service после установки расширения",
    description="""
    Принимает уведомление от batch-service о завершении установки расширения.
    Обновляет статус ExtensionInstallation на основе результата операции.
    """,
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'database_id': {'type': 'string', 'format': 'uuid'},
                'extension_name': {'type': 'string'},
                'status': {'type': 'string', 'enum': ['completed', 'failed']},
                'duration_seconds': {'type': 'number'},
                'error_message': {'type': 'string', 'nullable': True}
            },
            'required': ['database_id', 'extension_name', 'status']
        }
    },
    responses={
        200: OpenApiResponse(description="Callback processed successfully"),
        400: OpenApiResponse(description="Invalid request"),
        404: OpenApiResponse(description="Installation not found")
    }
)
def installation_callback(request):
    """
    Callback от batch-service после завершения установки расширения.

    Payload:
    {
        "database_id": "db_uuid",
        "extension_name": "ODataAutoConfig",
        "status": "completed",  # completed | failed
        "duration_seconds": 45.5,
        "error_message": null
    }
    """

    database_id = request.data.get('database_id')
    extension_name = request.data.get('extension_name')
    install_status = request.data.get('status')
    duration = request.data.get('duration_seconds', 0)
    error = request.data.get('error_message')

    if not all([database_id, extension_name, install_status]):
        return Response(
            {"error": "Missing required fields: database_id, extension_name, status"},
            status=status.HTTP_400_BAD_REQUEST
        )

    if install_status not in ['completed', 'failed']:
        return Response(
            {"error": "Invalid status. Must be 'completed' or 'failed'"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Найти ExtensionInstallation
        installation = ExtensionInstallation.objects.get(
            database_id=database_id,
            extension_name=extension_name,
            status__in=['pending', 'in_progress']
        )

        # Обновить статус
        installation.status = install_status
        installation.completed_at = timezone.now()
        installation.duration_seconds = int(duration)
        if error:
            installation.error_message = error
        installation.save()

        return Response({'status': 'ok'}, status=status.HTTP_200_OK)

    except ExtensionInstallation.DoesNotExist:
        return Response(
            {"error": f"No pending installation found for database {database_id} and extension {extension_name}"},
            status=status.HTTP_404_NOT_FOUND
        )


class ClusterViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления кластерами 1С.

    Endpoints:
    - GET /api/v1/clusters/ - список кластеров
    - POST /api/v1/clusters/ - создать кластер
    - GET /api/v1/clusters/{id}/ - получить кластер
    - PUT/PATCH /api/v1/clusters/{id}/ - обновить кластер
    - DELETE /api/v1/clusters/{id}/ - удалить кластер
    - POST /api/v1/clusters/{id}/sync/ - синхронизировать с RAS
    - GET /api/v1/clusters/{id}/databases/ - базы конкретного кластера
    """

    queryset = Cluster.objects.annotate(
        databases_count=Count('databases')
    )
    serializer_class = ClusterSerializer
    search_fields = ['name', 'description', 'ras_server']
    filterset_fields = ['status']
    ordering_fields = ['name', 'created_at', 'last_sync']
    ordering = ['-created_at']

    @extend_schema(
        summary="Синхронизация баз из RAS",
        description="Синхронизирует список баз данных из RAS через cluster-service",
        responses={
            200: OpenApiResponse(
                description="Синхронизация запущена",
                response={
                    'type': 'object',
                    'properties': {
                        'status': {'type': 'string'},
                        'message': {'type': 'string'},
                        'databases_found': {'type': 'integer'},
                    }
                }
            ),
            404: OpenApiResponse(description="Кластер не найден")
        }
    )
    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """
        Синхронизировать базы из RAS через cluster-service.

        POST /api/v1/clusters/{id}/sync/
        """
        cluster = self.get_object()

        try:
            from .services import ClusterService
            result = ClusterService.sync_infobases(cluster)

            return Response({
                'status': 'success',
                'message': f'Cluster {cluster.name} synchronized successfully',
                'databases_found': result['created'] + result['updated']
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Получить базы кластера",
        description="Возвращает список баз данных в конкретном кластере",
        responses={
            200: OpenApiResponse(
                description="Список баз",
                response=DatabaseSerializer(many=True)
            )
        }
    )
    @action(detail=True, methods=['get'])
    def databases(self, request, pk=None):
        """
        Получить список баз конкретного кластера.

        GET /api/v1/clusters/{id}/databases/
        """
        cluster = self.get_object()
        databases = Database.objects.filter(cluster=cluster)
        serializer = DatabaseSerializer(databases, many=True)
        return Response(serializer.data)


class DatabaseViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления базами данных 1С.

    Endpoints:
    - GET /api/v1/databases/ - список баз
    - POST /api/v1/databases/ - создать базу
    - GET /api/v1/databases/{id}/ - получить базу
    - PUT/PATCH /api/v1/databases/{id}/ - обновить базу
    - DELETE /api/v1/databases/{id}/ - удалить базу
    - POST /api/v1/databases/{id}/health-check/ - проверить здоровье
    - POST /api/v1/databases/bulk-health-check/ - проверить все базы
    - POST /api/v1/databases/{id}/install-extension/ - установить расширение
    """

    queryset = Database.objects.all()
    serializer_class = DatabaseSerializer
    filterset_fields = ['status', 'last_check_status']
    search_fields = ['name', 'host', 'description']
    ordering_fields = ['name', 'created_at', 'last_check']
    ordering = ['-created_at']

    @extend_schema(
        summary="Health check для одной базы",
        description="Проверяет доступность и работоспособность базы 1С через OData",
        responses={
            200: OpenApiResponse(
                description="Health check выполнен",
                response={
                    'type': 'object',
                    'properties': {
                        'database_id': {'type': 'string'},
                        'database_name': {'type': 'string'},
                        'healthy': {'type': 'boolean'},
                        'response_time': {'type': 'number'},
                        'error': {'type': 'string', 'nullable': True},
                        'status_code': {'type': 'integer', 'nullable': True}
                    }
                }
            ),
            404: OpenApiResponse(description="База не найдена")
        }
    )
    @action(detail=True, methods=['post'], url_path='health-check')
    def health_check(self, request, pk=None):
        """
        Проверить здоровье одной базы.

        POST /api/v1/databases/{id}/health-check/
        """
        database = self.get_object()
        result = DatabaseService.health_check_database(database)
        return Response({
            'database_id': str(database.id),
            'database_name': database.name,
            **result
        })

    @extend_schema(
        summary="Bulk health check для всех баз (async)",
        description="Асинхронная проверка всех баз или отфильтрованного набора баз через Celery",
        parameters=[
            OpenApiParameter(
                name='status',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Фильтр по статусу (active, inactive, error, maintenance)',
                required=False
            )
        ],
        responses={
            202: OpenApiResponse(
                description="Health check задача создана",
                response={
                    'type': 'object',
                    'properties': {
                        'task_id': {'type': 'string'},
                        'status': {'type': 'string'},
                        'total_databases': {'type': 'integer'}
                    }
                }
            )
        }
    )
    @action(detail=False, methods=['post'], url_path='bulk-health-check')
    def bulk_health_check(self, request):
        """
        Запланировать асинхронную проверку здоровья всех баз.

        POST /api/v1/databases/bulk-health-check/?status=active
        """
        from apps.operations.services import OperationsService

        queryset = self.filter_queryset(self.get_queryset())
        database_ids = list(queryset.values_list('id', flat=True))

        if OperationsService.is_celery_enabled():
            # Legacy Celery path
            from .tasks import check_databases_health
            task = check_databases_health.delay(database_ids)
            return Response({
                'task_id': str(task.id),
                'status': 'scheduled',
                'total_databases': len(database_ids)
            }, status=status.HTTP_202_ACCEPTED)
        else:
            # New Go Worker path
            result = OperationsService.enqueue_health_check(
                database_ids=[str(db_id) for db_id in database_ids],
                created_by=request.user.username if request.user and request.user.is_authenticated else 'system'
            )

            if result.success:
                return Response({
                    'operation_id': result.operation_id,
                    'status': 'scheduled',
                    'total_databases': len(database_ids)
                }, status=status.HTTP_202_ACCEPTED)
            else:
                return Response({
                    'error': result.error,
                    'status': 'error'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        summary="Установить расширение на базу",
        description="Запускает задачу установки расширения на выбранную базу данных",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'extension_config': {
                        'type': 'object',
                        'properties': {
                            'name': {'type': 'string'},
                            'path': {'type': 'string'}
                        },
                        'required': ['name', 'path']
                    }
                }
            }
        },
        responses={
            201: OpenApiResponse(
                description="Installation task created",
                response={
                    'type': 'object',
                    'properties': {
                        'status': {'type': 'string'},
                        'task_id': {'type': 'string'},
                        'message': {'type': 'string'}
                    }
                }
            ),
            400: OpenApiResponse(description="Invalid extension config"),
            404: OpenApiResponse(description="Database not found")
        }
    )
    @action(detail=True, methods=['post'], url_path='install-extension')
    def install_extension(self, request, pk=None):
        """
        Установить расширение на одну базу.

        POST /api/v1/databases/{id}/install-extension/
        """
        database = self.get_object()
        extension_config = request.data.get('extension_config', {})

        # Валидация
        if not extension_config.get('name') or not extension_config.get('path'):
            return Response(
                {"error": "extension_config must contain 'name' and 'path'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        from apps.operations.services import OperationsService

        if OperationsService.is_celery_enabled():
            # Legacy Celery path
            from .tasks import queue_extension_installation
            task = queue_extension_installation.delay([str(pk)], extension_config)

            # Получить результат task чтобы извлечь operation_id
            result = task.get(timeout=10)  # Ждём максимум 10 секунд

            return Response({
                "status": "queued",
                "task_id": str(task.id),
                "operation_id": result.get("operation_id"),
                "message": f"Installation started for {database.name} (Celery)",
                "queued_count": result.get("queued_count", 1)
            }, status=status.HTTP_201_CREATED)
        else:
            # New Go Worker path
            result = OperationsService.enqueue_extension_install(
                database_ids=[str(pk)],
                extension_config=extension_config,
                created_by=request.user.username if request.user and request.user.is_authenticated else 'system'
            )

            if result.success:
                return Response({
                    "status": "queued",
                    "operation_id": result.operation_id,
                    "message": f"Installation started for {database.name} (Go Worker)",
                    "queued_count": 1
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    "error": result.error,
                    "status": "error"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="Получить статус установки расширения",
        description="Возвращает статус установки расширения для данной базы",
        responses={
            200: OpenApiResponse(
                description="Extension status",
                response=ExtensionInstallationSerializer
            ),
            404: OpenApiResponse(description="Installation not found")
        }
    )
    @action(detail=True, methods=['get'], url_path='extension-status')
    def extension_status(self, request, pk=None):
        """
        Получить статус установки расширения.
        
        GET /api/v1/databases/{id}/extension-status/
        
        Returns the latest extension installation task for this database.
        """
        from apps.operations.models import Task, BatchOperation
        
        try:
            # Найти последнюю задачу установки расширения для этой базы
            task = Task.objects.filter(
                database_id=pk,
                batch_operation__operation_type=BatchOperation.TYPE_INSTALL_EXTENSION
            ).select_related('batch_operation').latest('created_at')
            
            return Response({
                "id": task.id,
                "database_id": str(task.database_id),
                "extension_name": task.batch_operation.target_entity,
                "status": task.status,
                "started_at": task.started_at,
                "completed_at": task.completed_at,
                "error_message": task.error_message,
                "duration_seconds": task.duration_seconds,
                "retry_count": task.retry_count,
                "metadata": {
                    "operation_id": task.batch_operation.id,
                    "operation_name": task.batch_operation.name,
                    "progress_percent": task.batch_operation.progress
                }
            })
        except Task.DoesNotExist:
            return Response(
                {"error": "No installation found for this database"},
                status=status.HTTP_404_NOT_FOUND
            )

    @extend_schema(
        summary="Обновить статус установки расширения (для Go Worker)",
        description="Endpoint для Go Worker чтобы обновлять статус установки расширения",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'status': {
                        'type': 'string',
                        'enum': ['pending', 'in_progress', 'completed', 'failed'],
                        'description': 'Новый статус установки'
                    },
                    'error_message': {
                        'type': 'string',
                        'description': 'Сообщение об ошибке (если status=failed)'
                    },
                    'progress_percent': {
                        'type': 'integer',
                        'description': 'Процент выполнения (0-100)'
                    }
                },
                'required': ['status']
            }
        },
        responses={
            200: OpenApiResponse(description="Status updated successfully"),
            404: OpenApiResponse(description="No pending installation found")
        }
    )
    @action(detail=True, methods=['patch'], url_path='extension-installation-status')
    def update_extension_installation_status(self, request, pk=None):
        """
        Обновить статус установки расширения (используется Go Worker).
        
        PATCH /api/v1/databases/{id}/extension-installation-status/
        
        Body:
        {
            "status": "in_progress|completed|failed",
            "error_message": "optional error",
            "progress_percent": 50
        }
        """
        from apps.operations.models import Task, BatchOperation
        
        database = self.get_object()
        
        # Получить последнюю pending/in_progress задачу установки расширения
        task = Task.objects.filter(
            database=database,
            batch_operation__operation_type=BatchOperation.TYPE_INSTALL_EXTENSION,
            status__in=[Task.STATUS_PENDING, Task.STATUS_PROCESSING]
        ).select_related('batch_operation').order_by('-created_at').first()
        
        if not task:
            return Response(
                {"error": "No pending installation task found for this database"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Маппинг статусов
        status_mapping = {
            'pending': Task.STATUS_PENDING,
            'in_progress': Task.STATUS_PROCESSING,
            'completed': Task.STATUS_COMPLETED,
            'failed': Task.STATUS_FAILED
        }
        
        new_status = request.data.get('status')
        if new_status not in status_mapping:
            return Response(
                {"error": "Invalid status. Must be: pending, in_progress, completed, or failed"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Обновить статус задачи
        if new_status == 'in_progress':
            task.mark_started(worker_id=request.data.get('worker_id', 'worker-1'))
        elif new_status == 'completed':
            result = {
                "success": True,
                "progress_percent": request.data.get('progress_percent', 100)
            }
            task.mark_completed(result=result)
        elif new_status == 'failed':
            error_message = request.data.get('error_message', 'Unknown error')
            task.mark_failed(error_message=error_message, should_retry=False)
        
        return Response({
            "id": task.id,
            "database_id": str(task.database_id),
            "status": task.status,
            "error_message": task.error_message,
            "duration_seconds": task.duration_seconds
        })

    @action(detail=True, methods=['get'], url_path='cluster-info')
    def get_cluster_info(self, request, pk=None):
        """
        GET /api/v1/databases/{id}/cluster-info/

        Returns cluster_id (RAS UUID) and infobase_id для RAS operations.
        """
        database = self.get_object()

        # cluster_id: use cluster.ras_cluster_uuid (actual RAS cluster UUID)
        # NOT database.ras_cluster_id or database.cluster_id (Django FK)
        cluster_id = None
        if database.cluster and database.cluster.ras_cluster_uuid:
            cluster_id = str(database.cluster.ras_cluster_uuid)

        # infobase_id: use ras_infobase_id if set, otherwise database.id as fallback
        infobase_id = str(database.ras_infobase_id) if database.ras_infobase_id else str(database.id)

        return Response({
            "database_id": str(database.id),
            "cluster_id": cluster_id,
            "infobase_id": infobase_id,
        })

    @action(detail=True, methods=['post'], url_path='retry-installation')
    def retry_installation(self, request, pk=None):
        """
        Повторить установку расширения.

        POST /api/v1/databases/{id}/retry-installation/
        """
        try:
            installation = ExtensionInstallation.objects.filter(
                database_id=pk,
                status='failed'
            ).latest('created_at')

            extension_config = {
                'name': installation.extension_name,
                'path': installation.extension_path
            }

            from apps.operations.services import OperationsService

            if OperationsService.is_celery_enabled():
                # Legacy Celery path
                from .tasks import queue_extension_installation
                task = queue_extension_installation.delay([str(pk)], extension_config)
                return Response({"task_id": str(task.id)})
            else:
                # New Go Worker path
                result = OperationsService.enqueue_extension_install(
                    database_ids=[str(pk)],
                    extension_config=extension_config,
                    created_by=request.user.username if request.user and request.user.is_authenticated else 'system'
                )

                if result.success:
                    return Response({"operation_id": result.operation_id})
                else:
                    return Response(
                        {"error": result.error},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

        except ExtensionInstallation.DoesNotExist:
            return Response(
                {"error": "No failed installation found for this database"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        summary="Получить credentials для базы (для Go Worker)",
        description="Возвращает OData URL и credentials для базы данных",
        responses={
            200: OpenApiResponse(
                description="Credentials returned",
                response={
                    'type': 'object',
                    'properties': {
                        'database_id': {'type': 'string'},
                        'odata_url': {'type': 'string'},
                        'username': {'type': 'string'},
                        'password': {'type': 'string'}
                    }
                }
            ),
            404: OpenApiResponse(description="Database not found")
        }
    )
    @action(detail=True, methods=['get'], url_path='credentials', permission_classes=[IsAuthenticated])
    def get_credentials(self, request, pk=None):
        """
        Получить credentials для базы (encrypted payload).

        GET /api/v1/databases/{id}/credentials/

        Returns encrypted credentials payload for secure transport:
        {
            "encrypted_data": "base64(...)",
            "nonce": "base64(...)",
            "expires_at": "ISO8601 timestamp",
            "encryption_version": "aes-gcm-256-v1"
        }

        Security: AES-GCM-256 encrypted payload + short TTL (5 min)
        """
        import logging
        logger = logging.getLogger(__name__)

        # Debug logging - incoming request
        auth_header = request.META.get('HTTP_AUTHORIZATION', 'missing')
        logger.info("Credentials request received", extra={
            "database_id": pk,
            "user": str(request.user),
            "auth_header": auth_header[:50] if auth_header else 'missing',
            "remote_addr": request.META.get('REMOTE_ADDR'),
            "is_authenticated": request.user.is_authenticated,
            "is_service_user": hasattr(request.user, 'service_name'),
        })

        try:
            database = self.get_object()

            if not database.odata_url or not database.username:
                logger.warning("Database configuration incomplete", extra={
                    "database_id": str(database.id),
                    "has_odata_url": bool(database.odata_url),
                    "has_username": bool(database.username),
                })
                return Response(
                    {"error": "Database configuration is incomplete"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # ВАЖНО: Ручная расшифровка пароля
            # Библиотека django-encrypted-model-fields НЕ делает автоматическую расшифровку
            from cryptography.fernet import Fernet
            from django.conf import settings

            # Пароль может быть дважды зашифрован (legacy issue)
            # Сначала пробуем расшифровать ключом из .env (legacy)
            encrypted_password = database.password

            try:
                # Попытка 1: Обычная расшифровка (single encryption)
                f = Fernet(settings.FIELD_ENCRYPTION_KEY.encode())
                decrypted_password = f.decrypt(encrypted_password.encode()).decode()
            except Exception as e1:
                try:
                    # Попытка 2: Двойная расшифровка (double encryption - legacy)
                    key1 = 'jSYlz4dLk2FuVQo_UOiqlir4Lv8q5M_GbpTQWfyco-o='  # старый ключ из .env
                    f1 = Fernet(key1.encode())
                    temp = f1.decrypt(encrypted_password.encode()).decode()

                    key2 = settings.FIELD_ENCRYPTION_KEY
                    f2 = Fernet(key2.encode())
                    decrypted_password = f2.decrypt(temp.encode()).decode()

                    logger.warning(f"Password double-encrypted (legacy) for database {database.id}")
                except Exception as e2:
                    # Последняя попытка: пароль НЕ зашифрован (plain text)
                    logger.error(f"Failed to decrypt password for database {database.id}: {e1}, {e2}")
                    decrypted_password = encrypted_password  # Fallback to plain text

            # Prepare plain credentials dictionary
            plain_credentials = {
                "database_id": str(database.id),
                # OData credentials
                "odata_url": database.odata_url,
                "username": database.username,
                "password": decrypted_password,  # Расшифрованный пароль
                # 1C Server connection (для DESIGNER режима)
                "server_address": database.server_address,
                "server_port": database.server_port,
                "infobase_name": database.infobase_name or database.name,
                # Legacy fields (для обратной совместимости)
                "host": database.host,
                "port": database.port,
                "base_name": database.base_name or database.name,
            }

            # Encrypt credentials for transport (AES-GCM-256)
            from .encryption import encrypt_credentials_for_transport
            encrypted_payload = encrypt_credentials_for_transport(plain_credentials)

            # Success logging
            logger.info("Encrypted credentials returned", extra={
                "database_id": str(database.id),
                "database_name": database.name,
                "encryption_version": encrypted_payload["encryption_version"],
                "expires_at": encrypted_payload["expires_at"],
            })

            return Response(encrypted_payload)

        except Exception as e:
            # Error logging
            logger.error(f"Failed to get credentials for database {pk}: {e}", exc_info=True, extra={
                "database_id": pk,
                "user": str(request.user),
                "error_type": type(e).__name__,
            })
            raise


@api_view(['GET'])
def list_extension_storage(request):
    """
    Получить список файлов расширений в хранилище.
    
    GET /api/v1/extensions/storage/
    """
    try:
        extensions = ExtensionStorageService.list_extensions()
        
        # Форматировать даты
        from datetime import datetime
        for ext in extensions:
            ext['modified_at'] = datetime.fromtimestamp(ext['modified_at']).isoformat()
        
        return Response({
            'extensions': extensions,
            'count': len(extensions)
        })
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def upload_extension(request):
    """
    Загрузить файл расширения в хранилище.
    
    POST /api/v1/extensions/upload/
    
    Form data:
        file: .cfe file
        filename: optional custom filename
    """
    try:
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        filename = request.data.get('filename', None)
        
        # Валидация
        if not file.name.lower().endswith('.cfe'):
            return Response(
                {'error': 'File must have .cfe extension'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Проверка размера (max 100MB)
        if file.size > 100 * 1024 * 1024:
            return Response(
                {'error': 'File too large (max 100MB)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Сохранить
        result = ExtensionStorageService.save_extension(file, filename)
        
        return Response({
            'message': 'File uploaded successfully',
            'file': result
        }, status=status.HTTP_201_CREATED)
        
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
def delete_extension_storage(request, filename):
    """
    Удалить файл расширения из хранилища.
    
    DELETE /api/v1/extensions/storage/{filename}/
    """
    try:
        deleted = ExtensionStorageService.delete_extension(filename)
        
        if deleted:
            return Response({'message': 'File deleted successfully'})
        else:
            return Response(
                {'error': 'File not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

