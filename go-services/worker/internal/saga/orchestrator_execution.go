package saga

import (
	"context"
	"fmt"
	"time"

	"go.uber.org/zap"
)

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
	if err := o.store.SaveState(ctx, state); err != nil {
		o.logger.Warn("failed to save saga state",
			zap.String("execution_id", state.ExecutionID),
			zap.Error(err),
		)
	}

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
		if err := o.store.SaveState(ctx, state); err != nil {
			o.logger.Warn("failed to save saga state",
				zap.String("execution_id", state.ExecutionID),
				zap.Error(err),
			)
		}

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

			if err := o.store.SaveState(ctx, state); err != nil {
				o.logger.Warn("failed to save saga state",
					zap.String("execution_id", state.ExecutionID),
					zap.Error(err),
				)
			}
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
	if err := o.store.SaveState(ctx, state); err != nil {
		o.logger.Warn("failed to save saga state",
			zap.String("execution_id", state.ExecutionID),
			zap.Error(err),
		)
	}

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
	if err := o.store.SaveState(ctx, state); err != nil {
		o.logger.Warn("failed to save saga state",
			zap.String("execution_id", state.ExecutionID),
			zap.Error(err),
		)
	}

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
