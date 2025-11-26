"""
URL routing for Workflow Engine REST API.

Routes:
- /workflows/ - WorkflowTemplate CRUD + actions
- /executions/ - WorkflowExecution read + actions
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import WorkflowExecutionViewSet, WorkflowTemplateViewSet

app_name = 'workflow'

router = DefaultRouter()
router.register(r'workflows', WorkflowTemplateViewSet, basename='workflow')
router.register(r'executions', WorkflowExecutionViewSet, basename='execution')

urlpatterns = [
    path('', include(router.urls)),
]
