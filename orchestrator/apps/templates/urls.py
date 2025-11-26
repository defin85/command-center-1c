from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'templates'

router = DefaultRouter()
router.register(r'', views.OperationTemplateViewSet, basename='template')

urlpatterns = [
    path('', include(router.urls)),
    # Workflow Engine API (Week 10)
    path('workflow/', include('apps.templates.workflow.urls')),
]
