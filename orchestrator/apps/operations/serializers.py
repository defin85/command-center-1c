from rest_framework import serializers
from .models import Operation, BatchOperation


class OperationSerializer(serializers.ModelSerializer):
    """Serializer for Operation model."""

    class Meta:
        model = Operation
        fields = [
            'id', 'type', 'status', 'database', 'template',
            'payload', 'result', 'error',
            'created_at', 'updated_at', 'completed_at',
            'retry_count', 'max_retries'
        ]
        read_only_fields = ['id', 'status', 'result', 'error', 'created_at', 'updated_at', 'completed_at']


class BatchOperationSerializer(serializers.ModelSerializer):
    """Serializer for BatchOperation model."""

    class Meta:
        model = BatchOperation
        fields = [
            'id', 'name', 'status', 'progress',
            'total_operations', 'completed_operations', 'failed_operations',
            'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'progress', 'created_at', 'updated_at']
