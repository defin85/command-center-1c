from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'operations'

router = DefaultRouter()
router.register(r'', views.BatchOperationViewSet, basename='operation')

urlpatterns = [
    path('', include(router.urls)),

    # Callback endpoint для Go Worker
    path(
        '<str:operation_id>/callback',
        views.operation_callback,
        name='operation-callback'
    ),
]
