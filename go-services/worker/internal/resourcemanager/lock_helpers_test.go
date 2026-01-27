package resourcemanager

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

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
