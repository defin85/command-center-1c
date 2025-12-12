package saga

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/events"
)

// OrchestratorConfig holds configuration for the saga orchestrator.
type OrchestratorConfig struct {
	// DefaultStepTimeout is the default timeout for steps without explicit timeout.
	DefaultStepTimeout time.Duration

	// LockTTL is the TTL for execution locks.
	LockTTL time.Duration

	// LockHeartbeatInterval is the interval for lock heartbeat.
	LockHeartbeatInterval time.Duration

	// EnableEvents enables publishing saga events to Redis Streams.
	EnableEvents bool

	// EventChannel is the Redis Stream channel for saga events.
	EventChannel string
}

// DefaultOrchestratorConfig returns default configuration.
func DefaultOrchestratorConfig() *OrchestratorConfig {
	return &OrchestratorConfig{
		DefaultStepTimeout:    5 * time.Minute,
		LockTTL:               5 * time.Minute,
		LockHeartbeatInterval: 1 * time.Minute,
		EnableEvents:          true,
		EventChannel:          "events:saga",
	}
}

// orchestrator implements the SagaOrchestrator interface.
type orchestrator struct {
	store                SagaStore
	compensationExecutor *CompensationExecutor
	compensationRunner   *CompensationRunner
	publisher            *events.Publisher
	logger               *zap.Logger
	config               *OrchestratorConfig
	metrics              *Metrics

	mu    sync.RWMutex
	sagas map[string]*SagaDefinition
}

// NewOrchestrator creates a new saga orchestrator.
func NewOrchestrator(
	store SagaStore,
	publisher *events.Publisher,
	logger *zap.Logger,
	config *OrchestratorConfig,
) SagaOrchestrator {
	if config == nil {
		config = DefaultOrchestratorConfig()
	}
	if logger == nil {
		logger = zap.NewNop()
	}

	compensationExecutor := NewCompensationExecutor(logger)
	compensationRunner := NewCompensationRunner(compensationExecutor, store, logger)

	return &orchestrator{
		store:                store,
		compensationExecutor: compensationExecutor,
		compensationRunner:   compensationRunner,
		publisher:            publisher,
		logger:               logger,
		config:               config,
		metrics:              NewMetrics(),
		sagas:                make(map[string]*SagaDefinition),
	}
}

// RegisterSaga registers a saga definition.
func (o *orchestrator) RegisterSaga(def *SagaDefinition) error {
	if def == nil {
		return ErrInvalidSagaDefinition
	}

	if err := def.Validate(); err != nil {
		return fmt.Errorf("%w: %v", ErrInvalidSagaDefinition, err)
	}

	o.mu.Lock()
	defer o.mu.Unlock()

	if _, exists := o.sagas[def.ID]; exists {
		return ErrSagaAlreadyRegistered
	}

	// Apply default timeout if not set
	if def.DefaultTimeout == 0 {
		def.DefaultTimeout = o.config.DefaultStepTimeout
	}

	o.sagas[def.ID] = def
	o.logger.Info("saga registered",
		zap.String("saga_id", def.ID),
		zap.String("name", def.Name),
		zap.Int("steps", len(def.Steps)),
	)

	return nil
}

// GetSaga returns a registered saga definition.
func (o *orchestrator) GetSaga(sagaID string) (*SagaDefinition, error) {
	o.mu.RLock()
	defer o.mu.RUnlock()

	saga, exists := o.sagas[sagaID]
	if !exists {
		return nil, ErrSagaNotFound
	}

	return saga, nil
}

// Execute starts a new saga execution.
func (o *orchestrator) Execute(ctx context.Context, sagaID string, input map[string]interface{}) (*SagaResult, error) {
	correlationID := uuid.New().String()
	return o.ExecuteWithCorrelation(ctx, sagaID, input, correlationID)
}

