package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// A/B Testing Metrics для сравнения Event-Driven vs HTTP Sync режимов
// Используются для real-time мониторинга и принятия решений о rollout

var (
	// ExecutionMode - счетчик выполнений по mode
	// Labels: mode (event_driven, http_sync)
	ExecutionMode = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "worker_execution_mode_total",
			Help: "Total executions by mode (event_driven vs http_sync)",
		},
		[]string{"mode"},
	)

	// ExecutionDuration - histogram времени выполнения по mode
	// Buckets подобраны для latency измерений от 10ms до 60s
	// Labels: mode (event_driven, http_sync)
	ExecutionDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "worker_execution_duration_seconds",
			Help:    "Execution duration by mode",
			Buckets: []float64{.01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10, 30, 60},
		},
		[]string{"mode"},
	)

	// ExecutionSuccess - счетчик успешных выполнений по mode
	// Labels: mode (event_driven, http_sync)
	ExecutionSuccess = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "worker_execution_success_total",
			Help: "Successful executions by mode",
		},
		[]string{"mode"},
	)

	// ExecutionFailure - счетчик неудачных выполнений по mode
	// Labels: mode (event_driven, http_sync)
	ExecutionFailure = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "worker_execution_failure_total",
			Help: "Failed executions by mode",
		},
		[]string{"mode"},
	)

	// CompensationExecuted - счетчик compensation actions
	// Labels: mode (event_driven, http_sync), reason (lock_failed, install_failed, etc)
	CompensationExecuted = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "worker_compensation_executed_total",
			Help: "Compensation actions executed",
		},
		[]string{"mode", "reason"},
	)

	// CircuitBreakerTrips - счетчик срабатываний circuit breaker
	// Labels: mode (event_driven, http_sync)
	CircuitBreakerTrips = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "worker_circuit_breaker_trips_total",
			Help: "Circuit breaker trips by mode",
		},
		[]string{"mode"},
	)

	// SuccessRate - gauge текущего success rate (calculated)
	// Labels: mode (event_driven, http_sync)
	// Value range: 0.0-1.0
	SuccessRate = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "worker_success_rate",
			Help: "Current success rate by mode (0.0-1.0)",
		},
		[]string{"mode"},
	)

	// RetryAttempts - счетчик retry попыток по mode
	// Labels: mode (event_driven, http_sync)
	RetryAttempts = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "worker_retry_attempts_total",
			Help: "Total retry attempts by mode",
		},
		[]string{"mode"},
	)

	// QueueDepth - gauge текущей глубины очереди по mode
	// Labels: mode (event_driven, http_sync)
	QueueDepth = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "worker_queue_depth",
			Help: "Current queue depth by mode",
		},
		[]string{"mode"},
	)
)

// validateMode ensures mode is one of the expected values to prevent label explosion
// FIXED: Issue #11 - Prometheus metrics cardinality risk
func validateMode(mode string) string {
	switch mode {
	case "event_driven", "http_sync":
		return mode
	default:
		return "unknown"
	}
}

// RecordExecution записывает метрики выполнения операции
func RecordExecution(mode string, durationSeconds float64, success bool) {
	validMode := validateMode(mode)

	ExecutionMode.WithLabelValues(validMode).Inc()
	ExecutionDuration.WithLabelValues(validMode).Observe(durationSeconds)

	if success {
		ExecutionSuccess.WithLabelValues(validMode).Inc()
	} else {
		ExecutionFailure.WithLabelValues(validMode).Inc()
	}
}

// RecordCompensation записывает метрику compensation action
func RecordCompensation(mode, reason string) {
	validMode := validateMode(mode)
	CompensationExecuted.WithLabelValues(validMode, reason).Inc()
}

// RecordCircuitBreakerTrip записывает срабатывание circuit breaker
func RecordCircuitBreakerTrip(mode string) {
	validMode := validateMode(mode)
	CircuitBreakerTrips.WithLabelValues(validMode).Inc()
}

// RecordRetry записывает retry попытку
func RecordRetry(mode string) {
	validMode := validateMode(mode)
	RetryAttempts.WithLabelValues(validMode).Inc()
}

// UpdateQueueDepth обновляет gauge глубины очереди
func UpdateQueueDepth(mode string, depth int) {
	validMode := validateMode(mode)
	QueueDepth.WithLabelValues(validMode).Set(float64(depth))
}

// UpdateSuccessRate обновляет success rate gauge
// Note: В production лучше использовать Prometheus recording rules
// для расчета success rate вместо manual updates.
// Эта функция оставлена для compatibility и testing purposes.
func UpdateSuccessRate(mode string, rate float64) {
	validMode := validateMode(mode)

	if rate < 0 {
		rate = 0
	}
	if rate > 1 {
		rate = 1
	}
	SuccessRate.WithLabelValues(validMode).Set(rate)
}

// GetMetricsForMode возвращает текущие значения счетчиков для mode
// Используется для debugging и testing
type ModeMetrics struct {
	Mode             string
	TotalExecutions  float64
	SuccessCount     float64
	FailureCount     float64
	CompensationCount float64
	CircuitBreakerTrips float64
	RetryCount       float64
}

// Note: Prometheus Counters не поддерживают прямое чтение значений
// в production. Используйте PromQL queries для получения данных.
// Эта функция для testing purposes only.
