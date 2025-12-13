package eventhandlers

import (
	"context"
	"encoding/json"
	"errors"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
	sharedodata "github.com/commandcenter1c/commandcenter/shared/odata"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

// Mock ODataClient for testing
type mockODataClient struct {
	executeBatchFunc func(ctx context.Context, creds sharedodata.ODataCredentials, items []sharedodata.BatchItem) (*sharedodata.BatchResult, error)
}

func (m *mockODataClient) Query(ctx context.Context, creds sharedodata.ODataCredentials, entity string, query *sharedodata.QueryParams) ([]map[string]interface{}, error) {
	return nil, errors.New("not implemented")
}

func (m *mockODataClient) Create(ctx context.Context, creds sharedodata.ODataCredentials, entity string, data map[string]interface{}) (map[string]interface{}, error) {
	return nil, errors.New("not implemented")
}

func (m *mockODataClient) Update(ctx context.Context, creds sharedodata.ODataCredentials, entity, entityID string, data map[string]interface{}) error {
	return errors.New("not implemented")
}

func (m *mockODataClient) Delete(ctx context.Context, creds sharedodata.ODataCredentials, entity, entityID string) error {
	return errors.New("not implemented")
}

func (m *mockODataClient) ExecuteBatch(ctx context.Context, creds sharedodata.ODataCredentials, items []sharedodata.BatchItem) (*sharedodata.BatchResult, error) {
	if m.executeBatchFunc != nil {
		return m.executeBatchFunc(ctx, creds, items)
	}
	return nil, errors.New("executeBatchFunc not set")
}

// Mock EventPublisher for testing
type mockEventPublisher struct {
	publishedEvents []mockPublishedEvent
}

type mockPublishedEvent struct {
	channel       string
	eventType     string
	payload       interface{}
	correlationID string
}

func (m *mockEventPublisher) Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error {
	m.publishedEvents = append(m.publishedEvents, mockPublishedEvent{
		channel:       channel,
		eventType:     eventType,
		payload:       payload,
		correlationID: correlationID,
	})
	return nil
}

func (m *mockEventPublisher) Close() error {
	return nil
}

// Mock RedisClient for testing
type mockRedisClient struct {
	setNXFunc func(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.BoolCmd
}

func (m *mockRedisClient) SetNX(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.BoolCmd {
	if m.setNXFunc != nil {
		return m.setNXFunc(ctx, key, value, expiration)
	}
	// Default: return success (first time)
	cmd := redis.NewBoolCmd(ctx)
	cmd.SetVal(true)
	return cmd
}

func TestBatchHandler_HandleBatchCommand_Success(t *testing.T) {
	// Setup mocks
	mockClient := &mockODataClient{
		executeBatchFunc: func(ctx context.Context, creds sharedodata.ODataCredentials, items []sharedodata.BatchItem) (*sharedodata.BatchResult, error) {
			result := sharedodata.NewBatchResult(len(items))
			for i, item := range items {
				result.AddSuccess(i, item.Operation, item.Entity, "guid'123'", nil, 201)
			}
			return result, nil
		},
	}

	mockPublisher := &mockEventPublisher{}

	mockRedis := &mockRedisClient{
		setNXFunc: func(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.BoolCmd {
			cmd := redis.NewBoolCmd(ctx)
			cmd.SetVal(true) // First time
			return cmd
		},
	}

	logger := zap.NewNop()
	handler := NewBatchHandler(mockClient, mockPublisher, mockRedis, nil, nil, logger)

	// Create test command
	cmd := sharedodata.ODataCommand{
		OperationID: "op-123",
		DatabaseID:  "db-456",
		CommandType: sharedodata.CommandTypeBatch,
		Credentials: sharedodata.ODataCredentials{
			BaseURL:  "http://server/base/odata/standard.odata",
			Username: "admin",
			Password: "secret",
		},
		BatchItems: []sharedodata.BatchItem{
			{
				Operation: sharedodata.BatchOperationCreate,
				Entity:    "Catalog_Users",
				Data:      map[string]interface{}{"Description": "Test User"},
			},
		},
		CreatedAt: time.Now(),
	}

	payload, _ := json.Marshal(cmd)
	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payload,
	}

	// Execute handler
	err := handler.HandleBatchCommand(context.Background(), envelope)
	if err != nil {
		t.Fatalf("HandleBatchCommand() error = %v", err)
	}

	// Verify published event
	if len(mockPublisher.publishedEvents) != 1 {
		t.Fatalf("expected 1 published event, got %d", len(mockPublisher.publishedEvents))
	}

	event := mockPublisher.publishedEvents[0]
	if event.channel != BatchCompletedChannel {
		t.Errorf("channel = %s, want %s", event.channel, BatchCompletedChannel)
	}
	if event.eventType != BatchCompletedEvent {
		t.Errorf("eventType = %s, want %s", event.eventType, BatchCompletedEvent)
	}
	if event.correlationID != "corr-123" {
		t.Errorf("correlationID = %s, want corr-123", event.correlationID)
	}

	// Verify result payload
	result, ok := event.payload.(*sharedodata.ODataResult)
	if !ok {
		t.Fatalf("payload is not *ODataResult")
	}
	if !result.Success {
		t.Error("result.Success should be true")
	}
	if result.OperationID != "op-123" {
		t.Errorf("result.OperationID = %s, want op-123", result.OperationID)
	}
}

func TestBatchHandler_HandleBatchCommand_InvalidJSON(t *testing.T) {
	mockClient := &mockODataClient{}
	mockPublisher := &mockEventPublisher{}
	mockRedis := &mockRedisClient{}
	logger := zap.NewNop()
	handler := NewBatchHandler(mockClient, mockPublisher, mockRedis, nil, nil, logger)

	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       []byte("invalid json"),
	}

	err := handler.HandleBatchCommand(context.Background(), envelope)
	if err == nil {
		t.Fatal("expected error for invalid JSON")
	}

	// Should publish error event
	if len(mockPublisher.publishedEvents) != 1 {
		t.Fatalf("expected 1 published event, got %d", len(mockPublisher.publishedEvents))
	}

	event := mockPublisher.publishedEvents[0]
	if event.channel != BatchFailedChannel {
		t.Errorf("channel = %s, want %s", event.channel, BatchFailedChannel)
	}
}

func TestBatchHandler_HandleBatchCommand_InvalidCommandType(t *testing.T) {
	mockClient := &mockODataClient{}
	mockPublisher := &mockEventPublisher{}
	mockRedis := &mockRedisClient{}
	logger := zap.NewNop()
	handler := NewBatchHandler(mockClient, mockPublisher, mockRedis, nil, nil, logger)

	cmd := sharedodata.ODataCommand{
		OperationID: "op-123",
		DatabaseID:  "db-456",
		CommandType: sharedodata.CommandTypeQuery, // Wrong type
		Credentials: sharedodata.ODataCredentials{
			BaseURL:  "http://server/base/odata/standard.odata",
			Username: "admin",
			Password: "secret",
		},
		Entity:    "Catalog_Users",
		CreatedAt: time.Now(),
	}

	payload, _ := json.Marshal(cmd)
	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payload,
	}

	err := handler.HandleBatchCommand(context.Background(), envelope)
	if err == nil {
		t.Fatal("expected error for wrong command type")
	}

	// Should publish error event
	if len(mockPublisher.publishedEvents) != 1 {
		t.Fatalf("expected 1 published event, got %d", len(mockPublisher.publishedEvents))
	}

	event := mockPublisher.publishedEvents[0]
	if event.channel != BatchFailedChannel {
		t.Errorf("channel = %s, want %s", event.channel, BatchFailedChannel)
	}
}

func TestBatchHandler_HandleBatchCommand_EmptyBatchItems(t *testing.T) {
	mockClient := &mockODataClient{}
	mockPublisher := &mockEventPublisher{}
	mockRedis := &mockRedisClient{}
	logger := zap.NewNop()
	handler := NewBatchHandler(mockClient, mockPublisher, mockRedis, nil, nil, logger)

	cmd := sharedodata.ODataCommand{
		OperationID: "op-123",
		DatabaseID:  "db-456",
		CommandType: sharedodata.CommandTypeBatch,
		Credentials: sharedodata.ODataCredentials{
			BaseURL:  "http://server/base/odata/standard.odata",
			Username: "admin",
			Password: "secret",
		},
		BatchItems: []sharedodata.BatchItem{}, // Empty
		CreatedAt:  time.Now(),
	}

	payload, _ := json.Marshal(cmd)
	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payload,
	}

	err := handler.HandleBatchCommand(context.Background(), envelope)
	if err == nil {
		t.Fatal("expected error for empty batch items")
	}

	// Should publish error event
	if len(mockPublisher.publishedEvents) != 1 {
		t.Fatalf("expected 1 published event, got %d", len(mockPublisher.publishedEvents))
	}
}

