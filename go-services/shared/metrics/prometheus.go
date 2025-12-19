package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// Metrics holds all application metrics
type Metrics struct {
	// API Gateway metrics
	RequestsTotal   *prometheus.CounterVec
	RequestDuration *prometheus.HistogramVec

	// Worker metrics
	TasksProcessed *prometheus.CounterVec
	TaskDuration   *prometheus.HistogramVec
	ActiveWorkers  prometheus.Gauge
	QueueDepth     prometheus.Gauge

	// 1C operations metrics
	OneCOperations *prometheus.CounterVec
	OneCErrors     *prometheus.CounterVec

	// Worker driver metrics (Phase A: Driver framework)
	DriverExecutions *prometheus.CounterVec
	DriverDuration   *prometheus.HistogramVec
}

// NewMetrics creates and registers all metrics
func NewMetrics(namespace string) *Metrics {
	return &Metrics{
		// API Gateway metrics
		RequestsTotal: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: namespace,
				Name:      "requests_total",
				Help:      "Total number of HTTP requests",
			},
			[]string{"method", "path", "status"},
		),
		RequestDuration: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Namespace: namespace,
				Name:      "request_duration_seconds",
				Help:      "HTTP request latencies in seconds",
				Buckets:   prometheus.DefBuckets,
			},
			[]string{"method", "path"},
		),

		// Worker metrics
		TasksProcessed: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: namespace,
				Name:      "tasks_processed_total",
				Help:      "Total number of processed tasks",
			},
			[]string{"task_type", "status"},
		),
		TaskDuration: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Namespace: namespace,
				Name:      "task_duration_seconds",
				Help:      "Task processing duration in seconds",
				Buckets:   prometheus.DefBuckets,
			},
			[]string{"task_type"},
		),
		ActiveWorkers: promauto.NewGauge(
			prometheus.GaugeOpts{
				Namespace: namespace,
				Name:      "active_workers",
				Help:      "Number of currently active workers",
			},
		),
		QueueDepth: promauto.NewGauge(
			prometheus.GaugeOpts{
				Namespace: namespace,
				Name:      "queue_depth",
				Help:      "Current depth of task queue",
			},
		),

		// 1C operations metrics
		OneCOperations: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: namespace,
				Name:      "onec_operations_total",
				Help:      "Total number of 1C operations",
			},
			[]string{"operation_type", "database", "status"},
		),
		OneCErrors: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: namespace,
				Name:      "onec_errors_total",
				Help:      "Total number of 1C operation errors",
			},
			[]string{"operation_type", "error_type"},
		),

		DriverExecutions: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: namespace,
				Name:      "driver_executions_total",
				Help:      "Total number of worker driver executions",
			},
			[]string{"driver", "operation_type", "status"},
		),
		DriverDuration: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Namespace: namespace,
				Name:      "driver_duration_seconds",
				Help:      "Worker driver execution duration in seconds",
				Buckets:   prometheus.DefBuckets,
			},
			[]string{"driver", "operation_type"},
		),
	}
}
