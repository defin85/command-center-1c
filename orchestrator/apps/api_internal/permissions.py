"""
Custom permissions for Internal API.

Re-exports IsInternalService from apps.core for convenience.
Adds X-Internal-Token header support alongside existing X-Internal-Service-Token.
"""

from django.conf import settings
from rest_framework.permissions import BasePermission


class IsInternalService(BasePermission):
    """
    Permission class for internal service-to-service requests.

    Allows access if:
    1. Request has valid X-Internal-Token header matching INTERNAL_API_TOKEN
    2. OR X-Internal-Service-Token header matching WORKER_API_KEY
    3. OR request is authenticated with a service JWT token

    Usage in views:
        @permission_classes([IsInternalService])
        def my_internal_endpoint(request):
            ...
    """
    message = "Authentication required for internal API"

    def has_permission(self, request, view):
        # Option 1: Check X-Internal-Token header (new, preferred)
        token = request.headers.get('X-Internal-Token')
        internal_api_token = getattr(settings, 'INTERNAL_API_TOKEN', None)

        if token and internal_api_token and token == internal_api_token:
            return True

        # Option 2: Check X-Internal-Service-Token header (legacy)
        service_token = request.headers.get('X-Internal-Service-Token')
        worker_api_key = getattr(settings, 'WORKER_API_KEY', None)

        if service_token and worker_api_key and service_token == worker_api_key:
            return True

        # Option 3: Check for authenticated service user (JWT with service: prefix)
        if hasattr(request, 'user') and request.user:
            user = request.user
            # Check for ServiceUser (from ServiceJWTAuthentication)
            if hasattr(user, 'service_name'):
                return True
            # Check regular user's username for service prefix
            if hasattr(user, 'username') and str(user.username).startswith('service:'):
                return True

        return False
