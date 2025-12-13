package eventhandlers

import (
	"context"
	"encoding/json"
	"fmt"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/shared/ras"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"go.uber.org/zap"
)

// Mock InfobaseManager
type MockInfobaseManager struct {
	mock.Mock
}

func (m *MockInfobaseManager) LockInfobase(ctx context.Context, clusterID, infobaseID, dbUser, dbPwd string) error {
	args := m.Called(ctx, clusterID, infobaseID, dbUser, dbPwd)
	return args.Error(0)
}

func (m *MockInfobaseManager) UnlockInfobase(ctx context.Context, clusterID, infobaseID, dbUser, dbPwd string) error {
	args := m.Called(ctx, clusterID, infobaseID, dbUser, dbPwd)
	return args.Error(0)
}

// Mock EventPublisher
type MockEventPublisher struct {
	mock.Mock
}

func (m *MockEventPublisher) Publish(ctx context.Context, channel, eventType string, payload interface{}, correlationID string) error {
	args := m.Called(ctx, channel, eventType, payload, correlationID)
	return args.Error(0)
}

func (m *MockEventPublisher) Close() error {
	return nil
}

// Mock RedisClient
type MockRedisClient struct {
	mock.Mock
}

func (m *MockRedisClient) SetNX(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.BoolCmd {
	args := m.Called(ctx, key, value, expiration)
	result := args.Get(0).(*redis.BoolCmd)
	return result
}

// Helper to create BoolCmd
func createBoolCmd(ctx context.Context, val bool, err error) *redis.BoolCmd {
	cmd := redis.NewBoolCmd(ctx)
	if err != nil {
		cmd.SetErr(err)
	} else {
		cmd.SetVal(val)
	}
	return cmd
}

// Tests

func TestNewLockHandler(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewLockHandler(mockSvc, mockPub, mockRedis, nil, nil, logger)

	assert.NotNil(t, handler)
	assert.Equal(t, mockSvc, handler.service)
	assert.Equal(t, mockPub, handler.publisher)
	assert.Equal(t, mockRedis, handler.redisClient)
}

func TestLockHandler_HandleLockCommand_Success(t *testing.T) {
	// Setup mocks
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewLockHandler(mockSvc, mockPub, mockRedis, nil, nil, logger)

	ctx := context.Background()

	// Mock idempotency check (first time)
	mockRedis.On("SetNX", mock.Anything, mock.MatchedBy(func(key string) bool {
		return key == "idempotency:lock:corr-123"
	}), "processed", IdempotencyTTL).Return(createBoolCmd(ctx, true, nil))

	// Mock service call
	mockSvc.On("LockInfobase", mock.Anything, "cluster-123", "infobase-456", "", "").Return(nil)

	// Mock event publishing
	mockPub.On("Publish", mock.Anything, LockedEventChannel, InfobaseLockedEvent, mock.Anything, "corr-123").Return(nil)

	// Create envelope with RASCommand payload
	cmd := ras.RASCommand{
		OperationID: "op-001",
		DatabaseID:  "db-789",
		ClusterID:   "cluster-123",
		InfobaseID:  "infobase-456",
		CommandType: ras.CommandTypeLock,
		CreatedAt:   time.Now(),
	}
	payloadBytes, _ := json.Marshal(cmd)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payloadBytes,
	}

	// Call handler
	err := handler.HandleLockCommand(ctx, envelope)

	// Assert
	assert.NoError(t, err)
	mockSvc.AssertExpectations(t)
	mockPub.AssertExpectations(t)
	mockRedis.AssertExpectations(t)
}

func TestLockHandler_HandleLockCommand_InvalidPayload(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewLockHandler(mockSvc, mockPub, mockRedis, nil, nil, logger)

	// Mock error publishing
	mockPub.On("Publish", mock.Anything, LockFailedChannel, InfobaseLockFailedEvent, mock.Anything, "corr-123").Return(nil)

	// Invalid JSON
	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       []byte("{invalid json"),
	}

	err := handler.HandleLockCommand(context.Background(), envelope)

	// Should publish error AND return error for Watermill retry
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "invalid payload")
	mockPub.AssertExpectations(t)
}

