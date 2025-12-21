//go:build integration

package statemachine

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"

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

// =============================================================================
// Helper: Setup Redis for Tests
// =============================================================================

// setupRedisForTest creates a Redis client for tests.
// Tries localhost:6380 first (docker-compose.test.yml), then 6379, falls back to testcontainers.
func setupRedisForTest(t *testing.T, ctx context.Context) *redis.Client {
	// Try localhost Redis on test port first (docker-compose.test.yml)
	ports := []string{"6380", "6379"}

	for _, port := range ports {
		localClient := redis.NewClient(&redis.Options{
			Addr: "127.0.0.1:" + port,
			DB:   1, // Use DB 1 for tests to avoid conflicts
		})

		pingCtx, pingCancel := context.WithTimeout(ctx, 2*time.Second)
		err := localClient.Ping(pingCtx).Err()
		pingCancel()

		if err == nil {
			t.Logf("Using local Redis on localhost:%s", port)

			// Flush test DB
			if err := localClient.FlushDB(ctx).Err(); err != nil {
				t.Logf("Warning: Failed to flush test DB: %v", err)
			}

			t.Cleanup(func() {
				localClient.Close()
			})

			return localClient
		}

		localClient.Close()
	}

	// Fallback to testcontainers
	t.Log("Local Redis not available on ports 6380/6379, starting testcontainers...")

	redisReq := testcontainers.ContainerRequest{
		Image:        "redis:7-alpine",
		ExposedPorts: []string{"6379/tcp"},
		WaitingFor:   wait.ForListeningPort("6379/tcp").WithStartupTimeout(30 * time.Second),
	}

	redisContainer, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
		ContainerRequest: redisReq,
		Started:          true,
	})
	if err != nil {
		t.Skipf("Cannot start Redis container: %v. Start test Redis: docker-compose -f docker-compose.test.yml up -d redis-test", err)
	}

	t.Cleanup(func() {
		if err := redisContainer.Terminate(ctx); err != nil {
			t.Logf("Warning: Failed to terminate Redis container: %v", err)
		}
	})

	redisHost, err := redisContainer.Host(ctx)
	require.NoError(t, err)

	redisPort, err := redisContainer.MappedPort(ctx, "6379")
	require.NoError(t, err)

	redisAddr := fmt.Sprintf("%s:%s", redisHost, redisPort.Port())
	t.Logf("Redis container started: %s", redisAddr)

	client := redis.NewClient(&redis.Options{
		Addr: redisAddr,
		DB:   0,
	})

	// Verify connection
	require.NoError(t, client.Ping(ctx).Err())

	t.Cleanup(func() {
		client.Close()
	})

	return client
}
