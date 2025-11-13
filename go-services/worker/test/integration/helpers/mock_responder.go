package helpers

import (
	"context"
	"encoding/json"
	"fmt"
	"math/rand"
	"strings"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
)

// EventBehavior defines how mock responder should handle a specific event type
type EventBehavior struct {
	ResponseEvent   string                 // Event type to publish in response
	ResponsePayload map[string]interface{} // Payload for response event
	Delay           time.Duration          // Artificial delay before responding
	FailureRate     float64                // 0.0 = always success, 1.0 = always fail
	TimeoutRate     float64                // 0.0 = never timeout, 1.0 = always timeout (no response)
}

// MockEventResponder simulates external services (cluster-service, batch-service) via events
type MockEventResponder struct {
	publisher  *events.Publisher
	subscriber *SubscriberAdapter
	behaviors  map[string]EventBehavior
	verbose    bool
}

// NewMockEventResponder creates a new mock event responder
func NewMockEventResponder(
	publisher *events.Publisher,
	subscriber *SubscriberAdapter,
	behaviors map[string]EventBehavior,
) *MockEventResponder {
	return &MockEventResponder{
		publisher:  publisher,
		subscriber: subscriber,
		behaviors:  behaviors,
		verbose:    false,
	}
}

// SetVerbose enables verbose logging
func (m *MockEventResponder) SetVerbose(verbose bool) {
	m.verbose = verbose
}

// Run starts the mock responder (blocking, run in goroutine)
func (m *MockEventResponder) Run(ctx context.Context) error {
	// Subscribe to all command channels that we want to mock
	m.subscriber.Subscribe("commands:cluster-service:infobase:lock", m.handleEvent)
	m.subscriber.Subscribe("commands:cluster-service:sessions:terminate", m.handleEvent)
	m.subscriber.Subscribe("commands:cluster-service:infobase:unlock", m.handleEvent)
	m.subscriber.Subscribe("commands:batch-service:extension:install", m.handleEvent)

	if m.verbose {
		fmt.Println("[MockResponder] Started, listening for commands...")
	}

	return m.subscriber.Run(ctx)
}

// handleEvent handles incoming command event and publishes response
func (m *MockEventResponder) handleEvent(ctx context.Context, envelope *events.Envelope) error {
	behavior, ok := m.behaviors[envelope.EventType]
	if !ok {
		if m.verbose {
			fmt.Printf("[MockResponder] No behavior configured for: %s\n", envelope.EventType)
		}
		return nil
	}

	if m.verbose {
		fmt.Printf("[MockResponder] Handling: %s (correlation_id=%s)\n",
			envelope.EventType, envelope.CorrelationID)
	}

	// Simulate delay
	if behavior.Delay > 0 {
		time.Sleep(behavior.Delay)
	}

	// Simulate timeout (no response at all)
	if behavior.TimeoutRate > 0 && rand.Float64() < behavior.TimeoutRate {
		if m.verbose {
			fmt.Printf("[MockResponder] Simulating timeout for %s\n", envelope.EventType)
		}
		return nil // No response
	}

	// Simulate failure
	if behavior.FailureRate > 0 && rand.Float64() < behavior.FailureRate {
		return m.publishFailure(ctx, envelope, behavior)
	}

	// Success response
	return m.publishSuccess(ctx, envelope, behavior)
}

// publishSuccess publishes a successful response event
func (m *MockEventResponder) publishSuccess(ctx context.Context, original *events.Envelope, behavior EventBehavior) error {
	channel := m.eventTypeToChannel(behavior.ResponseEvent)

	payload := behavior.ResponsePayload
	if payload == nil {
		payload = map[string]interface{}{"status": "success"}
	}

	err := m.publisher.Publish(ctx, channel, behavior.ResponseEvent, payload, original.CorrelationID)
	if err != nil {
		return fmt.Errorf("failed to publish success response: %w", err)
	}

	if m.verbose {
		fmt.Printf("[MockResponder] Published success: %s (correlation_id=%s)\n",
			behavior.ResponseEvent, original.CorrelationID)
	}

	return nil
}

