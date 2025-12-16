// Package processor provides tests for ClusterInfoWaiter.
package processor

import (
	"context"
	"testing"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/commandcenter1c/commandcenter/shared/events"
)

func getTestRedisClient(t *testing.T) *redis.Client {
	client := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
		DB:   15, // isolate tests from running services on default DB=0
	})

	ctx := context.Background()
	if err := client.Ping(ctx).Err(); err != nil {
		t.Skip("Redis not available, skipping test")
	}

	// Ensure clean slate for each test.
	_ = client.FlushDB(ctx).Err()

	return client
}

func TestNewClusterInfoWaiter(t *testing.T) {
	redisClient := getTestRedisClient(t)
	defer redisClient.Close()

	waiter := NewClusterInfoWaiter(redisClient, "")

	assert.NotNil(t, waiter)
	assert.Equal(t, events.ConsumerGroupWorkerClusterInfo, waiter.consumerGroup)
	assert.Equal(t, 0, waiter.PendingCount())
}

func TestClusterInfoWaiter_CustomConsumerGroup(t *testing.T) {
	redisClient := getTestRedisClient(t)
	defer redisClient.Close()

	waiter := NewClusterInfoWaiter(redisClient, "custom-group")

	assert.Equal(t, "custom-group", waiter.consumerGroup)
}

func TestClusterInfoWaiter_StartAndClose(t *testing.T) {
	redisClient := getTestRedisClient(t)
	defer redisClient.Close()

	waiter := NewClusterInfoWaiter(redisClient, "test-start-close-group")

	ctx := context.Background()
	err := waiter.Start(ctx)
	require.NoError(t, err)

	// Give time to start
	time.Sleep(50 * time.Millisecond)

	// Close should work cleanly
	err = waiter.Close()
	require.NoError(t, err)
}

func TestClusterInfoWaiter_DoubleCloseSafe(t *testing.T) {
	redisClient := getTestRedisClient(t)
	defer redisClient.Close()

	waiter := NewClusterInfoWaiter(redisClient, "test-double-close-group")

	ctx := context.Background()
	err := waiter.Start(ctx)
	require.NoError(t, err)

	time.Sleep(50 * time.Millisecond)

	// First close
	err = waiter.Close()
	require.NoError(t, err)

	// Second close should also succeed (idempotent)
	err = waiter.Close()
	require.NoError(t, err)
}

func TestClusterInfoWaiter_RequestTimeout(t *testing.T) {
	redisClient := getTestRedisClient(t)
	defer redisClient.Close()

	waiter := NewClusterInfoWaiter(redisClient, "test-timeout-group")

	ctx := context.Background()
	err := waiter.Start(ctx)
	require.NoError(t, err)
	defer waiter.Close()

	time.Sleep(50 * time.Millisecond)

	// Request with very short timeout - should timeout since no handler
	_, err = waiter.RequestClusterInfo(ctx, "nonexistent-db", 100*time.Millisecond)

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "timeout")
}

func TestClusterInfoWaiter_RequestAfterClose(t *testing.T) {
	redisClient := getTestRedisClient(t)
	defer redisClient.Close()

	waiter := NewClusterInfoWaiter(redisClient, "test-closed-group")

	ctx := context.Background()
	err := waiter.Start(ctx)
	require.NoError(t, err)

	time.Sleep(50 * time.Millisecond)

	// Close the waiter
	err = waiter.Close()
	require.NoError(t, err)

	// Request after close should fail
	_, err = waiter.RequestClusterInfo(ctx, "any-db", 1*time.Second)
	assert.Error(t, err)
	assert.Equal(t, ErrClusterInfoWaiterClosed, err)
}

func TestClusterInfoWaiter_StartAfterClose(t *testing.T) {
	redisClient := getTestRedisClient(t)
	defer redisClient.Close()

	waiter := NewClusterInfoWaiter(redisClient, "test-start-after-close-group")

	ctx := context.Background()
	err := waiter.Start(ctx)
	require.NoError(t, err)

	time.Sleep(50 * time.Millisecond)

	err = waiter.Close()
	require.NoError(t, err)

	// Start after close should fail
	err = waiter.Start(ctx)
	assert.Error(t, err)
	assert.Equal(t, ErrClusterInfoWaiterClosed, err)
}

func TestClusterInfoWaiter_SuccessfulRequestResponse(t *testing.T) {
	redisClient := getTestRedisClient(t)
	defer redisClient.Close()

	ctx := context.Background()

	// Clean up streams
	redisClient.Del(ctx, events.StreamCommandsGetClusterInfo)
	redisClient.Del(ctx, events.StreamEventsClusterInfoResponse)

	waiter := NewClusterInfoWaiter(redisClient, "test-success-group")

	err := waiter.Start(ctx)
	require.NoError(t, err)
	defer waiter.Close()

	time.Sleep(50 * time.Millisecond)

	// Start a goroutine to simulate Django handler
	done := make(chan struct{})
	go func() {
		defer close(done)

		// Wait for the request
		for i := 0; i < 20; i++ {
			result, err := redisClient.XRange(ctx, events.StreamCommandsGetClusterInfo, "-", "+").Result()
			if err == nil && len(result) > 0 {
				// Found the request, extract correlation_id
				msg := result[0]
				correlationID := msg.Values["correlation_id"].(string)
				databaseID := msg.Values["database_id"].(string)

				// Publish response
				response := map[string]interface{}{
					"correlation_id":   correlationID,
					"database_id":      databaseID,
					"cluster_id":       "test-cluster-uuid",
					"ras_server":       "localhost:1545",
					"ras_cluster_uuid": "test-ras-cluster-uuid",
					"infobase_id":      "test-infobase-uuid",
					"success":          "true",
					"error":            "",
				}
				redisClient.XAdd(ctx, &redis.XAddArgs{
					Stream: events.StreamEventsClusterInfoResponse,
					Values: response,
				})
				return
			}
			time.Sleep(50 * time.Millisecond)
		}
	}()

	// Make request
	info, err := waiter.RequestClusterInfo(ctx, "test-db-123", 5*time.Second)

	// Wait for handler goroutine
	<-done

	require.NoError(t, err)
	require.NotNil(t, info)
	assert.Equal(t, "test-db-123", info.DatabaseID)
	assert.Equal(t, "test-ras-cluster-uuid", info.ClusterID) // Uses RASClusterUUID
	assert.Equal(t, "test-infobase-uuid", info.InfobaseID)
}

