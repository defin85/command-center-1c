package odata

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

const (
	transportOperationUnknown = "unknown"
	transportStatusClassNA    = "n/a"
)

var (
	odataTransportLatencySeconds = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "cc1c_odata_transport_latency_seconds",
			Help:    "OData transport attempt latency by operation/method/status class",
			Buckets: []float64{0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60},
		},
		[]string{"operation", "method", "status_class", "resend_attempt"},
	)
	odataTransportRetriesTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "cc1c_odata_transport_retries_total",
			Help: "OData transport retry scheduling attempts",
		},
		[]string{"operation", "method", "error_class", "status_class"},
	)
	odataTransportErrorsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "cc1c_odata_transport_errors_total",
			Help: "OData transport failed attempts with normalized error labels",
		},
		[]string{"operation", "method", "error_code", "error_class", "status_class", "retryable"},
	)
	odataTransportResendAttemptsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "cc1c_odata_transport_resend_attempt_total",
			Help: "OData transport resend attempts (attempt number > 1)",
		},
		[]string{"operation", "method"},
	)
)

type transportTelemetryKey struct{}

// TransportTraceFunc receives transport trace events with pre-merged metadata.
type TransportTraceFunc func(ctx context.Context, event string, metadata map[string]interface{})

// TransportTelemetry enriches OData transport telemetry labels and optional trace callbacks.
type TransportTelemetry struct {
	Operation   string
	ExecutionID string
	NodeID      string
	DatabaseID  string
	Entity      string
	Trace       TransportTraceFunc
}

// WithTransportTelemetry stores OData transport telemetry metadata in context.
func WithTransportTelemetry(ctx context.Context, telemetry TransportTelemetry) context.Context {
	if ctx == nil {
		ctx = context.Background()
	}
	merged := telemetryFromContext(ctx)

	if value := strings.TrimSpace(telemetry.Operation); value != "" {
		merged.Operation = value
	}
	if value := strings.TrimSpace(telemetry.ExecutionID); value != "" {
		merged.ExecutionID = value
	}
	if value := strings.TrimSpace(telemetry.NodeID); value != "" {
		merged.NodeID = value
	}
	if value := strings.TrimSpace(telemetry.DatabaseID); value != "" {
		merged.DatabaseID = value
	}
	if value := strings.TrimSpace(telemetry.Entity); value != "" {
		merged.Entity = value
	}
	if telemetry.Trace != nil {
		merged.Trace = telemetry.Trace
	}

	return context.WithValue(ctx, transportTelemetryKey{}, merged)
}

func telemetryFromContext(ctx context.Context) TransportTelemetry {
	if ctx == nil {
		return TransportTelemetry{Operation: transportOperationUnknown}
	}
	raw, ok := ctx.Value(transportTelemetryKey{}).(TransportTelemetry)
	if !ok {
		return TransportTelemetry{Operation: transportOperationUnknown}
	}
	if strings.TrimSpace(raw.Operation) == "" {
		raw.Operation = transportOperationUnknown
	}
	return raw
}

func normalizedTransportOperation(ctx context.Context) string {
	value := strings.TrimSpace(telemetryFromContext(ctx).Operation)
	if value == "" {
		return transportOperationUnknown
	}
	return value
}

func normalizedTransportMethod(method string) string {
	value := strings.ToUpper(strings.TrimSpace(method))
	if value == "" {
		return "UNKNOWN"
	}
	return value
}

func normalizeStatusClass(value string) string {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return transportStatusClassNA
	}
	return trimmed
}

func statusClassFromStatusCode(statusCode int) string {
	if statusCode <= 0 {
		return transportStatusClassNA
	}
	return fmt.Sprintf("%dxx", statusCode/100)
}

func recordTransportLatency(
	ctx context.Context,
	method string,
	duration time.Duration,
	statusClass string,
	resendAttempt bool,
) {
	odataTransportLatencySeconds.WithLabelValues(
		normalizedTransportOperation(ctx),
		normalizedTransportMethod(method),
		normalizeStatusClass(statusClass),
		strconv.FormatBool(resendAttempt),
	).Observe(duration.Seconds())
}

func recordTransportRetry(ctx context.Context, method string, normalized NormalizedError) {
	odataTransportRetriesTotal.WithLabelValues(
		normalizedTransportOperation(ctx),
		normalizedTransportMethod(method),
		strings.TrimSpace(normalized.Class),
		normalizeStatusClass(normalized.StatusClass()),
	).Inc()
}

func recordTransportError(ctx context.Context, method string, normalized NormalizedError) {
	odataTransportErrorsTotal.WithLabelValues(
		normalizedTransportOperation(ctx),
		normalizedTransportMethod(method),
		strings.TrimSpace(normalized.Code),
		strings.TrimSpace(normalized.Class),
		normalizeStatusClass(normalized.StatusClass()),
		strconv.FormatBool(normalized.Retryable),
	).Inc()
}

func recordTransportResendAttempt(ctx context.Context, method string) {
	odataTransportResendAttemptsTotal.WithLabelValues(
		normalizedTransportOperation(ctx),
		normalizedTransportMethod(method),
	).Inc()
}

func emitTransportTrace(ctx context.Context, event string, metadata map[string]interface{}) {
	telemetry := telemetryFromContext(ctx)
	if telemetry.Trace == nil {
		return
	}

	payload := make(map[string]interface{}, len(metadata)+5)
	payload["transport_operation"] = normalizedTransportOperation(ctx)
	if telemetry.ExecutionID != "" {
		payload["execution_id"] = telemetry.ExecutionID
	}
	if telemetry.NodeID != "" {
		payload["node_id"] = telemetry.NodeID
	}
	if telemetry.DatabaseID != "" {
		payload["database_id"] = telemetry.DatabaseID
	}
	if telemetry.Entity != "" {
		payload["entity"] = telemetry.Entity
	}
	for key, value := range metadata {
		payload[key] = value
	}

	telemetry.Trace(ctx, event, payload)
}
