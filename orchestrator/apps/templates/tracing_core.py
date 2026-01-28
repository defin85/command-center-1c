"""
OpenTelemetry tracing utilities for Workflow Engine.

Provides distributed tracing capabilities with graceful degradation
when OpenTelemetry is not available or disabled.

Usage:
    from apps.templates.tracing import init_tracing, start_span, get_tracer

    # Initialize once at app startup
    init_tracing(
        service_name="orchestrator",
        service_version="1.0.0",
        otlp_endpoint="http://localhost:4317",
        enabled=True
    )

    # Create spans
    with start_span("my_operation", attributes={"key": "value"}):
        do_something()

    # Workflow-specific
    with start_workflow_span(workflow_id, name, execution_id, template_id):
        execute_workflow()
"""
import logging
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# Global state
_tracer = None
_initialized = False
_enabled = False

# Check if OpenTelemetry is available
try:
    from opentelemetry import trace
    from opentelemetry.propagate import extract, inject
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.trace import Status, StatusCode, SpanKind

    OTEL_AVAILABLE = True
    logger.debug("OpenTelemetry libraries loaded successfully.")
except ImportError as e:
    OTEL_AVAILABLE = False
    logger.warning(
        "OpenTelemetry not available. Tracing will be disabled. "
        "Install with: pip install opentelemetry-api opentelemetry-sdk "
        "opentelemetry-exporter-otlp. Error: %s",
        e
    )

    # Stub classes for type hints when OTEL is not available
    class Status:  # type: ignore
        pass

    class StatusCode:  # type: ignore
        ERROR = "ERROR"
        OK = "OK"

    class SpanKind:  # type: ignore
        INTERNAL = "INTERNAL"
        SERVER = "SERVER"
        CLIENT = "CLIENT"


def init_tracing(
    service_name: str = "orchestrator",
    service_version: str = "1.0.0",
    otlp_endpoint: Optional[str] = None,
    enabled: bool = True
) -> None:
    """
    Initialize OpenTelemetry tracing.

    Should be called once at application startup. Safe to call multiple times,
    subsequent calls are ignored.

    Args:
        service_name: Name of the service for trace identification.
        service_version: Version of the service.
        otlp_endpoint: OTLP collector endpoint (e.g., "http://localhost:4317").
                      If None, uses OTEL_EXPORTER_OTLP_ENDPOINT env var.
        enabled: Whether tracing is enabled. If False, all tracing is no-op.

    Example:
        >>> init_tracing(
        ...     service_name="orchestrator",
        ...     service_version="1.0.0",
        ...     otlp_endpoint="http://jaeger:4317",
        ...     enabled=True
        ... )
    """
    global _tracer, _initialized, _enabled

    if _initialized:
        logger.debug("Tracing already initialized, skipping.")
        return

    _enabled = enabled

    if not enabled:
        logger.info("Tracing is disabled by configuration.")
        _initialized = True
        return

    if not OTEL_AVAILABLE:
        logger.warning("Tracing requested but OpenTelemetry is not installed.")
        _initialized = True
        return

    try:
        # Create resource with service information
        resource = Resource.create({
            SERVICE_NAME: service_name,
            SERVICE_VERSION: service_version,
            "deployment.environment": getattr(settings, 'ENVIRONMENT', 'development'),
        })

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Add OTLP exporter if endpoint is provided
        if otlp_endpoint:
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
            logger.info(
                "OTLP exporter configured with endpoint: %s",
                otlp_endpoint
            )

        # Set global tracer provider
        trace.set_tracer_provider(provider)

        # Get tracer instance
        _tracer = trace.get_tracer(
            instrumenting_module_name=service_name,
            instrumenting_library_version=service_version
        )

        _initialized = True
        logger.info(
            "OpenTelemetry tracing initialized for service=%s, version=%s",
            service_name,
            service_version
        )

    except Exception as e:
        logger.error("Failed to initialize OpenTelemetry tracing: %s", e)
        _initialized = True  # Mark as initialized to prevent retry loops


