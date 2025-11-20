package eventhandlers

import (
	"context"
	"encoding/json"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"go.uber.org/zap"
)

// MockInfobaseManager is a mock for InfobaseManager interface
type MockInfobaseManager struct {
	mock.Mock
}

func (m *MockInfobaseManager) LockInfobase(ctx context.Context, clusterID, infobaseID string) error {
	args := m.Called(ctx, clusterID, infobaseID)
	return args.Error(0)
}

func (m *MockInfobaseManager) UnlockInfobase(ctx context.Context, clusterID, infobaseID string) error {
	args := m.Called(ctx, clusterID, infobaseID)
	return args.Error(0)
}

func (m *MockInfobaseManager) TerminateSessions(ctx context.Context, clusterID, infobaseID string) (int, error) {
	args := m.Called(ctx, clusterID, infobaseID)
	return args.Int(0), args.Error(1)
}

func (m *MockInfobaseManager) GetSessionsCount(ctx context.Context, clusterID, infobaseID string) (int, error) {
	args := m.Called(ctx, clusterID, infobaseID)
	return args.Int(0), args.Error(1)
}

// MockEventPublisher is a mock for EventPublisher interface
type MockEventPublisher struct {
	mock.Mock
	PublishedEvents []PublishedEvent
}

type PublishedEvent struct {
	Channel       string
	EventType     string
	Payload       interface{}
	CorrelationID string
}

func (m *MockEventPublisher) Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error {
	// Store published event for assertions
	m.PublishedEvents = append(m.PublishedEvents, PublishedEvent{
		Channel:       channel,
		EventType:     eventType,
		Payload:       payload,
		CorrelationID: correlationID,
	})

	args := m.Called(ctx, channel, eventType, payload, correlationID)
	return args.Error(0)
}

func (m *MockEventPublisher) Close() error {
	args := m.Called()
	return args.Error(0)
}

// MockRedisClient is a mock for RedisClient interface
type MockRedisClient struct {
	mock.Mock
}

func (m *MockRedisClient) SetNX(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.BoolCmd {
	args := m.Called(ctx, key, value, expiration)
	return args.Get(0).(*redis.BoolCmd)
}

// Helper function to create test envelope
func createTestEnvelope(t *testing.T, eventType string, payload interface{}, correlationID string) *events.Envelope {
	envelope, err := events.NewEnvelope(eventType, "test-service", payload, correlationID)
	assert.NoError(t, err)
	return envelope
}

// TestLockHandler_HandleLockCommand_Success tests successful lock command handling
func TestLockHandler_HandleLockCommand_Success(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewLockHandler(mockService, mockPublisher, nil, logger) // nil redisClient disables idempotency

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := LockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
		DatabaseID: "db-789",
	}
	envelope := createTestEnvelope(t, "lock.command", payload, correlationID)

	// Mock expectations
	mockService.On("LockInfobase", ctx, "cluster-123", "infobase-456").Return(nil)
	mockPublisher.On("Publish", ctx, LockedEventChannel, InfobaseLockedEvent, mock.Anything, correlationID).Return(nil)

	// Act
	err := handler.HandleLockCommand(ctx, envelope)

	// Assert
	assert.NoError(t, err)
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)

	// Verify published event
	assert.Len(t, mockPublisher.PublishedEvents, 1)
	publishedEvent := mockPublisher.PublishedEvents[0]
	assert.Equal(t, LockedEventChannel, publishedEvent.Channel)
	assert.Equal(t, InfobaseLockedEvent, publishedEvent.EventType)
	assert.Equal(t, correlationID, publishedEvent.CorrelationID)
}

// TestLockHandler_HandleLockCommand_ServiceError tests error handling when service fails
func TestLockHandler_HandleLockCommand_ServiceError(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewLockHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := LockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
	}
	envelope := createTestEnvelope(t, "lock.command", payload, correlationID)

	serviceErr := errors.New("failed to lock infobase")

	// Mock expectations
	mockService.On("LockInfobase", ctx, "cluster-123", "infobase-456").Return(serviceErr)
	mockPublisher.On("Publish", ctx, LockFailedChannel, InfobaseLockFailedEvent, mock.Anything, correlationID).Return(nil)

	// Act
	err := handler.HandleLockCommand(ctx, envelope)

	// Assert
	assert.Error(t, err)
	assert.Equal(t, serviceErr, err)
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)

	// Verify error event was published
	assert.Len(t, mockPublisher.PublishedEvents, 1)
	publishedEvent := mockPublisher.PublishedEvents[0]
	assert.Equal(t, LockFailedChannel, publishedEvent.Channel)
	assert.Equal(t, InfobaseLockFailedEvent, publishedEvent.EventType)
}

