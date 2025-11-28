package events_test

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Helper to create a test Redis client
// Note: This requires a running Redis instance for integration tests
// For unit tests without Redis, we'd need to mock the Redis client
func createTestRedisClient(t *testing.T) *redis.Client {
	client := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
		DB:   15, // Use a separate DB for testing
	})

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()

	if err := client.Ping(ctx).Err(); err != nil {
		t.Skipf("Redis not available: %v", err)
	}

	// Clean up test DB
	client.FlushDB(context.Background())

	return client
}

// Helper to create a test logger
func createTestLogger(t *testing.T) watermill.LoggerAdapter {
	return watermill.NewStdLogger(false, false)
}

func TestNewPublisher(t *testing.T) {
	tests := []struct {
		name        string
		redisClient *redis.Client
		serviceName string
		wantErr     bool
		expectedErr error
	}{
		{
			name:        "nil redis client",
			redisClient: nil,
			serviceName: "test-service",
			wantErr:     true,
			expectedErr: events.ErrRedisUnavailable,
		},
		{
			name:        "empty service name",
			redisClient: createTestRedisClient(t),
			serviceName: "",
			wantErr:     true,
			expectedErr: events.ErrEmptyServiceName,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			logger := watermill.NewStdLogger(false, false)
			publisher, err := events.NewPublisher(tt.redisClient, tt.serviceName, logger)

			if tt.wantErr {
				assert.Error(t, err)
				assert.Nil(t, publisher)
				if tt.expectedErr != nil {
					assert.ErrorIs(t, err, tt.expectedErr)
				}
				return
			}

			require.NoError(t, err)
			require.NotNil(t, publisher)

			// Cleanup
			if publisher != nil {
				publisher.Close()
			}
		})
	}
}

func TestPublisher_Publish(t *testing.T) {
	redisClient := createTestRedisClient(t)
	defer redisClient.Close()

	logger := watermill.NewStdLogger(false, false)
	publisher, err := events.NewPublisher(redisClient, "test-service", logger)
	require.NoError(t, err)
	defer publisher.Close()

	tests := []struct {
		name          string
		channel       string
		eventType     string
		payload       interface{}
		correlationID string
		wantErr       bool
	}{
		{
			name:          "valid message",
			channel:       "test-channel",
			eventType:     "test:event",
			payload:       map[string]string{"key": "value"},
			correlationID: "corr-123",
			wantErr:       false,
		},
		{
			name:          "auto-generate correlation ID",
			channel:       "test-channel",
			eventType:     "test:event",
			payload:       map[string]string{"key": "value"},
			correlationID: "",
			wantErr:       false,
		},
		{
			name:          "invalid payload",
			channel:       "test-channel",
			eventType:     "test:event",
			payload:       make(chan int), // cannot be marshaled
			correlationID: "",
			wantErr:       true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ctx := context.Background()
			err := publisher.Publish(ctx, tt.channel, tt.eventType, tt.payload, tt.correlationID)

			if tt.wantErr {
				assert.Error(t, err)
				return
			}

			require.NoError(t, err)

			// Verify message was published by reading from Redis stream
			result, err := redisClient.XRead(ctx, &redis.XReadArgs{
				Streams: []string{tt.channel, "0"},
				Count:   1,
			}).Result()

			require.NoError(t, err)
			require.Len(t, result, 1)
			require.Len(t, result[0].Messages, 1)

			// Parse envelope from message
			msgData := result[0].Messages[0].Values["payload"].(string)
			var envelope events.Envelope
			err = json.Unmarshal([]byte(msgData), &envelope)
			require.NoError(t, err)

			// Verify envelope fields
			assert.Equal(t, events.EnvelopeVersion, envelope.Version)
			assert.NotEmpty(t, envelope.MessageID)
			assert.NotEmpty(t, envelope.CorrelationID)
			assert.Equal(t, tt.eventType, envelope.EventType)
			assert.Equal(t, "test-service", envelope.ServiceName)
			assert.NotEmpty(t, envelope.Payload)
			assert.WithinDuration(t, time.Now(), envelope.Timestamp, time.Second)

			if tt.correlationID != "" {
				assert.Equal(t, tt.correlationID, envelope.CorrelationID)
			}

			// Clean up stream
			redisClient.Del(ctx, tt.channel)
		})
	}
}

