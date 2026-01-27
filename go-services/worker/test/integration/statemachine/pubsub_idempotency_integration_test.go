//go:build integration

package statemachine

import (
	"context"
	"fmt"
	"sync/atomic"
	"testing"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/worker/test/integration/helpers"
)

// =============================================================================
// Test 3: Idempotency (Duplicate Commands)
// =============================================================================

func TestPubSubIntegration_Idempotency(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	t.Log("========================================")
	t.Log("Pub/Sub Integration Test: Idempotency")
	t.Log("========================================")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	redisClient := setupRedisForTest(t, ctx)

	publisher, commandSubscriber := helpers.SetupEventBus(t, redisClient)
	_, eventSubscriber := helpers.SetupEventBus(t, redisClient)

	correlationID := fmt.Sprintf("test-idem-%d", time.Now().UnixNano())
	idempotencyKey := events.GenerateIdempotencyKey(correlationID, "cluster.infobase.lock")

	t.Logf("Correlation ID: %s", correlationID)
	t.Logf("Idempotency Key: %s", idempotencyKey)

	// Track event count
	var eventCount int32

	eventSubscriber.Subscribe("events:worker:infobase:locked", func(ctx context.Context, envelope *events.Envelope) error {
		if envelope.CorrelationID == correlationID {
			atomic.AddInt32(&eventCount, 1)
			t.Logf("Received event #%d for correlation_id=%s", atomic.LoadInt32(&eventCount), correlationID)
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

	// =============================================================================
	// Publish SAME command MULTIPLE times with idempotency key
	// =============================================================================

	t.Log("Publishing duplicate commands with same idempotency key...")

	payload := map[string]interface{}{
		"cluster_id":  "test-cluster",
		"infobase_id": "test-infobase",
	}

	metadata := map[string]interface{}{
		"idempotency_key": idempotencyKey,
	}

	// Publish 3 duplicate commands
	for i := 0; i < 3; i++ {
		err := publisher.PublishWithMetadata(
			ctx,
			"commands:worker:infobase:lock",
			"cluster.infobase.lock",
			payload,
			correlationID,
			metadata,
		)
		require.NoError(t, err, "Failed to publish command %d", i+1)
		t.Logf("Published command #%d", i+1)
	}

	// Wait for processing
	time.Sleep(2 * time.Second)

	// =============================================================================
	// Verify idempotency
	// =============================================================================

	finalCount := atomic.LoadInt32(&eventCount)
	t.Logf("Total events received: %d", finalCount)

	// Note: Without idempotency middleware on the command handler,
	// we expect 3 events (one per command). This test verifies the
	// Pub/Sub mechanism works correctly. Idempotency should be
	// implemented in the command handler, not in Pub/Sub itself.
	//
	// For true idempotency, the Mock Responder (or real worker)
	// should check idempotency_key and skip duplicate processing.

	// Current expectation: We receive events for all commands
	// because MockEventResponder doesn't implement idempotency
	assert.Equal(t, int32(3), finalCount,
		"Without handler-level idempotency, all commands generate events")

	t.Log("========================================")
	t.Log("Test PASSED: Pub/Sub delivers all messages")
	t.Log("Note: Handler-level idempotency should filter duplicates")
	t.Log("========================================")
}

// =============================================================================
// Test 4: Idempotency with Middleware (Full E2E)
// =============================================================================

func TestPubSubIntegration_IdempotencyWithMiddleware(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	t.Log("========================================")
	t.Log("Pub/Sub Integration Test: Idempotency with Middleware")
	t.Log("========================================")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	redisClient := setupRedisForTest(t, ctx)

	// Use watermill logger (required for middleware)
	logger := watermill.NewStdLogger(false, false)

	// Create publisher
	publisher, err := events.NewPublisher(redisClient, "test-publisher", logger)
	require.NoError(t, err)
	defer publisher.Close()

	// Create subscriber with idempotency middleware
	subscriber, err := events.NewSubscriber(
		redisClient,
		fmt.Sprintf("idem-test-group-%d", time.Now().UnixNano()),
		logger,
	)
	require.NoError(t, err)
	defer subscriber.Close()

	// Add idempotency middleware (logger is required!)
	subscriber.Router().AddMiddleware(
		events.WithIdempotency(redisClient, 10*time.Second, logger),
	)

	correlationID := fmt.Sprintf("test-idem-mw-%d", time.Now().UnixNano())
	idempotencyKey := events.GenerateIdempotencyKey(correlationID, "test.idempotency")

	// Track handler calls
	var handlerCalls int32

	subscriber.Subscribe("test-idempotency-channel", func(ctx context.Context, envelope *events.Envelope) error {
		if envelope.CorrelationID == correlationID {
			atomic.AddInt32(&handlerCalls, 1)
			t.Logf("Handler called #%d", atomic.LoadInt32(&handlerCalls))
		}
		return nil
	})

	// Start subscriber
	subCtx, subCancel := context.WithCancel(ctx)
	defer subCancel()
	go subscriber.Run(subCtx)

	time.Sleep(500 * time.Millisecond)

	// Publish duplicate messages with idempotency key
	metadata := map[string]interface{}{
		"idempotency_key": idempotencyKey,
	}

	for i := 0; i < 3; i++ {
		err := publisher.PublishWithMetadata(
			ctx,
			"test-idempotency-channel",
			"test.idempotency",
			map[string]int{"iteration": i},
			correlationID,
			metadata,
		)
		require.NoError(t, err)
		t.Logf("Published message #%d", i+1)
		time.Sleep(200 * time.Millisecond) // Small delay between publishes
	}

	// Wait for processing
	time.Sleep(2 * time.Second)

	// Verify handler was called only once
	finalCalls := atomic.LoadInt32(&handlerCalls)
	assert.Equal(t, int32(1), finalCalls,
		"Handler should be called exactly once due to idempotency middleware")

	t.Log("========================================")
	t.Log("Test PASSED: Idempotency middleware prevents duplicate processing")
	t.Log("========================================")
}
