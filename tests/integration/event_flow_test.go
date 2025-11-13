package integration

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"

	"github.com/commandcenter1c/commandcenter/shared/events"
)

/*
INTEGRATION TEST: Event Flow End-to-End (Simplified)

Этот тест проверяет БАЗОВЫЙ event flow через Redis без internal imports:
1. Publisher публикует событие в Redis
2. Subscriber получает событие
3. Проверяем корректность данных и correlation_id
4. Проверяем idempotency через Redis SetNX

Это упрощенная версия без cluster-service internal handlers.
Полный E2E тест с реальными сервисами требует запуска HTTP/gRPC endpoints.
*/

// TestEventFlow_PublishSubscribe tests basic event flow through Redis
func TestEventFlow_PublishSubscribe(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	ctx := context.Background()
	logger := watermill.NewStdLogger(false, false)

	// Connect to test Redis
	redisClient := redis.NewClient(&redis.Options{
		Addr:     "localhost:6380",
		Password: "",
		DB:       1,
	})
	defer redisClient.Close()

	// Check Redis availability
	_, err := redisClient.Ping(ctx).Result()
	if err != nil {
		t.Skipf("Test Redis not available: %v\nRun: docker run -d --name redis-test -p 6380:6379 redis:7-alpine", err)
	}

	// Cleanup
	redisClient.FlushDB(ctx)

	t.Log("✅ Connected to test Redis")

	// =============================================================================
	// TEST: Event Publishing and Subscription
	// =============================================================================

	publisher, err := events.NewPublisher(redisClient, "test-publisher", logger)
	assert.NoError(t, err)

	// Channel for receiving events
	eventReceived := make(chan map[string]interface{}, 1)

	// Setup subscriber
	subscriber, err := events.NewSubscriber(redisClient, "test-subscriber", logger)
	assert.NoError(t, err)

	testChannel := "events:test:sample"

	err = subscriber.Subscribe(testChannel, func(ctx context.Context, envelope *events.Envelope) error {
		var payload map[string]interface{}
		if err := json.Unmarshal(envelope.Payload, &payload); err != nil {
			return err
		}

		t.Logf("📥 Event received: correlation_id=%s, type=%s", envelope.CorrelationID, envelope.EventType)
		eventReceived <- payload
		return nil
	})
	assert.NoError(t, err)

	// Start subscriber router in background
	go subscriber.Run(ctx)

	// Give subscriber time to connect and start
	time.Sleep(500 * time.Millisecond)

	// Publish test event
	correlationID := "test-correlation-123"
	testPayload := map[string]interface{}{
		"action": "test",
		"value":  42,
		"status": "success",
	}

	t.Log("📤 Publishing test event...")
	err = publisher.Publish(ctx, testChannel, "test.event", testPayload, correlationID)
	assert.NoError(t, err)

	// Wait for event
	select {
	case payload := <-eventReceived:
		t.Log("✅ Event received successfully!")
		assert.Equal(t, "test", payload["action"])
		assert.Equal(t, float64(42), payload["value"])
		assert.Equal(t, "success", payload["status"])

	case <-time.After(2 * time.Second):
		t.Fatal("❌ Timeout waiting for event")
	}

	t.Log("✅ Basic event flow test completed")
}

// TestIdempotency_RedisSetNX tests Redis-based idempotency
func TestIdempotency_RedisSetNX(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	ctx := context.Background()

	redisClient := redis.NewClient(&redis.Options{
		Addr: "localhost:6380",
		DB:   1,
	})
	defer redisClient.Close()

	_, err := redisClient.Ping(ctx).Result()
	if err != nil {
		t.Skipf("Test Redis not available: %v", err)
	}

	// Cleanup
	redisClient.FlushDB(ctx)

	t.Log("Testing Redis SetNX idempotency...")

	correlationID := "corr-123"
	eventType := "lock"
	dedupKey := "dedupe:" + correlationID + ":" + eventType

	// First attempt - should succeed (key doesn't exist)
	isFirst, err := redisClient.SetNX(ctx, dedupKey, "1", 10*time.Minute).Result()
	assert.NoError(t, err)
	assert.True(t, isFirst, "First SetNX should return true")
	t.Log("✅ First attempt: SetNX returned true (new operation)")

	// Second attempt - should fail (key exists)
	isFirst, err = redisClient.SetNX(ctx, dedupKey, "1", 10*time.Minute).Result()
	assert.NoError(t, err)
	assert.False(t, isFirst, "Second SetNX should return false (duplicate)")
	t.Log("✅ Second attempt: SetNX returned false (duplicate detected)")

	// Verify TTL
	ttl, err := redisClient.TTL(ctx, dedupKey).Result()
	assert.NoError(t, err)
	assert.Greater(t, ttl.Seconds(), 0.0, "TTL should be set")
	assert.LessOrEqual(t, ttl.Seconds(), 600.0, "TTL should be <= 10 minutes")
	t.Logf("✅ TTL verified: %.0f seconds", ttl.Seconds())

	t.Log("✅ Idempotency test completed")
}