// TestLockHandler_HandleLockCommand_InvalidPayload tests invalid payload handling
func TestLockHandler_HandleLockCommand_InvalidPayload(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewLockHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"

	// Create envelope with invalid JSON
	envelope := &events.Envelope{
		MessageID:     "msg-123",
		CorrelationID: correlationID,
		EventType:     "lock.command",
		ServiceName:   "test-service",
		Timestamp:     time.Now(),
		Payload:       json.RawMessage(`{"invalid": json`), // Invalid JSON
	}

	mockPublisher.On("Publish", ctx, LockFailedChannel, InfobaseLockFailedEvent, mock.Anything, correlationID).Return(nil)

	// Act
	err := handler.HandleLockCommand(ctx, envelope)

	// Assert
	assert.Error(t, err)
	mockPublisher.AssertExpectations(t)
}

// TestUnlockHandler_HandleUnlockCommand_Success tests successful unlock command handling
func TestUnlockHandler_HandleUnlockCommand_Success(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewUnlockHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := UnlockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
		DatabaseID: "db-789",
	}
	envelope := createTestEnvelope(t, "unlock.command", payload, correlationID)

	// Mock expectations
	mockService.On("UnlockInfobase", ctx, "cluster-123", "infobase-456").Return(nil)
	mockPublisher.On("Publish", ctx, UnlockedEventChannel, InfobaseUnlockedEvent, mock.Anything, correlationID).Return(nil)

	// Act
	err := handler.HandleUnlockCommand(ctx, envelope)

	// Assert
	assert.NoError(t, err)
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)

	// Verify published event
	assert.Len(t, mockPublisher.PublishedEvents, 1)
	publishedEvent := mockPublisher.PublishedEvents[0]
	assert.Equal(t, UnlockedEventChannel, publishedEvent.Channel)
	assert.Equal(t, InfobaseUnlockedEvent, publishedEvent.EventType)
	assert.Equal(t, correlationID, publishedEvent.CorrelationID)
}

// TestTerminateHandler_HandleTerminateCommand_Success tests successful terminate command handling
func TestTerminateHandler_HandleTerminateCommand_Success(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewTerminateHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := TerminateCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
		DatabaseID: "db-789",
	}
	envelope := createTestEnvelope(t, "terminate.command", payload, correlationID)

	// Mock expectations
	mockService.On("GetSessionsCount", ctx, "cluster-123", "infobase-456").Return(5, nil)
	mockService.On("TerminateSessions", ctx, "cluster-123", "infobase-456").Return(5, nil)

	// Act
	err := handler.HandleTerminateCommand(ctx, envelope)

	// Assert
	assert.NoError(t, err)
	mockService.AssertExpectations(t)

	// Note: We don't test the monitoring goroutine here (it runs in background)
	// That would require integration tests with Redis
}

// TestTerminateHandler_HandleTerminateCommand_ServiceError tests error handling when terminate fails
func TestTerminateHandler_HandleTerminateCommand_ServiceError(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewTerminateHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := TerminateCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
	}
	envelope := createTestEnvelope(t, "terminate.command", payload, correlationID)

	serviceErr := errors.New("failed to terminate sessions")

	// Mock expectations
	mockService.On("GetSessionsCount", ctx, "cluster-123", "infobase-456").Return(5, nil)
	mockService.On("TerminateSessions", ctx, "cluster-123", "infobase-456").Return(0, serviceErr)
	mockPublisher.On("Publish", ctx, TerminateFailedChannel, SessionsTerminateFailedEvent, mock.Anything, correlationID).Return(nil)

	// Act
	err := handler.HandleTerminateCommand(ctx, envelope)

	// Assert
	assert.Error(t, err)
	assert.Equal(t, serviceErr, err)
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)

	// Verify error event was published
	assert.Len(t, mockPublisher.PublishedEvents, 1)
	publishedEvent := mockPublisher.PublishedEvents[0]
	assert.Equal(t, TerminateFailedChannel, publishedEvent.Channel)
	assert.Equal(t, SessionsTerminateFailedEvent, publishedEvent.EventType)
}

// TestTerminateHandler_HandleTerminateCommand_MissingFields tests validation
func TestTerminateHandler_HandleTerminateCommand_MissingFields(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewTerminateHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"

	// Payload with missing cluster_id
	payload := TerminateCommandPayload{
		ClusterID:  "",
		InfobaseID: "infobase-456",
	}
	envelope := createTestEnvelope(t, "terminate.command", payload, correlationID)

	mockPublisher.On("Publish", ctx, TerminateFailedChannel, SessionsTerminateFailedEvent, mock.Anything, correlationID).Return(nil)

	// Act
	err := handler.HandleTerminateCommand(ctx, envelope)

	// Assert
	assert.Error(t, err)
	mockPublisher.AssertExpectations(t)

	// Verify error event was published
	assert.Len(t, mockPublisher.PublishedEvents, 1)
}

