package tracing

import (
	"context"
	"net/http"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
	"go.opentelemetry.io/otel/trace/noop"
)

func setupTestTracer(t *testing.T) {
	t.Helper()
	ctx := context.Background()
	_, err := InitTracing(ctx, Config{
		ServiceName: "test-service",
		Enabled:     false,
	})
	require.NoError(t, err)
}

func TestStartSpan(t *testing.T) {
	setupTestTracer(t)

	ctx := context.Background()
	newCtx, span := StartSpan(ctx, "test-span")

	assert.NotNil(t, span)
	assert.NotEqual(t, ctx, newCtx)

	span.End()
}

func TestStartSpanWithKind(t *testing.T) {
	setupTestTracer(t)

	ctx := context.Background()
	newCtx, span := StartSpanWithKind(ctx, "test-span", trace.SpanKindClient)

	assert.NotNil(t, span)
	assert.NotEqual(t, ctx, newCtx)

	span.End()
}

func TestSpanFromContext(t *testing.T) {
	setupTestTracer(t)

	ctx := context.Background()
	_, span := StartSpan(ctx, "test-span")
	defer span.End()

	// Without span in context
	emptyCtx := context.Background()
	noSpan := SpanFromContext(emptyCtx)
	assert.NotNil(t, noSpan) // Should return noop span
}

func TestContextWithSpan(t *testing.T) {
	setupTestTracer(t)

	ctx := context.Background()
	_, span := StartSpan(ctx, "test-span")
	defer span.End()

	newCtx := ContextWithSpan(ctx, span)
	assert.NotNil(t, newCtx)

	extractedSpan := SpanFromContext(newCtx)
	assert.Equal(t, span.SpanContext(), extractedSpan.SpanContext())
}

func TestHeaderCarrier(t *testing.T) {
	headers := http.Header{}
	carrier := headerCarrier(headers)

	carrier.Set("X-Test-Header", "test-value")
	assert.Equal(t, "test-value", carrier.Get("X-Test-Header"))

	keys := carrier.Keys()
	assert.Contains(t, keys, "X-Test-Header")
}

func TestMapCarrier(t *testing.T) {
	m := make(map[string]string)
	carrier := MapCarrier(m)

	carrier.Set("test-key", "test-value")
	assert.Equal(t, "test-value", carrier.Get("test-key"))

	keys := carrier.Keys()
	assert.Contains(t, keys, "test-key")
}

func TestInjectExtractContext(t *testing.T) {
	setupTestTracer(t)

	ctx := context.Background()
	headers := http.Header{}

	// Inject context into headers
	InjectContext(ctx, headers)

	// Extract context from headers
	extractedCtx := ExtractContext(context.Background(), headers)
	assert.NotNil(t, extractedCtx)
}

func TestInjectExtractContextFromMap(t *testing.T) {
	setupTestTracer(t)

	ctx := context.Background()
	m := make(map[string]string)

	// Inject context into map
	InjectContextToMap(ctx, m)

	// Extract context from map
	extractedCtx := ExtractContextFromMap(context.Background(), m)
	assert.NotNil(t, extractedCtx)
}

func TestGetTraceID_NoSpan(t *testing.T) {
	ctx := context.Background()
	traceID := GetTraceID(ctx)
	assert.Empty(t, traceID)
}

func TestGetSpanID_NoSpan(t *testing.T) {
	ctx := context.Background()
	spanID := GetSpanID(ctx)
	assert.Empty(t, spanID)
}

func TestIsTraceValid_NoSpan(t *testing.T) {
	ctx := context.Background()
	valid := IsTraceValid(ctx)
	assert.False(t, valid)
}

func TestSetSpanError_NilSpan(t *testing.T) {
	// Should not panic
	SetSpanError(nil, nil)
}

func TestSetSpanError_NilError(t *testing.T) {
	setupTestTracer(t)

	ctx := context.Background()
	_, span := StartSpan(ctx, "test-span")
	defer span.End()

	// Should not panic
	SetSpanError(span, nil)
}

func TestSetSpanOK_NilSpan(t *testing.T) {
	// Should not panic
	SetSpanOK(nil)
}

func TestSetSpanAttributes_NilSpan(t *testing.T) {
	// Should not panic
	SetSpanAttributes(nil, attribute.String("key", "value"))
}

func TestInjectWorkflowContext(t *testing.T) {
	setupTestTracer(t)

	ctx := context.Background()
	_, span := StartSpan(ctx, "test-span")
	defer span.End()

	// Should not panic
	InjectWorkflowContext(span, "workflow-1", "exec-1", "node-1")
}

func TestInjectWorkflowContext_NilSpan(t *testing.T) {
	// Should not panic
	InjectWorkflowContext(nil, "workflow-1", "exec-1", "node-1")
}

func TestInjectWorkflowContext_EmptyValues(t *testing.T) {
	setupTestTracer(t)

	ctx := context.Background()
	_, span := StartSpan(ctx, "test-span")
	defer span.End()

	// Should not panic
	InjectWorkflowContext(span, "", "", "")
}

func TestInjectOperationContext(t *testing.T) {
	setupTestTracer(t)

	ctx := context.Background()
	_, span := StartSpan(ctx, "test-span")
	defer span.End()

	// Should not panic
	InjectOperationContext(span, "op-1", "lock_database")
}

func TestInjectOperationContext_NilSpan(t *testing.T) {
	// Should not panic
	InjectOperationContext(nil, "op-1", "lock_database")
}

func TestInjectDatabaseContext(t *testing.T) {
	setupTestTracer(t)

	ctx := context.Background()
	_, span := StartSpan(ctx, "test-span")
	defer span.End()

	// Should not panic
	InjectDatabaseContext(span, "db-1", "TestDB", "cluster-1")
}

func TestInjectDatabaseContext_NilSpan(t *testing.T) {
	// Should not panic
	InjectDatabaseContext(nil, "db-1", "TestDB", "cluster-1")
}

func TestAddEvent(t *testing.T) {
	setupTestTracer(t)

	ctx := context.Background()
	_, span := StartSpan(ctx, "test-span")
	defer span.End()

	// Should not panic
	AddEvent(span, "test-event", attribute.String("key", "value"))
}

func TestAddEvent_NilSpan(t *testing.T) {
	// Should not panic
	AddEvent(nil, "test-event")
}

func TestNewLink(t *testing.T) {
	setupTestTracer(t)

	ctx := context.Background()
	_, span := StartSpan(ctx, "test-span")
	defer span.End()

	link := NewLink(ctx)
	assert.NotNil(t, link)
}

func TestNewLinkWithAttributes(t *testing.T) {
	setupTestTracer(t)

	ctx := context.Background()
	_, span := StartSpan(ctx, "test-span")
	defer span.End()

	link := NewLinkWithAttributes(ctx, attribute.String("key", "value"))
	assert.NotNil(t, link)
	assert.Len(t, link.Attributes, 1)
}

func TestNoopTracerIntegration(t *testing.T) {
	// Test that noop tracer works correctly
	noopProvider := noop.NewTracerProvider()
	tracer := noopProvider.Tracer("test")

	ctx := context.Background()
	ctx, span := tracer.Start(ctx, "test-span")
	assert.NotNil(t, span)

	// Noop span should not have valid trace ID
	assert.False(t, span.SpanContext().HasTraceID())

	span.End()
}
