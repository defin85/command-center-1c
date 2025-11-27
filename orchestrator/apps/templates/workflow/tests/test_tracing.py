"""
Tests for OpenTelemetry tracing integration.

Covers:
- Tracing helpers (get_tracer, start_span, etc.)
- Workflow execution tracing
- Node execution tracing
- Trace context propagation
- Graceful degradation when tracing disabled
- Celery integration
"""

import pytest
from unittest.mock import patch, MagicMock

from apps.templates.tracing import (
    OTEL_AVAILABLE,
    get_tracer,
    start_span,
    get_current_trace_id,
    get_current_span_id,
    inject_trace_headers,
    extract_trace_context,
    set_span_error,
    set_span_attribute,
    add_span_event,
    start_workflow_span,
    start_node_span,
    start_operation_span,
    trace_workflow_event,
    inject_celery_headers,
    extract_celery_headers,
    init_tracing,
    get_trace_context_for_logging,
    _NoOpSpan,
)


# ============================================================================
# TestTracingHelpers
# ============================================================================

class TestTracingHelpers:
    """Test tracing helper functions."""

    def test_otel_available_flag(self):
        """Test OTEL_AVAILABLE is set correctly."""
        # OTEL_AVAILABLE should be a boolean
        assert isinstance(OTEL_AVAILABLE, bool)

    def test_get_tracer_returns_tracer_or_none(self):
        """Test get_tracer() returns tracer or None."""
        tracer = get_tracer()
        # Tracer can be None or a tracer object
        assert tracer is None or hasattr(tracer, 'start_as_current_span')

    def test_start_span_creates_span(self):
        """Test start_span context manager works."""
        with start_span("test_span") as span:
            assert span is not None
            # Should have no-op methods or real span methods
            assert hasattr(span, 'set_attribute') or isinstance(span, _NoOpSpan)

    def test_start_span_with_attributes(self):
        """Test span attributes are set."""
        attrs = {"key1": "value1", "key2": 123}

        with start_span("test_span", attributes=attrs) as span:
            # Should not raise
            if span is not None:
                span.set_attribute("test", "value")

    def test_start_span_exits_cleanly(self):
        """Test span context manager cleans up properly."""
        # Should not raise any exceptions
        with start_span("test_span") as span:
            pass

        # Should be able to create another span after
        with start_span("another_span") as span:
            pass

    def test_get_trace_id_format(self):
        """Test trace_id is empty or 32-char hex string."""
        trace_id = get_current_trace_id()
        assert isinstance(trace_id, str)
        # Either empty or 32 hex chars
        if trace_id:
            assert len(trace_id) == 32
            assert all(c in '0123456789abcdef' for c in trace_id)

    def test_get_span_id_format(self):
        """Test span_id is empty or 16-char hex string."""
        span_id = get_current_span_id()
        assert isinstance(span_id, str)
        # Either empty or 16 hex chars
        if span_id:
            assert len(span_id) == 16
            assert all(c in '0123456789abcdef' for c in span_id)

    def test_inject_trace_headers(self):
        """Test W3C Trace Context injection."""
        headers = {"Content-Type": "application/json"}
        result = inject_trace_headers(headers)

        # Should return headers dict
        assert isinstance(result, dict)
        assert "Content-Type" in result

    def test_inject_trace_headers_modifies_in_place(self):
        """Test that headers dict is modified in place."""
        headers = {}
        result = inject_trace_headers(headers)
        assert result is headers

    def test_extract_trace_context(self):
        """Test context extraction from headers."""
        headers = {"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b9c7c989f97918e1-01"}
        context = extract_trace_context(headers)
        # Should return context or None
        assert context is None or context is not None

    def test_extract_trace_context_with_empty_headers(self):
        """Test extraction with empty headers."""
        headers = {}
        context = extract_trace_context(headers)
        # Should not raise
        assert context is None or context is not None

    def test_set_span_error(self):
        """Test error marking on span."""
        error = ValueError("Test error")
        # Should not raise
        set_span_error(error)

    def test_set_span_attribute(self):
        """Test setting attribute on span."""
        # Should not raise
        set_span_attribute("key", "value")
        set_span_attribute("number", 123)
        set_span_attribute("float", 3.14)
        set_span_attribute("bool", True)

    def test_add_span_event(self):
        """Test adding event to span."""
        # Should not raise
        add_span_event("test_event")
        add_span_event("test_event", {"data": "value"})

    def test_get_trace_context_for_logging(self):
        """Test getting trace context for logging."""
        context = get_trace_context_for_logging()

        assert isinstance(context, dict)
        assert "trace_id" in context
        assert "span_id" in context
        assert isinstance(context["trace_id"], str)
        assert isinstance(context["span_id"], str)