// TestLockHandler_PublishSuccessFails tests error when publishing success event fails
func TestLockHandler_PublishSuccessFails(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewLockHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := LockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
	}
	envelope := createTestEnvelope(t, "lock.command", payload, correlationID)

	publishErr := errors.New("failed to publish event")

	// Mock expectations
	mockService.On("LockInfobase", ctx, "cluster-123", "infobase-456").Return(nil)
	mockPublisher.On("Publish", ctx, LockedEventChannel, InfobaseLockedEvent, mock.Anything, correlationID).Return(publishErr)

	// Act
	err := handler.HandleLockCommand(ctx, envelope)

	// Assert
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to publish success event")
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)
}

// TestUnlockHandler_ServiceError tests error handling when unlock service fails
func TestUnlockHandler_ServiceError(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewUnlockHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := UnlockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
	}
	envelope := createTestEnvelope(t, "unlock.command", payload, correlationID)

	serviceErr := errors.New("failed to unlock infobase")

	// Mock expectations
	mockService.On("UnlockInfobase", ctx, "cluster-123", "infobase-456").Return(serviceErr)
	mockPublisher.On("Publish", ctx, UnlockFailedChannel, InfobaseUnlockFailedEvent, mock.Anything, correlationID).Return(nil)

	// Act
	err := handler.HandleUnlockCommand(ctx, envelope)

	// Assert
	assert.Error(t, err)
	assert.Equal(t, serviceErr, err)
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)

	// Verify error event was published
	assert.Len(t, mockPublisher.PublishedEvents, 1)
	publishedEvent := mockPublisher.PublishedEvents[0]
	assert.Equal(t, UnlockFailedChannel, publishedEvent.Channel)
	assert.Equal(t, InfobaseUnlockFailedEvent, publishedEvent.EventType)
}

// TestTerminateHandler_GetSessionsCountError tests error when getting initial sessions count
func TestTerminateHandler_GetSessionsCountError(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewTerminateHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := TerminateCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
	}
	envelope := createTestEnvelope(t, "terminate.command", payload, correlationID)

	serviceErr := errors.New("failed to get sessions count")

	// Mock expectations
	mockService.On("GetSessionsCount", ctx, "cluster-123", "infobase-456").Return(0, serviceErr)
	mockPublisher.On("Publish", ctx, TerminateFailedChannel, SessionsTerminateFailedEvent, mock.Anything, correlationID).Return(nil)

	// Act
	err := handler.HandleTerminateCommand(ctx, envelope)

	// Assert
	assert.Error(t, err)
	assert.Equal(t, serviceErr, err)
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)
}

// BenchmarkLockHandler_HandleLockCommand benchmarks lock command handling
func BenchmarkLockHandler_HandleLockCommand(b *testing.B) {
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewLockHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	payload := LockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
	}
	envelope := createTestEnvelope(&testing.T{}, "lock.command", payload, "correlation-id")

	mockService.On("LockInfobase", mock.Anything, mock.Anything, mock.Anything).Return(nil)
	mockPublisher.On("Publish", mock.Anything, mock.Anything, mock.Anything, mock.Anything, mock.Anything).Return(nil)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		handler.HandleLockCommand(ctx, envelope)
	}
}

// ============================================================
// IDEMPOTENCY TESTS
// ============================================================

// TestLockHandler_Idempotent tests duplicate lock command is skipped
func TestLockHandler_Idempotent(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()
	handler := NewLockHandler(mockService, mockPublisher, mockRedis, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := LockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
		DatabaseID: "db-789",
	}
	envelope := createTestEnvelope(t, "lock.command", payload, correlationID)

	// First call: SetNX returns true (key didn't exist)
	mockRedis.On("SetNX",
		mock.Anything,
		"dedupe:test-correlation-id:lock",
		"1",
		10*time.Minute,
	).Return(redis.NewBoolResult(true, nil)).Once()

	mockService.On("LockInfobase",
		mock.Anything,
		"cluster-123",
		"infobase-456",
	).Return(nil).Once()

	mockPublisher.On("Publish",
		mock.Anything,
		LockedEventChannel,
		InfobaseLockedEvent,
		mock.Anything,
		correlationID,
	).Return(nil).Once()

	// First call should execute
	err := handler.HandleLockCommand(ctx, envelope)
	assert.NoError(t, err)
	mockService.AssertExpectations(t)

	// Second call: SetNX returns false (key exists)
	mockRedis.On("SetNX",
		mock.Anything,
		"dedupe:test-correlation-id:lock",
		"1",
		10*time.Minute,
	).Return(redis.NewBoolResult(false, nil)).Once()

	// Publisher should still be called (idempotent success response)
	mockPublisher.On("Publish",
		mock.Anything,
		LockedEventChannel,
		InfobaseLockedEvent,
		mock.Anything,
		correlationID,
	).Return(nil).Once()

	// Second call should skip operation but publish success
	err = handler.HandleLockCommand(ctx, envelope)
	assert.NoError(t, err)

	// Service should NOT be called second time
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)
	mockRedis.AssertExpectations(t)
}

