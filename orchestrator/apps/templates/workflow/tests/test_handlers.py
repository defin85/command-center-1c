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
from unittest.mock import Mock, patch
from uuid import uuid4

from apps.runtime_settings.models import RuntimeSetting
from apps.templates.models import OperationDefinition, OperationExposure
from apps.templates.workflow.decision_tables import create_decision_table_revision
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
    WorkflowStepResult,
    NodeConfig,
)


def _create_template_exposure(
    *,
    template_id: str,
    name: str,
    operation_type: str,
    target_entity: str,
    template_data: object,
    contract_version: int = 1,
    is_active: bool = True,
    status: str = OperationExposure.STATUS_PUBLISHED,
    executor_kind: str = OperationDefinition.EXECUTOR_DESIGNER_CLI,
    system_managed: bool = False,
    domain: str = "",
) -> OperationExposure:
    definition = OperationDefinition.objects.create(
        tenant_scope="global",
        executor_kind=executor_kind,
        executor_payload={
            "operation_type": operation_type,
            "target_entity": target_entity,
            "template_data": template_data,
        },
        contract_version=contract_version,
        fingerprint=f"fp-{template_id}",
        status=OperationDefinition.STATUS_ACTIVE,
    )
    return OperationExposure.objects.create(
        definition=definition,
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias=template_id,
        tenant=None,
        label=name,
        description="",
        is_active=is_active,
        capability="",
        contexts=[],
        display_order=0,
        capability_config={},
        status=status,
        system_managed=system_managed,
        domain=domain,
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
        """Test error when template exposure alias doesn't exist."""
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

    def test_operation_handler_rejects_alias_latest_when_runtime_enforce_pinned_enabled(
        self,
        workflow_execution,
    ):
        _create_template_exposure(
            template_id="enforce_template",
            name="Enforce Template",
            operation_type="query",
            target_entity="Users",
            template_data={"query": "SELECT 1"},
        )
        RuntimeSetting.objects.update_or_create(
            key="workflows.operation_binding.enforce_pinned",
            defaults={"value": True},
        )

        node = WorkflowNode(
            id="op1",
            name="Alias Latest Operation",
            type="operation",
            template_id="enforce_template",
        )

        handler = OperationHandler()
        mock_renderer = Mock()
        handler.renderer = mock_renderer
        result = handler.execute(node, {"dry_run": True}, workflow_execution)

        assert result.success is False
        assert (result.error or "").startswith("TEMPLATE_PIN_REQUIRED:")
        mock_renderer.render.assert_not_called()

    def test_operation_handler_template_not_published(self, workflow_execution):
        _create_template_exposure(
            template_id="draft_template",
            name="Draft Template",
            operation_type="query",
            target_entity="Users",
            template_data={},
            status=OperationExposure.STATUS_DRAFT,
        )

        node = WorkflowNode(
            id="op1",
            name="Test Operation",
            type="operation",
            template_id="draft_template",
        )
        context = {}

        handler = OperationHandler()
        result = handler.execute(node, context, workflow_execution)

        assert result.success is False
        assert (result.error or "").startswith("TEMPLATE_NOT_PUBLISHED:")
        assert result.mode == NodeExecutionMode.SYNC

    def test_operation_handler_template_invalid_payload(self, workflow_execution):
        _create_template_exposure(
            template_id="invalid_template",
            name="Invalid Template",
            operation_type="query",
            target_entity="Users",
            template_data="not-an-object",
        )

        node = WorkflowNode(
            id="op1",
            name="Test Operation",
            type="operation",
            template_id="invalid_template",
        )
        context = {}

        handler = OperationHandler()
        result = handler.execute(node, context, workflow_execution)

        assert result.success is False
        assert (result.error or "").startswith("TEMPLATE_INVALID:")
        assert result.mode == NodeExecutionMode.SYNC

    def test_operation_handler_pinned_exposure_success(self, workflow_execution):
        exposure = _create_template_exposure(
            template_id="pinned_template",
            name="Pinned Template",
            operation_type="query",
            target_entity="Users",
            template_data={"query": "SELECT 1"},
            contract_version=7,
        )
        RuntimeSetting.objects.update_or_create(
            key="workflows.operation_binding.enforce_pinned",
            defaults={"value": True},
        )

        node = WorkflowNode(
            id="op1",
            name="Pinned Operation",
            type="operation",
            operation_ref={
                "alias": "pinned_template",
                "binding_mode": "pinned_exposure",
                "template_exposure_id": str(exposure.id),
                "template_exposure_revision": 7,
            },
        )
        context = {"dry_run": True}

        handler = OperationHandler()
        mock_renderer = Mock()
        mock_renderer.render.return_value = {"ok": True}
        handler.renderer = mock_renderer

        result = handler.execute(node, context, workflow_execution)

        assert result.success is True
        assert result.output["execution_skipped"] is True
        mock_renderer.render.assert_called_once()

    def test_operation_handler_pinned_exposure_drift_rejected(self, workflow_execution):
        exposure = _create_template_exposure(
            template_id="pinned_drift_template",
            name="Pinned Drift Template",
            operation_type="query",
            target_entity="Users",
            template_data={"query": "SELECT 1"},
            contract_version=3,
        )

        node = WorkflowNode(
            id="op1",
            name="Pinned Operation",
            type="operation",
            operation_ref={
                "alias": "pinned_drift_template",
                "binding_mode": "pinned_exposure",
                "template_exposure_id": str(exposure.id),
                "template_exposure_revision": 2,
            },
        )

        handler = OperationHandler()
        mock_renderer = Mock()
        handler.renderer = mock_renderer

        result = handler.execute(node, {"dry_run": True}, workflow_execution)

        assert result.success is False
        assert (result.error or "").startswith("TEMPLATE_DRIFT:")
        mock_renderer.render.assert_not_called()

    def test_operation_handler_pool_pinned_missing_maps_not_configured(self, workflow_execution):
        node = WorkflowNode(
            id="pool-missing",
            name="Pool Missing Exposure",
            type="operation",
            operation_ref={
                "alias": "pool.prepare_input",
                "binding_mode": "pinned_exposure",
                "template_exposure_id": str(uuid4()),
                "template_exposure_revision": 1,
            },
        )

        handler = OperationHandler()
        result = handler.execute(node, {"dry_run": True}, workflow_execution)

        assert result.success is False
        assert (result.error or "").startswith("POOL_RUNTIME_TEMPLATE_NOT_CONFIGURED:")

    def test_operation_handler_pool_pinned_inactive_maps_inactive_code(self, workflow_execution):
        exposure = _create_template_exposure(
            template_id="pool.prepare_input",
            name="Pool Prepare Input",
            operation_type="pool.prepare_input",
            target_entity="pool_run",
            template_data={"pool_runtime": {"step_id": "prepare_input"}},
            contract_version=3,
            is_active=False,
            executor_kind=OperationDefinition.EXECUTOR_WORKFLOW,
            system_managed=True,
            domain=OperationExposure.DOMAIN_POOL_RUNTIME,
        )

        node = WorkflowNode(
            id="pool-inactive",
            name="Pool Inactive Exposure",
            type="operation",
            operation_ref={
                "alias": "pool.prepare_input",
                "binding_mode": "pinned_exposure",
                "template_exposure_id": str(exposure.id),
                "template_exposure_revision": 3,
            },
        )

        handler = OperationHandler()
        result = handler.execute(node, {"dry_run": True}, workflow_execution)

        assert result.success is False
        assert (result.error or "").startswith("POOL_RUNTIME_TEMPLATE_INACTIVE:")

    def test_operation_handler_pool_pinned_routes_to_pool_backend_without_fallback(
        self,
        workflow_execution,
    ):
        exposure = _create_template_exposure(
            template_id="pool.prepare_input",
            name="Pool Prepare Input",
            operation_type="pool.prepare_input",
            target_entity="pool_run",
            template_data={
                "pool_runtime": {"step_id": "prepare_input"},
                "options": {"target_scope": "global"},
            },
            contract_version=5,
            executor_kind=OperationDefinition.EXECUTOR_WORKFLOW,
            system_managed=True,
            domain=OperationExposure.DOMAIN_POOL_RUNTIME,
        )
        node = WorkflowNode(
            id="pool-route",
            name="Pool Route",
            type="operation",
            operation_ref={
                "alias": "pool.prepare_input",
                "binding_mode": "pinned_exposure",
                "template_exposure_id": str(exposure.id),
                "template_exposure_revision": 5,
            },
        )
        handler = OperationHandler()
        mock_renderer = Mock()
        mock_renderer.render.return_value = {
            "pool_runtime": {"step_id": "prepare_input"},
            "options": {"target_scope": "global"},
        }
        handler.renderer = mock_renderer

        with (
            patch("apps.templates.workflow.handlers.backends.pool_domain.PoolDomainBackend.execute") as pool_execute,
            patch("apps.templates.workflow.handlers.backends.odata.ODataBackend.execute") as odata_execute,
            patch("apps.templates.workflow.handlers.backends.cli.CLIBackend.execute") as cli_execute,
            patch("apps.templates.workflow.handlers.backends.ibcmd.IBCMDBackend.execute") as ibcmd_execute,
            patch("apps.templates.workflow.handlers.backends.ras.RASBackend.execute") as ras_execute,
        ):
            pool_execute.return_value = NodeExecutionResult(
                success=True,
                output={"backend": "pool_domain", "status": "ok"},
                error=None,
                mode=NodeExecutionMode.SYNC,
                duration_seconds=0.0,
            )
            result = handler.execute(
                node,
                {"pool_run_id": str(uuid4()), "target_databases": ["db-1"]},
                workflow_execution,
            )

        assert result.success is True
        pool_execute.assert_called_once()
        odata_execute.assert_not_called()
        cli_execute.assert_not_called()
        ibcmd_execute.assert_not_called()
        ras_execute.assert_not_called()

    def test_operation_handler_pool_pinned_unsupported_executor_fail_closed(self, workflow_execution):
        exposure = _create_template_exposure(
            template_id="pool.prepare_input",
            name="Pool Prepare Input",
            operation_type="query",
            target_entity="pool_run",
            template_data={"query": "SELECT 1"},
            contract_version=2,
            executor_kind=OperationDefinition.EXECUTOR_WORKFLOW,
            system_managed=True,
            domain=OperationExposure.DOMAIN_POOL_RUNTIME,
        )
        node = WorkflowNode(
            id="pool-unsupported",
            name="Pool Unsupported",
            type="operation",
            operation_ref={
                "alias": "pool.prepare_input",
                "binding_mode": "pinned_exposure",
                "template_exposure_id": str(exposure.id),
                "template_exposure_revision": 2,
            },
        )
        handler = OperationHandler()
        mock_renderer = Mock()
        mock_renderer.render.return_value = {"query": "SELECT 1"}
        handler.renderer = mock_renderer

        with patch("apps.templates.workflow.handlers.backends.odata.ODataBackend.execute") as odata_execute:
            result = handler.execute(node, {"target_databases": ["db-1"]}, workflow_execution)

        assert result.success is False
        assert (result.error or "").startswith("POOL_RUNTIME_TEMPLATE_UNSUPPORTED_EXECUTOR:")
        odata_execute.assert_not_called()

    def test_operation_handler_success(self, admin_user, workflow_execution):
        """Test successful operation execution."""
        _create_template_exposure(
            template_id="test_template",
            name="Test Template",
            operation_type="query",
            target_entity="Users",
            template_data={"query": "SELECT * FROM Users"},
        )

        node = WorkflowNode(
            id="op1",
            name="Test Operation",
            type="operation",
            template_id="test_template"
        )
        context = {"user_id": 123, "dry_run": True}

        handler = OperationHandler()

        # Mock the renderer instance on the handler
        mock_renderer = Mock()
        mock_renderer.render.return_value = {"result": "rendered_data"}
        handler.renderer = mock_renderer

        result = handler.execute(node, context, workflow_execution)

        assert result.success is True
        # Without target_databases, requires explicit dry_run=true for render-only execution
        assert result.output['rendered_data'] == {"result": "rendered_data"}
        assert result.output['execution_skipped'] is True
        assert result.mode == NodeExecutionMode.SYNC
        assert result.duration_seconds is not None
        assert result.operation_id is None  # No operation created without target_databases
        assert result.task_id is None

        # Verify renderer was called
        mock_renderer.render.assert_called_once()

    def test_operation_handler_explicit_strict_uses_mapped_render_context(self, workflow_execution):
        _create_template_exposure(
            template_id="strict_input_template",
            name="Strict Input Template",
            operation_type="query",
            target_entity="Users",
            template_data={"query": "SELECT 1"},
        )

        node = WorkflowNode(
            id="op_strict_input",
            name="Strict Input Operation",
            type="operation",
            template_id="strict_input_template",
            io={
                "mode": "explicit_strict",
                "input_mapping": {"params.user_id": "workflow.user_id"},
            },
        )
        context = {
            "workflow": {"user_id": "u-123"},
            "dry_run": True,
            "unmapped_secret": "should_not_be_visible",
        }

        handler = OperationHandler()
        mock_renderer = Mock()
        mock_renderer.render.return_value = {"ok": True}
        handler.renderer = mock_renderer

        result = handler.execute(node, context, workflow_execution)

        assert result.success is True
        assert result.output["execution_skipped"] is True
        render_kwargs = mock_renderer.render.call_args.kwargs
        assert render_kwargs["context_data"] == {"params": {"user_id": "u-123"}}

    def test_operation_handler_explicit_strict_missing_input_path_fails_closed(self, workflow_execution):
        _create_template_exposure(
            template_id="strict_missing_template",
            name="Strict Missing Template",
            operation_type="query",
            target_entity="Users",
            template_data={"query": "SELECT 1"},
        )

        node = WorkflowNode(
            id="op_strict_missing",
            name="Strict Missing Operation",
            type="operation",
            template_id="strict_missing_template",
            io={
                "mode": "explicit_strict",
                "input_mapping": {"params.user_id": "workflow.user_id"},
            },
        )

        handler = OperationHandler()
        mock_renderer = Mock()
        handler.renderer = mock_renderer
        result = handler.execute(node, {"dry_run": True}, workflow_execution)

        assert result.success is False
        assert (result.error or "").startswith("OPERATION_INPUT_MAPPING_ERROR:")
        mock_renderer.render.assert_not_called()

    def test_operation_handler_explicit_output_mapping_exposes_context_updates(self, workflow_execution):
        _create_template_exposure(
            template_id="strict_output_template",
            name="Strict Output Template",
            operation_type="query",
            target_entity="Users",
            template_data={"query": "SELECT 1"},
        )

        node = WorkflowNode(
            id="op_strict_output",
            name="Strict Output Operation",
            type="operation",
            template_id="strict_output_template",
            io={
                "mode": "explicit_strict",
                "input_mapping": {"params.user_id": "workflow.user_id"},
                "output_mapping": {"workflow.state.query_result": "operation.result"},
            },
        )

        handler = OperationHandler()
        mock_renderer = Mock()
        mock_renderer.render.return_value = {"query": "payload"}
        handler.renderer = mock_renderer

        backend = Mock()
        backend.execute.return_value = NodeExecutionResult(
            success=True,
            output={"operation": {"result": {"rows": 10}}},
            error=None,
            mode=NodeExecutionMode.SYNC,
            duration_seconds=0.1,
        )

        with patch.object(handler, "_get_backend", return_value=backend):
            result = handler.execute(
                node,
                {"workflow": {"user_id": "u-123"}, "database_ids": ["db-1"]},
                workflow_execution,
            )

        assert result.success is True
        assert result.context_updates == {
            "workflow.state.query_result": {"rows": 10},
        }

    def test_operation_handler_implicit_legacy_keeps_full_render_context(self, workflow_execution):
        _create_template_exposure(
            template_id="legacy_mode_template",
            name="Legacy Mode Template",
            operation_type="query",
            target_entity="Users",
            template_data={"query": "SELECT 1"},
        )

        node = WorkflowNode(
            id="op_legacy_mode",
            name="Legacy Mode Operation",
            type="operation",
            template_id="legacy_mode_template",
        )
        context = {
            "workflow": {"user_id": "u-123"},
            "database_ids": ["db-1"],
            "extra": {"x": 1},
        }

        handler = OperationHandler()
        mock_renderer = Mock()
        mock_renderer.render.return_value = {"query": "payload"}
        handler.renderer = mock_renderer

        backend = Mock()
        backend.execute.return_value = NodeExecutionResult(
            success=True,
            output={"ok": True},
            error=None,
            mode=NodeExecutionMode.SYNC,
            duration_seconds=0.1,
        )

        with patch.object(handler, "_get_backend", return_value=backend):
            result = handler.execute(node, context, workflow_execution)

        assert result.success is True
        render_kwargs = mock_renderer.render.call_args.kwargs
        assert render_kwargs["context_data"] == context

    def test_extract_target_databases_accepts_database_ids(self):
        handler = OperationHandler()
        node = WorkflowNode(
            id="op1",
            name="Test Operation",
            type="operation",
            template_id="test_template",
        )

        target = handler._extract_target_databases({"database_ids": ["db1", "db2"]}, node)
        assert target == ["db1", "db2"]

    def test_operation_handler_render_error(self, admin_user, workflow_execution):
        """Test error handling when template rendering fails."""
        from apps.templates.engine.exceptions import TemplateRenderError

        _create_template_exposure(
            template_id="bad_template",
            name="Bad Template",
            operation_type="query",
            target_entity="Users",
            template_data={"query": "test"},
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
        _create_template_exposure(
            template_id="audit_test",
            name="Audit Test",
            operation_type="test",
            target_entity="Test",
            template_data={},
        )

        node = WorkflowNode(
            id="audit_node",
            name="Audit Node",
            type="operation",
            template_id="audit_test"
        )

        handler = OperationHandler()

        with patch.object(handler.renderer, 'render', return_value={"ok": True}):
            handler.execute(node, {}, workflow_execution)

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

    def test_condition_handler_evaluates_pinned_decision_ref_and_applies_output_mapping(
        self,
        workflow_execution,
    ):
        decision = create_decision_table_revision(
            contract={
                "decision_table_id": f"route-policy-{uuid4().hex[:8]}",
                "decision_key": "route_policy",
                "name": "Route Policy",
                "inputs": [
                    {"name": "direction", "value_type": "string", "required": True},
                    {"name": "mode", "value_type": "string", "required": True},
                ],
                "outputs": [
                    {"name": "route_policy", "value_type": "string", "required": True},
                ],
                "rules": [
                    {
                        "rule_id": "safe-bottom-up",
                        "priority": 0,
                        "conditions": {"direction": "bottom_up", "mode": "safe"},
                        "outputs": {"route_policy": "publish"},
                    }
                ],
            }
        )
        node = WorkflowNode(
            id="decision_gate",
            name="Decision Gate",
            type="condition",
            decision_ref={
                "decision_table_id": decision.decision_table_id,
                "decision_key": decision.decision_key,
                "decision_revision": decision.version_number,
            },
            io={
                "mode": "explicit_strict",
                "input_mapping": {
                    "direction": "direction",
                    "mode": "mode",
                },
                "output_mapping": {
                    "workflow.state.route_policy": "result.route_policy",
                },
            },
            config=NodeConfig(),
        )

        handler = ConditionHandler()
        result = handler.execute(
            node,
            {"direction": "bottom_up", "mode": "safe"},
            workflow_execution,
        )

        assert result.success is True
        assert result.output is True
        assert result.context_updates == {
            "decisions.route_policy": "publish",
            "workflow.state.route_policy": "publish",
        }


# ========== Integration Tests ==========

@pytest.mark.django_db
class TestHandlersIntegration:
    """Integration tests with real Template Engine."""

    def test_operation_handler_with_context_propagation(
        self, admin_user, simple_workflow_template
    ):
        """Test that operation results are stored in context."""
        _create_template_exposure(
            template_id="context_test",
            name="Context Test",
            operation_type="query",
            target_entity="Test",
            template_data={"query": "test"},
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

        context = {"initial": "data", "dry_run": True}
        handler = OperationHandler()

        # Mock renderer
        mock_renderer = Mock()
        mock_renderer.render.return_value = {"result": "operation_output"}
        handler.renderer = mock_renderer

        result = handler.execute(node, context, execution)

        # Dry-run: rendered_data should be returned without creating operation
        assert result.success is True
        assert result.output["execution_skipped"] is True
        assert result.output["rendered_data"] == {"result": "operation_output"}

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
        # Test OperationHandler
        _create_template_exposure(
            template_id="step_test",
            name="Step Test",
            operation_type="test",
            target_entity="Test",
            template_data={},
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
        """Test operation fails with empty context (no target databases)."""
        _create_template_exposure(
            template_id="empty_ctx",
            name="Empty Context",
            operation_type="test",
            target_entity="Test",
            template_data={"static": "data"},
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

        assert result.success is False
        assert "No target databases specified" in (result.error or "")

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
        _create_template_exposure(
            template_id="unicode_test",
            name="Тестовый шаблон",  # Cyrillic
            operation_type="test",
            target_entity="Пользователи",  # Cyrillic
            template_data={"имя": "значение"},  # Cyrillic
        )

        node = WorkflowNode(
            id="op1",
            name="Юникод узел",  # Cyrillic
            type="operation",
            template_id="unicode_test"
        )

        handler = OperationHandler()

        with patch.object(handler.renderer, 'render', return_value={"результат": "успех"}):
            result = handler.execute(node, {"dry_run": True}, workflow_execution)

        assert result.success is True
        assert result.output["rendered_data"] == {"результат": "успех"}


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
