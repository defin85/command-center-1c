"""
Unit tests for ODataBackend.

Tests cover:
- Operation type support checks
- OData operation execution (create, update, delete, query)
- Error handling (timeout, factory errors, etc.)
- SYNC vs ASYNC modes
"""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from apps.templates.workflow.handlers.backends.odata import ODataBackend
from apps.templates.workflow.handlers.base import NodeExecutionMode


def _build_runtime_template(
    *,
    name: str,
    operation_type: str,
    target_entity: str,
    template_data: dict,
):
    return SimpleNamespace(
        id=str(uuid4()),
        name=name,
        operation_type=operation_type,
        target_entity=target_entity,
        template_data=template_data,
    )


class TestODataBackendOperationTypeSupport:
    """Tests for OData operation type support."""

    def test_supports_create(self):
        """Test ODataBackend supports create operation."""
        backend = ODataBackend()
        assert backend.supports_operation_type('create') is True

    def test_supports_update(self):
        """Test ODataBackend supports update operation."""
        backend = ODataBackend()
        assert backend.supports_operation_type('update') is True

    def test_supports_delete(self):
        """Test ODataBackend supports delete operation."""
        backend = ODataBackend()
        assert backend.supports_operation_type('delete') is True

    def test_supports_query(self):
        """Test ODataBackend supports query operation."""
        backend = ODataBackend()
        assert backend.supports_operation_type('query') is True

    def test_does_not_support_lock_scheduled_jobs(self):
        """Test ODataBackend does not support RAS lock_scheduled_jobs."""
        backend = ODataBackend()
        assert backend.supports_operation_type('lock_scheduled_jobs') is False

    def test_does_not_support_unlock_scheduled_jobs(self):
        """Test ODataBackend does not support RAS unlock_scheduled_jobs."""
        backend = ODataBackend()
        assert backend.supports_operation_type('unlock_scheduled_jobs') is False

    def test_does_not_support_terminate_sessions(self):
        """Test ODataBackend does not support RAS terminate_sessions."""
        backend = ODataBackend()
        assert backend.supports_operation_type('terminate_sessions') is False

    def test_does_not_support_block_sessions(self):
        """Test ODataBackend does not support RAS block_sessions."""
        backend = ODataBackend()
        assert backend.supports_operation_type('block_sessions') is False

    def test_does_not_support_unblock_sessions(self):
        """Test ODataBackend does not support RAS unblock_sessions."""
        backend = ODataBackend()
        assert backend.supports_operation_type('unblock_sessions') is False

    def test_get_supported_types(self):
        """Test get_supported_types returns all OData operation types."""
        supported_types = ODataBackend.get_supported_types()

        assert 'create' in supported_types
        assert 'update' in supported_types
        assert 'delete' in supported_types
        assert 'query' in supported_types

        # Should not contain RAS types
        assert 'lock_scheduled_jobs' not in supported_types
        assert 'unlock_scheduled_jobs' not in supported_types
        assert 'terminate_sessions' not in supported_types
        assert 'block_sessions' not in supported_types
        assert 'unblock_sessions' not in supported_types