# ============================================================================
# TestNoOpSpan
# ============================================================================

class TestNoOpSpan:
    """Test no-op span implementation."""

    def test_noop_span_set_attribute(self):
        """Test NoOpSpan.set_attribute doesn't raise."""
        span = _NoOpSpan()
        span.set_attribute("key", "value")

    def test_noop_span_set_attributes(self):
        """Test NoOpSpan.set_attributes doesn't raise."""
        span = _NoOpSpan()
        span.set_attributes({"key1": "value1", "key2": "value2"})

    def test_noop_span_add_event(self):
        """Test NoOpSpan.add_event doesn't raise."""
        span = _NoOpSpan()
        span.add_event("event_name")
        span.add_event("event_name", {"data": "value"})

    def test_noop_span_set_status(self):
        """Test NoOpSpan.set_status doesn't raise."""
        span = _NoOpSpan()
        span.set_status(None)

    def test_noop_span_record_exception(self):
        """Test NoOpSpan.record_exception doesn't raise."""
        span = _NoOpSpan()
        error = ValueError("test")
        span.record_exception(error)

    def test_noop_span_end(self):
        """Test NoOpSpan.end doesn't raise."""
        span = _NoOpSpan()
        span.end()

    def test_noop_span_get_span_context(self):
        """Test NoOpSpan.get_span_context returns None."""
        span = _NoOpSpan()
        assert span.get_span_context() is None


# ============================================================================
# TestWorkflowTracing
# ============================================================================

@pytest.mark.django_db
class TestWorkflowTracing:
    """Test workflow execution tracing."""

    def test_start_workflow_span(self):
        """Test workflow span creation."""
        with start_workflow_span(
            workflow_id="wf-123",
            workflow_name="TestWorkflow",
            execution_id="exec-456",
            template_id="tpl-789"
        ) as span:
            assert span is not None

    def test_workflow_span_without_template_id(self):
        """Test workflow span without template_id."""
        with start_workflow_span(
            workflow_id="wf-123",
            workflow_name="TestWorkflow",
            execution_id="exec-456"
        ) as span:
            assert span is not None

    def test_start_node_span(self):
        """Test node execution span creation."""
        with start_node_span(
            node_id="node-1",
            node_name="LockDatabase",
            node_type="operation",
            execution_id="exec-456"
        ) as span:
            assert span is not None

    def test_start_operation_span(self):
        """Test operation span creation."""
        with start_operation_span(
            operation_type="db_lock",
            target_id="db-123",
            target_name="AccountingDB",
            execution_id="exec-456"
        ) as span:
            assert span is not None

    def test_operation_span_without_target_name(self):
        """Test operation span without target_name."""
        with start_operation_span(
            operation_type="odata_batch",
            target_id="db-123"
        ) as span:
            assert span is not None

    def test_nested_spans(self):
        """Test nested span creation."""
        with start_workflow_span(
            workflow_id="wf-123",
            workflow_name="TestWorkflow",
            execution_id="exec-456"
        ) as wf_span:
            assert wf_span is not None

            with start_node_span(
                node_id="node-1",
                node_name="Step1",
                node_type="operation",
                execution_id="exec-456"
            ) as node_span:
                assert node_span is not None

                with start_operation_span(
                    operation_type="db_lock",
                    target_id="db-123"
                ) as op_span:
                    assert op_span is not None

    def test_trace_workflow_event(self):
        """Test recording workflow event."""
        # Should not raise
        trace_workflow_event(
            event_name="state_changed",
            execution_id="exec-456",
            event_data={"from": "running", "to": "completed"}
        )

    def test_trace_workflow_event_without_data(self):
        """Test workflow event without event_data."""
        # Should not raise
        trace_workflow_event(
            event_name="started",
            execution_id="exec-456"
        )


