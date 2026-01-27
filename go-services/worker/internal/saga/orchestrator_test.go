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
