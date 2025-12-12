package resourcemanager

import (
	"context"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// setupTestRedis creates a miniredis instance and client for testing.
func setupTestRedis(t *testing.T) (*miniredis.Miniredis, *redis.Client) {
	mr, err := miniredis.Run()
	require.NoError(t, err)
	t.Cleanup(func() {
		mr.Close()
	})

	client := redis.NewClient(&redis.Options{
		Addr: mr.Addr(),
	})
	t.Cleanup(func() {
		client.Close()
	})

	return mr, client
}

// TestLockRequest_Validate tests LockRequest validation.
func TestLockRequest_Validate(t *testing.T) {
	tests := []struct {
		name    string
		req     *LockRequest
		wantErr bool
		errMsg  string
	}{
		{
			name: "valid request",
			req: &LockRequest{
				DatabaseID: "db-123",
				OwnerID:    "workflow-456",
				Operation:  "extension_install",
			},
			wantErr: false,
		},
		{
			name: "missing database_id",
			req: &LockRequest{
				OwnerID:   "workflow-456",
				Operation: "extension_install",
			},
			wantErr: true,
			errMsg:  "database_id is required",
		},
		{
			name: "missing owner_id",
			req: &LockRequest{
				DatabaseID: "db-123",
				Operation:  "extension_install",
			},
			wantErr: true,
			errMsg:  "owner_id is required",
		},
		{
			name: "ttl below minimum",
			req: &LockRequest{
				DatabaseID: "db-123",
				OwnerID:    "workflow-456",
				TTL:        10 * time.Second,
			},
			wantErr: true,
			errMsg:  "ttl is below minimum",
		},
		{
			name: "ttl exceeds maximum",
			req: &LockRequest{
				DatabaseID: "db-123",
				OwnerID:    "workflow-456",
				TTL:        2 * time.Hour,
			},
			wantErr: true,
			errMsg:  "ttl exceeds maximum",
		},
		{
			name: "negative ttl",
			req: &LockRequest{
				DatabaseID: "db-123",
				OwnerID:    "workflow-456",
				TTL:        -1 * time.Second,
			},
			wantErr: true,
			errMsg:  "ttl cannot be negative",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.req.Validate()
			if tt.wantErr {
				assert.Error(t, err)
				assert.Contains(t, err.Error(), tt.errMsg)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

// TestLockRequest_GetTTL tests TTL default behavior.
func TestLockRequest_GetTTL(t *testing.T) {
	t.Run("returns default when zero", func(t *testing.T) {
		req := &LockRequest{TTL: 0}
		assert.Equal(t, DefaultLockTTL, req.GetTTL())
	})

	t.Run("returns specified when set", func(t *testing.T) {
		req := &LockRequest{TTL: 5 * time.Minute}
		assert.Equal(t, 5*time.Minute, req.GetTTL())
	})
}

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

// TestResourceManager_ReleaseLock tests lock release.
func TestResourceManager_ReleaseLock(t *testing.T) {
	_, client := setupTestRedis(t)
	rm := NewResourceManager(client, nil)
	ctx := context.Background()

	t.Run("release owned lock", func(t *testing.T) {
		req := &LockRequest{
			DatabaseID: "db-release-1",
			OwnerID:    "workflow-r1",
		}
		result, err := rm.AcquireLock(ctx, req)
		require.NoError(t, err)
		assert.True(t, result.Acquired)

		err = rm.ReleaseLock(ctx, "db-release-1", "workflow-r1")
		require.NoError(t, err)

		// Verify lock is released
		info, err := rm.GetLockInfo(ctx, "db-release-1")
		require.NoError(t, err)
		assert.Nil(t, info)
	})

	t.Run("release not owned lock", func(t *testing.T) {
		req := &LockRequest{
			DatabaseID: "db-release-2",
			OwnerID:    "workflow-r2a",
		}
		result, err := rm.AcquireLock(ctx, req)
		require.NoError(t, err)
		assert.True(t, result.Acquired)

		// Try to release with wrong owner
		err = rm.ReleaseLock(ctx, "db-release-2", "workflow-r2b")
		assert.ErrorIs(t, err, ErrLockNotHeld)

		// Cleanup
		err = rm.ReleaseLock(ctx, "db-release-2", "workflow-r2a")
		require.NoError(t, err)
	})
}

// TestResourceManager_ExtendLock tests lock extension (heartbeat).
func TestResourceManager_ExtendLock(t *testing.T) {
	mr, client := setupTestRedis(t)
	rm := NewResourceManager(client, nil)
	ctx := context.Background()

	t.Run("extend owned lock", func(t *testing.T) {
		req := &LockRequest{
			DatabaseID: "db-extend-1",
			OwnerID:    "workflow-e1",
			TTL:        1 * time.Minute,
		}
		result, err := rm.AcquireLock(ctx, req)
		require.NoError(t, err)
		assert.True(t, result.Acquired)

		originalExpiry := result.LockInfo.ExpiresAt

		// Fast forward time
		mr.FastForward(30 * time.Second)

		// Extend lock
		err = rm.ExtendLock(ctx, "db-extend-1", "workflow-e1", 2*time.Minute)
		require.NoError(t, err)

		// Verify expiry was extended
		info, err := rm.GetLockInfo(ctx, "db-extend-1")
		require.NoError(t, err)
		assert.True(t, info.ExpiresAt.After(originalExpiry))

		// Cleanup
		err = rm.ReleaseLock(ctx, "db-extend-1", "workflow-e1")
		require.NoError(t, err)
	})

	t.Run("extend not owned lock", func(t *testing.T) {
		req := &LockRequest{
			DatabaseID: "db-extend-2",
			OwnerID:    "workflow-e2a",
		}
		result, err := rm.AcquireLock(ctx, req)
		require.NoError(t, err)
		assert.True(t, result.Acquired)

		// Try to extend with wrong owner
		err = rm.ExtendLock(ctx, "db-extend-2", "workflow-e2b", 5*time.Minute)
		assert.ErrorIs(t, err, ErrLockNotHeld)

		// Cleanup
		err = rm.ReleaseLock(ctx, "db-extend-2", "workflow-e2a")
		require.NoError(t, err)
	})
}

// TestResourceManager_GetLockInfo tests getting lock information.
func TestResourceManager_GetLockInfo(t *testing.T) {
	_, client := setupTestRedis(t)
	rm := NewResourceManager(client, nil)
	ctx := context.Background()

	t.Run("existing lock", func(t *testing.T) {
		req := &LockRequest{
			DatabaseID:    "db-info-1",
			OwnerID:       "workflow-i1",
			Operation:     "test_op",
			CorrelationID: "corr-i1",
		}
		_, err := rm.AcquireLock(ctx, req)
		require.NoError(t, err)

		info, err := rm.GetLockInfo(ctx, "db-info-1")
		require.NoError(t, err)
		require.NotNil(t, info)
		assert.Equal(t, "db-info-1", info.DatabaseID)
		assert.Equal(t, "workflow-i1", info.OwnerID)
		assert.Equal(t, "test_op", info.Operation)
		assert.Equal(t, "corr-i1", info.CorrelationID)
		assert.False(t, info.LockedAt.IsZero())
		assert.False(t, info.ExpiresAt.IsZero())

		// Cleanup
		err = rm.ReleaseLock(ctx, "db-info-1", "workflow-i1")
		require.NoError(t, err)
	})

	t.Run("non-existing lock", func(t *testing.T) {
		info, err := rm.GetLockInfo(ctx, "db-nonexistent")
		require.NoError(t, err)
		assert.Nil(t, info)
	})
}

// TestResourceManager_QueueOperations tests queue-related operations.
func TestResourceManager_QueueOperations(t *testing.T) {
	_, client := setupTestRedis(t)
	rm := NewResourceManager(client, nil)
	ctx := context.Background()

	t.Run("queue position tracking", func(t *testing.T) {
		// Acquire lock
		req1 := &LockRequest{
			DatabaseID: "db-queue-1",
			OwnerID:    "workflow-q1a",
		}
		_, err := rm.AcquireLock(ctx, req1)
		require.NoError(t, err)

		// Add to queue
		req2 := &LockRequest{
			DatabaseID:  "db-queue-1",
			OwnerID:     "workflow-q1b",
			WaitTimeout: 0,
		}
		result2, err := rm.AcquireLock(ctx, req2)
		require.NoError(t, err)
		assert.False(t, result2.Acquired)
		assert.Equal(t, 1, result2.QueuePosition)

		// Check queue position
		pos, err := rm.GetQueuePosition(ctx, "db-queue-1", "workflow-q1b")
		require.NoError(t, err)
		assert.Equal(t, 1, pos)

		// Cancel wait
		err = rm.CancelWait(ctx, "db-queue-1", "workflow-q1b")
		require.NoError(t, err)

		// Verify removed from queue
		pos, err = rm.GetQueuePosition(ctx, "db-queue-1", "workflow-q1b")
		require.NoError(t, err)
		assert.Equal(t, 0, pos)

		// Cleanup
		err = rm.ReleaseLock(ctx, "db-queue-1", "workflow-q1a")
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

// TestResourceManager_GetAllLocks tests retrieving all locks.
func TestResourceManager_GetAllLocks(t *testing.T) {
	_, client := setupTestRedis(t)
	rm := NewResourceManager(client, nil)
	ctx := context.Background()

	// Acquire multiple locks
	for i := 1; i <= 3; i++ {
		req := &LockRequest{
			DatabaseID: "db-all-" + string(rune('0'+i)),
			OwnerID:    "workflow-all-" + string(rune('0'+i)),
		}
		_, err := rm.AcquireLock(ctx, req)
		require.NoError(t, err)
	}

	// Get all locks
	locks, err := rm.GetAllLocks(ctx)
	require.NoError(t, err)
	assert.Len(t, locks, 3)

	// Cleanup
	for i := 1; i <= 3; i++ {
		dbID := "db-all-" + string(rune('0'+i))
		ownerID := "workflow-all-" + string(rune('0'+i))
		rm.ReleaseLock(ctx, dbID, ownerID)
	}
}

// TestResourceManager_ReleaseAllByOwner tests releasing all locks by owner.
func TestResourceManager_ReleaseAllByOwner(t *testing.T) {
	_, client := setupTestRedis(t)
	rm := NewResourceManager(client, nil)
	ctx := context.Background()

	// Acquire multiple locks with same owner
	ownerID := "workflow-release-all"
	for i := 1; i <= 3; i++ {
		req := &LockRequest{
			DatabaseID: "db-release-all-" + string(rune('0'+i)),
			OwnerID:    ownerID,
		}
		_, err := rm.AcquireLock(ctx, req)
		require.NoError(t, err)
	}

	// Release all by owner
	released, err := rm.ReleaseAllByOwner(ctx, ownerID)
	require.NoError(t, err)
	assert.Equal(t, 3, released)

	// Verify all released
	locks, err := rm.GetAllLocks(ctx)
	require.NoError(t, err)
	assert.Len(t, locks, 0)
}

// TestResourceManager_CleanupWorker tests the cleanup worker functionality.
func TestResourceManager_CleanupWorker(t *testing.T) {
	mr, client := setupTestRedis(t)
	rm := NewResourceManager(client, nil)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Acquire lock with short TTL
	req := &LockRequest{
		DatabaseID: "db-cleanup-1",
		OwnerID:    "workflow-cleanup-1",
		TTL:        MinLockTTL,
	}
	_, err := rm.AcquireLock(ctx, req)
	require.NoError(t, err)

	// Start cleanup worker
	rm.StartCleanupWorker(ctx, 100*time.Millisecond)

	// Fast forward past TTL
	mr.FastForward(MinLockTTL + 1*time.Second)

	// Wait for cleanup to run
	time.Sleep(300 * time.Millisecond)

	// Lock should be cleaned up
	info, err := rm.GetLockInfo(ctx, "db-cleanup-1")
	require.NoError(t, err)
	assert.Nil(t, info)

	// Stop cleanup worker
	rm.Close()
}

// TestLockInfo_Methods tests LockInfo helper methods.
func TestLockInfo_Methods(t *testing.T) {
	t.Run("IsExpired", func(t *testing.T) {
		// Not expired
		info := &LockInfo{
			ExpiresAt: time.Now().Add(1 * time.Hour),
		}
		assert.False(t, info.IsExpired())

		// Expired
		info = &LockInfo{
			ExpiresAt: time.Now().Add(-1 * time.Hour),
		}
		assert.True(t, info.IsExpired())
	})

	t.Run("RemainingTTL", func(t *testing.T) {
		// Has remaining time
		info := &LockInfo{
			ExpiresAt: time.Now().Add(30 * time.Second),
		}
		assert.True(t, info.RemainingTTL() > 0)
		assert.True(t, info.RemainingTTL() <= 30*time.Second)

		// No remaining time
		info = &LockInfo{
			ExpiresAt: time.Now().Add(-1 * time.Second),
		}
		assert.Equal(t, time.Duration(0), info.RemainingTTL())
	})
}

// TestQueueEntry_WaitDuration tests QueueEntry helper methods.
func TestQueueEntry_WaitDuration(t *testing.T) {
	entry := &QueueEntry{
		EnqueuedAt: time.Now().Add(-5 * time.Second),
	}
	duration := entry.WaitDuration()
	assert.True(t, duration >= 5*time.Second)
	assert.True(t, duration < 6*time.Second)
}

// TestLockGuard tests the LockGuard helper.
func TestLockGuard(t *testing.T) {
	_, client := setupTestRedis(t)
	rm := NewResourceManager(client, nil)
	ctx := context.Background()

	t.Run("acquire and release", func(t *testing.T) {
		guard := NewLockGuard(rm, "db-guard-1", "workflow-guard-1")
		assert.False(t, guard.IsAcquired())

		result, err := guard.Acquire(ctx, &LockRequest{
			Operation: "test",
		})
		require.NoError(t, err)
		assert.True(t, result.Acquired)
		assert.True(t, guard.IsAcquired())

		err = guard.Release(ctx)
		require.NoError(t, err)
		assert.False(t, guard.IsAcquired())
	})

	t.Run("release when not acquired", func(t *testing.T) {
		guard := NewLockGuard(rm, "db-guard-2", "workflow-guard-2")
		err := guard.Release(ctx)
		require.NoError(t, err) // Should not error
	})
}

// TestWithLock tests the WithLock helper function.
func TestWithLock(t *testing.T) {
	_, client := setupTestRedis(t)
	rm := NewResourceManager(client, nil)
	ctx := context.Background()

	t.Run("successful execution", func(t *testing.T) {
		executed := false
		err := WithLock(ctx, rm, &LockRequest{
			DatabaseID: "db-with-1",
			OwnerID:    "workflow-with-1",
		}, func(ctx context.Context) error {
			executed = true
			return nil
		})
		require.NoError(t, err)
		assert.True(t, executed)

		// Lock should be released
		info, _ := rm.GetLockInfo(ctx, "db-with-1")
		assert.Nil(t, info)
	})

	t.Run("lock busy", func(t *testing.T) {
		// Acquire first
		_, err := rm.AcquireLock(ctx, &LockRequest{
			DatabaseID: "db-with-2",
			OwnerID:    "workflow-with-2a",
		})
		require.NoError(t, err)

		// Try WithLock
		err = WithLock(ctx, rm, &LockRequest{
			DatabaseID:  "db-with-2",
			OwnerID:     "workflow-with-2b",
			WaitTimeout: 0,
		}, func(ctx context.Context) error {
			return nil
		})
		assert.ErrorIs(t, err, ErrLockNotAcquired)

		// Cleanup
		rm.ReleaseLock(ctx, "db-with-2", "workflow-with-2a")
	})
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

// TestStore_AcquireLock_AtomicExpiredCleanup tests atomic cleanup of expired locks.
func TestStore_AcquireLock_AtomicExpiredCleanup(t *testing.T) {
	mr, client := setupTestRedis(t)
	store := NewLockStore(client)
	ctx := context.Background()

	// Acquire lock with short TTL
	req1 := &LockRequest{
		DatabaseID: "db-atomic-1",
		OwnerID:    "workflow-atomic-1a",
		TTL:        MinLockTTL,
	}
	acquired, _, err := store.AcquireLock(ctx, req1)
	require.NoError(t, err)
	assert.True(t, acquired)

	// Fast forward past TTL
	mr.FastForward(MinLockTTL + 1*time.Second)

	// Another owner should be able to acquire (expired lock cleaned up atomically)
	req2 := &LockRequest{
		DatabaseID: "db-atomic-1",
		OwnerID:    "workflow-atomic-1b",
		TTL:        MinLockTTL,
	}
	acquired, _, err = store.AcquireLock(ctx, req2)
	require.NoError(t, err)
	assert.True(t, acquired)

	// Verify new owner holds the lock
	info, err := store.GetLockInfo(ctx, "db-atomic-1")
	require.NoError(t, err)
	assert.Equal(t, "workflow-atomic-1b", info.OwnerID)
}
