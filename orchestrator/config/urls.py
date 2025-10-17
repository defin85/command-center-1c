"""URL configuration for CommandCenter1C orchestrator."""

from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView
)
from apps.health import health_check, health_check_detailed

urlpatterns = [
    path('admin/', admin.site.urls),

    # Health checks
    path('health', health_check, name='health'),
    path('health/', health_check, name='health-slash'),
    path('health/detailed', health_check_detailed, name='health-detailed'),

    # API v1
    path('api/v1/', include('apps.databases.urls')),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