func TestClusterInfoWaiter_ErrorResponse(t *testing.T) {
	redisClient := getTestRedisClient(t)
	defer redisClient.Close()

	ctx := context.Background()

	// Clean up streams
	redisClient.Del(ctx, events.StreamCommandsGetClusterInfo)
	redisClient.Del(ctx, events.StreamEventsClusterInfoResponse)

	waiter := NewClusterInfoWaiter(redisClient, "test-error-group")

	err := waiter.Start(ctx)
	require.NoError(t, err)
	defer waiter.Close()

	time.Sleep(50 * time.Millisecond)

	// Start a goroutine to simulate Django handler returning error
	done := make(chan struct{})
	go func() {
		defer close(done)

		for i := 0; i < 20; i++ {
			result, err := redisClient.XRange(ctx, events.StreamCommandsGetClusterInfo, "-", "+").Result()
			if err == nil && len(result) > 0 {
				msg := result[0]
				correlationID := msg.Values["correlation_id"].(string)
				databaseID := msg.Values["database_id"].(string)

				// Publish error response
				response := map[string]interface{}{
					"correlation_id":   correlationID,
					"database_id":      databaseID,
					"cluster_id":       "",
					"ras_server":       "",
					"ras_cluster_uuid": "",
					"infobase_id":      "",
					"success":          "false",
					"error":            "Database not found",
				}
				redisClient.XAdd(ctx, &redis.XAddArgs{
					Stream: events.StreamEventsClusterInfoResponse,
					Values: response,
				})
				return
			}
			time.Sleep(50 * time.Millisecond)
		}
	}()

	// Make request
	info, err := waiter.RequestClusterInfo(ctx, "nonexistent-db", 5*time.Second)

	// Wait for handler goroutine
	<-done

	assert.Nil(t, info)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "Database not found")
}

func TestClusterInfoWaiter_PendingCount(t *testing.T) {
	redisClient := getTestRedisClient(t)
	defer redisClient.Close()

	waiter := NewClusterInfoWaiter(redisClient, "test-pending-group")

	ctx := context.Background()
	err := waiter.Start(ctx)
	require.NoError(t, err)
	defer waiter.Close()

	time.Sleep(50 * time.Millisecond)

	// Initial count should be 0
	assert.Equal(t, 0, waiter.PendingCount())

	// Start a request in background (will timeout)
	go func() {
		waiter.RequestClusterInfo(ctx, "pending-db", 500*time.Millisecond)
	}()

	// Wait a bit for request to register
	time.Sleep(50 * time.Millisecond)

	// Should have 1 pending
	assert.Equal(t, 1, waiter.PendingCount())

	// Wait for timeout
	time.Sleep(500 * time.Millisecond)

	// Should be back to 0
	assert.Equal(t, 0, waiter.PendingCount())
}

func TestClusterInfoRequest_Fields(t *testing.T) {
	req := ClusterInfoRequest{
		CorrelationID: "corr-123",
		DatabaseID:    "db-456",
		OperationID:   "op-789",
		Timestamp:     "2025-12-15T10:30:00Z",
	}

	assert.Equal(t, "corr-123", req.CorrelationID)
	assert.Equal(t, "db-456", req.DatabaseID)
	assert.Equal(t, "op-789", req.OperationID)
	assert.Equal(t, "2025-12-15T10:30:00Z", req.Timestamp)
}

func TestClusterInfoResponse_Fields(t *testing.T) {
	resp := ClusterInfoResponse{
		CorrelationID:  "corr-123",
		DatabaseID:     "db-456",
		ClusterID:      "cluster-uuid",
		RASServer:      "localhost:1545",
		RASClusterUUID: "ras-cluster-uuid",
		InfobaseID:     "infobase-uuid",
		Success:        true,
		Error:          "",
	}

	assert.Equal(t, "corr-123", resp.CorrelationID)
	assert.Equal(t, "db-456", resp.DatabaseID)
	assert.Equal(t, "cluster-uuid", resp.ClusterID)
	assert.Equal(t, "localhost:1545", resp.RASServer)
	assert.Equal(t, "ras-cluster-uuid", resp.RASClusterUUID)
	assert.Equal(t, "infobase-uuid", resp.InfobaseID)
	assert.True(t, resp.Success)
	assert.Empty(t, resp.Error)
}

func TestClusterInfoWaiterErrors(t *testing.T) {
	assert.Error(t, ErrClusterInfoTimeout)
	assert.Error(t, ErrClusterInfoWaiterClosed)
	assert.Error(t, ErrClusterInfoDuplicateCorrelationID)
	assert.Error(t, ErrClusterInfoNotFound)

	assert.Contains(t, ErrClusterInfoTimeout.Error(), "timeout")
	assert.Contains(t, ErrClusterInfoWaiterClosed.Error(), "closed")
	assert.Contains(t, ErrClusterInfoDuplicateCorrelationID.Error(), "duplicate")
	assert.Contains(t, ErrClusterInfoNotFound.Error(), "not found")
}
