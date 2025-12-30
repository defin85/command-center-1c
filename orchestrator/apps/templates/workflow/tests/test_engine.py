"""
Tests for WorkflowEngine in Workflow Engine.

Covers:
- Singleton pattern
- Workflow execution lifecycle
- FSM state transitions
- Error handling
- Status tracking
- Thread safety
"""

import pytest
import threading
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from apps.templates.workflow.engine import WorkflowEngine, WorkflowEngineError, get_workflow_engine
from apps.templates.workflow.models import WorkflowExecution


class TestWorkflowEngineSingleton:
    """Tests for WorkflowEngine singleton pattern."""

    def teardown_method(self):
        """Reset singleton after each test."""
        WorkflowEngine.reset_singleton()

    def test_singleton_same_instance(self):
        """Test that multiple instantiations return same instance."""
        engine1 = WorkflowEngine()
        engine2 = WorkflowEngine()

        assert engine1 is engine2

    def test_singleton_thread_safe(self):
        """Test that singleton is thread-safe."""
        instances = []

        def create_instance():
            instances.append(WorkflowEngine())

        threads = [threading.Thread(target=create_instance) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # All instances should be the same
        assert all(inst is instances[0] for inst in instances)

    def test_get_workflow_engine_returns_singleton(self):
        """Test convenience function returns singleton."""
        engine1 = get_workflow_engine()
        engine2 = get_workflow_engine()

        assert engine1 is engine2
        assert isinstance(engine1, WorkflowEngine)

    def test_reset_singleton(self):
        """Test that reset_singleton() creates new instance."""
        engine1 = WorkflowEngine()
        WorkflowEngine.reset_singleton()
        engine2 = WorkflowEngine()

        assert engine1 is not engine2

    def test_singleton_only_initializes_once(self):
        """Test that __init__ only runs once due to singleton."""
        with patch('apps.templates.workflow.engine.logger') as mock_logger:
            WorkflowEngine()
            engine1_init_calls = mock_logger.info.call_count

            WorkflowEngine()
            engine2_init_calls = mock_logger.info.call_count

            # init should only log once
            assert engine2_init_calls == engine1_init_calls


class TestWorkflowEngineExecution:
    """Tests for workflow execution."""

    @pytest.fixture(autouse=True)
    def cleanup_singleton(self):
        """Clean up singleton after each test."""
        yield
        WorkflowEngine.reset_singleton()

    def test_execute_workflow_simple_success(self, simple_workflow_template):
        """Test successful workflow execution."""
        engine = WorkflowEngine()

        with patch('apps.templates.workflow.engine.DAGExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor
            mock_executor.execute = AsyncMock(return_value=(True, {
                'nodes': {
                    'step1': {'success': True, 'output': 'result1'},
                    'step2': {'success': True, 'output': 'result2'},
                }
            }))

            execution = engine.execute_workflow_sync(
                simple_workflow_template,
                {'input': 'test_value'}
            )

            assert execution.status == WorkflowExecution.STATUS_COMPLETED
            assert execution.final_result is not None
            assert execution.completed_at is not None

    def test_execute_workflow_failure(self, simple_workflow_template):
        """Test workflow execution failure."""
        engine = WorkflowEngine()

        with patch('apps.templates.workflow.engine.DAGExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor
            mock_executor.execute = AsyncMock(return_value=(False, {
                'error': 'Node execution failed',
                'node_id': 'step1'
            }))

            execution = engine.execute_workflow_sync(
                simple_workflow_template,
                {'input': 'test_value'}
            )

            assert execution.status == WorkflowExecution.STATUS_FAILED
            assert execution.error_message == 'Node execution failed'
            assert execution.error_node_id == 'step1'

    def test_execute_workflow_invalid_template(self, simple_workflow_template):
        """Test execution with invalid template."""
        engine = WorkflowEngine()

        # Mark template as invalid
        simple_workflow_template.is_valid = False
        simple_workflow_template.save()

        # Mock template.validate() to raise error
        with patch.object(simple_workflow_template, 'validate') as mock_validate:
            mock_validate.side_effect = ValueError("Invalid DAG: cycle detected")

            with pytest.raises(WorkflowEngineError, match="Template validation failed"):
                engine.execute_workflow_sync(simple_workflow_template, {})

    def test_execute_workflow_inactive_template(self, simple_workflow_template):
        """Test that inactive template cannot be executed."""
        engine = WorkflowEngine()

        simple_workflow_template.is_active = False
        simple_workflow_template.save()

        with pytest.raises(WorkflowEngineError, match="is not active"):
            engine.execute_workflow_sync(simple_workflow_template, {})

    def test_execute_workflow_creates_execution(self, simple_workflow_template):
        """Test that execute_workflow creates WorkflowExecution."""
        engine = WorkflowEngine()

        with patch('apps.templates.workflow.engine.DAGExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor
            mock_executor.execute = AsyncMock(return_value=(True, {}))

            execution = engine.execute_workflow_sync(
                simple_workflow_template,
                {'key': 'value'}
            )

            assert isinstance(execution, WorkflowExecution)
            assert execution.workflow_template == simple_workflow_template
            assert execution.input_context == {'key': 'value'}

    def test_execute_workflow_fsm_transitions(self, simple_workflow_template):
        """Test FSM state transitions during execution."""
        engine = WorkflowEngine()

        with patch('apps.templates.workflow.engine.DAGExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor
            mock_executor.execute = AsyncMock(return_value=(True, {'result': 'data'}))

            execution = engine.execute_workflow_sync(simple_workflow_template, {})

            # Check transitions: created -> pending -> running -> completed
            assert execution.status == WorkflowExecution.STATUS_COMPLETED
            assert execution.started_at is not None
            assert execution.completed_at is not None

    def test_execute_workflow_input_context_passed_to_dag(self, simple_workflow_template):
        """Test that input context is passed to DAGExecutor."""
        engine = WorkflowEngine()
        input_context = {'database_id': '123', 'user_id': 'user456'}

        with patch('apps.templates.workflow.engine.DAGExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor
            mock_executor.execute = AsyncMock(return_value=(True, {}))

            engine.execute_workflow_sync(simple_workflow_template, input_context)

            # Verify DAGExecutor was called with correct context
            mock_executor.execute.assert_called_once()
            call_args = mock_executor.execute.call_args
            context_arg = call_args[0][0]  # First positional argument

            assert context_arg.get('database_id') == '123'
            assert context_arg.get('user_id') == 'user456'


class TestWorkflowEngineCancel:
    """Tests for workflow cancellation."""

    @pytest.fixture(autouse=True)
    def cleanup_singleton(self):
        """Clean up singleton after each test."""
        yield
        WorkflowEngine.reset_singleton()

    @pytest.mark.django_db
    def test_cancel_workflow_success(self, db, workflow_execution):
        """Test successful workflow cancellation."""
        engine = WorkflowEngine()

        # Create a new pending execution (FSM starts in pending state)
        new_execution = WorkflowExecution.objects.create(
            workflow_template=workflow_execution.workflow_template,
            input_context={},
        )
        # Status is already STATUS_PENDING by default

        result = engine.cancel_workflow_sync(str(new_execution.id))

        assert result is True

        # Get fresh instance from DB (avoid FSM refresh_from_db issue)
        fresh_execution = WorkflowExecution.objects.get(id=new_execution.id)
        assert fresh_execution.status == WorkflowExecution.STATUS_CANCELLED

    @pytest.mark.django_db
    def test_cancel_workflow_running(self, db, workflow_execution):
        """Test cancellation of running workflow."""
        engine = WorkflowEngine()

        # Create a new execution and transition to running via FSM
        new_execution = WorkflowExecution.objects.create(
            workflow_template=workflow_execution.workflow_template,
            input_context={},
        )
        new_execution.start()  # FSM transition: pending -> running
        new_execution.save()

        result = engine.cancel_workflow_sync(str(new_execution.id))

        assert result is True

        # Get fresh instance from DB (avoid FSM refresh_from_db issue)
        fresh_execution = WorkflowExecution.objects.get(id=new_execution.id)
        assert fresh_execution.status == WorkflowExecution.STATUS_CANCELLED

    @pytest.mark.django_db
    def test_cancel_workflow_already_completed(self, db, workflow_execution):
        """Test that completed workflow cannot be cancelled."""
        engine = WorkflowEngine()

        # Create a new execution and transition to completed via FSM
        new_execution = WorkflowExecution.objects.create(
            workflow_template=workflow_execution.workflow_template,
            input_context={},
        )
        new_execution.start()  # pending -> running
        new_execution.complete({'success': True})  # running -> completed
        new_execution.save()

        result = engine.cancel_workflow_sync(str(new_execution.id))

        assert result is False

    def test_cancel_workflow_not_found(self):
        """Test cancellation of non-existent workflow."""
        engine = WorkflowEngine()

        result = engine.cancel_workflow_sync(str(uuid4()))

        assert result is False

    def test_cancel_workflow_error_handling(self):
        """Test error handling during cancellation."""
        engine = WorkflowEngine()

        with patch('apps.templates.workflow.engine.WorkflowExecution.objects.get') as mock_get:
            mock_get.side_effect = Exception("DB error")

            result = engine.cancel_workflow_sync('some-id')

            assert result is False


class TestWorkflowEngineStatus:
    """Tests for execution status retrieval."""

    @pytest.fixture(autouse=True)
    def cleanup_singleton(self):
        """Clean up singleton after each test."""
        yield
        WorkflowEngine.reset_singleton()

    @pytest.mark.django_db
    def test_get_execution_status_pending(self, workflow_execution):
        """Test getting status of pending execution."""
        engine = WorkflowEngine()

        # Create new execution in pending state (default)
        new_execution = WorkflowExecution.objects.create(
            workflow_template=workflow_execution.workflow_template,
            input_context={},
        )

        status = engine.get_execution_status_sync(str(new_execution.id))

        assert status['status'] == WorkflowExecution.STATUS_PENDING
        assert status['execution_id'] == str(new_execution.id)
        assert 'progress_percent' in status

    @pytest.mark.django_db
    def test_get_execution_status_running(self, workflow_execution):
        """Test getting status of running execution."""
        engine = WorkflowEngine()

        # Create and transition to running via FSM
        new_execution = WorkflowExecution.objects.create(
            workflow_template=workflow_execution.workflow_template,
            input_context={},
        )
        new_execution.start()  # FSM: pending -> running
        new_execution.save()

        status = engine.get_execution_status_sync(str(new_execution.id))

        assert status['status'] == WorkflowExecution.STATUS_RUNNING
        assert status['started_at'] is not None

    @pytest.mark.django_db
    def test_get_execution_status_completed(self, workflow_execution):
        """Test getting status of completed execution."""
        engine = WorkflowEngine()

        # Create and transition to completed via FSM
        new_execution = WorkflowExecution.objects.create(
            workflow_template=workflow_execution.workflow_template,
            input_context={},
        )
        new_execution.start()  # pending -> running
        new_execution.complete({'success': True})  # running -> completed
        new_execution.save()

        status = engine.get_execution_status_sync(str(new_execution.id))

        assert status['status'] == WorkflowExecution.STATUS_COMPLETED
        assert 'result' in status
        assert status['result'] == {'success': True}

    @pytest.mark.django_db
    def test_get_execution_status_failed(self, workflow_execution):
        """Test getting status of failed execution."""
        engine = WorkflowEngine()

        # Create and transition to failed via FSM
        new_execution = WorkflowExecution.objects.create(
            workflow_template=workflow_execution.workflow_template,
            input_context={},
        )
        new_execution.start()  # pending -> running
        new_execution.fail('Node execution failed', 'step1')  # running -> failed
        new_execution.save()

        status = engine.get_execution_status_sync(str(new_execution.id))

        assert status['status'] == WorkflowExecution.STATUS_FAILED
        assert 'error' in status
        assert status['error'] == 'Node execution failed'
        assert status['error_node_id'] == 'step1'

    @pytest.mark.django_db
    def test_get_execution_status_not_found(self, db):
        """Test getting status of non-existent execution."""
        engine = WorkflowEngine()

        status = engine.get_execution_status_sync(str(uuid4()))

        # May return 'not_found' or 'error' depending on implementation
        assert status['status'] in ['not_found', 'error']

    @pytest.mark.django_db
    def test_get_execution_status_error_handling(self):
        """Test error handling in get_execution_status."""
        engine = WorkflowEngine()

        with patch('apps.templates.workflow.engine.WorkflowExecution.objects.select_related') as mock_select:
            mock_select.return_value.get.side_effect = Exception("DB error")

            status = engine.get_execution_status_sync('some-id')

            assert status['status'] == 'error'
            assert 'error' in status


class TestWorkflowEngineGetExecution:
    """Tests for getting execution instance."""

    @pytest.fixture(autouse=True)
    def cleanup_singleton(self):
        """Clean up singleton after each test."""
        yield
        WorkflowEngine.reset_singleton()

    def test_get_execution_found(self, workflow_execution):
        """Test getting existing execution."""
        engine = WorkflowEngine()

        execution = engine.get_execution_sync(str(workflow_execution.id))

        assert execution is not None
        assert execution.id == workflow_execution.id

    @pytest.mark.django_db
    def test_get_execution_not_found(self):
        """Test getting non-existent execution."""
        engine = WorkflowEngine()

        execution = engine.get_execution_sync(str(uuid4()))

        assert execution is None

    @pytest.mark.django_db
    def test_get_execution_returns_fresh_instance(self, workflow_execution):
        """Test that get_execution returns fresh instance."""
        engine = WorkflowEngine()

        # Create new execution and transition via FSM
        new_execution = WorkflowExecution.objects.create(
            workflow_template=workflow_execution.workflow_template,
            input_context={},
        )
        new_execution.start()  # FSM: pending -> running
        new_execution.save()

        # Get fresh instance
        execution = engine.get_execution_sync(str(new_execution.id))

        assert execution.status == WorkflowExecution.STATUS_RUNNING


class TestWorkflowEngineIntegration:
    """Integration tests for WorkflowEngine."""

    @pytest.fixture(autouse=True)
    def cleanup_singleton(self):
        """Clean up singleton after each test."""
        yield
        WorkflowEngine.reset_singleton()

    def test_execute_workflow_full_flow(self, simple_workflow_template):
        """Test complete workflow execution flow."""
        engine = WorkflowEngine()

        with patch('apps.templates.workflow.engine.DAGExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor
            mock_executor.execute = AsyncMock(return_value=(True, {
                'nodes': {
                    'step1': {'success': True, 'output': {'status': 'ok'}},
                    'step2': {'success': True, 'output': {'count': 42}},
                },
                'status': 'completed'
            }))

            # Execute
            execution = engine.execute_workflow_sync(
                simple_workflow_template,
                {'database_id': '123'}
            )

            assert execution.status == WorkflowExecution.STATUS_COMPLETED
            assert execution.final_result is not None

            # Check status
            status = engine.get_execution_status_sync(str(execution.id))
            assert status['status'] == WorkflowExecution.STATUS_COMPLETED
            assert status['result'] is not None

    @pytest.mark.django_db
    def test_cancel_pending_workflow(self, simple_workflow_template):
        """Test cancelling a pending workflow before execution."""
        engine = WorkflowEngine()

        # Create execution directly (pending state)
        new_execution = WorkflowExecution.objects.create(
            workflow_template=simple_workflow_template,
            input_context={},
        )

        # Cancel it while still pending
        result = engine.cancel_workflow_sync(str(new_execution.id))

        assert result is True

        # Verify status changed (use fresh query to avoid FSM refresh issue)
        fresh_execution = WorkflowExecution.objects.get(id=new_execution.id)
        assert fresh_execution.status == WorkflowExecution.STATUS_CANCELLED

    def test_multiple_workflows_independent(self, simple_workflow_template):
        """Test that multiple workflow executions are independent."""
        engine = WorkflowEngine()

        with patch('apps.templates.workflow.engine.DAGExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor
            mock_executor.execute = AsyncMock(return_value=(True, {}))

            # Execute two workflows
            execution1 = engine.execute_workflow_sync(
                simple_workflow_template,
                {'input': 'value1'}
            )
            execution2 = engine.execute_workflow_sync(
                simple_workflow_template,
                {'input': 'value2'}
            )

            # Should have different IDs
            assert execution1.id != execution2.id

            # Should have independent input context
            assert execution1.input_context == {'input': 'value1'}
            assert execution2.input_context == {'input': 'value2'}
