package eventhandlers

import (
	"context"
	"encoding/json"
	"fmt"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"go.uber.org/zap"
)

func TestNewUnlockHandler(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewUnlockHandler(mockSvc, mockPub, mockRedis, logger)

	assert.NotNil(t, handler)
	assert.Equal(t, mockSvc, handler.service)
	assert.Equal(t, mockPub, handler.publisher)
	assert.Equal(t, mockRedis, handler.redisClient)
}

func TestUnlockHandler_HandleUnlockCommand_Success(t *testing.T) {
	// Setup mocks
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewUnlockHandler(mockSvc, mockPub, mockRedis, logger)

	ctx := context.Background()

	// Mock idempotency check (first time)
	mockRedis.On("SetNX", mock.Anything, mock.MatchedBy(func(key string) bool {
		return key == "idempotency:unlock:corr-123"
	}), "processed", IdempotencyTTL).Return(createBoolCmd(ctx, true, nil))

	// Mock service call
	mockSvc.On("UnlockInfobase", mock.Anything, "cluster-123", "infobase-456").Return(nil)

	// Mock event publishing
	mockPub.On("Publish", mock.Anything, UnlockedEventChannel, InfobaseUnlockedEvent, mock.Anything, "corr-123").Return(nil)

	// Create envelope
	payload := UnlockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
		DatabaseID: "db-789",
	}
	payloadBytes, _ := json.Marshal(payload)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payloadBytes,
	}

	// Call handler
	err := handler.HandleUnlockCommand(ctx, envelope)

	// Assert
	assert.NoError(t, err)
	mockSvc.AssertExpectations(t)
	mockPub.AssertExpectations(t)
	mockRedis.AssertExpectations(t)
}

func TestUnlockHandler_HandleUnlockCommand_InvalidPayload(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewUnlockHandler(mockSvc, mockPub, mockRedis, logger)

	// Mock error publishing
	mockPub.On("Publish", mock.Anything, UnlockFailedChannel, InfobaseUnlockFailedEvent, mock.Anything, "corr-123").Return(nil)

	// Invalid JSON
	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       []byte("{invalid json"),
	}

	err := handler.HandleUnlockCommand(context.Background(), envelope)

	// Should publish error AND return error for Watermill retry
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "invalid payload")
	mockPub.AssertExpectations(t)
}

func TestUnlockHandler_HandleUnlockCommand_MissingClusterID(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewUnlockHandler(mockSvc, mockPub, mockRedis, logger)

	mockPub.On("Publish", mock.Anything, UnlockFailedChannel, InfobaseUnlockFailedEvent, mock.Anything, "corr-123").Return(nil)

	payload := UnlockCommandPayload{
		ClusterID:  "", // Empty
		InfobaseID: "infobase-456",
	}
	payloadBytes, _ := json.Marshal(payload)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payloadBytes,
	}

	err := handler.HandleUnlockCommand(context.Background(), envelope)

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "cluster_id and infobase_id are required")
	mockPub.AssertExpectations(t)
}

func TestUnlockHandler_HandleUnlockCommand_MissingInfobaseID(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewUnlockHandler(mockSvc, mockPub, mockRedis, logger)

	mockPub.On("Publish", mock.Anything, UnlockFailedChannel, InfobaseUnlockFailedEvent, mock.Anything, "corr-123").Return(nil)

	payload := UnlockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "", // Empty
	}
	payloadBytes, _ := json.Marshal(payload)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payloadBytes,
	}

	err := handler.HandleUnlockCommand(context.Background(), envelope)

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "cluster_id and infobase_id are required")
	mockPub.AssertExpectations(t)
}

func TestUnlockHandler_HandleUnlockCommand_ServiceError(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewUnlockHandler(mockSvc, mockPub, mockRedis, logger)

	ctx := context.Background()

	// Mock idempotency (first time)
	mockRedis.On("SetNX", mock.Anything, "idempotency:unlock:corr-123", "processed", IdempotencyTTL).
		Return(createBoolCmd(ctx, true, nil))

	// Service returns error
	mockSvc.On("UnlockInfobase", mock.Anything, "cluster-123", "infobase-456").
		Return(fmt.Errorf("RAS connection failed"))

	mockPub.On("Publish", mock.Anything, UnlockFailedChannel, InfobaseUnlockFailedEvent, mock.Anything, "corr-123").Return(nil)

	payload := UnlockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
	}
	payloadBytes, _ := json.Marshal(payload)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payloadBytes,
	}

	err := handler.HandleUnlockCommand(ctx, envelope)

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "RAS connection failed")
	mockSvc.AssertExpectations(t)
	mockPub.AssertExpectations(t)
}

