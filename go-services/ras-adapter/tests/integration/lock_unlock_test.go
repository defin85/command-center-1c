// +build integration

package integration

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"
)

// TestLockUnlockIntegration tests basic lock/unlock operations against real RAS server
func TestLockUnlockIntegration(t *testing.T) {
	rasPool, redisClient, logger := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(t, rasPool)
	infobaseID := GetTestInfobaseID(t, rasPool)

	infobaseSvc := createInfobaseService(t, rasPool)

	ctx := context.Background()

	// Test Lock
	t.Run("lock_infobase", func(t *testing.T) {
		err := infobaseSvc.LockInfobase(ctx, clusterID, infobaseID)
		require.NoError(t, err, "Lock operation should succeed")

		// Verify lock state
		client, err := rasPool.GetConnection(ctx)
		require.NoError(t, err)
		defer rasPool.ReleaseConnection(client)

		infobase, err := client.GetInfobaseInfo(ctx, clusterID, infobaseID)
		require.NoError(t, err, "Failed to get infobase info after lock")
		require.NotNil(t, infobase)

		// ScheduledJobsDeny should be true after lock
		assert.True(t, infobase.ScheduledJobsDeny,
			"ScheduledJobsDeny should be true after lock operation")

		t.Logf("Infobase locked successfully: %s", infobaseID)
	})

	// Test Unlock
	t.Run("unlock_infobase", func(t *testing.T) {
		err := infobaseSvc.UnlockInfobase(ctx, clusterID, infobaseID)
		require.NoError(t, err, "Unlock operation should succeed")

		// Verify unlock state
		client, err := rasPool.GetConnection(ctx)
		require.NoError(t, err)
		defer rasPool.ReleaseConnection(client)

		infobase, err := client.GetInfobaseInfo(ctx, clusterID, infobaseID)
		require.NoError(t, err, "Failed to get infobase info after unlock")
		require.NotNil(t, infobase)

		// ScheduledJobsDeny should be false after unlock
		assert.False(t, infobase.ScheduledJobsDeny,
			"ScheduledJobsDeny should be false after unlock operation")

		t.Logf("Infobase unlocked successfully: %s", infobaseID)
	})

	// Test Lock-Unlock cycle
	t.Run("lock_unlock_cycle", func(t *testing.T) {
		for i := 0; i < 3; i++ {
			// Lock
			err := infobaseSvc.LockInfobase(ctx, clusterID, infobaseID)
			require.NoError(t, err, "Lock cycle %d: lock should succeed", i+1)

			// Small delay
			time.Sleep(100 * time.Millisecond)

			// Unlock
			err = infobaseSvc.UnlockInfobase(ctx, clusterID, infobaseID)
			require.NoError(t, err, "Lock cycle %d: unlock should succeed", i+1)
		}

		t.Logf("Lock-Unlock cycle completed: 3 cycles executed successfully")
	})

	// Cleanup: ensure infobase is unlocked after tests
	t.Run("cleanup_unlock", func(t *testing.T) {
		err := infobaseSvc.UnlockInfobase(ctx, clusterID, infobaseID)
		if err != nil {
			t.Logf("Warning: cleanup unlock failed: %v", err)
		}
	})
}

// TestConcurrentLockOperations tests concurrent lock operations on same infobase
func TestConcurrentLockOperations(t *testing.T) {
	rasPool, redisClient, logger := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(t, rasPool)
	infobaseID := GetTestInfobaseID(t, rasPool)

	infobaseSvc := createInfobaseService(t, rasPool)

	const numOps = 10
	errors := make(chan error, numOps)
	var wg sync.WaitGroup

	t.Run("concurrent_locks_same_infobase", func(t *testing.T) {
		// Launch 10 concurrent lock operations
		for i := 0; i < numOps; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()

				ctx := context.Background()
				err := infobaseSvc.LockInfobase(ctx, clusterID, infobaseID)
				errors <- err

				if err != nil {
					t.Logf("Lock %d: error=%v", idx, err)
				}
			}(i)
		}

		// Wait for all operations to complete
		wg.Wait()
		close(errors)

		// Collect and analyze results
		successCount := 0
		var errorList []error

		for err := range errors {
			if err == nil {
				successCount++
			} else {
				errorList = append(errorList, err)
			}
		}

		// At least 1 should succeed (lock is idempotent operation)
		assert.GreaterOrEqual(t, successCount, 1,
			"At least 1 concurrent lock should succeed (operation is idempotent)")

		t.Logf("Concurrent locks: %d succeeded, %d errors", successCount, len(errorList))
	})

	// Cleanup
	ctx := context.Background()
	err := infobaseSvc.UnlockInfobase(ctx, clusterID, infobaseID)
	require.NoError(t, err, "Cleanup unlock should succeed")
}

