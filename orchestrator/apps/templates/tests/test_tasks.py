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


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def celery_eager_mode(settings):
    """
    Enable Celery eager mode for all tests in this module.

    In eager mode, tasks execute synchronously without needing a broker (Redis).
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture
def running_execution(db, simple_workflow_template):
    """
    Create workflow execution in running state using proper FSM transition.
    """
    execution = simple_workflow_template.create_execution({'input': 'value'})
    # Use FSM transition method (not direct assignment)
    execution.start()
    execution.save(update_fields=['status', 'started_at'])
    return execution


@pytest.fixture
def completed_execution(db, simple_workflow_template):
    """
    Create workflow execution in completed state using proper FSM transitions.
    """
    execution = simple_workflow_template.create_execution({'input': 'value'})
    execution.start()
    execution.save(update_fields=['status', 'started_at'])
    execution.complete(result={'success': True})
    execution.save(update_fields=['status', 'final_result', 'completed_at'])
    return execution


# ============================================================================
# TestExecuteWorkflowNodeTask
# ============================================================================

@pytest.mark.django_db
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
        # Patch at import location inside the function
        with patch('apps.templates.workflow.handlers.NodeHandlerFactory') as mock_factory:
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

            # In eager mode, apply_async executes synchronously
            result = execute_workflow_node.apply_async(
                args=[
                    str(execution.id),
                    'step1',
                    {'input': 'value'}
                ],
            ).get(timeout=10)

            assert result['success'] is True
            assert result['node_id'] == 'step1'
            assert result['output'] == {'status': 'completed', 'count': 42}
            assert result['error'] is None
            assert result['duration_seconds'] == 1.5

    def test_execute_workflow_node_failure(self, execution):
        """Test node execution failure."""
        with patch('apps.templates.workflow.handlers.NodeHandlerFactory') as mock_factory:
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

            result = execute_workflow_node.apply_async(
                args=[str(execution.id), 'step1', {}],
            ).get(timeout=10)

            assert result['success'] is False
            assert result['node_id'] == 'step1'
            assert result['error'] == 'Node execution failed: connection timeout'

    def test_execute_workflow_node_execution_not_found(self, db):
        """Test that missing execution returns error."""
        result = execute_workflow_node.apply_async(
            args=[str(uuid4()), 'step1', {}],
        ).get(timeout=10)

        assert result['success'] is False
        assert 'not found' in result['error'].lower()

    def test_execute_workflow_node_not_running_execution(self, completed_execution):
        """Test handling of non-running execution."""
        # completed_execution is already in COMPLETED state
        result = execute_workflow_node.apply_async(
            args=[str(completed_execution.id), 'step1', {}],
        ).get(timeout=10)

        assert result['success'] is False
        assert 'not running' in result['error'].lower()

    def test_execute_workflow_node_context_propagation(self, execution):
        """Test that context is properly passed to handler."""
        context_passed = []

        with patch('apps.templates.workflow.handlers.NodeHandlerFactory') as mock_factory:
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

            input_context = {
                'database_id': '123',
                'user_id': 'user456',
                'data': {'nested': 'value'}
            }

            execute_workflow_node.apply_async(
                args=[str(execution.id), 'step1', input_context],
            ).get(timeout=10)

            assert len(context_passed) == 1
            assert context_passed[0]['database_id'] == '123'
            assert context_passed[0]['user_id'] == 'user456'

    def test_execute_workflow_node_handler_error(self, execution):
        """Test handling of handler exceptions - task will retry."""
        from celery.exceptions import Retry

        with patch('apps.templates.workflow.handlers.NodeHandlerFactory') as mock_factory:
            mock_factory.get_handler.side_effect = ValueError("Unknown handler type")

            # In eager mode with EAGER_PROPAGATES=True, the Retry exception propagates.
            # The task attempts retry on exceptions (retries < max_retries).
            # This is the expected behavior for recoverable errors.
            with pytest.raises(Retry) as exc_info:
                execute_workflow_node.apply_async(
                    args=[str(execution.id), 'step1', {}],
                ).get(timeout=10)

            # Verify the original exception is in the retry
            assert 'Unknown handler type' in str(exc_info.value)


# ============================================================================
# TestExecuteWorkflowAsyncTask
# ============================================================================

@pytest.mark.django_db
class TestExecuteWorkflowAsyncTask:
    """Tests for execute_workflow_async Celery task."""

    def test_execute_workflow_async_success(self, simple_workflow_template):
        """Test successful async workflow execution."""
        with patch('apps.templates.workflow.engine.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine

            execution = simple_workflow_template.create_execution({'input': 'value'})
            # Properly transition to completed state
            execution.start()
            execution.save(update_fields=['status', 'started_at'])
            execution.complete(result={'success': True})
            execution.save(update_fields=['status', 'final_result', 'completed_at'])

            mock_engine.execute_workflow.return_value = execution

            result = execute_workflow_async.apply_async(
                args=[str(simple_workflow_template.id), {'input': 'value'}],
            ).get(timeout=10)

            assert result == str(execution.id)
            mock_engine.execute_workflow.assert_called_once()

    def test_execute_workflow_async_template_not_found(self, db):
        """Test that missing template raises error."""
        # The task should raise an exception
        with pytest.raises(ValueError, match="not found"):
            execute_workflow_async.apply_async(
                args=[str(uuid4()), {}],
            ).get(timeout=10)

    def test_execute_workflow_async_workflow_error(self, simple_workflow_template):
        """Test handling of workflow engine errors."""
        from apps.templates.workflow.engine import WorkflowEngineError

        with patch('apps.templates.workflow.engine.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine
            mock_engine.execute_workflow.side_effect = WorkflowEngineError(
                "Template validation failed",
                execution_id=None
            )

            with pytest.raises(WorkflowEngineError):
                execute_workflow_async.apply_async(
                    args=[str(simple_workflow_template.id), {}],
                ).get(timeout=10)

    def test_execute_workflow_async_context_passed(self, simple_workflow_template):
        """Test that input context is passed to engine."""
        context_received = []

        with patch('apps.templates.workflow.engine.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine

            def capture_args(template, context):
                context_received.append(context)
                execution = simple_workflow_template.create_execution(context)
                execution.start()
                execution.save(update_fields=['status', 'started_at'])
                execution.complete(result={'success': True})
                execution.save(update_fields=['status', 'final_result', 'completed_at'])
                return execution

            mock_engine.execute_workflow = capture_args

            input_context = {
                'database_id': '123',
                'operation': 'backup'
            }

            execute_workflow_async.apply_async(
                args=[str(simple_workflow_template.id), input_context],
            ).get(timeout=10)

            assert len(context_received) == 1
            assert context_received[0] == input_context

    def test_execute_workflow_async_returns_execution_id(self, simple_workflow_template):
        """Test that execution_id is returned as string."""
        with patch('apps.templates.workflow.engine.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine

            execution = simple_workflow_template.create_execution({'input': 'value'})
            execution.start()
            execution.save(update_fields=['status', 'started_at'])
            execution.complete(result={'success': True})
            execution.save(update_fields=['status', 'final_result', 'completed_at'])

            mock_engine.execute_workflow.return_value = execution

            result = execute_workflow_async.apply_async(
                args=[str(simple_workflow_template.id), {}],
            ).get(timeout=10)

            assert isinstance(result, str)
            assert result == str(execution.id)


# ============================================================================
# TestExecuteParallelNodesTask
# ============================================================================

@pytest.mark.django_db
class TestExecuteParallelNodesTask:
    """Tests for execute_parallel_nodes Celery task."""

    @pytest.fixture
    def execution(self, simple_workflow_template):
        """Create workflow execution in running state using FSM transition."""
        execution = simple_workflow_template.create_execution({})
        execution.start()  # FSM transition
        execution.save(update_fields=['status', 'started_at'])
        return execution

    def test_execute_parallel_nodes_wait_for_all(self, execution):
        """Test parallel execution with wait_for='all'."""
        # Mock the group from celery that is imported inside the task
        with patch('celery.group') as mock_group:
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
            ).get(timeout=10)

            assert result['success'] is True
            assert result['completed_count'] == 2
            assert result['failed_count'] == 0
            assert result['total_count'] == 2

    def test_execute_parallel_nodes_wait_for_any(self, execution):
        """Test parallel execution with wait_for='any'."""
        with patch('celery.group') as mock_group:
            mock_group_result = Mock()
            # Mock iterator for 'any' mode
            mock_results = [
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
            ]
            mock_group_result.__iter__ = Mock(return_value=iter(mock_results))
            mock_group.return_value.apply_async.return_value = mock_group_result

            result = execute_parallel_nodes.apply_async(
                args=[str(execution.id), ['node1', 'node2'], {}, 'any'],
            ).get(timeout=10)

            assert result['success'] is True  # At least one succeeded
            assert result['completed_count'] >= 1

    def test_execute_parallel_nodes_wait_for_count(self, execution):
        """Test parallel execution with wait_for as count."""
        with patch('celery.group') as mock_group:
            mock_group_result = Mock()
            mock_results = [
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
            ]
            mock_group_result.__iter__ = Mock(return_value=iter(mock_results))
            mock_group.return_value.apply_async.return_value = mock_group_result

            result = execute_parallel_nodes.apply_async(
                args=[str(execution.id), ['node1', 'node2', 'node3'], {}, '2'],
            ).get(timeout=10)

            assert result['success'] is True  # 2 out of 3 completed
            assert result['completed_count'] >= 2


# ============================================================================
# TestCancelWorkflowAsyncTask
# ============================================================================

@pytest.mark.django_db
class TestCancelWorkflowAsyncTask:
    """Tests for cancel_workflow_async Celery task."""

    def test_cancel_workflow_async_success(self, running_execution):
        """Test successful async cancellation."""
        with patch('apps.templates.workflow.engine.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine
            mock_engine.cancel_workflow.return_value = True

            result = cancel_workflow_async.apply_async(
                args=[str(running_execution.id)],
            ).get(timeout=10)

            assert result is True
            mock_engine.cancel_workflow.assert_called_once_with(str(running_execution.id))

    def test_cancel_workflow_async_not_found(self, db):
        """Test cancellation of non-existent workflow."""
        with patch('apps.templates.workflow.engine.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine
            mock_engine.cancel_workflow.return_value = False

            result = cancel_workflow_async.apply_async(
                args=[str(uuid4())],
            ).get(timeout=10)

            assert result is False

    def test_cancel_workflow_async_already_completed(self, completed_execution):
        """Test cancellation of already completed workflow."""
        with patch('apps.templates.workflow.engine.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine
            mock_engine.cancel_workflow.return_value = False

            result = cancel_workflow_async.apply_async(
                args=[str(completed_execution.id)],
            ).get(timeout=10)

            assert result is False


# ============================================================================
# TestTaskRetryLogic
# ============================================================================

@pytest.mark.django_db
class TestTaskRetryLogic:
    """Tests for task retry behavior."""

    @pytest.fixture
    def execution(self, simple_workflow_template):
        """Create workflow execution using FSM transition."""
        execution = simple_workflow_template.create_execution({})
        execution.start()
        execution.save(update_fields=['status', 'started_at'])
        return execution

    def test_execute_workflow_node_retry_on_error(self, execution):
        """Test that task attempts retry on errors."""
        from celery.exceptions import Retry

        with patch('apps.templates.workflow.handlers.NodeHandlerFactory') as mock_factory:
            mock_factory.get_handler.side_effect = Exception("Temporary connection error")

            # In eager mode with EAGER_PROPAGATES=True, Retry exception propagates.
            # The task attempts retry when retries < max_retries.
            with pytest.raises(Retry) as exc_info:
                execute_workflow_node.apply_async(
                    args=[str(execution.id), 'step1', {}],
                ).get(timeout=10)

            # Verify the original exception message is preserved
            assert 'Temporary connection error' in str(exc_info.value)


# ============================================================================
# TestTaskIntegration
# ============================================================================

@pytest.mark.django_db
class TestTaskIntegration:
    """Integration tests for task workflows."""

    def test_workflow_execution_task_chain(self, simple_workflow_template):
        """Test sequential task execution chain."""
        with patch('apps.templates.workflow.engine.WorkflowEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine

            execution = simple_workflow_template.create_execution({'input': 'value'})
            execution.start()
            execution.save(update_fields=['status', 'started_at'])
            execution.complete(result={'success': True})
            execution.save(update_fields=['status', 'final_result', 'completed_at'])

            mock_engine.execute_workflow.return_value = execution
            mock_engine.get_execution_status.return_value = {
                'execution_id': str(execution.id),
                'status': WorkflowExecution.STATUS_COMPLETED,
                'result': {'success': True}
            }

            # Execute workflow
            execution_id = execute_workflow_async.apply_async(
                args=[str(simple_workflow_template.id), {}],
            ).get(timeout=10)

            assert execution_id == str(execution.id)
