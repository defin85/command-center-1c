package resourcemanager

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

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
