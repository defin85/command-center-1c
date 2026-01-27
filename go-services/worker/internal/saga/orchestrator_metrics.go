package saga

import (
	"sync"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// Metrics for saga orchestrator.
type Metrics struct {
	// SagasStarted counts started sagas by saga ID.
	SagasStarted *prometheus.CounterVec

	// SagasCompleted counts completed sagas by saga ID.
	SagasCompleted *prometheus.CounterVec

	// SagasFailed counts failed sagas by saga ID.
	SagasFailed *prometheus.CounterVec

	// SagasCompensated counts compensated sagas by saga ID.
	SagasCompensated *prometheus.CounterVec

	// SagaDuration measures saga execution duration.
	SagaDuration *prometheus.HistogramVec

	// StepsCompleted counts completed steps by saga ID and step ID.
	StepsCompleted *prometheus.CounterVec

	// StepsFailed counts failed steps by saga ID and step ID.
	StepsFailed *prometheus.CounterVec

	// StepDuration measures step execution duration.
	StepDuration *prometheus.HistogramVec
}

var (
	globalSagaMetrics     *Metrics
	globalSagaMetricsOnce sync.Once
)

// NewMetrics returns singleton Prometheus metrics for saga orchestrator.
func NewMetrics() *Metrics {
	globalSagaMetricsOnce.Do(func() {
		globalSagaMetrics = &Metrics{
			SagasStarted: promauto.NewCounterVec(
				prometheus.CounterOpts{
					Namespace: "cc1c",
					Subsystem: "saga",
					Name:      "started_total",
					Help:      "Total number of sagas started",
				},
				[]string{"saga_id"},
			),

			SagasCompleted: promauto.NewCounterVec(
				prometheus.CounterOpts{
					Namespace: "cc1c",
					Subsystem: "saga",
					Name:      "completed_total",
					Help:      "Total number of sagas completed successfully",
				},
				[]string{"saga_id"},
			),

			SagasFailed: promauto.NewCounterVec(
				prometheus.CounterOpts{
					Namespace: "cc1c",
					Subsystem: "saga",
					Name:      "failed_total",
					Help:      "Total number of sagas failed",
				},
				[]string{"saga_id"},
			),

			SagasCompensated: promauto.NewCounterVec(
				prometheus.CounterOpts{
					Namespace: "cc1c",
					Subsystem: "saga",
					Name:      "compensated_total",
					Help:      "Total number of sagas that triggered compensation",
				},
				[]string{"saga_id"},
			),

			SagaDuration: promauto.NewHistogramVec(
				prometheus.HistogramOpts{
					Namespace: "cc1c",
					Subsystem: "saga",
					Name:      "duration_seconds",
					Help:      "Saga execution duration in seconds",
					Buckets:   []float64{0.1, 0.5, 1, 5, 10, 30, 60, 120, 300, 600},
				},
				[]string{"saga_id", "status"},
			),

			StepsCompleted: promauto.NewCounterVec(
				prometheus.CounterOpts{
					Namespace: "cc1c",
					Subsystem: "saga",
					Name:      "steps_completed_total",
					Help:      "Total number of saga steps completed",
				},
				[]string{"saga_id", "step_id"},
			),

			StepsFailed: promauto.NewCounterVec(
				prometheus.CounterOpts{
					Namespace: "cc1c",
					Subsystem: "saga",
					Name:      "steps_failed_total",
					Help:      "Total number of saga steps failed",
				},
				[]string{"saga_id", "step_id"},
			),

			StepDuration: promauto.NewHistogramVec(
				prometheus.HistogramOpts{
					Namespace: "cc1c",
					Subsystem: "saga",
					Name:      "step_duration_seconds",
					Help:      "Saga step execution duration in seconds",
					Buckets:   []float64{0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30, 60},
				},
				[]string{"saga_id", "step_id"},
			),
		}
	})
	return globalSagaMetrics
}
