package tracing

import (
	"context"
	"net/http"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"
)

// Workflow attribute keys for CC1C context
const (
	WorkflowIDKey   = attribute.Key("cc1c.workflow.id")
	ExecutionIDKey  = attribute.Key("cc1c.workflow.execution_id")
	NodeIDKey       = attribute.Key("cc1c.workflow.node_id")
	OperationIDKey  = attribute.Key("cc1c.operation.id")
	OperationTypeKey = attribute.Key("cc1c.operation.type")
	DatabaseIDKey   = attribute.Key("cc1c.database.id")
	DatabaseNameKey = attribute.Key("cc1c.database.name")
	ClusterIDKey    = attribute.Key("cc1c.cluster.id")
)

// StartSpan creates a new span with the given name and options.
// Returns the context with the span and the span itself.
func StartSpan(ctx context.Context, name string, opts ...trace.SpanStartOption) (context.Context, trace.Span) {
	return GetTracer().Start(ctx, name, opts...)
}

// StartSpanWithKind creates a new span with a specific kind.
func StartSpanWithKind(ctx context.Context, name string, kind trace.SpanKind, opts ...trace.SpanStartOption) (context.Context, trace.Span) {
	opts = append(opts, trace.WithSpanKind(kind))
	return GetTracer().Start(ctx, name, opts...)
}

// SpanFromContext returns the current span from context.
// If no span is present, returns a noop span.
func SpanFromContext(ctx context.Context) trace.Span {
	return trace.SpanFromContext(ctx)
}

// ContextWithSpan returns a copy of parent context with the given span.
func ContextWithSpan(parent context.Context, span trace.Span) context.Context {
	return trace.ContextWithSpan(parent, span)
}

// headerCarrier adapts http.Header to the TextMapCarrier interface
type headerCarrier http.Header

func (hc headerCarrier) Get(key string) string {
	return http.Header(hc).Get(key)
}

func (hc headerCarrier) Set(key, value string) {
	http.Header(hc).Set(key, value)
}

func (hc headerCarrier) Keys() []string {
	keys := make([]string, 0, len(hc))
	for k := range hc {
		keys = append(keys, k)
	}
	return keys
}

// InjectContext injects the current trace context into HTTP headers.
// Used when making outgoing HTTP requests to propagate trace context.
func InjectContext(ctx context.Context, headers http.Header) {
	otel.GetTextMapPropagator().Inject(ctx, headerCarrier(headers))
}

// ExtractContext extracts trace context from HTTP headers.
// Used when receiving incoming HTTP requests to continue the trace.
func ExtractContext(ctx context.Context, headers http.Header) context.Context {
	return otel.GetTextMapPropagator().Extract(ctx, headerCarrier(headers))
}

// MapCarrier adapts map[string]string to the TextMapCarrier interface.
// Useful for propagating context through message queues or other non-HTTP transports.
type MapCarrier map[string]string

func (mc MapCarrier) Get(key string) string {
	return mc[key]
}

func (mc MapCarrier) Set(key, value string) {
	mc[key] = value
}

func (mc MapCarrier) Keys() []string {
	keys := make([]string, 0, len(mc))
	for k := range mc {
		keys = append(keys, k)
	}
	return keys
}

// InjectContextToMap injects trace context into a map.
// Useful for Redis/message queue propagation.
func InjectContextToMap(ctx context.Context, carrier map[string]string) {
	otel.GetTextMapPropagator().Inject(ctx, MapCarrier(carrier))
}

// ExtractContextFromMap extracts trace context from a map.
func ExtractContextFromMap(ctx context.Context, carrier map[string]string) context.Context {
	return otel.GetTextMapPropagator().Extract(ctx, MapCarrier(carrier))
}

// GetTraceID returns the trace ID from the current span context.
// Returns empty string if no span is present.
func GetTraceID(ctx context.Context) string {
	span := trace.SpanFromContext(ctx)
	if !span.SpanContext().HasTraceID() {
		return ""
	}
	return span.SpanContext().TraceID().String()
}

