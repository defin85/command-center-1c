"""URL routing для databases app."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DatabaseViewSet,
    DatabaseGroupViewSet,
    batch_install_extension,
    installation_progress,
    extension_status,
    retry_installation,
)

router = DefaultRouter()
router.register('databases', DatabaseViewSet)
router.register('groups', DatabaseGroupViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # Installation Service endpoints
    path('batch-install-extension/', batch_install_extension, name='batch-install-extension'),
    path('installation-progress/<str:task_id>/', installation_progress, name='installation-progress'),
    path('<str:pk>/extension-status/', extension_status, name='extension-status'),
    path('<str:pk>/retry-installation/', retry_installation, name='retry-installation'),
]
