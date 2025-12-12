package saga

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"
)

func TestNewSagaContext(t *testing.T) {
	ctx := NewSagaContext("test-saga", "exec-1", "corr-1")

	assert.Equal(t, "test-saga", ctx.SagaID)
	assert.Equal(t, "exec-1", ctx.ExecutionID)
	assert.Equal(t, "corr-1", ctx.CorrelationID)
	assert.Equal(t, SagaStatusPending, ctx.Status)
	assert.NotNil(t, ctx.Variables)
}

func TestSagaContextVariables(t *testing.T) {
	ctx := NewSagaContext("test-saga", "exec-1", "corr-1")

	// Test Set and Get
	ctx.Set("key1", "value1")
	val, ok := ctx.Get("key1")
	assert.True(t, ok)
	assert.Equal(t, "value1", val)

	// Test GetString
	ctx.Set("string_key", "hello")
	assert.Equal(t, "hello", ctx.GetString("string_key"))
	assert.Equal(t, "", ctx.GetString("nonexistent"))

	// Test GetBool
	ctx.Set("bool_key", true)
	assert.True(t, ctx.GetBool("bool_key"))
	assert.False(t, ctx.GetBool("nonexistent"))

	// Test GetStringSlice
	ctx.Set("slice_key", []string{"a", "b", "c"})
	slice := ctx.GetStringSlice("slice_key")
	assert.Equal(t, []string{"a", "b", "c"}, slice)

	// Test GetStringSlice with []interface{}
	ctx.Set("interface_slice", []interface{}{"x", "y", "z"})
	slice2 := ctx.GetStringSlice("interface_slice")
	assert.Equal(t, []string{"x", "y", "z"}, slice2)
}

func TestSagaContextClone(t *testing.T) {
	ctx := NewSagaContext("test-saga", "exec-1", "corr-1")
	ctx.Set("key", "value")
	ctx.DatabaseIDs = []string{"db-1", "db-2"}
	ctx.CurrentStep = 5
	ctx.Status = SagaStatusRunning

	clone := ctx.Clone()

	// Verify clone has same values
	assert.Equal(t, ctx.SagaID, clone.SagaID)
	assert.Equal(t, ctx.ExecutionID, clone.ExecutionID)
	assert.Equal(t, ctx.CurrentStep, clone.CurrentStep)
	assert.Equal(t, ctx.Status, clone.Status)

	// Verify independence
	clone.Set("key", "new_value")
	assert.Equal(t, "value", ctx.GetString("key"))
	assert.Equal(t, "new_value", clone.GetString("key"))

	clone.DatabaseIDs[0] = "modified"
	assert.Equal(t, "db-1", ctx.DatabaseIDs[0])
}

