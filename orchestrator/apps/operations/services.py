"""Business logic for operations."""
import uuid
from typing import Dict, List
from .models import Operation, BatchOperation


class OperationService:
    """Service for managing operations."""

    @staticmethod
    def create_operation(operation_type: str, database_id: str, payload: Dict, template_id: str = None) -> Operation:
        """Create a new operation."""
        operation = Operation.objects.create(
            id=str(uuid.uuid4()),
            type=operation_type,
            database_id=database_id,
            template_id=template_id,
            payload=payload,
        )
        return operation

    @staticmethod
    def create_batch_operation(name: str, operations_data: List[Dict]) -> BatchOperation:
        """Create a batch operation with multiple operations."""
        batch = BatchOperation.objects.create(
            id=str(uuid.uuid4()),
            name=name,
            total_operations=len(operations_data),
        )

        # Create individual operations
        # TODO: Link operations to batch

        return batch

    @staticmethod
    def queue_operation(operation: Operation):
        """Queue an operation for processing."""
        # TODO: Push operation to Redis queue for workers
        pass

    @staticmethod
    def update_operation_status(operation_id: str, status: str, result: Dict = None, error: str = None):
        """Update operation status and result."""
        operation = Operation.objects.get(id=operation_id)
        operation.status = status
        if result:
            operation.result = result
        if error:
            operation.error = error
        operation.save()
        return operation
