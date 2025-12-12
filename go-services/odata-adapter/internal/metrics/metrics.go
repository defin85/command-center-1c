package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

const (
	Namespace = "cc1c"
	Subsystem = "odata"
)

// ODataMetrics contains all Prometheus metrics for OData Adapter
type ODataMetrics struct {
	// HTTP metrics
	RequestsTotal   *prometheus.CounterVec
	RequestDuration *prometheus.HistogramVec

	// OData operations
	OperationsTotal   *prometheus.CounterVec   // {operation, status}
	OperationDuration *prometheus.HistogramVec // {operation}

	// 1C transactions (CRITICAL: must be < 15s!)
	TransactionDuration *prometheus.HistogramVec // {operation} - buckets up to 15s!

	// Batch operations
	BatchSize       *prometheus.HistogramVec // {operation}
	BatchItemsTotal *prometheus.CounterVec   // {operation, status}

	// Connections
	ConnectionsActive prometheus.Gauge
	ConnectionErrors  *prometheus.CounterVec // {error_type}
}

// NewODataMetrics creates and registers all OData Adapter metrics
func NewODataMetrics() *ODataMetrics {
	return &ODataMetrics{
		RequestsTotal: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "requests_total",
				Help:      "Total HTTP requests to OData Adapter",
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
				Help:      "Total OData operations",
			},
			[]string{"operation", "status"}, // operation: query, create, update, delete, batch
		),
		OperationDuration: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "operation_duration_seconds",
				Help:      "OData operation duration",
				Buckets:   []float64{0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30},
			},
			[]string{"operation"},
		),
		// CRITICAL metric for monitoring 15s limit!
		TransactionDuration: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "transaction_duration_seconds",
				Help:      "1C transaction duration - CRITICAL: must be < 15s",
				// Buckets optimized for 15s SLA alerting
				Buckets: []float64{0.5, 1, 2, 5, 8, 10, 12, 14, 15, 20, 30},
			},
			[]string{"operation"},
		),
		BatchSize: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "batch_size",
				Help:      "Number of items in batch operations",
				Buckets:   []float64{1, 10, 50, 100, 200, 500, 1000},
			},
			[]string{"operation"},
		),
		BatchItemsTotal: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "batch_items_total",
				Help:      "Total items processed in batch operations",
			},
			[]string{"operation", "status"},
		),
		ConnectionsActive: promauto.NewGauge(
			prometheus.GaugeOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "connections_active",
				Help:      "Number of active OData connections",
			},
		),
		ConnectionErrors: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: Namespace,
				Subsystem: Subsystem,
				Name:      "connection_errors_total",
				Help:      "Total OData connection errors",
			},
			[]string{"error_type"},
		),
	}
}

// RecordOperation records an OData operation execution
func (m *ODataMetrics) RecordOperation(operation, status string, duration float64) {
	m.OperationsTotal.WithLabelValues(operation, status).Inc()
	m.OperationDuration.WithLabelValues(operation).Observe(duration)
}

// RecordTransaction records a 1C transaction duration (CRITICAL: must be < 15s!)
// Use this for operations that directly interact with 1C database (create, update, delete, batch)
// Query operations typically don't need transaction tracking as they are read-only
func (m *ODataMetrics) RecordTransaction(operation string, duration float64) {
	m.TransactionDuration.WithLabelValues(operation).Observe(duration)
}

// RecordBatch records a batch operation with item counts
func (m *ODataMetrics) RecordBatch(operation string, size int, successCount, failCount int) {
	m.BatchSize.WithLabelValues(operation).Observe(float64(size))
	m.BatchItemsTotal.WithLabelValues(operation, StatusSuccess).Add(float64(successCount))
	m.BatchItemsTotal.WithLabelValues(operation, StatusError).Add(float64(failCount))
}

// RecordConnectionError records an OData connection error
func (m *ODataMetrics) RecordConnectionError(errorType string) {
	m.ConnectionErrors.WithLabelValues(errorType).Inc()
}

// IncrementActiveConnections increments active connection count
func (m *ODataMetrics) IncrementActiveConnections() {
	m.ConnectionsActive.Inc()
}

// DecrementActiveConnections decrements active connection count
func (m *ODataMetrics) DecrementActiveConnections() {
	m.ConnectionsActive.Dec()
}

// SetActiveConnections sets the current active connection count
func (m *ODataMetrics) SetActiveConnections(count float64) {
	m.ConnectionsActive.Set(count)
}

// Operation types for OData operations
const (
	OpQuery  = "query"
	OpCreate = "create"
	OpUpdate = "update"
	OpDelete = "delete"
	OpBatch  = "batch"
)

// Status values for operations
const (
	StatusSuccess = "success"
	StatusError   = "error"
)

// Connection error types
const (
	ErrTypeTimeout     = "timeout"
	ErrTypeConnection  = "connection"
	ErrTypeAuth        = "auth"
	ErrTypeServerError = "server_error"
)