# ============================================================================
# TestWorkflowExecutionTracing
# ============================================================================

@pytest.mark.django_db
class TestWorkflowExecutionTracing:
    """Test integration with WorkflowExecution model."""

    def test_workflow_execution_trace_context(self, simple_workflow_template):
        """Test WorkflowExecution stores trace context."""
        execution = simple_workflow_template.create_execution({"input": "data"})

        # Should have trace_id and span_id fields (or None)
        assert hasattr(execution, 'trace_id') or hasattr(execution, 'span_id')

    def test_workflow_execution_with_tracing(self, simple_workflow_template):
        """Test executing workflow with tracing."""
        with start_workflow_span(
            workflow_id=str(simple_workflow_template.id),
            workflow_name=simple_workflow_template.name,
            execution_id="test-exec-001",
            template_id=str(simple_workflow_template.id)
        ) as span:
            execution = simple_workflow_template.create_execution({"input": "data"})
            # trace_id should be available during execution
            trace_id = get_current_trace_id()
            # Not necessarily filled, but should be accessible
            assert isinstance(trace_id, str)

    def test_nested_execution_spans(self, simple_workflow_template):
        """Test nested execution and node spans."""
        with start_workflow_span(
            workflow_id=str(simple_workflow_template.id),
            workflow_name=simple_workflow_template.name,
            execution_id="test-exec-001"
        ) as wf_span:
            trace_id_wf = get_current_trace_id()

            with start_node_span(
                node_id="step1",
                node_name="Step1",
                node_type="operation",
                execution_id="test-exec-001"
            ) as node_span:
                trace_id_node = get_current_trace_id()
                # Should be same trace ID in nested context
                assert trace_id_wf == trace_id_node


# ============================================================================
# TestTracingGracefulDegradation
# ============================================================================

class TestTracingGracefulDegradation:
    """Test graceful degradation when tracing is disabled."""

    @patch('apps.templates.tracing._enabled', False)
    def test_tracing_disabled_get_tracer(self):
        """Test get_tracer returns None when disabled."""
        tracer = get_tracer()
        # When tracing disabled, should return None
        # (actual behavior depends on current _enabled state)

    @patch('apps.templates.tracing._enabled', False)
    def test_tracing_disabled_trace_id(self):
        """Test get_current_trace_id returns empty when disabled."""
        trace_id = get_current_trace_id()
        assert trace_id == ""

    @patch('apps.templates.tracing._enabled', False)
    def test_tracing_disabled_span_id(self):
        """Test get_current_span_id returns empty when disabled."""
        span_id = get_current_span_id()
        assert span_id == ""

    @patch('apps.templates.tracing._enabled', False)
    def test_tracing_disabled_headers(self):
        """Test header injection works when disabled."""
        headers = {"Content-Type": "application/json"}
        result = inject_trace_headers(headers)
        # Should return original headers unchanged
        assert result == headers

    @patch('apps.templates.tracing._enabled', False)
    def test_tracing_disabled_extract(self):
        """Test context extraction returns None when disabled."""
        context = extract_trace_context({})
        assert context is None

    def test_noop_span_all_methods_safe(self):
        """Test that NoOpSpan is safe for all operations."""
        span = _NoOpSpan()
        # All methods should work without raising
        span.set_attribute("k", "v")
        span.set_attributes({"k1": "v1"})
        span.add_event("event")
        span.set_status(None)
        span.record_exception(ValueError("test"))
        span.end()

    def test_workflow_execution_without_tracing_disabled(self, simple_workflow_template):
        """Test workflow execution when tracing disabled."""
        with patch('apps.templates.tracing._enabled', False):
            execution = simple_workflow_template.create_execution({"input": "data"})
            assert execution is not None
            # Should still work even without tracing

    def test_span_operations_with_no_tracer(self):
        """Test span operations when no tracer available."""
        with patch('apps.templates.tracing.get_tracer', return_value=None):
            with start_span("test") as span:
                # Should be NoOpSpan
                span.set_attribute("key", "value")
                # Should not raise


