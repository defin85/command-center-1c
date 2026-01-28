from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from .tracing_core import (
    OTEL_AVAILABLE,
    SpanKind,
    add_span_event,
    get_current_span_id,
    get_current_trace_id,
    start_span,
)


@contextmanager
def start_workflow_span(
    workflow_id: str,
    workflow_name: str,
    execution_id: str,
    template_id: Optional[str] = None,
) -> Generator[Any, None, None]:
    attributes = {
        "workflow.id": workflow_id,
        "workflow.name": workflow_name,
        "workflow.execution_id": execution_id,
    }

    if template_id:
        attributes["workflow.template_id"] = template_id

    with start_span(
        name=f"workflow:{workflow_name}",
        attributes=attributes,
        kind=SpanKind.INTERNAL if OTEL_AVAILABLE else None,
    ) as span:
        yield span


@contextmanager
def start_node_span(
    node_id: str,
    node_name: str,
    node_type: str,
    execution_id: str,
    workflow_id: Optional[str] = None,
    workflow_name: Optional[str] = None,
) -> Generator[Any, None, None]:
    attributes = {
        "workflow.node.id": node_id,
        "workflow.node.name": node_name,
        "workflow.node.type": node_type,
        "workflow.execution_id": execution_id,
    }

    if workflow_id:
        attributes["workflow.id"] = workflow_id
    if workflow_name:
        attributes["workflow.name"] = workflow_name

    with start_span(name=f"node:{node_type}:{node_name}", attributes=attributes) as span:
        yield span


@contextmanager
def start_operation_span(
    operation_type: str,
    target_id: str,
    target_name: Optional[str] = None,
    execution_id: Optional[str] = None,
) -> Generator[Any, None, None]:
    attributes = {
        "operation.type": operation_type,
        "operation.target.id": target_id,
    }

    if target_name:
        attributes["operation.target.name"] = target_name
    if execution_id:
        attributes["workflow.execution_id"] = execution_id

    span_kind = SpanKind.CLIENT if OTEL_AVAILABLE else None

    with start_span(
        name=f"operation:{operation_type}",
        attributes=attributes,
        kind=span_kind,
    ) as span:
        yield span


def trace_workflow_event(
    event_name: str,
    execution_id: str,
    event_data: Optional[Dict[str, Any]] = None,
) -> None:
    attributes = {"workflow.execution_id": execution_id, **(event_data or {})}
    add_span_event(f"workflow.{event_name}", attributes)


def get_trace_context_for_logging() -> Dict[str, str]:
    return {
        "trace_id": get_current_trace_id(),
        "span_id": get_current_span_id(),
    }
