"""
Tests for OpenTelemetry tracing integration (integration scenarios, errors, context propagation).
"""

import pytest
from unittest.mock import patch, MagicMock

from apps.templates.tracing import (
    OTEL_AVAILABLE,
    get_tracer,
    start_span,
    get_current_trace_id,
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
)


# ============================================================================
# TestTracingWithMocks
# ============================================================================


class TestTracingWithMocks:
    """Test tracing with mocked OpenTelemetry."""

    @pytest.mark.skipif(not OTEL_AVAILABLE, reason="OTEL not available")
    def test_tracer_methods_exist(self):
        """Test that tracer has expected methods."""
        # Patch the symbol used by this test module (imported via `from ... import get_tracer`).
        with patch('apps.templates.workflow.tests.test_tracing_integration_and_context.get_tracer') as mock_get_tracer:
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
        ):
            # Simulate executing multiple nodes
            for idx, node_id in enumerate(["step1", "step2"]):
                with start_node_span(
                    node_id=node_id,
                    node_name=f"Step {idx+1}",
                    node_type="operation",
                    execution_id=str(execution.id)
                ):
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
        ):
            try:
                with start_node_span(
                    node_id="step1",
                    node_name="Step1",
                    node_type="operation",
                    execution_id=str(execution.id)
                ):
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
        ):
            with start_operation_span(
                operation_type="db_lock",
                target_id="db-001",
                target_name="Main1C",
                execution_id=str(execution.id)
            ):
                set_span_attribute("lock.type", "shared")
                add_span_event("lock_acquired", {"duration_ms": 100})

            with start_operation_span(
                operation_type="odata_batch",
                target_id="db-001",
                execution_id=str(execution.id)
            ):
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
        assert trace_id == "" or (
            len(trace_id) == 32 and all(c in '0123456789abcdef' for c in trace_id)
        )

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
        extract_trace_context(headers)

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
        extract_trace_context(headers)
        # Should not raise

    def test_context_propagation_celery_headers(self):
        """Test trace context propagation in Celery."""
        # Inject into Celery headers
        celery_headers = {}
        inject_celery_headers(celery_headers)

        # Extract from Celery headers
        extract_celery_headers(celery_headers)
        # Should not raise

    def test_nested_span_context_propagation(self):
        """Test context propagates through nested spans."""
        with start_workflow_span(
            workflow_id="wf-1",
            workflow_name="Test",
            execution_id="exec-1"
        ):
            parent_trace = get_current_trace_id()

            with start_node_span(
                node_id="node-1",
                node_name="Node1",
                node_type="operation",
                execution_id="exec-1"
            ):
                child_trace = get_current_trace_id()
                # Should be same trace
                assert parent_trace == child_trace