func TestSagaDefinitionValidation(t *testing.T) {
	tests := []struct {
		name    string
		saga    *SagaDefinition
		wantErr bool
	}{
		{
			name:    "empty ID",
			saga:    &SagaDefinition{},
			wantErr: true,
		},
		{
			name:    "no steps",
			saga:    &SagaDefinition{ID: "test"},
			wantErr: true,
		},
		{
			name: "step without ID",
			saga: &SagaDefinition{
				ID: "test",
				Steps: []*Step{
					{Execute: func(ctx context.Context, sagaCtx *SagaContext) error { return nil }},
				},
			},
			wantErr: true,
		},
		{
			name: "step without Execute",
			saga: &SagaDefinition{
				ID: "test",
				Steps: []*Step{
					{ID: "step1"},
				},
			},
			wantErr: true,
		},
		{
			name: "duplicate step IDs",
			saga: &SagaDefinition{
				ID: "test",
				Steps: []*Step{
					{ID: "step1", Execute: func(ctx context.Context, sagaCtx *SagaContext) error { return nil }},
					{ID: "step1", Execute: func(ctx context.Context, sagaCtx *SagaContext) error { return nil }},
				},
			},
			wantErr: true,
		},
		{
			name: "valid saga",
			saga: &SagaDefinition{
				ID:   "test",
				Name: "Test Saga",
				Steps: []*Step{
					{
						ID:      "step1",
						Name:    "Step 1",
						Execute: func(ctx context.Context, sagaCtx *SagaContext) error { return nil },
					},
					{
						ID:      "step2",
						Name:    "Step 2",
						Execute: func(ctx context.Context, sagaCtx *SagaContext) error { return nil },
					},
				},
			},
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.saga.Validate()
			if tt.wantErr {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestSagaState(t *testing.T) {
	state := NewSagaState("exec-1", "saga-1", "corr-1")

	assert.Equal(t, SagaStatusPending, state.Status)
	assert.Empty(t, state.CompletedSteps)
	assert.Empty(t, state.CompensationStack)

	// Test AddCompletedStep
	state.AddCompletedStep("step1", true)
	assert.Equal(t, []string{"step1"}, state.CompletedSteps)
	assert.Equal(t, []string{"step1"}, state.CompensationStack)

	state.AddCompletedStep("step2", false) // No compensation
	assert.Equal(t, []string{"step1", "step2"}, state.CompletedSteps)
	assert.Equal(t, []string{"step1"}, state.CompensationStack) // step2 not added

	state.AddCompletedStep("step3", true)
	assert.Equal(t, []string{"step1", "step3"}, state.CompensationStack)

	// Test PopCompensationStep (LIFO order)
	stepID, ok := state.PopCompensationStep()
	assert.True(t, ok)
	assert.Equal(t, "step3", stepID)

	stepID, ok = state.PopCompensationStep()
	assert.True(t, ok)
	assert.Equal(t, "step1", stepID)

	stepID, ok = state.PopCompensationStep()
	assert.False(t, ok)
	assert.Empty(t, stepID)
}

func TestSagaStateStatusTransitions(t *testing.T) {
	state := NewSagaState("exec-1", "saga-1", "corr-1")

	// Test SetCompleted
	state.SetCompleted()
	assert.Equal(t, SagaStatusCompleted, state.Status)
	assert.NotNil(t, state.CompletedAt)

	// Reset for next test
	state = NewSagaState("exec-2", "saga-1", "corr-1")

	// Test SetFailed
	state.SetFailed(errors.New("test error"))
	assert.Equal(t, SagaStatusFailed, state.Status)
	assert.Equal(t, "test error", state.Error)
	assert.NotNil(t, state.CompletedAt)

	// Reset for compensation test
	state = NewSagaState("exec-3", "saga-1", "corr-1")
	state.AddCompletedStep("step1", true)

	// Test SetCompensating
	state.SetCompensating()
	assert.Equal(t, SagaStatusCompensating, state.Status)

	// Test SetCompensated with all success
	results := []CompensationResult{
		{StepID: "step1", Success: true},
	}
	state.SetCompensated(results)
	assert.Equal(t, SagaStatusCompensated, state.Status)

	// Test SetCompensated with partial failure
	state = NewSagaState("exec-4", "saga-1", "corr-1")
	state.AddCompletedStep("step1", true)
	state.AddCompletedStep("step2", true)
	state.SetCompensating()

	results = []CompensationResult{
		{StepID: "step2", Success: true},
		{StepID: "step1", Success: false, Error: "compensation failed"},
	}
	state.SetCompensated(results)
	assert.Equal(t, SagaStatusPartiallyCompensated, state.Status)
}

func TestInMemorySagaStore(t *testing.T) {
	store := NewInMemorySagaStore()
	ctx := context.Background()

	// Test SaveState and LoadState
	state := NewSagaState("exec-1", "saga-1", "corr-1")
	err := store.SaveState(ctx, state)
	require.NoError(t, err)

	loaded, err := store.LoadState(ctx, "exec-1")
	require.NoError(t, err)
	assert.Equal(t, state.ExecutionID, loaded.ExecutionID)
	assert.Equal(t, state.SagaID, loaded.SagaID)

	// Test LoadState not found
	_, err = store.LoadState(ctx, "nonexistent")
	assert.Equal(t, ErrExecutionNotFound, err)

	// Test ListByStatus
	state2 := NewSagaState("exec-2", "saga-1", "corr-2")
	state2.Status = SagaStatusRunning
	store.SaveState(ctx, state2)

	running, err := store.ListByStatus(ctx, SagaStatusRunning, 10)
	require.NoError(t, err)
	assert.Len(t, running, 1)
	assert.Equal(t, "exec-2", running[0].ExecutionID)

	// Test DeleteState
	err = store.DeleteState(ctx, "exec-1")
	require.NoError(t, err)

	_, err = store.LoadState(ctx, "exec-1")
	assert.Equal(t, ErrExecutionNotFound, err)

	// Test AcquireLock
	locked, err := store.AcquireLock(ctx, "exec-2", time.Minute)
	require.NoError(t, err)
	assert.True(t, locked)

	// Try to acquire same lock
	locked, err = store.AcquireLock(ctx, "exec-2", time.Minute)
	require.NoError(t, err)
	assert.False(t, locked)

	// Release and reacquire
	err = store.ReleaseLock(ctx, "exec-2")
	require.NoError(t, err)

	locked, err = store.AcquireLock(ctx, "exec-2", time.Minute)
	require.NoError(t, err)
	assert.True(t, locked)
}

func TestRetryPolicyBackoff(t *testing.T) {
	policy := &RetryPolicy{
		MaxRetries:     5,
		InitialBackoff: 100 * time.Millisecond,
		MaxBackoff:     2 * time.Second,
		BackoffFactor:  2.0,
	}

	// Test initial backoff
	assert.Equal(t, 100*time.Millisecond, policy.CalculateBackoff(0))

	// Test exponential backoff
	assert.Equal(t, 200*time.Millisecond, policy.CalculateBackoff(1))
	assert.Equal(t, 400*time.Millisecond, policy.CalculateBackoff(2))
	assert.Equal(t, 800*time.Millisecond, policy.CalculateBackoff(3))
	assert.Equal(t, 1600*time.Millisecond, policy.CalculateBackoff(4))

	// Test max backoff cap
	assert.Equal(t, 2*time.Second, policy.CalculateBackoff(5))
	assert.Equal(t, 2*time.Second, policy.CalculateBackoff(10))
}

func TestOrchestratorRegisterSaga(t *testing.T) {
	store := NewInMemorySagaStore()
	logger := zap.NewNop()
	orch := NewOrchestrator(store, nil, logger, nil)

	saga := &SagaDefinition{
		ID:   "test-saga",
		Name: "Test Saga",
		Steps: []*Step{
			{
				ID:      "step1",
				Execute: func(ctx context.Context, sagaCtx *SagaContext) error { return nil },
			},
		},
	}

	// Register saga
	err := orch.RegisterSaga(saga)
	require.NoError(t, err)

	// Get registered saga
	retrieved, err := orch.GetSaga("test-saga")
	require.NoError(t, err)
	assert.Equal(t, saga.ID, retrieved.ID)

	// Try to register duplicate
	err = orch.RegisterSaga(saga)
	assert.Equal(t, ErrSagaAlreadyRegistered, err)

	// Try to get non-existent saga
	_, err = orch.GetSaga("nonexistent")
	assert.Equal(t, ErrSagaNotFound, err)
}

func TestOrchestratorExecuteSuccess(t *testing.T) {
	store := NewInMemorySagaStore()
	logger := zap.NewNop()
	config := DefaultOrchestratorConfig()
	config.EnableEvents = false
	orch := NewOrchestrator(store, nil, logger, config)

	var step1Called, step2Called atomic.Bool

	saga := &SagaDefinition{
		ID:   "success-saga",
		Name: "Success Saga",
		Steps: []*Step{
			{
				ID:   "step1",
				Name: "Step 1",
				Execute: func(ctx context.Context, sagaCtx *SagaContext) error {
					step1Called.Store(true)
					sagaCtx.Set("step1_result", "done")
					return nil
				},
				Compensate: func(ctx context.Context, sagaCtx *SagaContext) error {
					return nil
				},
			},
			{
				ID:   "step2",
				Name: "Step 2",
				Execute: func(ctx context.Context, sagaCtx *SagaContext) error {
					step2Called.Store(true)
					// Verify step1 result is available
					if sagaCtx.GetString("step1_result") != "done" {
						return errors.New("step1_result not found")
					}
					sagaCtx.Set("final_result", "success")
					return nil
				},
				Compensate: func(ctx context.Context, sagaCtx *SagaContext) error {
					return nil
				},
			},
		},
	}

	err := orch.RegisterSaga(saga)
	require.NoError(t, err)

	ctx := context.Background()
	result, err := orch.Execute(ctx, "success-saga", map[string]interface{}{
		"input_param": "value",
	})

	require.NoError(t, err)
	assert.Equal(t, SagaStatusCompleted, result.Status)
	assert.True(t, step1Called.Load())
	assert.True(t, step2Called.Load())
	assert.Equal(t, []string{"step1", "step2"}, result.CompletedSteps)
	assert.Equal(t, "success", result.Output["final_result"])
}

func TestOrchestratorExecuteFailureWithCompensation(t *testing.T) {
	store := NewInMemorySagaStore()
	logger := zap.NewNop()
	config := DefaultOrchestratorConfig()
	config.EnableEvents = false
	orch := NewOrchestrator(store, nil, logger, config)

	var step1Compensated, step2Compensated atomic.Bool
	var compensationOrder []string
	var orderMu sync.Mutex

	saga := &SagaDefinition{
		ID:   "fail-saga",
		Name: "Fail Saga",
		Steps: []*Step{
			{
				ID:   "step1",
				Name: "Step 1",
				Execute: func(ctx context.Context, sagaCtx *SagaContext) error {
					return nil
				},
				Compensate: func(ctx context.Context, sagaCtx *SagaContext) error {
					step1Compensated.Store(true)
					orderMu.Lock()
					compensationOrder = append(compensationOrder, "step1")
					orderMu.Unlock()
					return nil
				},
			},
			{
				ID:   "step2",
				Name: "Step 2",
				Execute: func(ctx context.Context, sagaCtx *SagaContext) error {
					return nil
				},
				Compensate: func(ctx context.Context, sagaCtx *SagaContext) error {
					step2Compensated.Store(true)
					orderMu.Lock()
					compensationOrder = append(compensationOrder, "step2")
					orderMu.Unlock()
					return nil
				},
			},
			{
				ID:   "step3",
				Name: "Step 3 - Fails",
				Execute: func(ctx context.Context, sagaCtx *SagaContext) error {
					return errors.New("step3 failed")
				},
			},
		},
	}

	err := orch.RegisterSaga(saga)
	require.NoError(t, err)

	ctx := context.Background()
	result, err := orch.Execute(ctx, "fail-saga", nil)

	require.NoError(t, err)
	assert.Equal(t, SagaStatusCompensated, result.Status)
	assert.True(t, step1Compensated.Load())
	assert.True(t, step2Compensated.Load())
	assert.Contains(t, result.ErrorMessage, "step3 failed")

	// Verify compensation order is LIFO (step2 then step1)
	orderMu.Lock()
	assert.Equal(t, []string{"step2", "step1"}, compensationOrder)
	orderMu.Unlock()
}

func TestOrchestratorExecuteWithRetry(t *testing.T) {
	store := NewInMemorySagaStore()
	logger := zap.NewNop()
	config := DefaultOrchestratorConfig()
	config.EnableEvents = false
	orch := NewOrchestrator(store, nil, logger, config)

	var attempts atomic.Int32

	saga := &SagaDefinition{
		ID:   "retry-saga",
		Name: "Retry Saga",
		Steps: []*Step{
			{
				ID:   "retry-step",
				Name: "Retry Step",
				Execute: func(ctx context.Context, sagaCtx *SagaContext) error {
					count := attempts.Add(1)
					if count < 3 {
						return errors.New("temporary failure")
					}
					return nil
				},
				RetryPolicy: &RetryPolicy{
					MaxRetries:     3,
					InitialBackoff: 10 * time.Millisecond,
					MaxBackoff:     100 * time.Millisecond,
					BackoffFactor:  2.0,
				},
			},
		},
	}

	err := orch.RegisterSaga(saga)
	require.NoError(t, err)

	ctx := context.Background()
	result, err := orch.Execute(ctx, "retry-saga", nil)

	require.NoError(t, err)
	assert.Equal(t, SagaStatusCompleted, result.Status)
	assert.Equal(t, int32(3), attempts.Load())
}

func TestOrchestratorCancel(t *testing.T) {
	store := NewInMemorySagaStore()
	logger := zap.NewNop()
	config := DefaultOrchestratorConfig()
	config.EnableEvents = false
	orch := NewOrchestrator(store, nil, logger, config)

	var compensated atomic.Bool

	saga := &SagaDefinition{
		ID:   "cancel-saga",
		Name: "Cancel Saga",
		Steps: []*Step{
			{
				ID:   "step1",
				Name: "Step 1",
				Execute: func(ctx context.Context, sagaCtx *SagaContext) error {
					return nil
				},
				Compensate: func(ctx context.Context, sagaCtx *SagaContext) error {
					compensated.Store(true)
					return nil
				},
			},
			{
				ID:   "step2",
				Name: "Step 2 - Long Running",
				Execute: func(ctx context.Context, sagaCtx *SagaContext) error {
					// Simulate long-running operation
					select {
					case <-ctx.Done():
						return ctx.Err()
					case <-time.After(10 * time.Second):
						return nil
					}
				},
			},
		},
	}

	err := orch.RegisterSaga(saga)
	require.NoError(t, err)

	// Start saga in background
	ctx, cancel := context.WithCancel(context.Background())
	resultCh := make(chan *SagaResult, 1)
	errCh := make(chan error, 1)

	go func() {
		result, err := orch.Execute(ctx, "cancel-saga", nil)
		resultCh <- result
		errCh <- err
	}()

	// Wait for step1 to complete, then cancel
	time.Sleep(100 * time.Millisecond)
	cancel()

	result := <-resultCh
	err = <-errCh

	require.NoError(t, err)
	// When cancelled, the saga can be in various terminal states depending on timing
	assert.True(t, result.Status.IsFinal() || result.Status == SagaStatusCompensating,
		"expected final status, got: %s", result.Status)
}

func TestOrchestratorResume(t *testing.T) {
	store := NewInMemorySagaStore()
	logger := zap.NewNop()
	config := DefaultOrchestratorConfig()
	config.EnableEvents = false
	orch := NewOrchestrator(store, nil, logger, config)

	var step2Called atomic.Bool

	saga := &SagaDefinition{
		ID:   "resume-saga",
		Name: "Resume Saga",
		Steps: []*Step{
			{
				ID:   "step1",
				Name: "Step 1",
				Execute: func(ctx context.Context, sagaCtx *SagaContext) error {
					return nil
				},
			},
			{
				ID:   "step2",
				Name: "Step 2",
				Execute: func(ctx context.Context, sagaCtx *SagaContext) error {
					step2Called.Store(true)
					return nil
				},
			},
		},
	}

	err := orch.RegisterSaga(saga)
	require.NoError(t, err)

	ctx := context.Background()

	// Create a paused state manually
	state := NewSagaState("resume-exec-1", "resume-saga", "corr-1")
	state.Status = SagaStatusRunning
	state.CurrentStep = 1
	state.CompletedSteps = []string{"step1"}
	err = store.SaveState(ctx, state)
	require.NoError(t, err)

	// Resume
	result, err := orch.Resume(ctx, "resume-exec-1")
	require.NoError(t, err)
	assert.Equal(t, SagaStatusCompleted, result.Status)
	assert.True(t, step2Called.Load())
}

func TestOrchestratorGetStatus(t *testing.T) {
	store := NewInMemorySagaStore()
	logger := zap.NewNop()
	config := DefaultOrchestratorConfig()
	config.EnableEvents = false
	orch := NewOrchestrator(store, nil, logger, config)

	saga := &SagaDefinition{
		ID:   "status-saga",
		Name: "Status Saga",
		Steps: []*Step{
			{
				ID:   "step1",
				Name: "Step 1",
				Execute: func(ctx context.Context, sagaCtx *SagaContext) error {
					return nil
				},
			},
		},
	}

	err := orch.RegisterSaga(saga)
	require.NoError(t, err)

	ctx := context.Background()
	result, err := orch.Execute(ctx, "status-saga", nil)
	require.NoError(t, err)

	// Get status
	state, err := orch.GetStatus(ctx, result.ExecutionID)
	require.NoError(t, err)
	assert.Equal(t, SagaStatusCompleted, state.Status)
	assert.Equal(t, "status-saga", state.SagaID)
}

func TestCompensationExecutor(t *testing.T) {
	logger := zap.NewNop()
	executor := NewCompensationExecutor(logger)

	var compensationOrder []string
	var orderMu sync.Mutex

	saga := &SagaDefinition{
		ID: "test",
		Steps: []*Step{
			{
				ID: "step1",
				Compensate: func(ctx context.Context, sagaCtx *SagaContext) error {
					orderMu.Lock()
					compensationOrder = append(compensationOrder, "step1")
					orderMu.Unlock()
					return nil
				},
			},
			{
				ID: "step2",
				Compensate: func(ctx context.Context, sagaCtx *SagaContext) error {
					orderMu.Lock()
					compensationOrder = append(compensationOrder, "step2")
					orderMu.Unlock()
					return nil
				},
			},
			{
				ID: "step3",
				Compensate: func(ctx context.Context, sagaCtx *SagaContext) error {
					orderMu.Lock()
					compensationOrder = append(compensationOrder, "step3")
					orderMu.Unlock()
					return nil
				},
			},
		},
	}

	state := NewSagaState("exec-1", "test", "corr-1")
	state.AddCompletedStep("step1", true)
	state.AddCompletedStep("step2", true)
	state.AddCompletedStep("step3", true)

	sagaCtx := state.ToContext()

	results := executor.Execute(context.Background(), saga, state, sagaCtx)

	assert.Len(t, results, 3)
	for _, r := range results {
		assert.True(t, r.Success)
	}

	// Verify LIFO order
	orderMu.Lock()
	assert.Equal(t, []string{"step3", "step2", "step1"}, compensationOrder)
	orderMu.Unlock()
}

func TestCompensationExecutorWithRetry(t *testing.T) {
	logger := zap.NewNop()
	executor := NewCompensationExecutor(logger)

	var attempts atomic.Int32

	saga := &SagaDefinition{
		ID: "test",
		Steps: []*Step{
			{
				ID: "retry-step",
				Compensate: func(ctx context.Context, sagaCtx *SagaContext) error {
					count := attempts.Add(1)
					if count < 3 {
						return errors.New("temporary failure")
					}
					return nil
				},
				CompensationRetryPolicy: &RetryPolicy{
					MaxRetries:     5,
					InitialBackoff: 10 * time.Millisecond,
					MaxBackoff:     50 * time.Millisecond,
					BackoffFactor:  2.0,
				},
			},
		},
	}

	state := NewSagaState("exec-1", "test", "corr-1")
	state.AddCompletedStep("retry-step", true)

	sagaCtx := state.ToContext()

	results := executor.Execute(context.Background(), saga, state, sagaCtx)

	assert.Len(t, results, 1)
	assert.True(t, results[0].Success)
	assert.Equal(t, int32(3), attempts.Load())
}

func TestCompensationExecutorPartialFailure(t *testing.T) {
	logger := zap.NewNop()
	executor := NewCompensationExecutor(logger)

	saga := &SagaDefinition{
		ID: "test",
		Steps: []*Step{
			{
				ID: "step1",
				Compensate: func(ctx context.Context, sagaCtx *SagaContext) error {
					return nil
				},
			},
			{
				ID: "step2",
				Compensate: func(ctx context.Context, sagaCtx *SagaContext) error {
					return errors.New("permanent failure")
				},
				CompensationRetryPolicy: &RetryPolicy{
					MaxRetries:     1,
					InitialBackoff: 1 * time.Millisecond,
					MaxBackoff:     1 * time.Millisecond,
					BackoffFactor:  1.0,
				},
			},
		},
	}

	state := NewSagaState("exec-1", "test", "corr-1")
	state.AddCompletedStep("step1", true)
	state.AddCompletedStep("step2", true)

	sagaCtx := state.ToContext()

	results := executor.Execute(context.Background(), saga, state, sagaCtx)

	assert.Len(t, results, 2)

	// step2 (LIFO order) should fail
	assert.False(t, results[0].Success)
	assert.Equal(t, "step2", results[0].StepID)

	// step1 should succeed
	assert.True(t, results[1].Success)
	assert.Equal(t, "step1", results[1].StepID)
}

func TestSagaStateSerialization(t *testing.T) {
	state := NewSagaState("exec-1", "saga-1", "corr-1")
	state.Status = SagaStatusRunning
	state.CurrentStep = 2
	state.Variables["key1"] = "value1"
	state.Variables["key2"] = 42
	state.AddCompletedStep("step1", true)
	state.AddCompletedStep("step2", true)

	// Serialize
	data, err := state.ToJSON()
	require.NoError(t, err)

	// Deserialize
	restored, err := SagaStateFromJSON(data)
	require.NoError(t, err)

	assert.Equal(t, state.ExecutionID, restored.ExecutionID)
	assert.Equal(t, state.SagaID, restored.SagaID)
	assert.Equal(t, state.Status, restored.Status)
	assert.Equal(t, state.CurrentStep, restored.CurrentStep)
	assert.Equal(t, state.CompletedSteps, restored.CompletedSteps)
	assert.Equal(t, state.CompensationStack, restored.CompensationStack)
	assert.Equal(t, "value1", restored.Variables["key1"])
}

func TestSagaStatusIsFinal(t *testing.T) {
	assert.False(t, SagaStatusPending.IsFinal())
	assert.False(t, SagaStatusRunning.IsFinal())
	assert.False(t, SagaStatusCompensating.IsFinal())
	assert.True(t, SagaStatusCompleted.IsFinal())
	assert.True(t, SagaStatusFailed.IsFinal())
	assert.True(t, SagaStatusCompensated.IsFinal())
	assert.True(t, SagaStatusPartiallyCompensated.IsFinal())
}

