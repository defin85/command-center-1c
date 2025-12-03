package metrics

import (
	"sync/atomic"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// activeStateMachineCounter tracks the current number of active state machines
// NOTE: Prometheus gauges don't support direct reading of values;
// we use an atomic counter that mirrors the gauge value
var activeStateMachineCounter int64

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

	// StateMachineFinalState - счетчик финальных состояний State Machine
	// Labels: final_state (completed, failed, compensating)
	// Используется для мониторинга Event-Driven execution outcomes
	StateMachineFinalState = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "worker_state_machine_final_state_total",
			Help: "State Machine final states (event-driven mode only)",
		},
		[]string{"final_state"},
	)

	// StateMachineCreated - счетчик созданных State Machine
	// Labels: success (true, false)
	StateMachineCreated = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "worker_state_machine_created_total",
			Help: "State Machine creation attempts",
		},
		[]string{"success"},
	)

	// StateMachineActiveCount - gauge количества активных State Machine
	// Используется для мониторинга текущей нагрузки
	StateMachineActiveCount = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "worker_state_machine_active_count",
			Help: "Number of currently active state machines",
		},
	)

	// StateMachineDuration - histogram общего времени выполнения State Machine
	// Labels: final_state (completed, failed, compensating)
	// Buckets подобраны для long-running операций от 1s до 120s
	StateMachineDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "worker_state_machine_duration_seconds",
			Help:    "Total execution duration of state machine in seconds",
			Buckets: []float64{1, 2.5, 5, 10, 30, 60, 120},
		},
		[]string{"final_state"},
	)

	// StateMachineTimeoutTotal - счетчик timeout событий State Machine
	// Labels: state (init, jobs_locked, sessions_closed, extension_installed)
	StateMachineTimeoutTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "worker_state_machine_timeout_total",
			Help: "Total number of state machine timeouts",
		},
		[]string{"state"},
	)

	// EventDrivenRolloutRequests - счетчик запросов по режиму rollout
	// Labels: selected_mode (event_driven, http_sync), reason (rollout_percent, feature_flag, circuit_breaker)
	EventDrivenRolloutRequests = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "worker_event_driven_rollout_requests_total",
			Help: "Total requests by rollout selection",
		},
		[]string{"selected_mode", "reason"},
	)

	// ClusterResolveDuration - histogram времени резолва cluster info
	// Используется для мониторинга latency Orchestrator API
	ClusterResolveDuration = promauto.NewHistogram(
		prometheus.HistogramOpts{
			Name:    "worker_cluster_resolve_duration_seconds",
			Help:    "Duration of cluster info resolution from Orchestrator",
			Buckets: []float64{.01, .025, .05, .1, .25, .5, 1, 2.5, 5},
		},
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

// --- State Machine specific metrics ---

// validateFinalState ensures final_state is one of expected values
func validateFinalState(state string) string {
	switch state {
	case "completed", "failed", "compensating", "init", "jobs_locked", "sessions_closed", "extension_installed":
		return state
	default:
		return "unknown"
	}
}

// RecordStateMachineFinalState записывает финальное состояние State Machine
func RecordStateMachineFinalState(finalState string) {
	validState := validateFinalState(finalState)
	StateMachineFinalState.WithLabelValues(validState).Inc()
}

// RecordStateMachineCreated записывает попытку создания State Machine
func RecordStateMachineCreated(success bool) {
	successStr := "false"
	if success {
		successStr = "true"
	}
	StateMachineCreated.WithLabelValues(successStr).Inc()
}

// RecordClusterResolveDuration записывает время резолва cluster info
func RecordClusterResolveDuration(durationSeconds float64) {
	ClusterResolveDuration.Observe(durationSeconds)
}

// --- State Machine Active Count ---

// IncActiveStateMachine increases the active State Machine counter
func IncActiveStateMachine() {
	StateMachineActiveCount.Inc()
	atomic.AddInt64(&activeStateMachineCounter, 1)
}

// DecActiveStateMachine decreases the active State Machine counter
// Protected against negative values - if counter would go negative,
// the decrement is ignored (indicates a bug in calling code)
func DecActiveStateMachine() {
	current := atomic.AddInt64(&activeStateMachineCounter, -1)
	if current < 0 {
		// Restore counter - this indicates a bug in calling code
		atomic.AddInt64(&activeStateMachineCounter, 1)
		return
	}
	StateMachineActiveCount.Dec()
}

// GetActiveStateMachineCount returns the current number of active State Machines
// This provides direct access to the counter value for the /rollout-stats endpoint
func GetActiveStateMachineCount() int64 {
	return atomic.LoadInt64(&activeStateMachineCounter)
}

// --- State Machine Duration ---

// validateDurationFinalState validates final_state for duration metric
// More restrictive than validateFinalState - only terminal states
func validateDurationFinalState(state string) string {
	switch state {
	case "completed", "failed", "compensating":
		return state
	default:
		return "unknown"
	}
}

// RecordStateMachineDuration записывает время выполнения State Machine
func RecordStateMachineDuration(finalState string, durationSeconds float64) {
	validState := validateDurationFinalState(finalState)
	StateMachineDuration.WithLabelValues(validState).Observe(durationSeconds)
}

// --- State Machine Timeout ---

// validateTimeoutState validates state for timeout metric
func validateTimeoutState(state string) string {
	switch state {
	case "init", "jobs_locked", "sessions_closed", "extension_installed":
		return state
	default:
		return "unknown"
	}
}

// RecordStateMachineTimeout записывает timeout событие State Machine
func RecordStateMachineTimeout(state string) {
	validState := validateTimeoutState(state)
	StateMachineTimeoutTotal.WithLabelValues(validState).Inc()
}

// --- Rollout Selection ---

// validateRolloutReason validates reason for rollout metric
func validateRolloutReason(reason string) string {
	switch reason {
	case "rollout_percent", "feature_flag", "circuit_breaker":
		return reason
	default:
		return "unknown"
	}
}

// RecordRolloutSelection записывает выбор режима rollout
func RecordRolloutSelection(selectedMode, reason string) {
	validMode := validateMode(selectedMode)
	validReason := validateRolloutReason(reason)
	EventDrivenRolloutRequests.WithLabelValues(validMode, validReason).Inc()
}
