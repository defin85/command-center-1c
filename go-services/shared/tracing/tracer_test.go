package tracing

import (
	"context"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestInitTracing_Disabled(t *testing.T) {
	ctx := context.Background()

	tp, err := InitTracing(ctx, Config{
		ServiceName: "test-service",
		Enabled:     false,
	})

	require.NoError(t, err)
	assert.NotNil(t, tp)

	// Should be able to shut down without error
	err = tp.Shutdown(ctx)
	assert.NoError(t, err)
}

func TestInitTracing_EmptyServiceName(t *testing.T) {
	ctx := context.Background()

	tp, err := InitTracing(ctx, Config{
		ServiceName: "",
		Enabled:     true,
	})

	require.Error(t, err)
	assert.Nil(t, tp)
	assert.Contains(t, err.Error(), "service name is required")
}

func TestGetTracer_BeforeInit(t *testing.T) {
	// Reset global state
	globalTracer = nil

	tracer := GetTracer()
	assert.NotNil(t, tracer)
}

func TestGetTracer_AfterInit(t *testing.T) {
	ctx := context.Background()

	tp, err := InitTracing(ctx, Config{
		ServiceName: "test-service",
		Enabled:     false,
	})
	require.NoError(t, err)
	defer tp.Shutdown(ctx)

	tracer := GetTracer()
	assert.NotNil(t, tracer)
}

func TestGetTracerProvider(t *testing.T) {
	ctx := context.Background()

	tp, err := InitTracing(ctx, Config{
		ServiceName: "test-service",
		Enabled:     false,
	})
	require.NoError(t, err)
	defer tp.Shutdown(ctx)

	provider := GetTracerProvider()
	assert.NotNil(t, provider)
	assert.Equal(t, tp, provider)
}

func TestTracerProvider_Shutdown_Idempotent(t *testing.T) {
	ctx := context.Background()

	tp, err := InitTracing(ctx, Config{
		ServiceName: "test-service",
		Enabled:     false,
	})
	require.NoError(t, err)

	// Shutdown should be safe to call multiple times
	err = tp.Shutdown(ctx)
	assert.NoError(t, err)

	err = tp.Shutdown(ctx)
	assert.NoError(t, err)
}

func TestCreateNoopProvider(t *testing.T) {
	tp, err := createNoopProvider("noop-service")

	require.NoError(t, err)
	assert.NotNil(t, tp)

	ctx := context.Background()
	err = tp.Shutdown(ctx)
	assert.NoError(t, err)
}
