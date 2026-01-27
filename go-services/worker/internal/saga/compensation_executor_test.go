package saga

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"go.uber.org/zap"
)

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
