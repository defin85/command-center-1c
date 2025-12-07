package jobs

import (
	"context"
	"encoding/json"
	"errors"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
)

// MockEventReplayClient is a mock implementation of orchestrator.EventReplayClient
type MockEventReplayClient struct {
	mock.Mock
}

func (m *MockEventReplayClient) GetPendingFailedEvents(ctx context.Context, batchSize int) ([]orchestrator.FailedEvent, error) {
	args := m.Called(ctx, batchSize)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]orchestrator.FailedEvent), args.Error(1)
}

func (m *MockEventReplayClient) MarkEventReplayed(ctx context.Context, eventID int) error {
	args := m.Called(ctx, eventID)
	return args.Error(0)
}

func (m *MockEventReplayClient) MarkEventReplayedAt(ctx context.Context, eventID int, replayedAt *time.Time) error {
	args := m.Called(ctx, eventID, replayedAt)
	return args.Error(0)
}

func (m *MockEventReplayClient) MarkEventFailed(ctx context.Context, eventID int, errorMessage string) (*orchestrator.FailedEventFailedResponse, error) {
	args := m.Called(ctx, eventID, errorMessage)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*orchestrator.FailedEventFailedResponse), args.Error(1)
}

func (m *MockEventReplayClient) MarkEventFailedWithOptions(ctx context.Context, eventID int, errorMessage string, incrementRetry bool) (*orchestrator.FailedEventFailedResponse, error) {
	args := m.Called(ctx, eventID, errorMessage, incrementRetry)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*orchestrator.FailedEventFailedResponse), args.Error(1)
}

func (m *MockEventReplayClient) CleanupOldEvents(ctx context.Context, retentionDays int) (int, error) {
	args := m.Called(ctx, retentionDays)
	return args.Int(0), args.Error(1)
}

// Verify MockEventReplayClient implements EventReplayClient
var _ orchestrator.EventReplayClient = (*MockEventReplayClient)(nil)

func setupTestRedis(t *testing.T) (*miniredis.Miniredis, redis.Cmdable) {
	mr, err := miniredis.Run()
	require.NoError(t, err)
	t.Cleanup(func() {
		mr.Close()
	})

	client := redis.NewClient(&redis.Options{
		Addr: mr.Addr(),
	})
	t.Cleanup(func() {
		client.Close()
	})

	return mr, client
}

func testLogger() *zap.Logger {
	logger, _ := zap.NewDevelopment()
	return logger
}

func TestEventReplayJob_Name(t *testing.T) {
	mockClient := new(MockEventReplayClient)
	_, redisClient := setupTestRedis(t)
	logger := testLogger()

	job := NewEventReplayJob(mockClient, redisClient, logger, 100)

	assert.Equal(t, EventReplayJobName, job.Name())
	assert.Equal(t, "replay_failed_events", job.Name())
}

func TestEventReplayJob_Execute_EmptyEvents(t *testing.T) {
	mockClient := new(MockEventReplayClient)
	_, redisClient := setupTestRedis(t)
	logger := testLogger()

	job := NewEventReplayJob(mockClient, redisClient, logger, 100)

	// Setup mock to return empty list
	mockClient.On("GetPendingFailedEvents", mock.Anything, 100).Return([]orchestrator.FailedEvent{}, nil)

	// Execute
	err := job.Execute(context.Background())

	// Assert
	assert.NoError(t, err)
	mockClient.AssertExpectations(t)
}