// TestUnlockHandler_Idempotent tests duplicate unlock command is skipped
func TestUnlockHandler_Idempotent(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()
	handler := NewUnlockHandler(mockService, mockPublisher, mockRedis, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := UnlockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
		DatabaseID: "db-789",
	}
	envelope := createTestEnvelope(t, "unlock.command", payload, correlationID)

	// First call: SetNX returns true (key didn't exist)
	mockRedis.On("SetNX",
		mock.Anything,
		"dedupe:test-correlation-id:unlock",
		"1",
		10*time.Minute,
	).Return(redis.NewBoolResult(true, nil)).Once()

	mockService.On("UnlockInfobase",
		mock.Anything,
		"cluster-123",
		"infobase-456",
	).Return(nil).Once()

	mockPublisher.On("Publish",
		mock.Anything,
		UnlockedEventChannel,
		InfobaseUnlockedEvent,
		mock.Anything,
		correlationID,
	).Return(nil).Once()

	// First call should execute
	err := handler.HandleUnlockCommand(ctx, envelope)
	assert.NoError(t, err)
	mockService.AssertExpectations(t)

	// Second call: SetNX returns false (key exists)
	mockRedis.On("SetNX",
		mock.Anything,
		"dedupe:test-correlation-id:unlock",
		"1",
		10*time.Minute,
	).Return(redis.NewBoolResult(false, nil)).Once()

	// Publisher should still be called (idempotent success response)
	mockPublisher.On("Publish",
		mock.Anything,
		UnlockedEventChannel,
		InfobaseUnlockedEvent,
		mock.Anything,
		correlationID,
	).Return(nil).Once()

	// Second call should skip operation but publish success
	err = handler.HandleUnlockCommand(ctx, envelope)
	assert.NoError(t, err)

	// Service should NOT be called second time
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)
	mockRedis.AssertExpectations(t)
}

// TestTerminateHandler_Idempotent tests duplicate terminate command is skipped
func TestTerminateHandler_Idempotent(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()
	handler := NewTerminateHandler(mockService, mockPublisher, mockRedis, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := TerminateCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
		DatabaseID: "db-789",
	}
	envelope := createTestEnvelope(t, "terminate.command", payload, correlationID)

	// First call: SetNX returns true (key didn't exist)
	mockRedis.On("SetNX",
		mock.Anything,
		"dedupe:test-correlation-id:terminate",
		"1",
		10*time.Minute,
	).Return(redis.NewBoolResult(true, nil)).Once()

	mockService.On("GetSessionsCount",
		mock.Anything,
		"cluster-123",
		"infobase-456",
	).Return(5, nil).Once()

	mockService.On("TerminateSessions",
		mock.Anything,
		"cluster-123",
		"infobase-456",
	).Return(5, nil).Once()

	// First call should execute
	err := handler.HandleTerminateCommand(ctx, envelope)
	assert.NoError(t, err)
	mockService.AssertExpectations(t)

	// Second call: SetNX returns false (key exists)
	mockRedis.On("SetNX",
		mock.Anything,
		"dedupe:test-correlation-id:terminate",
		"1",
		10*time.Minute,
	).Return(redis.NewBoolResult(false, nil)).Once()

	// Publisher should be called with success event (0 sessions closed, idempotent)
	mockPublisher.On("Publish",
		mock.Anything,
		SessionsClosedChannel,
		SessionsClosedEvent,
		mock.Anything,
		correlationID,
	).Return(nil).Once()

	// Second call should skip operation but publish success
	err = handler.HandleTerminateCommand(ctx, envelope)
	assert.NoError(t, err)

	// Service should NOT be called second time
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)
	mockRedis.AssertExpectations(t)
}

// TestLockHandler_RedisError_FailOpen tests fail-open behavior when Redis is unavailable
func TestLockHandler_RedisError_FailOpen(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()
	handler := NewLockHandler(mockService, mockPublisher, mockRedis, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := LockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
		DatabaseID: "db-789",
	}
	envelope := createTestEnvelope(t, "lock.command", payload, correlationID)

	// SetNX returns error (Redis unavailable)
	redisErr := errors.New("Redis connection failed")
	mockRedis.On("SetNX",
		mock.Anything,
		"dedupe:test-correlation-id:lock",
		"1",
		10*time.Minute,
	).Return(redis.NewBoolResult(false, redisErr)).Once()

	// Operation should continue despite Redis error (fail-open)
	mockService.On("LockInfobase",
		mock.Anything,
		"cluster-123",
		"infobase-456",
	).Return(nil).Once()

	mockPublisher.On("Publish",
		mock.Anything,
		LockedEventChannel,
		InfobaseLockedEvent,
		mock.Anything,
		correlationID,
	).Return(nil).Once()

	// Call should execute operation despite Redis error
	err := handler.HandleLockCommand(ctx, envelope)
	assert.NoError(t, err)

	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)
	mockRedis.AssertExpectations(t)
}

