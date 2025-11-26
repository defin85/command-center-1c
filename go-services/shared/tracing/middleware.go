package tracing

import (
	"fmt"
	"time"

	"github.com/gin-gonic/gin"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/propagation"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"go.opentelemetry.io/otel/trace"
)

// TracingMiddleware creates a Gin middleware for HTTP request tracing.
// It automatically creates spans for each request and propagates trace context.
func TracingMiddleware() gin.HandlerFunc {
	return TracingMiddlewareWithTracer(GetTracer())
}

// TracingMiddlewareWithTracer creates a Gin middleware with a specific tracer.
func TracingMiddlewareWithTracer(tracer trace.Tracer) gin.HandlerFunc {
	propagator := otel.GetTextMapPropagator()

	return func(c *gin.Context) {
		// Extract trace context from incoming request headers
		ctx := propagator.Extract(c.Request.Context(), propagation.HeaderCarrier(c.Request.Header))

		// Create span name from route pattern or path
		spanName := c.FullPath()
		if spanName == "" {
			spanName = c.Request.URL.Path
		}
		spanName = fmt.Sprintf("%s %s", c.Request.Method, spanName)

		// Start span with HTTP attributes
		ctx, span := tracer.Start(ctx, spanName,
			trace.WithSpanKind(trace.SpanKindServer),
			trace.WithAttributes(
				semconv.HTTPMethod(c.Request.Method),
				semconv.HTTPRoute(c.FullPath()),
				semconv.HTTPTarget(c.Request.URL.Path),
				semconv.HTTPScheme(getScheme(c)),
				semconv.HTTPUserAgent(c.Request.UserAgent()),
				semconv.NetHostName(c.Request.Host),
				semconv.HTTPRequestContentLength(int(c.Request.ContentLength)),
			),
		)
		defer span.End()

		// Add trace and span IDs to response headers for debugging
		if span.SpanContext().HasTraceID() {
			c.Header("X-Trace-ID", span.SpanContext().TraceID().String())
		}
		if span.SpanContext().HasSpanID() {
			c.Header("X-Span-ID", span.SpanContext().SpanID().String())
		}

		// Update request context
		c.Request = c.Request.WithContext(ctx)

		// Record start time
		startTime := time.Now()

		// Process request
		c.Next()

		// Record response attributes
		duration := time.Since(startTime)
		statusCode := c.Writer.Status()

		span.SetAttributes(
			semconv.HTTPStatusCode(statusCode),
			semconv.HTTPResponseContentLength(c.Writer.Size()),
			attribute.Float64("http.duration_ms", float64(duration.Milliseconds())),
		)

		// Set span status based on HTTP status code
		if statusCode >= 400 {
			span.SetStatus(codes.Error, fmt.Sprintf("HTTP %d", statusCode))
		} else {
			span.SetStatus(codes.Ok, "")
		}

		// Record errors if any
		if len(c.Errors) > 0 {
			for _, err := range c.Errors {
				span.RecordError(err.Err)
			}
			span.SetStatus(codes.Error, c.Errors.String())
		}
	}
}

// TracingMiddlewareWithConfig creates a middleware with custom configuration.
type MiddlewareConfig struct {
	// Tracer to use (uses global tracer if nil)
	Tracer trace.Tracer
	// SkipPaths are paths that should not be traced (e.g., health checks)
	SkipPaths []string
	// IncludeRequestBody includes request body in span attributes (use with caution!)
	IncludeRequestBody bool
	// SpanNameFormatter custom function to format span names
	SpanNameFormatter func(c *gin.Context) string
}

// TracingMiddlewareWithConfig creates a middleware with custom configuration.
func TracingMiddlewareWithConfigOptions(cfg MiddlewareConfig) gin.HandlerFunc {
	tracer := cfg.Tracer
	if tracer == nil {
		tracer = GetTracer()
	}

	propagator := otel.GetTextMapPropagator()
	skipPaths := make(map[string]bool)
	for _, path := range cfg.SkipPaths {
		skipPaths[path] = true
	}

	return func(c *gin.Context) {
		// Skip tracing for configured paths
		if skipPaths[c.Request.URL.Path] {
			c.Next()
			return
		}

		// Extract trace context from incoming request headers
		ctx := propagator.Extract(c.Request.Context(), propagation.HeaderCarrier(c.Request.Header))

		// Format span name
		var spanName string
		if cfg.SpanNameFormatter != nil {
			spanName = cfg.SpanNameFormatter(c)
		} else {
			spanName = c.FullPath()
			if spanName == "" {
				spanName = c.Request.URL.Path
			}
			spanName = fmt.Sprintf("%s %s", c.Request.Method, spanName)
		}

		// Start span
		ctx, span := tracer.Start(ctx, spanName,
			trace.WithSpanKind(trace.SpanKindServer),
			trace.WithAttributes(
				semconv.HTTPMethod(c.Request.Method),
				semconv.HTTPRoute(c.FullPath()),
				semconv.HTTPTarget(c.Request.URL.Path),
				semconv.HTTPScheme(getScheme(c)),
				semconv.HTTPUserAgent(c.Request.UserAgent()),
				semconv.NetHostName(c.Request.Host),
			),
		)
		defer span.End()

		// Add trace IDs to response headers
		if span.SpanContext().HasTraceID() {
			c.Header("X-Trace-ID", span.SpanContext().TraceID().String())
		}

		// Update request context
		c.Request = c.Request.WithContext(ctx)

		// Process request
		startTime := time.Now()
		c.Next()
		duration := time.Since(startTime)

		// Record response
		statusCode := c.Writer.Status()
		span.SetAttributes(
			semconv.HTTPStatusCode(statusCode),
			attribute.Float64("http.duration_ms", float64(duration.Milliseconds())),
		)

		if statusCode >= 400 {
			span.SetStatus(codes.Error, fmt.Sprintf("HTTP %d", statusCode))
		} else {
			span.SetStatus(codes.Ok, "")
		}

		if len(c.Errors) > 0 {
			for _, err := range c.Errors {
				span.RecordError(err.Err)
			}
		}
	}
}

// RequestTracingContext extracts the tracing context from a Gin context.
// Useful for getting trace info in handlers.
func RequestTracingContext(c *gin.Context) (traceID, spanID string) {
	span := trace.SpanFromContext(c.Request.Context())
	if span.SpanContext().HasTraceID() {
		traceID = span.SpanContext().TraceID().String()
	}
	if span.SpanContext().HasSpanID() {
		spanID = span.SpanContext().SpanID().String()
	}
	return
}

// StartHandlerSpan creates a child span for a specific handler operation.
// Use this within handlers to trace specific operations.
func StartHandlerSpan(c *gin.Context, name string, opts ...trace.SpanStartOption) (trace.Span, func()) {
	ctx, span := GetTracer().Start(c.Request.Context(), name, opts...)
	c.Request = c.Request.WithContext(ctx)
	return span, func() { span.End() }
}

// getScheme returns the URL scheme (http or https)
func getScheme(c *gin.Context) string {
	if c.Request.TLS != nil {
		return "https"
	}
	// Check X-Forwarded-Proto header for reverse proxy setups
	if proto := c.GetHeader("X-Forwarded-Proto"); proto != "" {
		return proto
	}
	return "http"
}