// TestConcurrentUnlockOperations tests concurrent unlock operations on same infobase
func TestConcurrentUnlockOperations(t *testing.T) {
	rasPool, redisClient, logger := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(t, rasPool)
	infobaseID := GetTestInfobaseID(t, rasPool)

	infobaseSvc := createInfobaseService(t, rasPool)
	ctx := context.Background()

	// First lock the infobase
	err := infobaseSvc.LockInfobase(ctx, clusterID, infobaseID)
	require.NoError(t, err, "Initial lock should succeed")

	const numOps = 10
	errors := make(chan error, numOps)
	var wg sync.WaitGroup

	t.Run("concurrent_unlocks_same_infobase", func(t *testing.T) {
		// Launch 10 concurrent unlock operations
		for i := 0; i < numOps; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()

				ctx := context.Background()
				err := infobaseSvc.UnlockInfobase(ctx, clusterID, infobaseID)
				errors <- err

				if err != nil {
					t.Logf("Unlock %d: error=%v", idx, err)
				}
			}(i)
		}

		wg.Wait()
		close(errors)

		// Collect results
		successCount := 0
		var errorList []error

		for err := range errors {
			if err == nil {
				successCount++
			} else {
				errorList = append(errorList, err)
			}
		}

		assert.GreaterOrEqual(t, successCount, 1,
			"At least 1 concurrent unlock should succeed")

		t.Logf("Concurrent unlocks: %d succeeded, %d errors", successCount, len(errorList))
	})
}

// TestLockWithTimeout tests lock operation with timeout
func TestLockWithTimeout(t *testing.T) {
	rasPool, redisClient, logger := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(t, rasPool)
	infobaseID := GetTestInfobaseID(t, rasPool)

	infobaseSvc := createInfobaseService(t, rasPool)

	t.Run("lock_with_timeout", func(t *testing.T) {
		// Create context with 5 second timeout
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		// Lock should complete before timeout
		done := make(chan error, 1)
		go func() {
			done <- infobaseSvc.LockInfobase(ctx, clusterID, infobaseID)
		}()

		select {
		case err := <-done:
			require.NoError(t, err, "Lock should complete within timeout")
		case <-time.After(6 * time.Second):
			t.Fatal("Lock operation exceeded timeout (5 seconds)")
		}

		t.Log("Lock operation completed within timeout")
	})

	// Cleanup
	ctx := context.Background()
	err := infobaseSvc.UnlockInfobase(ctx, clusterID, infobaseID)
	require.NoError(t, err)
}

// TestLockIdempotency tests that lock is idempotent
func TestLockIdempotency(t *testing.T) {
	rasPool, redisClient, logger := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(t, rasPool)
	infobaseID := GetTestInfobaseID(t, rasPool)

	infobaseSvc := createInfobaseService(t, rasPool)
	ctx := context.Background()

	t.Run("lock_idempotency", func(t *testing.T) {
		// Lock once
		err1 := infobaseSvc.LockInfobase(ctx, clusterID, infobaseID)
		require.NoError(t, err1, "First lock should succeed")

		// Lock again (idempotent)
		err2 := infobaseSvc.LockInfobase(ctx, clusterID, infobaseID)
		require.NoError(t, err2, "Second lock (idempotent) should succeed")

		// Lock third time
		err3 := infobaseSvc.LockInfobase(ctx, clusterID, infobaseID)
		require.NoError(t, err3, "Third lock (idempotent) should succeed")

		t.Log("Lock operation is idempotent (can be called multiple times safely)")
	})

	// Cleanup
	err := infobaseSvc.UnlockInfobase(ctx, clusterID, infobaseID)
	require.NoError(t, err)
}

// TestUnlockIdempotency tests that unlock is idempotent
func TestUnlockIdempotency(t *testing.T) {
	rasPool, redisClient, logger := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(t, rasPool)
	infobaseID := GetTestInfobaseID(t, rasPool)

	infobaseSvc := createInfobaseService(t, rasPool)
	ctx := context.Background()

	// First lock
	err := infobaseSvc.LockInfobase(ctx, clusterID, infobaseID)
	require.NoError(t, err)

	t.Run("unlock_idempotency", func(t *testing.T) {
		// Unlock once
		err1 := infobaseSvc.UnlockInfobase(ctx, clusterID, infobaseID)
		require.NoError(t, err1, "First unlock should succeed")

		// Unlock again (idempotent)
		err2 := infobaseSvc.UnlockInfobase(ctx, clusterID, infobaseID)
		require.NoError(t, err2, "Second unlock (idempotent) should succeed")

		// Unlock third time
		err3 := infobaseSvc.UnlockInfobase(ctx, clusterID, infobaseID)
		require.NoError(t, err3, "Third unlock (idempotent) should succeed")

		t.Log("Unlock operation is idempotent (can be called multiple times safely)")
	})
}
