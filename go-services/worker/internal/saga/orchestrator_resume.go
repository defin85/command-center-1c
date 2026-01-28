package saga

import (
	"context"
	"fmt"
	"time"

	"go.uber.org/zap"
)

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
		if err := o.store.ReleaseLock(releaseCtx, executionID); err != nil {
			o.logger.Warn("failed to release saga lock",
				zap.String("execution_id", executionID),
				zap.Error(err),
			)
		}
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
	if err := o.store.SaveState(ctx, state); err != nil {
		o.logger.Warn("failed to save saga state",
			zap.String("execution_id", state.ExecutionID),
			zap.Error(err),
		)
	}

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
		if err := o.store.SaveState(ctx, state); err != nil {
			o.logger.Warn("failed to save saga state",
				zap.String("execution_id", state.ExecutionID),
				zap.Error(err),
			)
		}

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

			if err := o.store.SaveState(ctx, state); err != nil {
				o.logger.Warn("failed to save saga state",
					zap.String("execution_id", state.ExecutionID),
					zap.Error(err),
				)
			}
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
	if err := o.store.SaveState(ctx, state); err != nil {
		o.logger.Warn("failed to save saga state",
			zap.String("execution_id", state.ExecutionID),
			zap.Error(err),
		)
	}

	if saga.OnComplete != nil {
		if err := saga.OnComplete(ctx, sagaCtx); err != nil {
			o.logger.Warn("OnComplete callback failed",
				zap.String("execution_id", state.ExecutionID),
				zap.Error(err),
			)
		}
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
		if err := o.store.ReleaseLock(releaseCtx, executionID); err != nil {
			o.logger.Warn("failed to release saga lock",
				zap.String("execution_id", executionID),
				zap.Error(err),
			)
		}
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
		if err := o.store.SaveState(ctx, state); err != nil {
			o.logger.Warn("failed to save saga state",
				zap.String("execution_id", state.ExecutionID),
				zap.Error(err),
			)
		}
	}

	return nil
}

// Close releases resources.
func (o *orchestrator) Close() error {
	return nil
}