class TestODataBackendExecution:
    """Tests for OData operation execution."""

    @pytest.mark.django_db
    def test_execute_create_sync_mode(
        self,
        database,
        create_operation_template,
        workflow_execution
    ):
        """Test create operation in SYNC mode."""
        backend = ODataBackend()

        with patch('apps.templates.workflow.handlers.backends.odata.BatchOperationFactory') as mock_factory:
            mock_operation = MagicMock()
            mock_operation.id = str(uuid4())
            mock_operation.total_tasks = 2
            mock_factory.create.return_value = mock_operation

            with patch('apps.operations.services.OperationsService.enqueue_operation') as mock_enqueue:
                mock_enqueue.return_value = MagicMock(
                    success=True,
                    operation_id="task-123",
                    status="queued",
                    error=None
                )

                with patch('apps.templates.workflow.handlers.backends.odata.ResultWaiter') as mock_waiter:
                    mock_waiter.wait.return_value = {
                        'success': True,
                        'status': 'completed',
                        'total_tasks': 2,
                        'completed_tasks': 2,
                        'error': None
                    }

                    result = backend.execute(
                        template=create_operation_template,
                        rendered_data={'name': 'Test', 'email': 'test@example.com'},
                        target_databases=[str(database.id)],
                        context={'user_id': 'test_user', 'timeout_seconds': 30},
                        execution=workflow_execution,
                        mode=NodeExecutionMode.SYNC
                    )

        assert result.success is True
        assert result.mode == NodeExecutionMode.SYNC
        assert result.operation_id == mock_operation.id
        assert result.task_id == 'task-123'
        assert result.output['backend'] == 'odata'
        assert result.output['status'] == 'completed'

    @pytest.mark.django_db
    def test_execute_update_sync_mode(
        self,
        database,
        update_operation_template,
        workflow_execution
    ):
        """Test update operation in SYNC mode."""
        backend = ODataBackend()

        with patch('apps.templates.workflow.handlers.backends.odata.BatchOperationFactory') as mock_factory:
            mock_operation = MagicMock()
            mock_operation.id = str(uuid4())
            mock_operation.total_tasks = 1
            mock_factory.create.return_value = mock_operation

            with patch('apps.operations.services.OperationsService.enqueue_operation') as mock_enqueue:
                mock_enqueue.return_value = MagicMock(
                    success=True,
                    operation_id="task-456",
                    status="queued",
                    error=None
                )

                with patch('apps.templates.workflow.handlers.backends.odata.ResultWaiter') as mock_waiter:
                    mock_waiter.wait.return_value = {
                        'success': True,
                        'status': 'completed',
                        'total_tasks': 1,
                        'completed_tasks': 1,
                        'error': None
                    }

                    result = backend.execute(
                        template=update_operation_template,
                        rendered_data={'id': '123', 'status': 'active'},
                        target_databases=[str(database.id)],
                        context={'user_id': 'test_user'},
                        execution=workflow_execution,
                        mode=NodeExecutionMode.SYNC
                    )

        assert result.success is True
        assert result.mode == NodeExecutionMode.SYNC

    @pytest.mark.django_db
    def test_execute_async_mode(
        self,
        database,
        create_operation_template,
        workflow_execution
    ):
        """Test ASYNC mode returns immediately after enqueueing."""
        backend = ODataBackend()

        with patch('apps.templates.workflow.handlers.backends.odata.BatchOperationFactory') as mock_factory:
            mock_operation = MagicMock()
            mock_operation.id = str(uuid4())
            mock_operation.total_tasks = 5
            mock_factory.create.return_value = mock_operation

            with patch('apps.operations.services.OperationsService.enqueue_operation') as mock_enqueue:
                mock_enqueue.return_value = MagicMock(
                    success=True,
                    operation_id="task-async",
                    status="queued",
                    error=None
                )

                result = backend.execute(
                    template=create_operation_template,
                    rendered_data={'name': 'Test'},
                    target_databases=[str(database.id)],
                    context={'user_id': 'test_user'},
                    execution=workflow_execution,
                    mode=NodeExecutionMode.ASYNC
                )

        # ASYNC should return immediately
        assert result.success is True
        assert result.mode == NodeExecutionMode.ASYNC
        assert result.output['status'] == 'queued'
        assert result.output['operation_id'] == mock_operation.id
        assert result.output['task_id'] == 'task-async'
        assert result.output['total_tasks'] == 5

    @pytest.mark.django_db
    def test_execute_with_timeout(
        self,
        database,
        create_operation_template,
        workflow_execution
    ):
        """Test execution respects timeout from context."""
        from apps.operations.waiter import OperationTimeoutError

        backend = ODataBackend()

        with patch('apps.templates.workflow.handlers.backends.odata.BatchOperationFactory') as mock_factory:
            mock_operation = MagicMock()
            mock_operation.id = str(uuid4())
            mock_factory.create.return_value = mock_operation

            with patch('apps.operations.services.OperationsService.enqueue_operation') as mock_enqueue:
                mock_enqueue.return_value = MagicMock(
                    success=True,
                    operation_id="task-123",
                    status="queued",
                    error=None
                )

                with patch('apps.templates.workflow.handlers.backends.odata.ResultWaiter') as mock_waiter:
                    # Simulate timeout
                    mock_waiter.wait.side_effect = OperationTimeoutError(
                        operation_id=mock_operation.id,
                        timeout_seconds=10
                    )

                    result = backend.execute(
                        template=create_operation_template,
                        rendered_data={},
                        target_databases=[str(database.id)],
                        context={'user_id': 'test_user', 'timeout_seconds': 10},
                        execution=workflow_execution,
                        mode=NodeExecutionMode.SYNC
                    )

        assert result.success is False
        assert 'timed out' in result.error.lower()
        assert result.operation_id == mock_operation.id

    @pytest.mark.django_db
    def test_execute_with_factory_error(
        self,
        database,
        create_operation_template,
        workflow_execution
    ):
        """Test execution handles factory creation errors."""
        backend = ODataBackend()

        with patch('apps.templates.workflow.handlers.backends.odata.BatchOperationFactory') as mock_factory:
            mock_factory.create.side_effect = Exception("Factory error")

            result = backend.execute(
                template=create_operation_template,
                rendered_data={},
                target_databases=[str(database.id)],
                context={'user_id': 'test_user'},
                execution=workflow_execution,
                mode=NodeExecutionMode.SYNC
            )

        assert result.success is False
        assert 'failed' in result.error.lower()

    @pytest.mark.django_db
    def test_execute_with_enqueue_error(
        self,
        database,
        create_operation_template,
        workflow_execution
    ):
        """Test execution handles enqueue errors."""
        backend = ODataBackend()

        with patch('apps.templates.workflow.handlers.backends.odata.BatchOperationFactory') as mock_factory:
            mock_operation = MagicMock()
            mock_operation.id = str(uuid4())
            mock_factory.create.return_value = mock_operation

            with patch('apps.operations.services.OperationsService.enqueue_operation') as mock_enqueue:
                mock_enqueue.side_effect = Exception("Queue error")

                result = backend.execute(
                    template=create_operation_template,
                    rendered_data={},
                    target_databases=[str(database.id)],
                    context={'user_id': 'test_user'},
                    execution=workflow_execution,
                    mode=NodeExecutionMode.SYNC
                )

        assert result.success is False
        assert 'failed' in result.error.lower()

    @pytest.mark.django_db
    def test_execute_operation_with_sync_failure(
        self,
        database,
        create_operation_template,
        workflow_execution
    ):
        """Test SYNC execution when operation fails."""
        backend = ODataBackend()

        with patch('apps.templates.workflow.handlers.backends.odata.BatchOperationFactory') as mock_factory:
            mock_operation = MagicMock()
            mock_operation.id = str(uuid4())
            mock_factory.create.return_value = mock_operation

            with patch('apps.operations.services.OperationsService.enqueue_operation') as mock_enqueue:
                mock_enqueue.return_value = MagicMock(
                    success=True,
                    operation_id="task-123",
                    status="queued",
                    error=None
                )

                with patch('apps.templates.workflow.handlers.backends.odata.ResultWaiter') as mock_waiter:
                    mock_waiter.wait.return_value = {
                        'success': False,
                        'status': 'failed',
                        'total_tasks': 2,
                        'completed_tasks': 1,
                        'error': 'OData error: Connection refused'
                    }

                    result = backend.execute(
                        template=create_operation_template,
                        rendered_data={},
                        target_databases=[str(database.id)],
                        context={'user_id': 'test_user'},
                        execution=workflow_execution,
                        mode=NodeExecutionMode.SYNC
                    )

        assert result.success is False
        assert result.output['status'] == 'failed'
        assert result.output['error'] == 'OData error: Connection refused'

    @pytest.mark.django_db
    def test_execute_delete_operation(
        self,
        database,
        workflow_execution
    ):
        """Test delete operation execution."""
        template = _build_runtime_template(
            name="Delete Records",
            operation_type='delete',
            target_entity="Users",
            template_data={"filter": "id = {{ id }}"},
        )

        backend = ODataBackend()

        with patch('apps.templates.workflow.handlers.backends.odata.BatchOperationFactory') as mock_factory:
            mock_operation = MagicMock()
            mock_operation.id = str(uuid4())
            mock_factory.create.return_value = mock_operation

            with patch('apps.operations.services.OperationsService.enqueue_operation') as mock_enqueue:
                mock_enqueue.return_value = MagicMock(
                    success=True,
                    operation_id="task-del",
                    status="queued",
                    error=None
                )

                with patch('apps.templates.workflow.handlers.backends.odata.ResultWaiter') as mock_waiter:
                    mock_waiter.wait.return_value = {
                        'success': True,
                        'status': 'completed',
                        'total_tasks': 1,
                        'completed_tasks': 1,
                        'error': None
                    }

                    result = backend.execute(
                        template=template,
                        rendered_data={'id': '123'},
                        target_databases=[str(database.id)],
                        context={'user_id': 'test_user'},
                        execution=workflow_execution,
                        mode=NodeExecutionMode.SYNC
                    )

        assert result.success is True

    @pytest.mark.django_db
    def test_execute_query_operation(
        self,
        database,
        workflow_execution
    ):
        """Test query operation execution."""
        template = _build_runtime_template(
            name="Query Records",
            operation_type='query',
            target_entity="Users",
            template_data={"filter": "status = '{{ status }}'"},
        )

        backend = ODataBackend()

        with patch('apps.templates.workflow.handlers.backends.odata.BatchOperationFactory') as mock_factory:
            mock_operation = MagicMock()
            mock_operation.id = str(uuid4())
            mock_factory.create.return_value = mock_operation

            with patch('apps.operations.services.OperationsService.enqueue_operation') as mock_enqueue:
                mock_enqueue.return_value = MagicMock(
                    success=True,
                    operation_id="task-query",
                    status="queued",
                    error=None
                )

                with patch('apps.templates.workflow.handlers.backends.odata.ResultWaiter') as mock_waiter:
                    mock_waiter.wait.return_value = {
                        'success': True,
                        'status': 'completed',
                        'total_tasks': 1,
                        'completed_tasks': 1,
                        'error': None,
                        'results': [{'id': '1', 'name': 'User 1'}]
                    }

                    result = backend.execute(
                        template=template,
                        rendered_data={'status': 'active'},
                        target_databases=[str(database.id)],
                        context={'user_id': 'test_user'},
                        execution=workflow_execution,
                        mode=NodeExecutionMode.SYNC
                    )

        assert result.success is True


        assert result.success is True


