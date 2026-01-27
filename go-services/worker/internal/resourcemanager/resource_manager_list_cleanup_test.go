package resourcemanager

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

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