func TestEventReplayJob_Execute_SuccessfulReplay(t *testing.T) {
	mockClient := new(MockEventReplayClient)
	mr, redisClient := setupTestRedis(t)
	logger := testLogger()

	job := NewEventReplayJob(mockClient, redisClient, logger, 100)

	// Create test event
	testEvent := orchestrator.FailedEvent{
		ID:                1,
		Channel:           "test:events:stream",
		EventType:         "database.health.changed",
		CorrelationID:     "corr-123",
		Payload:           map[string]interface{}{"database_id": "db-1", "healthy": true},
		SourceService:     "orchestrator",
		OriginalTimestamp: time.Now().Add(-1 * time.Hour),
		Status:            "pending",
		RetryCount:        1,
		MaxRetries:        3,
	}

	// Setup mocks
	mockClient.On("GetPendingFailedEvents", mock.Anything, 100).Return([]orchestrator.FailedEvent{testEvent}, nil)
	mockClient.On("MarkEventReplayedAt", mock.Anything, 1, mock.AnythingOfType("*time.Time")).Return(nil)

	// Execute
	err := job.Execute(context.Background())

	// Assert no error
	assert.NoError(t, err)
	mockClient.AssertExpectations(t)

	// Verify Redis stream received the message
	result, err := redisClient.XRange(context.Background(), "test:events:stream", "-", "+").Result()
	require.NoError(t, err)
	assert.Len(t, result, 1)

	// Verify payload structure
	payloadStr, ok := result[0].Values["payload"].(string)
	require.True(t, ok, "payload should be a string")

	var envelope map[string]interface{}
	err = json.Unmarshal([]byte(payloadStr), &envelope)
	require.NoError(t, err)

	assert.Equal(t, "1.0", envelope["version"])
	assert.Equal(t, "database.health.changed", envelope["event_type"])
	assert.Equal(t, "corr-123", envelope["correlation_id"])
	assert.Equal(t, "orchestrator", envelope["source_service"])

	// Verify metadata
	metadata, ok := envelope["metadata"].(map[string]interface{})
	require.True(t, ok)
	assert.Equal(t, true, metadata["replayed"])
	assert.Equal(t, float64(2), metadata["replay_count"]) // RetryCount + 1

	// Close miniredis to cleanup
	mr.Close()
}

func TestEventReplayJob_Execute_RedisUnavailable(t *testing.T) {
	mockClient := new(MockEventReplayClient)
	logger := testLogger()

	// Create redis client pointing to non-existent server
	redisClient := redis.NewClient(&redis.Options{
		Addr: "localhost:59999", // Non-existent
	})
	defer redisClient.Close()

	job := NewEventReplayJob(mockClient, redisClient, logger, 100)

	// Execute
	err := job.Execute(context.Background())

	// Assert error about Redis
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "redis unavailable")
}

func TestEventReplayJob_Execute_OrchestratorError(t *testing.T) {
	mockClient := new(MockEventReplayClient)
	_, redisClient := setupTestRedis(t)
	logger := testLogger()

	job := NewEventReplayJob(mockClient, redisClient, logger, 100)

	// Setup mock to return error
	mockClient.On("GetPendingFailedEvents", mock.Anything, 100).Return(nil, errors.New("orchestrator unavailable"))

	// Execute
	err := job.Execute(context.Background())

	// Assert error
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to get pending failed events")
	mockClient.AssertExpectations(t)
}

func TestEventReplayJob_Execute_PartialSuccess(t *testing.T) {
	mockClient := new(MockEventReplayClient)
	mr, redisClient := setupTestRedis(t)
	logger := testLogger()

	job := NewEventReplayJob(mockClient, redisClient, logger, 100)

	// Create test events
	event1 := orchestrator.FailedEvent{
		ID:                1,
		Channel:           "test:events:stream1",
		EventType:         "event.type.1",
		CorrelationID:     "corr-1",
		Payload:           map[string]interface{}{"key": "value1"},
		SourceService:     "service1",
		OriginalTimestamp: time.Now(),
		Status:            "pending",
		RetryCount:        0,
	}
	event2 := orchestrator.FailedEvent{
		ID:                2,
		Channel:           "test:events:stream2",
		EventType:         "event.type.2",
		CorrelationID:     "corr-2",
		Payload:           map[string]interface{}{"key": "value2"},
		SourceService:     "service2",
		OriginalTimestamp: time.Now(),
		Status:            "pending",
		RetryCount:        0,
	}

	// Setup mocks
	mockClient.On("GetPendingFailedEvents", mock.Anything, 100).Return([]orchestrator.FailedEvent{event1, event2}, nil)
	// Event 1 succeeds
	mockClient.On("MarkEventReplayedAt", mock.Anything, 1, mock.AnythingOfType("*time.Time")).Return(nil)
	// Event 2's MarkEventReplayedAt fails (but the event was still published to Redis)
	mockClient.On("MarkEventReplayedAt", mock.Anything, 2, mock.AnythingOfType("*time.Time")).Return(errors.New("orchestrator error"))

	// Execute
	err := job.Execute(context.Background())

	// Should not return error - partial success is acceptable
	assert.NoError(t, err)
	mockClient.AssertExpectations(t)

	// Both events should be in Redis streams
	result1, err := redisClient.XRange(context.Background(), "test:events:stream1", "-", "+").Result()
	require.NoError(t, err)
	assert.Len(t, result1, 1)

	result2, err := redisClient.XRange(context.Background(), "test:events:stream2", "-", "+").Result()
	require.NoError(t, err)
	assert.Len(t, result2, 1)

	mr.Close()
}

