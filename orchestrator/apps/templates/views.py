from rest_framework import viewsets
from .models import OperationTemplate
from .serializers import OperationTemplateSerializer


class OperationTemplateViewSet(viewsets.ModelViewSet):
    queryset = OperationTemplate.objects.all()
    serializer_class = OperationTemplateSerializer
    filterset_fields = ['operation_type', 'is_active']