// ============================================================
// MONITORING GOROUTINE TESTS
// ============================================================

// TestTerminateHandler_MonitoringSuccess tests monitoring goroutine when sessions decrease to 0
func TestTerminateHandler_MonitoringSuccess(t *testing.T) {
	t.Skip("Skipping monitoring success test - requires real goroutine timing (run manually if needed)")

	// This test is complex due to asynchronous monitoring goroutine behavior.
	// The monitoring goroutine polls GetSessionsCount() in a loop every 1 second,
	// and the exact number of calls is non-deterministic.
	// For proper testing, this would need integration tests with real Redis or
	// refactoring to inject configurable polling behavior for testability.
}

// TestTerminateHandler_MonitoringTimeout tests monitoring goroutine timeout when sessions don't decrease
func TestTerminateHandler_MonitoringTimeout(t *testing.T) {
	t.Skip("Skipping timeout test - requires 30+ seconds (run manually if needed)")

	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewTerminateHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := TerminateCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
		DatabaseID: "db-789",
	}
	envelope := createTestEnvelope(t, "terminate.command", payload, correlationID)

	// Initial GetSessionsCount
	mockService.On("GetSessionsCount", mock.Anything, "cluster-123", "infobase-456").Return(5, nil).Once()

	// TerminateSessions call
	mockService.On("TerminateSessions", mock.Anything, "cluster-123", "infobase-456").Return(5, nil).Once()

	// Monitoring goroutine: sessions stay at 5 (no decrease)
	// Mock many calls to simulate polling for 30+ seconds
	for i := 0; i < 35; i++ {
		mockService.On("GetSessionsCount", mock.Anything, "cluster-123", "infobase-456").Return(5, nil).Once()
	}

	// Expect partial success event publication after timeout (remaining_count=5)
	mockPublisher.On("Publish",
		mock.Anything,
		SessionsClosedChannel,
		SessionsClosedEvent,
		mock.MatchedBy(func(p TerminateSuccessPayload) bool {
			return p.ClusterID == "cluster-123" &&
				p.InfobaseID == "infobase-456" &&
				p.RemainingCount == 5
		}),
		correlationID,
	).Return(nil).Once()

	// Act
	err := handler.HandleTerminateCommand(ctx, envelope)

	// Assert
	assert.NoError(t, err)

	// Wait for timeout + goroutine completion (35 seconds is too long for test)
	// In real implementation, timeout is 30s. For test, we wait 32s to ensure timeout logic runs
	time.Sleep(32 * time.Second)

	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)

	// Verify partial success event was published
	assert.Len(t, mockPublisher.PublishedEvents, 1)
	publishedEvent := mockPublisher.PublishedEvents[0]
	assert.Equal(t, SessionsClosedChannel, publishedEvent.Channel)
	assert.Equal(t, SessionsClosedEvent, publishedEvent.EventType)
}

// TestTerminateHandler_MonitoringPartialSuccess tests partial success when sessions decrease slowly
func TestTerminateHandler_MonitoringPartialSuccess(t *testing.T) {
	t.Skip("Skipping partial success test - requires 30+ seconds (run manually if needed)")

	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewTerminateHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := TerminateCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
		DatabaseID: "db-789",
	}
	envelope := createTestEnvelope(t, "terminate.command", payload, correlationID)

	// Initial GetSessionsCount
	mockService.On("GetSessionsCount", mock.Anything, "cluster-123", "infobase-456").Return(10, nil).Once()

	// TerminateSessions call
	mockService.On("TerminateSessions", mock.Anything, "cluster-123", "infobase-456").Return(10, nil).Once()

	// Monitoring goroutine: sessions decrease slowly (10 → 7 → 5 → 3)
	// But timeout happens before reaching 0
	count := 10
	for i := 0; i < 35; i++ {
		if i%10 == 0 && count > 3 {
			count -= 2
		}
		mockService.On("GetSessionsCount", mock.Anything, "cluster-123", "infobase-456").Return(count, nil).Once()
	}

	// Expect partial success event with remaining_count > 0
	mockPublisher.On("Publish",
		mock.Anything,
		SessionsClosedChannel,
		SessionsClosedEvent,
		mock.MatchedBy(func(p TerminateSuccessPayload) bool {
			return p.ClusterID == "cluster-123" &&
				p.InfobaseID == "infobase-456" &&
				p.RemainingCount > 0 && p.RemainingCount < 10
		}),
		correlationID,
	).Return(nil).Once()

	// Act
	err := handler.HandleTerminateCommand(ctx, envelope)

	// Assert
	assert.NoError(t, err)

	// Wait for timeout + goroutine completion
	time.Sleep(32 * time.Second)

	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)

	// Verify partial success event was published
	assert.Len(t, mockPublisher.PublishedEvents, 1)
}

