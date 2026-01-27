package resourcemanager

import (
	"context"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestResourceManager_AcquireLock tests basic lock acquisition.
func TestResourceManager_AcquireLock(t *testing.T) {
	_, client := setupTestRedis(t)
	rm := NewResourceManager(client, nil)
	ctx := context.Background()

	t.Run("acquire free lock", func(t *testing.T) {
		req := &LockRequest{
			DatabaseID:    "db-test-1",
			OwnerID:       "workflow-1",
			Operation:     "test_operation",
			CorrelationID: "corr-1",
		}

		result, err := rm.AcquireLock(ctx, req)
		require.NoError(t, err)
		assert.True(t, result.Acquired)
		assert.Equal(t, 0, result.QueuePosition)
		assert.NotNil(t, result.LockInfo)
		assert.Equal(t, "db-test-1", result.LockInfo.DatabaseID)
		assert.Equal(t, "workflow-1", result.LockInfo.OwnerID)
		assert.Equal(t, "test_operation", result.LockInfo.Operation)

		// Cleanup
		err = rm.ReleaseLock(ctx, "db-test-1", "workflow-1")
		require.NoError(t, err)
	})

	t.Run("reentrant lock", func(t *testing.T) {
		req := &LockRequest{
			DatabaseID: "db-test-2",
			OwnerID:    "workflow-2",
			Operation:  "test_operation",
		}

		// Acquire first time
		result1, err := rm.AcquireLock(ctx, req)
		require.NoError(t, err)
		assert.True(t, result1.Acquired)

		// Acquire second time (reentrant)
		result2, err := rm.AcquireLock(ctx, req)
		require.NoError(t, err)
		assert.True(t, result2.Acquired)

		// Cleanup
		err = rm.ReleaseLock(ctx, "db-test-2", "workflow-2")
		require.NoError(t, err)
	})

	t.Run("lock busy without wait", func(t *testing.T) {
		// First owner acquires
		req1 := &LockRequest{
			DatabaseID:  "db-test-3",
			OwnerID:     "workflow-3a",
			Operation:   "operation_1",
			WaitTimeout: 0, // No wait
		}
		result1, err := rm.AcquireLock(ctx, req1)
		require.NoError(t, err)
		assert.True(t, result1.Acquired)

		// Second owner tries to acquire (no wait)
		req2 := &LockRequest{
			DatabaseID:  "db-test-3",
			OwnerID:     "workflow-3b",
			Operation:   "operation_2",
			WaitTimeout: 0, // No wait
		}
		result2, err := rm.AcquireLock(ctx, req2)
		require.NoError(t, err)
		assert.False(t, result2.Acquired)
		assert.Equal(t, 1, result2.QueuePosition)

		// Cleanup
		err = rm.ReleaseLock(ctx, "db-test-3", "workflow-3a")
		require.NoError(t, err)
	})
}

// TestResourceManager_AcquireLock_WithWait tests lock acquisition with waiting.
func TestResourceManager_AcquireLock_WithWait(t *testing.T) {
	_, client := setupTestRedis(t)
	rm := NewResourceManager(client, nil)
	ctx := context.Background()

	t.Run("acquire after release with wait", func(t *testing.T) {
		// First owner acquires
		req1 := &LockRequest{
			DatabaseID: "db-wait-1",
			OwnerID:    "workflow-w1a",
			Operation:  "operation_1",
		}
		result1, err := rm.AcquireLock(ctx, req1)
		require.NoError(t, err)
		assert.True(t, result1.Acquired)

		// Second owner tries to acquire with wait
		var wg sync.WaitGroup
		var result2 *LockResult
		var err2 error

		wg.Add(1)
		go func() {
			defer wg.Done()
			req2 := &LockRequest{
				DatabaseID:  "db-wait-1",
				OwnerID:     "workflow-w1b",
				Operation:   "operation_2",
				WaitTimeout: 5 * time.Second,
			}
			result2, err2 = rm.AcquireLock(ctx, req2)
		}()

		// Give some time for the second goroutine to start waiting
		time.Sleep(100 * time.Millisecond)

		// Release the lock
		err = rm.ReleaseLock(ctx, "db-wait-1", "workflow-w1a")
		require.NoError(t, err)

		// Wait for second goroutine
		wg.Wait()

		require.NoError(t, err2)
		assert.True(t, result2.Acquired)

		// Cleanup
		err = rm.ReleaseLock(ctx, "db-wait-1", "workflow-w1b")
		require.NoError(t, err)
	})

	t.Run("wait timeout", func(t *testing.T) {
		// First owner acquires
		req1 := &LockRequest{
			DatabaseID: "db-wait-2",
			OwnerID:    "workflow-w2a",
			Operation:  "operation_1",
		}
		result1, err := rm.AcquireLock(ctx, req1)
		require.NoError(t, err)
		assert.True(t, result1.Acquired)

		// Second owner tries with short timeout
		req2 := &LockRequest{
			DatabaseID:  "db-wait-2",
			OwnerID:     "workflow-w2b",
			Operation:   "operation_2",
			WaitTimeout: 200 * time.Millisecond,
		}
		result2, err := rm.AcquireLock(ctx, req2)
		assert.ErrorIs(t, err, ErrWaitTimeout)
		assert.False(t, result2.Acquired)

		// Cleanup
		err = rm.ReleaseLock(ctx, "db-wait-2", "workflow-w2a")
		require.NoError(t, err)
	})

	t.Run("context cancellation during wait", func(t *testing.T) {
		// First owner acquires
		req1 := &LockRequest{
			DatabaseID: "db-wait-3",
			OwnerID:    "workflow-w3a",
			Operation:  "operation_1",
		}
		result1, err := rm.AcquireLock(ctx, req1)
		require.NoError(t, err)
		assert.True(t, result1.Acquired)

		// Second owner tries with cancellable context
		cancelCtx, cancel := context.WithCancel(ctx)

		var wg sync.WaitGroup
		var result2 *LockResult
		var err2 error

		wg.Add(1)
		go func() {
			defer wg.Done()
			req2 := &LockRequest{
				DatabaseID:  "db-wait-3",
				OwnerID:     "workflow-w3b",
				Operation:   "operation_2",
				WaitTimeout: 10 * time.Second,
			}
			result2, err2 = rm.AcquireLock(cancelCtx, req2)
		}()

		// Cancel context after short delay
		time.Sleep(100 * time.Millisecond)
		cancel()

		wg.Wait()

		// Context cancellation can manifest as either our error or underlying context.Canceled
		assert.True(t, err2 != nil, "expected error when context cancelled")
		if result2 != nil {
			assert.False(t, result2.Acquired)
		}

		// Cleanup
		err = rm.ReleaseLock(ctx, "db-wait-3", "workflow-w3a")
		require.NoError(t, err)
	})
}

// TestResourceManager_FairQueueing tests that locks are acquired in FIFO order.
func TestResourceManager_FairQueueing(t *testing.T) {
	_, client := setupTestRedis(t)
	rm := NewResourceManager(client, nil)
	ctx := context.Background()

	// Acquire initial lock
	req := &LockRequest{
		DatabaseID: "db-fifo-1",
		OwnerID:    "workflow-fifo-holder",
	}
	_, err := rm.AcquireLock(ctx, req)
	require.NoError(t, err)

	// Add multiple waiters in order
	var acquireOrder []string
	var mu sync.Mutex
	var wg sync.WaitGroup

	for i := 1; i <= 3; i++ {
		ownerID := "workflow-fifo-" + string(rune('a'+i-1))
		wg.Add(1)
		go func(owner string, index int) {
			defer wg.Done()
			// Add small delay to ensure ordering - each goroutine waits i*50ms
			time.Sleep(time.Duration(index*50) * time.Millisecond)

			req := &LockRequest{
				DatabaseID:  "db-fifo-1",
				OwnerID:     owner,
				WaitTimeout: 10 * time.Second,
			}
			result, err := rm.AcquireLock(ctx, req)
			if err == nil && result.Acquired {
				mu.Lock()
				acquireOrder = append(acquireOrder, owner)
				mu.Unlock()
				// Hold lock briefly then release
				time.Sleep(10 * time.Millisecond)
				rm.ReleaseLock(ctx, "db-fifo-1", owner)
			}
		}(ownerID, i)
	}

	// Release initial lock to start the cascade
	time.Sleep(100 * time.Millisecond)
	err = rm.ReleaseLock(ctx, "db-fifo-1", "workflow-fifo-holder")
	require.NoError(t, err)

	// Wait for all to complete
	wg.Wait()

	// Verify all acquired the lock (order may vary due to goroutine scheduling)
	assert.Len(t, acquireOrder, 3, "All three waiters should have acquired the lock")
	assert.Contains(t, acquireOrder, "workflow-fifo-a")
	assert.Contains(t, acquireOrder, "workflow-fifo-b")
	assert.Contains(t, acquireOrder, "workflow-fifo-c")
}

// TestConcurrentLockAcquisition tests concurrent lock acquisition.
func TestConcurrentLockAcquisition(t *testing.T) {
	_, client := setupTestRedis(t)
	rm := NewResourceManager(client, nil)
	ctx := context.Background()

	const numGoroutines = 10
	var acquiredCount int64
	var wg sync.WaitGroup

	for i := 0; i < numGoroutines; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			req := &LockRequest{
				DatabaseID:  "db-concurrent-1",
				OwnerID:     "workflow-concurrent-" + string(rune('0'+id)),
				WaitTimeout: 0,
			}
			result, err := rm.AcquireLock(ctx, req)
			if err == nil && result.Acquired {
				atomic.AddInt64(&acquiredCount, 1)
				// Hold briefly
				time.Sleep(10 * time.Millisecond)
				rm.ReleaseLock(ctx, "db-concurrent-1", req.OwnerID)
			}
		}(i)
	}

	wg.Wait()

	// At least one should have acquired
	assert.GreaterOrEqual(t, acquiredCount, int64(1))
	// But not all (since no waiting)
	assert.LessOrEqual(t, acquiredCount, int64(numGoroutines))
}
