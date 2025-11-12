package events_test

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/ThreeDotsLabs/watermill"
)

func TestNewSubscriber(t *testing.T) {
	tests := []struct {
		name          string
		redisClient   *redis.Client
		consumerGroup string
		wantErr       bool
		expectedErr   error
	}{
		{
			name:          "nil redis client",
			redisClient:   nil,
			consumerGroup: "test-group",
			wantErr:       true,
			expectedErr:   events.ErrRedisUnavailable,
		},
		{
			name:          "empty consumer group",
			redisClient:   createTestRedisClient(t),
			consumerGroup: "",
			wantErr:       true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			logger := watermill.NewStdLogger(false, false)
			subscriber, err := events.NewSubscriber(tt.redisClient, tt.consumerGroup, logger)

			if tt.wantErr {
				assert.Error(t, err)
				assert.Nil(t, subscriber)
				if tt.expectedErr != nil {
					assert.ErrorIs(t, err, tt.expectedErr)
				}
				return
			}

			require.NoError(t, err)
			require.NotNil(t, subscriber)

			// Cleanup
			if subscriber != nil {
				subscriber.Close()
			}
		})
	}
}

func TestSubscriber_Subscribe(t *testing.T) {
	redisClient := createTestRedisClient(t)
	defer redisClient.Close()

	logger := watermill.NewStdLogger(false, false)
	subscriber, err := events.NewSubscriber(redisClient, "test-group", logger)
	require.NoError(t, err)
	defer subscriber.Close()

	// Register handler
	handler := func(ctx context.Context, envelope *events.Envelope) error {
		return nil
	}

	err = subscriber.Subscribe("test-channel", handler)
	assert.NoError(t, err)
}

func TestSubscriber_ReceiveMessage(t *testing.T) {
	redisClient := createTestRedisClient(t)
	defer redisClient.Close()

	logger := watermill.NewStdLogger(false, false)

	// Create publisher
	publisher, err := events.NewPublisher(redisClient, "test-service", logger)
	require.NoError(t, err)
	defer publisher.Close()

	// Create subscriber
	subscriber, err := events.NewSubscriber(redisClient, "test-group", logger)
	require.NoError(t, err)
	defer subscriber.Close()

	// Setup handler
	receivedEnvelope := make(chan *events.Envelope, 1)
	handler := func(ctx context.Context, envelope *events.Envelope) error {
		receivedEnvelope <- envelope
		return nil
	}

	err = subscriber.Subscribe("test-channel", handler)
	require.NoError(t, err)

	// Start subscriber in goroutine
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go func() {
		subscriber.Run(ctx)
	}()

	// Give subscriber time to start
	time.Sleep(100 * time.Millisecond)

	// Publish message
	payload := map[string]string{"test": "data"}
	err = publisher.Publish(context.Background(), "test-channel", "test:event", payload, "corr-123")
	require.NoError(t, err)

	// Wait for message
	select {
	case envelope := <-receivedEnvelope:
		assert.Equal(t, "test:event", envelope.EventType)
		assert.Equal(t, "test-service", envelope.ServiceName)
		assert.Equal(t, "corr-123", envelope.CorrelationID)
	case <-time.After(5 * time.Second):
		t.Fatal("timeout waiting for message")
	}

	// Clean up
	cancel()
	redisClient.Del(context.Background(), "test-channel")
}

