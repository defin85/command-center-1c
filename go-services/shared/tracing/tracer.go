// Package tracing provides OpenTelemetry tracing utilities for CC1C services.
package tracing

import (
	"context"
	"fmt"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"go.opentelemetry.io/otel/trace"
	"go.opentelemetry.io/otel/trace/noop"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// Config holds tracing configuration
type Config struct {
	ServiceName    string
	ServiceVersion string
	Environment    string
	OTLPEndpoint   string // e.g., "localhost:4317"
	Enabled        bool
}

// TracerProvider wraps the SDK TracerProvider with shutdown capability
type TracerProvider struct {
	provider trace.TracerProvider
	shutdown func(context.Context) error
}

// globalTracer holds the global tracer instance
var globalTracer trace.Tracer

// globalTracerProvider holds the global tracer provider
var globalTracerProvider *TracerProvider

// InitTracing initializes OpenTelemetry tracing with the given configuration.
// Returns a TracerProvider that should be shut down when the application exits.
func InitTracing(ctx context.Context, cfg Config) (*TracerProvider, error) {
	// If tracing is disabled, return a noop tracer provider
	if !cfg.Enabled {
		noopProvider := noop.NewTracerProvider()
		globalTracer = noopProvider.Tracer(cfg.ServiceName)
		globalTracerProvider = &TracerProvider{
			provider: noopProvider,
			shutdown: func(context.Context) error { return nil },
		}
		return globalTracerProvider, nil
	}

	// Validate required configuration
	if cfg.ServiceName == "" {
		return nil, fmt.Errorf("service name is required")
	}

	if cfg.OTLPEndpoint == "" {
		cfg.OTLPEndpoint = "localhost:4317"
	}

	// Create OTLP exporter with gRPC
	conn, err := grpc.NewClient(
		cfg.OTLPEndpoint,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		// Graceful degradation: return noop tracer on connection error
		return createNoopProvider(cfg.ServiceName)
	}

	exporter, err := otlptracegrpc.New(ctx, otlptracegrpc.WithGRPCConn(conn))
	if err != nil {
		// Graceful degradation: return noop tracer on exporter error
		return createNoopProvider(cfg.ServiceName)
	}

	// Create resource with service information
	res, err := resource.New(ctx,
		resource.WithAttributes(
			semconv.ServiceName(cfg.ServiceName),
			semconv.ServiceVersion(cfg.ServiceVersion),
			semconv.DeploymentEnvironment(cfg.Environment),
		),
		resource.WithHost(),
		resource.WithProcess(),
		resource.WithTelemetrySDK(),
	)
	if err != nil {
		// Use default resource if creation fails
		res = resource.Default()
	}

	// Create TracerProvider with batch span processor
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter,
			sdktrace.WithBatchTimeout(5*time.Second),
			sdktrace.WithMaxExportBatchSize(512),
			sdktrace.WithMaxQueueSize(2048),
		),
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)

	// Set global tracer provider and propagator
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	// Store global tracer
	globalTracer = tp.Tracer(cfg.ServiceName)

	globalTracerProvider = &TracerProvider{
		provider: tp,
		shutdown: tp.Shutdown,
	}

	return globalTracerProvider, nil
}

// Shutdown gracefully shuts down the tracer provider
func (tp *TracerProvider) Shutdown(ctx context.Context) error {
	if tp.shutdown == nil {
		return nil
	}
	return tp.shutdown(ctx)
}

// GetTracer returns the global tracer
func GetTracer() trace.Tracer {
	if globalTracer == nil {
		// Return noop tracer if not initialized
		return noop.NewTracerProvider().Tracer("uninitialized")
	}
	return globalTracer
}

// GetTracerProvider returns the global tracer provider
func GetTracerProvider() *TracerProvider {
	return globalTracerProvider
}

// createNoopProvider creates a noop tracer provider for graceful degradation
func createNoopProvider(serviceName string) (*TracerProvider, error) {
	noopProvider := noop.NewTracerProvider()
	globalTracer = noopProvider.Tracer(serviceName)
	globalTracerProvider = &TracerProvider{
		provider: noopProvider,
		shutdown: func(context.Context) error { return nil },
	}
	return globalTracerProvider, nil
}
