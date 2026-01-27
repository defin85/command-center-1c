//go:build integration

package statemachine

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/worker/test/integration/helpers"
)

/*
INTEGRATION TESTS: Pub/Sub End-to-End для Worker State Machine

Тестирование полного цикла Redis Pub/Sub между сервисами:
1. Публикация команды lock -> получение события locked
2. Публикация команды unlock -> получение события unlocked
3. Корректная фильтрация по correlation_id
4. Idempotency (дублирование команды не создает дубликат события)

Запуск:
  go test -tags=integration -v ./test/integration/statemachine/ -run TestPubSub

Требования:
  - Docker для testcontainers ИЛИ
  - Локальный Redis на localhost:6380 (docker-compose.test.yml)
*/

// =============================================================================
// Test 1: Lock/Unlock Full Cycle
// =============================================================================

func TestPubSubIntegration_LockUnlock(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	t.Log("========================================")
	t.Log("Pub/Sub Integration Test: Lock/Unlock Cycle")
	t.Log("========================================")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Setup Redis (prefer localhost, fallback to testcontainers)
	redisClient := setupRedisForTest(t, ctx)

	// Setup Event Bus - Publisher and Subscribers
	publisher, commandSubscriber := helpers.SetupEventBus(t, redisClient)
	_, eventSubscriber := helpers.SetupEventBus(t, redisClient)

	// Generate unique correlation ID
	correlationID := fmt.Sprintf("test-pubsub-lock-%d", time.Now().UnixNano())
	t.Logf("Correlation ID: %s", correlationID)

	// Channel to receive lock event
	lockEventReceived := make(chan *events.Envelope, 1)

	// Setup event listener BEFORE publishing command
	eventSubscriber.Subscribe("events:worker:infobase:locked", func(ctx context.Context, envelope *events.Envelope) error {
		// Filter by correlation_id
		if envelope.CorrelationID == correlationID {
			t.Logf("Received locked event: message_id=%s, correlation_id=%s",
				envelope.MessageID, envelope.CorrelationID)
			select {
			case lockEventReceived <- envelope:
			default:
				// Channel full, duplicate event
			}
		}
		return nil
	})

	// Start event subscriber in background
	eventSubCtx, eventSubCancel := context.WithCancel(ctx)
	defer eventSubCancel()
	go eventSubscriber.Run(eventSubCtx)

	// Setup Mock Responder (simulates worker)
	responder := helpers.NewMockEventResponder(
		publisher,
		commandSubscriber,
		helpers.HappyPathBehaviors(),
	)
	responder.SetVerbose(testing.Verbose())

	responderCtx, responderCancel := context.WithCancel(ctx)
	defer responderCancel()
	go responder.Run(responderCtx)

	// Wait for subscribers to be ready
	time.Sleep(500 * time.Millisecond)

	// =============================================================================
	// Step 1: Publish LOCK command
	// =============================================================================

	t.Log("Step 1: Publishing lock command...")

	lockPayload := map[string]interface{}{
		"cluster_id":  "test-cluster-001",
		"infobase_id": "test-infobase-001",
		"database_id": "test-db-001",
		"reason":      "integration test",
	}

	err := publisher.Publish(
		ctx,
		"commands:worker:infobase:lock",
		"cluster.infobase.lock",
		lockPayload,
		correlationID,
	)
	require.NoError(t, err, "Failed to publish lock command")
	t.Log("Lock command published successfully")

	// =============================================================================
	// Step 2: Wait for LOCKED event
	// =============================================================================

	t.Log("Step 2: Waiting for locked event...")

	select {
	case envelope := <-lockEventReceived:
		t.Log("Locked event received!")

		// Verify correlation_id
		assert.Equal(t, correlationID, envelope.CorrelationID,
			"Correlation ID should match")

		// Verify event type
		assert.Equal(t, "cluster.infobase.locked", envelope.EventType,
			"Event type should be cluster.infobase.locked")

		// Verify payload
		var payload map[string]interface{}
		err := json.Unmarshal(envelope.Payload, &payload)
		require.NoError(t, err)
		assert.Equal(t, "locked", payload["status"])

		t.Logf("Locked event verified: message_id=%s", envelope.MessageID)

	case <-time.After(5 * time.Second):
		t.Fatal("Timeout waiting for locked event")
	}

	// =============================================================================
	// Step 3: Publish UNLOCK command and verify
	// =============================================================================

	t.Log("Step 3: Publishing unlock command...")

	// Channel to receive unlock event
	unlockEventReceived := make(chan *events.Envelope, 1)

	// Add unlock event listener
	_, unlockEventSub := helpers.SetupEventBus(t, redisClient)
	unlockEventSub.Subscribe("events:worker:infobase:unlocked", func(ctx context.Context, envelope *events.Envelope) error {
		if envelope.CorrelationID == correlationID {
			t.Logf("Received unlocked event: message_id=%s", envelope.MessageID)
			select {
			case unlockEventReceived <- envelope:
			default:
			}
		}
		return nil
	})

	unlockSubCtx, unlockSubCancel := context.WithCancel(ctx)
	defer unlockSubCancel()
	go unlockEventSub.Run(unlockSubCtx)

	time.Sleep(300 * time.Millisecond)

	unlockPayload := map[string]interface{}{
		"cluster_id":  "test-cluster-001",
		"infobase_id": "test-infobase-001",
		"database_id": "test-db-001",
	}

	err = publisher.Publish(
		ctx,
		"commands:worker:infobase:unlock",
		"cluster.infobase.unlock",
		unlockPayload,
		correlationID,
	)
	require.NoError(t, err, "Failed to publish unlock command")

	select {
	case envelope := <-unlockEventReceived:
		assert.Equal(t, correlationID, envelope.CorrelationID)
		assert.Equal(t, "cluster.infobase.unlocked", envelope.EventType)
		t.Log("Unlocked event received and verified!")
	case <-time.After(5 * time.Second):
		t.Fatal("Timeout waiting for unlocked event")
	}

	t.Log("========================================")
	t.Log("Test PASSED: Lock/Unlock cycle completed")
	t.Log("========================================")
}

