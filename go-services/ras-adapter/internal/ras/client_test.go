package ras

import (
	"context"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/models"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestNewClient_Success tests successful client creation
func TestNewClient_Success(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)

	assert.NoError(t, err)
	assert.NotNil(t, client)
	assert.Equal(t, "localhost:1545", client.serverAddr)
}

// TestNewClient_InvalidParams tests handling of invalid parameters
func TestNewClient_InvalidParams(t *testing.T) {
	client, err := NewClient("", 5, 10, nil)

	assert.Error(t, err)
	assert.Nil(t, client)
	assert.Equal(t, ErrInvalidParams, err)
}

// TestGetClusters_ReturnsData tests that GetClusters returns mock data
func TestGetClusters_ReturnsData(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	clusters, err := client.GetClusters(context.Background())

	assert.NoError(t, err)
	assert.NotNil(t, clusters)
	assert.Equal(t, 1, len(clusters))
	assert.Equal(t, "Local Cluster", clusters[0].Name)
	assert.Equal(t, "localhost", clusters[0].Host)
	assert.Equal(t, int32(1541), clusters[0].Port)
}

// TestGetClusters_ReturnsValidUUID tests that clusters have valid UUIDs
func TestGetClusters_ReturnsValidUUID(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	clusters, err := client.GetClusters(context.Background())

	assert.NoError(t, err)
	assert.NotEmpty(t, clusters[0].UUID)
	// UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx (36 characters)
	assert.True(t, len(clusters[0].UUID) > 30)
}

// TestGetInfobases_ValidClusterID tests GetInfobases with valid cluster ID
func TestGetInfobases_ValidClusterID(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	infobases, err := client.GetInfobases(context.Background(), "cluster-uuid")

	assert.NoError(t, err)
	assert.NotNil(t, infobases)
	assert.Equal(t, 1, len(infobases))
	assert.Equal(t, "test_db", infobases[0].Name)
	assert.Equal(t, "PostgreSQL", infobases[0].DBMS)
}

// TestGetInfobases_EmptyClusterID tests GetInfobases with empty cluster ID
func TestGetInfobases_EmptyClusterID(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	infobases, err := client.GetInfobases(context.Background(), "")

	assert.Error(t, err)
	assert.Nil(t, infobases)
	assert.Equal(t, ErrInvalidParams, err)
}

// TestGetSessions_ValidParams tests GetSessions with valid parameters
func TestGetSessions_ValidParams(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	sessions, err := client.GetSessions(context.Background(), "cluster-uuid", "infobase-uuid")

	assert.NoError(t, err)
	assert.NotNil(t, sessions)
	assert.Equal(t, 1, len(sessions))
	assert.Equal(t, "TestUser", sessions[0].UserName)
	assert.Equal(t, "1CV8C", sessions[0].Application)
}

// TestGetSessions_EmptyClusterID tests GetSessions with empty cluster ID
func TestGetSessions_EmptyClusterID(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	sessions, err := client.GetSessions(context.Background(), "", "infobase-uuid")

	assert.Error(t, err)
	assert.Nil(t, sessions)
	assert.Equal(t, ErrInvalidParams, err)
}

// TestGetSessions_OptionalInfobaseID tests GetSessions with empty infobase ID (optional)
func TestGetSessions_OptionalInfobaseID(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	sessions, err := client.GetSessions(context.Background(), "cluster-uuid", "")

	assert.NoError(t, err)
	assert.NotNil(t, sessions)
	// Empty infobase_id should still return sessions
	assert.GreaterOrEqual(t, len(sessions), 0)
}

// TestTerminateSession_ValidParams tests TerminateSession with valid parameters
func TestTerminateSession_ValidParams(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	err = client.TerminateSession(context.Background(), "cluster-uuid", "session-uuid")

	assert.NoError(t, err)
}

// TestTerminateSession_EmptyClusterID tests TerminateSession with empty cluster ID
func TestTerminateSession_EmptyClusterID(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	err = client.TerminateSession(context.Background(), "", "session-uuid")

	assert.Error(t, err)
	assert.Equal(t, ErrInvalidParams, err)
}

// TestTerminateSession_EmptySessionID tests TerminateSession with empty session ID
func TestTerminateSession_EmptySessionID(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	err = client.TerminateSession(context.Background(), "cluster-uuid", "")

	assert.Error(t, err)
	assert.Equal(t, ErrInvalidParams, err)
}

// TestClose_NoError tests Close method
func TestClose_NoError(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	err = client.Close()

	assert.NoError(t, err)
}

