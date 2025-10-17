from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import JsonResponse
from .models import Operation, BatchOperation
from .serializers import OperationSerializer, BatchOperationSerializer


def health_check(request):
    """Health check endpoint."""
    return JsonResponse({
        'status': 'healthy',
        'service': 'orchestrator',
    })


class OperationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing operations."""

    queryset = Operation.objects.all()
    serializer_class = OperationSerializer
    filterset_fields = ['status', 'type', 'database']

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an operation."""
        operation = self.get_object()
        if operation.status in [Operation.STATUS_PENDING, Operation.STATUS_PROCESSING]:
            operation.status = Operation.STATUS_CANCELLED
            operation.save()
            return Response({'status': 'cancelled'})
        return Response(
            {'error': 'Operation cannot be cancelled'},
            status=status.HTTP_400_BAD_REQUEST
        )


class BatchOperationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing batch operations."""

    queryset = BatchOperation.objects.all()
    serializer_class = BatchOperationSerializer
    filterset_fields = ['status']