// ExecuteWithCorrelation starts a saga with a specific correlation ID.
func (o *orchestrator) ExecuteWithCorrelation(
	ctx context.Context,
	sagaID string,
	input map[string]interface{},
	correlationID string,
) (*SagaResult, error) {
	start := time.Now()

	// Get saga definition
	saga, err := o.GetSaga(sagaID)
	if err != nil {
		return nil, err
	}

	// Generate execution ID
	executionID := uuid.New().String()

	// Create initial state
	state := NewSagaState(executionID, sagaID, correlationID)
	if input != nil {
		state.Variables = input
	}

	// Extract database IDs from input if present
	if dbIDs, ok := input["database_ids"].([]string); ok {
		state.Locks = dbIDs
	} else if dbIDs, ok := input["database_ids"].([]interface{}); ok {
		state.Locks = make([]string, 0, len(dbIDs))
		for _, id := range dbIDs {
			if str, ok := id.(string); ok {
				state.Locks = append(state.Locks, str)
			}
		}
	}

	// Save initial state
	if err := o.store.SaveState(ctx, state); err != nil {
		return nil, fmt.Errorf("failed to save initial state: %w", err)
	}

	// Acquire execution lock
	locked, err := o.store.AcquireLock(ctx, executionID, o.config.LockTTL)
	if err != nil {
		return nil, fmt.Errorf("failed to acquire lock: %w", err)
	}
	if !locked {
		return nil, ErrExecutionAlreadyRunning
	}

	// Ensure lock is released
	defer func() {
		releaseCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		o.store.ReleaseLock(releaseCtx, executionID)
	}()

	// Create saga context
	sagaCtx := state.ToContext()

	// Start metrics and events
	o.metrics.SagasStarted.WithLabelValues(sagaID).Inc()
	o.publishEvent(ctx, SagaEventStarted, executionID, sagaID, correlationID, "", nil, 0)

	// Execute saga
	result := o.executeSaga(ctx, saga, state, sagaCtx)

	// Record metrics
	duration := time.Since(start)
	result.Duration = duration

	o.metrics.SagaDuration.WithLabelValues(sagaID, string(result.Status)).Observe(duration.Seconds())

	switch result.Status {
	case SagaStatusCompleted:
		o.metrics.SagasCompleted.WithLabelValues(sagaID).Inc()
	case SagaStatusFailed:
		o.metrics.SagasFailed.WithLabelValues(sagaID).Inc()
	case SagaStatusCompensated, SagaStatusPartiallyCompensated:
		o.metrics.SagasCompensated.WithLabelValues(sagaID).Inc()
	}

	return result, nil
}

// executeSaga runs the saga steps sequentially.
func (o *orchestrator) executeSaga(
	ctx context.Context,
	saga *SagaDefinition,
	state *SagaState,
	sagaCtx *SagaContext,
) *SagaResult {
	result := &SagaResult{
		ExecutionID:    state.ExecutionID,
		SagaID:         state.SagaID,
		CompletedSteps: make([]string, 0),
	}

	// Update status to running
	state.Status = SagaStatusRunning
	sagaCtx.Status = SagaStatusRunning
	o.store.SaveState(ctx, state)

	// Execute steps
	for i, step := range saga.Steps {
		// Check context cancellation
		select {
		case <-ctx.Done():
			o.logger.Warn("saga execution cancelled",
				zap.String("execution_id", state.ExecutionID),
				zap.String("step_id", step.ID),
			)
			result.Status = SagaStatusFailed
			result.Error = ErrContextCancelled
			result.ErrorMessage = "execution cancelled"
			return o.handleFailure(ctx, saga, state, sagaCtx, result, ErrContextCancelled)
		default:
		}

		// Update current step
		state.CurrentStep = i
		state.CurrentStepID = step.ID
		sagaCtx.CurrentStep = i
		sagaCtx.CurrentStepID = step.ID
		o.store.SaveState(ctx, state)

		// Publish step started event
		o.publishEvent(ctx, SagaEventStepStarted, state.ExecutionID, state.SagaID,
			state.CorrelationID, step.ID, nil, 0)

		// Execute step
		stepResult := o.executeStep(ctx, step, sagaCtx)

		// Store step result
		if state.StepResults == nil {
			state.StepResults = make(map[string]*StepResult)
		}
		state.StepResults[step.ID] = stepResult

		if stepResult.Success {
			// Step succeeded
			state.AddCompletedStep(step.ID, step.HasCompensation())
			result.CompletedSteps = append(result.CompletedSteps, step.ID)

			o.publishEvent(ctx, SagaEventStepCompleted, state.ExecutionID, state.SagaID,
				state.CorrelationID, step.ID, nil, stepResult.Duration)

			o.metrics.StepsCompleted.WithLabelValues(state.SagaID, step.ID).Inc()
			o.metrics.StepDuration.WithLabelValues(state.SagaID, step.ID).Observe(stepResult.Duration.Seconds())

			// Update variables from context
			if sagaCtx.Variables != nil {
				if state.Variables == nil {
					state.Variables = make(map[string]interface{})
				}
				for k, v := range sagaCtx.Variables {
					state.Variables[k] = v
				}
			}

			o.store.SaveState(ctx, state)
		} else {
			// Step failed
			o.logger.Error("step execution failed",
				zap.String("execution_id", state.ExecutionID),
				zap.String("step_id", step.ID),
				zap.String("error", stepResult.Error),
			)

			o.publishEvent(ctx, SagaEventStepFailed, state.ExecutionID, state.SagaID,
				state.CorrelationID, step.ID, stepResult.Error, stepResult.Duration)

			o.metrics.StepsFailed.WithLabelValues(state.SagaID, step.ID).Inc()

			result.Status = SagaStatusFailed
			result.Error = fmt.Errorf("step %s failed: %s", step.ID, stepResult.Error)
			result.ErrorMessage = stepResult.Error

			return o.handleFailure(ctx, saga, state, sagaCtx, result, result.Error)
		}
	}

	// All steps completed successfully
	state.SetCompleted()
	sagaCtx.Status = SagaStatusCompleted
	o.store.SaveState(ctx, state)

	// Call OnComplete callback if defined
	if saga.OnComplete != nil {
		if err := saga.OnComplete(ctx, sagaCtx); err != nil {
			o.logger.Warn("OnComplete callback failed",
				zap.String("execution_id", state.ExecutionID),
				zap.Error(err),
			)
		}
	}

	o.publishEvent(ctx, SagaEventCompleted, state.ExecutionID, state.SagaID,
		state.CorrelationID, "", nil, 0)

	result.Status = SagaStatusCompleted
	result.Output = sagaCtx.Variables

	return result
}

