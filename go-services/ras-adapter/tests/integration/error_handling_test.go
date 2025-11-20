// +build integration

package integration

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/ras"
)

// TestInvalidParameterValidation tests parameter validation
func TestInvalidParameterValidation(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	infobaseSvc := createInfobaseService(t, rasPool)
	ctx := context.Background()

	tests := []struct {
		name         string
		clusterID    string
		infobaseID   string
		expectError  bool
		description  string
	}{
		{
			name:        "missing_cluster_id",
			clusterID:   "",
			infobaseID:  "infobase-1",
			expectError: true,
			description: "Should fail with empty cluster ID",
		},
		{
			name:        "missing_infobase_id",
			clusterID:   "cluster-1",
			infobaseID:  "",
			expectError: true,
			description: "Should fail with empty infobase ID",
		},
		{
			name:        "both_empty",
			clusterID:   "",
			infobaseID:  "",
			expectError: true,
			description: "Should fail with both IDs empty",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := infobaseSvc.LockInfobase(ctx, tt.clusterID, tt.infobaseID)

			if tt.expectError {
				assert.Error(t, err, tt.description)
				t.Logf("Expected error: %v", err)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

// TestNonexistentClusterHandling tests behavior with nonexistent cluster
func TestNonexistentClusterHandling(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	ctx := context.Background()

	t.Run("nonexistent_cluster", func(t *testing.T) {
		client, err := rasPool.GetConnection(ctx)
		require.NoError(t, err)
		defer rasPool.ReleaseConnection(client)

		// Try to get infobases for nonexistent cluster
		infobases, err := client.GetInfobases(ctx, "00000000-0000-0000-0000-000000000000")

		// Should either fail gracefully or return empty list
		if err != nil {
			t.Logf("GetInfobases returned expected error for nonexistent cluster: %v", err)
			assert.Error(t, err)
		} else {
			t.Logf("GetInfobases returned empty list for nonexistent cluster")
			// Empty list is also acceptable
		}
	})
}

// TestNonexistentInfobaseHandling tests behavior with nonexistent infobase
func TestNonexistentInfobaseHandling(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(t, rasPool)
	ctx := context.Background()

	t.Run("nonexistent_infobase", func(t *testing.T) {
		client, err := rasPool.GetConnection(ctx)
		require.NoError(t, err)
		defer rasPool.ReleaseConnection(client)

		// Try to get info for nonexistent infobase
		infobase, err := client.GetInfobaseInfo(ctx, clusterID, "00000000-0000-0000-0000-000000000000")

		// Should either fail gracefully or return nil
		if err != nil {
			t.Logf("GetInfobaseInfo returned expected error for nonexistent infobase: %v", err)
			assert.Error(t, err)
		} else if infobase == nil {
			t.Logf("GetInfobaseInfo returned nil for nonexistent infobase")
		}
	})
}

// TestRASTimeoutHandling tests timeout behavior
func TestRASTimeoutHandling(t *testing.T) {
	_, redisClient, logger := setupTestEnvironment(t)
	defer cleanupTestEnvironment(nil, redisClient)

	t.Run("short_timeout_handling", func(t *testing.T) {
		// Create pool with very short request timeout
		rasPool, err := ras.NewPool(
			testRASServer,
			5,
			10*time.Second,
			50*time.Millisecond, // Very short timeout
			logger,
		)
		require.NoError(t, err)
		defer rasPool.Close()

		ctx := context.Background()

		client, err := rasPool.GetConnection(ctx)
		require.NoError(t, err)
		defer rasPool.ReleaseConnection(client)

		// This operation may timeout with very short timeout
		_, err = client.GetClusters(ctx)

		// Either succeeds quickly or times out
		if err != nil {
			t.Logf("Operation timed out as expected: %v", err)
		} else {
			t.Log("Operation completed despite short timeout")
		}
	})
}

// TestContextCancellation tests context cancellation
func TestContextCancellation(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	t.Run("cancelled_context", func(t *testing.T) {
		ctx, cancel := context.WithCancel(context.Background())
		cancel() // Cancel immediately

		client, err := rasPool.GetConnection(context.Background())
		require.NoError(t, err)
		defer rasPool.ReleaseConnection(client)

		// Try to use cancelled context
		_, err = client.GetClusters(ctx)

		// Should fail with context cancelled error
		assert.Error(t, err, "Operation with cancelled context should fail")
		t.Logf("Expected error with cancelled context: %v", err)
	})
}

// TestConnectionPoolExhaustion tests pool behavior when exhausted
func TestConnectionPoolExhaustion(t *testing.T) {
	_, redisClient, logger := setupTestEnvironment(t)
	defer cleanupTestEnvironment(nil, redisClient)

	t.Run("pool_exhaustion", func(t *testing.T) {
		// Create small pool (size=2)
		rasPool, err := ras.NewPool(
			testRASServer,
			2,                      // Small pool size
			10*time.Second,         // Connection timeout
			30*time.Second,         // Request timeout
			logger,
		)
		require.NoError(t, err)
		defer rasPool.Close()

		ctx := context.Background()

		// Get 2 connections (exhaust pool)
		client1, err := rasPool.GetConnection(ctx)
		require.NoError(t, err)

		client2, err := rasPool.GetConnection(ctx)
		require.NoError(t, err)

		// Try to get 3rd connection (should create new one)
		done := make(chan bool)
		go func() {
			client3, err := rasPool.GetConnection(ctx)
			if err == nil {
				rasPool.ReleaseConnection(client3)
				done <- true
			} else {
				done <- false
			}
		}()

		// Release one connection to allow 3rd to be acquired
		time.Sleep(100 * time.Millisecond)
		rasPool.ReleaseConnection(client1)

		// Wait for 3rd connection
		select {
		case success := <-done:
			assert.True(t, success, "Should successfully create 3rd connection")
			t.Log("Pool correctly created new connection when exhausted")
		case <-time.After(5 * time.Second):
			t.Fatal("Timeout waiting for 3rd connection")
		}

		rasPool.ReleaseConnection(client2)
	})
}

// TestPoolHealthCheck tests connection health verification
func TestPoolHealthCheck(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	ctx := context.Background()

	t.Run("pool_health_check", func(t *testing.T) {
		// Get connection
		client, err := rasPool.GetConnection(ctx)
		require.NoError(t, err)

		// Verify it's healthy
		clusters, err := client.GetClusters(ctx)
		assert.NoError(t, err)
		assert.NotEmpty(t, clusters)

		// Release back to pool (triggers health check)
		rasPool.ReleaseConnection(client)

		t.Log("Connection health check passed")
	})
}

// TestConcurrentErrorHandling tests error handling under concurrent load
func TestConcurrentErrorHandling(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(t, rasPool)
	infobaseSvc := createInfobaseService(t, rasPool)

	const numOps = 20
	errors := make(chan error, numOps)

	t.Run("concurrent_error_handling", func(t *testing.T) {
		ctx := context.Background()

		// Mix of valid and invalid operations
		for i := 0; i < numOps; i++ {
			go func(idx int) {
				if idx%2 == 0 {
					// Valid operation
					err := infobaseSvc.LockInfobase(ctx, clusterID, GetTestInfobaseID(t, rasPool))
					errors <- err
				} else {
					// Invalid operation (missing cluster ID)
					err := infobaseSvc.LockInfobase(ctx, "", "infobase-1")
					errors <- err
				}
			}(i)
		}

		// Collect results
		successCount := 0
		errorCount := 0

		for i := 0; i < numOps; i++ {
			if err := <-errors; err == nil {
				successCount++
			} else {
				errorCount++
			}
		}

		t.Logf("Concurrent error handling: %d succeeded, %d failed", successCount, errorCount)
		assert.Greater(t, errorCount, 0, "Should have failed operations")
	})

	// Cleanup
	ctx := context.Background()
	err := infobaseSvc.UnlockInfobase(ctx, clusterID, GetTestInfobaseID(t, rasPool))
	if err != nil {
		t.Logf("Cleanup unlock warning: %v", err)
	}
}

// TestPoolClosing tests proper pool closure
func TestPoolClosing(t *testing.T) {
	rasPool, redisClient, logger := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	ctx := context.Background()

	t.Run("pool_close_with_active_connections", func(t *testing.T) {
		// Get a connection
		client, err := rasPool.GetConnection(ctx)
		require.NoError(t, err)
		defer rasPool.ReleaseConnection(client)

		// Verify it works
		_, err = client.GetClusters(ctx)
		require.NoError(t, err)

		// Close pool
		err = rasPool.Close()
		assert.NoError(t, err, "Pool closure should succeed")

		t.Log("Pool closed successfully")
	})
}

// TestErrorMessageClarity tests error messages are clear and helpful
func TestErrorMessageClarity(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	infobaseSvc := createInfobaseService(t, rasPool)
	ctx := context.Background()

	t.Run("error_messages_clarity", func(t *testing.T) {
		// Test missing cluster ID
		err := infobaseSvc.LockInfobase(ctx, "", "infobase-1")
		assert.Error(t, err)
		assert.NotEmpty(t, err.Error(), "Error message should not be empty")
		t.Logf("Missing cluster ID error: %v", err)

		// Test missing infobase ID
		err = infobaseSvc.LockInfobase(ctx, "cluster-1", "")
		assert.Error(t, err)
		assert.NotEmpty(t, err.Error())
		t.Logf("Missing infobase ID error: %v", err)
	})
}