// TestCorrelationID_Tracing tests end-to-end correlation ID propagation
func TestCorrelationID_Tracing(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	ctx := context.Background()
	logger := watermill.NewStdLogger(false, false)

	redisClient := redis.NewClient(&redis.Options{
		Addr: "localhost:6380",
		DB:   1,
	})
	defer redisClient.Close()

	_, err := redisClient.Ping(ctx).Result()
	if err != nil {
		t.Skipf("Test Redis not available: %v", err)
	}

	redisClient.FlushDB(ctx)

	t.Log("Testing correlation ID end-to-end tracing...")

	publisher, err := events.NewPublisher(redisClient, "test-publisher", logger)
	assert.NoError(t, err)

	correlationIDReceived := make(chan string, 1)

	subscriber, err := events.NewSubscriber(redisClient, "test-subscriber", logger)
	assert.NoError(t, err)

	testChannel := "events:test:tracing"

	err = subscriber.Subscribe(testChannel, func(ctx context.Context, envelope *events.Envelope) error {
		t.Logf("📥 Received event with correlation_id: %s", envelope.CorrelationID)
		correlationIDReceived <- envelope.CorrelationID
		return nil
	})
	assert.NoError(t, err)

	// Start subscriber router in background
	go subscriber.Run(ctx)

	time.Sleep(500 * time.Millisecond)

	// Publish with specific correlation ID
	expectedCorrelationID := "batch-op-123-task-456"
	testPayload := map[string]string{"test": "data"}

	t.Logf("📤 Publishing with correlation_id: %s", expectedCorrelationID)
	err = publisher.Publish(ctx, testChannel, "test.trace", testPayload, expectedCorrelationID)
	assert.NoError(t, err)

	// Verify correlation ID preserved
	select {
	case receivedID := <-correlationIDReceived:
		assert.Equal(t, expectedCorrelationID, receivedID, "Correlation ID should be preserved")
		t.Log("✅ Correlation ID correctly propagated end-to-end")

	case <-time.After(2 * time.Second):
		t.Fatal("❌ Timeout waiting for event")
	}

	t.Log("✅ Correlation ID tracing test completed")
}

// TestMultipleSubscribers tests event fanout to multiple subscribers
func TestMultipleSubscribers(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	ctx := context.Background()
	logger := watermill.NewStdLogger(false, false)

	redisClient := redis.NewClient(&redis.Options{
		Addr: "localhost:6380",
		DB:   1,
	})
	defer redisClient.Close()

	_, err := redisClient.Ping(ctx).Result()
	if err != nil {
		t.Skipf("Test Redis not available: %v", err)
	}

	redisClient.FlushDB(ctx)

	t.Log("Testing event fanout to multiple subscribers...")

	publisher, err := events.NewPublisher(redisClient, "test-publisher", logger)
	assert.NoError(t, err)

	testChannel := "events:test:fanout"

	// Create multiple subscribers
	subscriber1Received := make(chan bool, 1)
	subscriber2Received := make(chan bool, 1)

	subscriber1, err := events.NewSubscriber(redisClient, "subscriber-1", logger)
	assert.NoError(t, err)

	err = subscriber1.Subscribe(testChannel, func(ctx context.Context, envelope *events.Envelope) error {
		t.Log("📥 Subscriber 1 received event")
		subscriber1Received <- true
		return nil
	})
	assert.NoError(t, err)

	subscriber2, err := events.NewSubscriber(redisClient, "subscriber-2", logger)
	assert.NoError(t, err)

	err = subscriber2.Subscribe(testChannel, func(ctx context.Context, envelope *events.Envelope) error {
		t.Log("📥 Subscriber 2 received event")
		subscriber2Received <- true
		return nil
	})
	assert.NoError(t, err)

	// Start both subscriber routers in background
	go subscriber1.Run(ctx)
	go subscriber2.Run(ctx)

	time.Sleep(500 * time.Millisecond)

	// Publish one event
	testPayload := map[string]string{"message": "fanout test"}
	t.Log("📤 Publishing event to multiple subscribers...")
	err = publisher.Publish(ctx, testChannel, "test.fanout", testPayload, "corr-fanout")
	assert.NoError(t, err)

	// Both subscribers should receive the event
	timeout := time.After(2 * time.Second)
	subscriber1Got := false
	subscriber2Got := false

	for i := 0; i < 2; i++ {
		select {
		case <-subscriber1Received:
			subscriber1Got = true
		case <-subscriber2Received:
			subscriber2Got = true
		case <-timeout:
			t.Fatal("❌ Timeout waiting for fanout events")
		}
	}

	assert.True(t, subscriber1Got, "Subscriber 1 should receive event")
	assert.True(t, subscriber2Got, "Subscriber 2 should receive event")

	t.Log("✅ Event fanout test completed (both subscribers received)")
}

/*
SUMMARY:

Эти integration тесты проверяют:
✅ Базовый event flow (Publish → Subscribe)
✅ Redis SetNX idempotency mechanism
✅ Correlation ID end-to-end tracing
✅ Event fanout to multiple subscribers

Что НЕ покрыто (требуется полный E2E):
⚠️ Real cluster-service event handlers
⚠️ PostgreSQL Task status updates
⚠️ Full workflow: command → processing → event → DB update

Для полного E2E теста нужно:
1. Запустить cluster-service HTTP/gRPC endpoint
2. Запустить Orchestrator Django app
3. Apply migrations к test PostgreSQL
4. Тестировать через HTTP API calls
5. Проверять DB state в PostgreSQL

Эти тесты - это БАЗА для понимания integration testing подхода.
*/
