package events_test

import (
	"context"
	"encoding/json"
	"sync"
	"testing"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestIntegration_PublishSubscribe tests the full publish-subscribe flow
func TestIntegration_PublishSubscribe(t *testing.T) {
	redisClient := createTestRedisClient(t)
	defer redisClient.Close()

	logger := watermill.NewStdLogger(false, false)

	// Create publisher
	publisher, err := events.NewPublisher(redisClient, "integration-service", logger)
	require.NoError(t, err)
	defer publisher.Close()

	// Create subscriber
	subscriber, err := events.NewSubscriber(redisClient, "integration-consumer", logger)
	require.NoError(t, err)
	defer subscriber.Close()

	// Track received messages
	receivedMessages := make(chan *events.Envelope, 10)
	handler := func(ctx context.Context, envelope *events.Envelope) error {
		receivedMessages <- envelope
		return nil
	}

	err = subscriber.Subscribe("integration-channel", handler)
	require.NoError(t, err)

	// Start subscriber
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go func() {
		subscriber.Run(ctx)
	}()

	time.Sleep(200 * time.Millisecond)

	// Publish multiple messages
	type TestPayload struct {
		ID      int    `json:"id"`
		Message string `json:"message"`
	}

	numMessages := 5
	correlationID := events.GenerateCorrelationID()

	for i := 0; i < numMessages; i++ {
		payload := TestPayload{
			ID:      i,
			Message: "test message",
		}
		err := publisher.Publish(ctx, "integration-channel", "integration:test", payload, correlationID)
		require.NoError(t, err)
	}

	// Collect all received messages
	receivedCount := 0
	timeout := time.After(10 * time.Second)

	for receivedCount < numMessages {
		select {
		case envelope := <-receivedMessages:
			assert.Equal(t, "integration:test", envelope.EventType)
			assert.Equal(t, "integration-service", envelope.ServiceName)
			assert.Equal(t, correlationID, envelope.CorrelationID)

			// Parse payload
			var payload TestPayload
			err := json.Unmarshal(envelope.Payload, &payload)
			require.NoError(t, err)
			assert.Equal(t, "test message", payload.Message)

			receivedCount++
		case <-timeout:
			t.Fatalf("timeout: received %d/%d messages", receivedCount, numMessages)
		}
	}

	assert.Equal(t, numMessages, receivedCount, "should receive all published messages")

	// Clean up
	cancel()
	redisClient.Del(context.Background(), "integration-channel")
}

// TestIntegration_ConsumerGroups tests load balancing with consumer groups
func TestIntegration_ConsumerGroups(t *testing.T) {
	redisClient := createTestRedisClient(t)
	defer redisClient.Close()

	logger := watermill.NewStdLogger(false, false)

	// Create publisher
	publisher, err := events.NewPublisher(redisClient, "cg-service", logger)
	require.NoError(t, err)
	defer publisher.Close()

	// Create two subscribers in the same consumer group
	subscriber1, err := events.NewSubscriber(redisClient, "cg-group", logger)
	require.NoError(t, err)
	defer subscriber1.Close()

	subscriber2, err := events.NewSubscriber(redisClient, "cg-group", logger)
	require.NoError(t, err)
	defer subscriber2.Close()

	// Track which subscriber received which message
	var mu sync.Mutex
	sub1Count := 0
	sub2Count := 0

	handler1 := func(ctx context.Context, envelope *events.Envelope) error {
		mu.Lock()
		sub1Count++
		mu.Unlock()
		return nil
	}

	handler2 := func(ctx context.Context, envelope *events.Envelope) error {
		mu.Lock()
		sub2Count++
		mu.Unlock()
		return nil
	}

	err = subscriber1.Subscribe("cg-channel", handler1)
	require.NoError(t, err)

	err = subscriber2.Subscribe("cg-channel", handler2)
	require.NoError(t, err)

	// Start both subscribers
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go func() {
		subscriber1.Run(ctx)
	}()

	go func() {
		subscriber2.Run(ctx)
	}()

	time.Sleep(300 * time.Millisecond)

	// Publish messages
	numMessages := 10
	for i := 0; i < numMessages; i++ {
		payload := map[string]int{"id": i}
		err := publisher.Publish(ctx, "cg-channel", "cg:test", payload, "")
		require.NoError(t, err)
		time.Sleep(50 * time.Millisecond) // Small delay between messages
	}

	// Wait for all messages to be processed
	time.Sleep(2 * time.Second)

	// Both subscribers should have processed some messages (load balancing)
	mu.Lock()
	totalReceived := sub1Count + sub2Count
	mu.Unlock()

	assert.Equal(t, numMessages, totalReceived, "all messages should be received")
	t.Logf("Subscriber 1: %d messages, Subscriber 2: %d messages", sub1Count, sub2Count)

	// Clean up
	cancel()
	redisClient.Del(context.Background(), "cg-channel")
}

// TestIntegration_CorrelationTracking tests correlation ID tracking across events
func TestIntegration_CorrelationTracking(t *testing.T) {
	redisClient := createTestRedisClient(t)
	defer redisClient.Close()

	logger := watermill.NewStdLogger(false, false)

	// Create publishers for different services
	service1Pub, err := events.NewPublisher(redisClient, "service-1", logger)
	require.NoError(t, err)
	defer service1Pub.Close()

	service2Pub, err := events.NewPublisher(redisClient, "service-2", logger)
	require.NoError(t, err)
	defer service2Pub.Close()

	// Create subscribers
	sub1, err := events.NewSubscriber(redisClient, "tracking-sub1", logger)
	require.NoError(t, err)
	defer sub1.Close()

	sub2, err := events.NewSubscriber(redisClient, "tracking-sub2", logger)
	require.NoError(t, err)
	defer sub2.Close()

	// Track correlation IDs
	receivedCorrelations := make(chan string, 2)

	// Service 1 receives event and publishes to service 2
	handler1 := func(ctx context.Context, envelope *events.Envelope) error {
		receivedCorrelations <- envelope.CorrelationID
		// Forward event with same correlation ID
		return service2Pub.Publish(ctx, "channel-2", "service2:event", map[string]string{"from": "service1"}, envelope.CorrelationID)
	}

	// Service 2 receives event
	handler2 := func(ctx context.Context, envelope *events.Envelope) error {
		receivedCorrelations <- envelope.CorrelationID
		return nil
	}

	err = sub1.Subscribe("channel-1", handler1)
	require.NoError(t, err)

	err = sub2.Subscribe("channel-2", handler2)
	require.NoError(t, err)

	// Start subscribers
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go func() {
		sub1.Run(ctx)
	}()

	go func() {
		sub2.Run(ctx)
	}()

	time.Sleep(200 * time.Millisecond)

	// Publish initial event
	originalCorrelationID := events.GenerateCorrelationID()
	err = service1Pub.Publish(ctx, "channel-1", "service1:event", map[string]string{"start": "true"}, originalCorrelationID)
	require.NoError(t, err)

	// Collect correlation IDs
	var correlations []string
	timeout := time.After(5 * time.Second)

	for len(correlations) < 2 {
		select {
		case corrID := <-receivedCorrelations:
			correlations = append(correlations, corrID)
		case <-timeout:
			t.Fatalf("timeout: received %d/2 correlation IDs", len(correlations))
		}
	}

	// Both services should have received the same correlation ID
	assert.Len(t, correlations, 2)
	assert.Equal(t, originalCorrelationID, correlations[0], "service 1 should receive original correlation ID")
	assert.Equal(t, originalCorrelationID, correlations[1], "service 2 should receive same correlation ID")

	// Clean up
	cancel()
	redisClient.Del(context.Background(), "channel-1", "channel-2")
}

// TestIntegration_IdempotencyMiddleware tests idempotency middleware
func TestIntegration_IdempotencyMiddleware(t *testing.T) {
	redisClient := createTestRedisClient(t)
	defer redisClient.Close()

	logger := watermill.NewStdLogger(false, false)

	// Create publisher
	publisher, err := events.NewPublisher(redisClient, "idem-service", logger)
	require.NoError(t, err)
	defer publisher.Close()

	// Create subscriber with idempotency middleware
	subscriber, err := events.NewSubscriber(redisClient, "idem-consumer", logger)
	require.NoError(t, err)
	defer subscriber.Close()

	// Add idempotency middleware
	subscriber.Router().AddMiddleware(
		events.WithIdempotency(redisClient, 10*time.Second, logger),
	)

	// Track handler calls
	handlerCalls := 0
	var mu sync.Mutex

	handler := func(ctx context.Context, envelope *events.Envelope) error {
		mu.Lock()
		handlerCalls++
		mu.Unlock()
		return nil
	}

	err = subscriber.Subscribe("idem-channel", handler)
	require.NoError(t, err)

	// Start subscriber
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go func() {
		subscriber.Run(ctx)
	}()

	time.Sleep(200 * time.Millisecond)

	// Generate idempotency key
	correlationID := events.GenerateCorrelationID()
	idempotencyKey := events.GenerateIdempotencyKey(correlationID, "idem:test")

	// Publish message with idempotency key
	metadata := map[string]interface{}{
		"idempotency_key": idempotencyKey,
	}

	payload := map[string]string{"data": "test"}
	err = publisher.PublishWithMetadata(ctx, "idem-channel", "idem:test", payload, correlationID, metadata)
	require.NoError(t, err)

	// Wait for processing
	time.Sleep(500 * time.Millisecond)

	// Publish the same message again (duplicate)
	err = publisher.PublishWithMetadata(ctx, "idem-channel", "idem:test", payload, correlationID, metadata)
	require.NoError(t, err)

	// Wait for processing
	time.Sleep(500 * time.Millisecond)

	// Handler should only be called once (idempotency)
	mu.Lock()
	finalCalls := handlerCalls
	mu.Unlock()

	assert.Equal(t, 1, finalCalls, "handler should only be called once due to idempotency")

	// Clean up
	cancel()
	redisClient.Del(context.Background(), "idem-channel")
}