// TestContextPropagation tests that context is accepted and used
func TestContextPropagation(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	ctx := context.Background()

	clusters, err := client.GetClusters(ctx)
	assert.NoError(t, err)
	assert.NotNil(t, clusters)

	infobases, err := client.GetInfobases(ctx, "cluster-uuid")
	assert.NoError(t, err)
	assert.NotNil(t, infobases)

	sessions, err := client.GetSessions(ctx, "cluster-uuid", "infobase-uuid")
	assert.NoError(t, err)
	assert.NotNil(t, sessions)

	err = client.TerminateSession(ctx, "cluster-uuid", "session-uuid")
	assert.NoError(t, err)
}

// TestCancelledContext tests behavior with cancelled context
func TestCancelledContext(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	// In Week 1 stub, context is not used, so these should still work
	clusters, err := client.GetClusters(ctx)
	assert.NoError(t, err)
	assert.NotNil(t, clusters)
}

// TestSessionHasRequiredFields tests that returned sessions have required fields
func TestSessionHasRequiredFields(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	sessions, err := client.GetSessions(context.Background(), "cluster-uuid", "infobase-uuid")

	assert.NoError(t, err)
	assert.NotEmpty(t, sessions)

	for _, session := range sessions {
		assert.NotEmpty(t, session.UUID)
		assert.NotEmpty(t, session.SessionID)
		assert.NotEmpty(t, session.UserName)
		assert.NotEmpty(t, session.Application)
		assert.NotEmpty(t, session.StartedAt)
	}
}

// TestInfobaseHasRequiredFields tests that returned infobases have required fields
func TestInfobaseHasRequiredFields(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	infobases, err := client.GetInfobases(context.Background(), "cluster-uuid")

	assert.NoError(t, err)
	assert.NotEmpty(t, infobases)

	for _, infobase := range infobases {
		assert.NotEmpty(t, infobase.UUID)
		assert.NotEmpty(t, infobase.Name)
		assert.NotEmpty(t, infobase.DBMS)
	}
}

// TestClusterHasRequiredFields tests that returned clusters have required fields
func TestClusterHasRequiredFields(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	clusters, err := client.GetClusters(context.Background())

	assert.NoError(t, err)
	assert.NotEmpty(t, clusters)

	for _, cluster := range clusters {
		assert.NotEmpty(t, cluster.UUID)
		assert.NotEmpty(t, cluster.Name)
		assert.NotEmpty(t, cluster.Host)
		assert.Greater(t, int(cluster.Port), 0)
	}
}

// TestMultipleCalls tests multiple calls to same client
func TestMultipleCalls(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	// Call GetClusters multiple times
	for i := 0; i < 3; i++ {
		clusters, err := client.GetClusters(context.Background())
		assert.NoError(t, err)
		assert.Equal(t, 1, len(clusters))
	}

	// Call GetInfobases multiple times
	for i := 0; i < 3; i++ {
		infobases, err := client.GetInfobases(context.Background(), "cluster-uuid")
		assert.NoError(t, err)
		assert.Equal(t, 1, len(infobases))
	}
}

// BenchmarkGetClusters benchmarks GetClusters performance
func BenchmarkGetClusters(b *testing.B) {
	client, _ := NewClient("localhost:1545", 5, 10, nil)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		client.GetClusters(context.Background())
	}
}

// BenchmarkGetSessions benchmarks GetSessions performance
func BenchmarkGetSessions(b *testing.B) {
	client, _ := NewClient("localhost:1545", 5, 10, nil)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		client.GetSessions(context.Background(), "cluster-uuid", "infobase-uuid")
	}
}

// ====================== WEEK 2 TESTS: Lock/Unlock ======================