func TestLockHandler_HandleLockCommand_MissingOperationID(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewLockHandler(mockSvc, mockPub, mockRedis, nil, nil, logger)

	mockPub.On("Publish", mock.Anything, LockFailedChannel, InfobaseLockFailedEvent, mock.Anything, "corr-123").Return(nil)

	cmd := ras.RASCommand{
		OperationID: "", // Empty - should fail validation
		DatabaseID:  "db-789",
		ClusterID:   "cluster-123",
		InfobaseID:  "infobase-456",
		CommandType: ras.CommandTypeLock,
	}
	payloadBytes, _ := json.Marshal(cmd)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payloadBytes,
	}

	err := handler.HandleLockCommand(context.Background(), envelope)

	assert.Error(t, err)
	assert.Equal(t, ras.ErrEmptyOperationID, err)
	mockPub.AssertExpectations(t)
}

func TestLockHandler_HandleLockCommand_MissingClusterID(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewLockHandler(mockSvc, mockPub, mockRedis, nil, nil, logger)

	mockPub.On("Publish", mock.Anything, LockFailedChannel, InfobaseLockFailedEvent, mock.Anything, "corr-123").Return(nil)

	cmd := ras.RASCommand{
		OperationID: "op-001",
		DatabaseID:  "db-789",
		ClusterID:   "", // Empty
		InfobaseID:  "infobase-456",
		CommandType: ras.CommandTypeLock,
	}
	payloadBytes, _ := json.Marshal(cmd)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payloadBytes,
	}

	err := handler.HandleLockCommand(context.Background(), envelope)

	assert.Error(t, err)
	assert.Equal(t, ras.ErrEmptyClusterID, err)
	mockPub.AssertExpectations(t)
}

func TestLockHandler_HandleLockCommand_MissingInfobaseID(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewLockHandler(mockSvc, mockPub, mockRedis, nil, nil, logger)

	mockPub.On("Publish", mock.Anything, LockFailedChannel, InfobaseLockFailedEvent, mock.Anything, "corr-123").Return(nil)

	cmd := ras.RASCommand{
		OperationID: "op-001",
		DatabaseID:  "db-789",
		ClusterID:   "cluster-123",
		InfobaseID:  "", // Empty
		CommandType: ras.CommandTypeLock,
	}
	payloadBytes, _ := json.Marshal(cmd)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payloadBytes,
	}

	err := handler.HandleLockCommand(context.Background(), envelope)

	assert.Error(t, err)
	assert.Equal(t, ras.ErrEmptyInfobaseID, err)
	mockPub.AssertExpectations(t)
}

func TestLockHandler_HandleLockCommand_ServiceError(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewLockHandler(mockSvc, mockPub, mockRedis, nil, nil, logger)

	ctx := context.Background()

	// Mock idempotency (first time)
	mockRedis.On("SetNX", mock.Anything, "idempotency:lock:corr-123", "processed", IdempotencyTTL).
		Return(createBoolCmd(ctx, true, nil))

	// Service returns error
	mockSvc.On("LockInfobase", mock.Anything, "cluster-123", "infobase-456", "", "").
		Return(fmt.Errorf("RAS connection failed"))

	mockPub.On("Publish", mock.Anything, LockFailedChannel, InfobaseLockFailedEvent, mock.Anything, "corr-123").Return(nil)

	cmd := ras.RASCommand{
		OperationID: "op-001",
		DatabaseID:  "db-789",
		ClusterID:   "cluster-123",
		InfobaseID:  "infobase-456",
		CommandType: ras.CommandTypeLock,
	}
	payloadBytes, _ := json.Marshal(cmd)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payloadBytes,
	}

	err := handler.HandleLockCommand(ctx, envelope)

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "RAS connection failed")
	mockSvc.AssertExpectations(t)
	mockPub.AssertExpectations(t)
}

func TestLockHandler_HandleLockCommand_IdempotentRequest(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewLockHandler(mockSvc, mockPub, mockRedis, nil, nil, logger)

	ctx := context.Background()

	// Mock idempotency check (NOT first time)
	mockRedis.On("SetNX", mock.Anything, "idempotency:lock:corr-123", "processed", IdempotencyTTL).
		Return(createBoolCmd(ctx, false, nil))

	// Mock success publishing (idempotent response)
	mockPub.On("Publish", mock.Anything, LockedEventChannel, InfobaseLockedEvent, mock.Anything, "corr-123").Return(nil)

	cmd := ras.RASCommand{
		OperationID: "op-001",
		DatabaseID:  "db-789",
		ClusterID:   "cluster-123",
		InfobaseID:  "infobase-456",
		CommandType: ras.CommandTypeLock,
	}
	payloadBytes, _ := json.Marshal(cmd)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payloadBytes,
	}

	err := handler.HandleLockCommand(ctx, envelope)

	// Should not call service (idempotent)
	assert.NoError(t, err)
	mockPub.AssertExpectations(t)
	mockRedis.AssertExpectations(t)

	// Service should NOT be called
	mockSvc.AssertNotCalled(t, "LockInfobase")
}

