import time

import pytest

from apps.operations.factory import BatchOperationFactory
from apps.operations.models import BatchOperation, Task
from apps.operations.waiter import OperationTimeoutError, ResultWaiter


@pytest.mark.django_db
class TestResultWaiter:
    def test_wait_already_completed(self, operation_template, test_database):
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(test_database.id)],
        )

        operation.status = BatchOperation.STATUS_COMPLETED
        operation.progress = 100
        operation.completed_tasks = 1
        operation.save()

        Task.objects.create(
            id=f"{operation.id}-task1",
            batch_operation=operation,
            database=test_database,
            status=Task.STATUS_COMPLETED,
            result={"status": "ok"},
        )

        result = ResultWaiter.wait(operation.id, timeout_seconds=5)
        assert result["success"] is True
        assert result["status"] == BatchOperation.STATUS_COMPLETED
        assert result["progress"] == 100

    def test_wait_failed_operation(self, operation_template, test_database):
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(test_database.id)],
        )

        operation.status = BatchOperation.STATUS_FAILED
        operation.progress = 50
        operation.failed_tasks = 1
        operation.save()

        Task.objects.create(
            id=f"{operation.id}-task1",
            batch_operation=operation,
            database=test_database,
            status=Task.STATUS_FAILED,
            error_message="Database connection timeout",
            error_code="DB_TIMEOUT",
        )

        result = ResultWaiter.wait(operation.id, timeout_seconds=5)

        assert result["success"] is False
        assert result["status"] == BatchOperation.STATUS_FAILED
        assert result["error"] is not None
        assert "Database connection timeout" in result["error"]

    def test_wait_failed_operation_uses_metadata_error(self, operation_template, test_database):
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(test_database.id)],
        )

        operation.status = BatchOperation.STATUS_FAILED
        operation.metadata = {**(operation.metadata or {}), "error": "command is required"}
        operation.save(update_fields=["status", "metadata", "updated_at"])

        result = ResultWaiter.wait(operation.id, timeout_seconds=5)

        assert result["success"] is False
        assert result["status"] == BatchOperation.STATUS_FAILED
        assert result["error"] == "command is required"

    def test_wait_cancelled_operation(self, operation_template, test_database):
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(test_database.id)],
        )

        operation.status = BatchOperation.STATUS_CANCELLED
        operation.save()

        result = ResultWaiter.wait(operation.id, timeout_seconds=5)
        assert result["success"] is False
        assert result["status"] == BatchOperation.STATUS_CANCELLED
        assert "cancelled" in result["error"].lower()

    def test_wait_nonexistent_operation_raises_error(self):
        with pytest.raises(BatchOperation.DoesNotExist):
            ResultWaiter.wait("nonexistent_id", timeout_seconds=1)

    def test_wait_timeout(self, operation_template, test_database):
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(test_database.id)],
        )

        start = time.time()
        with pytest.raises(OperationTimeoutError) as exc_info:
            ResultWaiter.wait(operation.id, timeout_seconds=1, poll_interval_seconds=0.1)

        elapsed = time.time() - start
        assert 0.8 < elapsed < 1.5
        assert exc_info.value.operation_id == operation.id
        assert exc_info.value.timeout_seconds == 1

    def test_check_status_pending(self, operation_template, test_database):
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(test_database.id)],
        )

        status = ResultWaiter.check_status(operation.id)
        assert status["operation_id"] == operation.id
        assert status["status"] == BatchOperation.STATUS_PENDING
        assert status["is_terminal"] is False
        assert status["progress"] == 0

    def test_check_status_completed(self, operation_template, test_database):
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(test_database.id)],
        )

        operation.status = BatchOperation.STATUS_COMPLETED
        operation.progress = 100
        operation.completed_tasks = 1
        operation.save()

        status = ResultWaiter.check_status(operation.id)
        assert status["is_terminal"] is True
        assert status["status"] == BatchOperation.STATUS_COMPLETED

    def test_collect_task_results_multiple_tasks(self, operation_template, multiple_databases):
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(db.id) for db in multiple_databases],
        )

        tasks = list(operation.tasks.all().order_by("id"))
        assert len(tasks) == 3, "BatchOperationFactory should create 3 tasks"

        tasks[0].status = Task.STATUS_COMPLETED
        tasks[0].result = {"rows_affected": 10}
        tasks[0].save()

        tasks[1].status = Task.STATUS_FAILED
        tasks[1].error_message = "Connection refused"
        tasks[1].error_code = "CONN_ERROR"
        tasks[1].save()

        operation.status = BatchOperation.STATUS_FAILED
        operation.completed_tasks = 1
        operation.failed_tasks = 1
        operation.save()

        result = ResultWaiter.wait(operation.id, timeout_seconds=5)

        assert len(result["results"]) == 3
        statuses = {r["status"] for r in result["results"]}
        assert "completed" in statuses
        assert "failed" in statuses
        assert "pending" in statuses

        completed = next(r for r in result["results"] if r["status"] == "completed")
        failed = next(r for r in result["results"] if r["status"] == "failed")

        assert completed["success"] is True
        assert failed["success"] is False
        assert "Connection refused" in failed["error"]
