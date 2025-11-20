// +build integration

package integration

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestGetClustersIntegration tests cluster discovery from real RAS server
func TestGetClustersIntegration(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterSvc := createClusterService(t, rasPool)
	ctx := context.Background()

	t.Run("get_clusters", func(t *testing.T) {
		clusters, err := clusterSvc.GetClusters(ctx)
		require.NoError(t, err, "GetClusters should succeed")
		require.NotEmpty(t, clusters, "At least one cluster should exist")

		// Verify cluster structure
		for _, cluster := range clusters {
			assert.NotEmpty(t, cluster.UUID, "Cluster UUID should not be empty")
			assert.NotEmpty(t, cluster.Name, "Cluster name should not be empty")
			// Host and Port may be empty in some configurations
		}

		t.Logf("Retrieved %d cluster(s)", len(clusters))
		for i, cluster := range clusters {
			t.Logf("  [%d] %s (UUID: %s, Host: %s:%d)",
				i+1, cluster.Name, cluster.UUID, cluster.Host, cluster.Port)
		}
	})
}

// TestGetInfobasesIntegration tests infobase discovery for a cluster
func TestGetInfobasesIntegration(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(t, rasPool)
	infobaseSvc := createInfobaseService(t, rasPool)
	ctx := context.Background()

	t.Run("get_infobases_for_cluster", func(t *testing.T) {
		infobases, err := infobaseSvc.GetInfobases(ctx, clusterID)
		require.NoError(t, err, "GetInfobases should succeed")
		require.NotEmpty(t, infobases, "At least one infobase should exist in cluster")

		// Verify infobase structure
		for _, infobase := range infobases {
			assert.NotEmpty(t, infobase.UUID, "Infobase UUID should not be empty")
			assert.NotEmpty(t, infobase.Name, "Infobase name should not be empty")
		}

		t.Logf("Retrieved %d infobase(es) for cluster %s", len(infobases), clusterID)
		for i, ib := range infobases {
			t.Logf("  [%d] %s (UUID: %s, DBMS: %s)",
				i+1, ib.Name, ib.UUID, ib.DBMS)
		}
	})
}

// TestGetSessionsIntegration tests session listing
func TestGetSessionsIntegration(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(t, rasPool)
	sessionSvc := createSessionService(t, rasPool)
	ctx := context.Background()

	t.Run("get_sessions", func(t *testing.T) {
		sessions, err := sessionSvc.GetSessions(ctx, clusterID)
		require.NoError(t, err, "GetSessions should succeed")

		// Sessions may be empty (no active sessions)
		t.Logf("Retrieved %d session(s) for cluster %s", len(sessions), clusterID)
		for i, session := range sessions {
			t.Logf("  [%d] User: %s, App: %s (Session ID: %s)",
				i+1, session.UserName, session.AppID, session.SessionID)
		}
	})
}

// TestGetInfobaseInfoIntegration tests infobase detailed info
func TestGetInfobaseInfoIntegration(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(t, rasPool)
	infobaseID := GetTestInfobaseID(t, rasPool)

	ctx := context.Background()

	t.Run("get_infobase_info", func(t *testing.T) {
		client, err := rasPool.GetConnection(ctx)
		require.NoError(t, err)
		defer rasPool.ReleaseConnection(client)

		infobase, err := client.GetInfobaseInfo(ctx, clusterID, infobaseID)
		require.NoError(t, err, "GetInfobaseInfo should succeed")
		require.NotNil(t, infobase)

		assert.NotEmpty(t, infobase.UUID)
		assert.NotEmpty(t, infobase.Name)

		t.Logf("Infobase info: %s (ScheduledJobsDeny: %v, SessionsDeny: %v)",
			infobase.Name, infobase.ScheduledJobsDeny, infobase.SessionsDeny)
	})
}

// TestClusterConnectionPoolIntegration tests pool reuse
func TestClusterConnectionPoolIntegration(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(t, rasPool)
	infobaseSvc := createInfobaseService(t, rasPool)
	ctx := context.Background()

	t.Run("connection_pool_reuse", func(t *testing.T) {
		// Make multiple requests to verify pool reuse
		for i := 0; i < 5; i++ {
			infobases, err := infobaseSvc.GetInfobases(ctx, clusterID)
			require.NoError(t, err)
			require.NotEmpty(t, infobases)
		}

		// Check pool stats
		stats := rasPool.Stats()
		assert.NotNil(t, stats)
		assert.NotEmpty(t, stats["server"])
		assert.Greater(t, stats["max_connections"], 0)

		t.Logf("Pool stats: %+v", stats)
	})
}

// TestConcurrentClusterOperations tests concurrent cluster operations
func TestConcurrentClusterOperations(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(t, rasPool)
	clusterSvc := createClusterService(t, rasPool)
	ctx := context.Background()

	const numOps = 5
	errors := make(chan error, numOps)

	t.Run("concurrent_get_clusters", func(t *testing.T) {
		// Launch 5 concurrent GetClusters operations
		for i := 0; i < numOps; i++ {
			go func(idx int) {
				ctx := context.Background()
				_, err := clusterSvc.GetClusters(ctx)
				errors <- err
			}(i)
		}

		// Collect results
		successCount := 0
		for i := 0; i < numOps; i++ {
			if err := <-errors; err == nil {
				successCount++
			}
		}

		assert.Equal(t, numOps, successCount, "All concurrent GetClusters should succeed")
		t.Logf("Concurrent GetClusters: %d/%d succeeded", successCount, numOps)
	})
}

// TestOperationLatency measures operation latency
func TestOperationLatency(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(t, rasPool)
	clusterSvc := createClusterService(t, rasPool)
	ctx := context.Background()

	t.Run("operation_latency_measurement", func(t *testing.T) {
		// Measure GetClusters latency
		start := time.Now()
		_, err := clusterSvc.GetClusters(ctx)
		getClustersLatency := time.Since(start)
		require.NoError(t, err)

		// Measure GetInfobases latency
		infobaseSvc := createInfobaseService(t, rasPool)
		start = time.Now()
		_, err = infobaseSvc.GetInfobases(ctx, clusterID)
		getInfobasesLatency := time.Since(start)
		require.NoError(t, err)

		// Measure GetSessions latency
		sessionSvc := createSessionService(t, rasPool)
		start = time.Now()
		_, err = sessionSvc.GetSessions(ctx, clusterID)
		getSessionsLatency := time.Since(start)
		require.NoError(t, err)

		t.Logf("Operation latencies:")
		t.Logf("  GetClusters: %v", getClustersLatency)
		t.Logf("  GetInfobases: %v", getInfobasesLatency)
		t.Logf("  GetSessions: %v", getSessionsLatency)

		// All operations should complete in reasonable time (< 5 seconds)
		assert.Less(t, getClustersLatency, 5*time.Second)
		assert.Less(t, getInfobasesLatency, 5*time.Second)
		assert.Less(t, getSessionsLatency, 5*time.Second)
	})
}