func TestLockHandler_HandleLockCommand_ContextTimeout(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewLockHandler(mockSvc, mockPub, mockRedis, nil, nil, logger)

	// Create context with immediate timeout
	ctx, cancel := context.WithTimeout(context.Background(), 1*time.Nanosecond)
	defer cancel()

	time.Sleep(10 * time.Millisecond) // Ensure context is expired

	// Mock idempotency (first time)
	mockRedis.On("SetNX", mock.Anything, "idempotency:lock:corr-123", "processed", IdempotencyTTL).
		Return(createBoolCmd(context.Background(), true, nil))

	// Service will receive cancelled context
	mockSvc.On("LockInfobase", mock.Anything, "cluster-123", "infobase-456", "", "").
		Return(context.DeadlineExceeded)

	mockPub.On("Publish", mock.Anything, LockFailedChannel, InfobaseLockFailedEvent, mock.Anything, "corr-123").Return(nil)

	cmd := ras.RASCommand{
		OperationID: "op-001",
		DatabaseID:  "db-789",
		ClusterID:   "cluster-123",
		InfobaseID:  "infobase-456",
		CommandType: ras.CommandTypeLock,
	}
	payloadBytes, _ := json.Marshal(cmd)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payloadBytes,
	}

	err := handler.HandleLockCommand(ctx, envelope)

	assert.Error(t, err)
	assert.Equal(t, context.DeadlineExceeded, err)
	mockSvc.AssertExpectations(t)
	mockPub.AssertExpectations(t)
}

func TestLockHandler_HandleLockCommand_PublishingError(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	mockRedis := new(MockRedisClient)
	logger := zap.NewNop()

	handler := NewLockHandler(mockSvc, mockPub, mockRedis, nil, nil, logger)

	ctx := context.Background()

	// Mock idempotency (first time)
	mockRedis.On("SetNX", mock.Anything, "idempotency:lock:corr-123", "processed", IdempotencyTTL).
		Return(createBoolCmd(ctx, true, nil))

	// Service succeeds
	mockSvc.On("LockInfobase", mock.Anything, "cluster-123", "infobase-456", "", "").Return(nil)

	// Publishing fails
	mockPub.On("Publish", mock.Anything, LockedEventChannel, InfobaseLockedEvent, mock.Anything, "corr-123").
		Return(fmt.Errorf("Redis publish failed"))

	cmd := ras.RASCommand{
		OperationID: "op-001",
		DatabaseID:  "db-789",
		ClusterID:   "cluster-123",
		InfobaseID:  "infobase-456",
		CommandType: ras.CommandTypeLock,
	}
	payloadBytes, _ := json.Marshal(cmd)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payloadBytes,
	}

	err := handler.HandleLockCommand(ctx, envelope)

	// Publishing error should be returned
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to publish success event")
	mockSvc.AssertExpectations(t)
	mockPub.AssertExpectations(t)
}

func TestLockHandler_HandleLockCommand_RedisNotConfigured(t *testing.T) {
	mockSvc := new(MockInfobaseManager)
	mockPub := new(MockEventPublisher)
	logger := zap.NewNop()

	// No Redis client
	handler := NewLockHandler(mockSvc, mockPub, nil, nil, nil, logger)

	ctx := context.Background()

	// Service should be called (no idempotency check)
	mockSvc.On("LockInfobase", mock.Anything, "cluster-123", "infobase-456", "", "").Return(nil)

	mockPub.On("Publish", mock.Anything, LockedEventChannel, InfobaseLockedEvent, mock.Anything, "corr-123").Return(nil)

	cmd := ras.RASCommand{
		OperationID: "op-001",
		DatabaseID:  "db-789",
		ClusterID:   "cluster-123",
		InfobaseID:  "infobase-456",
		CommandType: ras.CommandTypeLock,
	}
	payloadBytes, _ := json.Marshal(cmd)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payloadBytes,
	}

	err := handler.HandleLockCommand(ctx, envelope)

	assert.NoError(t, err)
	mockSvc.AssertExpectations(t)
	mockPub.AssertExpectations(t)
}
