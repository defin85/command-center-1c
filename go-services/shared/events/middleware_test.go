package events_test

import (
	"context"
	"encoding/json"
	"errors"
	"sync/atomic"
	"testing"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/ThreeDotsLabs/watermill/message"
	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestWithLogging(t *testing.T) {
	logger := watermill.NewStdLogger(false, false)

	// Create test envelope
	envelope, err := events.NewEnvelope("test:event", "test-service", map[string]string{"key": "value"}, "")
	require.NoError(t, err)

	envelopeBytes, err := json.Marshal(envelope)
	require.NoError(t, err)

	// Create test message
	msg := message.NewMessage("test-id", envelopeBytes)

	// Create handler with logging middleware
	handlerCalled := false
	handler := func(msg *message.Message) ([]*message.Message, error) {
		handlerCalled = true
		return nil, nil
	}

	wrappedHandler := events.WithLogging(logger)(handler)

	// Call wrapped handler
	_, err = wrappedHandler(msg)
	assert.NoError(t, err)
	assert.True(t, handlerCalled)
}

func TestWithRetry(t *testing.T) {
	logger := watermill.NewStdLogger(false, false)

	envelope, err := events.NewEnvelope("test:event", "test-service", map[string]string{"key": "value"}, "")
	require.NoError(t, err)

	envelopeBytes, err := json.Marshal(envelope)
	require.NoError(t, err)

	msg := message.NewMessage("test-id", envelopeBytes)

	tests := []struct {
		name           string
		maxRetries     int
		failUntil      int
		expectedCalls  int
		expectedError  bool
	}{
		{
			name:          "success on first attempt",
			maxRetries:    3,
			failUntil:     0,
			expectedCalls: 1,
			expectedError: false,
		},
		{
			name:          "success after 2 retries",
			maxRetries:    3,
			failUntil:     2,
			expectedCalls: 3,
			expectedError: false,
		},
		{
			name:          "fail all attempts",
			maxRetries:    2,
			failUntil:     10,
			expectedCalls: 3, // initial + 2 retries
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var attempts int32

			handler := func(msg *message.Message) ([]*message.Message, error) {
				currentAttempt := atomic.AddInt32(&attempts, 1)
				if int(currentAttempt) <= tt.failUntil {
					return nil, errors.New("temporary error")
				}
				return nil, nil
			}

			wrappedHandler := events.WithRetry(tt.maxRetries, 10*time.Millisecond, logger)(handler)

			_, err := wrappedHandler(msg)

			assert.Equal(t, int32(tt.expectedCalls), atomic.LoadInt32(&attempts))

			if tt.expectedError {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestWithRecovery(t *testing.T) {
	logger := watermill.NewStdLogger(false, false)

	envelope, err := events.NewEnvelope("test:event", "test-service", map[string]string{"key": "value"}, "")
	require.NoError(t, err)

	envelopeBytes, err := json.Marshal(envelope)
	require.NoError(t, err)

	msg := message.NewMessage("test-id", envelopeBytes)

	// Handler that panics
	handler := func(msg *message.Message) ([]*message.Message, error) {
		panic("test panic")
	}

	wrappedHandler := events.WithRecovery(logger)(handler)

	// Should recover from panic and return error
	_, err = wrappedHandler(msg)
	assert.Error(t, err)
	assert.ErrorIs(t, err, events.ErrHandlerPanic)
}

func TestWithTimeout(t *testing.T) {
	logger := watermill.NewStdLogger(false, false)

	envelope, err := events.NewEnvelope("test:event", "test-service", map[string]string{"key": "value"}, "")
	require.NoError(t, err)

	envelopeBytes, err := json.Marshal(envelope)
	require.NoError(t, err)

	tests := []struct {
		name          string
		timeout       time.Duration
		handlerDelay  time.Duration
		expectedError bool
	}{
		{
			name:          "completes within timeout",
			timeout:       500 * time.Millisecond,
			handlerDelay:  100 * time.Millisecond,
			expectedError: false,
		},
		{
			name:          "exceeds timeout",
			timeout:       100 * time.Millisecond,
			handlerDelay:  500 * time.Millisecond,
			expectedError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			msg := message.NewMessage("test-id", envelopeBytes)

			handler := func(msg *message.Message) ([]*message.Message, error) {
				time.Sleep(tt.handlerDelay)
				return nil, nil
			}

			wrappedHandler := events.WithTimeout(tt.timeout, logger)(handler)

			_, err := wrappedHandler(msg)

			if tt.expectedError {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestWithIdempotency(t *testing.T) {
	redisClient := createTestRedisClient(t)
	defer redisClient.Close()

	logger := watermill.NewStdLogger(false, false)

	// Create envelope with idempotency key
	correlationID := events.GenerateCorrelationID()
	idempotencyKey := events.GenerateIdempotencyKey(correlationID, "test:event")

	envelope, err := events.NewEnvelope("test:event", "test-service", map[string]string{"key": "value"}, correlationID)
	require.NoError(t, err)
	envelope.SetIdempotencyKey(idempotencyKey)

	envelopeBytes, err := json.Marshal(envelope)
	require.NoError(t, err)

	// Test first call (should process)
	t.Run("first call processes", func(t *testing.T) {
		msg := message.NewMessage("test-id-1", envelopeBytes)

		handlerCalled := false
		handler := func(msg *message.Message) ([]*message.Message, error) {
			handlerCalled = true
			return nil, nil
		}

		wrappedHandler := events.WithIdempotency(redisClient, 10*time.Second, logger)(handler)

		_, err := wrappedHandler(msg)
		assert.NoError(t, err)
		assert.True(t, handlerCalled, "handler should be called on first attempt")
	})

	// Test second call (should skip due to idempotency)
	t.Run("second call skips (idempotent)", func(t *testing.T) {
		msg := message.NewMessage("test-id-2", envelopeBytes)

		handlerCalled := false
		handler := func(msg *message.Message) ([]*message.Message, error) {
			handlerCalled = true
			return nil, nil
		}

		wrappedHandler := events.WithIdempotency(redisClient, 10*time.Second, logger)(handler)

		_, err := wrappedHandler(msg)
		assert.NoError(t, err)
		assert.False(t, handlerCalled, "handler should NOT be called on duplicate (idempotent)")
	})

	// Test handler error (should not mark as processed)
	t.Run("handler error does not mark as processed", func(t *testing.T) {
		// Create new envelope with different idempotency key
		newCorrelationID := events.GenerateCorrelationID()
		newIdempotencyKey := events.GenerateIdempotencyKey(newCorrelationID, "test:event2")

		newEnvelope, err := events.NewEnvelope("test:event2", "test-service", map[string]string{"key": "value"}, newCorrelationID)
		require.NoError(t, err)
		newEnvelope.SetIdempotencyKey(newIdempotencyKey)

		newEnvelopeBytes, err := json.Marshal(newEnvelope)
		require.NoError(t, err)

		msg := message.NewMessage("test-id-3", newEnvelopeBytes)

		var attempts int32
		handler := func(msg *message.Message) ([]*message.Message, error) {
			atomic.AddInt32(&attempts, 1)
			return nil, errors.New("handler error")
		}

		wrappedHandler := events.WithIdempotency(redisClient, 10*time.Second, logger)(handler)

		// First call (fails)
		_, err = wrappedHandler(msg)
		assert.Error(t, err)
		assert.Equal(t, int32(1), atomic.LoadInt32(&attempts))

		// Second call (should try again because first failed)
		msg2 := message.NewMessage("test-id-4", newEnvelopeBytes)
		_, err = wrappedHandler(msg2)
		assert.Error(t, err)
		assert.Equal(t, int32(2), atomic.LoadInt32(&attempts), "handler should be called again after failure")
	})

	// Clean up Redis keys
	ctx := context.Background()
	keys, _ := redisClient.Keys(ctx, "idempotency:*").Result()
	for _, key := range keys {
		redisClient.Del(ctx, key)
	}
}

func TestMiddleware_Chaining(t *testing.T) {
	redisClient := createTestRedisClient(t)
	defer redisClient.Close()

	logger := watermill.NewStdLogger(false, false)

	// Create envelope
	correlationID := events.GenerateCorrelationID()
	idempotencyKey := events.GenerateIdempotencyKey(correlationID, "test:event")

	envelope, err := events.NewEnvelope("test:event", "test-service", map[string]string{"key": "value"}, correlationID)
	require.NoError(t, err)
	envelope.SetIdempotencyKey(idempotencyKey)

	envelopeBytes, err := json.Marshal(envelope)
	require.NoError(t, err)

	msg := message.NewMessage("test-id", envelopeBytes)

	// Create handler that fails once then succeeds
	var attempts int32
	handler := func(msg *message.Message) ([]*message.Message, error) {
		currentAttempt := atomic.AddInt32(&attempts, 1)
		if currentAttempt == 1 {
			return nil, errors.New("first attempt fails")
		}
		return nil, nil
	}

	// Chain multiple middleware
	wrappedHandler := handler
	wrappedHandler = events.WithLogging(logger)(wrappedHandler)
	wrappedHandler = events.WithRecovery(logger)(wrappedHandler)
	wrappedHandler = events.WithRetry(2, 10*time.Millisecond, logger)(wrappedHandler)
	wrappedHandler = events.WithTimeout(5*time.Second, logger)(wrappedHandler)
	wrappedHandler = events.WithIdempotency(redisClient, 10*time.Second, logger)(wrappedHandler)

	// Call wrapped handler
	_, err = wrappedHandler(msg)
	assert.NoError(t, err, "should succeed after retry")
	assert.Equal(t, int32(2), atomic.LoadInt32(&attempts), "should retry once")

	// Clean up
	ctx := context.Background()
	keys, _ := redisClient.Keys(ctx, "idempotency:*").Result()
	for _, key := range keys {
		redisClient.Del(ctx, key)
	}
}
