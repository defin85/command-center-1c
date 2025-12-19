package statemachine

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
)

// publishCommand publishes a command event
func (sm *ExtensionInstallStateMachine) publishCommand(
	ctx context.Context,
	channel string,
	eventType string,
	payload interface{},
) error {

	// Get circuit breaker for this channel
	breaker := sm.getCircuitBreaker(channel)

	if breaker != nil {
		// Execute through circuit breaker
		_, err := breaker.Execute(func() (interface{}, error) {
			err := sm.publisher.Publish(ctx, channel, eventType, payload, sm.CorrelationID)
			if err != nil {
				return nil, err
			}

			fmt.Printf("[StateMachine] Published command: %s (correlation_id=%s)\n",
				eventType, sm.CorrelationID)

			return nil, nil
		})

		if err != nil {
			return fmt.Errorf("failed to publish command %s: %w", eventType, err)
		}

		return nil
	}

	// Fallback without circuit breaker (for other channels)
	err := sm.publisher.Publish(ctx, channel, eventType, payload, sm.CorrelationID)
	if err != nil {
		return fmt.Errorf("failed to publish command %s: %w", eventType, err)
	}

	fmt.Printf("[StateMachine] Published command: %s (correlation_id=%s)\n",
		eventType, sm.CorrelationID)

	return nil
}

// waitForEvent waits for specific event with timeout and retry logic
func (sm *ExtensionInstallStateMachine) waitForEvent(
	ctx context.Context,
	expectedEventType string,
	timeout time.Duration,
) (*events.Envelope, error) {

	// First, check event buffer
	sm.mu.Lock()
	for i, buffered := range sm.eventBuffer {
		if buffered.EventType == expectedEventType {
			// Found in buffer - remove and return
			sm.eventBuffer = append(sm.eventBuffer[:i], sm.eventBuffer[i+1:]...)
			sm.mu.Unlock()

			fmt.Printf("[StateMachine] Event found in buffer: %s\n", expectedEventType)
			return buffered, nil
		}
	}
	sm.mu.Unlock()

	// Then wait for new events
	for attempt := 1; attempt <= sm.config.MaxRetries; attempt++ {

		// Use anonymous function for immediate defer cancel()
		envelope, err := func() (*events.Envelope, error) {
			timeoutCtx, cancel := context.WithTimeout(ctx, timeout)
			defer cancel() // Called immediately after each iteration

			select {
			case envelope := <-sm.eventChan:
				if envelope.EventType == expectedEventType {
					if sm.isEventProcessed(envelope.MessageID) {
						fmt.Printf("[StateMachine] Duplicate event ignored: %s\n", envelope.MessageID)
						return nil, nil // Signal to retry
					}

					sm.markEventProcessed(envelope.MessageID)
					fmt.Printf("[StateMachine] Received event: %s (correlation_id=%s)\n",
						expectedEventType, sm.CorrelationID)

					return envelope, nil
				}

				// Check for failure events (e.g., "cluster.infobase.lock-failed")
				if isFailureEvent(envelope.EventType, expectedEventType) {
					sm.markEventProcessed(envelope.MessageID)
					fmt.Printf("[StateMachine] Received failure event: %s (expected: %s)\n",
						envelope.EventType, expectedEventType)

					// Extract error message from payload
					errorMsg := "operation failed"
					var payloadData map[string]interface{}
					if err := json.Unmarshal(envelope.Payload, &payloadData); err == nil {
						if errPayload, ok := payloadData["error"].(string); ok {
							errorMsg = errPayload
						}
					}

					return nil, fmt.Errorf("%s: %s", envelope.EventType, errorMsg)
				}

				// Unexpected event - save to buffer
				sm.mu.Lock()
				sm.eventBuffer = append(sm.eventBuffer, envelope)
				sm.mu.Unlock()

				fmt.Printf("[StateMachine] Unexpected event buffered: %s (expected: %s)\n",
					envelope.EventType, expectedEventType)

				return nil, nil // Continue waiting

			case <-timeoutCtx.Done():
				return nil, fmt.Errorf("timeout on attempt %d/%d", attempt, sm.config.MaxRetries)
			}
		}()

		if err == nil && envelope != nil {
			return envelope, nil
		}

		// If we got an error (not timeout), return immediately
		if err != nil {
			return nil, err
		}

		// Retry with exponential backoff
		if attempt < sm.config.MaxRetries {
			fmt.Printf("[StateMachine] Timeout waiting for %s, retry %d/%d\n",
				expectedEventType, attempt, sm.config.MaxRetries)

			delay := sm.calculateBackoff(attempt)
			time.Sleep(delay)
		}
	}

	return nil, fmt.Errorf("timeout waiting for event %s after %d attempts",
		expectedEventType, sm.config.MaxRetries)
}

// isFailureEvent checks if an event is a failure variant of the expected event
func isFailureEvent(eventType, expectedEventType string) bool {
	// Map expected events to their failure counterparts
	failureMap := map[string]string{
		"cluster.infobase.locked":   "cluster.infobase.lock-failed",
		"cluster.sessions.closed":   "cluster.sessions.terminate-failed",
		"cluster.infobase.unlocked": "cluster.infobase.unlock-failed",
		"batch.extension.installed": "batch.extension.install-failed",
	}

	if failureType, ok := failureMap[expectedEventType]; ok {
		return eventType == failureType
	}

	return false
}

// calculateBackoff calculates exponential backoff with jitter
func (sm *ExtensionInstallStateMachine) calculateBackoff(attempt int) time.Duration {
	delay := sm.config.RetryInitialDelay * time.Duration(1<<uint(attempt-1))
	if delay > sm.config.RetryMaxDelay {
		delay = sm.config.RetryMaxDelay
	}

	// Add jitter (±10%)
	jitter := time.Duration(float64(delay) * 0.1)
	return delay + jitter
}

// isEventProcessed checks if event was already processed
func (sm *ExtensionInstallStateMachine) isEventProcessed(messageID string) bool {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	return sm.processedEvents[messageID]
}

// markEventProcessed marks event as processed
func (sm *ExtensionInstallStateMachine) markEventProcessed(messageID string) {
	sm.mu.Lock()
	defer sm.mu.Unlock()
	sm.processedEvents[messageID] = true
}