func TestBatchHandler_HandleBatchCommand_BatchSizeExceedsLimit(t *testing.T) {
	mockClient := &mockODataClient{}
	mockPublisher := &mockEventPublisher{}
	mockRedis := &mockRedisClient{}
	logger := zap.NewNop()
	handler := NewBatchHandler(mockClient, mockPublisher, mockRedis, nil, nil, logger)

	// Create batch with > MaxBatchSize items
	items := make([]sharedodata.BatchItem, MaxBatchSize+1)
	for i := range items {
		items[i] = sharedodata.BatchItem{
			Operation: sharedodata.BatchOperationCreate,
			Entity:    "Catalog_Users",
			Data:      map[string]interface{}{"Description": "Test"},
		}
	}

	cmd := sharedodata.ODataCommand{
		OperationID: "op-123",
		DatabaseID:  "db-456",
		CommandType: sharedodata.CommandTypeBatch,
		Credentials: sharedodata.ODataCredentials{
			BaseURL:  "http://server/base/odata/standard.odata",
			Username: "admin",
			Password: "secret",
		},
		BatchItems: items,
		CreatedAt:  time.Now(),
	}

	payload, _ := json.Marshal(cmd)
	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payload,
	}

	err := handler.HandleBatchCommand(context.Background(), envelope)
	if err == nil {
		t.Fatal("expected error for batch size exceeds limit")
	}

	// Should publish error event
	if len(mockPublisher.publishedEvents) != 1 {
		t.Fatalf("expected 1 published event, got %d", len(mockPublisher.publishedEvents))
	}
}

