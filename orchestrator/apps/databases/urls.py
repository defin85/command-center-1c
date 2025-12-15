"""URL routing для databases app."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DatabaseViewSet,
    DatabaseGroupViewSet,
    ClusterViewSet,
    batch_install_extension,
    installation_progress,
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

    # Batch installation endpoint (not tied to a specific database)
    path('databases/batch-install-extension/', batch_install_extension, name='batch-install-extension'),
    path('databases/installation-progress/<str:task_id>/', installation_progress, name='installation-progress'),

    # NOTE: HTTP callback endpoint removed - using event-driven architecture via Redis Streams
    # Events: events:batch-service:extension:installed, events:batch-service:extension:install-failed
    # See: apps/operations/event_subscriber.py

    # Extension storage
    path('extensions/storage/', list_extension_storage, name='list-extension-storage'),
    path('extensions/upload/', upload_extension, name='upload-extension'),
    path('extensions/storage/<str:filename>/', delete_extension_storage, name='delete-extension-storage'),
]
