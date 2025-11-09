from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'operations'

router = DefaultRouter()
router.register(r'', views.OperationViewSet, basename='operation')
router.register(r'batches', views.BatchOperationViewSet, basename='batch')

urlpatterns = [
    path('', include(router.urls)),

    # Callback endpoint для Go Worker
    path(
        'operations/<str:operation_id>/callback',
        views.operation_callback,
        name='operation-callback'
    ),
]
