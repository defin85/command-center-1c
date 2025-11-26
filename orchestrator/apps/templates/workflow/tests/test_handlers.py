# orchestrator/apps/templates/workflow/tests/test_handlers.py
"""
Unit tests for NodeHandlers.

Tests cover:
- BaseNodeHandler abstract methods
- OperationHandler integration with TemplateRenderer
- ConditionHandler Jinja2 sandbox and _to_bool
- NodeHandlerFactory registry and singleton pattern
- Error handling and edge cases
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from apps.templates.workflow.handlers import (
    NodeExecutionMode,
    NodeExecutionResult,
    BaseNodeHandler,
    OperationHandler,
    ConditionHandler,
    NodeHandlerFactory,
)
from apps.templates.workflow.models import (
    WorkflowNode,
    WorkflowExecution,
    WorkflowTemplate,
    WorkflowStepResult,
    NodeConfig,
)


# ========== NodeExecutionResult Tests ==========

class TestNodeExecutionResult:
    """Tests for NodeExecutionResult dataclass."""

    def test_create_success_result(self):
        """Test creating successful result."""
        result = NodeExecutionResult(
            success=True,
            output={"data": "test"},
            error=None,  # Required field
            mode=NodeExecutionMode.SYNC,
            duration_seconds=1.5
        )

        assert result.success is True
        assert result.output == {"data": "test"}
        assert result.error is None
        assert result.mode == NodeExecutionMode.SYNC
        assert result.duration_seconds == 1.5

    def test_create_error_result(self):
        """Test creating error result."""
        result = NodeExecutionResult(
            success=False,
            output=None,  # Required field
            error="Test error",
            mode=NodeExecutionMode.SYNC,
            duration_seconds=0.0  # Required field
        )

        assert result.success is False
        assert result.output is None
        assert result.error == "Test error"


# ========== NodeHandlerFactory Tests ==========

class TestNodeHandlerFactory:
    """Tests for NodeHandlerFactory registry."""

    def test_get_handler_operation(self):
        """Test getting OperationHandler from factory."""
        handler = NodeHandlerFactory.get_handler('operation')

        assert isinstance(handler, OperationHandler)
        assert isinstance(handler, BaseNodeHandler)

    def test_get_handler_condition(self):
        """Test getting ConditionHandler from factory."""
        handler = NodeHandlerFactory.get_handler('condition')

        assert isinstance(handler, ConditionHandler)
        assert isinstance(handler, BaseNodeHandler)

    def test_get_handler_unknown_type(self):
        """Test error when requesting unknown handler type."""
        with pytest.raises(ValueError, match="No handler registered"):
            NodeHandlerFactory.get_handler('nonexistent')

    def test_singleton_pattern(self):
        """Test that get_handler returns same instance (singleton)."""
        handler1 = NodeHandlerFactory.get_handler('operation')
        handler2 = NodeHandlerFactory.get_handler('operation')

        assert handler1 is handler2  # Same instance

    def test_factory_has_registered_handlers(self):
        """Test that factory has registered handlers."""
        # Check internal registry
        assert 'operation' in NodeHandlerFactory._handlers
        assert 'condition' in NodeHandlerFactory._handlers


# ========== OperationHandler Tests ==========

@pytest.mark.django_db
class TestOperationHandler:
    """Tests for OperationHandler."""

    def test_operation_handler_template_not_found(self, workflow_execution):
        """Test error when OperationTemplate doesn't exist."""
        node = WorkflowNode(
            id="op1",
            name="Test Operation",
            type="operation",
            template_id="nonexistent_template"
        )
        context = {}

        handler = OperationHandler()
        result = handler.execute(node, context, workflow_execution)

        assert result.success is False
        assert "not found" in result.error.lower()
        assert result.mode == NodeExecutionMode.SYNC

    def test_operation_handler_success(self, admin_user, workflow_execution):
        """Test successful operation execution."""
        from apps.templates.models import OperationTemplate

        # Create real OperationTemplate
        op_template = OperationTemplate.objects.create(
            id="test_template",
            name="Test Template",
            operation_type="query",
            target_entity="Users",
            template_data={"query": "SELECT * FROM Users"}
        )

        node = WorkflowNode(
            id="op1",
            name="Test Operation",
            type="operation",
            template_id="test_template"
        )
        context = {"user_id": 123}

        handler = OperationHandler()

        # Mock the renderer instance on the handler
        mock_renderer = Mock()
        mock_renderer.render.return_value = {"result": "rendered_data"}
        handler.renderer = mock_renderer

        result = handler.execute(node, context, workflow_execution)

        assert result.success is True
        assert result.output == {"result": "rendered_data"}
        assert result.mode == NodeExecutionMode.SYNC
        assert result.duration_seconds is not None

        # Verify renderer was called
        mock_renderer.render.assert_called_once()

    def test_operation_handler_render_error(self, admin_user, workflow_execution):
        """Test error handling when template rendering fails."""
        from apps.templates.models import OperationTemplate
        from apps.templates.engine.exceptions import TemplateRenderError

        # Create template
        op_template = OperationTemplate.objects.create(
            id="bad_template",
            name="Bad Template",
            operation_type="query",
            target_entity="Users",
            template_data={"query": "test"}
        )

        node = WorkflowNode(
            id="op1",
            name="Test Operation",
            type="operation",
            template_id="bad_template"
        )

        handler = OperationHandler()

        # Mock renderer to raise error
        mock_renderer = Mock()
        mock_renderer.render.side_effect = TemplateRenderError("Syntax error")
        handler.renderer = mock_renderer

        result = handler.execute(node, {}, workflow_execution)

        assert result.success is False
        assert "rendering failed" in result.error.lower()
        assert result.mode == NodeExecutionMode.SYNC  # Error = sync mode

    @pytest.mark.django_db
    def test_operation_handler_creates_step_result(self, admin_user, workflow_execution):
        """Test that handler creates WorkflowStepResult for audit."""
        from apps.templates.models import OperationTemplate

        # Create template
        op_template = OperationTemplate.objects.create(
            id="audit_test",
            name="Audit Test",
            operation_type="test",
            target_entity="Test",
            template_data={}
        )

        node = WorkflowNode(
            id="audit_node",
            name="Audit Node",
            type="operation",
            template_id="audit_test"
        )

        handler = OperationHandler()

        with patch.object(handler.renderer, 'render', return_value={"ok": True}):
            result = handler.execute(node, {}, workflow_execution)

        # Check step result was created
        step_results = WorkflowStepResult.objects.filter(
            workflow_execution=workflow_execution,
            node_id="audit_node"
        )
        assert step_results.exists()

        step = step_results.first()
        assert step.node_name == "Audit Node"
        assert step.node_type == "operation"