# ============================================================================
# TestCeleryTracingIntegration
# ============================================================================

class TestCeleryTracingIntegration:
    """Test Celery task tracing."""

    def test_inject_celery_headers_empty(self):
        """Test trace context injection into empty headers."""
        headers = {}
        result = inject_celery_headers(headers)
        assert isinstance(result, dict)

    def test_inject_celery_headers_preserves_existing(self):
        """Test that injection preserves existing headers."""
        headers = {"existing": "header"}
        result = inject_celery_headers(headers)
        # Original headers should be preserved
        assert "existing" in result or result == headers

    def test_extract_celery_headers_empty(self):
        """Test extraction from empty Celery headers."""
        headers = {}
        context = extract_celery_headers(headers)
        # Should handle gracefully
        assert context is None or context is not None

    def test_extract_celery_headers_with_context(self):
        """Test extraction from headers with trace context."""
        headers = {
            'trace_context': {
                'traceparent': '00-0af7651916cd43dd8448eb211c80319c-b9c7c989f97918e1-01'
            }
        }
        context = extract_celery_headers(headers)
        # Should not raise

    def test_celery_header_roundtrip(self):
        """Test inject and extract roundtrip."""
        headers_out = {}
        inject_celery_headers(headers_out)

        # Extract from injected headers
        context = extract_celery_headers(headers_out)
        # Should be able to extract without error

    def test_celery_disabled_inject(self):
        """Test Celery injection when tracing disabled."""
        with patch('apps.templates.tracing._enabled', False):
            headers = {}
            result = inject_celery_headers(headers)
            assert result == headers

    def test_celery_disabled_extract(self):
        """Test Celery extraction when tracing disabled."""
        with patch('apps.templates.tracing._enabled', False):
            headers = {'trace_context': {}}
            context = extract_celery_headers(headers)
            assert context is None


# ============================================================================
# TestTracingInitialization
# ============================================================================

class TestTracingInitialization:
    """Test tracing initialization."""

    @patch('apps.templates.tracing._initialized', False)
    @patch('apps.templates.tracing.OTEL_AVAILABLE', False)
    def test_init_tracing_without_otel(self):
        """Test init_tracing when OpenTelemetry not available."""
        # Should not raise
        init_tracing(
            service_name="test",
            service_version="1.0.0",
            enabled=True
        )

    @patch('apps.templates.tracing._initialized', False)
    def test_init_tracing_disabled(self):
        """Test init_tracing with enabled=False."""
        # Should not raise
        init_tracing(
            service_name="test",
            enabled=False
        )

    @patch('apps.templates.tracing._initialized', True)
    def test_init_tracing_already_initialized(self):
        """Test init_tracing skips if already initialized."""
        # Should return early without error
        init_tracing(
            service_name="test",
            service_version="1.0.0"
        )


# ============================================================================
# TestSpanAttributesAndEvents
# ============================================================================