func TestEventReplayJob_Execute_RedisXAddFailure(t *testing.T) {
	// This test verifies that when Redis XADD fails (after PING succeeds),
	// the job marks the event as failed and continues.
	// We use a special payload that causes JSON marshal to fail to simulate
	// an XADD failure scenario.
	mockClient := new(MockEventReplayClient)
	mr, redisClient := setupTestRedis(t)
	logger := testLogger()

	job := NewEventReplayJob(mockClient, redisClient, logger, 100)

	// Create event with payload that will marshal fine but close redis after PING
	testEvent := orchestrator.FailedEvent{
		ID:                1,
		Channel:           "test:stream",
		EventType:         "test.event",
		CorrelationID:     "corr-1",
		Payload:           map[string]interface{}{"key": "value"},
		SourceService:     "test-service",
		OriginalTimestamp: time.Now(),
		Status:            "pending",
		RetryCount:        0,
	}

	// Setup mocks - return events
	mockClient.On("GetPendingFailedEvents", mock.Anything, 100).Return([]orchestrator.FailedEvent{testEvent}, nil).Run(func(args mock.Arguments) {
		// Close miniredis AFTER PING succeeds but BEFORE XADD
		// This simulates Redis becoming unavailable during processing
		mr.Close()
	})

	// MarkEventFailed should be called when Redis XADD fails
	mockClient.On("MarkEventFailed", mock.Anything, 1, mock.MatchedBy(func(msg string) bool {
		return len(msg) > 0 // Any non-empty error message
	})).Return(&orchestrator.FailedEventFailedResponse{
		Success:    true,
		NewStatus:  "pending",
		RetryCount: 1,
	}, nil)

	// Execute
	err := job.Execute(context.Background())

	// Should not return error - individual event failures are handled gracefully
	assert.NoError(t, err)
	mockClient.AssertExpectations(t)
}

func TestEventReplayJob_BuildEnvelope(t *testing.T) {
	mockClient := new(MockEventReplayClient)
	_, redisClient := setupTestRedis(t)
	logger := testLogger()

	job := NewEventReplayJob(mockClient, redisClient, logger, 100)

	originalTimestamp := time.Date(2025, 1, 15, 10, 30, 0, 0, time.UTC)
	testEvent := orchestrator.FailedEvent{
		ID:                42,
		Channel:           "events:stream",
		EventType:         "database.updated",
		CorrelationID:     "correlation-abc-123",
		Payload:           map[string]interface{}{"database_id": "db-123", "name": "Test DB"},
		SourceService:     "orchestrator",
		OriginalTimestamp: originalTimestamp,
		Status:            "pending",
		RetryCount:        2,
		MaxRetries:        5,
	}

	envelope := job.buildEnvelope(testEvent)

	// Verify envelope structure
	assert.Equal(t, "1.0", envelope["version"])
	assert.Equal(t, "database.updated", envelope["event_type"])
	assert.Equal(t, "correlation-abc-123", envelope["correlation_id"])
	assert.Equal(t, "orchestrator", envelope["source_service"])
	assert.Equal(t, originalTimestamp.Format(time.RFC3339), envelope["timestamp"])

	// Verify message_id format
	messageID, ok := envelope["message_id"].(string)
	require.True(t, ok)
	assert.Contains(t, messageID, "replay-42-")

	// Verify payload
	payload, ok := envelope["payload"].(map[string]interface{})
	require.True(t, ok)
	assert.Equal(t, "db-123", payload["database_id"])
	assert.Equal(t, "Test DB", payload["name"])

	// Verify metadata
	metadata, ok := envelope["metadata"].(map[string]interface{})
	require.True(t, ok)
	assert.Equal(t, true, metadata["replayed"])
	assert.Equal(t, 3, metadata["replay_count"]) // RetryCount + 1 = 2 + 1 = 3
	assert.Equal(t, originalTimestamp.Format(time.RFC3339), metadata["original_created_at"])
}

