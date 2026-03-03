from typing import List

from rest_framework import serializers
from .models import BatchOperation, Task
from .ibcmd_cli_builder import mask_argv


_SENSITIVE_KEYS = {
    'db_password',
    'db_pwd',
    'target_db_password',
    'password',
    'secret',
    'token',
    'api_key',
    'access_key',
    'secret_key',
    'stdin',
}


def _mask_value(value):
    if isinstance(value, dict):
        return _mask_dict(value)
    if isinstance(value, list):
        return _mask_list(value)
    return value


def _mask_dict(data: dict):
    masked = {}
    for key, value in data.items():
        key_str = str(key or "")
        key_norm = key_str.strip().lower()
        if key_norm in _SENSITIVE_KEYS or key_norm.endswith('_password') or key_norm.endswith('_pwd'):
            masked[key] = '***'
            continue
        if key_norm in {'argv', 'args'} and isinstance(value, list) and all(isinstance(x, str) for x in value):
            masked[key] = _mask_cli_argv(value)
            continue
        masked[key] = _mask_value(value)
    return masked


def _mask_list(items: list):
    return [_mask_value(item) for item in items]


def _mask_cli_argv(argv: list[str]) -> list[str]:
    # IBCMD-style flags: --db-pwd=..., --password=..., etc.
    masked = mask_argv(argv)

    # DESIGNER-style password arg: /P<password>
    result = []
    for token in masked:
        if isinstance(token, str) and token.startswith("/P") and token != "/P***" and len(token) > 2:
            result.append("/P***")
        else:
            result.append(token)
    return result


class TaskSerializer(serializers.ModelSerializer):
    """Serializer for Task model."""
    
    database_name = serializers.SerializerMethodField()
    
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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if "result" in data:
            data["result"] = _mask_value(data["result"])
            request = self.context.get("request") if isinstance(getattr(self, "context", None), dict) else None
            is_staff = bool(getattr(getattr(request, "user", None), "is_staff", False))
            if not is_staff and isinstance(data.get("result"), dict):
                data["result"].pop("runtime_bindings", None)
        return data

    def get_database_name(self, obj: Task) -> str | None:
        if obj.database_id:
            return obj.database.name
        return None


class BatchOperationSerializer(serializers.ModelSerializer):
    """Serializer for BatchOperation model."""
    
    tasks = TaskSerializer(many=True, read_only=True)
    database_names = serializers.SerializerMethodField()
    workflow_execution_id = serializers.SerializerMethodField()
    node_id = serializers.SerializerMethodField()
    root_operation_id = serializers.SerializerMethodField()
    execution_consumer = serializers.SerializerMethodField()
    lane = serializers.SerializerMethodField()
    priority = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    server_affinity = serializers.SerializerMethodField()
    deadline_at = serializers.SerializerMethodField()
    
    class Meta:
        model = BatchOperation
        fields = [
            'id', 'name', 'description', 'operation_type', 'target_entity',
            'status', 'progress', 'total_tasks', 'completed_tasks', 'failed_tasks',
            'payload', 'config', 'task_id',
            'started_at', 'completed_at', 'duration_seconds', 'success_rate',
            'created_by', 'metadata', 'created_at', 'updated_at',
            'workflow_execution_id', 'node_id', 'root_operation_id', 'execution_consumer', 'lane',
            'priority', 'role', 'server_affinity', 'deadline_at',
            'database_names', 'tasks'
        ]
        read_only_fields = [
            'id', 'status', 'progress', 'total_tasks', 'completed_tasks',
            'failed_tasks', 'duration_seconds', 'success_rate',
            'created_at', 'updated_at', 'tasks'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if "payload" in data:
            data["payload"] = _mask_value(data["payload"])
        if "config" in data:
            data["config"] = _mask_value(data["config"])
        if "metadata" in data:
            data["metadata"] = _mask_value(data["metadata"])
            if isinstance(data["metadata"], dict):
                # execution_plan/bindings are staff-only and exposed via dedicated fields in details responses.
                data["metadata"].pop("execution_plan", None)
                data["metadata"].pop("bindings", None)
        return data
    
    def get_database_names(self, obj: BatchOperation) -> List[str]:
        """Get list of database names for this operation."""
        return list(obj.target_databases.values_list('name', flat=True))

    def _workflow_metadata(self, obj: BatchOperation) -> dict:
        metadata = obj.metadata if isinstance(obj.metadata, dict) else {}
        execution_consumer = str(metadata.get("execution_consumer") or "").strip() or "operations"
        lane = str(metadata.get("lane") or "").strip() or execution_consumer
        return {
            "workflow_execution_id": metadata.get("workflow_execution_id"),
            "node_id": metadata.get("node_id"),
            "root_operation_id": str(metadata.get("root_operation_id") or obj.id),
            "execution_consumer": execution_consumer,
            "lane": lane,
            "priority": str(metadata.get("priority") or "").strip() or None,
            "role": str(metadata.get("role") or "").strip() or None,
            "server_affinity": str(metadata.get("server_affinity") or "").strip() or None,
            "deadline_at": str(metadata.get("deadline_at") or "").strip() or None,
        }

    def get_workflow_execution_id(self, obj: BatchOperation) -> str | None:
        value = self._workflow_metadata(obj).get("workflow_execution_id")
        return str(value) if value is not None else None

    def get_node_id(self, obj: BatchOperation) -> str | None:
        value = self._workflow_metadata(obj).get("node_id")
        return str(value) if value is not None else None

    def get_root_operation_id(self, obj: BatchOperation) -> str:
        return str(self._workflow_metadata(obj).get("root_operation_id") or obj.id)

    def get_execution_consumer(self, obj: BatchOperation) -> str:
        return str(self._workflow_metadata(obj).get("execution_consumer") or "operations")

    def get_lane(self, obj: BatchOperation) -> str:
        return str(self._workflow_metadata(obj).get("lane") or "operations")

    def get_priority(self, obj: BatchOperation) -> str | None:
        value = self._workflow_metadata(obj).get("priority")
        return str(value) if value is not None else None

    def get_role(self, obj: BatchOperation) -> str | None:
        value = self._workflow_metadata(obj).get("role")
        return str(value) if value is not None else None

    def get_server_affinity(self, obj: BatchOperation) -> str | None:
        value = self._workflow_metadata(obj).get("server_affinity")
        return str(value) if value is not None else None

    def get_deadline_at(self, obj: BatchOperation) -> str | None:
        value = self._workflow_metadata(obj).get("deadline_at")
        return str(value) if value is not None else None