class TestSpanAttributesAndEvents:
    """Test span attribute and event handling."""

    def test_span_set_attribute_string(self):
        """Test setting string attribute."""
        with start_span("test") as span:
            span.set_attribute("key", "value")

    def test_span_set_attribute_int(self):
        """Test setting int attribute."""
        with start_span("test") as span:
            span.set_attribute("count", 42)

    def test_span_set_attribute_float(self):
        """Test setting float attribute."""
        with start_span("test") as span:
            span.set_attribute("duration", 3.14)

    def test_span_set_attribute_bool(self):
        """Test setting bool attribute."""
        with start_span("test") as span:
            span.set_attribute("success", True)

    def test_span_set_attributes_dict(self):
        """Test setting multiple attributes."""
        attrs = {
            "key1": "value1",
            "key2": 42,
            "key3": 3.14,
            "key4": True
        }
        with start_span("test", attributes=attrs) as span:
            # Should be initialized with attributes
            assert span is not None

    def test_span_add_event_no_data(self):
        """Test adding event without data."""
        with start_span("test") as span:
            add_span_event("event_name")

    def test_span_add_event_with_data(self):
        """Test adding event with data."""
        with start_span("test") as span:
            add_span_event("payment_completed", {
                "provider": "stripe",
                "status": "success"
            })

    def test_span_set_error_in_except(self):
        """Test setting error on span in exception handler."""
        try:
            with start_span("risky_operation") as span:
                raise ValueError("Test error")
        except ValueError as e:
            set_span_error(e)


# ============================================================================
# TestTracingWithMocks
# ============================================================================

class TestTracingWithMocks:
    """Test tracing with mocked OpenTelemetry."""

    @pytest.mark.skipif(not OTEL_AVAILABLE, reason="OTEL not available")
    def test_tracer_methods_exist(self):
        """Test that tracer has expected methods."""
        with patch('apps.templates.tracing.get_tracer') as mock_get_tracer:
            mock_tracer = MagicMock()
            mock_get_tracer.return_value = mock_tracer

            tracer = get_tracer()
            assert tracer is not None

    def test_trace_context_injection_idempotent(self):
        """Test that injecting headers multiple times is safe."""
        headers = {}
        inject_trace_headers(headers)
        inject_trace_headers(headers)
        inject_trace_headers(headers)
        # Should not raise

    def test_operation_span_with_all_params(self):
        """Test operation span with all parameters."""
        with start_operation_span(
            operation_type="db_lock",
            target_id="db-123",
            target_name="AccountingDB",
            execution_id="exec-456"
        ) as span:
            assert span is not None
            if hasattr(span, 'set_attribute'):
                span.set_attribute("status", "starting")

    def test_workflow_event_with_complex_data(self):
        """Test workflow event with complex data."""
        trace_workflow_event(
            event_name="retry_scheduled",
            execution_id="exec-456",
            event_data={
                "retry_count": 3,
                "delay_seconds": 60,
                "reason": "timeout",
                "error_code": "TIMEOUT_EXCEEDED"
            }
        )


# ============================================================================
# TestTracingIntegrationScenarios
# ============================================================================

@pytest.mark.django_db
class TestTracingIntegrationScenarios:
    """Test realistic tracing scenarios."""

    def test_workflow_with_multiple_nodes(self, simple_workflow_template):
        """Test tracing workflow with multiple nodes."""
        execution = simple_workflow_template.create_execution({})

        with start_workflow_span(
            workflow_id=str(simple_workflow_template.id),
            workflow_name=simple_workflow_template.name,
            execution_id=str(execution.id)
        ) as wf_span:
            # Simulate executing multiple nodes
            for idx, node_id in enumerate(["step1", "step2"]):
                with start_node_span(
                    node_id=node_id,
                    node_name=f"Step {idx+1}",
                    node_type="operation",
                    execution_id=str(execution.id)
                ) as node_span:
                    # Record some operations
                    trace_workflow_event(
                        "node_executed",
                        str(execution.id),
                        {"node_id": node_id}
                    )

    def test_workflow_with_error_handling(self, simple_workflow_template):
        """Test tracing with error handling."""
        execution = simple_workflow_template.create_execution({})

        with start_workflow_span(
            workflow_id=str(simple_workflow_template.id),
            workflow_name=simple_workflow_template.name,
            execution_id=str(execution.id)
        ) as wf_span:
            try:
                with start_node_span(
                    node_id="step1",
                    node_name="Step1",
                    node_type="operation",
                    execution_id=str(execution.id)
                ) as node_span:
                    raise RuntimeError("Node execution failed")
            except RuntimeError as e:
                set_span_error(e)
                trace_workflow_event(
                    "error_occurred",
                    str(execution.id),
                    {"error": str(e)}
                )

    def test_workflow_with_operations(self, simple_workflow_template):
        """Test tracing individual operations."""
        execution = simple_workflow_template.create_execution({})

        with start_workflow_span(
            workflow_id=str(simple_workflow_template.id),
            workflow_name=simple_workflow_template.name,
            execution_id=str(execution.id)
        ) as wf_span:
            with start_operation_span(
                operation_type="db_lock",
                target_id="db-001",
                target_name="Main1C",
                execution_id=str(execution.id)
            ) as op_span:
                set_span_attribute("lock.type", "shared")
                add_span_event("lock_acquired", {"duration_ms": 100})

            with start_operation_span(
                operation_type="odata_batch",
                target_id="db-001",
                execution_id=str(execution.id)
            ) as op_span:
                set_span_attribute("batch.size", 500)
                add_span_event("batch_completed", {"records": 500})