// executeStep executes a single step with timeout and retry.
func (o *orchestrator) executeStep(
	ctx context.Context,
	step *Step,
	sagaCtx *SagaContext,
) *StepResult {
	result := &StepResult{
		StepID:    step.ID,
		StartedAt: time.Now(),
	}

	policy := step.RetryPolicy
	var lastErr error

	maxAttempts := 1
	if policy != nil {
		maxAttempts = policy.MaxRetries + 1
	}

	for attempt := 0; attempt < maxAttempts; attempt++ {
		result.Retries = attempt

		// Apply backoff for retries
		if attempt > 0 && policy != nil {
			backoff := policy.CalculateBackoff(attempt - 1)
			select {
			case <-ctx.Done():
				result.Success = false
				result.Error = "context cancelled during retry backoff"
				result.CompletedAt = time.Now()
				result.Duration = result.CompletedAt.Sub(result.StartedAt)
				return result
			case <-time.After(backoff):
			}
		}

		// Create step context with timeout
		stepCtx := ctx
		var cancel context.CancelFunc
		timeout := step.Timeout
		if timeout == 0 {
			timeout = o.config.DefaultStepTimeout
		}
		if timeout > 0 {
			stepCtx, cancel = context.WithTimeout(ctx, timeout)
		}

		// Execute step
		err := step.Execute(stepCtx, sagaCtx)

		if cancel != nil {
			cancel()
		}

		if err == nil {
			result.Success = true
			result.CompletedAt = time.Now()
			result.Duration = result.CompletedAt.Sub(result.StartedAt)
			return result
		}

		lastErr = err

		// Check if error is retryable
		if policy != nil && !isRetryable(err, policy) {
			break
		}

		o.logger.Warn("step execution failed, retrying",
			zap.String("step_id", step.ID),
			zap.Int("attempt", attempt+1),
			zap.Int("max_attempts", maxAttempts),
			zap.Error(err),
		)
	}

	result.Success = false
	result.CompletedAt = time.Now()
	result.Duration = result.CompletedAt.Sub(result.StartedAt)
	if lastErr != nil {
		result.Error = lastErr.Error()
	}

	return result
}