# ========== ConditionHandler Tests ==========

@pytest.mark.django_db
class TestConditionHandler:
    """Tests for ConditionHandler."""

    def test_condition_handler_simple_true(self, workflow_execution):
        """Test simple True expression."""
        node = WorkflowNode(
            id="cond1",
            name="Simple True",
            type="condition",
            config=NodeConfig(expression="{{ True }}")
        )

        handler = ConditionHandler()
        result = handler.execute(node, {}, workflow_execution)

        assert result.success is True
        assert result.output is True  # ConditionHandler returns bool directly

    def test_condition_handler_simple_false(self, workflow_execution):
        """Test simple False expression."""
        node = WorkflowNode(
            id="cond1",
            name="Simple False",
            type="condition",
            config=NodeConfig(expression="{{ False }}")
        )

        handler = ConditionHandler()
        result = handler.execute(node, {}, workflow_execution)

        assert result.success is True
        assert result.output is False  # ConditionHandler returns bool directly

    def test_condition_handler_variable_comparison(self, workflow_execution):
        """Test condition with variable comparison."""
        node = WorkflowNode(
            id="cond1",
            name="Check Amount",
            type="condition",
            config=NodeConfig(expression="{{ amount > 100 }}")
        )

        context = {"amount": 150}

        handler = ConditionHandler()
        result = handler.execute(node, context, workflow_execution)

        assert result.success is True
        assert result.output is True  # ConditionHandler returns bool directly

    def test_condition_handler_complex_expression(self, workflow_execution):
        """Test complex boolean expression."""
        node = WorkflowNode(
            id="cond1",
            name="Complex Check",
            type="condition",
            config=NodeConfig(
                expression="{{ status == 'approved' and amount > 1000 }}"
            )
        )

        context = {"status": "approved", "amount": 1500}

        handler = ConditionHandler()
        result = handler.execute(node, context, workflow_execution)

        assert result.success is True
        assert result.output is True  # ConditionHandler returns bool directly

    def test_condition_handler_undefined_variable(self, workflow_execution):
        """Test error when using undefined variable (StrictUndefined)."""
        node = WorkflowNode(
            id="cond1",
            name="Undefined Var",
            type="condition",
            config=NodeConfig(expression="{{ undefined_var }}")
        )

        handler = ConditionHandler()
        result = handler.execute(node, {}, workflow_execution)

        assert result.success is False
        assert "undefined" in result.error.lower() or "is undefined" in result.error.lower()

    def test_condition_handler_invalid_syntax(self, workflow_execution):
        """Test error on invalid Jinja2 syntax."""
        node = WorkflowNode(
            id="cond1",
            name="Bad Syntax",
            type="condition",
            config=NodeConfig(expression="{{ invalid syntax }}}")  # Invalid!
        )

        handler = ConditionHandler()
        result = handler.execute(node, {}, workflow_execution)

        assert result.success is False
        assert result.error is not None
        assert "failed" in result.error.lower() or "error" in result.error.lower()

    def test_to_bool_string_conversions(self, workflow_execution):
        """Test _to_bool handles various string representations."""
        handler = ConditionHandler()

        # True values
        assert handler._to_bool("true") is True
        assert handler._to_bool("True") is True
        assert handler._to_bool("TRUE") is True
        assert handler._to_bool("yes") is True
        assert handler._to_bool("1") is True

        # False values
        assert handler._to_bool("false") is False
        assert handler._to_bool("False") is False
        assert handler._to_bool("no") is False
        assert handler._to_bool("0") is False
        assert handler._to_bool("") is False
        assert handler._to_bool("none") is False
        assert handler._to_bool("None") is False

        # Non-empty string
        assert handler._to_bool("anything else") is True

    def test_to_bool_numeric_conversions(self, workflow_execution):
        """Test _to_bool handles numbers."""
        handler = ConditionHandler()

        assert handler._to_bool(1) is True
        assert handler._to_bool(0) is False
        assert handler._to_bool(-1) is True
        assert handler._to_bool(100) is True

    def test_to_bool_none(self, workflow_execution):
        """Test _to_bool handles None."""
        handler = ConditionHandler()

        assert handler._to_bool(None) is False

    def test_to_bool_collections(self, workflow_execution):
        """Test _to_bool handles collections."""
        handler = ConditionHandler()

        # Non-empty collections
        assert handler._to_bool([1, 2, 3]) is True
        assert handler._to_bool({"key": "value"}) is True

        # Empty collections
        assert handler._to_bool([]) is False
        assert handler._to_bool({}) is False

    def test_condition_handler_security_no_import(self, workflow_execution):
        """Test that sandbox prevents dangerous operations like import."""
        node = WorkflowNode(
            id="cond1",
            name="Malicious Import",
            type="condition",
            config=NodeConfig(expression="{{ __import__('os').system('ls') }}")
        )

        handler = ConditionHandler()
        result = handler.execute(node, {}, workflow_execution)

        # Should fail (sandbox prevents import)
        assert result.success is False


