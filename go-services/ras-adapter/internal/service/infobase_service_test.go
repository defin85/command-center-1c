//go:build integration
// +build integration

package service

import (
	"context"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/ras"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"
)

// TestNewInfobaseService tests InfobaseService instantiation
func TestNewInfobaseService(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	assert.NotNil(t, svc)
	assert.NotNil(t, svc.rasPool)
	assert.Equal(t, logger, svc.logger)

	pool.Close()
}

// TestGetInfobases_Success tests successful retrieval of infobases
func TestGetInfobases_Success(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	infobases, err := svc.GetInfobases(context.Background(), "cluster-uuid")

	assert.NoError(t, err)
	assert.NotNil(t, infobases)
	assert.Equal(t, 1, len(infobases))
	assert.Equal(t, "test_db", infobases[0].Name)

	pool.Close()
}

// TestGetInfobases_MissingClusterID tests handling of missing cluster ID
func TestGetInfobases_MissingClusterID(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	infobases, err := svc.GetInfobases(context.Background(), "")

	assert.Error(t, err)
	assert.Nil(t, infobases)
	assert.Contains(t, err.Error(), "cluster_id is required")

	pool.Close()
}

// TestGetInfobases_ValidClusterID tests with different cluster IDs
func TestGetInfobases_ValidClusterID(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	testCases := []string{
		"00000000-0000-0000-0000-000000000001",
		"cluster-1",
		"some-cluster-id",
	}

	for _, clusterID := range testCases {
		infobases, err := svc.GetInfobases(context.Background(), clusterID)

		assert.NoError(t, err)
		assert.NotNil(t, infobases)
		assert.GreaterOrEqual(t, len(infobases), 0)
	}

	pool.Close()
}

// TestGetInfobases_ContextWithTimeout tests context with timeout
func TestGetInfobases_ContextWithTimeout(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	infobases, err := svc.GetInfobases(ctx, "cluster-uuid")

	assert.NoError(t, err)
	assert.NotNil(t, infobases)

	pool.Close()
}

// BenchmarkGetInfobases benchmarks GetInfobases performance
func BenchmarkGetInfobases(b *testing.B) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(b, err)

	svc := NewInfobaseService(pool, logger)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		svc.GetInfobases(context.Background(), "cluster-uuid")
	}

	pool.Close()
}

// ====================== WEEK 2 TESTS: Lock/Unlock ======================

// TestLockInfobase_Success tests successful lock
func TestLockInfobase_Success(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	err = svc.LockInfobase(context.Background(), "cluster-uuid", "infobase-uuid", "dbuser", "dbpassword")

	assert.NoError(t, err)

	pool.Close()
}

// TestLockInfobase_EmptyClusterID tests lock with empty cluster ID
func TestLockInfobase_EmptyClusterID(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	err = svc.LockInfobase(context.Background(), "", "infobase-uuid", "dbuser", "dbpassword")

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "cluster_id and infobase_id are required")

	pool.Close()
}

// TestLockInfobase_EmptyInfobaseID tests lock with empty infobase ID
func TestLockInfobase_EmptyInfobaseID(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	err = svc.LockInfobase(context.Background(), "cluster-uuid", "", "dbuser", "dbpassword")

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "cluster_id and infobase_id are required")

	pool.Close()
}

// TestLockInfobase_BothParamsEmpty tests lock with both params empty
func TestLockInfobase_BothParamsEmpty(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	err = svc.LockInfobase(context.Background(), "", "", "dbuser", "dbpassword")

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "cluster_id and infobase_id are required")

	pool.Close()
}

// TestLockInfobase_WithTimeout tests lock with timeout context
func TestLockInfobase_WithTimeout(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err = svc.LockInfobase(ctx, "cluster-uuid", "infobase-uuid", "dbuser", "dbpassword")

	assert.NoError(t, err)

	pool.Close()
}

