"""
WebSocket URL routing for workflow templates app.

Routes:
- ws/workflow/<execution_id>/ - Real-time workflow execution updates
"""
from django.urls import re_path

from apps.templates.consumers import WorkflowExecutionConsumer

websocket_urlpatterns = [
    # Workflow execution real-time updates
    # Format: ws://host:port/ws/workflow/<uuid:execution_id>/
    re_path(
        r'ws/workflow/(?P<execution_id>[0-9a-f-]+)/$',
        WorkflowExecutionConsumer.as_asgi()
    ),
]