// publishFailure publishes a failure response event
func (m *MockEventResponder) publishFailure(ctx context.Context, original *events.Envelope, behavior EventBehavior) error {
	// Convert success event to failed event (e.g., "cluster.infobase.locked" -> "cluster.infobase.lock.failed")
	failedEvent := behavior.ResponseEvent
	if strings.HasSuffix(failedEvent, "ed") {
		// "locked" -> "lock.failed"
		// "installed" -> "install.failed"
		// "closed" -> "close.failed"
		// "unlocked" -> "unlock.failed"
		base := strings.TrimSuffix(failedEvent, "ed")
		if strings.HasSuffix(base, "l") && strings.HasSuffix(failedEvent, "lled") {
			// "installed" -> "install"
			base = strings.TrimSuffix(failedEvent, "led")
		}
		failedEvent = base + ".failed"
	} else if !strings.HasSuffix(failedEvent, ".failed") {
		failedEvent += ".failed"
	}

	channel := m.eventTypeToChannel(failedEvent)

	payload := map[string]interface{}{
		"status": "failed",
		"error":  "simulated failure for testing",
	}

	// Parse original payload to extract context
	var originalPayload map[string]interface{}
	if err := json.Unmarshal(original.Payload, &originalPayload); err == nil {
		// Copy relevant fields
		if clusterID, ok := originalPayload["cluster_id"]; ok {
			payload["cluster_id"] = clusterID
		}
		if infobaseID, ok := originalPayload["infobase_id"]; ok {
			payload["infobase_id"] = infobaseID
		}
		if databaseID, ok := originalPayload["database_id"]; ok {
			payload["database_id"] = databaseID
		}
	}

	err := m.publisher.Publish(ctx, channel, failedEvent, payload, original.CorrelationID)
	if err != nil {
		return fmt.Errorf("failed to publish failure response: %w", err)
	}

	if m.verbose {
		fmt.Printf("[MockResponder] Published failure: %s (correlation_id=%s)\n",
			failedEvent, original.CorrelationID)
	}

	return nil
}

// eventTypeToChannel converts event type to channel name
// Maps event types to their actual channels as used by cluster-service and batch-service
// Examples:
// - "cluster.infobase.locked" -> "events:cluster-service:infobase:locked"
// - "batch.extension.installed" -> "events:batch-service:extension:installed"
func (m *MockEventResponder) eventTypeToChannel(eventType string) string {
	parts := strings.Split(eventType, ".")
	if len(parts) < 2 {
		return "events:unknown"
	}

	service := parts[0]      // "cluster", "batch"
	rest := parts[1:]        // ["infobase", "locked"] or ["extension", "installed"]

	// Map service short names to full service names
	var serviceName string
	switch service {
	case "cluster":
		serviceName = "cluster-service"
	case "batch":
		serviceName = "batch-service"
	default:
		serviceName = service
	}

	// Join the rest with colons
	resourceAction := strings.Join(rest, ":")

	return fmt.Sprintf("events:%s:%s", serviceName, resourceAction)
}

// --- Predefined Behavior Presets ---

// HappyPathBehaviors returns behaviors for successful workflow
func HappyPathBehaviors() map[string]EventBehavior {
	return map[string]EventBehavior{
		"cluster.infobase.lock": {
			ResponseEvent: "cluster.infobase.locked",
			Delay:         100 * time.Millisecond,
			ResponsePayload: map[string]interface{}{
				"status": "locked",
			},
		},
		"cluster.sessions.terminate": {
			ResponseEvent: "cluster.sessions.closed",
			Delay:         500 * time.Millisecond,
			ResponsePayload: map[string]interface{}{
				"terminated_count": 5,
			},
		},
		"batch.extension.install": {
			ResponseEvent: "batch.extension.installed",
			Delay:         2 * time.Second,
			ResponsePayload: map[string]interface{}{
				"duration_seconds": 2.0,
				"status":           "installed",
			},
		},
		"cluster.infobase.unlock": {
			ResponseEvent: "cluster.infobase.unlocked",
			Delay:         100 * time.Millisecond,
			ResponsePayload: map[string]interface{}{
				"status": "unlocked",
			},
		},
	}
}

// LockFailedBehaviors returns behaviors where lock operation fails
func LockFailedBehaviors() map[string]EventBehavior {
	return map[string]EventBehavior{
		"cluster.infobase.lock": {
			ResponseEvent: "cluster.infobase.locked",
			Delay:         100 * time.Millisecond,
			FailureRate:   1.0, // Always fail
		},
	}
}

// InstallFailedBehaviors returns behaviors where install operation fails
func InstallFailedBehaviors() map[string]EventBehavior {
	behaviors := HappyPathBehaviors()
	behaviors["batch.extension.install"] = EventBehavior{
		ResponseEvent: "batch.extension.installed",
		Delay:         500 * time.Millisecond,
		FailureRate:   1.0, // Always fail
	}
	return behaviors
}

// TerminateTimeoutBehaviors returns behaviors where terminate times out
func TerminateTimeoutBehaviors() map[string]EventBehavior {
	behaviors := HappyPathBehaviors()
	behaviors["cluster.sessions.terminate"] = EventBehavior{
		ResponseEvent: "cluster.sessions.closed",
		TimeoutRate:   1.0, // Never respond (simulate timeout)
	}
	return behaviors
}
