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
	ready      chan struct{} // Signal when subscriptions are established
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
		ready:      make(chan struct{}),
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

	// Signal ready AFTER subscriptions are established
	close(m.ready)

	return m.subscriber.Run(ctx)
}

// WaitReady blocks until the responder is ready to handle events
func (m *MockEventResponder) WaitReady(timeout time.Duration) error {
	select {
	case <-m.ready:
		return nil
	case <-time.After(timeout):
		return fmt.Errorf("responder did not become ready within %v", timeout)
	}
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

		// Special case: "installed" → "install"
		if strings.HasSuffix(failedEvent, "lled") {
			base := strings.TrimSuffix(failedEvent, "led")  // "installed" → "instal"
			failedEvent = base + "l.failed"                   // "instal" → "install.failed"
		} else {
			// General case: remove "ed"
			base := strings.TrimSuffix(failedEvent, "ed")
			failedEvent = base + ".failed"
		}
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

// UnlockRetriesBehaviors returns behaviors where unlock fails N times then succeeds
func UnlockRetriesBehaviors(failCount int) map[string]EventBehavior {
	behaviors := HappyPathBehaviors()

	// Create a stateful behavior that tracks attempts
	// Note: This is a simplified version. In real implementation,
	// we would need more complex state tracking per correlation_id
	// For now, we'll use FailureRate as approximation

	if failCount > 0 {
		// Set FailureRate to simulate N failures
		// This is simplified - real implementation would need counter per correlation_id
		behaviors["cluster.infobase.unlock"] = EventBehavior{
			ResponseEvent: "cluster.infobase.unlocked",
			Delay:         100 * time.Millisecond,
			FailureRate:   0.7, // 70% failure rate (approximation)
		}
	}

	return behaviors
}

// DuplicateEventBehaviors returns behaviors that publish duplicate events
// This is used to test deduplication in State Machine
func DuplicateEventBehaviors() map[string]EventBehavior {
	return HappyPathBehaviors()
	// Note: Duplicate publishing is handled externally in tests
	// This function exists for consistency
}