func TestBatchHandler_HandleBatchCommand_InvalidBatchItem(t *testing.T) {
	mockClient := &mockODataClient{}
	mockPublisher := &mockEventPublisher{}
	mockRedis := &mockRedisClient{}
	logger := zap.NewNop()
	handler := NewBatchHandler(mockClient, mockPublisher, mockRedis, nil, nil, logger)

	cmd := sharedodata.ODataCommand{
		OperationID: "op-123",
		DatabaseID:  "db-456",
		CommandType: sharedodata.CommandTypeBatch,
		Credentials: sharedodata.ODataCredentials{
			BaseURL:  "http://server/base/odata/standard.odata",
			Username: "admin",
			Password: "secret",
		},
		BatchItems: []sharedodata.BatchItem{
			{
				Operation: sharedodata.BatchOperationCreate,
				Entity:    "", // Invalid: empty entity
				Data:      map[string]interface{}{"Description": "Test"},
			},
		},
		CreatedAt: time.Now(),
	}

	payload, _ := json.Marshal(cmd)
	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payload,
	}

	err := handler.HandleBatchCommand(context.Background(), envelope)
	if err == nil {
		t.Fatal("expected error for invalid batch item")
	}

	// Should publish error event
	if len(mockPublisher.publishedEvents) != 1 {
		t.Fatalf("expected 1 published event, got %d", len(mockPublisher.publishedEvents))
	}
}