def get_tracer():
    """
    Get the global tracer instance.

    Returns:
        Tracer instance or None if tracing is not available/disabled.

    Example:
        >>> tracer = get_tracer()
        >>> if tracer:
        ...     with tracer.start_as_current_span("my_span"):
        ...         do_work()
    """
    global _tracer

    if not _enabled or not OTEL_AVAILABLE:
        return None

    if _tracer is None and OTEL_AVAILABLE:
        # Lazy initialization with default tracer
        _tracer = trace.get_tracer("orchestrator")

    return _tracer


class _NoOpSpan:
    """No-op span implementation for when tracing is disabled."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_attributes(self, attributes: Dict[str, Any]) -> None:
        pass

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass

    def end(self) -> None:
        pass

    def get_span_context(self):
        return None


@contextmanager
def start_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    kind: Optional[Any] = None
) -> Generator[Any, None, None]:
    """
    Context manager for creating spans.

    Creates a new span as a child of the current span. Safe to use even
    when tracing is disabled - returns a no-op span in that case.

    Args:
        name: Name of the span.
        attributes: Optional dictionary of span attributes.
        kind: Optional span kind (SpanKind.INTERNAL, SERVER, CLIENT, etc.).

    Yields:
        The created span (or no-op span if tracing disabled).

    Example:
        >>> with start_span("process_data", {"item_count": 100}) as span:
        ...     result = process_items()
        ...     span.set_attribute("result_size", len(result))
    """
    tracer = get_tracer()

    if tracer is None:
        yield _NoOpSpan()
        return

    span_kind = kind if kind is not None else SpanKind.INTERNAL

    with tracer.start_as_current_span(
        name,
        kind=span_kind,
        attributes=attributes or {}
    ) as span:
        yield span


def get_current_trace_id() -> str:
    """
    Get current trace ID as 32-character hex string.

    Returns:
        Trace ID as hex string, or empty string if no active trace.

    Example:
        >>> trace_id = get_current_trace_id()
        >>> logger.info("Processing request", extra={"trace_id": trace_id})
    """
    if not OTEL_AVAILABLE or not _enabled:
        return ""

    try:
        span = trace.get_current_span()
        if span is None:
            return ""

        span_context = span.get_span_context()
        if span_context is None or not span_context.is_valid:
            return ""

        return format(span_context.trace_id, '032x')
    except Exception:
        return ""


def get_current_span_id() -> str:
    """
    Get current span ID as 16-character hex string.

    Returns:
        Span ID as hex string, or empty string if no active span.

    Example:
        >>> span_id = get_current_span_id()
        >>> logger.info("Step completed", extra={"span_id": span_id})
    """
    if not OTEL_AVAILABLE or not _enabled:
        return ""

    try:
        span = trace.get_current_span()
        if span is None:
            return ""

        span_context = span.get_span_context()
        if span_context is None or not span_context.is_valid:
            return ""

        return format(span_context.span_id, '016x')
    except Exception:
        return ""


def inject_trace_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Inject W3C Trace Context headers into a dictionary.

    Used for propagating trace context to downstream services via HTTP.
    Adds 'traceparent' and optionally 'tracestate' headers.

    Args:
        headers: Dictionary to inject headers into. Modified in-place.

    Returns:
        The modified headers dictionary.

    Example:
        >>> headers = {"Content-Type": "application/json"}
        >>> inject_trace_headers(headers)
        >>> response = requests.post(url, headers=headers)
    """
    if not OTEL_AVAILABLE or not _enabled:
        return headers

    try:
        inject(headers)
    except Exception as e:
        logger.debug("Failed to inject trace headers: %s", e)

    return headers


def extract_trace_context(headers: Dict[str, str]) -> Optional[Any]:
    """
    Extract trace context from incoming headers.

    Used for continuing a trace from an upstream service.

    Args:
        headers: Dictionary containing trace headers (e.g., 'traceparent').

    Returns:
        Context object for use with tracer, or None if extraction fails.

    Example:
        >>> context = extract_trace_context(request.headers)
        >>> with tracer.start_as_current_span("handle_request", context=context):
        ...     process_request()
    """
    if not OTEL_AVAILABLE or not _enabled:
        return None

    try:
        return extract(headers)
    except Exception as e:
        logger.debug("Failed to extract trace context: %s", e)
        return None


