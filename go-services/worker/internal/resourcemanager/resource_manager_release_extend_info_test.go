package resourcemanager

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

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
