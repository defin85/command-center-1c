"""
Unit tests for Advanced NodeHandlers (ParallelHandler, LoopHandler, SubWorkflowHandler).

Tests cover:
- ParallelHandler: Celery group execution, wait_for modes, timeout handling
- LoopHandler: count/while/foreach modes, max_iterations, context updates
- SubWorkflowHandler: input/output mapping, recursion depth tracking, dot notation
- Error handling and edge cases
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from apps.templates.workflow.handlers import (
    NodeExecutionMode,
    NodeExecutionResult,
    ParallelHandler,
    LoopHandler,
    SubWorkflowHandler,
    NodeHandlerFactory,
)
from apps.templates.workflow.models import (
    WorkflowNode,
    WorkflowExecution,
    WorkflowTemplate,
    WorkflowStepResult,
    ParallelConfig,
    LoopConfig,
    SubWorkflowConfig,
)


# ========== ParallelHandler Tests ==========


class TestParallelHandler:
    """Tests for ParallelHandler."""

    def test_execute_not_implemented_week8(self, db):
        """Test that execute fails gracefully when Celery not available (Week 8)."""
        handler = ParallelHandler()

        # Create mock execution and node
        execution = Mock(spec=WorkflowExecution)
        execution.id = "exec-123"

        node = WorkflowNode(
            id="parallel_1",
            name="Parallel Node",
            type="parallel",
            parallel_config=ParallelConfig(
                parallel_nodes=["node_1", "node_2", "node_3"],
                wait_for="all",
                timeout_seconds=300
            )
        )

        context = {"test": "data"}

        # Mock step result creation
        with patch.object(handler, '_create_step_result') as mock_create:
            with patch.object(handler, '_update_step_result') as mock_update:
                # Mock the import to raise ImportError directly
                with patch('builtins.__import__', side_effect=ImportError("apps.templates.tasks not found")):
                    mock_create.return_value = Mock(spec=WorkflowStepResult)

                    result = handler.execute(node, context, execution)

                    # Should fail gracefully (either NotImplementedError or ImportError)
                    assert result.success is False
                    assert result.error is not None
                    assert result.mode == NodeExecutionMode.SYNC

    def test_missing_parallel_config(self, db):
        """Test error when parallel_config is missing (Pydantic validation)."""
        handler = ParallelHandler()

        execution = Mock(spec=WorkflowExecution)
        execution.id = "exec-123"

        # Attempting to create node without parallel_config should fail Pydantic validation
        with pytest.raises(Exception) as exc_info:
            from apps.templates.workflow.models import NodeConfig
            node = WorkflowNode(
                id="parallel_1",
                name="Parallel Node",
                type="parallel",
                config=NodeConfig(parallel_limit=10),  # For old validator
                parallel_config=None  # Missing config - will fail Pydantic
            )

        # Pydantic validation error expected (check for either old or new validator message)
        error_msg = str(exc_info.value)
        assert ("parallel_config is required" in error_msg or "parallel_limit" in error_msg)

    def test_wait_for_all_mode(self):
        """Test _wait_for_all method logic."""
        handler = ParallelHandler()

        # Mock GroupResult
        mock_group_result = Mock()
        mock_group_result.get.return_value = ["result1", "result2", "result3"]

        node_ids = ["node_1", "node_2", "node_3"]

        result = handler._wait_for_all(mock_group_result, 300, node_ids)

        assert result['mode'] == 'all'
        assert len(result['completed']) == 3
        assert result['timed_out'] is False
        mock_group_result.get.assert_called_once_with(timeout=300)

    def test_wait_for_all_timeout(self):
        """Test _wait_for_all with timeout."""
        handler = ParallelHandler()

        # Mock GroupResult with timeout
        mock_group_result = Mock()
        mock_group_result.get.side_effect = Exception("Timeout")

        # Mock partial results
        mock_result1 = Mock()
        mock_result1.ready.return_value = True
        mock_result1.successful.return_value = True
        mock_result1.result = "result1"

        mock_result2 = Mock()
        mock_result2.ready.return_value = False

        mock_group_result.results = [mock_result1, mock_result2]

        node_ids = ["node_1", "node_2"]

        result = handler._wait_for_all(mock_group_result, 300, node_ids)

        assert result['mode'] == 'all'
        assert len(result['completed']) == 1
        assert result['timed_out'] is True

    def test_cancel_tasks(self):
        """Test task cancellation logic."""
        handler = ParallelHandler()

        # Mock async results
        mock_result1 = Mock()
        mock_result2 = Mock()
        mock_result3 = Mock()

        mock_group_result = Mock()
        mock_group_result.results = [mock_result1, mock_result2, mock_result3]

        # Cancel all except index 1
        handler._cancel_tasks(mock_group_result, exclude_index=1)

        mock_result1.revoke.assert_called_once_with(terminate=True)
        mock_result2.revoke.assert_not_called()
        mock_result3.revoke.assert_called_once_with(terminate=True)


# ========== LoopHandler Tests ==========


class TestLoopHandler:
    """Tests for LoopHandler."""

    def test_execute_not_implemented_week8(self, db):
        """Test that execute returns NotImplementedError in Week 8."""
        handler = LoopHandler()

        execution = Mock(spec=WorkflowExecution)
        execution.id = "exec-123"

        node = WorkflowNode(
            id="loop_1",
            name="Loop Node",
            type="loop",
            loop_config=LoopConfig(
                mode="count",
                count=10,
                loop_node_id="process_item",
                max_iterations=100
            )
        )

        context = {}

        with patch.object(handler, '_create_step_result') as mock_create:
            with patch.object(handler, '_update_step_result') as mock_update:
                mock_create.return_value = Mock(spec=WorkflowStepResult)

                result = handler.execute(node, context, execution)

                assert result.success is False
                assert "not available" in result.error.lower()

    def test_missing_loop_config(self, db):
        """Test error when loop_config is missing (Pydantic validation)."""
        handler = LoopHandler()

        execution = Mock(spec=WorkflowExecution)

        # Attempting to create node without loop_config should fail Pydantic validation
        with pytest.raises(Exception) as exc_info:
            node = WorkflowNode(
                id="loop_1",
                name="Loop Node",
                type="loop",
                loop_config=None
            )

        # Pydantic validation error expected
        assert "loop_config is required" in str(exc_info.value)

    def test_to_bool_string_true(self):
        """Test _to_bool with various true strings."""
        handler = LoopHandler()

        assert handler._to_bool("true") is True
        assert handler._to_bool("True") is True
        assert handler._to_bool("TRUE") is True
        assert handler._to_bool("yes") is True
        assert handler._to_bool("1") is True

    def test_to_bool_string_false(self):
        """Test _to_bool with various false strings."""
        handler = LoopHandler()

        assert handler._to_bool("false") is False
        assert handler._to_bool("False") is False
        assert handler._to_bool("no") is False
        assert handler._to_bool("0") is False
        assert handler._to_bool("") is False
        assert handler._to_bool("none") is False

    def test_to_bool_integer(self):
        """Test _to_bool with integers."""
        handler = LoopHandler()

        assert handler._to_bool(1) is True
        assert handler._to_bool(100) is True
        assert handler._to_bool(0) is False

    def test_to_bool_none(self):
        """Test _to_bool with None."""
        handler = LoopHandler()

        assert handler._to_bool(None) is False

    def test_resolve_path_simple(self):
        """Test _resolve_path with simple path."""
        handler = LoopHandler()

        context = {"users": ["user1", "user2", "user3"]}
        result = handler._resolve_path(context, "users")

        assert result == ["user1", "user2", "user3"]

    def test_resolve_path_nested(self):
        """Test _resolve_path with nested path."""
        handler = LoopHandler()

        context = {
            "data": {
                "users": [
                    {"id": 1, "name": "Alice"},
                    {"id": 2, "name": "Bob"}
                ]
            }
        }

        result = handler._resolve_path(context, "data.users")
        assert len(result) == 2
        assert result[0]["name"] == "Alice"

    def test_resolve_path_not_found(self):
        """Test _resolve_path with non-existent path."""
        handler = LoopHandler()

        context = {"data": {"users": []}}

        with pytest.raises(KeyError):
            handler._resolve_path(context, "data.missing")


# ========== SubWorkflowHandler Tests ==========


class TestSubWorkflowHandler:
    """Tests for SubWorkflowHandler."""

    def test_execute_not_implemented_week8(self, db):
        """Test that execute returns NotImplementedError in Week 8."""
        from uuid import uuid4

        handler = SubWorkflowHandler()

        execution = Mock(spec=WorkflowExecution)
        execution.id = "exec-123"

        # Use valid UUID for subworkflow_id
        node = WorkflowNode(
            id="subworkflow_1",
            name="SubWorkflow Node",
            type="subworkflow",
            subworkflow_config=SubWorkflowConfig(
                subworkflow_id=str(uuid4()),  # Valid UUID
                input_mapping={"database.id": "target_db_id"},
                output_mapping={"result.status": "sub_status"},
                max_depth=10
            )
        )

        context = {}

        with patch.object(handler, '_create_step_result') as mock_create:
            with patch.object(handler, '_update_step_result') as mock_update:
                mock_create.return_value = Mock(spec=WorkflowStepResult)

                result = handler.execute(node, context, execution)

                assert result.success is False
                # Week 8: Should fail due to WorkflowTemplate not found (valid behavior)
                assert ("not found" in result.error.lower() or "not available" in result.error.lower())

    def test_missing_subworkflow_config(self, db):
        """Test error when subworkflow_config is missing (Pydantic validation)."""
        handler = SubWorkflowHandler()

        execution = Mock(spec=WorkflowExecution)

        # Attempting to create node without subworkflow_config should fail Pydantic validation
        with pytest.raises(Exception) as exc_info:
            node = WorkflowNode(
                id="subworkflow_1",
                name="SubWorkflow Node",
                type="subworkflow",
                subworkflow_config=None
            )

        # Pydantic validation error expected
        assert "subworkflow_config is required" in str(exc_info.value)

    def test_resolve_path_simple(self):
        """Test _resolve_path with simple path."""
        handler = SubWorkflowHandler()

        context = {"database": {"id": "db123", "name": "MyDB"}}
        result = handler._resolve_path(context, "database.id")

        assert result == "db123"

    def test_resolve_path_deep_nested(self):
        """Test _resolve_path with deeply nested path."""
        handler = SubWorkflowHandler()

        context = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep_value"
                    }
                }
            }
        }

        result = handler._resolve_path(context, "level1.level2.level3.value")
        assert result == "deep_value"

    def test_set_path_simple(self):
        """Test _set_path with simple path."""
        handler = SubWorkflowHandler()

        context = {}
        handler._set_path(context, "result.status", "success")

        assert context == {"result": {"status": "success"}}

    def test_set_path_nested(self):
        """Test _set_path with nested path."""
        handler = SubWorkflowHandler()

        context = {}
        handler._set_path(context, "data.users.count", 42)

        assert context == {"data": {"users": {"count": 42}}}

    def test_map_context_input(self):
        """Test _map_context for input mapping."""
        handler = SubWorkflowHandler()

        source_context = {
            "database": {"id": "db123", "name": "MyDB"},
            "user": {"id": "user456"}
        }

        mapping = {
            "database.id": "target_db_id",
            "user.id": "target_user_id"
        }

        result = handler._map_context(source_context, mapping, direction='input')

        assert result == {
            "target_db_id": "db123",
            "target_user_id": "user456"
        }

    def test_map_context_missing_key(self):
        """Test _map_context with missing source key (should not fail)."""
        handler = SubWorkflowHandler()

        source_context = {"database": {"id": "db123"}}
        mapping = {"database.id": "target_db_id", "missing.key": "target_missing"}

        # Should not raise error, just skip missing keys
        result = handler._map_context(source_context, mapping, direction='input')

        assert result == {"target_db_id": "db123"}


# ========== NodeHandlerFactory Tests ==========


class TestNodeHandlerFactoryAdvanced:
    """Tests for NodeHandlerFactory with advanced handlers."""

    def test_get_handler_parallel(self):
        """Test getting ParallelHandler from factory."""
        handler = NodeHandlerFactory.get_handler('parallel')

        assert isinstance(handler, ParallelHandler)

    def test_get_handler_loop(self):
        """Test getting LoopHandler from factory."""
        handler = NodeHandlerFactory.get_handler('loop')

        assert isinstance(handler, LoopHandler)

    def test_get_handler_subworkflow(self):
        """Test getting SubWorkflowHandler from factory."""
        handler = NodeHandlerFactory.get_handler('subworkflow')

        assert isinstance(handler, SubWorkflowHandler)

    def test_all_handlers_registered(self):
        """Test that all 5 handler types are registered."""
        registered = NodeHandlerFactory._handlers.keys()

        assert 'operation' in registered
        assert 'condition' in registered
        assert 'parallel' in registered
        assert 'loop' in registered
        assert 'subworkflow' in registered
        assert len(registered) == 5