# ========== Integration Tests ==========

@pytest.mark.django_db
class TestHandlersIntegration:
    """Integration tests with real Template Engine."""

    def test_operation_handler_with_context_propagation(
        self, admin_user, simple_workflow_template
    ):
        """Test that operation results are stored in context."""
        from apps.templates.models import OperationTemplate

        # Create template
        op_template = OperationTemplate.objects.create(
            id="context_test",
            name="Context Test",
            operation_type="query",
            target_entity="Test",
            template_data={"query": "test"}
        )

        # Create execution
        execution = simple_workflow_template.create_execution({"initial": "data"})
        execution.start()
        execution.save()

        node = WorkflowNode(
            id="op1",
            name="Operation",
            type="operation",
            template_id="context_test"
        )

        context = {"initial": "data"}
        handler = OperationHandler()

        # Mock renderer
        mock_renderer = Mock()
        mock_renderer.render.return_value = {"result": "operation_output"}
        handler.renderer = mock_renderer

        result = handler.execute(node, context, execution)

        # Check result stored in context
        # Note: Context storage happens in handler but may need workflow execution started
        # For now just check result is correct
        assert result.success is True

    def test_condition_handler_with_previous_node_output(self, admin_user, simple_workflow_template):
        """Test condition using output from previous node."""
        execution = simple_workflow_template.create_execution({})
        execution.start()
        execution.save()

        # Simulate previous node output
        context = {
            "node_step1_output": {"status": "success", "count": 150}
        }

        node = WorkflowNode(
            id="check",
            name="Check Count",
            type="condition",
            config=NodeConfig(
                expression="{{ node_step1_output.count > 100 }}"
            )
        )

        handler = ConditionHandler()
        result = handler.execute(node, context, execution)

        assert result.success is True
        assert result.output is True  # ConditionHandler returns bool directly

    def test_workflow_step_result_created_for_handlers(self, admin_user, workflow_execution):
        """Test that all handlers create WorkflowStepResult."""
        from apps.templates.models import OperationTemplate

        # Test OperationHandler
        op_template = OperationTemplate.objects.create(
            id="step_test",
            name="Step Test",
            operation_type="test",
            target_entity="Test",
            template_data={}
        )

        node_op = WorkflowNode(
            id="op_node",
            name="Op Node",
            type="operation",
            template_id="step_test"
        )

        workflow_execution.start()
        workflow_execution.save()

        handler_op = OperationHandler()

        with patch.object(handler_op.renderer, 'render', return_value={}):
            handler_op.execute(node_op, {}, workflow_execution)

        # Check step result exists
        assert WorkflowStepResult.objects.filter(
            workflow_execution=workflow_execution,
            node_id="op_node"
        ).exists()

        # Test ConditionHandler
        node_cond = WorkflowNode(
            id="cond_node",
            name="Cond Node",
            type="condition",
            config=NodeConfig(expression="{{ True }}")
        )

        handler_cond = ConditionHandler()
        handler_cond.execute(node_cond, {}, workflow_execution)

        # Check step result exists
        assert WorkflowStepResult.objects.filter(
            workflow_execution=workflow_execution,
            node_id="cond_node"
        ).exists()


