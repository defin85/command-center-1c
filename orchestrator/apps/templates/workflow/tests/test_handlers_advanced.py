"""
Unit tests for Advanced NodeHandlers (ParallelHandler, LoopHandler, SubWorkflowHandler).

Tests cover:
- ParallelHandler: Celery group execution, wait_for modes, timeout handling
- LoopHandler: count/while/foreach modes, max_iterations, context updates
- SubWorkflowHandler: input/output mapping, recursion depth tracking, dot notation
- Error handling and edge cases
"""

import asyncio
from concurrent.futures import Future
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from apps.templates.workflow.handlers import (
    NodeExecutionMode,
    ParallelHandler,
    LoopHandler,
    SubWorkflowHandler,
    NodeHandlerFactory,
)
from apps.templates.workflow.models import (
    WorkflowNode,
    WorkflowExecution,
    WorkflowStepResult,
    ParallelConfig,
    LoopConfig,
    SubWorkflowConfig,
    SubWorkflowRef,
    WorkflowTemplate,
    WorkflowType,
)


# ========== ParallelHandler Tests ==========


class TestParallelHandler:
    """Tests for ParallelHandler."""

    def test_execute_marks_failed_when_any_child_failed(self, db):
        """Parallel node should fail when any child node failed."""
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
            with patch.object(handler, '_update_step_result'):
                mock_create.return_value = Mock(spec=WorkflowStepResult)

                with patch.object(handler, '_execute_parallel') as mock_execute_parallel:
                    mock_execute_parallel.return_value = {
                        'mode': 'all',
                        'completed': [],
                        'failed': [{'node_id': 'node_2', 'error': 'boom'}],
                        'timed_out': False,
                    }

                    result = handler.execute(node, context, execution)

                    assert result.success is False
                    assert result.error is not None
                    assert result.mode == NodeExecutionMode.SYNC

    def test_missing_parallel_config(self, db):
        """Test error when parallel_config is missing (Pydantic validation)."""
        ParallelHandler()

        execution = Mock(spec=WorkflowExecution)
        execution.id = "exec-123"

        # Attempting to create node without parallel_config should fail Pydantic validation
        with pytest.raises(Exception) as exc_info:
            from apps.templates.workflow.models import NodeConfig
            WorkflowNode(
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

        node_ids = ["node_1", "node_2", "node_3"]
        f1 = Future()
        f2 = Future()
        f3 = Future()
        f1.set_result({'success': True})
        f2.set_result({'success': True})
        f3.set_result({'success': True})

        future_to_node = {f1: "node_1", f2: "node_2", f3: "node_3"}
        result = handler._wait_for_all(future_to_node, 300, node_ids)

        assert result['mode'] == 'all'
        assert len(result['completed']) == 3
        assert result['timed_out'] is False

    def test_wait_for_all_timeout(self):
        """Test _wait_for_all with timeout."""
        handler = ParallelHandler()

        node_ids = ["node_1", "node_2"]

        done_future = Future()
        pending_future = Future()
        done_future.set_result({'success': True})

        future_to_node = {done_future: "node_1", pending_future: "node_2"}
        result = handler._wait_for_all(future_to_node, 0, node_ids)

        assert result['mode'] == 'all'
        assert len(result['completed']) == 1
        assert result['timed_out'] is True

    def test_cancel_tasks(self):
        """Test task cancellation logic."""
        handler = ParallelHandler()

        f1 = Future()
        f2 = Future()
        f3 = Future()
        f1.cancel = Mock(wraps=f1.cancel)
        f2.cancel = Mock(wraps=f2.cancel)
        f3.cancel = Mock(wraps=f3.cancel)

        # f3 already completed, should not be cancelled
        f3.set_result({'success': True})

        future_to_node = {f1: "node_1", f2: "node_2", f3: "node_3"}
        cancelled = handler._cancel_tasks(future_to_node, exclude_node_ids={"node_2"})

        assert "node_1" in cancelled
        assert "node_2" not in cancelled
        assert "node_3" not in cancelled
        f1.cancel.assert_called_once()
        f2.cancel.assert_not_called()
        f3.cancel.assert_not_called()


# ========== LoopHandler Tests ==========


class TestLoopHandler:
    """Tests for LoopHandler."""

    def test_execute_count_mode_success(self, db):
        """Test that execute runs count loop successfully (Week 9 implementation)."""
        from uuid import uuid4
        handler = LoopHandler()

        execution = Mock(spec=WorkflowExecution)
        execution.id = uuid4()  # Use valid UUID

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
            with patch.object(handler, '_update_step_result'):
                mock_create.return_value = Mock(spec=WorkflowStepResult)

                result = handler.execute(node, context, execution)

                # Loop handler executes successfully (child tasks may fail due to mock)
                assert result.success is True
                assert 'iterations' in result.output
                assert result.output['iterations'] == 10
                assert result.output['mode'] == 'count'

    def test_missing_loop_config(self, db):
        """Test error when loop_config is missing (Pydantic validation)."""
        LoopHandler()

        Mock(spec=WorkflowExecution)

        # Attempting to create node without loop_config should fail Pydantic validation
        with pytest.raises(Exception) as exc_info:
            WorkflowNode(
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
        execution.bindings = []

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
            with patch.object(handler, '_update_step_result'):
                mock_create.return_value = Mock(spec=WorkflowStepResult)

                result = asyncio.run(handler.execute(node, context, execution))

                assert result.success is False
                # Week 8: Should fail due to WorkflowTemplate not found (valid behavior)
                assert ("not found" in result.error.lower() or "not available" in result.error.lower())

    def test_resolve_subworkflow_template_uses_matching_pinned_subworkflow_metadata(self, db):
        """Pinned subworkflow_ref resolves the pinned revision when metadata is consistent."""
        handler = SubWorkflowHandler()

        root = WorkflowTemplate.objects.create(
            name=f"approval-root-{uuid4().hex[:8]}",
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure={
                "nodes": [
                    {
                        "id": "noop",
                        "name": "Noop",
                        "type": "operation",
                        "template_id": "noop.template",
                    }
                ],
                "edges": [],
            },
            config={},
            is_valid=True,
            is_active=True,
            version_number=1,
        )
        pinned_revision = WorkflowTemplate.objects.create(
            name=root.name,
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure=root.dag_structure,
            config=root.config,
            is_valid=True,
            is_active=True,
            parent_version=root,
            version_number=7,
        )
        latest_revision = WorkflowTemplate.objects.create(
            name=root.name,
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure=root.dag_structure,
            config=root.config,
            is_valid=True,
            is_active=True,
            parent_version=root,
            version_number=8,
        )

        subworkflow_config = SubWorkflowConfig.model_construct(
            subworkflow_id=str(pinned_revision.id),
            subworkflow_ref=SubWorkflowRef.model_construct(
                binding_mode="pinned_revision",
                workflow_definition_key=str(root.id),
                workflow_revision_id=str(pinned_revision.id),
                workflow_revision=7,
            ),
            input_mapping={},
            output_mapping={},
            max_depth=10,
        )

        resolved = handler._resolve_subworkflow_template(subworkflow_config)

        assert str(resolved.id) == str(pinned_revision.id)

    def test_execute_uses_resolved_pinned_subworkflow_revision(self, db):
        """Runtime execution must pass resolver-selected pinned revision into WorkflowEngine."""
        handler = SubWorkflowHandler()
        execution = Mock(spec=WorkflowExecution)
        execution.id = "exec-123"
        execution.bindings = []

        root = WorkflowTemplate.objects.create(
            name=f"approval-exec-root-{uuid4().hex[:8]}",
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure={
                "nodes": [
                    {
                        "id": "noop",
                        "name": "Noop",
                        "type": "operation",
                        "template_id": "noop.template",
                    }
                ],
                "edges": [],
            },
            config={},
            is_valid=True,
            is_active=True,
            version_number=1,
        )
        pinned_revision = WorkflowTemplate.objects.create(
            name=root.name,
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure=root.dag_structure,
            config=root.config,
            is_valid=True,
            is_active=True,
            parent_version=root,
            version_number=7,
        )

        node = WorkflowNode.model_construct(
            id="subworkflow_1",
            name="SubWorkflow Node",
            type="subworkflow",
            subworkflow_config=SubWorkflowConfig.model_construct(
                subworkflow_id=str(pinned_revision.id),
                subworkflow_ref=SubWorkflowRef.model_construct(
                    binding_mode="pinned_revision",
                    workflow_definition_key=str(root.id),
                    workflow_revision_id=str(pinned_revision.id),
                    workflow_revision=7,
                ),
                input_mapping={},
                output_mapping={},
                max_depth=10,
            ),
        )

        captured_template_ids: list[str] = []
        nested_execution = Mock(spec=WorkflowExecution)
        nested_execution.final_result = {"approval": {"status": "ok"}}

        with patch.object(handler, "_create_step_result") as mock_create:
            with patch.object(handler, "_update_step_result"):
                mock_create.return_value = Mock(spec=WorkflowStepResult)
                with patch("apps.templates.workflow.engine.WorkflowEngine") as mock_engine_cls:
                    mock_engine = mock_engine_cls.return_value
                    with patch.object(
                        handler,
                        "_resolve_subworkflow_template",
                        return_value=pinned_revision,
                    ) as mock_resolve:

                        async def _execute_workflow(template, input_context):
                            captured_template_ids.append(str(template.id))
                            return nested_execution

                        mock_engine.execute_workflow = AsyncMock(side_effect=_execute_workflow)

                        result = asyncio.run(handler.execute(node, {}, execution))

        assert result.success is True
        mock_resolve.assert_called_once_with(node.subworkflow_config)
        assert captured_template_ids == [str(pinned_revision.id)]

    def test_execute_records_pinned_subworkflow_provenance_in_execution_bindings(self, db):
        """Successful pinned subworkflow execution must persist immutable provenance on parent execution."""
        handler = SubWorkflowHandler()
        execution = Mock(spec=WorkflowExecution)
        execution.id = "exec-123"
        execution.bindings = []

        root = WorkflowTemplate.objects.create(
            name=f"approval-provenance-root-{uuid4().hex[:8]}",
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure={
                "nodes": [
                    {
                        "id": "noop",
                        "name": "Noop",
                        "type": "operation",
                        "template_id": "noop.template",
                    }
                ],
                "edges": [],
            },
            config={},
            is_valid=True,
            is_active=True,
            version_number=1,
        )
        pinned_revision = WorkflowTemplate.objects.create(
            name=root.name,
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure=root.dag_structure,
            config=root.config,
            is_valid=True,
            is_active=True,
            parent_version=root,
            version_number=7,
        )

        node = WorkflowNode.model_construct(
            id="subworkflow_1",
            name="SubWorkflow Node",
            type="subworkflow",
            subworkflow_config=SubWorkflowConfig.model_construct(
                subworkflow_id=str(pinned_revision.id),
                subworkflow_ref=SubWorkflowRef.model_construct(
                    binding_mode="pinned_revision",
                    workflow_definition_key=str(root.id),
                    workflow_revision_id=str(pinned_revision.id),
                    workflow_revision=7,
                ),
                input_mapping={},
                output_mapping={},
                max_depth=10,
            ),
        )
        nested_execution = Mock(spec=WorkflowExecution)
        nested_execution.final_result = {"approval": {"status": "ok"}}

        with patch.object(handler, "_create_step_result") as mock_create:
            with patch.object(handler, "_update_step_result"):
                mock_create.return_value = Mock(spec=WorkflowStepResult)
                with patch("apps.templates.workflow.engine.WorkflowEngine") as mock_engine_cls:
                    mock_engine_cls.return_value.execute_workflow = AsyncMock(
                        return_value=nested_execution
                    )
                    with patch.object(
                        handler,
                        "_resolve_subworkflow_template",
                        return_value=pinned_revision,
                    ):

                        result = asyncio.run(handler.execute(node, {}, execution))

        assert result.success is True
        assert len(execution.bindings) == 1
        binding = execution.bindings[0]
        assert binding["target_ref"] == "workflow.subworkflow.subworkflow_1"
        assert binding["source_ref"] == f"subworkflow_ref:{root.id}@7"
        assert binding["status"] == "applied"
        assert binding["binding_mode"] == "pinned_revision"
        assert binding["provenance"]["workflow_revision_id"] == str(pinned_revision.id)
        assert binding["provenance"]["resolved_template_id"] == str(pinned_revision.id)
        assert binding["provenance"]["resolved_template_version"] == 7
        execution.save.assert_called_with(update_fields=["bindings"])

    def test_execute_records_failed_pinned_subworkflow_provenance_for_conflict(self, db):
        """Conflicting pinned metadata must surface as failed provenance in parent execution diagnostics."""
        handler = SubWorkflowHandler()
        execution = Mock(spec=WorkflowExecution)
        execution.id = "exec-123"
        execution.bindings = []

        root = WorkflowTemplate.objects.create(
            name=f"approval-failed-provenance-root-{uuid4().hex[:8]}",
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure={
                "nodes": [
                    {
                        "id": "noop",
                        "name": "Noop",
                        "type": "operation",
                        "template_id": "noop.template",
                    }
                ],
                "edges": [],
            },
            config={},
            is_valid=True,
            is_active=True,
            version_number=1,
        )
        pinned_revision = WorkflowTemplate.objects.create(
            name=root.name,
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure=root.dag_structure,
            config=root.config,
            is_valid=True,
            is_active=True,
            parent_version=root,
            version_number=7,
        )
        conflicting_revision = WorkflowTemplate.objects.create(
            name=root.name,
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure=root.dag_structure,
            config=root.config,
            is_valid=True,
            is_active=True,
            parent_version=root,
            version_number=8,
        )

        node = WorkflowNode.model_construct(
            id="subworkflow_1",
            name="SubWorkflow Node",
            type="subworkflow",
            subworkflow_config=SubWorkflowConfig.model_construct(
                subworkflow_id=str(conflicting_revision.id),
                subworkflow_ref=SubWorkflowRef.model_construct(
                    binding_mode="pinned_revision",
                    workflow_definition_key=str(root.id),
                    workflow_revision_id=str(pinned_revision.id),
                    workflow_revision=7,
                ),
                input_mapping={},
                output_mapping={},
                max_depth=10,
            ),
        )

        with patch.object(handler, "_create_step_result") as mock_create:
            with patch.object(handler, "_update_step_result"):
                mock_create.return_value = Mock(spec=WorkflowStepResult)

                result = asyncio.run(handler.execute(node, {}, execution))

        assert result.success is False
        assert "Pinned subworkflow conflict" in (result.error or "")
        assert len(execution.bindings) == 1
        binding = execution.bindings[0]
        assert binding["target_ref"] == "workflow.subworkflow.subworkflow_1"
        assert binding["source_ref"] == f"subworkflow_ref:{root.id}@7"
        assert binding["status"] == "failed"
        assert binding["binding_mode"] == "pinned_revision"
        assert "Pinned subworkflow conflict" in binding["reason"]
        assert binding["provenance"]["compatibility_subworkflow_id"] == str(conflicting_revision.id)
        assert binding["provenance"]["workflow_revision_id"] == str(pinned_revision.id)
        execution.save.assert_called_with(update_fields=["bindings"])

    def test_resolve_subworkflow_template_rejects_conflicting_pinned_metadata(self, db):
        """Conflicting compatibility and pinned metadata must fail closed."""
        handler = SubWorkflowHandler()

        root = WorkflowTemplate.objects.create(
            name=f"approval-conflict-root-{uuid4().hex[:8]}",
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure={
                "nodes": [
                    {
                        "id": "noop",
                        "name": "Noop",
                        "type": "operation",
                        "template_id": "noop.template",
                    }
                ],
                "edges": [],
            },
            config={},
            is_valid=True,
            is_active=True,
            version_number=1,
        )
        pinned_revision = WorkflowTemplate.objects.create(
            name=root.name,
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure=root.dag_structure,
            config=root.config,
            is_valid=True,
            is_active=True,
            parent_version=root,
            version_number=7,
        )
        conflicting_revision = WorkflowTemplate.objects.create(
            name=root.name,
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure=root.dag_structure,
            config=root.config,
            is_valid=True,
            is_active=True,
            parent_version=root,
            version_number=8,
        )

        subworkflow_config = SubWorkflowConfig.model_construct(
            subworkflow_id=str(conflicting_revision.id),
            subworkflow_ref=SubWorkflowRef.model_construct(
                binding_mode="pinned_revision",
                workflow_definition_key=str(root.id),
                workflow_revision_id=str(pinned_revision.id),
                workflow_revision=7,
            ),
            input_mapping={},
            output_mapping={},
            max_depth=10,
        )

        with pytest.raises(ValueError, match="Pinned subworkflow conflict"):
            handler._resolve_subworkflow_template(subworkflow_config)

    def test_resolve_subworkflow_template_rejects_drifted_pinned_revision(self, db):
        """Pinned subworkflow revision drift must fail closed."""
        handler = SubWorkflowHandler()

        root = WorkflowTemplate.objects.create(
            name=f"approval-drift-root-{uuid4().hex[:8]}",
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure={
                "nodes": [
                    {
                        "id": "noop",
                        "name": "Noop",
                        "type": "operation",
                        "template_id": "noop.template",
                    }
                ],
                "edges": [],
            },
            config={},
            is_valid=True,
            is_active=True,
            version_number=1,
        )
        pinned_revision = WorkflowTemplate.objects.create(
            name=root.name,
            workflow_type=WorkflowType.SEQUENTIAL,
            dag_structure=root.dag_structure,
            config=root.config,
            is_valid=True,
            is_active=True,
            parent_version=root,
            version_number=7,
        )

        subworkflow_config = SubWorkflowConfig.model_construct(
            subworkflow_id=str(pinned_revision.id),
            subworkflow_ref=SubWorkflowRef.model_construct(
                binding_mode="pinned_revision",
                workflow_definition_key=str(root.id),
                workflow_revision_id=str(pinned_revision.id),
                workflow_revision=8,
            ),
            input_mapping={},
            output_mapping={},
            max_depth=10,
        )

        with pytest.raises(ValueError, match="Pinned subworkflow revision mismatch"):
            handler._resolve_subworkflow_template(subworkflow_config)

    def test_resolve_subworkflow_template_rejects_missing_pinned_revision(self, db):
        """Missing pinned subworkflow revision must fail closed."""
        handler = SubWorkflowHandler()

        missing_revision_id = str(uuid4())
        subworkflow_config = SubWorkflowConfig.model_construct(
            subworkflow_id=missing_revision_id,
            subworkflow_ref=SubWorkflowRef.model_construct(
                binding_mode="pinned_revision",
                workflow_definition_key=str(uuid4()),
                workflow_revision_id=missing_revision_id,
                workflow_revision=7,
            ),
            input_mapping={},
            output_mapping={},
            max_depth=10,
        )

        with pytest.raises(ValueError, match="Pinned subworkflow template not found"):
            handler._resolve_subworkflow_template(subworkflow_config)

    def test_missing_subworkflow_config(self, db):
        """Test error when subworkflow_config is missing (Pydantic validation)."""
        SubWorkflowHandler()

        Mock(spec=WorkflowExecution)

        # Attempting to create node without subworkflow_config should fail Pydantic validation
        with pytest.raises(Exception) as exc_info:
            WorkflowNode(
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
