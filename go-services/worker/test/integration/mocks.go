package integration

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/redis/go-redis/v9"

	"github.com/commandcenter1c/commandcenter/shared/events"
)

// MockEventResponder mocks external event producers (worker, worker)
type MockEventResponder struct {
	mu       sync.Mutex
	handlers map[string]ResponseHandler

	// Publisher for sending mock responses
	publisher  *events.Publisher
	subscriber *events.Subscriber

	// Tracking
	receivedCommands []string

	// Context
	ctx    context.Context
	cancel context.CancelFunc
}

// ResponseHandler defines handler for mock responses
type ResponseHandler func(ctx context.Context, envelope *events.Envelope) (*events.Envelope, error)

// NewMockEventResponder creates new mock event responder
func NewMockEventResponder(redisClient *redis.Client, logger watermill.LoggerAdapter) (*MockEventResponder, error) {
	publisher, err := events.NewPublisher(redisClient, "mock-responder-pub", logger)
	if err != nil {
		return nil, fmt.Errorf("failed to create publisher: %w", err)
	}

	subscriber, err := events.NewSubscriber(redisClient, "mock-responder-sub", logger)
	if err != nil {
		return nil, fmt.Errorf("failed to create subscriber: %w", err)
	}

	ctx, cancel := context.WithCancel(context.Background())

	mock := &MockEventResponder{
		handlers:         make(map[string]ResponseHandler),
		publisher:        publisher,
		subscriber:       subscriber,
		receivedCommands: make([]string, 0),
		ctx:              ctx,
		cancel:           cancel,
	}

	return mock, nil
}

// RegisterHandler registers handler for specific command channel
func (m *MockEventResponder) RegisterHandler(commandChannel string, handler ResponseHandler) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.handlers[commandChannel] = handler

	// Subscribe to command channel
	return m.subscriber.Subscribe(commandChannel, func(ctx context.Context, envelope *events.Envelope) error {
		m.mu.Lock()
		m.receivedCommands = append(m.receivedCommands, envelope.EventType)
		handler := m.handlers[commandChannel]
		m.mu.Unlock()

		if handler == nil {
			return nil // No handler, ignore
		}

		// Execute handler to get response
		response, err := handler(ctx, envelope)
		if err != nil {
			return err
		}

		if response == nil {
			return nil // No response to send
		}

		// Publish response event
		var payload map[string]interface{}
		if err := json.Unmarshal(response.Payload, &payload); err != nil {
			return fmt.Errorf("failed to unmarshal response payload: %w", err)
		}

		// Determine response channel based on event type
		responseChannel := m.getResponseChannel(response.EventType)

		return m.publisher.Publish(ctx, responseChannel, response.EventType, payload, envelope.CorrelationID)
	})
}

// getResponseChannel determines response channel based on event type
func (m *MockEventResponder) getResponseChannel(eventType string) string {
	// Map event types to channels
	channelMap := map[string]string{
		"cluster.infobase.locked":           "events:worker:infobase:locked",
		"cluster.infobase.lock-failed":      "events:worker:infobase:lock-failed",
		"cluster.infobase.unlocked":         "events:worker:infobase:unlocked",
		"cluster.infobase.unlock-failed":    "events:worker:infobase:unlock-failed",
		"cluster.sessions.closed":           "events:worker:sessions:closed",
		"cluster.sessions.terminate-failed": "events:worker:sessions:terminate-failed",
		"batch.extension.installed":         "events:worker:extension:installed",
		"batch.extension.install-failed":    "events:worker:extension:install-failed",
	}

	if channel, ok := channelMap[eventType]; ok {
		return channel
	}

	return "events:unknown"
}

// Run starts mock responder (processes commands)
func (m *MockEventResponder) Run() {
	go m.subscriber.Run(m.ctx)
}

// Stop stops mock responder
func (m *MockEventResponder) Stop() {
	m.cancel()
}

// GetReceivedCommands returns list of received command types
func (m *MockEventResponder) GetReceivedCommands() []string {
	m.mu.Lock()
	defer m.mu.Unlock()

	commands := make([]string, len(m.receivedCommands))
	copy(commands, m.receivedCommands)
	return commands
}

// ClearReceivedCommands clears received commands list
func (m *MockEventResponder) ClearReceivedCommands() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.receivedCommands = m.receivedCommands[:0]
}

// =============================================================================
// Pre-built Mock Response Helpers
// =============================================================================

// MockLockSuccessResponse creates successful lock response
func MockLockSuccessResponse() ResponseHandler {
	return func(ctx context.Context, envelope *events.Envelope) (*events.Envelope, error) {
		// Simulate processing delay
		time.Sleep(50 * time.Millisecond)

		response := &events.Envelope{
			EventType:     "cluster.infobase.locked",
			CorrelationID: envelope.CorrelationID,
			Timestamp:     time.Now(),
		}

		payload, _ := json.Marshal(map[string]interface{}{
			"cluster_id":  "test-cluster",
			"infobase_id": "test-infobase",
			"status":      "locked",
		})
		response.Payload = payload

		return response, nil
	}
}

