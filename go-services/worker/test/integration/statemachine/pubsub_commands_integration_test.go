//go:build integration

package statemachine

import (
	"context"
	"encoding/json"
	"fmt"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/worker/test/integration/helpers"
)

// =============================================================================
// Test 5: Session Terminate Command/Event Cycle
// =============================================================================

func TestPubSubIntegration_SessionTerminate(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	t.Log("========================================")
	t.Log("Pub/Sub Integration Test: Session Terminate")
	t.Log("========================================")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	redisClient := setupRedisForTest(t, ctx)

	publisher, commandSubscriber := helpers.SetupEventBus(t, redisClient)
	_, eventSubscriber := helpers.SetupEventBus(t, redisClient)

	correlationID := fmt.Sprintf("test-terminate-%d", time.Now().UnixNano())

	// Channel to receive sessions closed event
	sessionsClosedReceived := make(chan *events.Envelope, 1)

	eventSubscriber.Subscribe("events:worker:sessions:closed", func(ctx context.Context, envelope *events.Envelope) error {
		if envelope.CorrelationID == correlationID {
			t.Logf("Received sessions:closed event: message_id=%s", envelope.MessageID)
			select {
			case sessionsClosedReceived <- envelope:
			default:
			}
		}
		return nil
	})

	// Start subscribers
	eventSubCtx, eventSubCancel := context.WithCancel(ctx)
	defer eventSubCancel()
	go eventSubscriber.Run(eventSubCtx)

	responder := helpers.NewMockEventResponder(
		publisher,
		commandSubscriber,
		helpers.HappyPathBehaviors(),
	)
	responder.SetVerbose(testing.Verbose())

	responderCtx, responderCancel := context.WithCancel(ctx)
	defer responderCancel()
	go responder.Run(responderCtx)

	time.Sleep(500 * time.Millisecond)

	// Publish terminate command
	t.Log("Publishing sessions:terminate command...")

	terminatePayload := map[string]interface{}{
		"cluster_id":  "test-cluster",
		"infobase_id": "test-infobase",
		"session_ids": []string{"session-1", "session-2", "session-3"},
	}

	err := publisher.Publish(
		ctx,
		"commands:worker:sessions:terminate",
		"cluster.sessions.terminate",
		terminatePayload,
		correlationID,
	)
	require.NoError(t, err)

	// Wait for event
	select {
	case envelope := <-sessionsClosedReceived:
		assert.Equal(t, correlationID, envelope.CorrelationID)
		assert.Equal(t, "cluster.sessions.closed", envelope.EventType)

		var payload map[string]interface{}
		err := json.Unmarshal(envelope.Payload, &payload)
		require.NoError(t, err)

		// Verify terminated_count from mock responder
		terminatedCount, ok := payload["terminated_count"]
		assert.True(t, ok, "Should have terminated_count in payload")
		t.Logf("Terminated sessions: %v", terminatedCount)

	case <-time.After(5 * time.Second):
		t.Fatal("Timeout waiting for sessions:closed event")
	}

	t.Log("========================================")
	t.Log("Test PASSED: Session terminate cycle completed")
	t.Log("========================================")
}

// =============================================================================
// Test 6: Extension Install Command/Event Cycle
// =============================================================================

func TestPubSubIntegration_ExtensionInstall(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	t.Log("========================================")
	t.Log("Pub/Sub Integration Test: Extension Install")
	t.Log("========================================")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	redisClient := setupRedisForTest(t, ctx)

	publisher, commandSubscriber := helpers.SetupEventBus(t, redisClient)
	_, eventSubscriber := helpers.SetupEventBus(t, redisClient)

	correlationID := fmt.Sprintf("test-install-%d", time.Now().UnixNano())

	// Channel to receive extension installed event
	extensionInstalledReceived := make(chan *events.Envelope, 1)

	eventSubscriber.Subscribe("events:worker:extension:installed", func(ctx context.Context, envelope *events.Envelope) error {
		if envelope.CorrelationID == correlationID {
			t.Logf("Received extension:installed event: message_id=%s", envelope.MessageID)
			select {
			case extensionInstalledReceived <- envelope:
			default:
			}
		}
		return nil
	})

	// Start subscribers
	eventSubCtx, eventSubCancel := context.WithCancel(ctx)
	defer eventSubCancel()
	go eventSubscriber.Run(eventSubCtx)

	responder := helpers.NewMockEventResponder(
		publisher,
		commandSubscriber,
		helpers.HappyPathBehaviors(),
	)
	responder.SetVerbose(testing.Verbose())

	responderCtx, responderCancel := context.WithCancel(ctx)
	defer responderCancel()
	go responder.Run(responderCtx)

	time.Sleep(500 * time.Millisecond)

	// Publish install command
	t.Log("Publishing extension:install command...")

	installPayload := map[string]interface{}{
		"database_id":    "test-db",
		"extension_path": "/extensions/test.cfe",
		"extension_name": "TestExtension",
	}

	err := publisher.Publish(
		ctx,
		"commands:worker:extension:install",
		"batch.extension.install",
		installPayload,
		correlationID,
	)
	require.NoError(t, err)

	// Wait for event (longer timeout due to install delay in mock)
	select {
	case envelope := <-extensionInstalledReceived:
		assert.Equal(t, correlationID, envelope.CorrelationID)
		assert.Equal(t, "batch.extension.installed", envelope.EventType)

		var payload map[string]interface{}
		err := json.Unmarshal(envelope.Payload, &payload)
		require.NoError(t, err)

		assert.Equal(t, "installed", payload["status"])
		t.Logf("Extension installed, duration: %v seconds", payload["duration_seconds"])

	case <-time.After(10 * time.Second):
		t.Fatal("Timeout waiting for extension:installed event")
	}

	t.Log("========================================")
	t.Log("Test PASSED: Extension install cycle completed")
	t.Log("========================================")
}
