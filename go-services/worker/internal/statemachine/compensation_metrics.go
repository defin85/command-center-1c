package statemachine

import (
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	// compensationTotal tracks total compensation executions by name and status
	compensationTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "saga_compensation_total",
			Help: "Total number of compensation executions",
		},
		[]string{"name", "success"},
	)

	// compensationDuration tracks compensation execution duration
	compensationDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "saga_compensation_duration_seconds",
			Help:    "Duration of compensation execution in seconds",
			Buckets: prometheus.ExponentialBuckets(0.1, 2, 10), // 0.1s to ~100s
		},
		[]string{"name"},
	)

	// compensationAttempts tracks number of retry attempts
	compensationAttempts = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "saga_compensation_attempts",
			Help:    "Number of retry attempts for compensation execution",
			Buckets: []float64{1, 2, 3, 4, 5},
		},
		[]string{"name"},
	)

	// stuckWorkflowsRecovered tracks stuck workflows recovered by watchdog
	stuckWorkflowsRecovered = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "saga_stuck_workflows_recovered_total",
			Help: "Total number of stuck workflows recovered by watchdog",
		},
	)

	// failedEventsStored tracks events stored in PostgreSQL fallback
	failedEventsStored = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "saga_events_fallback_stored_total",
			Help: "Total number of events stored in PostgreSQL fallback",
		},
	)

	// failedEventsReplayed tracks events replayed from PostgreSQL fallback
	failedEventsReplayed = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "saga_events_fallback_replayed_total",
			Help: "Total number of events replayed from PostgreSQL fallback",
		},
	)
)

// PrometheusMetricsRecorder implements MetricsRecorder interface
type PrometheusMetricsRecorder struct{}

// NewPrometheusMetricsRecorder creates a new Prometheus metrics recorder
func NewPrometheusMetricsRecorder() *PrometheusMetricsRecorder {
	return &PrometheusMetricsRecorder{}
}

// RecordCompensation records compensation execution metrics
func (p *PrometheusMetricsRecorder) RecordCompensation(name string, success bool, duration time.Duration, attempts int) {
	successStr := "false"
	if success {
		successStr = "true"
	}

	compensationTotal.WithLabelValues(name, successStr).Inc()
	compensationDuration.WithLabelValues(name).Observe(duration.Seconds())
	compensationAttempts.WithLabelValues(name).Observe(float64(attempts))
}

// RecordStuckWorkflowRecovered increments stuck workflow counter
func RecordStuckWorkflowRecovered() {
	stuckWorkflowsRecovered.Inc()
}

// RecordFailedEventStored increments fallback stored counter
func RecordFailedEventStored() {
	failedEventsStored.Inc()
}

// RecordFailedEventReplayed increments fallback replayed counter
func RecordFailedEventReplayed() {
	failedEventsReplayed.Inc()
}
