package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

const (
	Namespace = "cc1c"
	Subsystem = "ras"
)

// RASMetrics contains all Prometheus metrics for RAS Adapter
type RASMetrics struct {
	// HTTP metrics
	RequestsTotal   *prometheus.CounterVec
	RequestDuration *prometheus.HistogramVec

	// RAS-specific metrics
	CommandsTotal     *prometheus.CounterVec   // {command_type, status}
	CommandDuration   *prometheus.HistogramVec // {command_type}
	ConnectionsActive prometheus.Gauge
	ConnectionErrors  *prometheus.CounterVec // {error_type}
}

// NewRASMetrics creates and registers all RAS Adapter metrics
func NewRASMetrics() *RASMetrics {
	return &RASMetrics{
		RequestsTotal: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "requests_total",
				Help:      "Total HTTP requests to RAS Adapter",
			},
			[]string{"method", "path", "status"},
		),
		RequestDuration: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "request_duration_seconds",
				Help:      "HTTP request duration in seconds",
				Buckets:   prometheus.DefBuckets,
			},
			[]string{"method", "path"},
		),
		CommandsTotal: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "commands_total",
				Help:      "Total RAS commands executed",
			},
			[]string{"command_type", "status"},
		),
		CommandDuration: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "command_duration_seconds",
				Help:      "RAS command execution duration",
				Buckets:   []float64{0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30},
			},
			[]string{"command_type"},
		),
		ConnectionsActive: promauto.NewGauge(
			prometheus.GaugeOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "connections_active",
				Help:      "Number of active RAS connections",
			},
		),
		ConnectionErrors: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "connection_errors_total",
				Help:      "Total RAS connection errors",
			},
			[]string{"error_type"},
		),
	}
}

// RecordCommand records a RAS command execution
func (m *RASMetrics) RecordCommand(commandType, status string, duration float64) {
	m.CommandsTotal.WithLabelValues(commandType, status).Inc()
	m.CommandDuration.WithLabelValues(commandType).Observe(duration)
}

// RecordConnectionError records a RAS connection error
func (m *RASMetrics) RecordConnectionError(errorType string) {
	m.ConnectionErrors.WithLabelValues(errorType).Inc()
}

// IncrementActiveConnections increments active connection count
func (m *RASMetrics) IncrementActiveConnections() {
	m.ConnectionsActive.Inc()
}

// DecrementActiveConnections decrements active connection count
func (m *RASMetrics) DecrementActiveConnections() {
	m.ConnectionsActive.Dec()
}

// SetActiveConnections sets the current active connection count
func (m *RASMetrics) SetActiveConnections(count float64) {
	m.ConnectionsActive.Set(count)
}