func TestNewEventReplayJob_BatchSizeLimits(t *testing.T) {
	mockClient := new(MockEventReplayClient)
	_, redisClient := setupTestRedis(t)
	logger := testLogger()

	tests := []struct {
		name          string
		inputBatch    int
		expectedBatch int
	}{
		{"zero becomes default", 0, 100},
		{"negative becomes default", -5, 100},
		{"normal value", 50, 50},
		{"max value", 1000, 1000},
		{"over max becomes max", 1500, 1000},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			job := NewEventReplayJob(mockClient, redisClient, logger, tt.inputBatch)
			assert.Equal(t, tt.expectedBatch, job.batchSize)
		})
	}
}

func TestStubEventReplayClient(t *testing.T) {
	logger := testLogger()
	stub := NewStubEventReplayClient(logger)

	ctx := context.Background()

	// Test all methods return expected stub values
	events, err := stub.GetPendingFailedEvents(ctx, 100)
	assert.NoError(t, err)
	assert.Empty(t, events)

	err = stub.MarkEventReplayed(ctx, 1)
	assert.NoError(t, err)

	err = stub.MarkEventReplayedAt(ctx, 1, nil)
	assert.NoError(t, err)

	resp, err := stub.MarkEventFailed(ctx, 1, "test error")
	assert.NoError(t, err)
	assert.True(t, resp.Success)
	assert.Equal(t, "pending", resp.NewStatus)

	resp, err = stub.MarkEventFailedWithOptions(ctx, 1, "test error", true)
	assert.NoError(t, err)
	assert.True(t, resp.Success)

	count, err := stub.CleanupOldEvents(ctx, 7)
	assert.NoError(t, err)
	assert.Equal(t, 0, count)
}

func TestEventReplayJob_Execute_MultipleEventsSuccess(t *testing.T) {
	mockClient := new(MockEventReplayClient)
	mr, redisClient := setupTestRedis(t)
	logger := testLogger()

	job := NewEventReplayJob(mockClient, redisClient, logger, 100)

	// Create multiple test events
	events := []orchestrator.FailedEvent{
		{
			ID:                1,
			Channel:           "stream:a",
			EventType:         "type.a",
			CorrelationID:     "corr-a",
			Payload:           map[string]interface{}{"id": 1},
			SourceService:     "service-a",
			OriginalTimestamp: time.Now(),
			RetryCount:        0,
		},
		{
			ID:                2,
			Channel:           "stream:b",
			EventType:         "type.b",
			CorrelationID:     "corr-b",
			Payload:           map[string]interface{}{"id": 2},
			SourceService:     "service-b",
			OriginalTimestamp: time.Now(),
			RetryCount:        1,
		},
		{
			ID:                3,
			Channel:           "stream:c",
			EventType:         "type.c",
			CorrelationID:     "corr-c",
			Payload:           map[string]interface{}{"id": 3},
			SourceService:     "service-c",
			OriginalTimestamp: time.Now(),
			RetryCount:        2,
		},
	}

	// Setup mocks
	mockClient.On("GetPendingFailedEvents", mock.Anything, 100).Return(events, nil)
	for _, event := range events {
		mockClient.On("MarkEventReplayedAt", mock.Anything, event.ID, mock.AnythingOfType("*time.Time")).Return(nil)
	}

	// Execute
	err := job.Execute(context.Background())
	assert.NoError(t, err)

	// Verify all streams received messages
	for _, event := range events {
		result, err := redisClient.XRange(context.Background(), event.Channel, "-", "+").Result()
		require.NoError(t, err)
		assert.Len(t, result, 1, "stream %s should have 1 message", event.Channel)
	}

	mockClient.AssertExpectations(t)
	mr.Close()
}
