package eventhandlers

import (
	"context"
	"encoding/json"
	"errors"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
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
	handler := NewLockHandler(mockService, mockPublisher, logger)

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
	handler := NewLockHandler(mockService, mockPublisher, logger)

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
	handler := NewLockHandler(mockService, mockPublisher, logger)

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
	handler := NewUnlockHandler(mockService, mockPublisher, logger)

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
	handler := NewTerminateHandler(mockService, mockPublisher, logger)

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
	handler := NewTerminateHandler(mockService, mockPublisher, logger)

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
	handler := NewTerminateHandler(mockService, mockPublisher, logger)

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
	handler := NewLockHandler(mockService, mockPublisher, logger)

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
	handler := NewUnlockHandler(mockService, mockPublisher, logger)

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
	handler := NewTerminateHandler(mockService, mockPublisher, logger)

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
	handler := NewLockHandler(mockService, mockPublisher, logger)

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
