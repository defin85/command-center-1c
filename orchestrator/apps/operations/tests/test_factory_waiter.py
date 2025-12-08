"""
Unit tests for Phase 4 Week 17: BatchOperationFactory and ResultWaiter.

Tests cover:
- BatchOperationFactory.create() - operation creation from templates
- BatchOperationFactory._generate_operation_id() - ID generation
- ResultWaiter.wait() - sync waiting with timeout and polling
- ResultWaiter.check_status() - status checking without waiting
- OperationHandler with target_databases - full integration flow
- Error handling and edge cases
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from uuid import uuid4


from apps.databases.models import Database
from apps.operations.factory import BatchOperationFactory
from apps.operations.models import BatchOperation, Task
from apps.operations.waiter import ResultWaiter, OperationTimeoutError
from apps.templates.models import OperationTemplate
from apps.templates.workflow.models import WorkflowTemplate


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_database(db):
    """Create a test database."""
    return Database.objects.create(
        id=str(uuid4())[:12],  # Short UUID for id field
        name="TestBase",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="test",
        password="test",
        status=Database.STATUS_ACTIVE,
    )


@pytest.fixture
def multiple_databases(db):
    """Create multiple test databases."""
    databases = []
    for i in range(3):
        db_obj = Database.objects.create(
            id=str(uuid4())[:12],
            name=f"TestBase{i}",
            host=f"server_{i}",
            port=80 + i,
            odata_url=f"http://server_{i}/odata",
            username="test",
            password="test",
            status=Database.STATUS_ACTIVE,
        )
        databases.append(db_obj)
    return databases


@pytest.fixture
def operation_template(db):
    """Create a test operation template."""
    return OperationTemplate.objects.create(
        id="test_template_" + str(uuid4())[:8],
        name="Test Operation Template",
        operation_type="query",
        target_entity="Users",
        template_data={"query": "SELECT * FROM Users"},
        description="Test template for factory",
    )


@pytest.fixture
def workflow_template(db):
    """Create a test workflow template."""
    return WorkflowTemplate.objects.create(
        id=str(uuid4()),
        name="Test Workflow Template",
        workflow_type="sequential",
        dag_structure={
            "nodes": [{
                "id": "test_node",
                "name": "Test Node",
                "type": "operation",
                "template_id": "test_template"
            }],
            "edges": []
        },
        is_valid=True,
        is_active=True,
    )


@pytest.fixture
def workflow_execution(db, workflow_template):
    """Create a workflow execution."""
    return workflow_template.create_execution({"test": "data"})


# ============================================================================
# BatchOperationFactory Tests
# ============================================================================

@pytest.mark.django_db
class TestBatchOperationFactory:
    """Tests for BatchOperationFactory.create()"""

    def test_create_basic_operation(self, operation_template, test_database):
        """Test creating a basic BatchOperation."""
        target_db_ids = [str(test_database.id)]
        rendered_data = {"result": "test_data"}

        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data=rendered_data,
            target_databases=target_db_ids,
        )

        # Verify operation was created
        assert operation is not None
        assert operation.id is not None
        assert operation.name == f"Manual: {operation_template.name}"
        assert operation.operation_type == "query"
        # target_entity is taken from rendered_data.get('entity', template.name)
        assert operation.target_entity in ["Users", operation_template.name]
        assert operation.payload == rendered_data
        assert operation.status == BatchOperation.STATUS_PENDING
        assert operation.total_tasks == 1
        assert operation.created_by == "system"

    def test_create_with_workflow_context(
        self, operation_template, test_database, workflow_execution
    ):
        """Test creating operation with workflow context."""
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

        # Verify workflow context is set
        assert operation.name == f"Workflow: {operation_template.name}"
        assert operation.metadata["workflow_execution_id"] == str(workflow_execution.id)
        assert operation.metadata["node_id"] == "node_1"
        assert operation.created_by == "test_user"

    def test_create_multiple_target_databases(
        self, operation_template, multiple_databases
    ):
        """Test creating operation with multiple target databases."""
        target_db_ids = [str(db.id) for db in multiple_databases]

        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={"batch": True},
            target_databases=target_db_ids,
        )

        # Verify operation and tasks
        assert operation.total_tasks == 3
        assert operation.target_databases.count() == 3

        # Verify tasks were created
        tasks = Task.objects.filter(batch_operation=operation)
        assert tasks.count() == 3

        for task in tasks:
            assert task.status == Task.STATUS_PENDING
            assert task.database in multiple_databases

    def test_create_empty_target_databases_raises_error(self, operation_template):
        """Test that empty target_databases raises ValueError."""
        with pytest.raises(ValueError, match="target_databases cannot be empty"):
            BatchOperationFactory.create(
                template=operation_template,
                rendered_data={},
                target_databases=[],  # Empty list
            )

    def test_create_with_missing_databases(self, operation_template, test_database):
        """Test creation with some missing databases (should warn but continue)."""
        # One real, one fake
        target_db_ids = [str(test_database.id), "nonexistent_id"]

        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=target_db_ids,
        )

        # Should create with only found databases
        assert operation.total_tasks == 1
        assert operation.target_databases.count() == 1

    def test_operation_id_generation_workflow(self, operation_template, test_database):
        """Test operation ID format for workflow operations."""
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(test_database.id)],
            workflow_execution_id="exec_123",
            node_id="node_456",
        )

        # Check ID format: batch-{workflow}-{node}-{timestamp}
        assert operation.id.startswith("batch-exec_123-node_456-")

    def test_operation_id_generation_manual(self, operation_template, test_database):
        """Test operation ID format for manual operations."""
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(test_database.id)],
        )

        # Check ID format: batch-manual-single-{timestamp}
        assert operation.id.startswith("batch-manual-single-")

    def test_tasks_created_with_correct_status(self, operation_template, test_database):
        """Test that tasks are created with correct initial status."""
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(test_database.id)],
        )

        tasks = Task.objects.filter(batch_operation=operation)
        assert all(task.status == Task.STATUS_PENDING for task in tasks)

    def test_operation_metadata_structure(self, operation_template, test_database):
        """Test that metadata is properly structured."""
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={"test": "data"},
            target_databases=[str(test_database.id)],
            workflow_execution_id="exec_id",
            node_id="node_id",
        )

        assert operation.metadata["workflow_execution_id"] == "exec_id"
        assert operation.metadata["node_id"] == "node_id"


# ============================================================================
# ResultWaiter Tests
# ============================================================================

@pytest.mark.django_db
class TestResultWaiter:
    """Tests for ResultWaiter.wait()"""

    def test_wait_already_completed(self, operation_template, test_database):
        """Test waiting for already completed operation."""
        # Create and mark as completed
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(test_database.id)],
        )

        # Manually mark as completed
        operation.status = BatchOperation.STATUS_COMPLETED
        operation.progress = 100
        operation.completed_tasks = 1
        operation.save()

        # Create corresponding task
        task = Task.objects.create(
            id=f"{operation.id}-task1",
            batch_operation=operation,
            database=test_database,
            status=Task.STATUS_COMPLETED,
            result={"status": "ok"},
        )

        # Wait should return immediately
        result = ResultWaiter.wait(operation.id, timeout_seconds=5)

        assert result["success"] is True
        assert result["status"] == BatchOperation.STATUS_COMPLETED
        assert result["progress"] == 100

    def test_wait_failed_operation(self, operation_template, test_database):
        """Test waiting for failed operation."""
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(test_database.id)],
        )

        # Mark as failed
        operation.status = BatchOperation.STATUS_FAILED
        operation.progress = 50
        operation.failed_tasks = 1
        operation.save()

        # Create failed task
        task = Task.objects.create(
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

    def test_wait_cancelled_operation(self, operation_template, test_database):
        """Test waiting for cancelled operation."""
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
        """Test waiting for nonexistent operation raises DoesNotExist."""
        with pytest.raises(BatchOperation.DoesNotExist):
            ResultWaiter.wait("nonexistent_id", timeout_seconds=1)

    def test_wait_timeout(self, operation_template, test_database):
        """Test timeout after specified seconds."""
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(test_database.id)],
        )

        # Leave in pending state (never completes)
        start = time.time()

        with pytest.raises(OperationTimeoutError) as exc_info:
            ResultWaiter.wait(
                operation.id,
                timeout_seconds=1,
                poll_interval_seconds=0.1
            )

        elapsed = time.time() - start

        # Should timeout after approximately 1 second
        assert 0.8 < elapsed < 1.5
        assert exc_info.value.operation_id == operation.id
        assert exc_info.value.timeout_seconds == 1

    def test_check_status_pending(self, operation_template, test_database):
        """Test check_status for pending operation."""
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
        """Test check_status for completed operation."""
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

    def test_collect_task_results_multiple_tasks(
        self, operation_template, multiple_databases
    ):
        """Test collecting results from multiple tasks."""
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={},
            target_databases=[str(db.id) for db in multiple_databases],
        )

        # Update existing tasks created by BatchOperationFactory
        tasks = list(operation.tasks.all().order_by('id'))
        assert len(tasks) == 3, "BatchOperationFactory should create 3 tasks"

        # Simulate different task outcomes by updating existing tasks
        tasks[0].status = Task.STATUS_COMPLETED
        tasks[0].result = {"rows_affected": 10}
        tasks[0].save()

        tasks[1].status = Task.STATUS_FAILED
        tasks[1].error_message = "Connection refused"
        tasks[1].error_code = "CONN_ERROR"
        tasks[1].save()

        # tasks[2] stays PENDING (default from factory)

        operation.status = BatchOperation.STATUS_FAILED
        operation.completed_tasks = 1
        operation.failed_tasks = 1
        operation.save()

        result = ResultWaiter.wait(operation.id, timeout_seconds=5)

        assert len(result["results"]) == 3
        # Check that we have expected task outcomes (order may vary)
        statuses = {r["status"] for r in result["results"]}
        assert "completed" in statuses
        assert "failed" in statuses
        assert "pending" in statuses

        # Find specific results
        completed = next(r for r in result["results"] if r["status"] == "completed")
        failed = next(r for r in result["results"] if r["status"] == "failed")

        assert completed["success"] is True
        assert failed["success"] is False
        assert "Connection refused" in failed["error"]


# ============================================================================
# OperationHandler with Target Databases Tests
# ============================================================================

@pytest.mark.django_db
class TestOperationHandlerTargetDatabases:
    """Tests for OperationHandler.execute() with target_databases integration."""

    def test_handler_creates_batch_operation(
        self, operation_template, test_database, workflow_execution
    ):
        """Test that OperationHandler creates BatchOperation with target_databases."""
        from apps.templates.workflow.handlers import OperationHandler, NodeExecutionMode
        from apps.templates.workflow.models import WorkflowNode

        node = WorkflowNode(
            id="op_node_1",
            name="Operation Node",
            type="operation",
            template_id=operation_template.id,
        )

        context = {
            "target_databases": [str(test_database.id)],
            "user_id": "test_user",
        }

        handler = OperationHandler()

        # Mock renderer to return valid data
        with patch.object(handler.renderer, 'render') as mock_render:
            mock_render.return_value = {"result": "test_data"}

            # Mock enqueue_operation (now in backends.odata)
            with patch('apps.templates.workflow.handlers.backends.odata.enqueue_operation') as mock_enqueue:
                mock_enqueue.delay.return_value = MagicMock(id="test_task_id")

                # Use ASYNC mode to test BatchOperation creation without waiting
                result = handler.execute(
                    node=node,
                    context=context,
                    execution=workflow_execution,
                    mode=NodeExecutionMode.ASYNC,
                )

        # Verify BatchOperation was created using operation_id from result
        assert result.operation_id is not None
        operation = BatchOperation.objects.get(id=result.operation_id)
        assert operation is not None
        assert operation.target_databases.count() == 1
        assert operation.total_tasks == 1

    def test_handler_async_mode_returns_immediately(
        self, operation_template, test_database, workflow_execution
    ):
        """Test ASYNC mode returns immediately without waiting."""
        from apps.templates.workflow.handlers import OperationHandler, NodeExecutionMode
        from apps.templates.workflow.models import WorkflowNode

        node = WorkflowNode(
            id="async_node",
            name="Async Operation",
            type="operation",
            template_id=operation_template.id,
        )

        context = {
            "target_databases": [str(test_database.id)],
        }

        handler = OperationHandler()

        with patch.object(handler.renderer, 'render') as mock_render:
            mock_render.return_value = {"data": "test"}

            with patch('apps.templates.workflow.handlers.backends.odata.enqueue_operation') as mock_enqueue:
                mock_enqueue.delay.return_value = MagicMock(id="celery_123")

                result = handler.execute(
                    node=node,
                    context=context,
                    execution=workflow_execution,
                    mode=NodeExecutionMode.ASYNC,
                )

        assert result.success is True
        assert result.mode == NodeExecutionMode.ASYNC
        assert result.output["status"] == "queued"
        assert result.operation_id is not None
        assert result.task_id == "celery_123"

    def test_handler_sync_mode_waits_for_completion(
        self, operation_template, test_database, workflow_execution
    ):
        """Test SYNC mode waits for operation completion."""
        from apps.templates.workflow.handlers import OperationHandler, NodeExecutionMode
        from apps.templates.workflow.models import WorkflowNode

        node = WorkflowNode(
            id="sync_node",
            name="Sync Operation",
            type="operation",
            template_id=operation_template.id,
        )

        context = {
            "target_databases": [str(test_database.id)],
        }

        # Create operation that will be marked complete
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={"test": "data"},
            target_databases=[str(test_database.id)],
        )

        # Mark as completed before handler runs
        operation.status = BatchOperation.STATUS_COMPLETED
        operation.progress = 100
        operation.completed_tasks = 1
        operation.save()

        handler = OperationHandler()

        with patch.object(handler.renderer, 'render') as mock_render:
            mock_render.return_value = {"test": "data"}

            with patch('apps.templates.workflow.handlers.backends.odata.enqueue_operation') as mock_enqueue:
                mock_enqueue.delay.return_value = MagicMock(id="celery_456")

                with patch('apps.templates.workflow.handlers.backends.odata.BatchOperationFactory.create') as mock_factory:
                    mock_factory.return_value = operation

                    result = handler.execute(
                        node=node,
                        context=context,
                        execution=workflow_execution,
                        mode=NodeExecutionMode.SYNC,
                    )

        assert result.success is True
        assert result.mode == NodeExecutionMode.SYNC
        assert result.operation_id == operation.id

    def test_handler_no_target_databases_skips_execution(
        self, operation_template, workflow_execution
    ):
        """Test that missing target_databases skips execution."""
        from apps.templates.workflow.handlers import OperationHandler, NodeExecutionMode
        from apps.templates.workflow.models import WorkflowNode

        node = WorkflowNode(
            id="skip_node",
            name="Skip Execution",
            type="operation",
            template_id=operation_template.id,
        )

        context = {}  # No target_databases

        handler = OperationHandler()

        with patch.object(handler.renderer, 'render') as mock_render:
            mock_render.return_value = {"data": "rendered"}

            result = handler.execute(
                node=node,
                context=context,
                execution=workflow_execution,
                mode=NodeExecutionMode.SYNC,
            )

        # Should return rendered data without creating operation
        assert result.success is True
        assert result.output["execution_skipped"] is True
        assert result.operation_id is None

        # No operation should be created
        assert BatchOperation.objects.count() == 0


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.django_db
class TestFactoryWaiterIntegration:
    """Integration tests for Factory + Waiter flow."""

    def test_full_workflow_create_wait_complete(
        self, operation_template, multiple_databases
    ):
        """Test full workflow: create operation -> modify status -> wait for result."""
        # 1. Create operation
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={"action": "sync"},
            target_databases=[str(db.id) for db in multiple_databases],
            workflow_execution_id="workflow_123",
            node_id="node_456",
        )

        assert operation.total_tasks == 3
        assert operation.status == BatchOperation.STATUS_PENDING

        # 2. Simulate task completion
        for i, task in enumerate(operation.tasks.all()):
            task.status = Task.STATUS_COMPLETED
            task.result = {"rows": i + 10}
            task.save()

        operation.status = BatchOperation.STATUS_COMPLETED
        operation.completed_tasks = 3
        operation.progress = 100
        operation.save()

        # 3. Wait for result
        result = ResultWaiter.wait(operation.id, timeout_seconds=5)

        assert result["success"] is True
        assert result["status"] == BatchOperation.STATUS_COMPLETED
        assert len(result["results"]) == 3
        assert all(r["success"] for r in result["results"])
        assert result["statistics"]["total_tasks"] == 3
        assert result["statistics"]["completed_tasks"] == 3


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.django_db
class TestErrorHandling:
    """Tests for error handling in factory and waiter."""

    def test_operation_timeout_error_has_correct_attributes(self):
        """Test OperationTimeoutError exception."""
        error = OperationTimeoutError(
            operation_id="op_123",
            timeout_seconds=300,
        )

        assert error.operation_id == "op_123"
        assert error.timeout_seconds == 300
        assert "op_123" in str(error)
        assert "300" in str(error)

    def test_factory_preserves_template_metadata(self, operation_template, test_database):
        """Test that factory preserves template information."""
        # Pass entity in rendered_data to verify it's used for target_entity
        operation = BatchOperationFactory.create(
            template=operation_template,
            rendered_data={"entity": "Users"},
            target_databases=[str(test_database.id)],
        )

        assert operation.template_id == operation_template.id
        assert operation.operation_type == operation_template.operation_type
        # target_entity comes from rendered_data['entity'] or falls back to template.name
        assert operation.target_entity == "Users"
