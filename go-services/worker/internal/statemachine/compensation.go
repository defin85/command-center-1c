package statemachine

import (
	"context"
	"fmt"
)

// pushCompensation adds compensation action to stack
func (sm *ExtensionInstallStateMachine) pushCompensation(name string, action func(context.Context) error) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	sm.compensationStack = append(sm.compensationStack, CompensationAction{
		Name:   name,
		Action: action,
	})

	fmt.Printf("[StateMachine] Added compensation: %s\n", name)
}

// executeCompensations executes compensation actions in LIFO order with retry logic
func (sm *ExtensionInstallStateMachine) executeCompensations(ctx context.Context) error {
	fmt.Printf("[StateMachine] Executing compensations (count=%d)\n", len(sm.compensationStack))

	// Record compensation start in timeline
	sm.timeline.Record(ctx, sm.OperationID, "saga.compensation.started", map[string]string{
		"compensation_count": fmt.Sprintf("%d", len(sm.compensationStack)),
		"correlation_id":     sm.CorrelationID,
	})

	ctx, cancel := context.WithTimeout(ctx, sm.config.TimeoutCompensation)
	defer cancel()

	results := make([]*CompensationResult, 0, len(sm.compensationStack))

	// Execute in reverse order (LIFO)
	for i := len(sm.compensationStack) - 1; i >= 0; i-- {
		comp := sm.compensationStack[i]

		fmt.Printf("[StateMachine] Executing compensation: %s\n", comp.Name)

		// Record compensation step start
		sm.timeline.Record(ctx, sm.OperationID, "saga.compensation.step", map[string]string{
			"step":           comp.Name,
			"status":         "started",
			"correlation_id": sm.CorrelationID,
		})

		var result *CompensationResult

		// Use executor if available, otherwise fallback to simple execution
		if sm.compensationExecutor != nil {
			result = sm.compensationExecutor.ExecuteWithRetry(ctx, sm.OperationID, comp)
		} else {
			// Fallback: simple execution without retry
			result = sm.executeCompensationSimple(ctx, comp)
		}

		results = append(results, result)

		if result.Success {
			fmt.Printf("[StateMachine] Compensation %s succeeded (attempts=%d, duration=%v)\n",
				comp.Name, result.Attempts, result.TotalDuration)
			// Record successful compensation in timeline
			sm.timeline.Record(ctx, sm.OperationID, "saga.compensation.step", map[string]string{
				"step":           comp.Name,
				"status":         "completed",
				"attempts":       fmt.Sprintf("%d", result.Attempts),
				"correlation_id": sm.CorrelationID,
			})
		} else {
			fmt.Printf("[StateMachine] Compensation %s failed: %s (attempts=%d)\n",
				comp.Name, result.Error, result.Attempts)
			// Record failed compensation in timeline
			sm.timeline.Record(ctx, sm.OperationID, "saga.compensation.step", map[string]string{
				"step":           comp.Name,
				"status":         "failed",
				"error":          result.Error,
				"attempts":       fmt.Sprintf("%d", result.Attempts),
				"correlation_id": sm.CorrelationID,
			})
			// Continue with other compensations even if one failed
		}
	}

	// Publish compensation summary to Orchestrator
	sm.publishCompensationSummary(ctx, results)

	// All compensations executed
	// Transition to Failed (will be done by main loop automatically)
	sm.transitionTo(StateFailed)
	return nil
}

// executeCompensationSimple executes compensation without retry (fallback)
func (sm *ExtensionInstallStateMachine) executeCompensationSimple(ctx context.Context, comp CompensationAction) *CompensationResult {
	result := &CompensationResult{
		Name:     comp.Name,
		Attempts: 1,
	}

	err := comp.Action(ctx)
	if err != nil {
		result.Success = false
		result.Error = err.Error()
	} else {
		result.Success = true
	}

	return result
}

// publishCompensationSummary publishes compensation results to Orchestrator via events
func (sm *ExtensionInstallStateMachine) publishCompensationSummary(ctx context.Context, results []*CompensationResult) {
	summary := NewCompensationSummary(sm.OperationID, results)

	fmt.Printf("[StateMachine] Publishing compensation summary: total=%d, success=%d, failed=%d\n",
		summary.TotalActions, summary.SuccessCount, summary.FailedCount)

	// Publish event for Orchestrator
	eventType := "worker:compensation:completed"
	channel := "events:worker:compensation"

	payload := map[string]interface{}{
		"operation_id":   summary.OperationID,
		"database_id":    sm.DatabaseID,
		"total_actions":  summary.TotalActions,
		"success_count":  summary.SuccessCount,
		"failed_count":   summary.FailedCount,
		"total_duration": summary.TotalDuration.String(),
		"all_succeeded":  summary.AllSucceeded(),
		"results":        summary.Results,
		"completed_at":   summary.CompletedAt,
	}

	if err := sm.publisher.Publish(ctx, channel, eventType, payload, sm.CorrelationID); err != nil {
		fmt.Printf("[StateMachine] Failed to publish compensation summary: %v\n", err)
	}
}