// ============================================================
// EDGE CASES TESTS
// ============================================================

// TestLockHandler_InvalidUUIDFormat tests invalid UUID format in payload
func TestLockHandler_InvalidUUIDFormat(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewLockHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := LockCommandPayload{
		ClusterID:  "invalid-uuid-123",
		InfobaseID: "also-invalid",
		DatabaseID: "db-789",
	}
	envelope := createTestEnvelope(t, "lock.command", payload, correlationID)

	// Mock service error due to invalid UUID format
	serviceErr := errors.New("invalid UUID format")
	mockService.On("LockInfobase", ctx, "invalid-uuid-123", "also-invalid").Return(serviceErr)

	// Expect error event publication
	mockPublisher.On("Publish",
		ctx,
		LockFailedChannel,
		InfobaseLockFailedEvent,
		mock.MatchedBy(func(p ErrorPayload) bool {
			return p.ClusterID == "invalid-uuid-123" &&
				p.InfobaseID == "also-invalid" &&
				p.Error == serviceErr.Error()
		}),
		correlationID,
	).Return(nil)

	// Act
	err := handler.HandleLockCommand(ctx, envelope)

	// Assert
	assert.Error(t, err)
	assert.Equal(t, serviceErr, err)
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)

	// Verify error event was published
	assert.Len(t, mockPublisher.PublishedEvents, 1)
	publishedEvent := mockPublisher.PublishedEvents[0]
	assert.Equal(t, LockFailedChannel, publishedEvent.Channel)
	assert.Equal(t, InfobaseLockFailedEvent, publishedEvent.EventType)
}

// TestTerminateHandler_GetSessionsCountError_Retry tests retry logic when GetSessionsCount fails
func TestTerminateHandler_GetSessionsCountError_Retry(t *testing.T) {
	t.Skip("Skipping retry test - requires monitoring goroutine (run manually if needed)")

	// This test verifies that monitoring goroutine handles GetSessionsCount() errors gracefully
	// and continues polling. However, due to non-deterministic number of calls in the goroutine,
	// it's difficult to test with static mocks. Better tested in integration tests.
}

// TestLockHandler_EmptyCorrelationID tests handler with empty correlation_id
func TestLockHandler_EmptyCorrelationID(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewLockHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "" // Empty correlation ID
	payload := LockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
		DatabaseID: "db-789",
	}

	// Manually create envelope with empty correlation_id (createTestEnvelope generates one)
	payloadBytes, err := json.Marshal(payload)
	assert.NoError(t, err)

	envelope := &events.Envelope{
		MessageID:     "msg-123",
		CorrelationID: correlationID, // Explicitly empty
		EventType:     "lock.command",
		ServiceName:   "test-service",
		Timestamp:     time.Now(),
		Payload:       json.RawMessage(payloadBytes),
	}

	// Mock expectations - handler should still work
	mockService.On("LockInfobase", ctx, "cluster-123", "infobase-456").Return(nil)
	mockPublisher.On("Publish", ctx, LockedEventChannel, InfobaseLockedEvent, mock.Anything, correlationID).Return(nil)

	// Act
	err = handler.HandleLockCommand(ctx, envelope)

	// Assert - should not crash, handler gracefully handles empty correlation_id
	assert.NoError(t, err)
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)
}

// TestUnlockHandler_PublishSuccessFails tests error when publishing unlock success event fails
func TestUnlockHandler_PublishSuccessFails(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewUnlockHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := UnlockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
	}
	envelope := createTestEnvelope(t, "unlock.command", payload, correlationID)

	publishErr := errors.New("failed to publish event")

	// Mock expectations
	mockService.On("UnlockInfobase", ctx, "cluster-123", "infobase-456").Return(nil)
	mockPublisher.On("Publish", ctx, UnlockedEventChannel, InfobaseUnlockedEvent, mock.Anything, correlationID).Return(publishErr)

	// Act
	err := handler.HandleUnlockCommand(ctx, envelope)

	// Assert
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to publish success event")
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)
}

// TestTerminateHandler_PublishErrorFails tests when publishing terminate error event fails
func TestTerminateHandler_PublishErrorFails(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewTerminateHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := TerminateCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
	}
	envelope := createTestEnvelope(t, "terminate.command", payload, correlationID)

	serviceErr := errors.New("failed to terminate sessions")
	publishErr := errors.New("failed to publish error event")

	// Mock expectations
	mockService.On("GetSessionsCount", ctx, "cluster-123", "infobase-456").Return(5, nil)
	mockService.On("TerminateSessions", ctx, "cluster-123", "infobase-456").Return(0, serviceErr)
	mockPublisher.On("Publish", ctx, TerminateFailedChannel, SessionsTerminateFailedEvent, mock.Anything, correlationID).Return(publishErr)

	// Act
	err := handler.HandleTerminateCommand(ctx, envelope)

	// Assert - should return original error, not publish error
	assert.Error(t, err)
	assert.Equal(t, serviceErr, err)
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)
}