// handleFailure handles saga failure and starts compensation.
func (o *orchestrator) handleFailure(
	ctx context.Context,
	saga *SagaDefinition,
	state *SagaState,
	sagaCtx *SagaContext,
	result *SagaResult,
	originalErr error,
) *SagaResult {
	// Update state to failed
	state.SetFailed(originalErr)
	sagaCtx.Status = SagaStatusFailed
	sagaCtx.SetError(originalErr)
	o.store.SaveState(ctx, state)

	// Publish failed event
	errMsg := ""
	if originalErr != nil {
		errMsg = originalErr.Error()
	}
	o.publishEvent(ctx, SagaEventFailed, state.ExecutionID, state.SagaID,
		state.CorrelationID, "", errMsg, 0)

	// Call OnFailed callback if defined
	if saga.OnFailed != nil {
		if err := saga.OnFailed(ctx, sagaCtx, originalErr); err != nil {
			o.logger.Warn("OnFailed callback failed",
				zap.String("execution_id", state.ExecutionID),
				zap.Error(err),
			)
		}
	}

	// Check if we need compensation
	if len(state.CompensationStack) == 0 {
		o.logger.Info("no compensation needed",
			zap.String("execution_id", state.ExecutionID),
		)
		return result
	}

	// Start compensation
	o.logger.Info("starting compensation",
		zap.String("execution_id", state.ExecutionID),
		zap.Int("steps_to_compensate", len(state.CompensationStack)),
	)

	o.publishEvent(ctx, SagaEventCompensating, state.ExecutionID, state.SagaID,
		state.CorrelationID, "", nil, 0)

	// Run compensation
	err := o.compensationRunner.Run(ctx, saga, state, sagaCtx)
	if err != nil {
		o.logger.Error("compensation runner failed",
			zap.String("execution_id", state.ExecutionID),
			zap.Error(err),
		)
	}

	// Update result
	result.Status = state.Status
	result.CompensationResults = state.CompensationResults

	// Publish compensated event
	o.publishEvent(ctx, SagaEventCompensated, state.ExecutionID, state.SagaID,
		state.CorrelationID, "", nil, 0)

	// Call OnCompensated callback if defined
	if saga.OnCompensated != nil {
		if err := saga.OnCompensated(ctx, sagaCtx, state.CompensationResults); err != nil {
			o.logger.Warn("OnCompensated callback failed",
				zap.String("execution_id", state.ExecutionID),
				zap.Error(err),
			)
		}
	}

	return result
}

// Resume continues a paused or failed saga execution.
func (o *orchestrator) Resume(ctx context.Context, executionID string) (*SagaResult, error) {
	// Load state
	state, err := o.store.LoadState(ctx, executionID)
	if err != nil {
		return nil, err
	}

	// Check if resumable
	if state.Status.IsFinal() {
		return nil, ErrExecutionCompleted
	}

	// Get saga definition
	saga, err := o.GetSaga(state.SagaID)
	if err != nil {
		return nil, err
	}

	// Acquire lock
	locked, err := o.store.AcquireLock(ctx, executionID, o.config.LockTTL)
	if err != nil {
		return nil, fmt.Errorf("failed to acquire lock: %w", err)
	}
	if !locked {
		return nil, ErrExecutionAlreadyRunning
	}

	defer func() {
		releaseCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		o.store.ReleaseLock(releaseCtx, executionID)
	}()

	// Create saga context from state
	sagaCtx := state.ToContext()

	// If in compensating state, continue compensation
	if state.Status == SagaStatusCompensating {
		result := &SagaResult{
			ExecutionID:    executionID,
			SagaID:         state.SagaID,
			CompletedSteps: state.CompletedSteps,
		}

		err := o.compensationRunner.Run(ctx, saga, state, sagaCtx)
		if err != nil {
			o.logger.Error("resume compensation failed",
				zap.String("execution_id", executionID),
				zap.Error(err),
			)
		}

		result.Status = state.Status
		result.CompensationResults = state.CompensationResults
		return result, nil
	}

	// Resume from current step
	start := time.Now()
	result := o.resumeSaga(ctx, saga, state, sagaCtx)
	result.Duration = time.Since(start)

	return result, nil
}

// resumeSaga resumes saga execution from current step.
func (o *orchestrator) resumeSaga(
	ctx context.Context,
	saga *SagaDefinition,
	state *SagaState,
	sagaCtx *SagaContext,
) *SagaResult {
	result := &SagaResult{
		ExecutionID:    state.ExecutionID,
		SagaID:         state.SagaID,
		CompletedSteps: make([]string, len(state.CompletedSteps)),
	}
	copy(result.CompletedSteps, state.CompletedSteps)

	// Update status to running
	state.Status = SagaStatusRunning
	sagaCtx.Status = SagaStatusRunning
	o.store.SaveState(ctx, state)

	// Find starting step
	startIdx := state.CurrentStep
	if startIdx >= len(saga.Steps) {
		startIdx = 0
	}

	// Execute remaining steps
	for i := startIdx; i < len(saga.Steps); i++ {
		step := saga.Steps[i]

		// Skip already completed steps
		completed := false
		for _, completedID := range state.CompletedSteps {
			if completedID == step.ID {
				completed = true
				break
			}
		}
		if completed {
			continue
		}

		// Check context cancellation
		select {
		case <-ctx.Done():
			result.Status = SagaStatusFailed
			result.Error = ErrContextCancelled
			result.ErrorMessage = "execution cancelled"
			return o.handleFailure(ctx, saga, state, sagaCtx, result, ErrContextCancelled)
		default:
		}

		// Update current step
		state.CurrentStep = i
		state.CurrentStepID = step.ID
		sagaCtx.CurrentStep = i
		sagaCtx.CurrentStepID = step.ID
		o.store.SaveState(ctx, state)

		// Execute step
		stepResult := o.executeStep(ctx, step, sagaCtx)

		if state.StepResults == nil {
			state.StepResults = make(map[string]*StepResult)
		}
		state.StepResults[step.ID] = stepResult

		if stepResult.Success {
			state.AddCompletedStep(step.ID, step.HasCompensation())
			result.CompletedSteps = append(result.CompletedSteps, step.ID)

			if sagaCtx.Variables != nil {
				if state.Variables == nil {
					state.Variables = make(map[string]interface{})
				}
				for k, v := range sagaCtx.Variables {
					state.Variables[k] = v
				}
			}

			o.store.SaveState(ctx, state)
		} else {
			result.Status = SagaStatusFailed
			result.Error = fmt.Errorf("step %s failed: %s", step.ID, stepResult.Error)
			result.ErrorMessage = stepResult.Error

			return o.handleFailure(ctx, saga, state, sagaCtx, result, result.Error)
		}
	}

	// All steps completed
	state.SetCompleted()
	sagaCtx.Status = SagaStatusCompleted
	o.store.SaveState(ctx, state)

	if saga.OnComplete != nil {
		saga.OnComplete(ctx, sagaCtx)
	}

	result.Status = SagaStatusCompleted
	result.Output = sagaCtx.Variables

	return result
}