func TestBatchHandler_HandleBatchCommand_ExecuteBatchError(t *testing.T) {
	// Setup mocks
	mockClient := &mockODataClient{
		executeBatchFunc: func(ctx context.Context, creds sharedodata.ODataCredentials, items []sharedodata.BatchItem) (*sharedodata.BatchResult, error) {
			return nil, errors.New("OData connection failed")
		},
	}

	mockPublisher := &mockEventPublisher{}
	mockRedis := &mockRedisClient{}
	logger := zap.NewNop()
	handler := NewBatchHandler(mockClient, mockPublisher, mockRedis, nil, nil, logger)

	cmd := sharedodata.ODataCommand{
		OperationID: "op-123",
		DatabaseID:  "db-456",
		CommandType: sharedodata.CommandTypeBatch,
		Credentials: sharedodata.ODataCredentials{
			BaseURL:  "http://server/base/odata/standard.odata",
			Username: "admin",
			Password: "secret",
		},
		BatchItems: []sharedodata.BatchItem{
			{
				Operation: sharedodata.BatchOperationCreate,
				Entity:    "Catalog_Users",
				Data:      map[string]interface{}{"Description": "Test"},
			},
		},
		CreatedAt: time.Now(),
	}

	payload, _ := json.Marshal(cmd)
	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payload,
	}

	err := handler.HandleBatchCommand(context.Background(), envelope)
	if err == nil {
		t.Fatal("expected error from ExecuteBatch")
	}

	// Should publish error event
	if len(mockPublisher.publishedEvents) != 1 {
		t.Fatalf("expected 1 published event, got %d", len(mockPublisher.publishedEvents))
	}

	event := mockPublisher.publishedEvents[0]
	if event.channel != BatchFailedChannel {
		t.Errorf("channel = %s, want %s", event.channel, BatchFailedChannel)
	}
}

func TestBatchHandler_HandleBatchCommand_Idempotency(t *testing.T) {
	// Setup mocks
	mockClient := &mockODataClient{
		executeBatchFunc: func(ctx context.Context, creds sharedodata.ODataCredentials, items []sharedodata.BatchItem) (*sharedodata.BatchResult, error) {
			t.Error("ExecuteBatch should not be called for duplicate command")
			return nil, errors.New("should not be called")
		},
	}

	mockPublisher := &mockEventPublisher{}

	// Mock Redis to return false (already processed)
	mockRedis := &mockRedisClient{
		setNXFunc: func(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.BoolCmd {
			cmd := redis.NewBoolCmd(ctx)
			cmd.SetVal(false) // Already exists
			return cmd
		},
	}

	logger := zap.NewNop()
	handler := NewBatchHandler(mockClient, mockPublisher, mockRedis, nil, nil, logger)

	cmd := sharedodata.ODataCommand{
		OperationID: "op-123",
		DatabaseID:  "db-456",
		CommandType: sharedodata.CommandTypeBatch,
		Credentials: sharedodata.ODataCredentials{
			BaseURL:  "http://server/base/odata/standard.odata",
			Username: "admin",
			Password: "secret",
		},
		BatchItems: []sharedodata.BatchItem{
			{
				Operation: sharedodata.BatchOperationCreate,
				Entity:    "Catalog_Users",
				Data:      map[string]interface{}{"Description": "Test"},
			},
		},
		CreatedAt: time.Now(),
	}

	payload, _ := json.Marshal(cmd)
	envelope := &events.Envelope{
		CorrelationID: "corr-123",
		Payload:       payload,
	}

	// Execute handler
	err := handler.HandleBatchCommand(context.Background(), envelope)
	if err != nil {
		t.Fatalf("HandleBatchCommand() error = %v", err)
	}

	// Should publish success event (idempotent response)
	if len(mockPublisher.publishedEvents) != 1 {
		t.Fatalf("expected 1 published event, got %d", len(mockPublisher.publishedEvents))
	}

	event := mockPublisher.publishedEvents[0]
	if event.channel != BatchCompletedChannel {
		t.Errorf("channel = %s, want %s", event.channel, BatchCompletedChannel)
	}

	result, ok := event.payload.(*sharedodata.ODataResult)
	if !ok {
		t.Fatalf("payload is not *ODataResult")
	}
	if !result.Success {
		t.Error("result.Success should be true for idempotent response")
	}
}
