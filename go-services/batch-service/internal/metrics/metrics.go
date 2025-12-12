package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

const (
	Namespace = "cc1c"
	Subsystem = "batch"
)

// BatchMetrics contains all Prometheus metrics for Batch Service
type BatchMetrics struct {
	// HTTP metrics
	RequestsTotal   *prometheus.CounterVec
	RequestDuration *prometheus.HistogramVec

	// Batch-specific metrics
	OperationsTotal   *prometheus.CounterVec   // {operation_type, status}
	OperationDuration *prometheus.HistogramVec // {operation_type}

	// v8executor metrics
	V8ExecutionsTotal   *prometheus.CounterVec   // {command, status}
	V8ExecutionDuration *prometheus.HistogramVec // {command}

	// Active operations gauge
	ActiveOperations prometheus.Gauge
}

// NewBatchMetrics creates and registers all Batch Service metrics
func NewBatchMetrics() *BatchMetrics {
	return &BatchMetrics{
		RequestsTotal: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "requests_total",
				Help:      "Total HTTP requests to Batch Service",
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
		OperationsTotal: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "operations_total",
				Help:      "Total batch operations executed",
			},
			[]string{"operation_type", "status"},
		),
		OperationDuration: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "operation_duration_seconds",
				Help:      "Batch operation duration in seconds",
				// Longer buckets for batch operations (can take up to 10 minutes)
				Buckets: []float64{1, 5, 10, 30, 60, 120, 300, 600},
			},
			[]string{"operation_type"},
		),
		V8ExecutionsTotal: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "v8_executions_total",
				Help:      "Total v8executor command executions",
			},
			[]string{"command", "status"},
		),
		V8ExecutionDuration: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "v8_execution_duration_seconds",
				Help:      "v8executor command execution duration",
				// v8 commands can also be long-running
				Buckets: []float64{1, 5, 10, 30, 60, 120, 300},
			},
			[]string{"command"},
		),
		ActiveOperations: promauto.NewGauge(
			prometheus.GaugeOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "active_operations",
				Help:      "Number of currently running batch operations",
			},
		),
	}
}

// RecordOperation records a batch operation execution
func (m *BatchMetrics) RecordOperation(operationType, status string, duration float64) {
	m.OperationsTotal.WithLabelValues(operationType, status).Inc()
	m.OperationDuration.WithLabelValues(operationType).Observe(duration)
}

// RecordV8Execution records a v8executor command execution
func (m *BatchMetrics) RecordV8Execution(command, status string, duration float64) {
	m.V8ExecutionsTotal.WithLabelValues(command, status).Inc()
	m.V8ExecutionDuration.WithLabelValues(command).Observe(duration)
}

// IncrementActiveOperations increments active operation count
func (m *BatchMetrics) IncrementActiveOperations() {
	m.ActiveOperations.Inc()
}

// DecrementActiveOperations decrements active operation count
func (m *BatchMetrics) DecrementActiveOperations() {
	m.ActiveOperations.Dec()
}

// SetActiveOperations sets the current active operation count
func (m *BatchMetrics) SetActiveOperations(count float64) {
	m.ActiveOperations.Set(count)
}

// Operation types for batch operations
const (
	OpExtensionInstall = "extension_install"
	OpExtensionRemove  = "extension_remove"
	OpBackup           = "backup"
	OpRollback         = "rollback"
	OpConfigUpdate     = "config_update"
)

// Status values for operations
const (
	StatusSuccess = "success"
	StatusError   = "error"
)

// V8 command types
const (
	V8CmdInstallExtension = "install_extension"
	V8CmdRemoveExtension  = "remove_extension"
	V8CmdListExtensions   = "list_extensions"
	V8CmdBackup           = "backup"
	V8CmdRestore          = "restore"
)
