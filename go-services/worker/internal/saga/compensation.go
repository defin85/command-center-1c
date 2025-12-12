package saga

import (
	"context"
	"fmt"
	"sync"
	"time"

	"go.uber.org/zap"
)

// CompensationExecutor handles saga compensation with retry logic.
type CompensationExecutor struct {
	logger        *zap.Logger
	defaultPolicy *RetryPolicy
	mu            sync.Mutex
}

// NewCompensationExecutor creates a new compensation executor.
func NewCompensationExecutor(logger *zap.Logger) *CompensationExecutor {
	if logger == nil {
		logger = zap.NewNop()
	}

	return &CompensationExecutor{
		logger:        logger,
		defaultPolicy: DefaultCompensationRetryPolicy(),
	}
}

// SetDefaultPolicy sets the default retry policy for compensation.
func (e *CompensationExecutor) SetDefaultPolicy(policy *RetryPolicy) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.defaultPolicy = policy
}

// Execute runs compensation for a list of steps in reverse order.
// It attempts to compensate all steps, collecting results.
// Failures are logged but don't stop compensation of remaining steps.
func (e *CompensationExecutor) Execute(
	ctx context.Context,
	saga *SagaDefinition,
	state *SagaState,
	sagaCtx *SagaContext,
) []CompensationResult {
	results := make([]CompensationResult, 0, len(state.CompensationStack))

	// Process compensation stack in LIFO order
	for len(state.CompensationStack) > 0 {
		stepID, ok := state.PopCompensationStep()
		if !ok {
			break
		}

		step := saga.GetStep(stepID)
		if step == nil {
			e.logger.Error("step not found for compensation",
				zap.String("execution_id", state.ExecutionID),
				zap.String("step_id", stepID),
			)
			results = append(results, CompensationResult{
				StepID:  stepID,
				Success: false,
				Error:   fmt.Sprintf("step not found: %s", stepID),
			})
			continue
		}

		result := e.compensateStep(ctx, step, sagaCtx)
		results = append(results, result)

		// Log result
		if result.Success {
			e.logger.Info("step compensation succeeded",
				zap.String("execution_id", state.ExecutionID),
				zap.String("step_id", stepID),
				zap.Duration("duration", result.Duration),
				zap.Int("retries", result.Retries),
			)
		} else {
			e.logger.Error("step compensation failed",
				zap.String("execution_id", state.ExecutionID),
				zap.String("step_id", stepID),
				zap.String("error", result.Error),
				zap.Int("retries", result.Retries),
			)
		}
	}

	return results
}

// compensateStep executes compensation for a single step with retry.
func (e *CompensationExecutor) compensateStep(
	ctx context.Context,
	step *Step,
	sagaCtx *SagaContext,
) CompensationResult {
	result := CompensationResult{
		StepID: step.ID,
	}

	if step.Compensate == nil {
		// No compensation function - consider it success
		result.Success = true
		return result
	}

	// Get retry policy
	policy := step.CompensationRetryPolicy
	if policy == nil {
		e.mu.Lock()
		policy = e.defaultPolicy
		e.mu.Unlock()
	}

	start := time.Now()
	var lastErr error

	for attempt := 0; attempt <= policy.MaxRetries; attempt++ {
		result.Retries = attempt

		// Check context cancellation
		select {
		case <-ctx.Done():
			result.Success = false
			result.Error = "context cancelled during compensation"
			result.Duration = time.Since(start)
			return result
		default:
		}

		// Apply backoff for retries
		if attempt > 0 {
			backoff := policy.CalculateBackoff(attempt - 1)
			select {
			case <-ctx.Done():
				result.Success = false
				result.Error = "context cancelled during backoff"
				result.Duration = time.Since(start)
				return result
			case <-time.After(backoff):
			}
		}

		// Create step context with timeout
		stepCtx := ctx
		var cancel context.CancelFunc
		if step.Timeout > 0 {
			stepCtx, cancel = context.WithTimeout(ctx, step.Timeout)
		}

		// Execute compensation
		err := step.Compensate(stepCtx, sagaCtx)

		if cancel != nil {
			cancel()
		}

		if err == nil {
			result.Success = true
			result.Duration = time.Since(start)
			return result
		}

		lastErr = err
		e.logger.Warn("compensation attempt failed",
			zap.String("step_id", step.ID),
			zap.Int("attempt", attempt+1),
			zap.Int("max_retries", policy.MaxRetries),
			zap.Error(err),
		)
	}

	// All retries exhausted
	result.Success = false
	result.Duration = time.Since(start)
	if lastErr != nil {
		result.Error = lastErr.Error()
	}

	return result
}