func TestUnlockHandler_HandleUnlockCommand_IdempotentRequest(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewUnlockHandler(mockSvc, mockPub, mockRedis, logger)

	ctx := context.Background()

	// Mock idempotency check (NOT first time)
	mockRedis.On("SetNX", mock.Anything, "idempotency:unlock:corr-123", "processed", IdempotencyTTL).
		Return(createBoolCmd(ctx, false, nil))

	// Mock success publishing (idempotent response)
	mockPub.On("Publish", mock.Anything, UnlockedEventChannel, InfobaseUnlockedEvent, mock.Anything, "corr-123").Return(nil)

	payload := UnlockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
	}
	payloadBytes, _ := json.Marshal(payload)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payloadBytes,
	}

	err := handler.HandleUnlockCommand(ctx, envelope)

	// Should not call service (idempotent)
	assert.NoError(t, err)
	mockPub.AssertExpectations(t)
	mockRedis.AssertExpectations(t)

	// Service should NOT be called
	mockSvc.AssertNotCalled(t, "UnlockInfobase")
}

func TestUnlockHandler_HandleUnlockCommand_ContextTimeout(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewUnlockHandler(mockSvc, mockPub, mockRedis, logger)

	// Create context with immediate timeout
	ctx, cancel := context.WithTimeout(context.Background(), 1*time.Nanosecond)
	defer cancel()

	time.Sleep(10 * time.Millisecond) // Ensure context is expired

	// Mock idempotency (first time)
	mockRedis.On("SetNX", mock.Anything, "idempotency:unlock:corr-123", "processed", IdempotencyTTL).
		Return(createBoolCmd(context.Background(), true, nil))

	// Service will receive cancelled context
	mockSvc.On("UnlockInfobase", mock.Anything, "cluster-123", "infobase-456").
		Return(context.DeadlineExceeded)

	mockPub.On("Publish", mock.Anything, UnlockFailedChannel, InfobaseUnlockFailedEvent, mock.Anything, "corr-123").Return(nil)

	payload := UnlockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
	}
	payloadBytes, _ := json.Marshal(payload)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payloadBytes,
	}

	err := handler.HandleUnlockCommand(ctx, envelope)

	assert.Error(t, err)
	assert.Equal(t, context.DeadlineExceeded, err)
	mockSvc.AssertExpectations(t)
	mockPub.AssertExpectations(t)
}

func TestUnlockHandler_HandleUnlockCommand_PublishingError(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewUnlockHandler(mockSvc, mockPub, mockRedis, logger)

	ctx := context.Background()

	// Mock idempotency (first time)
	mockRedis.On("SetNX", mock.Anything, "idempotency:unlock:corr-123", "processed", IdempotencyTTL).
		Return(createBoolCmd(ctx, true, nil))

	// Service succeeds
	mockSvc.On("UnlockInfobase", mock.Anything, "cluster-123", "infobase-456").Return(nil)

	// Publishing fails
	mockPub.On("Publish", mock.Anything, UnlockedEventChannel, InfobaseUnlockedEvent, mock.Anything, "corr-123").
		Return(fmt.Errorf("Redis publish failed"))

	payload := UnlockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
	}
	payloadBytes, _ := json.Marshal(payload)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payloadBytes,
	}

	err := handler.HandleUnlockCommand(ctx, envelope)

	// Publishing error should be returned
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to publish success event")
	mockSvc.AssertExpectations(t)
	mockPub.AssertExpectations(t)
}

func TestUnlockHandler_HandleUnlockCommand_RedisNotConfigured(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	logger := zap.NewNop()

	// No Redis client
	handler := NewUnlockHandler(mockSvc, mockPub, nil, logger)

	ctx := context.Background()

	// Service should be called (no idempotency check)
	mockSvc.On("UnlockInfobase", mock.Anything, "cluster-123", "infobase-456").Return(nil)

	mockPub.On("Publish", mock.Anything, UnlockedEventChannel, InfobaseUnlockedEvent, mock.Anything, "corr-123").Return(nil)

	payload := UnlockCommandPayload{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
	}
	payloadBytes, _ := json.Marshal(payload)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payloadBytes,
	}

	err := handler.HandleUnlockCommand(ctx, envelope)

	assert.NoError(t, err)
	mockSvc.AssertExpectations(t)
	mockPub.AssertExpectations(t)
}