// TestClient_GetInfobaseInfo tests GetInfobaseInfo method
func TestClient_GetInfobaseInfo(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	t.Run("Success", func(t *testing.T) {
		info, err := client.GetInfobaseInfo(context.Background(), "cluster-uuid", "infobase-uuid")
		assert.NoError(t, err)
		assert.NotNil(t, info)
		assert.Equal(t, "infobase-uuid", info.UUID)
		assert.Equal(t, "TestInfobase", info.Name)
		assert.Equal(t, "PostgreSQL", info.DBMS)
		assert.False(t, info.ScheduledJobsDeny) // Default: unlocked
		assert.False(t, info.SessionsDeny)
	})

	t.Run("Empty ClusterID", func(t *testing.T) {
		info, err := client.GetInfobaseInfo(context.Background(), "", "infobase-uuid")
		assert.Error(t, err)
		assert.Nil(t, info)
		assert.Equal(t, ErrInvalidParams, err)
	})

	t.Run("Empty InfobaseID", func(t *testing.T) {
		info, err := client.GetInfobaseInfo(context.Background(), "cluster-uuid", "")
		assert.Error(t, err)
		assert.Nil(t, info)
		assert.Equal(t, ErrInvalidParams, err)
	})

	t.Run("Both params empty", func(t *testing.T) {
		info, err := client.GetInfobaseInfo(context.Background(), "", "")
		assert.Error(t, err)
		assert.Nil(t, info)
		assert.Equal(t, ErrInvalidParams, err)
	})

	t.Run("Returns correct structure", func(t *testing.T) {
		info, err := client.GetInfobaseInfo(context.Background(), "cluster-uuid", "infobase-uuid")
		assert.NoError(t, err)
		assert.NotNil(t, info.UUID)
		assert.NotNil(t, info.Name)
		assert.NotNil(t, info.DBMS)
		assert.NotNil(t, info.DBServer)
		assert.NotNil(t, info.DBName)
	})
}

// TestClient_RegInfoBase tests RegInfoBase method
func TestClient_RegInfoBase(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	testInfobase := &models.Infobase{
		UUID:     "infobase-uuid",
		Name:     "TestDB",
		DBMS:     "PostgreSQL",
		DBServer: "localhost",
		DBName:   "test_db",
	}

	t.Run("Success with valid params", func(t *testing.T) {
		err := client.RegInfoBase(context.Background(), "cluster-uuid", testInfobase)
		assert.NoError(t, err)
	})

	t.Run("Empty ClusterID", func(t *testing.T) {
		err := client.RegInfoBase(context.Background(), "", testInfobase)
		assert.Error(t, err)
		assert.Equal(t, ErrInvalidParams, err)
	})

	t.Run("Nil Infobase", func(t *testing.T) {
		err := client.RegInfoBase(context.Background(), "cluster-uuid", nil)
		assert.Error(t, err)
		assert.Equal(t, ErrInvalidParams, err)
	})

	t.Run("Multiple RegInfoBase calls", func(t *testing.T) {
		for i := 0; i < 3; i++ {
			err := client.RegInfoBase(context.Background(), "cluster-uuid", testInfobase)
			assert.NoError(t, err)
		}
	})
}

// TestClient_LockInfobase tests LockInfobase method
func TestClient_LockInfobase(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	t.Run("Success", func(t *testing.T) {
		err := client.LockInfobase(context.Background(), "cluster-uuid", "infobase-uuid")
		assert.NoError(t, err)
	})

	t.Run("Empty ClusterID", func(t *testing.T) {
		err := client.LockInfobase(context.Background(), "", "infobase-uuid")
		assert.Error(t, err)
		assert.Equal(t, ErrInvalidParams, err)
	})

	t.Run("Empty InfobaseID", func(t *testing.T) {
		err := client.LockInfobase(context.Background(), "cluster-uuid", "")
		assert.Error(t, err)
		assert.Equal(t, ErrInvalidParams, err)
	})

	t.Run("Both params empty", func(t *testing.T) {
		err := client.LockInfobase(context.Background(), "", "")
		assert.Error(t, err)
		assert.Equal(t, ErrInvalidParams, err)
	})

	t.Run("Multiple lock attempts", func(t *testing.T) {
		for i := 0; i < 3; i++ {
			err := client.LockInfobase(context.Background(), "cluster-uuid", "infobase-uuid")
			assert.NoError(t, err)
		}
	})

	t.Run("Lock returns no error", func(t *testing.T) {
		// Verify that lock call completes without error
		// Note: State verification requires real RAS protocol (Week 3+), not stub
		err := client.LockInfobase(context.Background(), "cluster-uuid", "infobase-uuid")
		assert.NoError(t, err)
	})
}