// TestLockHandler_PublishErrorFails tests when publishing lock error event fails
func TestLockHandler_PublishErrorFails(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewLockHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := LockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
	}
	envelope := createTestEnvelope(t, "lock.command", payload, correlationID)

	serviceErr := errors.New("failed to lock infobase")
	publishErr := errors.New("failed to publish error event")

	// Mock expectations
	mockService.On("LockInfobase", ctx, "cluster-123", "infobase-456").Return(serviceErr)
	mockPublisher.On("Publish", ctx, LockFailedChannel, InfobaseLockFailedEvent, mock.Anything, correlationID).Return(publishErr)

	// Act
	err := handler.HandleLockCommand(ctx, envelope)

	// Assert - should return original error, not publish error
	assert.Error(t, err)
	assert.Equal(t, serviceErr, err)
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)
}

// TestUnlockHandler_PublishErrorFails tests when publishing unlock error event fails
func TestUnlockHandler_PublishErrorFails(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewUnlockHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := UnlockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
	}
	envelope := createTestEnvelope(t, "unlock.command", payload, correlationID)

	serviceErr := errors.New("failed to unlock infobase")
	publishErr := errors.New("failed to publish error event")

	// Mock expectations
	mockService.On("UnlockInfobase", ctx, "cluster-123", "infobase-456").Return(serviceErr)
	mockPublisher.On("Publish", ctx, UnlockFailedChannel, InfobaseUnlockFailedEvent, mock.Anything, correlationID).Return(publishErr)

	// Act
	err := handler.HandleUnlockCommand(ctx, envelope)

	// Assert - should return original error, not publish error
	assert.Error(t, err)
	assert.Equal(t, serviceErr, err)
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)
}

// TestUnlockHandler_MissingFields tests validation for missing required fields
func TestUnlockHandler_MissingFields(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewUnlockHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"

	// Payload with missing infobase_id
	payload := UnlockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "",
	}
	envelope := createTestEnvelope(t, "unlock.command", payload, correlationID)

	mockPublisher.On("Publish", ctx, UnlockFailedChannel, InfobaseUnlockFailedEvent, mock.Anything, correlationID).Return(nil)

	// Act
	err := handler.HandleUnlockCommand(ctx, envelope)

	// Assert
	assert.Error(t, err)
	mockPublisher.AssertExpectations(t)
}

// TestUnlockHandler_InvalidPayload tests invalid JSON payload handling
func TestUnlockHandler_InvalidPayload(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewUnlockHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"

	// Create envelope with invalid JSON
	envelope := &events.Envelope{
		MessageID:     "msg-123",
		CorrelationID: correlationID,
		EventType:     "unlock.command",
		ServiceName:   "test-service",
		Timestamp:     time.Now(),
		Payload:       json.RawMessage(`{"invalid": json`), // Invalid JSON
	}

	mockPublisher.On("Publish", ctx, UnlockFailedChannel, InfobaseUnlockFailedEvent, mock.Anything, correlationID).Return(nil)

	// Act
	err := handler.HandleUnlockCommand(ctx, envelope)

	// Assert
	assert.Error(t, err)
	mockPublisher.AssertExpectations(t)
}

// TestTerminateHandler_InvalidPayload tests invalid JSON payload handling
func TestTerminateHandler_InvalidPayload(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	logger := zap.NewNop()
	handler := NewTerminateHandler(mockService, mockPublisher, nil, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"

	// Create envelope with invalid JSON
	envelope := &events.Envelope{
		MessageID:     "msg-123",
		CorrelationID: correlationID,
		EventType:     "terminate.command",
		ServiceName:   "test-service",
		Timestamp:     time.Now(),
		Payload:       json.RawMessage(`{"invalid": json`), // Invalid JSON
	}

	mockPublisher.On("Publish", ctx, TerminateFailedChannel, SessionsTerminateFailedEvent, mock.Anything, correlationID).Return(nil)

	// Act
	err := handler.HandleTerminateCommand(ctx, envelope)

	// Assert
	assert.Error(t, err)
	mockPublisher.AssertExpectations(t)
}

// TestUnlockHandler_RedisError_FailOpen tests fail-open behavior for unlock when Redis is unavailable
func TestUnlockHandler_RedisError_FailOpen(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()
	handler := NewUnlockHandler(mockService, mockPublisher, mockRedis, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := UnlockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
		DatabaseID: "db-789",
	}
	envelope := createTestEnvelope(t, "unlock.command", payload, correlationID)

	// SetNX returns error (Redis unavailable)
	redisErr := errors.New("Redis connection failed")
	mockRedis.On("SetNX",
		mock.Anything,
		"dedupe:test-correlation-id:unlock",
		"1",
		10*time.Minute,
	).Return(redis.NewBoolResult(false, redisErr)).Once()

	// Operation should continue despite Redis error (fail-open)
	mockService.On("UnlockInfobase",
		mock.Anything,
		"cluster-123",
		"infobase-456",
	).Return(nil).Once()

	mockPublisher.On("Publish",
		mock.Anything,
		UnlockedEventChannel,
		InfobaseUnlockedEvent,
		mock.Anything,
		correlationID,
	).Return(nil).Once()

	// Act
	err := handler.HandleUnlockCommand(ctx, envelope)

	// Assert
	assert.NoError(t, err)
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)
	mockRedis.AssertExpectations(t)
}