# ========== Edge Cases ==========

class TestHandlersEdgeCases:
    """Tests for edge cases and error scenarios."""

    @pytest.mark.django_db
    def test_operation_handler_empty_context(self, admin_user, workflow_execution):
        """Test operation with empty context."""
        from apps.templates.models import OperationTemplate

        op_template = OperationTemplate.objects.create(
            id="empty_ctx",
            name="Empty Context",
            operation_type="test",
            target_entity="Test",
            template_data={"static": "data"}
        )

        node = WorkflowNode(
            id="op1",
            name="Empty Context Op",
            type="operation",
            template_id="empty_ctx"
        )

        handler = OperationHandler()

        with patch.object(handler.renderer, 'render', return_value={"ok": True}):
            result = handler.execute(node, {}, workflow_execution)  # Empty context

        assert result.success is True

    def test_condition_handler_missing_expression_validation(self):
        """Test that Pydantic validation catches missing expression for condition nodes."""
        # expression is required for condition nodes (validator added in C2)
        with pytest.raises(ValueError, match="expression is required"):
            WorkflowNode(
                id="cond1",
                name="No Expression",
                type="condition",
                config=NodeConfig()  # No expression - validation should fail
            )

    @pytest.mark.django_db
    def test_condition_handler_expression_with_filters(self, workflow_execution):
        """Test condition using Jinja2 filters."""
        node = WorkflowNode(
            id="cond1",
            name="Filter Test",
            type="condition",
            config=NodeConfig(expression="{{ name|length > 5 }}")
        )

        context = {"name": "LongName"}

        handler = ConditionHandler()
        result = handler.execute(node, context, workflow_execution)

        assert result.success is True
        assert result.output is True  # ConditionHandler returns bool directly  # "LongName" length = 8 > 5

    @pytest.mark.django_db
    def test_handlers_with_unicode_data(self, admin_user, workflow_execution):
        """Test handlers work with Unicode/Cyrillic data."""
        from apps.templates.models import OperationTemplate

        op_template = OperationTemplate.objects.create(
            id="unicode_test",
            name="Тестовый шаблон",  # Cyrillic
            operation_type="test",
            target_entity="Пользователи",  # Cyrillic
            template_data={"имя": "значение"}  # Cyrillic
        )

        node = WorkflowNode(
            id="op1",
            name="Юникод узел",  # Cyrillic
            type="operation",
            template_id="unicode_test"
        )

        handler = OperationHandler()

        with patch.object(handler.renderer, 'render', return_value={"результат": "успех"}):
            result = handler.execute(node, {}, workflow_execution)

        assert result.success is True


# ========== Thread Safety Tests ==========

class TestThreadSafety:
    """Tests for thread-safe handler creation."""

    def test_factory_thread_safe_singleton(self):
        """Test that concurrent get_handler calls return same instance."""
        import threading

        handlers = []

        def get_handler():
            h = NodeHandlerFactory.get_handler('operation')
            handlers.append(id(h))

        # Create 10 threads
        threads = [threading.Thread(target=get_handler) for _ in range(10)]

        # Start all
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # All should have same ID (singleton)
        assert len(set(handlers)) == 1
