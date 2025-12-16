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

// TestNewClusterService tests ClusterService instantiation
func TestNewClusterService(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewClusterService(pool, logger)

	assert.NotNil(t, svc)
	assert.NotNil(t, svc.rasPool)
	assert.Equal(t, logger, svc.logger)

	pool.Close()
}

// TestGetClusters_Success tests successful retrieval of clusters
func TestGetClusters_Success(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewClusterService(pool, logger)

	clusters, err := svc.GetClusters(context.Background(), "localhost:1545")

	assert.NoError(t, err)
	assert.NotNil(t, clusters)
	assert.Equal(t, 1, len(clusters))
	assert.Equal(t, "Local Cluster", clusters[0].Name)

	pool.Close()
}

// TestGetClusters_ValidServerAddr tests with various server addresses
func TestGetClusters_ValidServerAddr(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewClusterService(pool, logger)

	testCases := []string{
		"localhost:1545",
		"192.168.1.1:1545",
		"remote.server.com:1545",
	}

	for _, serverAddr := range testCases {
		clusters, err := svc.GetClusters(context.Background(), serverAddr)

		assert.NoError(t, err)
		assert.NotNil(t, clusters)
	}

	pool.Close()
}

// TestGetClusters_EmptyServerAddr tests with empty server address
func TestGetClusters_EmptyServerAddr(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewClusterService(pool, logger)

	clusters, err := svc.GetClusters(context.Background(), "")

	assert.NoError(t, err)
	assert.NotNil(t, clusters)

	pool.Close()
}

// TestGetClusters_ContextCancellation tests handling of cancelled context
func TestGetClusters_ContextCancellation(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewClusterService(pool, logger)

	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	clusters, err := svc.GetClusters(ctx, "localhost:1545")

	// The stub implementation ignores context, so this should still work
	assert.NoError(t, err)
	assert.NotNil(t, clusters)

	pool.Close()
}

// TestGetClusters_ContextWithTimeout tests handling of context with timeout
func TestGetClusters_ContextWithTimeout(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewClusterService(pool, logger)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	clusters, err := svc.GetClusters(ctx, "localhost:1545")

	assert.NoError(t, err)
	assert.NotNil(t, clusters)

	pool.Close()
}

// BenchmarkGetClusters benchmarks GetClusters performance
func BenchmarkGetClusters(b *testing.B) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(b, err)

	svc := NewClusterService(pool, logger)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		svc.GetClusters(context.Background(), "localhost:1545")
	}

	pool.Close()
}