def inject_celery_headers(task_headers: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inject trace context into Celery task headers.

    Enables trace propagation across Celery task executions.

    Args:
        task_headers: Celery task headers dictionary. Modified in-place.

    Returns:
        The modified headers dictionary.

    Example:
        >>> @celery_app.task(bind=True)
        ... def my_task(self, data):
        ...     headers = {}
        ...     inject_celery_headers(headers)
        ...     another_task.apply_async(args=[data], headers=headers)
    """
    if not OTEL_AVAILABLE or not _enabled:
        return task_headers

    try:
        # Create a carrier dict for trace context
        carrier: Dict[str, str] = {}
        inject(carrier)

        # Store trace context in task headers
        if carrier:
            task_headers['trace_context'] = carrier

    except Exception as e:
        logger.debug("Failed to inject Celery trace headers: %s", e)

    return task_headers


def extract_celery_headers(task_headers: Dict[str, Any]) -> Optional[Any]:
    """
    Extract trace context from Celery task headers.

    Used at the start of a Celery task to continue the trace.

    Args:
        task_headers: Celery task headers dictionary.

    Returns:
        Context object for use with tracer, or None if extraction fails.

    Example:
        >>> @celery_app.task(bind=True)
        ... def my_task(self, data):
        ...     context = extract_celery_headers(self.request.headers or {})
        ...     with start_span("task_execution", context=context):
        ...         process_data(data)
    """
    if not OTEL_AVAILABLE or not _enabled:
        return None

    try:
        carrier = task_headers.get('trace_context', {})
        if carrier:
            return extract(carrier)
    except Exception as e:
        logger.debug("Failed to extract Celery trace context: %s", e)

    return None


def set_span_error(error: Exception) -> None:
    """
    Mark current span as error and record the exception.

    Should be called when an error occurs within a span to ensure
    proper error tracking in the tracing backend.

    Args:
        error: The exception that occurred.

    Example:
        >>> with start_span("risky_operation") as span:
        ...     try:
        ...         do_risky_thing()
        ...     except Exception as e:
        ...         set_span_error(e)
        ...         raise
    """
    if not OTEL_AVAILABLE or not _enabled:
        return

    try:
        span = trace.get_current_span()
        if span is not None:
            span.set_status(Status(StatusCode.ERROR, str(error)))
            span.record_exception(error)
    except Exception as e:
        logger.debug("Failed to set span error: %s", e)


def set_span_attribute(key: str, value: Any) -> None:
    """
    Set an attribute on the current span.

    Args:
        key: Attribute key.
        value: Attribute value (string, int, float, or bool).

    Example:
        >>> with start_span("process_order"):
        ...     set_span_attribute("order.id", order_id)
        ...     set_span_attribute("order.total", total_amount)
        ...     process_order()
    """
    if not OTEL_AVAILABLE or not _enabled:
        return

    try:
        span = trace.get_current_span()
        if span is not None:
            span.set_attribute(key, value)
    except Exception as e:
        logger.debug("Failed to set span attribute: %s", e)


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
    """
    Add an event to the current span.

    Events are time-stamped annotations that can be used to track
    significant moments within a span.

    Args:
        name: Event name.
        attributes: Optional event attributes.

    Example:
        >>> with start_span("checkout"):
        ...     add_span_event("payment_started", {"provider": "stripe"})
        ...     process_payment()
        ...     add_span_event("payment_completed", {"status": "success"})
    """
    if not OTEL_AVAILABLE or not _enabled:
        return

    try:
        span = trace.get_current_span()
        if span is not None:
            span.add_event(name, attributes=attributes or {})
    except Exception as e:
        logger.debug("Failed to add span event: %s", e)


# Core OpenTelemetry tracing utilities.
# Workflow-specific helpers are in apps.templates.tracing_workflow.
