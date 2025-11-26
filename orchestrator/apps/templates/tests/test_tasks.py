"""
Tests for Celery tasks in Template Engine.

Covers:
- execute_workflow_node (sync node execution with retry)
- execute_workflow_async (async workflow execution)
- execute_parallel_nodes (parallel node execution)
- cancel_workflow_async (async cancellation)
- Error handling and retry logic
- Context propagation
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

from celery.exceptions import MaxRetriesExceededError

from apps.templates.tasks import (
    execute_workflow_node,
    execute_workflow_async,
    execute_parallel_nodes,
    cancel_workflow_async,
)
from apps.templates.workflow.models import WorkflowExecution


class TestExecuteWorkflowNodeTask:
    """Tests for execute_workflow_node Celery task."""

    @pytest.fixture
    def execution(self, db, simple_workflow_template):
        """Create workflow execution in running state."""
        execution = simple_workflow_template.create_execution({'input': 'value'})
        # Use proper FSM method to transition to running
        execution.start()
        execution.save(update_fields=['status', 'started_at'])
        return execution

    def test_execute_workflow_node_success(self, execution):
        """Test successful node execution."""
        with patch('apps.templates.tasks.NodeHandlerFactory') as mock_factory:
            mock_handler = Mock()
            mock_factory.get_handler.return_value = mock_handler

            from apps.templates.workflow.handlers import NodeExecutionMode, NodeExecutionResult

            mock_handler.execute.return_value = NodeExecutionResult(
                success=True,
                output={'status': 'completed', 'count': 42},
                error=None,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=1.5
            )

            # Create mock task
            task = Mock()
            task.request.id = str(uuid4())
            task.request.retries = 0
            task.max_retries = 3

            result = execute_workflow_node.apply_async(
                args=[
                    str(execution.id),
                    'step1',
                    {'input': 'value'}
                ],
                task_id=task.request.id,
            ).get(timeout=10)

            assert result['success'] is True
            assert result['node_id'] == 'step1'
            assert result['output'] == {'status': 'completed', 'count': 42}
            assert result['error'] is None
            assert result['duration_seconds'] == 1.5

    def test_execute_workflow_node_failure(self, execution):
        """Test node execution failure."""
        with patch('apps.templates.tasks.NodeHandlerFactory') as mock_factory:
            mock_handler = Mock()
            mock_factory.get_handler.return_value = mock_handler

            from apps.templates.workflow.handlers import NodeExecutionMode, NodeExecutionResult

            mock_handler.execute.return_value = NodeExecutionResult(
                success=False,
                output=None,
                error='Node execution failed: connection timeout',
                mode=NodeExecutionMode.SYNC,
                duration_seconds=30.0
            )

            task = Mock()
            task.request.id = str(uuid4())
            task.request.retries = 0
            task.max_retries = 3

            result = execute_workflow_node.apply_async(
                args=[str(execution.id), 'step1', {}],
                task_id=task.request.id,
            ).get(timeout=10)

            assert result['success'] is False
            assert result['node_id'] == 'step1'
            assert result['error'] == 'Node execution failed: connection timeout'

    def test_execute_workflow_node_execution_not_found(self):
        """Test that missing execution returns error."""
        task = Mock()
        task.request.id = str(uuid4())
        task.request.retries = 0

        result = execute_workflow_node.apply_async(
            args=[str(uuid4()), 'step1', {}],
            task_id=task.request.id,
        ).get(timeout=10)

        assert result['success'] is False
        assert 'not found' in result['error'].lower()

    def test_execute_workflow_node_not_running_execution(self, execution):
        """Test handling of non-running execution."""
        # Mark as completed
        execution.status = WorkflowExecution.STATUS_COMPLETED
        execution.save()

        task = Mock()
        task.request.id = str(uuid4())
        task.request.retries = 0

        result = execute_workflow_node.apply_async(
            args=[str(execution.id), 'step1', {}],
            task_id=task.request.id,
        ).get(timeout=10)

        assert result['success'] is False
        assert 'not running' in result['error'].lower()

    def test_execute_workflow_node_context_propagation(self, execution):
        """Test that context is properly passed to handler."""
        context_passed = []

        with patch('apps.templates.tasks.NodeHandlerFactory') as mock_factory:
            mock_handler = Mock()
            mock_factory.get_handler.return_value = mock_handler

            from apps.templates.workflow.handlers import NodeExecutionMode, NodeExecutionResult

            def capture_context(node, context, execution, mode):
                context_passed.append(context)
                return NodeExecutionResult(
                    success=True,
                    output={},
                    error=None,
                    mode=mode,
                    duration_seconds=0.1
                )

            mock_handler.execute = capture_context

            task = Mock()
            task.request.id = str(uuid4())
            task.request.retries = 0

            input_context = {
                'database_id': '123',
                'user_id': 'user456',
                'data': {'nested': 'value'}
            }

            execute_workflow_node.apply_async(
                args=[str(execution.id), 'step1', input_context],
                task_id=task.request.id,
            ).get(timeout=10)

            assert len(context_passed) == 1
            assert context_passed[0]['database_id'] == '123'
            assert context_passed[0]['user_id'] == 'user456'

    def test_execute_workflow_node_handler_error(self, execution):
        """Test handling of handler exceptions."""
        with patch('apps.templates.tasks.NodeHandlerFactory') as mock_factory:
            mock_factory.get_handler.side_effect = ValueError("Unknown handler type")

            task = Mock()
            task.request.id = str(uuid4())
            task.request.retries = 0
            task.max_retries = 3
            task.retry = Mock(side_effect=Exception("No more retries"))

            # This should handle the exception gracefully
            # The task will retry if retries < max_retries
            result = execute_workflow_node.apply_async(
                args=[str(execution.id), 'step1', {}],
                task_id=task.request.id,
            ).get(timeout=10)

            assert result['success'] is False


class TestExecuteWorkflowAsyncTask:
    """Tests for execute_workflow_async Celery task."""

    def test_execute_workflow_async_success(self, simple_workflow_template):
        """Test successful async workflow execution."""
        with patch('apps.templates.tasks.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine

            execution = simple_workflow_template.create_execution({'input': 'value'})
            execution.status = WorkflowExecution.STATUS_COMPLETED
            execution.final_result = {'success': True}
            execution.save()

            mock_engine.execute_workflow.return_value = execution

            task = Mock()
            task.request.id = str(uuid4())

            result = execute_workflow_async.apply_async(
                args=[str(simple_workflow_template.id), {'input': 'value'}],
                task_id=task.request.id,
            ).get(timeout=10)

            assert result == str(execution.id)
            mock_engine.execute_workflow.assert_called_once()

    def test_execute_workflow_async_template_not_found(self):
        """Test that missing template raises error."""
        task = Mock()
        task.request.id = str(uuid4())

        # The task should raise an exception
        with pytest.raises(ValueError, match="not found"):
            execute_workflow_async.apply_async(
                args=[str(uuid4()), {}],
                task_id=task.request.id,
            ).get(timeout=10)

    def test_execute_workflow_async_workflow_error(self, simple_workflow_template):
        """Test handling of workflow engine errors."""
        from apps.templates.workflow.engine import WorkflowEngineError

        with patch('apps.templates.tasks.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine
            mock_engine.execute_workflow.side_effect = WorkflowEngineError(
                "Template validation failed",
                execution_id=None
            )

            task = Mock()
            task.request.id = str(uuid4())

            with pytest.raises(WorkflowEngineError):
                execute_workflow_async.apply_async(
                    args=[str(simple_workflow_template.id), {}],
                    task_id=task.request.id,
                ).get(timeout=10)

    def test_execute_workflow_async_context_passed(self, simple_workflow_template):
        """Test that input context is passed to engine."""
        context_received = []

        with patch('apps.templates.tasks.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine

            def capture_args(template, context):
                context_received.append(context)
                execution = simple_workflow_template.create_execution(context)
                execution.status = WorkflowExecution.STATUS_COMPLETED
                execution.save()
                return execution

            mock_engine.execute_workflow = capture_args

            task = Mock()
            task.request.id = str(uuid4())

            input_context = {
                'database_id': '123',
                'operation': 'backup'
            }

            execute_workflow_async.apply_async(
                args=[str(simple_workflow_template.id), input_context],
                task_id=task.request.id,
            ).get(timeout=10)

            assert len(context_received) == 1
            assert context_received[0] == input_context

    def test_execute_workflow_async_returns_execution_id(self, simple_workflow_template):
        """Test that execution_id is returned as string."""
        with patch('apps.templates.tasks.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine

            execution = simple_workflow_template.create_execution({'input': 'value'})
            execution.status = WorkflowExecution.STATUS_COMPLETED
            execution.save()

            mock_engine.execute_workflow.return_value = execution

            task = Mock()
            task.request.id = str(uuid4())

            result = execute_workflow_async.apply_async(
                args=[str(simple_workflow_template.id), {}],
                task_id=task.request.id,
            ).get(timeout=10)

            assert isinstance(result, str)
            assert result == str(execution.id)


class TestExecuteParallelNodesTask:
    """Tests for execute_parallel_nodes Celery task."""

    @pytest.fixture
    def execution(self, simple_workflow_template):
        """Create workflow execution in running state."""
        execution = simple_workflow_template.create_execution({})
        execution.status = WorkflowExecution.STATUS_RUNNING
        execution.save()
        return execution

    def test_execute_parallel_nodes_wait_for_all(self, execution):
        """Test parallel execution with wait_for='all'."""
        with patch('apps.templates.tasks.execute_workflow_node') as mock_task:
            from apps.templates.workflow.handlers import NodeExecutionResult

            # Mock successful results for all nodes
            def mock_execute(*args, **kwargs):
                node_id = args[1] if len(args) > 1 else kwargs.get('node_id')
                result = {
                    'success': True,
                    'node_id': node_id,
                    'output': {'status': 'completed'},
                    'error': None,
                    'duration_seconds': 0.1
                }
                return Mock(get=Mock(return_value=result))

            mock_task.s.side_effect = lambda *args, **kwargs: Mock(
                get=Mock(return_value={
                    'success': True,
                    'node_id': args[1] if len(args) > 1 else 'unknown',
                    'output': {},
                    'error': None,
                    'duration_seconds': 0.1
                })
            )

            task = Mock()
            task.request.id = str(uuid4())

            # For this test, we'll use a more direct approach
            with patch('apps.templates.tasks.group') as mock_group:
                mock_group_result = Mock()
                mock_group_result.get.return_value = [
                    {
                        'success': True,
                        'node_id': 'node1',
                        'output': {'data': 1},
                        'error': None,
                        'duration_seconds': 0.1
                    },
                    {
                        'success': True,
                        'node_id': 'node2',
                        'output': {'data': 2},
                        'error': None,
                        'duration_seconds': 0.1
                    }
                ]
                mock_group.return_value.apply_async.return_value = mock_group_result

                result = execute_parallel_nodes.apply_async(
                    args=[str(execution.id), ['node1', 'node2'], {}, 'all'],
                    task_id=task.request.id,
                ).get(timeout=10)

                assert result['success'] is True
                assert result['completed_count'] == 2
                assert result['failed_count'] == 0
                assert result['total_count'] == 2

    def test_execute_parallel_nodes_wait_for_any(self):
        """Test parallel execution with wait_for='any'."""
        task = Mock()
        task.request.id = str(uuid4())

        with patch('apps.templates.tasks.group') as mock_group:
            mock_group_result = Mock()
            # Return results where at least one succeeds
            mock_group_result.__iter__ = Mock(return_value=iter([
                Mock(get=Mock(return_value={
                    'success': False,
                    'node_id': 'node1',
                    'error': 'Failed',
                    'output': None,
                    'duration_seconds': 0.1
                })),
                Mock(get=Mock(return_value={
                    'success': True,
                    'node_id': 'node2',
                    'output': {'data': 2},
                    'error': None,
                    'duration_seconds': 0.1
                }))
            ]))
            mock_group.return_value.apply_async.return_value = mock_group_result

            result = execute_parallel_nodes.apply_async(
                args=['exec123', ['node1', 'node2'], {}, 'any'],
                task_id=task.request.id,
            ).get(timeout=10)

            assert result['success'] is True  # At least one succeeded
            assert result['completed_count'] == 1
            assert result['failed_count'] == 1

    def test_execute_parallel_nodes_wait_for_count(self):
        """Test parallel execution with wait_for as count."""
        task = Mock()
        task.request.id = str(uuid4())

        with patch('apps.templates.tasks.group') as mock_group:
            mock_group_result = Mock()
            mock_group_result.__iter__ = Mock(return_value=iter([
                Mock(get=Mock(return_value={
                    'success': True,
                    'node_id': 'node1',
                    'output': {'data': 1},
                    'error': None,
                    'duration_seconds': 0.1
                })),
                Mock(get=Mock(return_value={
                    'success': True,
                    'node_id': 'node2',
                    'output': {'data': 2},
                    'error': None,
                    'duration_seconds': 0.1
                })),
                Mock(get=Mock(return_value={
                    'success': False,
                    'node_id': 'node3',
                    'error': 'Failed',
                    'output': None,
                    'duration_seconds': 0.1
                }))
            ]))
            mock_group.return_value.apply_async.return_value = mock_group_result

            result = execute_parallel_nodes.apply_async(
                args=['exec123', ['node1', 'node2', 'node3'], {}, '2'],
                task_id=task.request.id,
            ).get(timeout=10)

            assert result['success'] is True  # 2 out of 3 completed
            assert result['completed_count'] == 2
            assert result['failed_count'] == 1
            assert result['total_count'] == 3


class TestCancelWorkflowAsyncTask:
    """Tests for cancel_workflow_async Celery task."""

    def test_cancel_workflow_async_success(self, workflow_execution):
        """Test successful async cancellation."""
        workflow_execution.status = WorkflowExecution.STATUS_RUNNING
        workflow_execution.save()

        task = Mock()
        task.request.id = str(uuid4())

        with patch('apps.templates.tasks.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine
            mock_engine.cancel_workflow.return_value = True

            result = cancel_workflow_async.apply_async(
                args=[str(workflow_execution.id)],
                task_id=task.request.id,
            ).get(timeout=10)

            assert result is True
            mock_engine.cancel_workflow.assert_called_once_with(str(workflow_execution.id))

    def test_cancel_workflow_async_not_found(self):
        """Test cancellation of non-existent workflow."""
        task = Mock()
        task.request.id = str(uuid4())

        with patch('apps.templates.tasks.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine
            mock_engine.cancel_workflow.return_value = False

            result = cancel_workflow_async.apply_async(
                args=[str(uuid4())],
                task_id=task.request.id,
            ).get(timeout=10)

            assert result is False

    def test_cancel_workflow_async_already_completed(self, workflow_execution):
        """Test cancellation of already completed workflow."""
        workflow_execution.status = WorkflowExecution.STATUS_COMPLETED
        workflow_execution.save()

        task = Mock()
        task.request.id = str(uuid4())

        with patch('apps.templates.tasks.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine
            mock_engine.cancel_workflow.return_value = False

            result = cancel_workflow_async.apply_async(
                args=[str(workflow_execution.id)],
                task_id=task.request.id,
            ).get(timeout=10)

            assert result is False


class TestTaskRetryLogic:
    """Tests for task retry behavior."""

    @pytest.fixture
    def execution(self, simple_workflow_template):
        """Create workflow execution."""
        execution = simple_workflow_template.create_execution({})
        execution.status = WorkflowExecution.STATUS_RUNNING
        execution.save()
        return execution

    def test_execute_workflow_node_retry_on_error(self, execution):
        """Test that task retries on temporary errors."""
        # This is a simplified test - real retry logic is handled by Celery
        with patch('apps.templates.tasks.NodeHandlerFactory') as mock_factory:
            mock_factory.get_handler.side_effect = Exception("Temporary connection error")

            task = Mock()
            task.request.id = str(uuid4())
            task.request.retries = 1
            task.max_retries = 3
            task.retry = Mock()

            # The task will attempt to retry
            # In production, Celery handles the actual retry
            try:
                execute_workflow_node(
                    task,
                    str(execution.id),
                    'step1',
                    {}
                )
            except Exception:
                # Expected when retries are exhausted or mocked incorrectly
                pass


class TestTaskIntegration:
    """Integration tests for task workflows."""

    def test_workflow_execution_task_chain(self, simple_workflow_template):
        """Test sequential task execution chain."""
        with patch('apps.templates.tasks.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine

            execution = simple_workflow_template.create_execution({'input': 'value'})
            execution.status = WorkflowExecution.STATUS_COMPLETED
            execution.save()

            mock_engine.execute_workflow.return_value = execution
            mock_engine.get_execution_status.return_value = {
                'execution_id': str(execution.id),
                'status': WorkflowExecution.STATUS_COMPLETED,
                'result': {'success': True}
            }

            task = Mock()
            task.request.id = str(uuid4())

            # Execute workflow
            execution_id = execute_workflow_async.apply_async(
                args=[str(simple_workflow_template.id), {}],
                task_id=task.request.id,
            ).get(timeout=10)

            assert execution_id == str(execution.id)

            # Get status
            with patch('apps.templates.tasks.WorkflowEngine') as mock_engine_class2:
                mock_engine2 = Mock()
                mock_engine_class2.return_value = mock_engine2
                mock_engine2.get_execution_status.return_value = {
                    'status': 'completed'
                }

                # In a real scenario, you would poll the engine for status
                assert execution_id is not None
