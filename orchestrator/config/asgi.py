"""
ASGI config for CommandCenter1C orchestrator.

Supports both HTTP and WebSocket connections.
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

# Import WebSocket routing after Django is initialized
from apps.templates.routing import websocket_urlpatterns as templates_ws_patterns
from apps.operations.routing import websocket_urlpatterns as operations_ws_patterns

# Custom JWT middleware for WebSocket authentication
from apps.core.middleware import JWTAuthMiddlewareStack

# Combine all WebSocket URL patterns
websocket_urlpatterns = templates_ws_patterns + operations_ws_patterns

application = ProtocolTypeRouter({
    # HTTP requests are handled by Django's ASGI application
    "http": django_asgi_app,

    # WebSocket connections are routed through Channels
    # Uses JWT token from query string for authentication
    "websocket": AllowedHostsOriginValidator(
        JWTAuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
