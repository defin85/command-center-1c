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

// TestNewSessionService tests SessionService instantiation
func TestNewSessionService(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewSessionService(pool, logger)

	assert.NotNil(t, svc)
	assert.NotNil(t, svc.rasPool)
	assert.Equal(t, logger, svc.logger)

	pool.Close()
}

// TestGetSessions_Success tests successful retrieval of sessions
func TestGetSessions_Success(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewSessionService(pool, logger)

	sessions, err := svc.GetSessions(context.Background(), "cluster-uuid", "infobase-uuid")

	assert.NoError(t, err)
	assert.NotNil(t, sessions)
	assert.Equal(t, 1, len(sessions))
	assert.Equal(t, "TestUser", sessions[0].UserName)

	pool.Close()
}

// TestGetSessions_MissingClusterID tests handling of missing cluster ID
func TestGetSessions_MissingClusterID(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewSessionService(pool, logger)

	sessions, err := svc.GetSessions(context.Background(), "", "infobase-uuid")

	assert.Error(t, err)
	assert.Nil(t, sessions)
	assert.Contains(t, err.Error(), "cluster_id is required")

	pool.Close()
}

// TestGetSessions_OptionalInfobaseID tests that infobase_id is optional
func TestGetSessions_OptionalInfobaseID(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewSessionService(pool, logger)

	sessions, err := svc.GetSessions(context.Background(), "cluster-uuid", "")

	assert.NoError(t, err)
	assert.NotNil(t, sessions)

	pool.Close()
}

// TestTerminateSessions_Success tests successful session termination
func TestTerminateSessions_Success(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewSessionService(pool, logger)

	count, err := svc.TerminateSessions(context.Background(), "cluster-uuid", "infobase-uuid")

	assert.NoError(t, err)
	assert.Equal(t, 1, count) // Mock client returns 1 session

	pool.Close()
}

// TestTerminateSessions_MissingClusterID tests handling of missing cluster ID
func TestTerminateSessions_MissingClusterID(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewSessionService(pool, logger)

	count, err := svc.TerminateSessions(context.Background(), "", "infobase-uuid")

	assert.Error(t, err)
	assert.Equal(t, 0, count)
	assert.Contains(t, err.Error(), "cluster_id and infobase_id are required")

	pool.Close()
}

// TestTerminateSessions_MissingInfobaseID tests handling of missing infobase ID
func TestTerminateSessions_MissingInfobaseID(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewSessionService(pool, logger)

	count, err := svc.TerminateSessions(context.Background(), "cluster-uuid", "")

	assert.Error(t, err)
	assert.Equal(t, 0, count)
	assert.Contains(t, err.Error(), "cluster_id and infobase_id are required")

	pool.Close()
}

// TestGetSessionsCount_Success tests successful retrieval of session count
func TestGetSessionsCount_Success(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewSessionService(pool, logger)

	count, err := svc.GetSessionsCount(context.Background(), "cluster-uuid", "infobase-uuid")

	assert.NoError(t, err)
	assert.Equal(t, 1, count) // Mock client returns 1 session

	pool.Close()
}

// TestGetSessionsCount_MissingClusterID tests handling of missing cluster ID
func TestGetSessionsCount_MissingClusterID(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewSessionService(pool, logger)

	count, err := svc.GetSessionsCount(context.Background(), "", "infobase-uuid")

	assert.Error(t, err)
	assert.Equal(t, 0, count)
	assert.Contains(t, err.Error(), "cluster_id is required")

	pool.Close()
}

// TestGetSessionsCount_OptionalInfobaseID tests that infobase_id is optional
func TestGetSessionsCount_OptionalInfobaseID(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewSessionService(pool, logger)

	count, err := svc.GetSessionsCount(context.Background(), "cluster-uuid", "")

	assert.NoError(t, err)
	assert.GreaterOrEqual(t, count, 0)

	pool.Close()
}

// TestSessionService_ConcurrentRequests tests handling of concurrent requests
func TestSessionService_ConcurrentRequests(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 20, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewSessionService(pool, logger)

	// Simulate concurrent requests
	results := make(chan error, 5)
	for i := 0; i < 5; i++ {
		go func() {
			_, err := svc.GetSessions(context.Background(), "cluster-uuid", "infobase-uuid")
			results <- err
		}()
	}

	// Verify all requests succeeded
	for i := 0; i < 5; i++ {
		err := <-results
		assert.NoError(t, err)
	}

	pool.Close()
}

// TestSessionService_ContextWithDeadline tests handling of context with deadline
func TestSessionService_ContextWithDeadline(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	svc := NewSessionService(pool, logger)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	sessions, err := svc.GetSessions(ctx, "cluster-uuid", "infobase-uuid")

	assert.NoError(t, err)
	assert.NotNil(t, sessions)

	pool.Close()
}

// BenchmarkGetSessions benchmarks GetSessions performance
func BenchmarkGetSessions(b *testing.B) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(b, err)

	svc := NewSessionService(pool, logger)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		svc.GetSessions(context.Background(), "cluster-uuid", "infobase-uuid")
	}

	pool.Close()
}

// BenchmarkTerminateSessions benchmarks TerminateSessions performance
func BenchmarkTerminateSessions(b *testing.B) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(b, err)

	svc := NewSessionService(pool, logger)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		svc.TerminateSessions(context.Background(), "cluster-uuid", "infobase-uuid")
	}

	pool.Close()
}

// BenchmarkGetSessionsCount benchmarks GetSessionsCount performance
func BenchmarkGetSessionsCount(b *testing.B) {
	logger, _ := zap.NewDevelopment()

	pool, err := ras.NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(b, err)

	svc := NewSessionService(pool, logger)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		svc.GetSessionsCount(context.Background(), "cluster-uuid", "infobase-uuid")
	}

	pool.Close()
}