// =============================================================================
// Test 2: Correlation ID Filtering
// =============================================================================

func TestPubSubIntegration_CorrelationFiltering(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	t.Log("========================================")
	t.Log("Pub/Sub Integration Test: Correlation ID Filtering")
	t.Log("========================================")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	redisClient := setupRedisForTest(t, ctx)

	publisher, commandSubscriber := helpers.SetupEventBus(t, redisClient)
	_, eventSubscriber := helpers.SetupEventBus(t, redisClient)

	// Two different correlation IDs
	correlationID1 := fmt.Sprintf("test-corr-1-%d", time.Now().UnixNano())
	correlationID2 := fmt.Sprintf("test-corr-2-%d", time.Now().UnixNano())

	t.Logf("Correlation ID 1: %s", correlationID1)
	t.Logf("Correlation ID 2: %s", correlationID2)

	// Track events by correlation ID
	var mu sync.Mutex
	receivedByCorrelation := make(map[string][]*events.Envelope)

	eventSubscriber.Subscribe("events:worker:infobase:locked", func(ctx context.Context, envelope *events.Envelope) error {
		mu.Lock()
		defer mu.Unlock()
		receivedByCorrelation[envelope.CorrelationID] = append(
			receivedByCorrelation[envelope.CorrelationID],
			envelope,
		)
		t.Logf("Received event for correlation_id=%s", envelope.CorrelationID)
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
	// Publish commands with different correlation IDs
	// =============================================================================

	t.Log("Publishing commands with different correlation IDs...")

	// Publish command 1
	err := publisher.Publish(
		ctx,
		"commands:worker:infobase:lock",
		"cluster.infobase.lock",
		map[string]interface{}{"cluster_id": "cluster-1", "infobase_id": "ib-1"},
		correlationID1,
	)
	require.NoError(t, err)

	// Publish command 2
	err = publisher.Publish(
		ctx,
		"commands:worker:infobase:lock",
		"cluster.infobase.lock",
		map[string]interface{}{"cluster_id": "cluster-2", "infobase_id": "ib-2"},
		correlationID2,
	)
	require.NoError(t, err)

	// Wait for events
	time.Sleep(2 * time.Second)

	// =============================================================================
	// Verify filtering
	// =============================================================================

	mu.Lock()
	events1 := receivedByCorrelation[correlationID1]
	events2 := receivedByCorrelation[correlationID2]
	mu.Unlock()

	assert.Len(t, events1, 1, "Should receive exactly 1 event for correlation ID 1")
	assert.Len(t, events2, 1, "Should receive exactly 1 event for correlation ID 2")

	// Verify each event has correct correlation ID
	if len(events1) > 0 {
		assert.Equal(t, correlationID1, events1[0].CorrelationID)
	}
	if len(events2) > 0 {
		assert.Equal(t, correlationID2, events2[0].CorrelationID)
	}

	t.Log("========================================")
	t.Log("Test PASSED: Correlation filtering works correctly")
	t.Log("========================================")
}