// ExecuteSingle executes compensation for a single step.
func (e *CompensationExecutor) ExecuteSingle(
	ctx context.Context,
	step *Step,
	sagaCtx *SagaContext,
) CompensationResult {
	return e.compensateStep(ctx, step, sagaCtx)
}

// ExecuteParallel executes compensation for multiple steps in parallel.
// Use with caution - only for steps that are independent.
func (e *CompensationExecutor) ExecuteParallel(
	ctx context.Context,
	steps []*Step,
	sagaCtx *SagaContext,
) []CompensationResult {
	if len(steps) == 0 {
		return nil
	}

	results := make([]CompensationResult, len(steps))
	var wg sync.WaitGroup

	for i, step := range steps {
		wg.Add(1)
		go func(idx int, s *Step) {
			defer wg.Done()
			// Clone context to prevent data races
			ctxClone := sagaCtx.Clone()
			results[idx] = e.compensateStep(ctx, s, ctxClone)
		}(i, step)
	}

	wg.Wait()
	return results
}

// CompensationRunner manages compensation execution with state persistence.
type CompensationRunner struct {
	executor *CompensationExecutor
	store    SagaStore
	logger   *zap.Logger
}

// NewCompensationRunner creates a new compensation runner.
func NewCompensationRunner(
	executor *CompensationExecutor,
	store SagaStore,
	logger *zap.Logger,
) *CompensationRunner {
	if logger == nil {
		logger = zap.NewNop()
	}

	return &CompensationRunner{
		executor: executor,
		store:    store,
		logger:   logger,
	}
}

// Run executes compensation with state persistence.
func (r *CompensationRunner) Run(
	ctx context.Context,
	saga *SagaDefinition,
	state *SagaState,
	sagaCtx *SagaContext,
) error {
	// Update status to compensating
	state.SetCompensating()
	sagaCtx.Status = SagaStatusCompensating

	if err := r.store.SaveState(ctx, state); err != nil {
		r.logger.Error("failed to save compensating state",
			zap.String("execution_id", state.ExecutionID),
			zap.Error(err),
		)
		// Continue with compensation anyway
	}

	// Execute compensation
	results := r.executor.Execute(ctx, saga, state, sagaCtx)

	// Update state with results
	state.SetCompensated(results)
	sagaCtx.Status = state.Status

	// Check if all compensations succeeded
	allSuccess := true
	for _, result := range results {
		if !result.Success {
			allSuccess = false
			break
		}
	}

	if !allSuccess {
		r.logger.Warn("compensation completed with failures",
			zap.String("execution_id", state.ExecutionID),
			zap.Int("total_steps", len(results)),
			zap.Int("failed_steps", countFailedCompensations(results)),
		)
	}

	// Save final state
	if err := r.store.SaveState(ctx, state); err != nil {
		r.logger.Error("failed to save compensated state",
			zap.String("execution_id", state.ExecutionID),
			zap.Error(err),
		)
		return fmt.Errorf("failed to save compensated state: %w", err)
	}

	return nil
}

// countFailedCompensations counts failed compensations in results.
func countFailedCompensations(results []CompensationResult) int {
	count := 0
	for _, r := range results {
		if !r.Success {
			count++
		}
	}
	return count
}

// CompensationError wraps compensation failures with detailed results.
type CompensationError struct {
	OriginalError error
	Results       []CompensationResult
}

func (e *CompensationError) Error() string {
	failed := countFailedCompensations(e.Results)
	if e.OriginalError != nil {
		return fmt.Sprintf("compensation failed for %d/%d steps (original: %v)",
			failed, len(e.Results), e.OriginalError)
	}
	return fmt.Sprintf("compensation failed for %d/%d steps", failed, len(e.Results))
}

func (e *CompensationError) Unwrap() error {
	return e.OriginalError
}

// IsCompensationError checks if an error is a CompensationError.
func IsCompensationError(err error) bool {
	_, ok := err.(*CompensationError)
	return ok
}

// NewCompensationError creates a new CompensationError.
func NewCompensationError(original error, results []CompensationResult) *CompensationError {
	return &CompensationError{
		OriginalError: original,
		Results:       results,
	}
}