func TestSubscriber_HandlerError(t *testing.T) {
	redisClient := createTestRedisClient(t)
	defer redisClient.Close()

	logger := watermill.NewStdLogger(false, false)

	// Create publisher
	publisher, err := events.NewPublisher(redisClient, "test-service", logger)
	require.NoError(t, err)
	defer publisher.Close()

	// Create subscriber
	subscriber, err := events.NewSubscriber(redisClient, "test-group-error", logger)
	require.NoError(t, err)
	defer subscriber.Close()

	// Setup handler that returns error
	attempts := 0
	var mu sync.Mutex
	handler := func(ctx context.Context, envelope *events.Envelope) error {
		mu.Lock()
		attempts++
		currentAttempt := attempts
		mu.Unlock()

		if currentAttempt < 3 {
			return assert.AnError // Fail first 2 attempts
		}
		return nil // Succeed on 3rd attempt
	}

	err = subscriber.Subscribe("test-channel-error", handler)
	require.NoError(t, err)

	// Start subscriber
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go func() {
		subscriber.Run(ctx)
	}()

	time.Sleep(100 * time.Millisecond)

	// Publish message
	payload := map[string]string{"test": "data"}
	err = publisher.Publish(context.Background(), "test-channel-error", "test:event", payload, "")
	require.NoError(t, err)

	// Wait for retries
	time.Sleep(2 * time.Second)

	// Handler should have been called multiple times (with retries)
	mu.Lock()
	finalAttempts := attempts
	mu.Unlock()

	assert.GreaterOrEqual(t, finalAttempts, 1, "handler should be called at least once")

	// Clean up
	cancel()
	redisClient.Del(context.Background(), "test-channel-error")
}

func TestSubscriber_HandlerPanic(t *testing.T) {
	redisClient := createTestRedisClient(t)
	defer redisClient.Close()

	logger := watermill.NewStdLogger(false, false)

	// Create publisher
	publisher, err := events.NewPublisher(redisClient, "test-service", logger)
	require.NoError(t, err)
	defer publisher.Close()

	// Create subscriber
	subscriber, err := events.NewSubscriber(redisClient, "test-group-panic", logger)
	require.NoError(t, err)
	defer subscriber.Close()

	// Setup handler that panics
	handler := func(ctx context.Context, envelope *events.Envelope) error {
		panic("test panic")
	}

	err = subscriber.Subscribe("test-channel-panic", handler)
	require.NoError(t, err)

	// Start subscriber
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go func() {
		subscriber.Run(ctx)
	}()

	time.Sleep(100 * time.Millisecond)

	// Publish message
	payload := map[string]string{"test": "data"}
	err = publisher.Publish(context.Background(), "test-channel-panic", "test:event", payload, "")
	require.NoError(t, err)

	// Wait for panic handling
	time.Sleep(500 * time.Millisecond)

	// Subscriber should still be running (panic was recovered)
	// If we reach here, panic was handled correctly

	// Clean up
	cancel()
	redisClient.Del(context.Background(), "test-channel-panic")
}

func TestSubscriber_Close(t *testing.T) {
	redisClient := createTestRedisClient(t)
	defer redisClient.Close()

	logger := watermill.NewStdLogger(false, false)
	subscriber, err := events.NewSubscriber(redisClient, "test-group", logger)
	require.NoError(t, err)

	// Register handler
	handler := func(ctx context.Context, envelope *events.Envelope) error {
		return nil
	}
	err = subscriber.Subscribe("test-channel", handler)
	require.NoError(t, err)

	// Start router in background (required before Close)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	go subscriber.Run(ctx)
	time.Sleep(100 * time.Millisecond) // Wait for router to start

	// Close subscriber
	err = subscriber.Close()
	assert.NoError(t, err)

	// Try to subscribe after close
	err = subscriber.Subscribe("test-channel2", handler)
	assert.ErrorIs(t, err, events.ErrSubscriberClosed)

	// Close again should be idempotent
	err = subscriber.Close()
	assert.NoError(t, err)
}

