"""URL routing для databases app."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DatabaseViewSet,
    DatabaseGroupViewSet,
    ClusterViewSet,
    batch_install_extension,
    installation_progress,
    installation_callback,
    list_extension_storage,
    upload_extension,
    delete_extension_storage,
)

router = DefaultRouter()
router.register('databases', DatabaseViewSet, basename='database')
router.register('groups', DatabaseGroupViewSet, basename='group')
router.register('clusters', ClusterViewSet, basename='cluster')

urlpatterns = [
    path('', include(router.urls)),
    
    # Batch installation endpoint (не привязан к конкретной базе)
    path('databases/batch-install-extension/', batch_install_extension, name='batch-install-extension'),
    path('databases/installation-progress/<str:task_id>/', installation_progress, name='installation-progress'),
    
    # Callback from batch-service
    path('extensions/installation/callback/', installation_callback, name='installation-callback'),

    # Extension storage
    path('extensions/storage/', list_extension_storage, name='list-extension-storage'),
    path('extensions/upload/', upload_extension, name='upload-extension'),
    path('extensions/storage/<str:filename>/', delete_extension_storage, name='delete-extension-storage'),
]