// TestTerminateHandler_RedisError_FailOpen tests fail-open behavior for terminate when Redis is unavailable
func TestTerminateHandler_RedisError_FailOpen(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()
	handler := NewTerminateHandler(mockService, mockPublisher, mockRedis, logger)

	ctx := context.Background()
	correlationID := "test-correlation-id"
	payload := TerminateCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
		DatabaseID: "db-789",
	}
	envelope := createTestEnvelope(t, "terminate.command", payload, correlationID)

	// SetNX returns error (Redis unavailable)
	redisErr := errors.New("Redis connection failed")
	mockRedis.On("SetNX",
		mock.Anything,
		"dedupe:test-correlation-id:terminate",
		"1",
		10*time.Minute,
	).Return(redis.NewBoolResult(false, redisErr)).Once()

	// Operation should continue despite Redis error (fail-open)
	mockService.On("GetSessionsCount",
		mock.Anything,
		"cluster-123",
		"infobase-456",
	).Return(5, nil).Once()

	mockService.On("TerminateSessions",
		mock.Anything,
		"cluster-123",
		"infobase-456",
	).Return(5, nil).Once()

	// Act
	err := handler.HandleTerminateCommand(ctx, envelope)

	// Assert
	assert.NoError(t, err)
	mockService.AssertExpectations(t)
	mockRedis.AssertExpectations(t)
}

// ============================================================
// CONCURRENT ACCESS TEST
// ============================================================

// TestLockHandler_ConcurrentRequests tests concurrent requests for the same infobase
func TestLockHandler_ConcurrentRequests(t *testing.T) {
	// Arrange
	mockService := new(MockInfobaseManager)
	mockPublisher := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()
	handler := NewLockHandler(mockService, mockPublisher, mockRedis, logger)

	ctx := context.Background()
	correlationID1 := "correlation-id-1"
	correlationID2 := "correlation-id-2"
	payload := LockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456", // Same infobase
		DatabaseID: "db-789",
	}
	envelope1 := createTestEnvelope(t, "lock.command", payload, correlationID1)
	envelope2 := createTestEnvelope(t, "lock.command", payload, correlationID2)

	// First request: SetNX succeeds
	mockRedis.On("SetNX",
		mock.Anything,
		"dedupe:correlation-id-1:lock",
		"1",
		10*time.Minute,
	).Return(redis.NewBoolResult(true, nil)).Once()

	mockService.On("LockInfobase",
		mock.Anything,
		"cluster-123",
		"infobase-456",
	).Return(nil).Once()

	mockPublisher.On("Publish",
		mock.Anything,
		LockedEventChannel,
		InfobaseLockedEvent,
		mock.Anything,
		correlationID1,
	).Return(nil).Once()

	// Second request: SetNX succeeds (different correlation_id)
	mockRedis.On("SetNX",
		mock.Anything,
		"dedupe:correlation-id-2:lock",
		"1",
		10*time.Minute,
	).Return(redis.NewBoolResult(true, nil)).Once()

	mockService.On("LockInfobase",
		mock.Anything,
		"cluster-123",
		"infobase-456",
	).Return(nil).Once()

	mockPublisher.On("Publish",
		mock.Anything,
		LockedEventChannel,
		InfobaseLockedEvent,
		mock.Anything,
		correlationID2,
	).Return(nil).Once()

	// Act - run concurrently
	var wg sync.WaitGroup
	wg.Add(2)

	var err1, err2 error
	go func() {
		defer wg.Done()
		err1 = handler.HandleLockCommand(ctx, envelope1)
	}()

	go func() {
		defer wg.Done()
		err2 = handler.HandleLockCommand(ctx, envelope2)
	}()

	wg.Wait()

	// Assert - both should succeed
	assert.NoError(t, err1)
	assert.NoError(t, err2)

	// Verify both operations executed (idempotency is per correlation_id, not per infobase)
	mockService.AssertExpectations(t)
	mockPublisher.AssertExpectations(t)
	mockRedis.AssertExpectations(t)

	// Verify both success events were published
	assert.Len(t, mockPublisher.PublishedEvents, 2)
}
