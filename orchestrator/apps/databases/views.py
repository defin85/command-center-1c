"""REST API Views для databases app."""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from .models import Database, DatabaseGroup
from .serializers import DatabaseSerializer, DatabaseGroupSerializer
from .services import DatabaseService


class DatabaseViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления базами данных 1С.

    Endpoints:
    - GET /api/v1/databases/ - список баз
    - POST /api/v1/databases/ - создать базу
    - GET /api/v1/databases/{id}/ - получить базу
    - PUT/PATCH /api/v1/databases/{id}/ - обновить базу
    - DELETE /api/v1/databases/{id}/ - удалить базу
    - POST /api/v1/databases/{id}/health_check/ - проверить здоровье
    - POST /api/v1/databases/bulk_health_check/ - проверить все базы
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

        # Выполняем health check через service
        result = DatabaseService.health_check_database(database)

        return Response({
            'database_id': str(database.id),
            'database_name': database.name,
            **result
        })

    @extend_schema(
        summary="Bulk health check для всех баз",
        description="Проверяет все базы или отфильтрованный набор баз",
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
            200: OpenApiResponse(
                description="Bulk health check выполнен",
                response={
                    'type': 'object',
                    'properties': {
                        'total': {'type': 'integer'},
                        'healthy': {'type': 'integer'},
                        'unhealthy': {'type': 'integer'},
                        'results': {
                            'type': 'array',
                            'items': {'type': 'object'}
                        }
                    }
                }
            )
        }
    )
    @action(detail=False, methods=['post'], url_path='bulk-health-check')
    def bulk_health_check(self, request):
        """
        Проверить здоровье всех баз (или отфильтрованных).

        POST /api/v1/databases/bulk-health-check/?status=active
        """
        # Получаем queryset (может быть отфильтрован)
        queryset = self.filter_queryset(self.get_queryset())

        results = []
        healthy_count = 0

        for database in queryset:
            result = DatabaseService.health_check_database(database)
            results.append({
                'database_id': str(database.id),
                'database_name': database.name,
                **result
            })
            if result['healthy']:
                healthy_count += 1

        return Response({
            'total': len(results),
            'healthy': healthy_count,
            'unhealthy': len(results) - healthy_count,
            'results': results
        })


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