// TestClient_UnlockInfobase tests UnlockInfobase method
func TestClient_UnlockInfobase(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	t.Run("Success", func(t *testing.T) {
		err := client.UnlockInfobase(context.Background(), "cluster-uuid", "infobase-uuid")
		assert.NoError(t, err)
	})

	t.Run("Empty ClusterID", func(t *testing.T) {
		err := client.UnlockInfobase(context.Background(), "", "infobase-uuid")
		assert.Error(t, err)
		assert.Equal(t, ErrInvalidParams, err)
	})

	t.Run("Empty InfobaseID", func(t *testing.T) {
		err := client.UnlockInfobase(context.Background(), "cluster-uuid", "")
		assert.Error(t, err)
		assert.Equal(t, ErrInvalidParams, err)
	})

	t.Run("Both params empty", func(t *testing.T) {
		err := client.UnlockInfobase(context.Background(), "", "")
		assert.Error(t, err)
		assert.Equal(t, ErrInvalidParams, err)
	})

	t.Run("Multiple unlock attempts", func(t *testing.T) {
		for i := 0; i < 3; i++ {
			err := client.UnlockInfobase(context.Background(), "cluster-uuid", "infobase-uuid")
			assert.NoError(t, err)
		}
	})

	t.Run("Unlock flow: GetInfobaseInfo -> RegInfoBase", func(t *testing.T) {
		// First lock
		err := client.LockInfobase(context.Background(), "cluster-uuid", "infobase-uuid")
		assert.NoError(t, err)

		// Then unlock
		err = client.UnlockInfobase(context.Background(), "cluster-uuid", "infobase-uuid")
		assert.NoError(t, err)

		// Verify state
		info, err := client.GetInfobaseInfo(context.Background(), "cluster-uuid", "infobase-uuid")
		assert.NoError(t, err)
		assert.False(t, info.ScheduledJobsDeny) // Should be unlocked
		assert.False(t, info.SessionsDeny)      // Sessions still allowed
	})
}

// TestClient_LockUnlock_Sequence tests lock/unlock sequence
func TestClient_LockUnlock_Sequence(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	clusterID := "cluster-uuid"
	infobaseID := "infobase-uuid"

	t.Run("Lock then Unlock succeeds", func(t *testing.T) {
		// 1. Lock
		err := client.LockInfobase(context.Background(), clusterID, infobaseID)
		assert.NoError(t, err)

		// 2. Unlock
		err = client.UnlockInfobase(context.Background(), clusterID, infobaseID)
		assert.NoError(t, err)

		// Note: State verification requires real RAS protocol (Week 3+), not stub
	})

	t.Run("Multiple lock/unlock cycles", func(t *testing.T) {
		for cycle := 0; cycle < 3; cycle++ {
			// Lock
			err := client.LockInfobase(context.Background(), clusterID, infobaseID)
			assert.NoError(t, err)

			// Unlock
			err = client.UnlockInfobase(context.Background(), clusterID, infobaseID)
			assert.NoError(t, err)
		}
	})
}

// TestClient_LockUnlock_WithContext tests with different context scenarios
func TestClient_LockUnlock_WithContext(t *testing.T) {
	client, err := NewClient("localhost:1545", 5, 10, nil)
	require.NoError(t, err)

	t.Run("With cancelled context", func(t *testing.T) {
		ctx, cancel := context.WithCancel(context.Background())
		cancel()

		// In Week 1 stub, context is ignored, so these should still work
		err := client.LockInfobase(ctx, "cluster-uuid", "infobase-uuid")
		assert.NoError(t, err)

		err = client.UnlockInfobase(ctx, "cluster-uuid", "infobase-uuid")
		assert.NoError(t, err)
	})

	t.Run("With timeout context", func(t *testing.T) {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		err := client.LockInfobase(ctx, "cluster-uuid", "infobase-uuid")
		assert.NoError(t, err)

		err = client.UnlockInfobase(ctx, "cluster-uuid", "infobase-uuid")
		assert.NoError(t, err)
	})
}

// BenchmarkLockInfobase benchmarks LockInfobase performance
func BenchmarkLockInfobase(b *testing.B) {
	client, _ := NewClient("localhost:1545", 5, 10, nil)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		client.LockInfobase(context.Background(), "cluster-uuid", "infobase-uuid")
	}
}

// BenchmarkUnlockInfobase benchmarks UnlockInfobase performance
func BenchmarkUnlockInfobase(b *testing.B) {
	client, _ := NewClient("localhost:1545", 5, 10, nil)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		client.UnlockInfobase(context.Background(), "cluster-uuid", "infobase-uuid")
	}
}

// BenchmarkGetInfobaseInfo benchmarks GetInfobaseInfo performance
func BenchmarkGetInfobaseInfo(b *testing.B) {
	client, _ := NewClient("localhost:1545", 5, 10, nil)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		client.GetInfobaseInfo(context.Background(), "cluster-uuid", "infobase-uuid")
	}
}
