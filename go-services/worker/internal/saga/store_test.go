package saga

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

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