func TestPublisher_PublishWithMetadata(t *testing.T) {
	redisClient := createTestRedisClient(t)
	defer redisClient.Close()

	logger := watermill.NewStdLogger(false, false)
	publisher, err := events.NewPublisher(redisClient, "test-service", logger)
	require.NoError(t, err)
	defer publisher.Close()

	ctx := context.Background()
	channel := "test-channel"
	eventType := "test:event"
	payload := map[string]string{"key": "value"}
	correlationID := "corr-123"
	metadata := map[string]interface{}{
		"retry_count":     2,
		"timeout_seconds": 30,
		"idempotency_key": "idem-123",
	}

	err = publisher.PublishWithMetadata(ctx, channel, eventType, payload, correlationID, metadata)
	require.NoError(t, err)

	// Read from stream
	result, err := redisClient.XRead(ctx, &redis.XReadArgs{
		Streams: []string{channel, "0"},
		Count:   1,
	}).Result()

	require.NoError(t, err)
	require.Len(t, result, 1)
	require.Len(t, result[0].Messages, 1)

	// Parse envelope
	msgData := result[0].Messages[0].Values["payload"].(string)
	var envelope events.Envelope
	err = json.Unmarshal([]byte(msgData), &envelope)
	require.NoError(t, err)

	// Verify metadata
	assert.Equal(t, float64(2), envelope.Metadata["retry_count"]) // JSON unmarshals numbers as float64
	assert.Equal(t, float64(30), envelope.Metadata["timeout_seconds"])
	assert.Equal(t, "idem-123", envelope.Metadata["idempotency_key"])

	// Clean up
	redisClient.Del(ctx, channel)
}

func TestPublisher_Close(t *testing.T) {
	redisClient := createTestRedisClient(t)
	defer redisClient.Close()

	logger := watermill.NewStdLogger(false, false)
	publisher, err := events.NewPublisher(redisClient, "test-service", logger)
	require.NoError(t, err)

	// Close publisher
	err = publisher.Close()
	assert.NoError(t, err)

	// Try to publish after close
	ctx := context.Background()
	err = publisher.Publish(ctx, "test-channel", "test:event", map[string]string{"key": "value"}, "")
	assert.ErrorIs(t, err, events.ErrPublisherClosed)

	// Close again should be idempotent
	err = publisher.Close()
	assert.NoError(t, err)
}

func TestPublisher_ConcurrentPublish(t *testing.T) {
	redisClient := createTestRedisClient(t)
	defer redisClient.Close()

	logger := watermill.NewStdLogger(false, false)
	publisher, err := events.NewPublisher(redisClient, "test-service", logger)
	require.NoError(t, err)
	defer publisher.Close()

	// Publish 100 messages concurrently
	concurrency := 100
	done := make(chan error, concurrency)

	for i := 0; i < concurrency; i++ {
		go func(id int) {
			ctx := context.Background()
			payload := map[string]interface{}{"id": id}
			err := publisher.Publish(ctx, "test-channel", "test:event", payload, "")
			done <- err
		}(i)
	}

	// Wait for all goroutines
	for i := 0; i < concurrency; i++ {
		err := <-done
		assert.NoError(t, err)
	}

	// Verify all messages were published
	ctx := context.Background()
	result, err := redisClient.XLen(ctx, "test-channel").Result()
	require.NoError(t, err)
	assert.Equal(t, int64(concurrency), result)

	// Clean up
	redisClient.Del(ctx, "test-channel")
}