// MockLockFailedResponse creates failed lock response
func MockLockFailedResponse(reason string) ResponseHandler {
	return func(ctx context.Context, envelope *events.Envelope) (*events.Envelope, error) {
		time.Sleep(50 * time.Millisecond)

		response := &events.Envelope{
			EventType:     "cluster.infobase.lock-failed",
			CorrelationID: envelope.CorrelationID,
			Timestamp:     time.Now(),
		}

		payload, _ := json.Marshal(map[string]interface{}{
			"cluster_id":  "test-cluster",
			"infobase_id": "test-infobase",
			"error":       reason,
		})
		response.Payload = payload

		return response, nil
	}
}

// MockTerminateSuccessResponse creates successful terminate response
func MockTerminateSuccessResponse() ResponseHandler {
	return func(ctx context.Context, envelope *events.Envelope) (*events.Envelope, error) {
		time.Sleep(100 * time.Millisecond)

		response := &events.Envelope{
			EventType:     "cluster.sessions.closed",
			CorrelationID: envelope.CorrelationID,
			Timestamp:     time.Now(),
		}

		payload, _ := json.Marshal(map[string]interface{}{
			"cluster_id":       "test-cluster",
			"infobase_id":      "test-infobase",
			"sessions_closed":  5,
			"status":           "success",
		})
		response.Payload = payload

		return response, nil
	}
}

// MockTerminateTimeoutResponse creates timeout terminate response
func MockTerminateTimeoutResponse() ResponseHandler {
	return func(ctx context.Context, envelope *events.Envelope) (*events.Envelope, error) {
		// Simulate timeout - don't send response
		return nil, nil
	}
}

// MockInstallSuccessResponse creates successful install response
func MockInstallSuccessResponse() ResponseHandler {
	return func(ctx context.Context, envelope *events.Envelope) (*events.Envelope, error) {
		time.Sleep(200 * time.Millisecond)

		response := &events.Envelope{
			EventType:     "batch.extension.installed",
			CorrelationID: envelope.CorrelationID,
			Timestamp:     time.Now(),
		}

		payload, _ := json.Marshal(map[string]interface{}{
			"database_id":    "test-database",
			"extension_name": "TestExtension",
			"status":         "installed",
		})
		response.Payload = payload

		return response, nil
	}
}

// MockInstallFailedResponse creates failed install response
func MockInstallFailedResponse(reason string) ResponseHandler {
	return func(ctx context.Context, envelope *events.Envelope) (*events.Envelope, error) {
		time.Sleep(100 * time.Millisecond)

		response := &events.Envelope{
			EventType:     "batch.extension.install-failed",
			CorrelationID: envelope.CorrelationID,
			Timestamp:     time.Now(),
		}

		payload, _ := json.Marshal(map[string]interface{}{
			"database_id":    "test-database",
			"extension_name": "TestExtension",
			"error":          reason,
		})
		response.Payload = payload

		return response, nil
	}
}

// MockUnlockSuccessResponse creates successful unlock response
func MockUnlockSuccessResponse() ResponseHandler {
	return func(ctx context.Context, envelope *events.Envelope) (*events.Envelope, error) {
		time.Sleep(50 * time.Millisecond)

		response := &events.Envelope{
			EventType:     "cluster.infobase.unlocked",
			CorrelationID: envelope.CorrelationID,
			Timestamp:     time.Now(),
		}

		payload, _ := json.Marshal(map[string]interface{}{
			"cluster_id":  "test-cluster",
			"infobase_id": "test-infobase",
			"status":      "unlocked",
		})
		response.Payload = payload

		return response, nil
	}
}

// MockUnlockFailedResponse creates failed unlock response
func MockUnlockFailedResponse(reason string) ResponseHandler {
	return func(ctx context.Context, envelope *events.Envelope) (*events.Envelope, error) {
		time.Sleep(50 * time.Millisecond)

		response := &events.Envelope{
			EventType:     "cluster.infobase.unlock-failed",
			CorrelationID: envelope.CorrelationID,
			Timestamp:     time.Now(),
		}

		payload, _ := json.Marshal(map[string]interface{}{
			"cluster_id":  "test-cluster",
			"infobase_id": "test-infobase",
			"error":       reason,
		})
		response.Payload = payload

		return response, nil
	}
}

// MockUnlockRetriesResponse creates unlock response that fails N times then succeeds
func MockUnlockRetriesResponse(failCount int) ResponseHandler {
	attempts := 0
	var mu sync.Mutex

	return func(ctx context.Context, envelope *events.Envelope) (*events.Envelope, error) {
		mu.Lock()
		attempts++
		currentAttempt := attempts
		mu.Unlock()

		time.Sleep(50 * time.Millisecond)

		if currentAttempt <= failCount {
			// Fail
			response := &events.Envelope{
				EventType:     "cluster.infobase.unlock-failed",
				CorrelationID: envelope.CorrelationID,
				Timestamp:     time.Now(),
			}

			payload, _ := json.Marshal(map[string]interface{}{
				"cluster_id":  "test-cluster",
				"infobase_id": "test-infobase",
				"error":       fmt.Sprintf("unlock failed (attempt %d)", currentAttempt),
			})
			response.Payload = payload

			return response, nil
		}

		// Success after retries
		response := &events.Envelope{
			EventType:     "cluster.infobase.unlocked",
			CorrelationID: envelope.CorrelationID,
			Timestamp:     time.Now(),
		}

		payload, _ := json.Marshal(map[string]interface{}{
			"cluster_id":  "test-cluster",
			"infobase_id": "test-infobase",
			"status":      "unlocked",
		})
		response.Payload = payload

		return response, nil
	}
}