// GetSpanID returns the span ID from the current span context.
// Returns empty string if no span is present.
func GetSpanID(ctx context.Context) string {
	span := trace.SpanFromContext(ctx)
	if !span.SpanContext().HasSpanID() {
		return ""
	}
	return span.SpanContext().SpanID().String()
}

// IsTraceValid returns true if the context contains a valid trace.
func IsTraceValid(ctx context.Context) bool {
	span := trace.SpanFromContext(ctx)
	return span.SpanContext().IsValid()
}

// SetSpanError marks the span as errored with the given error.
func SetSpanError(span trace.Span, err error) {
	if err == nil || span == nil {
		return
	}
	span.RecordError(err)
	span.SetStatus(codes.Error, err.Error())
}

// SetSpanOK marks the span as successful.
func SetSpanOK(span trace.Span) {
	if span == nil {
		return
	}
	span.SetStatus(codes.Ok, "")
}

// SetSpanAttributes sets multiple attributes on a span.
func SetSpanAttributes(span trace.Span, attrs ...attribute.KeyValue) {
	if span == nil {
		return
	}
	span.SetAttributes(attrs...)
}

// InjectWorkflowContext adds workflow-specific attributes to a span.
// This provides correlation for distributed tracing across workflow execution.
func InjectWorkflowContext(span trace.Span, workflowID, executionID, nodeID string) {
	if span == nil {
		return
	}

	attrs := []attribute.KeyValue{}

	if workflowID != "" {
		attrs = append(attrs, WorkflowIDKey.String(workflowID))
	}
	if executionID != "" {
		attrs = append(attrs, ExecutionIDKey.String(executionID))
	}
	if nodeID != "" {
		attrs = append(attrs, NodeIDKey.String(nodeID))
	}

	if len(attrs) > 0 {
		span.SetAttributes(attrs...)
	}
}

// InjectOperationContext adds operation-specific attributes to a span.
func InjectOperationContext(span trace.Span, operationID, operationType string) {
	if span == nil {
		return
	}

	attrs := []attribute.KeyValue{}

	if operationID != "" {
		attrs = append(attrs, OperationIDKey.String(operationID))
	}
	if operationType != "" {
		attrs = append(attrs, OperationTypeKey.String(operationType))
	}

	if len(attrs) > 0 {
		span.SetAttributes(attrs...)
	}
}

// InjectDatabaseContext adds database-specific attributes to a span.
func InjectDatabaseContext(span trace.Span, databaseID, databaseName, clusterID string) {
	if span == nil {
		return
	}

	attrs := []attribute.KeyValue{}

	if databaseID != "" {
		attrs = append(attrs, DatabaseIDKey.String(databaseID))
	}
	if databaseName != "" {
		attrs = append(attrs, DatabaseNameKey.String(databaseName))
	}
	if clusterID != "" {
		attrs = append(attrs, ClusterIDKey.String(clusterID))
	}

	if len(attrs) > 0 {
		span.SetAttributes(attrs...)
	}
}

// AddEvent adds an event to the span with optional attributes.
func AddEvent(span trace.Span, name string, attrs ...attribute.KeyValue) {
	if span == nil {
		return
	}
	span.AddEvent(name, trace.WithAttributes(attrs...))
}

// NewLink creates a new span link to another trace context.
// Useful for linking related operations across different traces.
func NewLink(ctx context.Context) trace.Link {
	return trace.LinkFromContext(ctx)
}

// NewLinkWithAttributes creates a new span link with additional attributes.
func NewLinkWithAttributes(ctx context.Context, attrs ...attribute.KeyValue) trace.Link {
	return trace.Link{
		SpanContext: trace.SpanFromContext(ctx).SpanContext(),
		Attributes:  attrs,
	}
}