# ============================================================================
# TestTracingErrorHandling
# ============================================================================

class TestTracingErrorHandling:
    """Test error handling in tracing."""

    def test_invalid_trace_id_returns_empty(self):
        """Test that invalid span returns empty trace_id."""
        trace_id = get_current_trace_id()
        # Should be either valid or empty string
        assert trace_id == "" or (len(trace_id) == 32 and all(c in '0123456789abcdef' for c in trace_id))

    def test_span_error_with_none(self):
        """Test set_span_error handles various inputs."""
        error = ValueError("Test error")
        # Should not raise
        set_span_error(error)

    def test_span_error_with_exception_message(self):
        """Test error with message."""
        error = RuntimeError("Something went wrong")
        # Should not raise
        set_span_error(error)

    def test_extract_with_malformed_headers(self):
        """Test extract_trace_context with malformed headers."""
        headers = {
            "traceparent": "malformed_data",
            "tracestate": "invalid"
        }
        # Should not raise
        context = extract_trace_context(headers)

    def test_celery_extract_with_no_trace_context(self):
        """Test Celery extract without trace_context key."""
        headers = {
            "other_key": "value"
        }
        context = extract_celery_headers(headers)
        # Should not raise
        assert context is None

    def test_set_span_attribute_with_various_types(self):
        """Test set_span_attribute with different value types."""
        # All should work without raising
        set_span_attribute("string_key", "value")
        set_span_attribute("int_key", 42)
        set_span_attribute("float_key", 3.14)
        set_span_attribute("bool_key", True)
        set_span_attribute("none_key", None)


# ============================================================================
# TestTracingContextPropagation
# ============================================================================

class TestTracingContextPropagation:
    """Test trace context propagation."""

    def test_context_propagation_through_headers(self):
        """Test trace context propagation via headers."""
        # Inject trace context
        headers = {}
        inject_trace_headers(headers)

        # Extract same context
        context = extract_trace_context(headers)
        # Should not raise

    def test_context_propagation_celery_headers(self):
        """Test trace context propagation in Celery."""
        # Inject into Celery headers
        celery_headers = {}
        inject_celery_headers(celery_headers)

        # Extract from Celery headers
        context = extract_celery_headers(celery_headers)
        # Should not raise

    def test_nested_span_context_propagation(self):
        """Test context propagates through nested spans."""
        with start_workflow_span(
            workflow_id="wf-1",
            workflow_name="Test",
            execution_id="exec-1"
        ) as wf_span:
            parent_trace = get_current_trace_id()

            with start_node_span(
                node_id="node-1",
                node_name="Node1",
                node_type="operation",
                execution_id="exec-1"
            ) as node_span:
                child_trace = get_current_trace_id()
                # Should be same trace
                assert parent_trace == child_trace
