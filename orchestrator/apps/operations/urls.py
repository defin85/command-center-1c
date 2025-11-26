from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import all views from the views package
from apps.operations.views import (
    ServiceMeshMetricsView,
    ServiceMeshHistoryView,
    ServiceMeshOperationsView,
    BatchOperationViewSet,
    operation_callback,
    operation_stream,
)

app_name = 'operations'

router = DefaultRouter()
router.register(r'', BatchOperationViewSet, basename='operation')

urlpatterns = [
    # Service Mesh endpoints (must come before router urls to avoid conflicts)
    path(
        'service-mesh/metrics/',
        ServiceMeshMetricsView.as_view(),
        name='service-mesh-metrics'
    ),
    path(
        'service-mesh/history/<str:service>/',
        ServiceMeshHistoryView.as_view(),
        name='service-mesh-history'
    ),
    path(
        'service-mesh/operations/',
        ServiceMeshOperationsView.as_view(),
        name='service-mesh-operations'
    ),

    # Router URLs (operations CRUD)
    path('', include(router.urls)),

    # Callback endpoint для Go Worker
    path(
        '<str:operation_id>/callback',
        operation_callback,
        name='operation-callback'
    ),

    # SSE endpoint для real-time workflow tracking
    path(
        '<str:operation_id>/stream',
        operation_stream,
        name='operation-stream'
    ),
]
