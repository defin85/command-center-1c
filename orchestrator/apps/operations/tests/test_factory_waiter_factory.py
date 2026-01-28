import pytest
from uuid import uuid4

from apps.operations.factory import BatchOperationFactory
from apps.operations.models import BatchOperation, Task


@pytest.mark.django_db
class TestBatchOperationFactory:
    def test_create_basic_operation(self, operation_template, test_database):
        target_db_ids = [str(test_database.id)]
        rendered_data = {"result": "test_data"}

        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data=rendered_data,
            target_databases=target_db_ids,
        )

        assert operation is not None
        assert operation.id is not None
        assert operation.name == f"Manual: {operation_template.name}"
        assert operation.operation_type == "query"
        assert operation.target_entity in ["Users", operation_template.name]
        assert operation.payload == rendered_data
        assert operation.status == BatchOperation.STATUS_PENDING
        assert operation.total_tasks == 1
        assert operation.created_by == "system"

    def test_create_global_scope_creates_single_task_without_database(self, operation_template):
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={"options": {"target_scope": "global"}},
            target_databases=[],
        )

        assert operation.target_databases.count() == 0
        assert operation.total_tasks == 1
        task = operation.tasks.get()
        assert task.database_id is None
        assert task.status == Task.STATUS_PENDING

    def test_create_with_workflow_context(self, operation_template, test_database, workflow_execution):
        target_db_ids = [str(test_database.id)]
        rendered_data = {"action": "create"}

        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data=rendered_data,
            target_databases=target_db_ids,
            workflow_execution_id=str(workflow_execution.id),
            node_id="node_1",
            created_by="test_user",
        )

        assert operation.name == f"Workflow: {operation_template.name}"
        assert operation.metadata["workflow_execution_id"] == str(workflow_execution.id)
        assert operation.metadata["node_id"] == "node_1"
        assert operation.created_by == "test_user"

    def test_create_multiple_target_databases(self, operation_template, multiple_databases):
        target_db_ids = [str(db.id) for db in multiple_databases]

        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={"batch": True},
            target_databases=target_db_ids,
        )

        assert operation.total_tasks == 3
        assert operation.target_databases.count() == 3

        tasks = Task.objects.filter(batch_operation=operation)
        assert tasks.count() == 3

        for task in tasks:
            assert task.status == Task.STATUS_PENDING
            assert task.database in multiple_databases

    def test_create_empty_target_databases_raises_error(self, operation_template):
        with pytest.raises(ValueError, match="target_databases cannot be empty"):
            BatchOperationFactory.create(
                template=operation_template,
                rendered_data={},
                target_databases=[],
            )

    def test_create_with_missing_databases(self, operation_template, test_database):
        target_db_ids = [str(test_database.id), "nonexistent_id"]

        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=target_db_ids,
        )

        assert operation.total_tasks == 1
        assert operation.target_databases.count() == 1

    def test_operation_id_generation_workflow(self, operation_template, test_database):
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(test_database.id)],
            workflow_execution_id=str(uuid4()),
            node_id="node_" + ("x" * 80),
        )

        assert operation.id.startswith("batch-wf-")
        assert len(operation.id) <= 64

        tasks = Task.objects.filter(batch_operation=operation)
        assert tasks.count() == 1
        assert len(tasks[0].id) <= 64

    def test_operation_id_generation_manual(self, operation_template, test_database):
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(test_database.id)],
        )

        assert operation.id.startswith("batch-manual-")
        assert len(operation.id) <= 64

    def test_tasks_created_with_correct_status(self, operation_template, test_database):
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(test_database.id)],
        )

        tasks = Task.objects.filter(batch_operation=operation)
        assert all(task.status == Task.STATUS_PENDING for task in tasks)

    def test_operation_metadata_structure(self, operation_template, test_database):
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={"test": "data"},
            target_databases=[str(test_database.id)],
            workflow_execution_id="exec_id",
            node_id="node_id",
        )

        assert operation.metadata["workflow_execution_id"] == "exec_id"
        assert operation.metadata["node_id"] == "node_id"