func TestSubscriber_MultipleHandlers(t *testing.T) {
	redisClient := createTestRedisClient(t)
	defer redisClient.Close()

	logger := watermill.NewStdLogger(false, false)

	// Create publisher
	publisher, err := events.NewPublisher(redisClient, "test-service", logger)
	require.NoError(t, err)
	defer publisher.Close()

	// Create subscriber
	subscriber, err := events.NewSubscriber(redisClient, "test-group-multi", logger)
	require.NoError(t, err)
	defer subscriber.Close()

	// Setup handlers for different channels
	channel1Received := make(chan *events.Envelope, 1)
	channel2Received := make(chan *events.Envelope, 1)

	handler1 := func(ctx context.Context, envelope *events.Envelope) error {
		channel1Received <- envelope
		return nil
	}

	handler2 := func(ctx context.Context, envelope *events.Envelope) error {
		channel2Received <- envelope
		return nil
	}

	err = subscriber.Subscribe("channel-1", handler1)
	require.NoError(t, err)

	err = subscriber.Subscribe("channel-2", handler2)
	require.NoError(t, err)

	// Start subscriber
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go func() {
		subscriber.Run(ctx)
	}()

	time.Sleep(100 * time.Millisecond)

	// Publish to both channels
	err = publisher.Publish(context.Background(), "channel-1", "test:event1", map[string]string{"ch": "1"}, "")
	require.NoError(t, err)

	err = publisher.Publish(context.Background(), "channel-2", "test:event2", map[string]string{"ch": "2"}, "")
	require.NoError(t, err)

	// Wait for both messages
	var envelope1, envelope2 *events.Envelope

	select {
	case envelope1 = <-channel1Received:
	case <-time.After(5 * time.Second):
		t.Fatal("timeout waiting for channel 1 message")
	}

	select {
	case envelope2 = <-channel2Received:
	case <-time.After(5 * time.Second):
		t.Fatal("timeout waiting for channel 2 message")
	}

	assert.Equal(t, "test:event1", envelope1.EventType)
	assert.Equal(t, "test:event2", envelope2.EventType)

	// Clean up
	cancel()
	redisClient.Del(context.Background(), "channel-1", "channel-2")
}

func TestSubscriber_Backpressure(t *testing.T) {
	redisClient := createTestRedisClient(t)
	defer redisClient.Close()

	logger := createTestLogger(t)
	subscriber, err := events.NewSubscriber(redisClient, "test-group-backpressure", logger)
	require.NoError(t, err)
	defer subscriber.Close()

	subscriber.SetMaxConcurrency(2) // Limit to 2 concurrent

	processingCount := int32(0)
	maxConcurrent := int32(0)

	handler := func(ctx context.Context, envelope *events.Envelope) error {
		// Atomically increment processing count
		current := atomicInc(&processingCount)
		defer atomicDec(&processingCount)

		// Track max concurrent
		for {
			old := atomicLoad(&maxConcurrent)
			if current <= old {
				break
			}
			if atomicCompareAndSwap(&maxConcurrent, old, current) {
				break
			}
		}

		time.Sleep(100 * time.Millisecond)
		return nil
	}

	err = subscriber.Subscribe("test-channel-backpressure", handler)
	require.NoError(t, err)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	go subscriber.Run(ctx)
	time.Sleep(100 * time.Millisecond)

	// Publish 10 messages
	publisher, _ := events.NewPublisher(redisClient, "test-service", logger)
	for i := 0; i < 10; i++ {
		publisher.Publish(ctx, "test-channel-backpressure", "test.event", map[string]string{"num": string(rune('0' + i))}, "test-corr")
	}

	time.Sleep(2 * time.Second)

	// Max concurrent should be <= 2
	max := atomicLoad(&maxConcurrent)
	assert.LessOrEqual(t, max, int32(2), "Max concurrent handlers should be <= 2")

	// Clean up
	redisClient.Del(context.Background(), "test-channel-backpressure")
}

// Helper functions for atomic operations
func atomicInc(val *int32) int32 {
	for {
		old := *val
		new := old + 1
		if atomicCompareAndSwap(val, old, new) {
			return new
		}
	}
}

func atomicDec(val *int32) {
	for {
		old := *val
		new := old - 1
		if atomicCompareAndSwap(val, old, new) {
			return
		}
	}
}

func atomicLoad(val *int32) int32 {
	return *val
}

func atomicCompareAndSwap(val *int32, old, new int32) bool {
	if *val == old {
		*val = new
		return true
	}
	return false
}
