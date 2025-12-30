from typing import List

from rest_framework import serializers
from .models import BatchOperation, Task


class TaskSerializer(serializers.ModelSerializer):
    """Serializer for Task model."""
    
    database_name = serializers.CharField(source='database.name', read_only=True)
    
    class Meta:
        model = Task
        fields = [
            'id', 'batch_operation', 'database', 'database_name',
            'status', 'result', 'error_message', 'error_code',
            'retry_count', 'max_retries', 'worker_id',
            'started_at', 'completed_at', 'duration_seconds',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'result', 'error_message', 'worker_id',
            'duration_seconds', 'created_at', 'updated_at'
        ]


class BatchOperationSerializer(serializers.ModelSerializer):
    """Serializer for BatchOperation model."""
    
    tasks = TaskSerializer(many=True, read_only=True)
    database_names = serializers.SerializerMethodField()
    
    class Meta:
        model = BatchOperation
        fields = [
            'id', 'name', 'description', 'operation_type', 'target_entity',
            'status', 'progress', 'total_tasks', 'completed_tasks', 'failed_tasks',
            'payload', 'config', 'task_id',
            'started_at', 'completed_at', 'duration_seconds', 'success_rate',
            'created_by', 'metadata', 'created_at', 'updated_at',
            'database_names', 'tasks'
        ]
        read_only_fields = [
            'id', 'status', 'progress', 'total_tasks', 'completed_tasks',
            'failed_tasks', 'duration_seconds', 'success_rate',
            'created_at', 'updated_at', 'tasks'
        ]
    
    def get_database_names(self, obj: BatchOperation) -> List[str]:
        """Get list of database names for this operation."""
        return list(obj.target_databases.values_list('name', flat=True))
