"""
WebSocket URL routing for operations app.

Routes:
- ws/service-mesh/ - Real-time service mesh metrics
"""
from django.urls import re_path

from apps.operations.consumers import ServiceMeshConsumer

websocket_urlpatterns = [
    # Service mesh real-time metrics
    # Format: ws://host:port/ws/service-mesh/
    re_path(
        r'ws/service-mesh/$',
        ServiceMeshConsumer.as_asgi()
    ),
]
