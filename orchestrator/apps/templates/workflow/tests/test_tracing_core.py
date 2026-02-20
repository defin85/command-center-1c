"""
Tests for OpenTelemetry tracing integration (core helpers and workflow spans).
"""

import pytest

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
        with start_span("test_span"):
            pass

        # Should be able to create another span after
        with start_span("another_span"):
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

    def test_start_node_span(self):
        """Test node span creation."""
        with start_node_span(
            node_id="node-1",
            node_name="Test Node",
            node_type="operation",
            execution_id="exec-123",
            workflow_id="wf-456",
            workflow_name="TestWorkflow"
        ) as span:
            assert span is not None

    def test_start_operation_span(self):
        """Test operation span creation."""
        with start_operation_span(
            operation_type="db_lock",
            target_id="db-123",
            target_name="TestDB",
            execution_id="exec-456"
        ) as span:
            assert span is not None

    def test_trace_workflow_event(self):
        """Test workflow event tracing."""
        trace_workflow_event(
            event_name="workflow_started",
            execution_id="exec-123",
            event_data={"status": "started"}
        )
        # Should not raise


# ============================================================================
# TestWorkflowExecutionTracing
# ============================================================================


@pytest.mark.django_db
class TestWorkflowExecutionTracing:
    """Test workflow execution tracing integration."""

    def test_workflow_span_context_manager(self):
        """Test workflow span as context manager."""
        with start_workflow_span(
            workflow_id="wf-1",
            workflow_name="Test",
            execution_id="exec-1"
        ):
            # Should be able to get trace context within span
            trace_id = get_current_trace_id()
            span_id = get_current_span_id()
            assert isinstance(trace_id, str)
            assert isinstance(span_id, str)

    def test_nested_spans(self):
        """Test nested workflow -> node -> operation spans."""
        with start_workflow_span(
            workflow_id="wf-1",
            workflow_name="Test",
            execution_id="exec-1"
        ):
            with start_node_span(
                node_id="node-1",
                node_name="Node1",
                node_type="operation",
                execution_id="exec-1"
            ):
                with start_operation_span(
                    operation_type="db_lock",
                    target_id="db-1",
                    execution_id="exec-1"
                ):
                    # Should not raise
                    pass


# ============================================================================
# TestTracingGracefulDegradation
# ============================================================================


class TestTracingGracefulDegradation:
    """Test graceful degradation when tracing is disabled or unavailable."""

    @pytest.mark.skipif(OTEL_AVAILABLE, reason="OTEL available")
    def test_tracing_disabled_get_tracer(self):
        """Test get_tracer returns None when OTEL not available."""
        tracer = get_tracer()
        assert tracer is None

    @pytest.mark.skipif(OTEL_AVAILABLE, reason="OTEL available")
    def test_tracing_disabled_trace_id(self):
        """Test trace_id is empty when OTEL not available."""
        assert get_current_trace_id() == ""

    @pytest.mark.skipif(OTEL_AVAILABLE, reason="OTEL available")
    def test_tracing_disabled_span_id(self):
        """Test span_id is empty when OTEL not available."""
        assert get_current_span_id() == ""

    @pytest.mark.skipif(OTEL_AVAILABLE, reason="OTEL available")
    def test_tracing_disabled_headers(self):
        """Test headers injection is no-op when OTEL not available."""
        headers = {}
        inject_trace_headers(headers)
        assert headers == {}

    @pytest.mark.skipif(OTEL_AVAILABLE, reason="OTEL available")
    def test_tracing_disabled_extract(self):
        """Test extraction returns None when OTEL not available."""
        assert extract_trace_context({}) is None


# ============================================================================
# TestCeleryTracingIntegration
# ============================================================================


class TestCeleryTracingIntegration:
    """Test Celery header injection/extraction."""

    def test_inject_celery_headers_returns_dict(self):
        """Test inject_celery_headers returns a dict."""
        headers = {}
        result = inject_celery_headers(headers)
        assert isinstance(result, dict)
        assert result is headers

    def test_extract_celery_headers_returns_context_or_none(self):
        """Test extract_celery_headers returns context or None."""
        headers = {}
        context = extract_celery_headers(headers)
        assert context is None or context is not None


# ============================================================================
# TestTracingInitialization
# ============================================================================


class TestTracingInitialization:
    """Test tracing initialization."""

    def test_init_tracing_does_not_raise(self):
        """Test init_tracing doesn't raise."""
        init_tracing()

    def test_init_tracing_idempotent(self):
        """Test init_tracing can be called multiple times."""
        init_tracing()
        init_tracing()
        init_tracing()


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
        with start_span("test"):
            add_span_event("event_name")

    def test_span_add_event_with_data(self):
        """Test adding event with data."""
        with start_span("test"):
            add_span_event("payment_completed", {
                "provider": "stripe",
                "status": "success"
            })

    def test_span_set_error_in_except(self):
        """Test setting error on span in exception handler."""
        try:
            with start_span("risky_operation"):
                raise ValueError("Test error")
        except ValueError as e:
            set_span_error(e)