class TestODataBackendInitialization:
    """Tests for ODataBackend initialization."""

    def test_initialization_with_defaults(self):
        """Test ODataBackend initialization with defaults."""
        backend = ODataBackend()

        assert backend.DEFAULT_TIMEOUT_SECONDS == 300


class TestODataBackendIntegration:
    """Integration tests for ODataBackend."""

    @pytest.mark.django_db
    def test_execute_with_workflow_execution_context(
        self,
        database,
        create_operation_template,
        workflow_execution
    ):
        """Test that execution includes workflow_execution in factory call."""
        backend = ODataBackend()

        with patch('apps.templates.workflow.handlers.backends.odata.BatchOperationFactory') as mock_factory:
            mock_operation = MagicMock()
            mock_operation.id = str(uuid4())
            mock_factory.create.return_value = mock_operation

            with patch('apps.operations.services.OperationsService.enqueue_operation') as mock_enqueue:
                mock_enqueue.return_value = MagicMock(
                    success=True,
                    operation_id="task-123",
                    status="queued",
                    error=None
                )

                with patch('apps.templates.workflow.handlers.backends.odata.ResultWaiter') as mock_waiter:
                    mock_waiter.wait.return_value = {
                        'success': True,
                        'status': 'completed',
                        'total_tasks': 1,
                        'completed_tasks': 1,
                        'error': None
                    }

                    backend.execute(
                        template=create_operation_template,
                        rendered_data={},
                        target_databases=[str(database.id)],
                        context={'user_id': 'test_user', 'node_id': 'node1'},
                        execution=workflow_execution,
                        mode=NodeExecutionMode.SYNC
                    )

            # Verify factory was called with workflow execution
            call_kwargs = mock_factory.create.call_args[1]
            assert call_kwargs['workflow_execution_id'] == str(workflow_execution.id)
            assert call_kwargs['node_id'] == 'node1'
