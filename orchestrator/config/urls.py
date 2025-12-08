"""URL configuration for CommandCenter1C orchestrator."""

from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView
)
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)
from apps.core.jwt_views import CustomTokenObtainPairView
from apps.health import health_check, health_check_detailed

urlpatterns = [
    path('admin/', admin.site.urls),

    # Health checks
    path('health', health_check, name='health'),
    path('health/', health_check, name='health-slash'),
    path('health/detailed', health_check_detailed, name='health-detailed'),

    # JWT Authentication (custom view adds username + roles claims for Go compatibility)
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # API v1 (DEPRECATED - Sunset: 2026-03-01)
    # Only operations endpoint remains for SSE stream support
    # All other v1 endpoints migrated to v2
    path('api/v1/operations/', include('apps.operations.urls')),

    # API v2 (action-based routing)
    path('api/v2/', include('apps.api_v2.urls')),

    # Internal API (Go Worker communication)
    path('api/internal/', include('apps.api_internal.urls')),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