// TestLockInfobase_MultipleCalls tests multiple lock calls
func TestLockInfobase_MultipleCalls(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	for i := 0; i < 3; i++ {
		err := svc.LockInfobase(context.Background(), "cluster-uuid", "infobase-uuid", "dbuser", "dbpassword")
		assert.NoError(t, err)
	}

	pool.Close()
}

// TestUnlockInfobase_Success tests successful unlock
func TestUnlockInfobase_Success(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	err = svc.UnlockInfobase(context.Background(), "cluster-uuid", "infobase-uuid", "dbuser", "dbpassword")

	assert.NoError(t, err)

	pool.Close()
}

// TestUnlockInfobase_EmptyClusterID tests unlock with empty cluster ID
func TestUnlockInfobase_EmptyClusterID(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	err = svc.UnlockInfobase(context.Background(), "", "infobase-uuid", "dbuser", "dbpassword")

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "cluster_id and infobase_id are required")

	pool.Close()
}

// TestUnlockInfobase_EmptyInfobaseID tests unlock with empty infobase ID
func TestUnlockInfobase_EmptyInfobaseID(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	err = svc.UnlockInfobase(context.Background(), "cluster-uuid", "", "dbuser", "dbpassword")

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "cluster_id and infobase_id are required")

	pool.Close()
}

// TestUnlockInfobase_BothParamsEmpty tests unlock with both params empty
func TestUnlockInfobase_BothParamsEmpty(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	err = svc.UnlockInfobase(context.Background(), "", "", "dbuser", "dbpassword")

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "cluster_id and infobase_id are required")

	pool.Close()
}

// TestUnlockInfobase_WithTimeout tests unlock with timeout context
func TestUnlockInfobase_WithTimeout(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err = svc.UnlockInfobase(ctx, "cluster-uuid", "infobase-uuid", "dbuser", "dbpassword")

	assert.NoError(t, err)

	pool.Close()
}

// TestUnlockInfobase_MultipleCalls tests multiple unlock calls
func TestUnlockInfobase_MultipleCalls(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	for i := 0; i < 3; i++ {
		err := svc.UnlockInfobase(context.Background(), "cluster-uuid", "infobase-uuid", "dbuser", "dbpassword")
		assert.NoError(t, err)
	}

	pool.Close()
}

// TestLockUnlock_Sequence tests complete lock/unlock sequence
func TestLockUnlock_Sequence(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	// Lock
	err = svc.LockInfobase(context.Background(), "cluster-uuid", "infobase-uuid", "dbuser", "dbpassword")
	assert.NoError(t, err)

	// Unlock
	err = svc.UnlockInfobase(context.Background(), "cluster-uuid", "infobase-uuid", "dbuser", "dbpassword")
	assert.NoError(t, err)

	pool.Close()
}

// TestLockUnlock_MultipleCycles tests multiple lock/unlock cycles
func TestLockUnlock_MultipleCycles(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewInfobaseService(pool, logger)

	for cycle := 0; cycle < 3; cycle++ {
		// Lock
		err := svc.LockInfobase(context.Background(), "cluster-uuid", "infobase-uuid", "dbuser", "dbpassword")
		assert.NoError(t, err)

		// Unlock
		err = svc.UnlockInfobase(context.Background(), "cluster-uuid", "infobase-uuid", "dbuser", "dbpassword")
		assert.NoError(t, err)
	}

	pool.Close()
}

// BenchmarkLockInfobase benchmarks LockInfobase performance
func BenchmarkLockInfobase(b *testing.B) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(b, err)

	svc := NewInfobaseService(pool, logger)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		svc.LockInfobase(context.Background(), "cluster-uuid", "infobase-uuid", "dbuser", "dbpassword")
	}

	pool.Close()
}

// BenchmarkUnlockInfobase benchmarks UnlockInfobase performance
func BenchmarkUnlockInfobase(b *testing.B) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(b, err)

	svc := NewInfobaseService(pool, logger)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		svc.UnlockInfobase(context.Background(), "cluster-uuid", "infobase-uuid", "dbuser", "dbpassword")
	}

	pool.Close()
}
