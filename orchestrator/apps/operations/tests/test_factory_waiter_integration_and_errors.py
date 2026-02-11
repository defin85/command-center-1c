import pytest

from apps.operations.factory import BatchOperationFactory
from apps.operations.models import BatchOperation, Task
from apps.operations.waiter import OperationTimeoutError, ResultWaiter


@pytest.mark.django_db
class TestFactoryWaiterIntegration:
    def test_full_workflow_create_wait_complete(self, operation_template, multiple_databases):
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={"action": "sync"},
            target_databases=[str(db.id) for db in multiple_databases],
            workflow_execution_id="workflow_123",
            node_id="node_456",
        )

        assert operation.total_tasks == 3
        assert operation.status == BatchOperation.STATUS_PENDING

        for i, task in enumerate(operation.tasks.all()):
            task.status = Task.STATUS_COMPLETED
            task.result = {"rows": i + 10}
            task.save()

        operation.status = BatchOperation.STATUS_COMPLETED
        operation.completed_tasks = 3
        operation.progress = 100
        operation.save()

        result = ResultWaiter.wait(operation.id, timeout_seconds=5)
        assert result["success"] is True
        assert result["status"] == BatchOperation.STATUS_COMPLETED
        assert len(result["results"]) == 3
        assert all(r["success"] for r in result["results"])
        assert result["statistics"]["total_tasks"] == 3
        assert result["statistics"]["completed_tasks"] == 3


@pytest.mark.django_db
class TestErrorHandling:
    def test_operation_timeout_error_has_correct_attributes(self):
        error = OperationTimeoutError(operation_id="op_123", timeout_seconds=300)
        assert error.operation_id == "op_123"
        assert error.timeout_seconds == 300
        assert "op_123" in str(error)
        assert "300" in str(error)

    def test_factory_preserves_template_metadata(self, operation_template, test_database):
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={"entity": "Users"},
            target_databases=[str(test_database.id)],
        )

        assert operation.metadata["template_id"] == operation_template.id
        assert operation.operation_type == operation_template.operation_type
        assert operation.target_entity == "Users"
