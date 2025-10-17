"""URL routing для databases app."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DatabaseViewSet, DatabaseGroupViewSet

router = DefaultRouter()
router.register('databases', DatabaseViewSet)
router.register('groups', DatabaseGroupViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