// GetStatus returns the current status of a saga execution.
func (o *orchestrator) GetStatus(ctx context.Context, executionID string) (*SagaState, error) {
	return o.store.LoadState(ctx, executionID)
}

// Cancel cancels a running saga execution.
func (o *orchestrator) Cancel(ctx context.Context, executionID string) error {
	// Load state
	state, err := o.store.LoadState(ctx, executionID)
	if err != nil {
		return err
	}

	// Check if cancellable
	if state.Status.IsFinal() {
		return ErrExecutionCompleted
	}

	// Get saga definition
	saga, err := o.GetSaga(state.SagaID)
	if err != nil {
		return err
	}

	// Acquire lock
	locked, err := o.store.AcquireLock(ctx, executionID, o.config.LockTTL)
	if err != nil {
		return fmt.Errorf("failed to acquire lock: %w", err)
	}
	if !locked {
		return ErrExecutionAlreadyRunning
	}

	defer func() {
		releaseCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		o.store.ReleaseLock(releaseCtx, executionID)
	}()

	o.logger.Info("cancelling saga execution",
		zap.String("execution_id", executionID),
		zap.Int("steps_to_compensate", len(state.CompensationStack)),
	)

	// Create saga context
	sagaCtx := state.ToContext()
	sagaCtx.SetError(fmt.Errorf("cancelled"))

	o.publishEvent(ctx, SagaEventCancelled, executionID, state.SagaID,
		state.CorrelationID, "", "cancelled by user", 0)

	// Start compensation if needed
	if len(state.CompensationStack) > 0 {
		err := o.compensationRunner.Run(ctx, saga, state, sagaCtx)
		if err != nil {
			o.logger.Error("cancel compensation failed",
				zap.String("execution_id", executionID),
				zap.Error(err),
			)
		}
	} else {
		state.SetFailed(fmt.Errorf("cancelled"))
		o.store.SaveState(ctx, state)
	}

	return nil
}

// Close releases resources.
func (o *orchestrator) Close() error {
	return nil
}

// publishEvent publishes a saga event to Redis Streams.
func (o *orchestrator) publishEvent(
	ctx context.Context,
	eventType SagaEventType,
	executionID, sagaID, correlationID, stepID string,
	errorMsg interface{},
	duration time.Duration,
) {
	if !o.config.EnableEvents || o.publisher == nil {
		return
	}

	event := NewSagaEvent(eventType, executionID, sagaID, correlationID)
	event.StepID = stepID
	event.Duration = duration

	if errStr, ok := errorMsg.(string); ok && errStr != "" {
		event.Error = errStr
	}

	err := o.publisher.Publish(ctx, o.config.EventChannel, string(eventType), event, correlationID)
	if err != nil {
		o.logger.Warn("failed to publish saga event",
			zap.String("event_type", string(eventType)),
			zap.String("execution_id", executionID),
			zap.Error(err),
		)
	}
}

// isRetryable checks if an error should be retried.
func isRetryable(err error, policy *RetryPolicy) bool {
	if policy == nil || err == nil {
		return false
	}

	// If no specific retryable errors defined, retry all errors
	if len(policy.RetryableErrors) == 0 {
		return true
	}

	// Check if error matches any retryable error
	for _, retryable := range policy.RetryableErrors {
		if err == retryable {
			return true
		}
	}

	return false
}

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
